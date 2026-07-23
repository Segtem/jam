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
    return f"ASSET ACTIVO ✓ — {session.nombre()}  ({asset})"


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
    return f"ASSET ACTIVO ✓ (selección de Unreal) — {sel[0]['nombre']}{extra}"


def t_place(asset, *, x=0.0, y=0.0, z=0.0, view=True, surface=True, align=False, physics=False,
            yaw=0.0, scale=1.0) -> str:
    """Coloca un ladrillo en relación a su entorno: `view`=en el punto de mira del viewport (x/y/z
    son offset), `surface`=raycast al piso, `align`=orientar a la normal, `physics`=asentar por
    caída, `yaw`/`scale`. El oráculo del entorno verifica APOYADO sobre una superficie (gap≈0) +
    SIN CLAVARSE con los vecinos (geometría, no el soporte ni el landscape)."""
    from . import place
    actor = place.colocar(asset, (x, y, z), (0.0, 0.0, yaw), (scale, scale, scale),
                          view=view, surface=surface, align=align, physics=physics)
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

    # 2) vecinos = geometría real, sin el propio, sin el soporte, sin landscape
    def es_landscape(a):
        try:
            return isinstance(a, U.LandscapeProxy)
        except Exception:  # noqa: BLE001
            return False
    vecinos = [a for a in ue.actores_nivel()
               if a != actor and physics._es_geometria(a) and not es_landscape(a)
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
    evita el «dice confirmado pero no lo veo»: con eso lo buscás en el Outliner o volás con F."""
    loc = actor.get_actor_location()
    try:
        nivel = actor.get_level().get_outer().get_name()
    except Exception:  # noqa: BLE001
        nivel = "?"
    return (f"    en ({loc.x:.0f}, {loc.y:.0f}, {loc.z:.0f}) del nivel «{nivel}» — "
            f"seleccionado en el editor (F en el viewport para volar hasta él)")


def _grados_normal(normal) -> float:
    import math
    z = max(-1.0, min(1.0, normal.z))
    return math.degrees(math.asin(z))   # 90° = normal vertical (piso plano)


def t_scatter(asset, *, count=9, area=500.0, seed=7) -> str:
    from . import scatter, ue
    count, seed = int(count), int(seed)
    centro, semi = (0.0, 0.0), (area, area)
    actores = scatter.esparcir(asset, centro, semi, count, seed=seed)
    return ue.scatter_texto(actores, centro, semi, count)


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


def t_spline(asset, *, height=300.0, thickness=40.0, segment=200.0) -> str:
    """Scatter «a lo largo de un spline»: coloca piezas modulares sobre el spline seleccionado
    (o crea uno) orientadas a la tangente. El oráculo verifica continuidad de juntas. Una PARED de
    piedra es un PRESET de este tool (asset + height/thickness/segment)."""
    from . import oracle_pared, pared
    actor = pared.seleccionado_con_spline() or pared.crear_spline()
    build = pared.construir(actor, asset, alto=height, espesor=thickness, largo_segmento=segment)
    return oracle_pared.verificar_texto(build)


def t_create_spline(asset=None) -> str:
    """Create: agrega un spline editable a la escena (primitiva de curva, como el Create de Dash).
    Después movés sus puntos y «spline» levanta las piezas sobre él. No usa asset."""
    from . import pared
    actor = pared.crear_spline()
    etiqueta = actor.get_actor_label() if actor is not None else "spline"
    return f"SPLINE creado ✓ — «{etiqueta}»: editá sus puntos y usá «spline» para levantar piezas."


# ---- el registro: verbo → acción param-driven + defaults (fuente de verdad para DSL, help y panel) ----

# `cat` = categoría estilo Dash (Content/Place/Scatter/Create/Edit) → agrupa los verbos en la
# Dash Bar. Es dato: mover una herramienta de categoría es cambiar este campo, sin tocar C++.
REGISTRO = {
    "asset":        {"fn": t_asset,   "cat": "Content", "params": {"name": ""},
                     "doc": "elige el asset activo (Content); las demás herramientas lo heredan"},
    "pick":         {"fn": t_pick,    "cat": "Content", "params": {},
                     "doc": "usa la malla SELECCIONADA en el Content Browser de Unreal como asset activo"},
    "place":        {"fn": t_place,   "cat": "Place",
                     "params": {"x": 0.0, "y": 0.0, "z": 0.0, "view": True, "surface": True,
                                "align": False, "physics": False, "yaw": 0.0, "scale": 1.0},
                     "doc": "coloca un ladrillo donde mirás: raycast a superficie, align a la normal, física, rot/escala; verifica entorno"},
    "scatter":      {"fn": t_scatter, "cat": "Scatter", "params": {"count": 9, "area": 500.0, "seed": 7},
                     "doc": "esparce N copias en un área y verifica cobertura"},
    "drop":         {"fn": t_drop,    "cat": "Place",   "params": {"height": 800.0},
                     "doc": "deja caer el asset sobre el piso real y verifica apoyo"},
    "snap":         {"fn": t_snap,    "cat": "Place",   "params": {"grid": 100.0},
                     "doc": "snap a grilla y verifica alineación"},
    "replace":      {"fn": t_replace, "cat": "Create",  "params": {"sx": 2.0, "sy": 2.0, "sz": 3.0},
                     "doc": "blockout → asset conservando footprint"},
    "spline":       {"fn": t_spline,  "cat": "Scatter", "params": {"height": 300.0, "thickness": 40.0, "segment": 200.0},
                     "doc": "coloca piezas modulares a lo largo de un spline (verifica juntas)"},
    "create_spline": {"fn": t_create_spline, "cat": "Create", "params": {},
                      "doc": "agrega un spline editable a la escena (primitiva de curva)"},
}

# Orden de las categorías en la barra (como Dash). Las vacías no se muestran.
CATEGORIAS = ["Content", "Place", "Scatter", "Create", "Edit"]


def spec_json() -> str:
    """El registro como JSON (categoría/verbo/doc/params) para que la Dash Bar en C++ se arme sola.
    Agregar una herramienta a REGISTRO la hace aparecer en su sección sin tocar C++."""
    import json
    salida = []
    for nombre, info in REGISTRO.items():
        salida.append({
            "verbo": nombre,
            "cat": info.get("cat", "Place"),
            "doc": info["doc"],
            "params": [{"nombre": k, "default": str(v)} for k, v in info["params"].items()],
        })
    return json.dumps({"categorias": CATEGORIAS, "tools": salida}, ensure_ascii=True)
