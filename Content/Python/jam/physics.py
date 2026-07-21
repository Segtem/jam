"""Physics — soltar assets para que se asienten sobre la geometría (el "Physics Tools" de Dash).

MVP: DROP geométrico por AABB — baja el actor hasta apoyar su caja sobre el soporte más alto que
tiene debajo (solapando en XY). Determinista y headless-safe; misma fidelidad AABB que el resto del
kit (grado blockout). El raycast a la superficie real de malla resultó frágil headless en 5.7
(HitResult sin `blocking_hit`); simulación de física real (Chaos) y drop-a-superficie por raycast
quedan como crecimientos posteriores. La verificación la hace `jam.oracle_physics`.
"""

from __future__ import annotations

import unreal

from . import oracle_placement


def _actor_sub() -> unreal.EditorActorSubsystem:
    return unreal.get_editor_subsystem(unreal.EditorActorSubsystem)


def _soporte_top(actor, soportes, tol):
    """Top del AABB del soporte más alto que solapa a `actor` en XY y no está por encima de su centro.
    Devuelve (z_top, label), o (None, None) si no hay nada debajo."""
    oa, ea = oracle_placement.aabb(actor)
    mejor = None
    for s in soportes:
        if s == actor:
            continue
        os_, es = oracle_placement.aabb(s)
        if abs(os_.x - oa.x) > (es.x + ea.x) or abs(os_.y - oa.y) > (es.y + ea.y):
            continue  # no solapa en XY → no es soporte
        s_top = os_.z + es.z
        if s_top > oa.z + tol:
            continue  # el soporte asoma por encima del centro → no está "debajo"
        if mejor is None or s_top > mejor[0]:
            mejor = (s_top, s.get_actor_label())
    return mejor if mejor else (None, None)


def soltar(actor, soportes=None, *, tol=oracle_placement._TOL_CM):
    """Baja `actor` hasta apoyar su base sobre el soporte más alto debajo (AABB). `soportes` None
    = todos los actores del nivel. Devuelve {cayo, z_apoyo, soporte, caida} (caida en cm, >0 flotaba)."""
    if soportes is None:
        soportes = _actor_sub().get_all_level_actors()
    oa, ea = oracle_placement.aabb(actor)
    base = oa.z - ea.z
    z_top, label = _soporte_top(actor, soportes, tol)
    if z_top is None:
        return {"cayo": False, "z_apoyo": None, "soporte": None, "caida": 0.0}
    loc = actor.get_actor_location()
    caida = base - z_top
    actor.set_actor_location(unreal.Vector(loc.x, loc.y, loc.z - caida), False, True)
    return {"cayo": True, "z_apoyo": round(z_top, 1), "soporte": label, "caida": round(caida, 1)}
