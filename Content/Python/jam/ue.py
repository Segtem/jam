"""Adaptador Jam ↔ Unreal — la ÚNICA capa que toca `unreal` para LEER geometría del nivel.

El cerebro (`jam.geometry` + los oráculos) razona sobre datos planos; acá los extraemos del motor.
Cuando UE cambie (UE6/Scene Graph deprecan Actors, C++→Verse), se reescribe ESTE archivo, no el
cerebro. Una `pieza` = (nombre, AABB): lo mínimo que el oráculo necesita para dictaminar.
"""

from __future__ import annotations

import unreal

from .geometry import AABB, Vec3


def _sub():
    return unreal.get_editor_subsystem(unreal.EditorActorSubsystem)


def aabb(actor) -> AABB:
    """AABB (datos) del actor, en cm."""
    origin, extent = actor.get_actor_bounds(False)
    return AABB(Vec3(origin.x, origin.y, origin.z), Vec3(extent.x, extent.y, extent.z))


def pieza(actor) -> tuple[str, AABB]:
    """(nombre, AABB) — la unidad sobre la que razona el oráculo."""
    return (actor.get_actor_label(), aabb(actor))


def piezas(actores) -> list[tuple[str, AABB]]:
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
