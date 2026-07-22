"""Snap / Alinear — cuadrar piezas a una grilla o encajarlas al ras (los "Pivot/Snap Tools" de Dash).

Dos operaciones deterministas para prolijar un blockout modular:
  - `a_grilla(actor, grilla)`  — cuantiza el pivote del actor a la grilla (y el yaw a un paso).
  - `al_ras(actor, objetivo, eje)` — desliza al actor sobre un eje hasta que su cara toque la de
    `objetivo` (gap 0, sin solaparse). El lado se decide por la posición relativa actual.

La verificación la hace `jam.oracle_snap` (en-grilla / al-ras dentro de tolerancia). Todo por AABB
y traslación rígida — misma fidelidad grado-blockout que el resto del kit.
"""

from __future__ import annotations

import unreal

from . import oracle_placement, ue

_EJES = {"x": 0, "y": 1, "z": 2}


def _vec_comp(v) -> list[float]:
    return [v.x, v.y, v.z]


def a_grilla(actor, grilla: float = 100.0, *, snap_yaw: bool = True, paso_yaw: float = 90.0) -> dict:
    """Cuadra el pivote del actor a múltiplos de `grilla` (cm) y el yaw a múltiplos de `paso_yaw` (°)."""
    loc = actor.get_actor_location()
    nx = round(loc.x / grilla) * grilla
    ny = round(loc.y / grilla) * grilla
    nz = round(loc.z / grilla) * grilla
    actor.set_actor_location(unreal.Vector(nx, ny, nz), False, True)
    nyaw = None
    if snap_yaw:
        rot = actor.get_actor_rotation()
        nyaw = round(rot.yaw / paso_yaw) * paso_yaw
        actor.set_actor_rotation(unreal.Rotator(rot.roll, rot.pitch, nyaw), True)
    return {"loc": (nx, ny, nz), "yaw": nyaw}


def al_ras(actor, objetivo, eje: str = "x", *, tol: float = oracle_placement._TOL_CM) -> dict:
    """Desliza `actor` sobre `eje` hasta que su cara toque la de `objetivo` (gap 0, sin solapar).
    El lado (±) se toma del signo de la posición relativa actual sobre ese eje."""
    i = _EJES[eje]
    oa, ea = ue.aabb(actor)
    ob, eb = ue.aabb(objetivo)
    ca, cb = _vec_comp(oa), _vec_comp(ob)
    eai, ebi = _vec_comp(ea)[i], _vec_comp(eb)[i]
    lado = 1.0 if ca[i] >= cb[i] else -1.0
    nuevo_ci = cb[i] + lado * (ebi + eai)   # caras tocándose
    delta = nuevo_ci - ca[i]
    comp = _vec_comp(actor.get_actor_location())
    comp[i] += delta
    actor.set_actor_location(unreal.Vector(*comp), False, True)
    return {"eje": eje, "lado": "+" if lado > 0 else "-", "delta": round(delta, 1)}
