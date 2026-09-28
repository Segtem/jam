"""Registro de herramientas de Jam — la ÚNICA definición de cada capacidad (params + acción + oráculo).

Los front-ends (el panel de botones y la consola DSL) sólo resuelven el asset y los params, y llaman
acá. Cada herramienta spawnea en el nivel y devuelve el texto del veredicto de SU oráculo. Escalar =
agregar una entrada a REGISTRO (una fn param-driven), sin tocar UMG ni la consola.
"""

from __future__ import annotations

import unreal

from . import flow as _flow
from .registro import (  # noqa: F401 — se reexportan: `tools.X` sigue valiendo para todos
    _ANCLAS, _SALIDAS_MATERIAL, CATEGORIAS, GRAPH_ARITY, GRAPH_IN_NAMES, GRAPH_MIN_INPUTS,
    GRAPH_NO_ASSET, GRAPH_OUT_NAMES, GRAPH_SOURCES, NODOS_MATERIAL, NODOS_MATERIAL_EN_GRAPH,
    OPS_FLOW_EN_GRAPH, PARAMS_ANGULARES, PARAMS_MUDADOS, REGISTRO, SIN_SPAWN, necesita_instanciar,
    spec_json, unidad_de)


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
            kw, errores = dsl.coaccionar(r["verbo"], r["params"])
            if errores:
                raise RuntimeError(f"preset «{preset}»: " + "; ".join(errores))
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
            anchor="base", sink=0.0, align=False, yaw=0.0, scale=1.0,
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
        return _en_puntos(asset, points, anchor=anchor, sink=sink, align=align, apilar=False,
                          scale_min=float(scale_min), scale_max=float(scale_max), verbo="PLACE")

    actor = place.colocar(asset, (x, y, z - sink), (0.0, 0.0, yaw), (scale, scale, scale),
                          view=view, surface=surface, anchor=anchor, align=align)
    if actor is None:
        return f"no se pudo colocar {_corto(asset)}"
    return _veredicto_entorno(actor)


def _en_puntos(asset, puntos, *, anchor, sink, align, scale_min, scale_max,
               apilar=False, verbo="PLACE") -> str:
    """Pone el asset en cada punto. La ÚNICA diferencia entre `place` y `drop` es `apilar`.

    `place` reparte en un plano: lo que se cruzaría se descarta por huella. `drop` deja caer: nada
    se descarta —solaparse es la condición de que algo se apile— y después la tanda se asienta.

    Estaban en el mismo verbo con una perilla `physics`, y era confuso de la peor manera: el mismo
    nodo hacía dos cosas distintas y había que acordarse de cuál. Ahora el nombre del verbo lo dice.

    Lo demás —el dedup por HUELLA REAL, el oráculo doble— es idéntico, así que vive una sola vez.

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
    vivos, pisados = sc.repartir_o_apilar(list(puntos), radio_por, apilar=apilar)

    actores = scatter.instanciar_puntos(
        vivos, mallas, scale_min=scale_min, scale_max=scale_max, sink=sink,
        anchor=anchor, align=align, etiqueta="Jam_place")
    ue.seleccionar(actores)

    # El paso que convierte «sembrar» en PINTAR: la tanda se asienta contra el mundo y contra sí
    # misma, así que las piezas se apilan en vez de quedar todas clavadas en la misma cota.
    asentado = ""
    if apilar and actores:
        from . import physics as fisica, physics_core
        asentado = "\n" + physics_core.resumen(fisica.asentar_actores(actores))

    xs = [p.pos.x for p in vivos] or [0.0]
    ys = [p.pos.y for p in vivos] or [0.0]
    centro = ((min(xs) + max(xs)) / 2.0, (min(ys) + max(ys)) / 2.0)
    semi = (max(1.0, (max(xs) - min(xs)) / 2.0), max(1.0, (max(ys) - min(ys)) / 2.0))
    existentes = ue.vecinos_en_zona(centro, semi, ignorar=actores)
    oraculo = ue.scatter_texto(actores, centro, semi, len(vivos), existentes=existentes)
    return _veredicto_place(len(actores), len(puntos), len(pisados), asentado, oraculo, verbo)


def _veredicto_place(colocados: int, puntos: int, pisados: int, asentado: str, oraculo: str,
                     verbo: str = "PLACE") -> str:
    """El renglón de PLACE. Puro a propósito: la regla que importa —CERO colocados no puede decir
    \u2713— se prueba sin motor.

    Decía «PLACE \u2713 — 0 en 8 punto(s)» y el nodo se pintaba verde. Un tilde sobre cero piezas es
    exactamente la clase de veredicto que este proyecto existe para no dar.
    """
    extra = f" · {pisados} evitados por huella" if pisados else ""
    if colocados == 0:
        return (f"{verbo} \u2717 \u2014 no se colocó ninguna de las {puntos} piezas{extra} "
                f"\u2014 mirá «[Jam] colocar» en el log")
    return (f"{verbo} \u2713 \u2014 {colocados} en {puntos} punto(s){extra}{asentado}\n{oraculo}")


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
    "drop": ("x", "y"),
    "scatter": ("x", "y"),
}
# `pcg` y `fracture` no entran: no tienen params de posición donde escribirla. Con `view` apagado
# nacen en el origen — está anotado como pendiente, no disimulado con una captura que no existe.


PISTA_INSTANCE = "  \u2192 encha\u00falo al pin `points` de un `place` para colocarlos"


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
    oraculo = ue.scatter_texto(actores, centro, semi, len(puntos), existentes=existentes)
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


def t_drop(asset, *, points=None, x=0.0, y=0.0, height=800.0, view=True, anchor="base",
           sink=0.0, align=False, scale_min=1.0, scale_max=1.0) -> str:
    """Deja CAER: con puntos, una pieza por punto y la tanda se apila; sin puntos, una sola a plomo
    desde `height`. Es el hermano de `place`, que coloca en un plano y no deja que nada se cruce."""
    from . import physics, place, ue

    if points:
        # `height` no entra acá a propósito: el aterrizaje es determinista —cada pieza va al top de
        # lo que la sostiene— así que soltarla desde 8 m o desde 80 da exactamente lo mismo. Poner
        # la perilla igual sería otra que no hace nada.
        return _en_puntos(asset, points, anchor=anchor, sink=sink, align=align, apilar=True,
                          scale_min=float(scale_min), scale_max=float(scale_max), verbo="DROP")

    # Sin puntos: una sola pieza, a plomo. Antes caía SIEMPRE en (0,0) —a kilómetros de la cámara
    # en un mundo abierto— y parecía que la herramienta no había hecho nada.
    caja = place.colocar(asset, (x, y, height), anchor=anchor, view=view)
    if caja is None:
        return f"DROP \u2717 \u2014 no se pudo colocar {_corto(asset)}"
    r = physics.soltar(caja)                          # cae sobre la geometría real del nivel
    return f"cae {r['caida']}cm \u2192 " + ue.physics_texto(caja)


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


def t_nanite_analyze(asset, *, lod=0) -> str:
    """Mide Nanite sin modificar el asset y lo deja pasar por su salida A."""
    from . import nanite, nanite_core
    r = nanite.analizar(asset, lod=int(lod))
    if "error" in r:
        raise RuntimeError(r["error"])
    _RUNTIME_ASSET_OUTPUTS["nanite_analyze"] = r["asset"]
    return nanite_core.texto_analisis(r)


def t_nanite_validate(asset, *, lod=0) -> str:
    """Exige que el asset tenga una representación Nanite construida y lo deja pasar por A."""
    from . import nanite, nanite_core
    r = nanite.validar(asset, lod=int(lod))
    if "error" in r:
        raise RuntimeError(r["error"])
    if not r["valido"]:
        raise RuntimeError(nanite_core.texto_validacion(r))
    _RUNTIME_ASSET_OUTPUTS["nanite_validate"] = r["asset"]
    return nanite_core.texto_validacion(r)


def _mesh_output(verbo: str, result: dict, label: str) -> str:
    if "error" in result:
        raise RuntimeError(result["error"])
    _RUNTIME_DATA_OUTPUTS[verbo] = result["mesh"]
    return f"{label} ✓ — {result.get('info', 'DynamicMesh')}"


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


def _select(verbo: str, etiqueta: str, cond, si, no) -> str:
    """Elige una de dos ramas según un booleano. El cuerpo compartido de todos los `select_*`.

    Las DOS ramas ya se calcularon: esto es dataflow, no flujo de ejecución — corre todo lo que esté
    cableado y acá sólo se elige cuál sigue viaje. Es el Dispatch de Grasshopper, no el Branch de
    Blueprint, y la diferencia importa: poner un `select` no ahorra el trabajo de la rama descartada.
    """
    if cond is None:
        raise RuntimeError("«cond» necesita un cable booleano (usá una comparación)")
    elegido = si if cond else no
    rama = "sí" if cond else "no"
    if elegido is None:
        raise RuntimeError(f"la rama «{rama}» no tiene nada conectado")
    _RUNTIME_DATA_OUTPUTS[verbo] = elegido
    return f"SELECT {etiqueta} ✓ — siguió por «{rama}»"


def t_reroute(entrada=None, **_kw) -> str:
    """Punto de paso con forma de NODO: no toca el dato, sólo lo deja pasar.

    No publica nada en `_RUNTIME_DATA_OUTPUTS` a propósito: el runner ya cae a `entrada` cuando un
    verbo no produce salida propia (el mismo mecanismo del bypass), así que dejar pasar es
    literalmente no hacer nada. Por eso los cinco `reroute_*` comparten esta función y sólo se
    diferencian en los tipos que declaran.
    """
    return "REROUTE ✓"


def t_brush(_input=None, *, actor="", alto=200.0) -> str:
    """Pincel: marca los centros de reparto (salida P). No reparte — de eso se ocupa `scatter`.

    Dos formas de decir DÓNDE, y el orden importa:

      · con **nombre** (`actor`): busca ese actor por su etiqueta. El grafo queda AUTOCONTENIDO —
        se guarda, se reabre y da lo mismo. Es la única forma válida para una herramienta publicada:
        no puede depender de qué haya quedado seleccionado.
      · sin nombre: usa lo ELEGIDO en el nivel. Es el gesto cómodo —poner un actor, moverlo con el
        gizmo, correr— pero depende del estado del editor.

    El nombre gana cuando está puesto. La selección no sobrevive fuera de la GUI (comprobado: en
    commandlet `set_selected_level_actors` no vuelve por `get_`), así que es también el único camino
    verificable sin editor.
    """
    from . import brush_core, ue
    from . import scatter_core as sc

    etiqueta = str(actor).strip()
    if etiqueta:
        elegidos = [a for a in ue.actores_nivel()
                    if a and a.get_actor_label() == etiqueta]
        if not elegidos:
            raise RuntimeError(
                f"no encontré ningún actor llamado «{etiqueta}» en el nivel; "
                "dejá el campo vacío para usar el que tengas elegido")
    else:
        elegidos = list(ue._sub().get_selected_level_actors())
        if not elegidos:
            raise RuntimeError(
                "el pincel necesita un actor: elegí uno en el nivel (cualquiera sirve, movelo con "
                "el gizmo) o escribí su nombre en «actor» para que el grafo no dependa de la "
                "selección")

    posiciones = []
    for a in elegidos:
        loc = a.get_actor_location()
        posiciones.append((loc.x, loc.y, loc.z))

    puntos = []
    for x, y, z in brush_core.centros(posiciones, alto=float(alto)):
        puntos.append(sc.Sample(ue.Vec3(x, y, z), ue.Vec3(0.0, 0.0, 1.0), 0.0,
                                brush_core.semilla_por_centro(7, x, y), (0.5, 0.5)))
    _RUNTIME_DATA_OUTPUTS["brush"] = puntos
    cuantos = len(puntos)
    return (f"BRUSH ✓ — {cuantos} pincel(es) a {float(alto):.0f} cm de altura; "
            f"enchufalo a un scatter para repartir alrededor")


def t_select_mesh(_input=None, *, cond=None, si=None, no=None) -> str:
    return _select("select_mesh", "M", cond, si, no)


def t_select_asset(_input=None, *, cond=None, si=None, no=None) -> str:
    return _select("select_asset", "A", cond, si, no)


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


def t_mesh_triangle(_input=None, *, size=100.0) -> str:
    from . import mesh
    return _mesh_output("mesh_triangle", mesh.triangle(size=float(size)), "TRIANGLE M")


def t_mesh_from_asset(asset_input) -> str:
    from . import mesh
    return _mesh_output("mesh_from_asset", mesh.from_asset(asset_input), "FROM ASSET M")


def t_mesh_copy_static(asset_input, *, lod_type="max_available", lod_index=0,
                       apply_build_settings=True, request_tangents=True,
                       use_build_scale=True) -> str:
    from . import mesh
    return _mesh_output(
        "mesh_copy_static",
        mesh.copy_static(
            asset_input, lod_type=lod_type, lod_index=int(lod_index),
            apply_build_settings=bool(apply_build_settings),
            request_tangents=bool(request_tangents), use_build_scale=bool(use_build_scale)),
        "COPIAR STATIC M")


def t_mesh_copy_skeletal(asset_input, *, lod_type="max_available", lod_index=0,
                         apply_build_settings=True, request_tangents=True,
                         use_build_scale=True) -> str:
    from . import mesh
    return _mesh_output(
        "mesh_copy_skeletal",
        mesh.copy_skeletal(
            asset_input, lod_type=lod_type, lod_index=int(lod_index),
            apply_build_settings=bool(apply_build_settings),
            request_tangents=bool(request_tangents), use_build_scale=bool(use_build_scale)),
        "COPIAR SKELETAL M")


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


def t_mesh_ribbon(curve_input, *, width=360.0, plane="xy", join="miter",
                  miter_limit=4.0, uv_scale=200.0, material_id=0, samples=32) -> str:
    from . import mesh
    result = mesh.ribbon(
        curve_input, width=float(width), plane=str(plane), join=str(join),
        miter_limit=float(miter_limit), uv_scale=float(uv_scale),
        material_id=int(material_id), samples=int(samples))
    return _mesh_output("mesh_ribbon", result, "RIBBON M")


def t_mesh_extrude(mesh_input, *, distance=300.0, direction_x=0.0,
                   direction_y=0.0, direction_z=1.0, uv_scale=100.0) -> str:
    from . import mesh
    result = mesh.extrude(
        mesh_input, distance=float(distance), direction_x=float(direction_x),
        direction_y=float(direction_y), direction_z=float(direction_z),
        uv_scale=float(uv_scale))
    return _mesh_output("mesh_extrude", result, "EXTRUDE M")


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


def t_mesh_remap_materials(mesh_input, *, from_id=1, to_id=0) -> str:
    from . import mesh
    return _mesh_output(
        "mesh_remap_materials",
        mesh.reassign_material_ids(mesh_input, from_id=from_id, to_id=to_id),
        "REASIGNAR MATERIAL IDS M",
    )


def t_mesh_clean_material_ids(mesh_input, *, remove_duplicate_materials=True) -> str:
    from . import mesh
    return _mesh_output(
        "mesh_clean_material_ids",
        mesh.clean_material_ids(
            mesh_input, remove_duplicate_materials=bool(remove_duplicate_materials)),
        "LIMPIAR MATERIAL IDS M",
    )


def t_mesh_validate(mesh_input, *, require_closed=False, max_components=0,
                    require_uv=False, require_materials=False) -> str:
    from . import mesh
    result = mesh.validate(
        mesh_input, require_closed=bool(require_closed), max_components=int(max_components),
        require_uv=bool(require_uv), require_materials=bool(require_materials))
    if "error" in result:
        raise RuntimeError(result["error"])
    _RUNTIME_DATA_OUTPUTS["mesh_validate"] = result["mesh"]
    mark = "✓" if result["ok"] else "✗"
    defects = "" if result["ok"] else " · " + "; ".join(result["defects"])
    return f"VALIDAR M {mark} — {result['info']}{defects}"


def t_mesh_merge(mesh_inputs) -> str:
    from . import mesh
    return _mesh_output("mesh_merge", mesh.merge(mesh_inputs), "MERGE M")


def t_mesh_loft(curve_inputs, *, samples=16, uv_scale=200.0, material_id=0) -> str:
    from . import mesh
    return _mesh_output("mesh_loft", mesh.loft(
        curve_inputs, samples=int(samples), uv_scale=float(uv_scale),
        material_id=int(material_id)), "LOFT M")


def t_mesh_normals(mesh_input, *, angle_weighted=True, area_weighted=True) -> str:
    from . import mesh
    result = mesh.normals(mesh_input, angle_weighted=bool(angle_weighted),
                          area_weighted=bool(area_weighted))
    return _mesh_output("mesh_normals", result, "NORMALS M")


def t_mesh_weld(mesh_input, *, tolerance_cm=0.01, only_unique_pairs=True) -> str:
    from . import mesh
    return _mesh_output(
        "mesh_weld",
        mesh.weld(
            mesh_input, tolerance_cm=tolerance_cm, only_unique_pairs=bool(only_unique_pairs)),
        "SOLDAR BORDES M",
    )


def t_mesh_simplify_count(mesh_input, *, target_triangles=5000, method="attributes",
                          preserve_seams=True, regularize=0.000001) -> str:
    from . import mesh
    return _mesh_output(
        "mesh_simplify_count",
        mesh.simplify_count(
            mesh_input, target_triangles=target_triangles, method=str(method),
            preserve_seams=bool(preserve_seams), regularize=regularize),
        "SIMPLIFICAR POR TRIÁNGULOS M",
    )


def t_mesh_simplify_tolerance(mesh_input, *, tolerance_cm=1.0, method="attributes",
                              preserve_seams=True, regularize=0.000001) -> str:
    from . import mesh
    return _mesh_output(
        "mesh_simplify_tolerance",
        mesh.simplify_tolerance(
            mesh_input, tolerance_cm=tolerance_cm, method=str(method),
            preserve_seams=bool(preserve_seams), regularize=regularize),
        "SIMPLIFICAR POR TOLERANCIA M",
    )


def t_mesh_simplify_edge_length(mesh_input, *, edge_length_cm=5.0, method="attributes",
                                preserve_seams=True, regularize=0.000001) -> str:
    from . import mesh
    return _mesh_output(
        "mesh_simplify_edge_length",
        mesh.simplify_edge_length(
            mesh_input, edge_length_cm=edge_length_cm, method=str(method),
            preserve_seams=bool(preserve_seams), regularize=regularize),
        "SIMPLIFICAR POR ARISTA M",
    )


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


def t_mass_probe(frame_input) -> str:
    """Primera vertical Mass: crea, mide y limpia entidades, y deja pasar el mismo F."""
    from . import mass_core, ue

    prepared = mass_core.prepare(frame_input)
    if "error" in prepared:
        raise RuntimeError(prepared["error"])
    batch = prepared["batch"]
    result = mass_core.judge(batch, ue.mass_probe(batch))
    if not result["ok"]:
        raise RuntimeError("MassEntity no verificó: " + "; ".join(result["defects"]))
    _RUNTIME_DATA_OUTPUTS["mass_probe"] = frame_input
    return f"MASS PROBE F ✓ — {result['info']}"


def t_mass_config(_input=None, *, path="", require_ism=False,
                  require_lod_budget=False, require_patrol=False,
                  require_variation=False) -> str:
    """Ruta de asset → MC: valida traits y template mediante MassGameplay."""
    from . import mass_core, ue

    result = mass_core.make_config(
        path, ue.mass_config(str(path or "").strip()),
        require_ism=bool(require_ism),
        require_lod_budget=bool(require_lod_budget),
        require_patrol=bool(require_patrol),
        require_variation=bool(require_variation))
    if "error" in result:
        raise RuntimeError(result["error"])
    config = result["config"]
    _RUNTIME_DATA_OUTPUTS["mass_config"] = config
    representation = (f" · ISM estacionario · LOD {config.lod_distances}"
                      if config.representation == "ism" else "")
    budget = (f" · máximos LOD {config.lod_max_counts}"
              if require_lod_budget else "")
    variacion = (f" · variación {config.patrol_variation:.2f}"
                 if config.patrol_variation else "")
    behavior = (f" · patrulla {config.patrol_speed:g} cm/s en radio {config.patrol_radius:g} cm"
                if config.behavior == "patrol" else "")
    return (f"MASS CONFIG MC ✓ — {config.config_path} · template espacial válido"
            f"{representation}{budget}{behavior}{variacion}")


def t_mass_spec(frame_input, *, config="", config_path="", seed=7, budget=4096) -> str:
    """F → MS: construye una receta durable sin tocar Unreal."""
    from . import mass_core

    result = mass_core.make_spec(
        frame_input, config=config, config_path=config_path, seed=seed, budget=budget)
    if "error" in result:
        raise RuntimeError(result["error"])
    spec = result["spec"]
    _RUNTIME_DATA_OUTPUTS["mass_spec"] = spec
    config = spec.config_path or "arquetipo base FTransformFragment"
    return (f"MASS SPEC MS ✓ — {len(spec)} entidades · presupuesto {spec.budget} · "
            f"seed {spec.seed} · {config}")


def _mass_clear_handle(handle):
    from . import mass_core, ue

    result = mass_core.judge_clear(handle, ue.mass_clear(handle))
    if not result["ok"]:
        raise RuntimeError("MassEntity no limpió: " + "; ".join(result["defects"]))
    return result


def t_mass_spawn(spec_input) -> str:
    """MS → MH: crea una población viva y la incorpora a Preview/Discard."""
    from . import mass_core, panel, ue

    if not isinstance(spec_input, mass_core.MassSpec):
        raise RuntimeError("mass_spawn necesita una receta MS válida")
    facts = ue.mass_spawn(spec_input)
    result = mass_core.handle_from_spawn(spec_input, facts)
    if "error" in result:
        # Si C++ alcanzó a crear una población pero sus hechos no cumplen el contrato, no se fuga.
        if facts.get("population_id") and facts.get("world_id"):
            provisional = mass_core.MassHandle(
                str(facts["population_id"]), str(facts["world_id"]),
                len(spec_input), spec_input.position_sum)
            ue.mass_clear(provisional)
        raise RuntimeError("MassEntity no creó la población: " + result["error"])
    handle = result["handle"]
    panel.registrar_efecto_preview(
        lambda h=handle: _mass_clear_handle(h),
        descripcion=f"población Mass {handle.population_id}")
    _RUNTIME_DATA_OUTPUTS["mass_spawn"] = handle
    return f"MASS SPAWN MH ✓ — {handle.requested} entidades vivas · {handle.population_id}"


def t_mass_inspect(handle_input) -> str:
    """MH → MH: mide una población viva sin modificarla."""
    from . import mass_core, ue

    if not isinstance(handle_input, mass_core.MassHandle):
        raise RuntimeError("mass_inspect necesita un handle MH válido")
    result = mass_core.judge_inspect(handle_input, ue.mass_inspect(handle_input))
    if not result["ok"]:
        raise RuntimeError("MassEntity no verificó la población: " + "; ".join(result["defects"]))
    _RUNTIME_DATA_OUTPUTS["mass_inspect"] = handle_input
    return f"MASS INSPECT MH ✓ — {result['info']}"


def t_mass_clear(handle_input) -> str:
    """MH → MH: libera de forma idempotente la población indicada."""
    from . import mass_core

    if not isinstance(handle_input, mass_core.MassHandle):
        raise RuntimeError("mass_clear necesita un handle MH válido")
    result = _mass_clear_handle(handle_input)
    _RUNTIME_DATA_OUTPUTS["mass_clear"] = handle_input
    return f"MASS CLEAR MH ✓ — {result['info']}"


def t_mesh_box(_input=None, *, size_x=100.0, size_y=100.0, size_z=100.0,
               steps_x=0, steps_y=0, steps_z=0) -> str:
    """Base común: la caja la calcula el NÚCLEO (`jam.comun`); Unreal sólo la vuelve DynamicMesh.
    La misma que la de Geometry Script, medida por el motor en `verifica_caja_comun_58.py`."""
    from . import comun, malla_core, mesh
    try:
        malla, _texto = comun.IMPLEMENTA["mesh_box"](_input, size_x=size_x, size_y=size_y, size_z=size_z,
                                                     steps_x=steps_x, steps_y=steps_y, steps_z=steps_z)
    except malla_core.MallaError as e:
        raise RuntimeError(str(e)) from None
    dm = mesh.desde_malla(malla)
    return _mesh_output("mesh_box", {
        "mesh": dm,
        "info": f"{mesh._info(dm)} · {float(size_x):g}×{float(size_y):g}×{float(size_z):g}cm"}, "BOX M")


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


def t_mesh_noise(mesh_input, *, amplitud=100.0, frecuencia=0.003,
                 seed=7, por_normal=True) -> str:
    """Ruido Perlin 3D nativo de UE 5.8 sobre M; útil para terreno y formas orgánicas."""
    from . import mesh
    return _mesh_output(
        "mesh_noise",
        mesh.noise(mesh_input, amplitud=float(amplitud), frecuencia=float(frecuencia),
                   seed=int(seed), por_normal=bool(por_normal)),
        "PERLIN M",
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


def t_mesh_preview(mesh_input, *, name="JamPreview") -> str:
    """Muestra la malla en el nivel SIN hornearla. Es el nodo del live view.

    Se agrega como verbo y NO como un modo de `mesh_to_static` a propósito: hornear produce un asset
    `A` y mostrar produce un actor, así que hacer que el mismo verbo devuelva una cosa u otra según
    un modo le rompería el tipo a todo lo que cuelga aguas abajo —`place`, por ejemplo—. Son dos
    verbos porque son dos salidas distintas.

    Medido: mostrar cuesta ~1 ms contra los 68–257 ms de hornear la misma cadena.
    """
    from . import mesh
    result = mesh.mostrar(mesh_input, name=str(name or "JamPreview"))
    if "error" in result:
        raise RuntimeError(result["error"])
    return (f"PREVIEW ✓ — {result['triangulos']} triángulos sin hornear. "
            "Cambiá lo que quieras y volvé a correr; Bake recién cuando te guste.")


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


# ---- el adaptador de Unreal: cada verbo del registro neutro, con su implementación ----
# La DESCRIPCIÓN de cada verbo vive en `jam.registro` (puro). Acá se le enchufa `"fn"`: el ejecutor
# del Graph sigue llamando `info["fn"](entrada, **params)` sobre el mismo diccionario.
# ponytail: se inyecta en el mismo dict para no mudar a los ~40 consumidores de `tools.REGISTRO`;
# la etapa 2 (contrato JSON por adaptador) cambia el ejecutor para que pida la implementación acá.

def _envolver_comun(verbo: str):
    """Un verbo de la base común: lo calcula `jam.comun` —el mismo código que corre con Godot— y
    acá sólo se guarda lo que produjo para el que sigue."""
    def fn(entrada=None, **params):
        from . import comun
        dato, texto = comun.IMPLEMENTA[verbo](entrada, **params)
        _RUNTIME_DATA_OUTPUTS[verbo] = dato
        return texto
    fn.__name__ = f"t_{verbo}"
    return fn


def _envolver_comun_malla(verbo: str, etiqueta: str):
    """Un GENERADOR de la base común: la malla la calcula `jam.comun` y Unreal sólo la vuelve
    DynamicMesh (`mesh.desde_malla`). Los OPERADORES comunes (mesh_transform, mesh_merge) siguen con
    Geometry Script acá: reciben también mallas de verbos propios de Unreal, con materiales y
    colores que la malla del núcleo no lleva; que den lo mismo lo prueba el fixture de Unreal."""
    def fn(entrada=None, **params):
        from . import comun, malla_core, mesh
        try:
            malla, _texto = comun.IMPLEMENTA[verbo](entrada, **params)
        except malla_core.MallaError as e:
            raise RuntimeError(str(e)) from None
        dm = mesh.desde_malla(malla)
        _RUNTIME_DATA_OUTPUTS[verbo] = dm
        return f"{etiqueta} ✓ — {mesh._info(dm)}"
    fn.__name__ = f"t_{verbo}"
    return fn


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



IMPLEMENTA = {
    "asset": t_asset,
    "pick": t_pick,
    "pivot": t_pivot,
    "normalize": t_normalize,
    "pivot_set": t_pivot_set,
    "place": t_place,
    "scatter": t_scatter,
    "drop": t_drop,
    "snap": t_snap,
    "replace": t_replace,
    "spline": t_spline,
    "create_spline": t_create_spline,
    "fracture": t_fracture,
    "nanite": t_nanite,
    "nanite_analyze": t_nanite_analyze,
    "nanite_validate": t_nanite_validate,
    "curve_bezier": _envolver_comun("curve_bezier"),
    "curve_child": _envolver_comun("curve_child"),
    "curve_noise": t_curve_noise,
    "curve_frames": _envolver_comun("curve_frames"),
    "distribute_frames": _envolver_comun("distribute_frames"),
    "transform_frames": _envolver_comun("transform_frames"),
    "branch_from_frames": _envolver_comun("branch_from_frames"),
    "reroute_mesh": t_reroute,
    "reroute_asset": t_reroute,
    "reroute_points": t_reroute,
    "reroute_curve": t_reroute,
    "reroute_frames": t_reroute,
    "brush": t_brush,
    "select_mesh": t_select_mesh,
    "select_asset": t_select_asset,
    "asset_set": t_asset_set,
    "choose_asset": t_choose_asset,
    "graph_curve": _envolver_comun("graph_curve"),
    "series_range": _envolver_comun("series_range"),
    "series_remap": _envolver_comun("series_remap"),
    "curve_polyline": _envolver_comun("curve_polyline"),
    "curve_interpolate": _envolver_comun("curve_interpolate"),
    "curve_line": _envolver_comun("curve_line"),
    "curve_line_sdl": _envolver_comun("curve_line_sdl"),
    "curve_move": _envolver_comun("curve_move"),
    "curve_resample": _envolver_comun("curve_resample"),
    "curve_smooth": _envolver_comun("curve_smooth"),
    "curve_fuse_collinear": _envolver_comun("curve_fuse_collinear"),
    "curve_subdivide": _envolver_comun("curve_subdivide"),
    "curve_offset": _envolver_comun("curve_offset"),
    "curve_branches": _envolver_comun("curve_branches"),
    "mesh_triangle": t_mesh_triangle,
    "mesh_quad": _envolver_comun_malla("mesh_quad", "QUAD M"),
    "mesh_grid": _envolver_comun_malla("mesh_grid", "GRID M"),
    "mesh_cylinder": _envolver_comun_malla("mesh_cylinder", "CYLINDER M"),
    "mesh_cone": _envolver_comun_malla("mesh_cone", "CONE M"),
    "mesh_sphere": _envolver_comun_malla("mesh_sphere", "SPHERE M"),
    "mesh_from_asset": t_mesh_from_asset,
    "mesh_copy_static": t_mesh_copy_static,
    "mesh_copy_skeletal": t_mesh_copy_skeletal,
    "mesh_ribbon": t_mesh_ribbon,
    "mesh_extrude": t_mesh_extrude,
    "mesh_pipe": t_mesh_pipe,
    "mesh_pipe_profile": t_mesh_pipe_profile,
    "mesh_along_curve": t_mesh_along_curve,
    "copy_mesh_to_frames": t_copy_mesh_to_frames,
    "copy_asset_selection": t_copy_asset_selection,
    "hism_output": t_hism_output,
    "mass_probe": t_mass_probe,
    "mass_config": t_mass_config,
    "mass_spec": t_mass_spec,
    "mass_spawn": t_mass_spawn,
    "mass_inspect": t_mass_inspect,
    "mass_clear": t_mass_clear,
    "mesh_leaf": t_mesh_leaf,
    "mesh_transform": t_mesh_transform,
    "mesh_color": t_mesh_color,
    "material_wind": t_material_wind,
    "material_node": t_material_node,
    "material_connect": t_material_connect,
    "material_output": t_material_output,
    "material_build": t_material_build,
    "mesh_uv_box": t_mesh_uv_box,
    "mesh_uv_unwrap": t_mesh_uv_unwrap,
    "mesh_uv_pack": t_mesh_uv_pack,
    "material_function": t_material_function,
    "material_call": t_material_call,
    "material_instance": t_material_instance,
    "mesh_vertex_gradient": t_mesh_vertex_gradient,
    "mesh_uv_scale": t_mesh_uv_scale,
    "mesh_material": t_mesh_material,
    "mesh_remap_materials": t_mesh_remap_materials,
    "mesh_clean_material_ids": t_mesh_clean_material_ids,
    "mesh_validate": t_mesh_validate,
    "mesh_loft": t_mesh_loft,
    "mesh_merge": t_mesh_merge,
    "mesh_normals": t_mesh_normals,
    "mesh_weld": t_mesh_weld,
    "mesh_simplify_count": t_mesh_simplify_count,
    "mesh_simplify_tolerance": t_mesh_simplify_tolerance,
    "mesh_simplify_edge_length": t_mesh_simplify_edge_length,
    "debug": t_debug,
    "points_to_frames": _envolver_comun("points_to_frames"),
    "mesh_box": t_mesh_box,
    "mesh_capsule": t_mesh_capsule,
    "mesh_torus": t_mesh_torus,
    "mesh_disc": _envolver_comun_malla("mesh_disc", "DISC M"),
    "mesh_round_rect": t_mesh_round_rect,
    "mesh_stairs": t_mesh_stairs,
    "mesh_stairs_curved": t_mesh_stairs_curved,
    "mesh_sphere_box": t_mesh_sphere_box,
    "mesh_revolve": t_mesh_revolve,
    "mesh_bark": t_mesh_bark,
    "mesh_noise": t_mesh_noise,
    "mesh_compare": t_mesh_compare,
    "mesh_preview": t_mesh_preview,
    "mesh_to_static": t_mesh_to_static,
    "pcg": t_pcg,
    "gizmo": t_gizmo,
    "ghost": t_ghost,
}
IMPLEMENTA.update({kind: _envolver_op_flow(kind, _flow.OPS[kind][1]) for kind in OPS_FLOW_EN_GRAPH})
IMPLEMENTA.update({verbo: _envolver_nodo_material(verbo, NODOS_MATERIAL[verbo][0])
                   for verbo in NODOS_MATERIAL_EN_GRAPH})
for _verbo, _fn in IMPLEMENTA.items():
    REGISTRO[_verbo]["fn"] = _fn

MOTOR = "unreal"


def implementacion(verbo: str):
    """Lo que el ejecutor del Graph le pide al adaptador (ver `graph.ejecutar_detalle`)."""
    return REGISTRO[verbo]["fn"]


def motor_activo() -> tuple[str, frozenset | None]:
    """El motor del otro lado y lo que implementa: `("unreal", IMPLEMENTA)`.

    `JAM_MOTOR_SIMULADO=godot` hace de cuenta que el conectado es otro motor —se juzga por lo
    DECLARADO en `registro`, porque ese adaptador todavía no existe—: sirve para ver en el canvas y
    en el Compile qué verbos quedarían deshabilitados antes de tener Godot.
    """
    import os
    simulado = os.environ.get("JAM_MOTOR_SIMULADO", "").strip().lower()
    if simulado and simulado != MOTOR:
        return simulado, None
    # Lo que tiene `fn` AHORA, no la foto de IMPLEMENTA al importar: un verbo enchufado después
    # (una prueba, un plugin) también está implementado.
    return MOTOR, frozenset(v for v, info in REGISTRO.items() if callable(info.get("fn")))
