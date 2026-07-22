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

def t_colocar(asset, *, x=0.0, y=0.0, z=0.0) -> str:
    from . import oracle_placement, place
    actor = place.colocar(asset, (x, y, z))
    if actor is None:
        return f"no se pudo colocar {_corto(asset)}"
    return oracle_placement.verificar_texto(actor, _sub().get_all_level_actors())


def t_scatter(asset, *, cantidad=9, area=500.0, seed=7) -> str:
    from . import oracle_scatter, scatter
    cantidad, seed = int(cantidad), int(seed)
    centro, semi = (0.0, 0.0), (area, area)
    actores = scatter.esparcir(asset, centro, semi, cantidad, seed=seed)
    return oracle_scatter.verificar_texto(actores, centro, semi, cantidad)


def t_soltar(asset, *, altura=800.0) -> str:
    from . import oracle_physics, physics, place
    caja = place.colocar(asset, (0.0, 0.0, altura))  # a plomo desde `altura`
    r = physics.soltar(caja)                          # cae sobre la geometría real del nivel
    return f"cae {r['caida']}cm → " + oracle_physics.verificar_texto(caja)


def t_grilla(asset, *, grilla=100.0) -> str:
    from . import oracle_snap, place, snap
    caja = place.colocar(asset, (137.4, 62.9, 11.1), (0.0, 0.0, 37.0))
    snap.a_grilla(caja, grilla)
    return oracle_snap.texto_grilla(caja, grilla)


def t_reemplazar(asset, *, sx=2.0, sy=2.0, sz=3.0) -> str:
    from . import oracle_reemplazo, place, reemplazar
    blockout = place.colocar(asset, (0.0, 0.0, 150.0), scale=(sx, sy, sz))
    blockout.set_actor_label("Jam_blockout")
    nuevo, objetivo = reemplazar.reemplazar(blockout, asset, ajustar_escala=True)
    return oracle_reemplazo.verificar_texto(nuevo, objetivo)


def t_pared(asset, *, alto=300.0, espesor=40.0, largo_seg=200.0) -> str:
    from . import oracle_pared, pared
    actor = pared.seleccionado_con_spline() or pared.crear_spline()
    build = pared.construir(actor, asset, alto=alto, espesor=espesor, largo_segmento=largo_seg)
    return oracle_pared.verificar_texto(build)


# ---- el registro: nombre → acción param-driven + defaults (fuente de verdad para DSL, help y panel) ----

REGISTRO = {
    "colocar":    {"fn": t_colocar,    "params": {"x": 0.0, "y": 0.0, "z": 0.0},
                   "doc": "coloca el asset en (x,y,z) y verifica solape/vecino"},
    "scatter":    {"fn": t_scatter,    "params": {"cantidad": 9, "area": 500.0, "seed": 7},
                   "doc": "esparce N copias en un área y verifica cobertura"},
    "soltar":     {"fn": t_soltar,     "params": {"altura": 800.0},
                   "doc": "deja caer el asset sobre el piso real y verifica apoyo"},
    "grilla":     {"fn": t_grilla,     "params": {"grilla": 100.0},
                   "doc": "snap a grilla y verifica alineación"},
    "reemplazar": {"fn": t_reemplazar, "params": {"sx": 2.0, "sy": 2.0, "sz": 3.0},
                   "doc": "blockout → asset conservando footprint"},
    "pared":      {"fn": t_pared,      "params": {"alto": 300.0, "espesor": 40.0, "largo_seg": 200.0},
                   "doc": "pared por spline y verifica continuidad de juntas"},
}
