"""Registro de herramientas de Jam — la ÚNICA definición de cada capacidad (params + acción + oráculo).

Los front-ends (el panel de botones y la consola DSL) sólo resuelven el asset y los params, y llaman
acá. Cada herramienta spawnea en el nivel y devuelve el texto del veredicto de SU oráculo. Escalar =
agregar una entrada a REGISTRO (una fn param-driven), sin tocar UMG ni la consola.
"""

from __future__ import annotations

import unreal


def _sub():
    return unreal.get_editor_subsystem(unreal.EditorActorSubsystem)


def _corto(ruta: str) -> str:
    return ruta.rsplit(".", 1)[-1] if ruta else "asset"


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


def t_gizmo(asset, *, on=True) -> str:
    """Enciende/apaga el gizmo que marca DÓNDE ESTÁ PARADO Jam en el viewport (el punto de mira,
    que es donde coloca `place`) + la huella del asset activo."""
    from . import gizmo
    return gizmo.encender() if on else gizmo.apagar()


def t_ghost(asset, *, on=True) -> str:
    """Enciende/apaga el FANTASMA: la malla del asset activo siguiendo el punto de mira, para ver
    qué y de qué tamaño va a caer antes de colocarlo."""
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


def t_place(asset, *, x=0.0, y=0.0, z=0.0, view=True, surface=True, anchor="base", sink=0.0,
            align=False, physics=False, yaw=0.0, scale=1.0) -> str:
    """Coloca un ladrillo en relación a su entorno: `view`=en el punto de mira del viewport (x/y/z
    son offset), `surface`=raycast al piso, `anchor`=por qué punto de la pieza se coloca (base,
    center, corner, xmin…), `sink`=cuántos cm hundirla en la superficie (para que una roca no se vea
    apoyada como una calcomanía), `align`=orientar a la normal, `physics`=asentar por caída, `yaw`/`scale`.
    El oráculo del entorno verifica APOYADO sobre una superficie (gap≈0) + SIN CLAVARSE con los
    vecinos (geometría, no el soporte ni el landscape)."""
    from . import place
    actor = place.colocar(asset, (x, y, z - sink), (0.0, 0.0, yaw), (scale, scale, scale),
                          view=view, surface=surface, anchor=anchor, align=align, physics=physics)
    if actor is None:
        return f"no se pudo colocar {_corto(asset)}"
    return _veredicto_entorno(actor)


def _veredicto_entorno(actor) -> str:
    """Oráculo de PLACE: ¿el ladrillo quedó bien en su entorno? APOYADO sobre superficie (raycast,
    gap≈0, con su pendiente) + SIN CLAVARSE con vecinos reales (excluye soporte, landscape y no-geometría)."""
    import unreal as U
    from . import geometry, oracle_placement, physics, ue
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
    r = oracle_placement.verificar(ue.pieza(actor), ue.piezas(vecinos))
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


def t_scatter(asset, *, count=24, area=800.0, pattern="poisson", spacing=0.0, rings=3,
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
    cx, cy = 0.0, 0.0
    if view:
        mira = ue.punto_de_mira()
        if mira is not None and mira["punto"] is not None:
            cx, cy = mira["punto"].x, mira["punto"].y
    centro, semi = (cx, cy), (area, area)

    actores, v = scatter.esparcir_rico(
        asset, centro, semi, cantidad=count, patron=pattern, spacing=spacing, anillos=int(rings),
        seed=seed, surface=surface, align=align, slope_max=slope_max,
        height_min=(height_min if height_min else None),
        height_max=(height_max if height_max else None),
        noise=noise, density=density, scale_min=scale_min, scale_max=scale_max, espaciado=spread,
        sink=sink, anchor=anchor)
    if "error" in v:
        return v["error"]
    ue.seleccionar(actores)
    return _veredicto_scatter(actores, centro, semi, v)


def _veredicto_scatter(actores, centro, semi, v) -> str:
    """Reporte del reparto: cuánto pasó el filtro + el oráculo (cantidad/contención/clavado/cobertura)."""
    from . import ue
    cab = (f"SCATTER · {v['colocados']} colocados de {v['candidatos']} candidatos "
           f"({v['patron']}, sep {v['spacing']}cm, {v['assets']} asset(s), {v['mascaras']} máscara(s), "
           f"{v['filtrados']} filtrados, {v['pisados']} evitados por huella)")
    oraculo = ue.scatter_texto(actores, centro, semi, len(actores))
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
    etiqueta = actor.get_actor_label() if actor is not None else "spline"
    return f"SPLINE creado ✓ — «{etiqueta}»: editá sus puntos y usá «spline» para levantar piezas."


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
    "place":        {"fn": t_place,   "cat": "Place",
                     "params": {"x": 0.0, "y": 0.0, "z": 0.0, "view": True, "surface": True,
                                "anchor": "base", "sink": 0.0, "align": False, "physics": False,
                                "yaw": 0.0, "scale": 1.0},
                     "opciones": {"anchor": list(_ANCLAS)},
                     "doc": "coloca un ladrillo donde mirás: raycast a superficie, align a la normal, física, rot/escala; verifica entorno"},
    "scatter":      {"fn": t_scatter, "cat": "Scatter",
                     "params": {"count": 24, "area": 800.0, "pattern": "poisson", "spacing": 0.0,
                                "rings": 3, "surface": True, "align": False, "slope_max": 90.0,
                                "height_min": 0.0, "height_max": 0.0, "noise": 0.0, "density": 1.0,
                                "scale_min": 1.0, "scale_max": 1.0, "spread": 1.0, "sink": 0.0,
                                "anchor": "", "view": True, "seed": 7},
                     "opciones": {"pattern": ["poisson", "grid", "radial"],
                                  "anchor": [""] + list(_ANCLAS)},
                     "doc": "esparce sobre la superficie real con máscaras (pendiente/altura/ruido/densidad) y variación"},
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
    "gizmo":        {"fn": t_gizmo,   "cat": "Edit",    "params": {"on": True},
                     "doc": "marca en el viewport dónde está parado Jam + la huella del asset activo"},
    "ghost":        {"fn": t_ghost,   "cat": "Edit",    "params": {"on": True},
                     "doc": "muestra la malla que se va a colocar siguiendo el punto de mira"},
}

# Verbos que NO crean nada COLOCABLE: son selección o estado de la herramienta, así que no pasan por
# el preview (si pasaran, «Confirmar/Descartar» quedarían apuntando a una preview vacía). El
# fantasma sí crea un actor, pero es un ayudante efímero, no una pieza del nivel.
SIN_SPAWN = {"asset", "pick", "gizmo", "ghost", "pivot", "pivot_set", "normalize"}

# Orden de las categorías en la barra (como Dash). Las vacías no se muestran.
CATEGORIAS = ["Content", "Place", "Scatter", "Create", "Edit"]


def spec_json() -> str:
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
        opciones = info.get("opciones", {})
        salida.append({
            "verbo": nombre,
            "cat": info.get("cat", "Place"),
            "doc": info["doc"],
            # `opciones` → la UI dibuja una LISTA en vez de un campo de texto (anclas, modos…)
            "params": [{"nombre": k, "default": str(v), "tipo": tipo(v),
                        "opciones": opciones.get(k, [])}
                       for k, v in info["params"].items()],
        })
    return json.dumps({"categorias": CATEGORIAS, "tools": salida}, ensure_ascii=True)
