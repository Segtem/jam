"""Adaptador Jam ↔ Unreal — la ÚNICA capa que toca `unreal` para LEER geometría del nivel.

El cerebro (`jam.geometry` + los oráculos) razona sobre datos planos; acá los extraemos del motor.
Cuando UE cambie (UE6/Scene Graph deprecan Actors, C++→Verse), se reescribe ESTE archivo, no el
cerebro. Una `pieza` = (nombre, AABB): lo mínimo que el oráculo necesita para dictaminar.
"""

from __future__ import annotations

import unreal

from .geometry import AABB, Pieza, Vec3


def _sub():
    return unreal.get_editor_subsystem(unreal.EditorActorSubsystem)


def aabb(actor) -> AABB:
    """AABB (datos) del actor, en cm."""
    origin, extent = actor.get_actor_bounds(False)
    return AABB(Vec3(origin.x, origin.y, origin.z), Vec3(extent.x, extent.y, extent.z))


def pieza(actor) -> Pieza:
    """Pieza (dato puro) del actor: nombre + AABB + location (pivote) + yaw. Todo lo que un oráculo
    puede necesitar, extraído acá para que el cerebro no toque `unreal`."""
    loc = actor.get_actor_location()
    yaw = actor.get_actor_rotation().yaw
    return Pieza(actor.get_actor_label(), aabb(actor), Vec3(loc.x, loc.y, loc.z), yaw)


def piezas(actores) -> list:
    return [pieza(a) for a in actores]


def actores_nivel() -> list:
    return _sub().get_all_level_actors()


# ---- puentes actor → oráculo puro (para callers que tienen actores del editor) ----

def placement(actor, otros) -> dict:
    from . import oracle_placement
    otras = piezas([o for o in otros if o != actor])
    return oracle_placement.verificar(pieza(actor), otras)


def placement_texto(actor, otros) -> str:
    from . import oracle_placement
    otras = piezas([o for o in otros if o != actor])
    return oracle_placement.verificar_texto(pieza(actor), otras)


def scatter_texto(actores, centro, semi, cantidad, **kw) -> str:
    from . import oracle_scatter
    return oracle_scatter.verificar_texto(piezas(actores), centro, semi, cantidad, **kw)


def scatter(actores, centro, semi, cantidad, **kw) -> dict:
    from . import oracle_scatter
    return oracle_scatter.verificar(piezas(actores), centro, semi, cantidad, **kw)


def snap_grilla_texto(actor, grilla=100.0, **kw) -> str:
    from . import oracle_snap
    return oracle_snap.texto_grilla(pieza(actor), grilla, **kw)


def snap_grilla(actor, grilla=100.0, **kw) -> dict:
    from . import oracle_snap
    return oracle_snap.verificar_grilla(pieza(actor), grilla, **kw)


def snap_ras_texto(actor, objetivo, eje="x", **kw) -> str:
    from . import oracle_snap
    return oracle_snap.texto_ras(pieza(actor), pieza(objetivo), eje, **kw)


def physics_texto(actor, soportes=None, **kw) -> str:
    from . import oracle_physics, physics
    if soportes is None:
        soportes = physics.soportes_del_nivel()
    sp = piezas([s for s in soportes if s != actor])
    return oracle_physics.verificar_texto(pieza(actor), sp, **kw)


def physics(actor, soportes=None, **kw) -> dict:
    from . import oracle_physics, physics as _ph
    if soportes is None:
        soportes = _ph.soportes_del_nivel()
    sp = piezas([s for s in soportes if s != actor])
    return oracle_physics.verificar(pieza(actor), sp, **kw)


def reemplazo_texto(nuevo, objetivo, **kw) -> str:
    from . import oracle_reemplazo
    return oracle_reemplazo.verificar_texto(pieza(nuevo), objetivo, **kw)


def reemplazo(nuevo, objetivo, **kw) -> dict:
    from . import oracle_reemplazo
    return oracle_reemplazo.verificar(pieza(nuevo), objetivo, **kw)
