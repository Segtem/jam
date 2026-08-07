"""Physics — soltar assets para que se asienten sobre la geometría (el "Physics Tools" de Dash).

MVP: DROP geométrico por AABB — baja el actor hasta apoyar su caja sobre el soporte más alto que
tiene debajo (solapando en XY). Determinista y headless-safe; misma fidelidad AABB que el resto del
kit (grado blockout). El raycast a la superficie real de malla resultó frágil headless en 5.7
(HitResult sin `blocking_hit`); simulación de física real (Chaos) y drop-a-superficie por raycast
quedan como crecimientos posteriores. La verificación la hace `jam.oracle_physics`.
"""

from __future__ import annotations

import unreal

from . import geometry, oracle_placement, ue


def _actor_sub() -> unreal.EditorActorSubsystem:
    return unreal.get_editor_subsystem(unreal.EditorActorSubsystem)


def _es_geometria(actor) -> bool:
    """¿El actor es superficie sobre la que algo puede apoyarse? Malla o landscape — NO luces,
    cámaras, sky, volúmenes ni player-start (esos no tienen geometría renderizable)."""
    try:
        if isinstance(actor, unreal.LandscapeProxy):
            return True
    except Exception:
        pass
    return bool(actor.get_components_by_class(unreal.StaticMeshComponent))


def soportes_del_nivel():
    """Todos los actores del nivel que cuentan como piso/geometría (única fuente de verdad para
    `soltar` y su oráculo: ambos deben coincidir en «qué hay debajo»)."""
    return [a for a in _actor_sub().get_all_level_actors() if _es_geometria(a)]


def _soporte_top(actor, soportes, tol):
    """Top del soporte más alto debajo de `actor` (delega en el oráculo puro geometry.soporte_top)."""
    sp = ue.piezas([s for s in soportes if s != actor])
    return geometry.soporte_top(ue.aabb(actor), sp, tol)


def soltar(actor, soportes=None, *, tol=oracle_placement._TOL_CM):
    """Baja `actor` hasta apoyar su base sobre el soporte más alto debajo (AABB). `soportes` None
    = todos los actores del nivel. Devuelve {cayo, z_apoyo, soporte, caida} (caida en cm, >0 flotaba)."""
    if soportes is None:
        soportes = soportes_del_nivel()
    oa, ea = ue.aabb(actor)
    base = oa.z - ea.z
    z_top, label = _soporte_top(actor, soportes, tol)
    if z_top is None:
        return {"cayo": False, "z_apoyo": None, "soporte": None, "caida": 0.0}
    loc = actor.get_actor_location()
    caida = base - z_top
    actor.set_actor_location(unreal.Vector(loc.x, loc.y, loc.z - caida), False, True)
    return {"cayo": True, "z_apoyo": round(z_top, 1), "soporte": label, "caida": round(caida, 1)}


def asentar_actores(actores, soportes=None, *, tol=oracle_placement._TOL_CM) -> list[dict]:
    """Asienta una TANDA de actores: cada uno cae sobre lo que ya estaba **y sobre sus hermanos**.

    No es `soltar` en un bucle, por dos razones. Una es correcta: en un bucle cada actor caería
    contra la foto original del nivel y los N terminarían atravesados en el mismo pozo, en vez de
    apilarse — que es justo lo que uno espera al pintar. La otra es de costo: `soltar` sin
    `soportes` recorre TODOS los actores del nivel, así que llamarlo N veces escanea el nivel N
    veces. Acá se escanea una sola.

    El orden y la matemática viven en `physics_core`, puro y testeable sin motor; acá sólo se
    traduce actor ↔ pieza y se mueven las cosas.
    """
    from . import physics_core

    if not actores:
        return []
    if soportes is None:
        propios = set(actores)
        soportes = [a for a in soportes_del_nivel() if a not in propios]

    resultados = physics_core.asentar_tanda(ue.piezas(actores), ue.piezas(soportes), tol=tol)
    for actor, r in zip(actores, resultados):
        if r["apoyada"] and r["caida"]:
            loc = actor.get_actor_location()
            actor.set_actor_location(unreal.Vector(loc.x, loc.y, loc.z - r["caida"]), False, True)
    return resultados
