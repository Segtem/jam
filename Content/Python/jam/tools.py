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

def t_place(asset, *, x=0.0, y=0.0, z=0.0) -> str:
    from . import place, ue
    actor = place.colocar(asset, (x, y, z))
    if actor is None:
        return f"no se pudo colocar {_corto(asset)}"
    return ue.placement_texto(actor, _sub().get_all_level_actors())


def t_scatter(asset, *, count=9, area=500.0, seed=7) -> str:
    from . import oracle_scatter, scatter
    count, seed = int(count), int(seed)
    centro, semi = (0.0, 0.0), (area, area)
    actores = scatter.esparcir(asset, centro, semi, count, seed=seed)
    return oracle_scatter.verificar_texto(actores, centro, semi, count)


def t_drop(asset, *, height=800.0) -> str:
    from . import oracle_physics, physics, place
    caja = place.colocar(asset, (0.0, 0.0, height))  # a plomo desde `height`
    r = physics.soltar(caja)                          # cae sobre la geometría real del nivel
    return f"cae {r['caida']}cm → " + oracle_physics.verificar_texto(caja)


def t_snap(asset, *, grid=100.0) -> str:
    from . import oracle_snap, place, snap
    caja = place.colocar(asset, (137.4, 62.9, 11.1), (0.0, 0.0, 37.0))
    snap.a_grilla(caja, grid)
    return oracle_snap.texto_grilla(caja, grid)


def t_replace(asset, *, sx=2.0, sy=2.0, sz=3.0) -> str:
    from . import oracle_reemplazo, place, reemplazar
    blockout = place.colocar(asset, (0.0, 0.0, 150.0), scale=(sx, sy, sz))
    blockout.set_actor_label("Jam_blockout")
    nuevo, objetivo = reemplazar.reemplazar(blockout, asset, ajustar_escala=True)
    return oracle_reemplazo.verificar_texto(nuevo, objetivo)


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
    "place":        {"fn": t_place,   "cat": "Place",   "params": {"x": 0.0, "y": 0.0, "z": 0.0},
                     "doc": "coloca el asset en (x,y,z) y verifica solape/vecino"},
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
