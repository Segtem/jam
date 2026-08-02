"""Registro de herramientas de Jam — la ÚNICA definición de cada capacidad (params + acción + oráculo).

Los front-ends (el panel de botones y la consola DSL) sólo resuelven el asset y los params, y llaman
acá. Cada herramienta spawnea en el nivel y devuelve el texto del veredicto de SU oráculo. Escalar =
agregar una entrada a REGISTRO (una fn param-driven), sin tocar UMG ni la consola.
"""

from __future__ import annotations

import unreal

# Las salidas del material salen del IR (puro) y no de una lista repetida acá: el desplegable del
# nodo `material_output` y lo que el verificador acepta son la MISMA lista, por construcción.
from .shader import SALIDAS as _SALIDAS_MATERIAL


# Salidas de Content producidas durante la ejecución actual de un nodo transformador. Compile usa
# rutas finales deterministas; Run necesita la ruta temporal REAL para alimentar al siguiente nodo.
_RUNTIME_ASSET_OUTPUTS: dict[str, str] = {}
# Datos ricos que sólo viven durante una evaluación del Graph (``S`` = CurvePath, ``N[]`` = serie y
# ``M`` = DynamicMesh). Nunca cruzan la API UI↔Python ni se serializan: cada nodo los consume aguas abajo.
_RUNTIME_DATA_OUTPUTS: dict[str, object] = {}


def limpiar_asset_producido_runtime(verbo: str) -> None:
    _RUNTIME_ASSET_OUTPUTS.pop(str(verbo), None)
    _RUNTIME_DATA_OUTPUTS.pop(str(verbo), None)


def asset_producido_runtime(verbo: str, asset_entrada) -> str | None:
    return _RUNTIME_ASSET_OUTPUTS.get(str(verbo))


def dato_producido_runtime(verbo: str, entrada=None):
    """Salida real de un nodo: dato rico ``M`` o ruta ``A`` creada durante Run."""
    key = str(verbo)
    if key in _RUNTIME_DATA_OUTPUTS:
        return _RUNTIME_DATA_OUTPUTS[key]
    return _RUNTIME_ASSET_OUTPUTS.get(key)


def _sub():
    return unreal.get_editor_subsystem(unreal.EditorActorSubsystem)


def _corto(ruta: str) -> str:
    return ruta.rsplit(".", 1)[-1] if ruta else "asset"


def _slug_preset(nombre: str) -> str:
    import re
    return re.sub(r"[^A-Za-z0-9]+", "_", nombre).strip("_") or "JamPCG"


# ---- herramientas (asset = ObjectPath; el resto, params con default) ----
# Nota: los NOMBRES de programación (verbos + params) están en inglés (API/CLI); la PROSA (docs y
# veredictos del oráculo) queda en español. Los módulos internos (place/scatter/pared…) siguen en
# español y estas funciones traducen los kwargs.

def t_asset(asset, *, name="") -> str:
    """Content: fija el ASSET ACTIVO de la sesión. No spawnea nada — es una selección. Lo usan por
    igual la ventana de Content (clic en una miniatura), la línea de comando (`asset SM_Foo`) y el
    nodo «asset» del grafo (que se lo pasa aguas abajo por el cable). `name` es el mismo nombre que
    se tipea en el campo del nodo; quien llama ya lo resolvió a ObjectPath en `asset`."""
    from . import session
    session.set_asset(asset)
    # El veredicto del pivote sale SOLO al elegir el asset: es una propiedad del asset, no una tarea
    # que uno tenga que acordarse de correr. Así te enterás de que no tilea ANTES de repetirlo 200 veces.
    return f"ASSET ACTIVO ✓ — {session.nombre()}  ({asset})\n{t_pivot(asset)}"


def t_pick(asset, *, name="") -> str:
    """Content: toma como asset activo lo que esté SELECCIONADO en el Content Browser de Unreal.
    Es el puente con el flujo normal del editor: elegís la malla donde siempre y Jam la usa."""
    from . import library, session
    sel = library.seleccion_ue()
    if not sel:
        return ("no hay ninguna StaticMesh seleccionada en el Content Browser de Unreal — "
                "elegí una ahí y volvé a apretar.")
    session.set_asset(sel[0]["ruta"], sel[0]["nombre"])
    extra = f"  (+{len(sel) - 1} más seleccionadas)" if len(sel) > 1 else ""
    return (f"ASSET ACTIVO ✓ (selección de Unreal) — {sel[0]['nombre']}{extra}\n"
            f"{t_pivot(sel[0]['ruta'])}")


def t_pcg(asset, *, area=1600.0, count=200, density=0.0, view=True, name="JamPCG", preset="") -> str:
    """Realiza un scatter con el PCG NATIVO de Unreal (HISM, no-destructivo, regenerable) en vez de
    actores sueltos — el último eslabón del pipeline (tools → presets → PCG usando presets). Con
    `preset` toma sus params (área/cantidad/asset); si no, usa el asset activo. Arma el grafo
    (superficie→sampler→spawner), pone un PCGVolume en el punto de mira y lo genera (asíncrono)."""
    from . import pcg
    nombre = name
    # PCG USANDO PRESETS: si se da un preset de scatter, sus params dirigen la realización.
    if preset:
        from . import dsl, preset as pre
        p = pre.cargar(preset)
        if not p:
            raise RuntimeError(f"preset «{preset}» no encontrado")
        if p.get("kind") == "tool":
            r = dsl.parsear(p.get("command", ""))
            kw, _ = dsl.coaccionar(r["verbo"], r["params"])
            area = float(kw.get("area", area))
            count = int(kw.get("count", count))
            if r["asset"]:
                asset = r["asset"]
        nombre = _slug_preset(preset)
    r = pcg.realizar(asset, nombre=nombre, area=area, count=int(count), density=density, view=view)
    if "error" in r:
        raise RuntimeError(r["error"])
    from . import ue
    ue.seleccionar([r["volumen"]])
    loc = r["volumen"].get_actor_location()
    return (f"PCG realizado ✓ — «{r['volumen'].get_actor_label()}» ({r['assets']} asset(s), "
            f"{r['density']} pts/m², {r['cables']}/4 cables) en ({loc.x:.0f}, {loc.y:.0f}), "
            f"área {area:.0f}cm. Genera asíncrono (HISM); F para volar hasta él.")


def t_gizmo(asset, *, on=True) -> str:
    """Enciende/apaga el gizmo que marca DÓNDE ESTÁ PARADO Jam en el viewport (el punto de mira,
    que es donde coloca `place`) + la huella del asset activo."""
    if asset:
        from . import session
        session.set_asset(asset)
    from . import gizmo
    return gizmo.encender() if on else gizmo.apagar()


def t_ghost(asset, *, on=True) -> str:
    """Enciende/apaga el FANTASMA: la malla del asset activo siguiendo el punto de mira, para ver
    qué y de qué tamaño va a caer antes de colocarlo."""
    if asset:
        from . import session
        session.set_asset(asset)
    from . import ghost
    return ghost.encender() if on else ghost.apagar()


def t_pivot(asset, *, anchor="") -> str:
    """Diagnóstico del PIVOTE del asset: dónde está dentro de su propia caja y si el asset sirve
    para repetir tal cual o hay que colocarlo por un ancla. No toca la escena: mide la malla en su
    espacio local, donde el pivote es el origen por definición."""
    import unreal as U

    from . import library, pivot as pv
    from .geometry import AABB, Vec3
    malla = library.cargar_malla(asset) if isinstance(asset, str) else asset
    if malla is None:
        return f"no pude cargar {_corto(asset)}"
    caja = malla.get_bounding_box()
    mn, mx = caja.min, caja.max
    aabb = AABB(Vec3((mx.x + mn.x) / 2.0, (mx.y + mn.y) / 2.0, (mx.z + mn.z) / 2.0),
                Vec3((mx.x - mn.x) / 2.0, (mx.y - mn.y) / 2.0, (mx.z - mn.z) / 2.0))
    from . import kit, store
    store.cargar_kit()
    ruta = asset if isinstance(asset, str) else malla.get_path_name()
    texto = pv.diagnostico_texto(malla.get_name(), aabb, Vec3(0.0, 0.0, 0.0))
    if kit.normalizado(ruta):
        texto += f"\n    NORMALIZADO en el kit: se agarra por «{kit.ancla(ruta)}» ✓"
    elif not pv.diagnostico(aabb, Vec3(0.0, 0.0, 0.0))["tileable"]:
        texto += "\n    → «normalize» lo arregla de una vez para todas las herramientas"
    if anchor:
        if anchor not in pv.ANCLAS:
            return f"{texto}\n    ancla «{anchor}» desconocida — hay: {', '.join(pv.ANCLAS)}"
        p = pv.punto_ancla(aabb, anchor, Vec3(0.0, 0.0, 0.0))
        texto += (f"\n    ancla «{anchor}» = ({p.x:.0f}, {p.y:.0f}, {p.z:.0f}) respecto del pivote "
                  f"→ «place anchor={anchor}» corrige eso al colocar")
    return texto


def t_normalize(asset, *, anchor="", scene=True) -> str:
    """NORMALIZA el pivote del asset: anota en el kit por qué punto hay que agarrarlo, y arregla las
    piezas de ese asset que ya estén en el nivel. Se hace UNA vez por asset y desde entonces todas
    las herramientas lo tratan normalizado. No toca la malla del disco.

    Sin `anchor`, elige solo: si el pivote ya está en la base y centrado no hace nada; si está en una
    esquina o fuera de la malla, lo normaliza a `base` (el punto natural de agarre)."""
    from . import kit, pivot as pv, place, store, ue
    from .geometry import AABB, Vec3
    from . import library
    ruta = asset if isinstance(asset, str) else (asset.get_path_name() if asset else "")
    malla = library.cargar_malla(ruta) if ruta else None
    if malla is None:
        return f"no pude cargar {_corto(ruta)}"

    caja = malla.get_bounding_box()
    mn, mx = caja.min, caja.max
    aabb = AABB(Vec3((mx.x + mn.x) / 2.0, (mx.y + mn.y) / 2.0, (mx.z + mn.z) / 2.0),
                Vec3((mx.x - mn.x) / 2.0, (mx.y - mn.y) / 2.0, (mx.z - mn.z) / 2.0))
    diag = pv.diagnostico(aabb, Vec3(0.0, 0.0, 0.0))
    elegida = anchor or kit.sugerir(diag)
    if elegida not in pv.ANCLAS:
        return f"ancla «{elegida}» desconocida — hay: {', '.join(pv.ANCLAS)}"

    kit.set_ancla(ruta, elegida)
    guardado = store.guardar_kit()

    # arreglar lo que ya está en el nivel: el agarre de cada pieza de ese asset
    tocados = 0
    if scene:
        objetivo = malla.get_name()
        for a in ue.actores_nivel():
            try:
                comp = a.static_mesh_component
                if comp and comp.static_mesh and comp.static_mesh.get_name() == objetivo:
                    tocados += 1 if place.normalizar_agarre(a, elegida) else 0
            except Exception:  # noqa: BLE001
                continue

    ux, uy, uz = diag["u"]
    antes = (f"pivote original: x {ux * 100:.0f}%, y {uy * 100:.0f}%, z {uz * 100:.0f}% de su caja"
             + (" (FUERA de la malla)" if diag["fuera"] else ""))
    if elegida == "pivot":
        return (f"[{malla.get_name()}] YA ESTABA NORMALIZADO ✓ — {antes}. Se agarra por su propio "
                f"pivote; no hay nada que corregir.")
    return (f"[{malla.get_name()}] NORMALIZADO ✓ → se agarra por «{elegida}» — {antes}.\n"
            f"    {tocados} piezas del nivel reajustadas · todas las tools usan esta ancla"
            + (f" · guardado en {guardado}" if guardado else " · (no pude guardarlo en disco)"))


def t_pivot_set(asset, *, to="base") -> str:
    """Mueve el PIVOTE de los actores SELECCIONADOS al ancla `to` (base/center/top/corner…), como los
    «Center/Bottom/Top Pivot» de Dash pero con las 10 anclas. Toca el `pivot_offset` DEL ACTOR (lo
    que agarra el gizmo del editor), no la malla: el asset del disco queda intacto."""
    import unreal as U

    from . import pivot as pv, ue
    from .geometry import Vec3
    if to not in pv.ANCLAS:
        return f"ancla «{to}» desconocida — hay: {', '.join(pv.ANCLAS)}"
    from . import place
    sel = ue._sub().get_selected_level_actors()
    if not sel:
        return "no hay actores seleccionados en el nivel: elegí uno y volvé a intentar."
    n = sum(1 for a in sel if place.normalizar_agarre(a, to))
    return (f"PIVOTE → «{to}» ✓ en {n} de {len(sel)} actores (pivot_offset del actor; la malla del "
            f"disco no se toca).")


def t_place(asset, *, points=None, x=0.0, y=0.0, z=0.0, view=True, surface=True,
            anchor="base", sink=0.0, align=False, physics=False, yaw=0.0, scale=1.0,
            scale_min=1.0, scale_max=1.0) -> str:
    """Coloca un ladrillo en relación a su entorno: `view`=en el punto de mira del viewport (x/y/z
    son offset), `surface`=raycast al piso, `anchor`=por qué punto de la pieza se coloca (base,
    center, corner, xmin…), `sink`=cuántos cm hundirla en la superficie (para que una roca no se vea
    apoyada como una calcomanía), `align`=orientar a la normal, `physics`=asentar por caída, `yaw`/`scale`.
    El oráculo del entorno verifica APOYADO sobre una superficie (gap≈0) + SIN CLAVARSE con los
    vecinos (geometría, no el soporte ni el landscape)."""
    from . import place

    # UN nodo pone cosas en el mundo, y es éste. Con puntos coloca uno por punto; sin puntos, uno
    # en sus coordenadas. Es el mismo verbo porque es la misma pregunta —«poné ESTO acá»— y la
    # única diferencia es cuántos «acá» hay.
    if points:
        return _place_en_puntos(asset, points, anchor=anchor, sink=sink, align=align,
                                scale_min=float(scale_min), scale_max=float(scale_max))

    actor = place.colocar(asset, (x, y, z - sink), (0.0, 0.0, yaw), (scale, scale, scale),
                          view=view, surface=surface, anchor=anchor, align=align, physics=physics)
    if actor is None:
        return f"no se pudo colocar {_corto(asset)}"
    return _veredicto_entorno(actor)


def _place_en_puntos(asset, puntos, *, anchor, sink, align, scale_min, scale_max) -> str:
    """Coloca el asset en cada punto, con el dedup por HUELLA REAL y el oráculo doble.

    El dedup vive acá y no en `scatter` a propósito: para saber si dos piezas se pisan hay que
    conocer su tamaño, y el tamaño lo trae el ASSET. Ponerlo en el scatter obligaba a cablearle un
    asset que no usa para nada más — el asset entraba, salía convertido en punto, y había que
    volver a traerlo. Un nodo que pide algo que no necesita ensucia el diagrama y confunde sobre
    qué hace.
    """
    from . import scatter, ue

    mallas = scatter._mallas_de([asset] if isinstance(asset, str) else asset)
    if not mallas:
        mallas = [asset] if asset is not None else []
    if not mallas:
        return "PLACE — no sé QUÉ colocar: cableá un asset."

    radios = [ue.radio_de_malla(m) * max(scale_min, scale_max) for m in mallas]
    radio_por = [radios[p.seed % len(mallas)] for p in puntos]
    from . import scatter_core as sc
    vivos, pisados = sc.dedup_por_radio(list(puntos), radio_por, 1.0)

    actores = scatter.instanciar_puntos(
        vivos, mallas, scale_min=scale_min, scale_max=scale_max, sink=sink,
        anchor=anchor, align=align, etiqueta="Jam_place")
    ue.seleccionar(actores)

    xs = [p.pos.x for p in vivos] or [0.0]
    ys = [p.pos.y for p in vivos] or [0.0]
    centro = ((min(xs) + max(xs)) / 2.0, (min(ys) + max(ys)) / 2.0)
    semi = (max(1.0, (max(xs) - min(xs)) / 2.0), max(1.0, (max(ys) - min(ys)) / 2.0))
    existentes = ue.vecinos_en_zona(centro, semi, ignorar=actores)
    oraculo = ue.scatter_texto(actores, centro, semi, len(actores), existentes=existentes)
    extra = f" · {len(pisados)} evitados por huella" if pisados else ""
    return (f"PLACE \u2713 \u2014 {len(actores)} en {len(puntos)} punto(s){extra}\n{oraculo}")


def _veredicto_entorno(actor) -> str:
    """Oráculo de PLACE: ¿el ladrillo quedó bien en su entorno? APOYADO sobre superficie (raycast,
    gap≈0, con su pendiente) + SIN CLAVARSE con vecinos reales (excluye soporte, landscape y no-geometría)."""
    import unreal as U
    from . import geometry, physics, ue
    aabb = ue.aabb(actor)
    base_z = aabb.origin.z - aabb.extent.z

    # 1) superficie debajo (raycast desde la base, ignorando el propio actor)
    hit = ue.raycast(aabb.origin.x, aabb.origin.y, desde=base_z + 20.0, ignorar=[actor])
    soporte = hit["actor"] if hit["hit"] else None
    if not hit["hit"]:
        apoyo = "SIN SUELO ✗ — flota (no hay superficie debajo)"
    else:
        gap = base_z - hit["punto"].z
        pend = 90.0 - _grados_normal(hit["normal"])
        apoyo = (f"APOYADO ✓ sobre «{soporte}» (pendiente {pend:.0f}°)" if abs(gap) <= 5.0
                 else f"MAL APOYADO ✗ — {gap:+.1f}cm de «{soporte}»")

    # 2) vecinos = geometría real, sin el propio, sin el soporte, sin terreno ni proxies
    def es_terreno_o_proxy(a) -> bool:
        """Landscape y HLOD no son «vecinos»: el landscape es el suelo (ya lo mide el apoyo) y los
        HLOD de World Partition son COPIAS de baja resolución de lo que ya está en el nivel —
        contarlos daba «CLAVA ✗» contra todo en cualquier mapa de mundo abierto."""
        try:
            if isinstance(a, U.LandscapeProxy):
                return True
        except Exception:  # noqa: BLE001
            pass
        return "HLOD" in type(a).__name__ or a.get_actor_label().startswith("HLOD")

    from . import ghost
    vecinos = [a for a in ue.actores_nivel()
               if a != actor and physics._es_geometria(a) and not es_terreno_o_proxy(a)
               and ghost.TAG not in ue.tags(a)   # el fantasma está justo donde colocás: no es vecino
               and a.get_actor_label() != soporte]
    r = ue.placement(actor, [actor, *vecinos])
    if r["interpenetra"]:
        det = ", ".join(f"{n} ({d}cm)" for n, d in r["interpenetra"])
        clava = f"CLAVA ✗ con {det}"
    else:
        clava = "sin clavarse con vecinos ✓"

    ok = hit["hit"] and (soporte is None or abs(base_z - hit["punto"].z) <= 5.0) and not r["interpenetra"]
    cab = f"[{actor.get_actor_label()}] {'BIEN COLOCADO ✓' if ok else 'REVISAR ✗'}"
    return f"{cab} — {apoyo} · {clava}\n{_donde(actor)}"


def _donde(actor) -> str:
    """Coordenadas + nivel de lo que se acaba de colocar. Que el veredicto diga DÓNDE quedó es lo que
    evita el «dice confirmado pero no lo veo»: con eso lo buscás en el Outliner o volás con F.
    Y si quedó fuera de cuadro, lo AVISA — una pieza invisible se siente igual que ninguna pieza."""
    from . import ue
    loc = actor.get_actor_location()
    try:
        nivel = actor.get_level().get_outer().get_name()
    except Exception:  # noqa: BLE001
        nivel = "?"
    linea = (f"    en ({loc.x:.0f}, {loc.y:.0f}, {loc.z:.0f}) del nivel «{nivel}» — "
             f"seleccionado en el editor (F en el viewport para volar hasta él)")

    cam = ue.camara()
    if cam is not None:
        c = cam["loc"]
        d = ((loc.x - c.x) ** 2 + (loc.y - c.y) ** 2 + (loc.z - c.z) ** 2) ** 0.5
        if d > 5000.0:   # más de 50 m: no lo vas a ver, no importa cuánto insistas
            linea += (f"\n    ⚠ quedó a {d / 100.0:.0f} m de la cámara — NO lo vas a ver en pantalla. "
                      f"Usá «view=true» (coloca donde mirás) o apretá F.")
    return linea


def _grados_normal(normal) -> float:
    import math
    z = max(-1.0, min(1.0, normal.z))
    return math.degrees(math.asin(z))   # 90° = normal vertical (piso plano)


# El renglón que le dice a alguien qué falta cuando un verbo calcula pero no coloca. Es una
# constante y no un literal suelto para que se pueda EXIGIR desde un test: un verbo que dejó de
# hacer lo que hacía y no lo dice se siente exactamente como un botón roto.
# Verbos cuyo nodo nace CON el punto de mira ya escrito en estos params, en orden (x, y, z).
#
# Es la respuesta a que un grafo tiene que ser reproducible Y lo que uno coloca tiene que aparecer
# donde está mirando. Leer la cámara en cada Run da lo segundo y rompe lo primero; capturarla al
# crear el nodo da las dos, y deja las coordenadas a la vista para editarlas.
CAPTURA_LA_MIRA = {
    "place": ("x", "y", "z"),
    "scatter": ("x", "y"),
}
# `pcg` y `fracture` no entran: no tienen params de posición donde escribirla. Con `view` apagado
# nacen en el origen — está anotado como pendiente, no disimulado con una captura que no existe.


PISTA_INSTANCE = "  \u2192 encha\u00falo al pin `points` de un `place` para colocarlos"


def necesita_instanciar(verbo: str) -> bool:
    """¿Este verbo describe DÓNDE y necesita que otro lo vuelva escena?

    Se decide por el TIPO de salida y no por una lista de nombres: el día que otro verbo pase a
    producir puntos, la Dash Bar lo compone sola en vez de dejar de colocar en silencio.
    """
    return REGISTRO.get(verbo, {}).get("out_name") == "P"


def t_scatter(_input=None, *, count=24, area=800.0, x=0.0, y=0.0, pattern="poisson", spacing=0.0, rings=3,
              surface=True, align=False, slope_max=90.0, height_min=0.0, height_max=0.0,
              noise=0.0, density=1.0, scale_min=1.0, scale_max=1.0, spread=1.0,
              sink=0.0, anchor="", view=True, seed=7) -> str:
    """Surface Scatter con máscaras componibles (el «Scatter Suite» de Dash): reparte sobre la
    superficie real (raycast) con patrón poisson/grid/radial, filtra por pendiente/altura/ruido/
    densidad, y varía escala y rotación. `spacing`=0 usa la HUELLA REAL de la malla (nada se pisa);
    `spread`=factor de separación; `view`=centra el área en el punto de mira. El oráculo verifica
    cantidad, contención, no-clavado y cobertura."""
    from . import scatter, ue
    count, seed = int(count), int(seed)

    # centrar el área donde mirás (como place view), para no scatterear en el origen del mundo
    # Sin `view` (que es el default EN EL GRAFO, para que dos Run den lo mismo), el área se centra
    # donde diga x/y. Sin estos params el scatter caía siempre en el origen del mundo — invisible,
    # que es exactamente la queja que `view` vino a resolver en su momento.
    cx, cy = float(x), float(y)
    if view:
        mira = ue.punto_de_mira()
        if mira is not None and mira["punto"] is not None:
            cx, cy = mira["punto"].x, mira["punto"].y
    centro, semi = (cx, cy), (area, area)

    # Con PUNTOS de entrada, cada uno se vuelve el centro de su propio reparto: el scatter deja de
    # ser «llenar un área» y pasa a ser un MULTIPLICADOR — matas de pasto alrededor de cada árbol,
    # escombros alrededor de cada escombro. Es lo que hace que encadenar dos scatter signifique algo
    # obvio, en vez de dos repartos superpuestos.
    #
    # La semilla de cada racimo sale del punto que lo origina (`Sample.seed` es posicional y
    # determinista), así que dos racimos salen distintos y el grafo sigue dando lo mismo cada vez.
    entrada = list(_input or [])
    if entrada:
        todos = []
        for origen in entrada:
            locales, v = scatter.puntos_rico(
                None, (origen.pos.x, origen.pos.y), semi, cantidad=count, patron=pattern,
                spacing=spacing, anillos=int(rings), seed=int(origen.seed), surface=surface,
                align=align, slope_max=slope_max,
                height_min=(height_min if height_min else None),
                height_max=(height_max if height_max else None),
                noise=noise, density=density, scale_min=scale_min, scale_max=scale_max,
                espaciado=spread, sink=sink, anchor=anchor)
            if "error" not in v:
                todos.extend(locales)
        _RUNTIME_DATA_OUTPUTS["scatter"] = todos
        return (f"SCATTER \u2713 \u2014 {len(todos)} punto(s) en {len(entrada)} racimo(s) "
                f"de {count} ({pattern}, radio {area:g}cm)\n" + PISTA_INSTANCE)

    puntos, v = scatter.puntos_rico(
        None, centro, semi, cantidad=count, patron=pattern, spacing=spacing, anillos=int(rings),
        seed=seed, surface=surface, align=align, slope_max=slope_max,
        height_min=(height_min if height_min else None),
        height_max=(height_max if height_max else None),
        noise=noise, density=density, scale_min=scale_min, scale_max=scale_max, espaciado=spread,
        sink=sink, anchor=anchor)
    if "error" in v:
        return v["error"]

    # El scatter NO coloca: deja PUNTOS. Quien pone geometría en el mundo es `instance`, y es el
    # único. Mientras cada verbo colocaba por su cuenta, encadenar dos era encadenar dos efectos y
    # el resultado dependía del orden — que es exactamente cómo un segundo scatter terminaba encima
    # del primero sin que nada lo dijera.
    _RUNTIME_DATA_OUTPUTS["scatter"] = puntos
    _RUNTIME_DATA_OUTPUTS["_scatter_zona"] = (centro, semi)
    return (f"SCATTER \u2713 \u2014 {len(puntos)} punto(s) de {v['candidatos']} candidatos "
            f"({v['patron']}, sep {v['spacing']}cm, {v['assets']} asset(s), "
            f"{v['mascaras']} m\u00e1scara(s), {v['filtrados']} filtrados, "
            f"{v['filtrados']} filtrados)\n" + PISTA_INSTANCE)


def t_instance(points_input, *, assets="", asset_source=None, scale_min=1.0, scale_max=1.0,
               anchor="base", align=False, sink=0.0) -> str:
    """EL ÚNICO nodo que pone geometría nueva en el mundo. Toma puntos (P) y coloca en cada uno.

    Que haya uno solo no es prolijidad: es lo que le da un significado obvio a encadenar nodos. Con
    cada verbo colocando por su cuenta, «scatter y después scatter» eran dos efectos superpuestos y
    el resultado dependía del orden. Ahora la cadena describe DÓNDE, y un solo nodo decide CUÁNDO
    eso se vuelve escena.

    El oráculo corre acá, que es donde hay actores: primero la tanda contra sí misma y después
    contra lo que ya estaba.
    """
    from . import scatter, session, ue

    puntos = list(points_input or [])
    if not puntos:
        return "INSTANCE \u2014 no llegó ningún punto (¿corriste el scatter aguas arriba?)"

    # De dónde sale QUÉ colocar, en orden: el cable A, el campo, y el asset activo de la sesión.
    # El cable existe porque sin él la cadena `asset → scatter → instance` compilaba en VERDE y no
    # colocaba nada: el cable de puntos no lleva el asset, y `instance` se quedaba sin qué poner.
    rutas = [str(asset_source)] if asset_source else []
    rutas += [r.strip() for r in str(assets).split(",") if r.strip()]
    if not rutas and session.asset():
        rutas = [session.asset()]
    mallas = scatter._mallas_de(rutas)
    if not mallas:
        return ("INSTANCE \u2014 no s\u00e9 QU\u00c9 colocar: cablea un `asset` al pin "
                "`asset_source`, escrib\u00ed la ruta en `assets`, o eleg\u00ed uno en Content"
                + (f" (prob\u00e9 con {rutas})" if rutas else ""))

    actores = scatter.instanciar_puntos(
        puntos, mallas, scale_min=float(scale_min), scale_max=float(scale_max),
        sink=float(sink), anchor=str(anchor), align=bool(align))
    ue.seleccionar(actores)

    zona = _RUNTIME_DATA_OUTPUTS.get("_scatter_zona")
    if zona is None:
        xs = [p.pos.x for p in puntos]
        ys = [p.pos.y for p in puntos]
        centro = ((min(xs) + max(xs)) / 2.0, (min(ys) + max(ys)) / 2.0)
        semi = (max(1.0, (max(xs) - min(xs)) / 2.0), max(1.0, (max(ys) - min(ys)) / 2.0))
    else:
        centro, semi = zona
    existentes = ue.vecinos_en_zona(centro, semi, ignorar=actores)
    oraculo = ue.scatter_texto(actores, centro, semi, len(actores), existentes=existentes)
    _RUNTIME_ASSET_OUTPUTS["instance"] = rutas[0] if rutas else ""
    return (f"INSTANCE \u2713 \u2014 {len(actores)} colocado(s) en {len(puntos)} punto(s) "
            f"\u00b7 {len(mallas)} asset(s)\n{oraculo}")


def _veredicto_scatter(actores, centro, semi, v) -> str:
    """Reporte del reparto: el filtro, el oráculo de la TANDA, y el oráculo contra la ESCENA.

    Los dos chequeos hacen falta y miden cosas distintas. El primero dice si el reparto está bien
    hecho —cantidad, contención, sin clavarse, cobertura—. El segundo dice si además convive con lo
    que ya había, y es el que faltaba: dos scatter seguidos con los mismos parámetros caen
    exactamente uno encima del otro, y el primero informaba «REPARTO SANO · 0 clavados» porque
    dentro de su propia tanda, efectivamente, nadie se pisaba.
    """
    from . import ue
    cab = (f"SCATTER · {v['colocados']} colocados de {v['candidatos']} candidatos "
           f"({v['patron']}, sep {v['spacing']}cm, {v['assets']} asset(s), {v['mascaras']} máscara(s), "
           f"{v['filtrados']} filtrados, {v['pisados']} evitados por huella)")
    existentes = ue.vecinos_en_zona(centro, semi, ignorar=actores)
    oraculo = ue.scatter_texto(actores, centro, semi, len(actores), existentes=existentes)
    return f"{cab}\n{oraculo}"


def t_drop(asset, *, height=800.0) -> str:
    from . import physics, place, ue
    caja = place.colocar(asset, (0.0, 0.0, height))  # a plomo desde `height`
    r = physics.soltar(caja)                          # cae sobre la geometría real del nivel
    return f"cae {r['caida']}cm → " + ue.physics_texto(caja)


def t_snap(asset, *, grid=100.0) -> str:
    from . import place, snap, ue
    caja = place.colocar(asset, (137.4, 62.9, 11.1), (0.0, 0.0, 37.0))
    snap.a_grilla(caja, grid)
    return ue.snap_grilla_texto(caja, grid)


def t_replace(asset, *, sx=2.0, sy=2.0, sz=3.0) -> str:
    from . import place, reemplazar, ue
    blockout = place.colocar(asset, (0.0, 0.0, 150.0), scale=(sx, sy, sz))
    blockout.set_actor_label("Jam_blockout")
    nuevo, objetivo = reemplazar.reemplazar(blockout, asset, ajustar_escala=True)
    return ue.reemplazo_texto(nuevo, objetivo)


def t_spline(asset, *, gap=0.0, axis="x", anchor="base", align=False, surface=False,
             scale=1.0, jitter_yaw=0.0, seed=7) -> str:
    """Coloca piezas MODULARES a lo largo del spline seleccionado (o crea uno), cada una a su LARGO
    REAL (sin estirar), orientada a la tangente. `asset` puede ser una lista (kit → varía por pieza).
    `axis`=eje de avance de la malla, `gap`=separación entre piezas, `surface`=apoyar cada pieza en el
    terreno. El oráculo verifica que la cadena tile la curva sin solaparse. Con esto se hacen calles
    con adoquines, cercas, molduras y muros — una PARED es este tool con un asset de muro."""
    from . import pared, spline
    actor = pared.seleccionado_con_spline() or pared.crear_spline()
    actores, v = spline.construir(actor, asset, gap=gap, seed=int(seed), eje=axis, anchor=anchor,
                                  align=align, surface=surface, scale=scale, jitter_yaw=jitter_yaw)
    if "error" in v:
        return v["error"]
    from . import spline_core, ue
    ue.seleccionar(actores)
    cab = (f"SPLINE · {len(actores)} piezas modulares ({v['assets']} asset(s), módulos {v['modulos']}cm) "
           f"sobre curva de {v['largo_curva']}cm")
    return cab + "\n" + spline_core.texto_continuidad(v, v["largo_curva"])


def t_create_spline(asset=None) -> str:
    """Create: agrega un spline editable a la escena (primitiva de curva, como el Create de Dash).
    Después movés sus puntos y «spline» levanta las piezas sobre él. No usa asset."""
    from . import pared
    actor = pared.crear_spline()
    _RUNTIME_DATA_OUTPUTS["create_spline"] = actor
    etiqueta = actor.get_actor_label() if actor is not None else "spline"
    return f"SPLINE creado ✓ — «{etiqueta}»: editá sus puntos y usá «spline» para levantar piezas."


def t_fracture(asset, *, sites=20, seed=123, hollow=False, thickness=4.0, view=True) -> str:
    """CONVIERTE un StaticMesh en un DESTRUCTIBLE (Geometry Collection de Chaos, vía Dataflow). NO lo
    coloca: produce la GC y la deja como asset ACTIVO — colocarla es de `place` (que maneja GCs).
    Compone: `asset → fracture → place`. `sites` = pedazos. `hollow` vacía el volumen antes de
    fracturar (barril/piñata → rompe en CÁSCARA, no en macizo); `thickness` = espesor de pared (cm).
    EDITOR-ONLY (Dataflow no corre headless). (`view` se ignora: fracture no coloca.)"""
    from . import fracture, session
    r = fracture.fracturar(asset, sites=int(sites), seed=int(seed), hollow=bool(hollow),
                           thickness=float(thickness))
    if "error" in r:
        raise RuntimeError(r["error"])
    _RUNTIME_ASSET_OUTPUTS["fracture"] = r["ruta"]
    session.set_asset(r["ruta"], r["gc"].get_name())   # la GC queda como asset activo (place la coloca)
    modo = "hueca" if hollow else "sólida"
    return (f"DESTRUCTIBLE ✓ — GC «{r['gc'].get_name()}» ({r['sites']} pedazos, {modo}) en {r['ruta']}. "
            f"Queda como asset activo → usá «place» (o cableá a un nodo place) para colocarla.")


def t_nanite(asset) -> str:
    """StaticMesh → StaticMesh con Nanite. Es idempotente y no modifica la malla fuente: durante
    Run produce una copia temporal; Bake la promueve y Discard la elimina."""
    from . import nanite
    r = nanite.convertir(asset)
    if "error" in r:
        raise RuntimeError(r["error"])
    _RUNTIME_ASSET_OUTPUTS["nanite"] = r["ruta"]
    if r["already"]:
        return (f"NANITE ✓ — «{r['mesh'].get_name()}» ya tenía Nanite habilitado; "
                "se conserva el mismo asset.")
    return (f"NANITE ✓ — «{r['mesh'].get_name()}» convertido en {r['ruta']}. "
            "La malla fuente quedó intacta; Bake fija la copia y Discard la elimina.")


def _mesh_output(verbo: str, result: dict, label: str) -> str:
    if "error" in result:
        raise RuntimeError(result["error"])
    _RUNTIME_DATA_OUTPUTS[verbo] = result["mesh"]
    return f"{label} ✓ — {result.get('info', 'DynamicMesh')}"


def t_curve_bezier(_input=None, *, start_x=0.0, start_y=0.0, start_z=0.0,
                   end_x=0.0, end_y=0.0, end_z=500.0,
                   bend_x=0.0, bend_y=0.0, bend_z=0.0, segments=8) -> str:
    from . import curve
    result = curve.bezier(
        start_x=float(start_x), start_y=float(start_y), start_z=float(start_z),
        end_x=float(end_x), end_y=float(end_y), end_z=float(end_z),
        bend_x=float(bend_x), bend_y=float(bend_y), bend_z=float(bend_z),
        segments=int(segments),
    )
    if "error" in result:
        raise RuntimeError(result["error"])
    _RUNTIME_DATA_OUTPUTS["curve_bezier"] = result["curve"]
    return f"BEZIER S ✓ — {result['info']}"


def t_curve_child(curve_input, *, at=0.5, length=300.0, angle=55.0, azimuth=0.0,
                  bend=40.0, radial_offset=0.0, segments=8, samples=32) -> str:
    from . import curve
    result = curve.child(
        curve_input, at=float(at), length=float(length), angle=float(angle),
        azimuth=float(azimuth), bend=float(bend), radial_offset=float(radial_offset),
        segments=int(segments), samples=int(samples),
    )
    if "error" in result:
        raise RuntimeError(result["error"])
    _RUNTIME_DATA_OUTPUTS["curve_child"] = result["curve"]
    return f"CHILD S ✓ — {result['info']}"


def t_curve_noise(curve_input, *, amplitud=10.0, escala=0.004, octavas=3,
                  desde=0.0, seed=0, samples=16) -> str:
    from . import curve
    result = curve.noise(
        curve_input, amplitud=float(amplitud), escala=float(escala),
        octavas=int(octavas), desde=float(desde), seed=int(seed), samples=int(samples))
    if "error" in result:
        raise RuntimeError(result["error"])
    _RUNTIME_DATA_OUTPUTS["curve_noise"] = result["curve"]
    return f"NOISE S \u2713 \u2014 {result['info']}"


def t_curve_frames(curve_input, *, count=12, start=0.0, end=1.0,
                   radial_offset=0.0, turns=0.0, angle_offset=0.0,
                   radius_start=0.0, radius_end=0.0, samples=32, seed=7) -> str:
    from . import curve
    result = curve.frame_stream(
        curve_input, count=int(count), start=float(start), end=float(end),
        radial_offset=float(radial_offset), turns=float(turns),
        angle_offset=float(angle_offset), radius_start=float(radius_start),
        radius_end=float(radius_end), samples=int(samples), seed=int(seed),
    )
    if "error" in result:
        raise RuntimeError(result["error"])
    _RUNTIME_DATA_OUTPUTS["curve_frames"] = result["frame_set"]
    return f"FRAMES F ✓ — {result['info']}"


def t_distribute_frames(frame_input, *, count=12, start=0.0, end=1.0,
                        rotate_per_index=137.5, angle_offset=0.0,
                        angle_jitter=0.0, parameter_jitter=0.0, seed=7) -> str:
    from . import curve
    result = curve.distribute_frames(
        frame_input, count=int(count), start=float(start), end=float(end),
        rotate_per_index=float(rotate_per_index), angle_offset=float(angle_offset),
        angle_jitter=float(angle_jitter), parameter_jitter=float(parameter_jitter),
        seed=int(seed),
    )
    if "error" in result:
        raise RuntimeError(result["error"])
    _RUNTIME_DATA_OUTPUTS["distribute_frames"] = result["frame_set"]
    return f"DISTRIBUTE F ✓ — {result['info']}"


def t_transform_frames(frame_input, *, offset_x=0.0, offset_y=0.0, offset_z=0.0,
                       pitch=0.0, yaw=0.0, roll=0.0, scale=1.0,
                       offset_jitter_x=0.0, offset_jitter_y=0.0,
                       offset_jitter_z=0.0, pitch_jitter=0.0,
                       yaw_jitter=0.0, roll_jitter=0.0, scale_jitter=0.0,
                       inherit_scale=True, seed=7) -> str:
    from . import curve
    result = curve.transform_frames(
        frame_input, offset_x=float(offset_x), offset_y=float(offset_y),
        offset_z=float(offset_z), pitch=float(pitch), yaw=float(yaw), roll=float(roll),
        scale=float(scale), offset_jitter_x=float(offset_jitter_x),
        offset_jitter_y=float(offset_jitter_y), offset_jitter_z=float(offset_jitter_z),
        pitch_jitter=float(pitch_jitter), yaw_jitter=float(yaw_jitter),
        roll_jitter=float(roll_jitter), scale_jitter=float(scale_jitter),
        inherit_scale=bool(inherit_scale), seed=int(seed),
    )
    if "error" in result:
        raise RuntimeError(result["error"])
    _RUNTIME_DATA_OUTPUTS["transform_frames"] = result["frame_set"]
    return f"TRANSFORM F ✓ — {result['info']}"


def t_branch_from_frames(frame_input, *, length_min=200.0, length_max=400.0,
                         angle=55.0, angle_jitter=0.0, curl=20.0,
                         curl_jitter=0.0, segments=8, inherit_scale=True,
                         relative_to_parent=False, profile=None, seed=7) -> str:
    from . import curve
    result = curve.branch_from_frames(
        frame_input, length_min=float(length_min), length_max=float(length_max),
        angle=float(angle), angle_jitter=float(angle_jitter), curl=float(curl),
        curl_jitter=float(curl_jitter), segments=int(segments),
        inherit_scale=bool(inherit_scale),
        relative_to_parent=bool(relative_to_parent), profile=profile, seed=int(seed),
    )
    if "error" in result:
        raise RuntimeError(result["error"])
    _RUNTIME_DATA_OUTPUTS["branch_from_frames"] = result["curve"]
    return f"BRANCH FROM F ✓ — {result['info']}"


def t_asset_set(asset_inputs) -> str:
    from . import variants
    result = variants.make_asset_set(asset_inputs)
    if "error" in result:
        raise RuntimeError(result["error"])
    _RUNTIME_DATA_OUTPUTS["asset_set"] = result["asset_set"]
    return f"ASSET SET A[] ✓ — {result['info']}"


def t_choose_asset(frame_input, *, assets=None, mode="random", seed=7) -> str:
    from . import variants
    result = variants.choose_assets(frame_input, assets, mode=str(mode), seed=int(seed))
    if "error" in result:
        raise RuntimeError(result["error"])
    _RUNTIME_DATA_OUTPUTS["choose_asset"] = result["selection"]
    return f"CHOOSE ASSET AF ✓ — {result['info']}"


def t_graph_curve(_input=None, *, start_value=1.0, end_value=0.15, shape="custom",
                  power=2.0, midpoint=0.55, mid_value=0.72, samples=16) -> str:
    from . import fields
    result = fields.graph_curve(
        start_value=float(start_value), end_value=float(end_value), shape=str(shape),
        power=float(power), midpoint=float(midpoint), mid_value=float(mid_value),
        samples=int(samples),
    )
    if "error" in result:
        raise RuntimeError(result["error"])
    _RUNTIME_DATA_OUTPUTS["graph_curve"] = result["series"]
    return f"GRAPH CURVE N[] ✓ — {result['info']}"


def t_curve_branches(curve_input, *, count=12, start=0.2, end=0.92,
                     length_min=200.0, length_max=400.0,
                     parent_scale_start=1.0, parent_scale_end=1.0,
                     angle=70.0, angle_jitter=8.0, rotate_per_index=137.0,
                     azimuth=0.0, azimuth_jitter=5.0, bend=40.0,
                     bend_jitter=20.0, radial_offset=0.0,
                     segments=8, samples=32, seed=7) -> str:
    from . import curve
    result = curve.branches(
        curve_input, count=int(count), start=float(start), end=float(end),
        length_min=float(length_min), length_max=float(length_max),
        parent_scale_start=float(parent_scale_start), parent_scale_end=float(parent_scale_end),
        angle=float(angle), angle_jitter=float(angle_jitter),
        rotate_per_index=float(rotate_per_index), azimuth=float(azimuth),
        azimuth_jitter=float(azimuth_jitter), bend=float(bend),
        bend_jitter=float(bend_jitter), radial_offset=float(radial_offset),
        segments=int(segments), samples=int(samples), seed=int(seed),
    )
    if "error" in result:
        raise RuntimeError(result["error"])
    _RUNTIME_DATA_OUTPUTS["curve_branches"] = result["curve"]
    return f"BRANCHES S ✓ — {result['info']}"


def t_mesh_triangle(_input=None, *, size=100.0) -> str:
    from . import mesh
    return _mesh_output("mesh_triangle", mesh.triangle(size=float(size)), "TRIANGLE M")


def t_mesh_quad(_input=None, *, width=100.0, height=100.0) -> str:
    from . import mesh
    return _mesh_output("mesh_quad", mesh.quad(width=float(width), height=float(height)), "QUAD M")


def t_mesh_grid(_input=None, *, width=500.0, height=500.0, columns=6, rows=6) -> str:
    from . import mesh
    return _mesh_output(
        "mesh_grid",
        mesh.grid(width=float(width), height=float(height), columns=int(columns), rows=int(rows)),
        "GRID M",
    )


def t_mesh_cylinder(_input=None, *, radius=50.0, height=200.0, sides=16,
                    height_steps=1, capped=True) -> str:
    from . import mesh
    return _mesh_output(
        "mesh_cylinder",
        mesh.cylinder(radius=float(radius), height=float(height), sides=int(sides),
                      height_steps=int(height_steps), capped=bool(capped)),
        "CYLINDER M",
    )


def t_mesh_cone(_input=None, *, base_radius=60.0, top_radius=0.0, height=200.0,
                sides=16, height_steps=4, capped=True) -> str:
    from . import mesh
    return _mesh_output(
        "mesh_cone",
        mesh.cone(base_radius=float(base_radius), top_radius=float(top_radius), height=float(height),
                  sides=int(sides), height_steps=int(height_steps), capped=bool(capped)),
        "CONE M",
    )


def t_mesh_sphere(_input=None, *, radius=100.0, latitude_steps=8, longitude_steps=12) -> str:
    from . import mesh
    return _mesh_output(
        "mesh_sphere",
        mesh.sphere(radius=float(radius), latitude_steps=int(latitude_steps),
                    longitude_steps=int(longitude_steps)),
        "SPHERE M",
    )


def t_mesh_from_asset(asset_input) -> str:
    from . import mesh
    return _mesh_output("mesh_from_asset", mesh.from_asset(asset_input), "FROM ASSET M")


def t_mesh_pipe(curve_input, *, radius_start=30.0, radius_end=5.0, sides=10, samples=16,
                capped=True, profile_rotation=0.0, miter_limit=4.0,
                radius_from_parent=0.0, pivot_uvs=False) -> str:
    from . import mesh
    result = mesh.pipe(
        curve_input, radius_start=float(radius_start), radius_end=float(radius_end),
        sides=int(sides), samples=int(samples), capped=bool(capped),
        profile_rotation=float(profile_rotation), miter_limit=float(miter_limit),
        radius_from_parent=float(radius_from_parent), pivot_uvs=bool(pivot_uvs),
    )
    return _mesh_output("mesh_pipe", result, "PIPE M")


def t_mesh_pipe_profile(curve_input, *, profile=None, radius=30.0, sides=10, samples=16,
                        capped=True, profile_rotation=0.0, miter_limit=4.0,
                        pivot_uvs=False) -> str:
    from . import mesh
    result = mesh.pipe_profile(
        curve_input, profile, radius=float(radius), sides=int(sides), samples=int(samples),
        capped=bool(capped), profile_rotation=float(profile_rotation),
        miter_limit=float(miter_limit), pivot_uvs=bool(pivot_uvs),
    )
    return _mesh_output("mesh_pipe_profile", result, "PIPE PROFILE M")


def t_mesh_along_curve(curve_input, *, asset=None, count=12, start=0.1, end=0.95,
                       radial_offset=30.0, turns=2.0, angle_offset=0.0,
                       scale_start=0.45, scale_end=0.25,
                       scale_x=1.0, scale_y=1.0, scale_z=1.0,
                       orientation="outward", rotation_jitter=0.0, scale_jitter=0.0,
                       offset_jitter=0.0, seed=7, crossed=False, double_sided=False,
                       samples=32) -> str:
    from . import mesh
    result = mesh.along_curve(
        curve_input, asset, count=int(count), start=float(start), end=float(end),
        radial_offset=float(radial_offset), turns=float(turns), angle_offset=float(angle_offset),
        scale_start=float(scale_start), scale_end=float(scale_end),
        scale_x=float(scale_x), scale_y=float(scale_y), scale_z=float(scale_z),
        orientation=str(orientation), rotation_jitter=float(rotation_jitter),
        scale_jitter=float(scale_jitter), offset_jitter=float(offset_jitter), seed=int(seed),
        crossed=bool(crossed), double_sided=bool(double_sided), samples=int(samples))
    return _mesh_output("mesh_along_curve", result, "ALONG CURVE M")


def t_copy_mesh_to_frames(frame_input, *, asset=None,
                          asset_offset_x=0.0, asset_offset_y=0.0, asset_offset_z=0.0,
                          asset_pitch=0.0, asset_yaw=0.0, asset_roll=0.0,
                          asset_scale=1.0, scale_x=1.0, scale_y=1.0, scale_z=1.0,
                          inherit_scale=True) -> str:
    from . import mesh
    result = mesh.copy_to_frames(
        frame_input, asset, asset_offset_x=float(asset_offset_x),
        asset_offset_y=float(asset_offset_y), asset_offset_z=float(asset_offset_z),
        asset_pitch=float(asset_pitch), asset_yaw=float(asset_yaw),
        asset_roll=float(asset_roll), asset_scale=float(asset_scale),
        scale_x=float(scale_x), scale_y=float(scale_y), scale_z=float(scale_z),
        inherit_scale=bool(inherit_scale),
    )
    return _mesh_output("copy_mesh_to_frames", result, "COPY TO FRAMES M")


def t_copy_asset_selection(selection_input, *, asset_offset_x=0.0, asset_offset_y=0.0,
                           asset_offset_z=0.0, asset_pitch=0.0, asset_yaw=0.0,
                           asset_roll=0.0, asset_scale=1.0, scale_x=1.0,
                           scale_y=1.0, scale_z=1.0, inherit_scale=True) -> str:
    from . import mesh
    result = mesh.copy_to_frames(
        selection_input, None, asset_offset_x=float(asset_offset_x),
        asset_offset_y=float(asset_offset_y), asset_offset_z=float(asset_offset_z),
        asset_pitch=float(asset_pitch), asset_yaw=float(asset_yaw),
        asset_roll=float(asset_roll), asset_scale=float(asset_scale),
        scale_x=float(scale_x), scale_y=float(scale_y), scale_z=float(scale_z),
        inherit_scale=bool(inherit_scale),
    )
    return _mesh_output("copy_asset_selection", result, "COPY VARIANTS M")


def t_hism_output(selection_input, *, name="TreeGen_Foliage",
                  asset_offset_x=0.0, asset_offset_y=0.0, asset_offset_z=0.0,
                  asset_pitch=0.0, asset_yaw=0.0, asset_roll=0.0,
                  asset_scale=1.0, inherit_scale=True) -> str:
    from . import instances
    result = instances.from_selection(
        selection_input, name=str(name), asset_offset_x=float(asset_offset_x),
        asset_offset_y=float(asset_offset_y), asset_offset_z=float(asset_offset_z),
        asset_pitch=float(asset_pitch), asset_yaw=float(asset_yaw),
        asset_roll=float(asset_roll), asset_scale=float(asset_scale),
        inherit_scale=bool(inherit_scale),
    )
    if "error" in result:
        raise RuntimeError(result["error"])
    _RUNTIME_DATA_OUTPUTS["hism_output"] = result["actor"]
    return f"HISM H ✓ — {result['info']}"


def t_mesh_leaf(curve_input, *, asset=None, count=4, start=0.1, end=0.95,
                radial_offset=20.0, rotate_per_index=137.0, angle_offset=0.0,
                leaves_per_cluster=3, length=90.0, width=45.0,
                asset_scale=1.0, asset_pitch=0.0, asset_yaw=0.0, asset_roll=0.0,
                size_start=1.0, size_end=0.7, splay=70.0, lift=18.0,
                rotation_jitter=12.0, scale_jitter=0.2, offset_jitter=4.0,
                seed=7, inherit_scale=False, double_sided=True, samples=32) -> str:
    from . import mesh
    result = mesh.leaf(
        curve_input, asset=asset, count=int(count), start=float(start), end=float(end),
        radial_offset=float(radial_offset), rotate_per_index=float(rotate_per_index),
        angle_offset=float(angle_offset), leaves_per_cluster=int(leaves_per_cluster),
        length=float(length), width=float(width), size_start=float(size_start),
        asset_scale=float(asset_scale), asset_pitch=float(asset_pitch),
        asset_yaw=float(asset_yaw), asset_roll=float(asset_roll),
        size_end=float(size_end), splay=float(splay), lift=float(lift),
        rotation_jitter=float(rotation_jitter), scale_jitter=float(scale_jitter),
        offset_jitter=float(offset_jitter), seed=int(seed),
        inherit_scale=bool(inherit_scale), double_sided=bool(double_sided), samples=int(samples),
    )
    return _mesh_output("mesh_leaf", result, "LEAF M")


def t_mesh_transform(mesh_input, *, x=0.0, y=0.0, z=0.0, pitch=0.0, yaw=0.0, roll=0.0,
                     scale_x=1.0, scale_y=1.0, scale_z=1.0) -> str:
    from . import mesh
    result = mesh.transform(mesh_input, x=float(x), y=float(y), z=float(z),
                            pitch=float(pitch), yaw=float(yaw), roll=float(roll),
                            scale_x=float(scale_x), scale_y=float(scale_y), scale_z=float(scale_z))
    return _mesh_output("mesh_transform", result, "TRANSFORM M")


def t_mesh_color(mesh_input, *, color="#808080") -> str:
    from . import mesh
    return _mesh_output("mesh_color", mesh.vertex_color(mesh_input, color=str(color)), "COLOR M")


def t_material_wind(_input=None, *, name="M_JamArbolViento", folder="/Game/Jam/Materials",
                    fuerza=0.25, velocidad=1.2, concentracion=2.0,
                    eje_x=1.0, eje_y=0.3, eje_z=0.0) -> str:
    """Fabrica el material de viento que consume el pivote estampado por `mesh_pipe(pivot_uvs=True)`."""
    from . import materials, shader
    grafo = shader.viento_de_arbol(
        nombre=str(name), fuerza=float(fuerza), velocidad=float(velocidad),
        concentracion=float(concentracion),
        eje=(float(eje_x), float(eje_y), float(eje_z)))
    problemas = shader.verificar(grafo)
    if problemas:
        raise RuntimeError("el grafo del material no es válido: " + " · ".join(problemas))
    resultado = materials.emitir(grafo, str(folder))
    if "error" in resultado:
        raise RuntimeError(resultado["error"])
    _RUNTIME_DATA_OUTPUTS["material_wind"] = f"{folder}/{name}"
    return f"WIND MATERIAL A \u2713 \u2014 {resultado['info']}"


# ---- verbos genéricos de material: armar un shader nodo por nodo desde el canvas ----
# El cable lleva el GRAFO (tipo `MT`), no el material: recién `material_build` toca Unreal. Así el
# grafo se puede verificar, comparar y reusar sin crear assets, y un error de cableado sale en el
# Compile del canvas en vez de un log de compilación de shaders.


def _material_output(verbo: str, grafo, extra: str = "") -> str:
    _RUNTIME_DATA_OUTPUTS[verbo] = grafo
    from . import shader
    problemas = shader.verificar(grafo)
    # Un grafo a medio armar TIENE que poder existir: mientras se encadenan nodos no alimenta
    # ninguna salida ni tiene todo conectado. Los problemas se reportan como aviso y `material_build`
    # es el que se planta — si no, no se podría construir nada de a poco.
    aviso = f" · pendiente: {problemas[0]}" if problemas else ""
    return (f"{len(grafo.nodos)} nodo(s) · {len(grafo.aristas)} cable(s){extra}{aviso}")


def _material_entrada(mat_input, nombre: str):
    from . import shader
    if mat_input is None:
        return shader.vacio(nombre)
    if not isinstance(mat_input, shader.GrafoMaterial):
        raise RuntimeError(f"la entrada no es un grafo de material, es {type(mat_input).__name__}")
    return mat_input


def t_material_node(mat_input=None, *, type="Multiply", id="", inputs="", props="",
                    x=0, y=0, _verbo="material_node") -> str:
    """Agrega UN nodo al grafo. `type` es cualquiera de los 409 `MaterialExpression` del motor.

    `inputs` cablea de una vez lo que ya existe (`A=uv, B=escala`; con `nodo.R` se elige el canal de
    salida) y `props` fija propiedades del nodo (`scale=2.5, parameter_name=Fuerza`). Los nombres de
    entrada válidos los sabe el verificador para los 409 tipos, así que equivocarse dice cuáles son
    en vez de crear un material roto.
    """
    from . import shader
    grafo = _material_entrada(mat_input, "M_JamMaterial")
    grafo, creado = shader.con_nodo(
        grafo, str(type), id=str(id), props=shader.parsear_props(props),
        entradas=shader.parsear_pares(inputs), x=int(x), y=int(y))
    # La salida se registra bajo el verbo QUE LA PRODUJO, no bajo un nombre fijo: el ejecutor le
    # pregunta a cada nodo del canvas por su propia clave para alimentar al siguiente. Con la clave
    # clavada en «material_node», los verbos de la paleta escribían todos en el mismo lugar y el
    # grafo no llegaba aguas abajo — el segundo nodo veía un grafo vacío.
    return "MATERIAL NODE \u2713 \u2014 " + _material_output(
        _verbo, grafo, f" · «{creado}» ({type})")


def t_material_connect(mat_input, *, from_node="", to_node="", to_input="",
                       from_output="") -> str:
    """Conecta dos nodos que ya están en el grafo. Sin `to_input`, usa la única entrada del destino."""
    from . import shader
    grafo = _material_entrada(mat_input, "M_JamMaterial")
    grafo = shader.con_cable(grafo, str(from_node), str(to_node), str(to_input), str(from_output))
    return "MATERIAL CONNECT \u2713 \u2014 " + _material_output(
        "material_connect", grafo, f" · {from_node}\u2192{to_node}")


def t_material_output(mat_input, *, node="", target="MP_BASE_COLOR", from_output="") -> str:
    """Enchufa un nodo a una salida del material (BaseColor, Roughness, WPO…)."""
    from . import shader
    grafo = _material_entrada(mat_input, "M_JamMaterial")
    grafo = shader.con_salida(grafo, str(node), str(target), str(from_output))
    return "MATERIAL OUTPUT \u2713 \u2014 " + _material_output(
        "material_output", grafo, f" · {node}\u2192{target}")


def t_material_build(mat_input, *, name="M_JamMaterial", folder="/Game/Jam/Materials",
                     blend_mode="", shading_model="", two_sided=False, use_attributes=False,
                     max_instructions=0) -> str:
    """Hornea el grafo como material de verdad. Acá SÍ se planta si el grafo no es válido.

    `max_instructions` es el PRESUPUESTO: 0 = sin límite, y con un número el verbo mide el material
    compilado y falla si se pasa. El costo no se puede saber antes de compilar, así que el asset
    queda creado aunque se pase — a propósito, para poder abrirlo y ver qué lo encareció.
    """
    from . import materials, shader
    grafo = _material_entrada(mat_input, str(name))
    grafo = shader.GrafoMaterial(nombre=str(name), nodos=grafo.nodos, aristas=grafo.aristas,
                                 two_sided=bool(two_sided),
                                 shading_model=str(shading_model) or grafo.shading_model,
                                 blend_mode=str(blend_mode) or grafo.blend_mode)
    problemas = shader.verificar(grafo)
    if problemas:
        raise RuntimeError("el grafo del material no es válido: " + " \u00b7 ".join(problemas))
    resultado = materials.emitir(grafo, str(folder), usar_atributos=bool(use_attributes))
    if "error" in resultado:
        raise RuntimeError(resultado["error"])
    _RUNTIME_DATA_OUTPUTS["material_build"] = f"{folder}/{name}"

    problema = materials.veredicto_de_presupuesto(
        resultado.get("costo", {}), int(max_instructions), f"{folder}/{name}")
    if problema:
        raise RuntimeError(problema)
    return f"MATERIAL BUILD \u2713 \u2014 {resultado['info']}"


def t_mesh_uv_box(mesh_input, *, size_x=0.0, size_y=0.0, size_z=0.0,
                  yaw=0.0, pitch=0.0, roll=0.0, channel=0, min_island_tris=2) -> str:
    from . import mesh
    return _mesh_output("mesh_uv_box", mesh.uv_box(
        mesh_input, size_x=float(size_x), size_y=float(size_y), size_z=float(size_z),
        yaw=float(yaw), pitch=float(pitch), roll=float(roll),
        channel=int(channel), min_island_tris=int(min_island_tris)), "UV BOX M")


def t_mesh_uv_unwrap(mesh_input, *, method="conformal", channel=0, align_to_axes=True) -> str:
    from . import mesh
    return _mesh_output("mesh_uv_unwrap", mesh.uv_unwrap(
        mesh_input, method=str(method), channel=int(channel),
        align_to_axes=bool(align_to_axes)), "UV UNWRAP M")


def t_mesh_uv_pack(mesh_input, *, resolution=1024, channel=0, optimize_rotation=True) -> str:
    from . import mesh
    return _mesh_output("mesh_uv_pack", mesh.uv_pack(
        mesh_input, resolution=int(resolution), channel=int(channel),
        optimize_rotation=bool(optimize_rotation)), "UV PACK M")


def t_material_function(mat_input, *, name="MF_JamFuncion", folder="/Game/Jam/Functions",
                        kind="funcion", description="") -> str:
    """Hornea el grafo MT como FUNCIÓN de material reusable, no como material.

    Es el mismo IR y los mismos verbos; lo único que cambia es que el grafo termina en un
    `FunctionOutput` (o `MaterialLayerOutput` si `kind` es capa/mezcla) y el asset es una función.
    Sirve para que Jam acumule vocabulario PROPIO: lo que hoy es un subgrafo que se copia y pega,
    después es un nodo con nombre que se llama desde cualquier material con `material_call`.
    """
    from . import materials, shader
    grafo = _material_entrada(mat_input, str(name))
    grafo = shader.GrafoMaterial(nombre=str(name), nodos=grafo.nodos, aristas=grafo.aristas)
    problemas = shader.verificar(grafo)
    if problemas:
        raise RuntimeError("el grafo de la función no es válido: " + " \u00b7 ".join(problemas))
    resultado = materials.emitir_funcion(grafo, str(folder), clase=str(kind),
                                         descripcion=str(description))
    if "error" in resultado:
        raise RuntimeError(resultado["error"])
    _RUNTIME_DATA_OUTPUTS["material_function"] = f"{folder}/{name}"
    return f"MATERIAL FUNCTION \u2713 \u2014 {resultado['info']}"


def t_material_call(mat_input=None, *, function="", id="", inputs="", x=0, y=0) -> str:
    """Llama a una función de material dentro del grafo. Sus entradas se DESCUBREN del asset.

    Es el mismo trato que las 408 expresiones del motor: la firma no se declara, se pregunta. Por
    eso una función propia se usa igual que un nodo nativo, y equivocarse de nombre de entrada dice
    cuáles tiene.
    """
    from . import materials, shader
    grafo = _material_entrada(mat_input, "M_JamMaterial")
    ruta = str(function).strip()
    if not ruta:
        raise RuntimeError("hay que decir qué función llamar (ruta del asset)")
    entradas = materials.entradas_de_funcion(ruta)
    if entradas is None:
        raise RuntimeError(f"no pude cargar la función «{ruta}»")
    pedidas = shader.parsear_pares(inputs)
    invalidas = [p for p in pedidas if p not in entradas]
    if invalidas:
        raise RuntimeError(f"«{ruta}» no tiene la(s) entrada(s) {invalidas} "
                           f"(tiene {entradas or 'ninguna'})")
    grafo, creado = shader.con_nodo(
        grafo, "MaterialFunctionCall", id=str(id), props={"material_function": ruta},
        entradas=pedidas, x=int(x), y=int(y), firma=tuple(entradas))
    return "MATERIAL CALL \u2713 \u2014 " + _material_output(
        "material_call", grafo, f" \u00b7 \u00ab{creado}\u00bb \u2192 {ruta} {entradas}")


def t_material_instance(asset_input=None, *, name="MI_JamInstancia",
                        folder="/Game/Jam/Materials", parent="", scalars="", vectors="") -> str:
    """Crea una INSTANCIA del material y le fija parámetros. Retocar sin recompilar nada.

    Es el otro lado del trabajo de shader: el material define QUÉ se puede tocar (los parámetros con
    nombre) y la instancia decide CUÁNTO. Diez variantes de una pared son diez instancias, no diez
    materiales — y ninguna paga compilación.
    """
    from . import materials, shader
    ruta_padre = str(parent).strip() or str(asset_input or "").strip()
    if not ruta_padre:
        raise RuntimeError("hay que decir de qué material sale la instancia "
                           "(cable A desde material_build, o el campo `parent`)")
    resultado = materials.instanciar(
        ruta_padre, str(name), str(folder),
        escalares={k: float(v) for k, v in shader.parsear_pares(scalars).items()},
        vectores={k: shader.color_de_hex(v) for k, v in shader.parsear_pares(vectors).items()})
    if "error" in resultado:
        raise RuntimeError(resultado["error"])
    _RUNTIME_DATA_OUTPUTS["material_instance"] = f"{folder}/{name}"
    return f"MATERIAL INSTANCE \u2713 \u2014 {resultado['info']}"


def t_mesh_vertex_gradient(mesh_input, *, eje="z", desde=0.0, hasta=1.0,
                           power=1.0, canal="todos") -> str:
    from . import mesh
    return _mesh_output(
        "mesh_vertex_gradient",
        mesh.vertex_color_gradient(mesh_input, eje=str(eje), desde=float(desde),
                                   hasta=float(hasta), power=float(power), canal=str(canal)),
        "GRADIENT M")


def t_mesh_uv_scale(mesh_input, *, u=1.0, v=1.0, channel=0,
                    origin_u=0.0, origin_v=0.0) -> str:
    from . import mesh
    return _mesh_output(
        "mesh_uv_scale",
        mesh.uv_scale(mesh_input, u=float(u), v=float(v), channel=int(channel),
                      origin_u=float(origin_u), origin_v=float(origin_v)),
        "UV SCALE M",
    )


def t_mesh_material(mesh_input, *, material="", material_asset=None) -> str:
    """Asigna un material a la malla. El cable `A` manda sobre el campo de texto.

    El pin existe porque sin él el único camino era COPIAR la ruta que había impreso
    `material_build` en otro nodo, que es exactamente la clase de paso manual que un grafo
    está para eliminar — y que se rompe en silencio en cuanto alguien renombra el material.

    El campo se conserva para apuntar a un material que ya existe en el proyecto (uno del motor,
    uno importado) sin tener que construirlo en el grafo.
    """
    from . import mesh
    ruta = str(material_asset or "").strip() or str(material)
    return _mesh_output(
        "mesh_material", mesh.assign_material(mesh_input, material=ruta), "MATERIAL M")


def t_mesh_merge(mesh_inputs) -> str:
    from . import mesh
    return _mesh_output("mesh_merge", mesh.merge(mesh_inputs), "MERGE M")


def t_mesh_normals(mesh_input, *, angle_weighted=True, area_weighted=True) -> str:
    from . import mesh
    result = mesh.normals(mesh_input, angle_weighted=bool(angle_weighted),
                          area_weighted=bool(area_weighted))
    return _mesh_output("mesh_normals", result, "NORMALS M")


def t_debug(entrada, *, tamano=30.0, grosor=1.2, escalar_con_dato=True,
            cada=1, solo_direccion=False) -> str:
    """AYUDANTE universal: dibuja lo que llegue por el cable, sea del tipo que sea."""
    from . import mesh
    return _mesh_output(
        "debug",
        mesh.debug_de_cualquier_cosa(
            entrada, tamano=float(tamano), grosor=float(grosor),
            escalar_con_dato=bool(escalar_con_dato), cada=int(cada),
            solo_direccion=bool(solo_direccion)),
        "DEBUG M",
    )


def t_points_to_frames(stream_input, *, orientacion="normal", escala=1.0,
                       escala_desde_peso=True, giro_al_azar=True, seed=7) -> str:
    """Puente P → F: convierte el stream de puntos de Flow en frames que consume el tab Mesh."""
    from . import curve
    result = curve.frames_desde_puntos(
        stream_input, orientacion=str(orientacion), escala=float(escala),
        escala_desde_peso=bool(escala_desde_peso), giro_al_azar=bool(giro_al_azar),
        seed=int(seed))
    if "error" in result:
        raise RuntimeError(result["error"])
    _RUNTIME_DATA_OUTPUTS["points_to_frames"] = result["frame_set"]
    return f"POINTS TO F ✓ — {result['info']}"


def t_mesh_box(_input=None, *, size_x=100.0, size_y=100.0, size_z=100.0,
               steps_x=0, steps_y=0, steps_z=0) -> str:
    from . import mesh
    return _mesh_output("mesh_box", mesh.box(
        size_x=float(size_x), size_y=float(size_y), size_z=float(size_z),
        steps_x=int(steps_x), steps_y=int(steps_y), steps_z=int(steps_z)), "BOX M")


def t_mesh_capsule(_input=None, *, radius=30.0, length=150.0, hemisphere_steps=5, sides=12) -> str:
    from . import mesh
    return _mesh_output("mesh_capsule", mesh.capsule(
        radius=float(radius), length=float(length),
        hemisphere_steps=int(hemisphere_steps), sides=int(sides)), "CAPSULE M")


def t_mesh_torus(_input=None, *, major_radius=100.0, minor_radius=25.0,
                 major_steps=24, minor_steps=12) -> str:
    from . import mesh
    return _mesh_output("mesh_torus", mesh.torus(
        major_radius=float(major_radius), minor_radius=float(minor_radius),
        major_steps=int(major_steps), minor_steps=int(minor_steps)), "TORUS M")


def t_mesh_disc(_input=None, *, radius=100.0, sides=24, start_angle=0.0, end_angle=360.0,
                hole_radius=0.0) -> str:
    from . import mesh
    return _mesh_output("mesh_disc", mesh.disc(
        radius=float(radius), sides=int(sides), start_angle=float(start_angle),
        end_angle=float(end_angle), hole_radius=float(hole_radius)), "DISC M")


def t_mesh_round_rect(_input=None, *, size_x=200.0, size_y=200.0, corner_radius=20.0, steps_round=6) -> str:
    from . import mesh
    return _mesh_output("mesh_round_rect", mesh.round_rect(
        size_x=float(size_x), size_y=float(size_y),
        corner_radius=float(corner_radius), steps_round=int(steps_round)), "ROUND RECT M")


def t_mesh_stairs(_input=None, *, step_width=150.0, step_height=18.0, step_depth=28.0,
                  steps=10, floating=False) -> str:
    from . import mesh
    return _mesh_output("mesh_stairs", mesh.stairs(
        step_width=float(step_width), step_height=float(step_height),
        step_depth=float(step_depth), steps=int(steps),
        floating=bool(floating)), "STAIRS M")


def t_mesh_stairs_curved(_input=None, *, step_width=150.0, step_height=18.0, inner_radius=200.0,
                         curve_angle=90.0, steps=12, floating=False) -> str:
    from . import mesh
    return _mesh_output("mesh_stairs_curved", mesh.stairs_curved(
        step_width=float(step_width), step_height=float(step_height),
        inner_radius=float(inner_radius), curve_angle=float(curve_angle),
        steps=int(steps), floating=bool(floating)), "CURVED STAIRS M")


def t_mesh_sphere_box(_input=None, *, radius=80.0, steps=6) -> str:
    from . import mesh
    return _mesh_output("mesh_sphere_box", mesh.sphere_box(
        radius=float(radius), steps=int(steps)), "SPHERE BOX M")


def t_mesh_revolve(curve_input, *, steps=24, capped=True, degrees=360.0, samples=32) -> str:
    from . import mesh
    return _mesh_output("mesh_revolve", mesh.revolve(
        curve_input, steps=int(steps), capped=bool(capped),
        degrees=float(degrees), samples=int(samples)), "REVOLVE M")


def t_mesh_bark(mesh_input, *, amplitud=2.0, escala=0.06, alargue=0.25,
                octavas=3, surcos=0.6, seed=7) -> str:
    """Relieve de corteza sobre M: desplaza cada vértice por su normal con ruido estirado."""
    from . import mesh
    return _mesh_output(
        "mesh_bark",
        mesh.corteza(mesh_input, amplitud=float(amplitud), escala=float(escala),
                     alargue=float(alargue), octavas=int(octavas),
                     surcos=float(surcos), seed=int(seed)),
        "BARK M",
    )


def t_mesh_compare(mesh_input, *, asset=None, franjas=8, solo_forma=False,
                   alto=0.30, ancho=0.35, esbeltez=0.20, vertices=0.50,
                   triangulos=0.50, perfil=0.15, silueta=0.18) -> str:
    """Oráculo de forma: compara `M` contra un StaticMesh de referencia y DEJA PASAR la malla.

    No modifica nada. Se intercala antes de `Mesh to Static` para que el mismo Run que construye el
    árbol diga cuánto se parece al de referencia.
    """
    from . import mesh
    resultado = mesh.comparar(
        mesh_input, asset, franjas=int(franjas), tolerancia_perfil=float(perfil),
        tolerancia_silueta=float(silueta), solo_forma=bool(solo_forma),
        alto=float(alto), ancho=float(ancho), esbeltez=float(esbeltez),
        vertices=float(vertices), triangulos=float(triangulos))
    if "error" in resultado:
        raise RuntimeError(resultado["error"])
    _RUNTIME_DATA_OUTPUTS["mesh_compare"] = mesh._dynamic_mesh(mesh_input)
    marca = "✓" if resultado["ok"] else "✗"
    titulo = (f"COMPARE {marca} — se parece a la referencia" if resultado["ok"]
              else f"COMPARE {marca} — lo que más separa: {resultado['peor']}")
    return f"{titulo}\n{resultado['texto']}"


def t_mesh_to_static(mesh_input, *, name="GeneratedMesh", folder="/Game/Jam/Meshes",
                     collision=True, recompute_tangents=True, show_vertex_colors=True) -> str:
    from . import mesh
    result = mesh.to_static(mesh_input, name=name, folder=folder, collision=bool(collision),
                            recompute_tangents=bool(recompute_tangents),
                            show_vertex_colors=bool(show_vertex_colors))
    if "error" in result:
        raise RuntimeError(result["error"])
    _RUNTIME_ASSET_OUTPUTS["mesh_to_static"] = result["ruta"]
    return (f"STATIC MESH ✓ — {result['ruta']} · {result.get('info', 'DynamicMesh')}. "
            "Bake fija el asset; Discard lo elimina.")


def asset_producido(verbo: str, asset_entrada, params: dict | None = None) -> str | None:
    """Ruta prevista para conversores (Fracture mesh→GC, Nanite mesh→mesh) que sale por su pin.
    El grafo la pasa aguas abajo en vez del asset de entrada. None si el verbo no transforma."""
    if verbo == "fracture":
        from . import fracture
        return fracture.gc_path_for(asset_entrada)
    if verbo == "nanite":
        from . import nanite
        return nanite.asset_path_for(asset_entrada)
    if verbo == "mesh_to_static":
        from . import mesh
        p = params or {}
        return mesh.asset_path_for(p.get("name", "GeneratedMesh"), p.get("folder", mesh.CARPETA))
    return None


# ---- el registro: verbo → acción param-driven + defaults (fuente de verdad para DSL, help y panel) ----

# Anclas disponibles, para que los params que eligen una se dibujen como LISTA y no como campo de
# texto donde hay que acordarse el nombre (se lee del cerebro puro, una sola fuente de verdad).
def _anclas() -> list:
    from . import pivot
    return list(pivot.ANCLAS)


_ANCLAS = _anclas()

# `cat` = categoría estilo Dash (Content/Place/Scatter/Create/Edit) → agrupa los verbos en la
# Dash Bar. Es dato: mover una herramienta de categoría es cambiar este campo, sin tocar C++.
REGISTRO = {
    "asset":        {"fn": t_asset,   "cat": "Content", "params": {"name": ""},
                     "doc": "elige el asset activo (Content); las demás herramientas lo heredan"},
    "pick":         {"fn": t_pick,    "cat": "Content", "params": {},
                     "doc": "usa la malla SELECCIONADA en el Content Browser de Unreal como asset activo"},
    "pivot":        {"fn": t_pivot,   "cat": "Edit",    "params": {"anchor": ""},
                     "opciones": {"anchor": [""] + list(_ANCLAS)},
                     "doc": "dónde está el pivote del asset y si sirve para repetir (o hay que anclarlo)"},
    "normalize":    {"fn": t_normalize, "cat": "Edit",  "params": {"anchor": "", "scene": True},
                     "opciones": {"anchor": [""] + list(_ANCLAS)},
                     "doc": "normaliza el pivote del asset (una vez): todas las tools lo agarran por ahí"},
    "pivot_set":    {"fn": t_pivot_set, "cat": "Edit",  "params": {"to": "base"},
                     "opciones": {"to": list(_ANCLAS)},
                     "doc": "mueve el pivote de los actores seleccionados al ancla elegida"},
    # `view` arranca en FALSE en el grafo y en TRUE como comando, y no es una inconsistencia: son
    # dos cosas distintas. Un COMANDO es «ponelo donde estoy mirando» —por eso `view` existe—; un
    # GRAFO es una descripción que tiene que dar el mismo resultado cada vez que corre. Con `view`
    # prendido, cada Run re-apuntaba a la cámara viva y el modelo aparecía en otro lado.
    #
    # Sale gratis: el grafo pasa TODOS los params (de acá), y el comando sólo los que se tipean, así
    # que el default de la FUNCIÓN (`view=True`) es el que manda desde la Dash Bar.
    "place":        {"fn": t_place,   "cat": "Place",
                     "params": {"x": 0.0, "y": 0.0, "z": 0.0, "view": False, "surface": True,
                                "anchor": "base", "sink": 0.0, "align": False, "physics": False,
                                "yaw": 0.0, "scale": 1.0, "scale_min": 1.0, "scale_max": 1.0,
                                "points": ""},
                     "data_params": {"points": "P"},
                     "optional_data_params": ("points",),
                     "opciones": {"anchor": list(_ANCLAS)},
                     "doc": "pone el asset en el mundo: en sus coordenadas, o UNO POR PUNTO si le cableás "
                            "un scatter al pin `points`. Es el único nodo que coloca. Verifica el entorno"},
    "scatter":      {"fn": t_scatter, "cat": "Scatter",
                     "params": {"count": 24, "area": 800.0, "x": 0.0, "y": 0.0,
                                "pattern": "poisson", "spacing": 0.0,
                                "rings": 3, "surface": True, "align": False, "slope_max": 90.0,
                                "height_min": 0.0, "height_max": 0.0, "noise": 0.0, "density": 1.0,
                                "scale_min": 1.0, "scale_max": 1.0, "spread": 1.0, "sink": 0.0,
                                "anchor": "", "view": False, "seed": 7},
                     "opciones": {"pattern": ["poisson", "grid", "radial", "hexagonal", "triangular"],
                                  "anchor": [""] + list(_ANCLAS)},
                     "doc": "calcula PUNTOS sobre la superficie real con máscaras (pendiente/altura/ruido/densidad). "
                            "Sin entrada reparte en un área; con PUNTOS reparte alrededor de cada uno "
                            "(multiplicador). No coloca: enchufalo al pin `points` de un `place`. Salida P"},
    "drop":         {"fn": t_drop,    "cat": "Place",   "params": {"height": 800.0},
                     "doc": "deja caer el asset sobre el piso real y verifica apoyo"},
    "snap":         {"fn": t_snap,    "cat": "Place",   "params": {"grid": 100.0},
                     "doc": "snap a grilla y verifica alineación"},
    "replace":      {"fn": t_replace, "cat": "Create",  "params": {"sx": 2.0, "sy": 2.0, "sz": 3.0},
                     "doc": "blockout → asset conservando footprint"},
    "spline":       {"fn": t_spline,  "cat": "Scatter",
                     "params": {"gap": 0.0, "axis": "x", "anchor": "base", "align": False,
                                "surface": False, "scale": 1.0, "jitter_yaw": 0.0, "seed": 7},
                     "opciones": {"axis": ["x", "y"], "anchor": list(_ANCLAS)},
                     "doc": "piezas modulares a su largo real a lo largo de un spline (verifica que tile sin solaparse)"},
    "create_spline": {"fn": t_create_spline, "cat": "Create", "params": {},
                      "doc": "agrega un spline editable a la escena (primitiva de curva)"},
    "fracture":     {"fn": t_fracture, "cat": "Create",
                     "params": {"sites": 20, "seed": 123, "hollow": False, "thickness": 4.0,
                                "view": False},
                     "doc": "convierte un StaticMesh en destructible (Geometry Collection de Chaos). "
                            "hollow=vacía el volumen (barril/piñata). Conversor: place lo coloca "
                            "(editor-only, Dataflow)"},
    "nanite":       {"fn": t_nanite, "cat": "Create", "params": {},
                     "doc": "convierte un StaticMesh a Nanite sin tocar el original; "
                            "Run crea preview, Bake fija la copia y Discard la elimina"},
    # Mesh vive sólo en Graph: por sus cables fluye un DynamicMesh transitorio `M`. El tab no aparece
    # en Dash porque ejecutar una primitiva aislada allí no tiene un consumidor ni un asset que ver.
    "curve_bezier": {"fn": t_curve_bezier, "cat": "Mesh", "graph_only": True,
                     "params": {"start_x": 0.0, "start_y": 0.0, "start_z": 0.0,
                                "end_x": 0.0, "end_y": 0.0, "end_z": 500.0,
                                "bend_x": 0.0, "bend_y": 0.0, "bend_z": 0.0,
                                "segments": 8},
                     "doc": "crea una curva Bézier transitoria S para sweep, pipes y ramas"},
    "curve_child": {"fn": t_curve_child, "cat": "Mesh", "graph_only": True,
                    "params": {"at": 0.5, "length": 300.0, "angle": 55.0,
                               "azimuth": 0.0, "bend": 40.0, "radial_offset": 0.0,
                               "segments": 8, "samples": 32},
                    "doc": "crea una curva hija S anclada y orientada por el frame local de otra curva S"},
    "curve_noise": {"fn": t_curve_noise, "cat": "Mesh", "graph_only": True,
                    "params": {"amplitud": 10.0, "escala": 0.004, "octavas": 3,
                               "desde": 0.0, "seed": 0, "samples": 16},
                    "doc": "desvía una curva S perpendicular a su tangente con ruido; el tronco deja de ser un poste"},
    "curve_frames": {"fn": t_curve_frames, "cat": "Mesh", "graph_only": True,
                     "params": {"count": 12, "start": 0.0, "end": 1.0,
                                "radial_offset": 0.0, "turns": 0.0,
                                "angle_offset": 0.0, "radius_start": 0.0,
                                "radius_end": 0.0, "samples": 32, "seed": 7},
                     "doc": "samplea cada curva S como frames jerárquicos F con padre, índice, escala, radio, seed y pivote"},
    "distribute_frames": {"fn": t_distribute_frames, "cat": "Mesh", "graph_only": True,
                          "params": {"count": 12, "start": 0.0, "end": 1.0,
                                     "rotate_per_index": 137.5, "angle_offset": 0.0,
                                     "angle_jitter": 0.0, "parameter_jitter": 0.0,
                                     "seed": 7},
                          "doc": "redistribuye cada padre F por cantidad y rango, con giro e irregularidad deterministas"},
    "transform_frames": {"fn": t_transform_frames, "cat": "Mesh", "graph_only": True,
                         "params": {"offset_x": 0.0, "offset_y": 0.0,
                                    "offset_z": 0.0, "pitch": 0.0, "yaw": 0.0,
                                    "roll": 0.0, "scale": 1.0,
                                    "offset_jitter_x": 0.0, "offset_jitter_y": 0.0,
                                    "offset_jitter_z": 0.0, "pitch_jitter": 0.0,
                                    "yaw_jitter": 0.0, "roll_jitter": 0.0,
                                    "scale_jitter": 0.0, "inherit_scale": True,
                                    "seed": 7},
                         "doc": "desplaza, rota y escala frames F en sus ejes locales, con variación determinista"},
    "branch_from_frames": {"fn": t_branch_from_frames, "cat": "Mesh", "graph_only": True,
                           "params": {"length_min": 200.0, "length_max": 400.0,
                                      "angle": 55.0, "angle_jitter": 0.0,
                                      "curl": 20.0, "curl_jitter": 0.0,
                                      "segments": 8, "inherit_scale": True,
                                      "relative_to_parent": False, "profile": "",
                                      "seed": 7},
                           "data_params": {"profile": "N[]"},
                           "optional_data_params": ("profile",),
                           "doc": "crea una curva hija S por cada frame F. «relative_to_parent» mide el largo como fracción del padre en vez de centímetros; el perfil N[] opcional lo modula según dónde nace sobre el padre (silueta cónica)"},
    "asset_set": {"fn": t_asset_set, "cat": "Mesh", "graph_only": True,
                  "params": {}, "require_main_inputs": True,
                  "doc": "combina dos o más assets A como una colección ordenada A[] de variantes"},
    "choose_asset": {"fn": t_choose_asset, "cat": "Mesh", "graph_only": True,
                     "params": {"assets": "", "mode": "random", "seed": 7},
                     "data_params": {"assets": "A[]"},
                     "opciones": {"mode": ["random", "cycle", "parent"]},
                     "doc": "elige una variante A[] determinista para cada frame F y produce AF"},
    "graph_curve": {"fn": t_graph_curve, "cat": "Mesh", "graph_only": True,
                    "params": {"start_value": 1.0, "end_value": 0.15,
                               "shape": "custom", "power": 2.0,
                               "midpoint": 0.55, "mid_value": 0.72, "samples": 16},
                    "opciones": {"shape": ["linear", "ease_in", "ease_out", "smooth", "custom"]},
                    "doc": "crea un falloff numérico N[] editable en dominio 0..1"},
    "curve_branches": {"fn": t_curve_branches, "cat": "Mesh", "graph_only": True,
                       "params": {"count": 12, "start": 0.2, "end": 0.92,
                                  "length_min": 200.0, "length_max": 400.0,
                                  "parent_scale_start": 1.0, "parent_scale_end": 1.0,
                                  "angle": 70.0, "angle_jitter": 8.0,
                                  "rotate_per_index": 137.0, "azimuth": 0.0,
                                  "azimuth_jitter": 5.0, "bend": 40.0,
                                  "bend_jitter": 20.0, "radial_offset": 0.0,
                                  "segments": 8, "samples": 32, "seed": 7},
                       "doc": "genera una lista S de ramas sobre cada curva padre, con rango, giro por índice y seed estilo TreeGen"},
    "mesh_triangle": {"fn": t_mesh_triangle, "cat": "Mesh", "graph_only": True,
                      "params": {"size": 100.0},
                      "doc": "crea un triángulo procedural; fuente M"},
    "mesh_quad":    {"fn": t_mesh_quad, "cat": "Mesh", "graph_only": True,
                     "params": {"width": 100.0, "height": 100.0},
                     "doc": "crea un quad procedural con UV; fuente M"},
    "mesh_grid":    {"fn": t_mesh_grid, "cat": "Mesh", "graph_only": True,
                     "params": {"width": 500.0, "height": 500.0, "columns": 6, "rows": 6},
                     "doc": "crea una grilla procedural subdividida; fuente M"},
    "mesh_cylinder": {"fn": t_mesh_cylinder, "cat": "Mesh", "graph_only": True,
                      "params": {"radius": 50.0, "height": 200.0, "sides": 16,
                                 "height_steps": 1, "capped": True},
                      "doc": "crea un cilindro procedural parametrizado; fuente M"},
    "mesh_cone":    {"fn": t_mesh_cone, "cat": "Mesh", "graph_only": True,
                     "params": {"base_radius": 60.0, "top_radius": 0.0, "height": 200.0,
                                "sides": 16, "height_steps": 4, "capped": True},
                     "doc": "crea cono o tronco variando sus radios; fuente M"},
    "mesh_sphere":  {"fn": t_mesh_sphere, "cat": "Mesh", "graph_only": True,
                     "params": {"radius": 100.0, "latitude_steps": 8, "longitude_steps": 12},
                     "doc": "crea una esfera procedural de baja o alta resolución; fuente M"},
    "mesh_from_asset": {"fn": t_mesh_from_asset, "cat": "Mesh", "graph_only": True,
                        "params": {},
                        "doc": "convierte la geometría de un StaticMesh A en una malla transitoria M"},
    "mesh_pipe":    {"fn": t_mesh_pipe, "cat": "Mesh", "graph_only": True,
                     "params": {"radius_start": 30.0, "radius_end": 5.0,
                                "sides": 10, "samples": 16, "capped": True,
                                "profile_rotation": 0.0, "miter_limit": 4.0,
                                "radius_from_parent": 0.0, "pivot_uvs": False},
                     "doc": "barre un perfil circular sobre una curva S con taper lineal; salida M"},
    "mesh_pipe_profile": {"fn": t_mesh_pipe_profile, "cat": "Mesh", "graph_only": True,
                          "params": {"profile": "", "radius": 30.0,
                                     "sides": 10, "samples": 16, "capped": True,
                                     "profile_rotation": 0.0, "miter_limit": 4.0,
                                     "pivot_uvs": False},
                          "data_params": {"profile": "N[]"},
                          "doc": "barre S usando un perfil de radio N[] no lineal; salida M"},
    "mesh_along_curve": {"fn": t_mesh_along_curve, "cat": "Mesh", "graph_only": True,
                         "asset_argument": True,
                         "params": {"count": 12, "start": 0.1, "end": 0.95,
                                    "radial_offset": 30.0, "turns": 2.0,
                                    "angle_offset": 0.0, "scale_start": 0.45,
                                    "scale_end": 0.25, "scale_x": 1.0,
                                    "scale_y": 1.0, "scale_z": 1.0,
                                    "orientation": "outward", "rotation_jitter": 0.0,
                                    "scale_jitter": 0.0, "offset_jitter": 0.0, "seed": 7,
                                    "crossed": False, "double_sided": False, "samples": 32},
                         "opciones": {"orientation": ["outward", "world_up", "random"]},
                         "doc": "copia un StaticMesh A con escala, orientación y variación sobre una curva S"},
    "copy_mesh_to_frames": {"fn": t_copy_mesh_to_frames, "cat": "Mesh", "graph_only": True,
                            "asset_argument": True,
                            "params": {"asset_offset_x": 0.0, "asset_offset_y": 0.0,
                                       "asset_offset_z": 0.0, "asset_pitch": 0.0,
                                       "asset_yaw": 0.0, "asset_roll": 0.0,
                                       "asset_scale": 1.0, "scale_x": 1.0,
                                       "scale_y": 1.0, "scale_z": 1.0,
                                       "inherit_scale": True},
                            "doc": "copia una StaticMesh A sobre cada frame F usando su transform y escala"},
    "copy_asset_selection": {"fn": t_copy_asset_selection, "cat": "Mesh", "graph_only": True,
                             "params": {"asset_offset_x": 0.0, "asset_offset_y": 0.0,
                                        "asset_offset_z": 0.0, "asset_pitch": 0.0,
                                        "asset_yaw": 0.0, "asset_roll": 0.0,
                                        "asset_scale": 1.0, "scale_x": 1.0,
                                        "scale_y": 1.0, "scale_z": 1.0,
                                        "inherit_scale": True},
                             "doc": "copia la selección AF usando una variante distinta por frame"},
    "hism_output": {"fn": t_hism_output, "cat": "Mesh", "graph_only": True,
                    "params": {"name": "TreeGen_Foliage",
                               "asset_offset_x": 0.0, "asset_offset_y": 0.0,
                               "asset_offset_z": 0.0, "asset_pitch": 0.0,
                               "asset_yaw": 0.0, "asset_roll": 0.0,
                               "asset_scale": 1.0, "inherit_scale": True},
                    "doc": "crea un actor con un HISM por variante AF; participa de Preview/Bake/Discard"},
    "mesh_leaf": {"fn": t_mesh_leaf, "cat": "Mesh", "graph_only": True,
                  "asset_argument": True, "optional_asset_argument": True,
                  "params": {"count": 4, "start": 0.1, "end": 0.95,
                             "radial_offset": 20.0, "rotate_per_index": 137.0,
                             "angle_offset": 0.0, "leaves_per_cluster": 3,
                             "length": 90.0, "width": 45.0,
                             "asset_scale": 1.0, "asset_pitch": 0.0,
                             "asset_yaw": 0.0, "asset_roll": 0.0,
                             "size_start": 1.0, "size_end": 0.7,
                             "splay": 70.0, "lift": 18.0,
                             "rotation_jitter": 12.0, "scale_jitter": 0.2,
                             "offset_jitter": 4.0, "seed": 7,
                             "inherit_scale": False, "double_sided": True, "samples": 32},
                  "doc": "genera racimos de hojas sobre S; el pin A opcional usa una StaticMesh real y sin A conserva el follaje procedural portable"},
    "mesh_transform": {"fn": t_mesh_transform, "cat": "Mesh", "graph_only": True,
                       "params": {"x": 0.0, "y": 0.0, "z": 0.0, "pitch": 0.0,
                                  "yaw": 0.0, "roll": 0.0, "scale_x": 1.0,
                                  "scale_y": 1.0, "scale_z": 1.0},
                       "doc": "mueve, rota y escala una malla M sin modificar la entrada"},
    "mesh_color": {"fn": t_mesh_color, "cat": "Mesh", "graph_only": True,
                   "params": {"color": "#808080"},
                   "doc": "asigna un Vertex Color #RRGGBB a una malla M sin modificar la entrada"},
    "material_wind": {"fn": t_material_wind, "cat": "Shader", "graph_only": True,
                      "params": {"name": "M_JamArbolViento", "folder": "/Game/Jam/Materials",
                                 "fuerza": 0.25, "velocidad": 1.2, "concentracion": 2.0,
                                 "eje_x": 1.0, "eje_y": 0.3, "eje_z": 0.0},
                      "doc": "material de viento que gira cada rama sobre el pivote estampado en UV1/UV2; salida A"},
    "material_node": {"fn": t_material_node, "cat": "Shader", "graph_only": True,
                      "params": {"type": "Multiply", "id": "", "inputs": "", "props": "",
                                 "x": 0, "y": 0},
                      "doc": "agrega un nodo al grafo de material (cualquiera de los 409 tipos); "
                             "`inputs` cablea lo que ya existe (A=uv, B=escala); salida MT"},
    "material_connect": {"fn": t_material_connect, "cat": "Shader", "graph_only": True,
                         "params": {"from_node": "", "to_node": "", "to_input": "",
                                    "from_output": ""},
                         "doc": "conecta dos nodos del grafo de material por nombre de entrada; salida MT"},
    "material_output": {"fn": t_material_output, "cat": "Shader", "graph_only": True,
                        "params": {"node": "", "target": "MP_BASE_COLOR", "from_output": ""},
                        "opciones": {"target": list(_SALIDAS_MATERIAL)},
                        "doc": "enchufa un nodo a una salida del material (BaseColor, Roughness, WPO...); salida MT"},
    "material_build": {"fn": t_material_build, "cat": "Shader", "graph_only": True,
                       "params": {"name": "M_JamMaterial", "folder": "/Game/Jam/Materials",
                                  "blend_mode": "", "shading_model": "", "two_sided": False,
                                  "use_attributes": False, "max_instructions": 0},
                       "opciones": {"blend_mode": ["", "BLEND_OPAQUE", "BLEND_MASKED",
                                                   "BLEND_TRANSLUCENT", "BLEND_ADDITIVE"],
                                    "shading_model": ["", "MSM_DEFAULT_LIT", "MSM_UNLIT",
                                                      "MSM_SUBSURFACE", "MSM_TWO_SIDED_FOLIAGE"]},
                       "doc": "hornea el grafo MT como material de verdad; verifica antes de crear nada "
                              "y MIDE el costo (max_instructions = presupuesto, 0 = sin límite); salida A"},
    "mesh_uv_box": {"fn": t_mesh_uv_box, "cat": "Mesh", "graph_only": True,
                    "params": {"size_x": 0.0, "size_y": 0.0, "size_z": 0.0,
                               "yaw": 0.0, "pitch": 0.0, "roll": 0.0,
                               "channel": 0, "min_island_tris": 2},
                    "doc": "proyección CÚBICA de UVs (el UV cubic map): seis planos, cada triángulo al que mejor mira. size 0 = la caja se ajusta a la malla"},
    "mesh_uv_unwrap": {"fn": t_mesh_uv_unwrap, "cat": "Mesh", "graph_only": True,
                       "params": {"method": "conformal", "channel": 0, "align_to_axes": True},
                       "opciones": {"method": ["conformal", "spectral_conformal", "exp_map"]},
                       "doc": "despliega resolviendo el aplanado en vez de proyectar: menos estiramiento, más costuras"},
    "mesh_uv_pack": {"fn": t_mesh_uv_pack, "cat": "Mesh", "graph_only": True,
                     "params": {"resolution": 1024, "channel": 0, "optimize_rotation": True},
                     "doc": "empaqueta las islas en el atlas 0..1 (el uvlayout de Houdini) y dice cuánto quedó usado"},
    "material_function": {"fn": t_material_function, "cat": "Shader", "graph_only": True,
                          "params": {"name": "MF_JamFuncion", "folder": "/Game/Jam/Functions",
                                     "kind": "funcion", "description": ""},
                          "opciones": {"kind": ["funcion", "capa", "mezcla"]},
                          "doc": "hornea el grafo MT como FUNCIÓN reusable (o capa/mezcla de Material Layers); salida A"},
    "material_call": {"fn": t_material_call, "cat": "Shader", "graph_only": True,
                      "params": {"function": "", "id": "", "inputs": "", "x": 0, "y": 0},
                      "doc": "llama a una función de material dentro del grafo; sus entradas se DESCUBREN del asset; salida MT"},
    "material_instance": {"fn": t_material_instance, "cat": "Shader", "graph_only": True,
                          "params": {"name": "MI_JamInstancia", "folder": "/Game/Jam/Materials",
                                     "parent": "", "scalars": "", "vectors": ""},
                          "doc": "instancia del material con parámetros fijados: variantes sin recompilar; salida A"},
    "mesh_vertex_gradient": {"fn": t_mesh_vertex_gradient, "cat": "Mesh", "graph_only": True,
                             "params": {"eje": "z", "desde": 0.0, "hasta": 1.0,
                                        "power": 1.0, "canal": "todos"},
                             "doc": "pinta un gradiente 0..1 en el color de vértice de M: la máscara que el shader de viento necesita"},
    "mesh_uv_scale": {"fn": t_mesh_uv_scale, "cat": "Mesh", "graph_only": True,
                      "params": {"u": 1.0, "v": 1.0, "channel": 0,
                                 "origin_u": 0.0, "origin_v": 0.0},
                      "doc": "escala un canal UV existente sobre toda la malla M"},
    "mesh_material": {"fn": t_mesh_material, "cat": "Mesh", "graph_only": True,
                      "params": {"material": "/Engine/EngineMaterials/DefaultMaterial.DefaultMaterial",
                                 "material_asset": ""},
                      "data_params": {"material_asset": "A"},
                      "optional_data_params": ("material_asset",),
                      "doc": "asigna material y section a M; el pin A acepta la salida de material_build "
                             "(y manda sobre el campo); Mesh to Static conserva el slot"},
    "mesh_merge":  {"fn": t_mesh_merge, "cat": "Mesh", "graph_only": True, "params": {},
                     "doc": "combina dos o más mallas M en una salida"},
    "mesh_normals": {"fn": t_mesh_normals, "cat": "Mesh", "graph_only": True,
                     "params": {"angle_weighted": True, "area_weighted": True},
                     "doc": "recalcula normales conservando los atributos de la malla M"},
    "debug": {"fn": t_debug, "cat": "Debug", "graph_only": True,
              "params": {"tamano": 30.0, "grosor": 1.2, "escalar_con_dato": True,
                         "cada": 1, "solo_direccion": False},
              "doc": "AYUDANTE universal: conectale CUALQUIER cable y dibuja lo que corresponde. F→ejes por frame · P→cubo por punto (tamaño=peso) · S→recorrido de la curva · N[]→la serie como gráfico · M→caja + normales · AF→frames por variante. Sale por M: se mergea, hornea o coloca",
              },
    "points_to_frames": {"fn": t_points_to_frames, "cat": "Mesh", "graph_only": True,
                         "params": {"orientacion": "normal", "escala": 1.0,
                                    "escala_desde_peso": True, "giro_al_azar": True, "seed": 7},
                         "opciones": {"orientacion": ["normal", "vertical"]},
                         "doc": "PUENTE P → F: convierte el stream de puntos de Flow en frames. El peso de la máscara pasa a ser la escala de cada pieza"},
    "mesh_box": {"fn": t_mesh_box, "cat": "Mesh", "graph_only": True,
                 "params": {"size_x": 100.0, "size_y": 100.0, "size_z": 100.0,
                            "steps_x": 0, "steps_y": 0, "steps_z": 0},
                 "doc": "caja con el pivote en la BASE (apoya sola, como pide un kit)"},
    "mesh_capsule": {"fn": t_mesh_capsule, "cat": "Mesh", "graph_only": True,
                     "params": {"radius": 30.0, "length": 150.0,
                                "hemisphere_steps": 5, "sides": 12},
                     "doc": "cápsula: la forma de blockout y colisión por excelencia"},
    "mesh_torus": {"fn": t_mesh_torus, "cat": "Mesh", "graph_only": True,
                   "params": {"major_radius": 100.0, "minor_radius": 25.0,
                              "major_steps": 24, "minor_steps": 12},
                   "doc": "toro (dona); minor_radius tiene que ser menor que major_radius"},
    "mesh_disc": {"fn": t_mesh_disc, "cat": "Mesh", "graph_only": True,
                  "params": {"radius": 100.0, "sides": 24, "start_angle": 0.0,
                             "end_angle": 360.0, "hole_radius": 0.0},
                  "doc": "disco plano; con hole_radius es un anillo y con los ángulos, una porción"},
    "mesh_round_rect": {"fn": t_mesh_round_rect, "cat": "Mesh", "graph_only": True,
                        "params": {"size_x": 200.0, "size_y": 200.0,
                                   "corner_radius": 20.0, "steps_round": 6},
                        "doc": "rectángulo de esquinas redondeadas en el plano XY"},
    "mesh_stairs": {"fn": t_mesh_stairs, "cat": "Mesh", "graph_only": True,
                    "params": {"step_width": 150.0, "step_height": 18.0, "step_depth": 28.0,
                               "steps": 10, "floating": False},
                    "doc": "escalera recta; «floating» deja los escalones sueltos, sin faldón"},
    "mesh_stairs_curved": {"fn": t_mesh_stairs_curved, "cat": "Mesh", "graph_only": True,
                           "params": {"step_width": 150.0, "step_height": 18.0,
                                      "inner_radius": 200.0, "curve_angle": 90.0,
                                      "steps": 12, "floating": False},
                           "doc": "escalera curva; curve_angle con signo elige el sentido del giro"},
    "mesh_sphere_box": {"fn": t_mesh_sphere_box, "cat": "Mesh", "graph_only": True,
                        "params": {"radius": 80.0, "steps": 6},
                        "doc": "esfera de topología cúbica: cuadrángulos parejos, sin los polos apretados de la lat/long"},
    "mesh_revolve": {"fn": t_mesh_revolve, "cat": "Mesh", "graph_only": True,
                     "params": {"steps": 24, "capped": True, "degrees": 360.0, "samples": 32},
                     "doc": "TORNO: revoluciona el perfil de una curva S alrededor del eje Z (x = distancia al eje, z = altura). Columnas, balaustres, vasijas"},
    "mesh_bark": {"fn": t_mesh_bark, "cat": "Mesh", "graph_only": True,
                  "params": {"amplitud": 2.0, "escala": 0.06, "alargue": 0.25,
                             "octavas": 3, "surcos": 0.6, "seed": 7},
                  "doc": "relieve de corteza sobre M: ruido estirado a lo largo del eje (surcos verticales) desplazando cada vértice por su normal. «amplitud» debe ser menor que el radio más fino de la malla o la punta se invierte"},
    "mesh_compare": {"fn": t_mesh_compare, "cat": "Mesh", "graph_only": True,
                     "asset_argument": True,
                     "params": {"franjas": 8, "solo_forma": False,
                                "alto": 0.30, "ancho": 0.35, "esbeltez": 0.20,
                                "vertices": 0.50, "triangulos": 0.50,
                                "perfil": 0.15, "silueta": 0.18},
                     "doc": "ORÁCULO: compara la malla M contra un StaticMesh de referencia (tamaño, proporción, conteos, secciones, perfil de masa y silueta) y la deja pasar sin tocarla. «solo_forma» compara la FORMA sin exigir el mismo tamaño"},
    "mesh_to_static": {"fn": t_mesh_to_static, "cat": "Mesh", "graph_only": True,
                       "params": {"name": "GeneratedMesh", "folder": "/Game/Jam/Meshes",
                                  "collision": True, "recompute_tangents": True,
                                  "show_vertex_colors": True},
                       "doc": "convierte M a StaticMesh A y muestra sus Vertex Colors; Preview/Bake/Discard"},
    "pcg":          {"fn": t_pcg,     "cat": "Scatter",
                     "params": {"area": 1600.0, "count": 200, "density": 0.0, "view": False,
                                "name": "JamPCG", "preset": ""},
                     "doc": "realiza el scatter (o un preset) con el PCG nativo (HISM, regenerable)"},
    "gizmo":        {"fn": t_gizmo,   "cat": "Edit",    "params": {"on": True},
                     "doc": "marca en el viewport dónde está parado Jam + la huella del asset activo"},
    "ghost":        {"fn": t_ghost,   "cat": "Edit",    "params": {"on": True},
                     "doc": "muestra la malla que se va a colocar siguiendo el punto de mira"},
}

# Verbos que NO crean nada COLOCABLE: son selección, helpers o escritores de Content y por ahora no
# pasan por el Preview de actores. PCG ya no pertenece acá: su PCGVolume y su PCGGraph temporal
# participan juntos de Run/Bake/Discard.
SIN_SPAWN = {"asset", "pick", "gizmo", "ghost", "pivot", "pivot_set", "normalize", "fracture"}

# Orden de las categorías en la barra (como Dash). Las vacías no se muestran.
# Las seis primeras son verbos de herramienta; las que siguen llegan de las ops de Flow que ahora
# también son verbos del Graph (ver `_registrar_ops_flow`). El orden agrupa por lo que hace cada
# familia: generar puntos → filtrarlos → pesarlos → reordenarlos → moverlos → juntarlos → mirarlos.
CATEGORIAS = ["Content", "Place", "Scatter", "Create", "Mesh", "Edit",
              "Vector", "Mask", "Weight", "Sets", "Transform", "Combine", "Display", "Debug"]

# Contrato del Graph. Vive junto al REGISTRO para que Slate y el Preflight lean la misma verdad.
# `source` significa sin pin gordo `in`; una fuente todavía puede tener un pin de parámetro `asset`.
GRAPH_SOURCES = {"asset", "pick", "create_spline", "gizmo", "ghost", "pivot", "pivot_set",
                 "curve_bezier", "mesh_triangle", "mesh_quad", "mesh_grid", "mesh_cylinder",
                 "mesh_cone", "mesh_sphere", "graph_curve",
                 "mesh_box", "mesh_capsule", "mesh_torus", "mesh_disc",
                 "mesh_round_rect", "mesh_stairs", "mesh_stairs_curved", "mesh_sphere_box"}
# Tools que realmente pueden ejecutarse sin un asset. `asset` y `pick` lo PRODUCEN; `create_spline` y
# `pivot_set` trabajan sobre la escena/selección. Gizmo y Ghost sí necesitan uno para mostrar huella.
GRAPH_NO_ASSET = {"asset", "pick", "create_spline", "pivot_set", "instance",
                  # `scatter` genera PUNTOS: no toca ningún asset. Lo usaba sólo para
                  # medir huellas, y eso ahora pasa al colocar.
                  "scatter",
                  "curve_bezier", "mesh_triangle", "mesh_quad", "mesh_grid", "mesh_cylinder",
                  "mesh_cone", "mesh_sphere", "mesh_pipe", "mesh_pipe_profile",
                  "mesh_box", "mesh_capsule", "mesh_torus", "mesh_disc",
                  "mesh_round_rect", "mesh_stairs", "mesh_stairs_curved",
                  "mesh_sphere_box", "mesh_revolve",
                  "mesh_transform", "mesh_merge", "graph_curve",
                  "curve_child", "curve_frames", "distribute_frames", "transform_frames",
                  "branch_from_frames",
                  "asset_set", "choose_asset", "curve_branches", "mesh_leaf",
                  "copy_asset_selection", "hism_output",
                  "mesh_color", "mesh_uv_scale", "mesh_material", "mesh_bark", "points_to_frames", "debug",
                  "mesh_normals", "mesh_to_static",
                  # UVs procedurales y todo el frente de shader: ninguno necesita un asset de
                  # entrada — trabajan sobre la malla que les llega o sobre el grafo de material.
                  # Sin estar acá, `validar` los rechaza con «requiere asset explícito» y NO se
                  # pueden correr desde el canvas, aunque llamar a su función directamente funcione.
                  "mesh_uv_box", "mesh_uv_unwrap", "mesh_uv_pack",
                  "material_node", "material_connect", "material_output", "material_build",
                  "material_function", "material_call", "material_instance", "material_wind",
                  # Dos que estaban rotos desde que se agregaron y nadie podía correr en el canvas:
                  # transforman el dato que les llega y no tocan ningún asset.
                  "curve_noise", "mesh_vertex_gradient"}
GRAPH_IN_NAMES = {"points_to_frames": "P", "debug": "*", "curve_child": "S", "curve_noise": "S", "curve_frames": "S", "distribute_frames": "F",
                  "transform_frames": "F", "branch_from_frames": "F", "curve_branches": "S",
                  "asset_set": "A", "choose_asset": "F",
                  "mesh_from_asset": "A", "mesh_pipe": "S", "mesh_pipe_profile": "S",
                  "mesh_revolve": "S",
                  "mesh_along_curve": "S", "copy_mesh_to_frames": "F", "mesh_leaf": "S",
                  "copy_asset_selection": "AF",
                  "hism_output": "AF", "mesh_transform": "M", "mesh_color": "M",
                  "mesh_uv_scale": "M", "mesh_material": "M", "mesh_bark": "M",
                  "mesh_vertex_gradient": "M", "mesh_merge": "M", "mesh_normals": "M",
                  "mesh_uv_box": "M", "mesh_uv_unwrap": "M", "mesh_uv_pack": "M",
                  # Entrada OPCIONAL: sin cable reparte en un área; con puntos, alrededor de cada uno.
                  "scatter": "P",
                  "mesh_compare": "M", "mesh_to_static": "M",
                  "material_node": "MT", "material_connect": "MT", "material_output": "MT",
                  "material_build": "MT", "material_function": "MT", "material_call": "MT",
                  "material_instance": "A", "instance": "P"}
GRAPH_OUT_NAMES = {"points_to_frames": "F", "debug": "M", "asset": "A", "pick": "A", "create_spline": "S",
                   # `scatter` describe DÓNDE (puntos) y `instance` decide cuándo eso se vuelve
                   # escena. Es lo que le da un significado obvio a encadenar nodos de colocación.
                   "scatter": "P", "instance": "A",
                   "material_wind": "A", "material_build": "A",
                   "material_node": "MT", "material_connect": "MT", "material_output": "MT",
                   "material_call": "MT", "material_function": "A", "material_instance": "A",
                   "curve_bezier": "S", "curve_child": "S", "curve_noise": "S", "curve_frames": "F",
                   "distribute_frames": "F", "transform_frames": "F",
                   "branch_from_frames": "S", "curve_branches": "S",
                   "asset_set": "A[]", "choose_asset": "AF", "graph_curve": "N[]",
                   "mesh_triangle": "M", "mesh_quad": "M", "mesh_grid": "M",
                   "mesh_cylinder": "M", "mesh_cone": "M", "mesh_sphere": "M",
                   "mesh_box": "M", "mesh_capsule": "M", "mesh_torus": "M",
                   "mesh_disc": "M", "mesh_round_rect": "M", "mesh_stairs": "M",
                   "mesh_stairs_curved": "M", "mesh_sphere_box": "M", "mesh_revolve": "M",
                   "mesh_from_asset": "M", "mesh_pipe": "M", "mesh_pipe_profile": "M",
                   "mesh_along_curve": "M",
                   "copy_mesh_to_frames": "M", "mesh_leaf": "M",
                   "copy_asset_selection": "M",
                   "hism_output": "H", "mesh_transform": "M", "mesh_color": "M",
                   "mesh_uv_scale": "M", "mesh_material": "M", "mesh_bark": "M",
                   "mesh_vertex_gradient": "M", "mesh_merge": "M", "mesh_normals": "M",
                  "mesh_uv_box": "M", "mesh_uv_unwrap": "M", "mesh_uv_pack": "M",
                  # Entrada OPCIONAL: sin cable reparte en un área; con puntos, alrededor de cada uno.
                  "scatter": "P",
                   "mesh_compare": "M", "mesh_to_static": "A"}
# ---- las ops de Flow como verbos del Graph ----
# Hasta acá Jam tenía dos vocabularios que no se tocaban: 29 ops de Flow que producen un stream de
# puntos `P`, y 50 verbos de herramienta de los que NINGUNO consumía `P`. Un canvas mixto caía entero
# al runner de verbos, donde cada op de Flow era desconocida.
# El ejecutor del Graph es genérico —`info["fn"](entrada, **params)` más `dato_producido_runtime`—,
# así que envolver una op es mecánico. Con esto las máscaras, los weights y los generadores de puntos
# alimentan el tab Mesh, y `points_to_frames` cierra el puente `P → F`.
# `instance` y `source_surface` quedan afuera: sus funciones viven en el adaptador de Unreal.
# `number`, `math` y `text` también: el Graph ya los maneja como nodos de VALOR.

def _envolver_op_flow(kind: str, aridad: int):
    """Adapta la firma de una op de Flow —(list[stream], params) → stream— a la de un verbo."""
    def fn(entrada=None, **params):
        from . import flow
        implementacion = flow.OPS[kind][0]
        if aridad == 0:
            entradas = []
        elif aridad == -1:
            entradas = [e for e in (entrada or []) if e is not None]
        else:
            entradas = [entrada] if entrada is not None else []
        salida = implementacion(entradas, params)
        _RUNTIME_DATA_OUTPUTS[kind] = salida
        cantidad = len(salida) if isinstance(salida, (list, tuple)) else 0
        etiqueta = kind.replace("_", " ").upper()
        return f"{etiqueta} P ✓ — {cantidad} puntos"
    fn.__name__ = f"t_{kind}"
    return fn


# ---- los nodos de material, uno por ficha ----
# `material_node` puede crear cualquiera de los 408 tipos escribiendo su nombre, pero eso es una
# línea de comando disfrazada de nodo: para usarlo hay que SABER que `Lerp` se llama
# `LinearInterpolate`. El resto de Jam funciona al revés —una ficha por verbo, con su icono y su
# firma en el tooltip— y no hay razón para que el tab de shader sea la excepción.
#
# Éstos son los que se usan todo el tiempo. Los otros 390 siguen a un `material_node` de distancia,
# que queda como la puerta a lo que no está en la paleta.
NODOS_MATERIAL: dict[str, tuple[str, str]] = {
    # Constantes y parámetros: de dónde salen los números
    "mat_const":     ("Constant", "un número fijo"),
    "mat_color":     ("Constant3Vector", "un color/vector fijo (prop `constant=#RRGGBB`)"),
    "mat_scalar":    ("ScalarParameter", "número con NOMBRE: se retoca en una instancia sin recompilar"),
    "mat_vector":    ("VectorParameter", "color con NOMBRE: se retoca en una instancia"),
    # Matemática
    "mat_add":       ("Add", "A + B"),
    "mat_sub":       ("Subtract", "A − B"),
    "mat_mul":       ("Multiply", "A × B"),
    "mat_div":       ("Divide", "A ÷ B"),
    "mat_lerp":      ("LinearInterpolate", "mezcla A y B según Alpha (el Lerp de UE)"),
    "mat_power":     ("Power", "Base elevado a Exp: endurece o suaviza un gradiente"),
    "mat_clamp":     ("Clamp", "recorta entre Min y Max"),
    "mat_oneminus":  ("OneMinus", "1 − x: invierte una máscara"),
    "mat_saturate":  ("Saturate", "recorta a 0..1"),
    # Texturas y coordenadas
    "mat_texture":   ("TextureSample", "muestrea una textura (prop `texture=/Game/...`)"),
    "mat_uv":        ("TextureCoordinate", "las UVs de la malla (prop `coordinate_index`)"),
    "mat_panner":    ("Panner", "desplaza unas UVs con el tiempo: texturas que se mueven"),
    "mat_noise":     ("Noise", "ruido procedural, sin textura"),
    # Vectores
    "mat_append":    ("AppendVector", "junta A y B en un vector más ancho"),
    "mat_mask":      ("ComponentMask", "toma canales sueltos (props r/g/b/a)"),
    "mat_normalize": ("Normalize", "vector a largo 1"),
    "mat_dot":       ("DotProduct", "producto punto: cuánto se parecen dos direcciones"),
    # Lo que aporta la geometría y la escena
    "mat_worldpos":  ("WorldPosition", "la posición del píxel en el mundo"),
    "mat_vnormal":   ("VertexNormalWS", "la normal del vértice"),
    "mat_vcolor":    ("VertexColor", "el color de vértice pintado en la malla"),
    "mat_time":      ("Time", "el reloj: lo que hace que algo se mueva"),
    "mat_fresnel":   ("Fresnel", "más fuerte en los bordes vistos de canto"),
}


def _envolver_nodo_material(verbo: str, tipo: str):
    """Un verbo por tipo de nodo, todos sobre la misma implementación.

    No es una copia de `t_material_node` por nodo: es el mismo, con el tipo ya elegido. Así una
    corrección al armado vale para los veintipico de una vez.
    """
    def fn(mat_input=None, *, id="", inputs="", props="", x=0, y=0) -> str:
        return t_material_node(mat_input, type=tipo, id=id, inputs=inputs, props=props,
                               x=x, y=y, _verbo=verbo)
    fn.__name__ = f"t_mat_{tipo.lower()}"
    return fn


def _registrar_nodos_material() -> list[str]:
    from . import shader

    registrados = []
    for verbo, (tipo, doc) in NODOS_MATERIAL.items():
        entradas = shader.ENTRADAS.get(tipo, ())
        # La firma va en el DOC porque es lo que se necesita para cablearlo, y va derivada del motor
        # para que no pueda mentir: si UE renombra un pin, el tooltip cambia solo.
        firma = f" · entradas: {', '.join(entradas)}" if entradas else " · sin entradas"
        REGISTRO[verbo] = {
            "fn": _envolver_nodo_material(verbo, tipo), "cat": "Shader", "graph_only": True,
            "params": {"id": "", "inputs": "", "props": "", "x": 0, "y": 0},
            "doc": f"{tipo}: {doc}{firma}", "_nodo_material": tipo,
        }
        GRAPH_IN_NAMES[verbo] = "MT"
        GRAPH_OUT_NAMES[verbo] = "MT"
        GRAPH_MIN_INPUTS[verbo] = 0      # cualquiera puede arrancar un grafo de material
        GRAPH_NO_ASSET.add(verbo)
        registrados.append(verbo)
    return registrados


def _registrar_ops_flow() -> list[str]:
    from . import flow
    registradas = []
    for kind, meta in flow.OPS_META.items():
        if kind in REGISTRO or kind not in flow.OPS or kind in flow.VALOR_KINDS:
            continue
        aridad = flow.OPS[kind][1]
        REGISTRO[kind] = {
            "fn": _envolver_op_flow(kind, aridad), "cat": meta.get("cat", "Flow"),
            "graph_only": True, "params": dict(meta.get("params", {})),
            "opciones": dict(meta.get("opciones", {})),
            "doc": meta.get("doc", ""), "_flow_op": True,
        }
        GRAPH_IN_NAMES[kind] = "" if aridad == 0 else "P"
        GRAPH_OUT_NAMES[kind] = "P"
        if aridad == 0:
            GRAPH_SOURCES.add(kind)
        else:
            GRAPH_ARITY[kind] = aridad
            if aridad == -1:
                GRAPH_MIN_INPUTS[kind] = 2
        GRAPH_NO_ASSET.add(kind)
        registradas.append(kind)
    return registradas


GRAPH_ARITY = {"mesh_merge": -1, "asset_set": -1}
# `material_node` tiene pin de entrada MT pero el PRIMER nodo de una cadena no tiene de dónde
# venir: con el mínimo en 1 haría falta un verbo `material_new` de puro trámite en el canvas.
GRAPH_MIN_INPUTS = {"mesh_merge": 2, "asset_set": 2, "material_node": 0, "scatter": 0,
                    "material_call": 0, "material_instance": 0}
OPS_FLOW_EN_GRAPH = _registrar_ops_flow()
NODOS_MATERIAL_EN_GRAPH = _registrar_nodos_material()

for _nombre, _info in REGISTRO.items():
    _source = _nombre in GRAPH_SOURCES
    _info["source"] = _source
    _info["aridad"] = GRAPH_ARITY.get(_nombre, 0 if _source else 1)
    _info["min_inputs"] = GRAPH_MIN_INPUTS.get(_nombre, 0 if _source else 1)
    _info["in_name"] = "" if _source else GRAPH_IN_NAMES.get(_nombre, "A")
    _info["asset_required"] = _nombre not in GRAPH_NO_ASSET
    # `asset_pin` = este verbo CONSUME un asset (y hay que resolvérselo). No confundir con dibujar
    # una fila: son dos preguntas distintas y mezclarlas rompe la resolución.
    _info["asset_pin"] = bool(
        _info["asset_required"] or _info.get("optional_asset_argument", False))
    # `asset_row` = tiene una fila `asset` en el canvas: pin con NOMBRE y campo de texto, que se
    # grisea solo cuando le entra un cable (como cualquier otro param cableado).
    #
    # La tiene todo el que consume un asset. Cuando además su entrada principal es de tipo A, esa
    # fila ES la entrada principal y el nub anónimo del header se oculta — el duplicado no eran la
    # fila y el nub, era tener los DOS. Se queda el que dice qué es.
    _info["asset_row"] = bool(_info["asset_pin"])
    _info["out_name"] = GRAPH_OUT_NAMES.get(_nombre, "A")


def spec_json(*, include_graph_only: bool = False) -> str:
    """El registro como JSON (categoría/verbo/doc/params) para que la Dash Bar en C++ se arme sola.
    Agregar una herramienta a REGISTRO la hace aparecer en su sección sin tocar C++."""
    import json

    def tipo(v) -> str:
        # el TIPO viaja en el spec para que la UI use el control expresivo que corresponde
        # (checkbox para bool, spinner para números) en vez de un campo de texto para todo.
        if isinstance(v, bool):
            return "bool"
        if isinstance(v, int):
            return "int"
        if isinstance(v, float):
            return "float"
        return "str"

    salida = []
    for nombre, info in REGISTRO.items():
        if info.get("graph_only") and not include_graph_only:
            continue
        opciones = info.get("opciones", {})
        salida.append({
            "verbo": nombre,
            "cat": info.get("cat", "Place"),
            "doc": info["doc"],
            "source": info["source"],
            "aridad": info["aridad"],
            # Tipo del pin gordo de entrada: en el grafo de verbos viaja el asset/actor activo.
            "in_name": info["in_name"],
            "asset_pin": info["asset_pin"],
            "asset_row": info["asset_row"],
            "out_name": info["out_name"],
            # `opciones` → la UI dibuja una LISTA en vez de un campo de texto (anclas, modos…)
            "params": [{"nombre": k, "default": str(v), "tipo": tipo(v),
                        "data_type": info.get("data_params", {}).get(k, ""),
                        "opciones": opciones.get(k, [])}
                       for k, v in info["params"].items()],
        })
    return json.dumps({"categorias": CATEGORIAS, "tools": salida}, ensure_ascii=True)
