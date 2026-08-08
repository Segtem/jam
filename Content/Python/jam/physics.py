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


def _es_terreno(actor) -> bool:
    """¿Es un landscape? Su AABB no describe su superficie, así que sólo el rayo sabe su altura."""
    try:
        return isinstance(actor, unreal.LandscapeProxy)
    except Exception:  # noqa: BLE001
        return False


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
    """Asienta una TANDA de actores: cada uno cae sobre el suelo real **y sobre sus hermanos**.

    No es `soltar` en un bucle, por dos razones. Una es correcta: en un bucle cada actor caería
    contra la foto original del nivel y los N terminarían atravesados en el mismo pozo, en vez de
    apilarse — que es justo lo que uno espera al pintar. La otra es de costo: `soltar` sin
    `soportes` recorre TODOS los actores del nivel, así que llamarlo N veces escanea el nivel N
    veces.

    El SUELO se mide con un raycast por pieza y no con el AABB del nivel. Un AABB no puede describir
    un terreno: medido contra un landscape de 121 m, su caja dice `top = 3 m` y las piezas quedaban
    todas a la altura de la loma más alta, flotando. El rayo pega en la superficie real bajo cada
    una — es la misma primitiva que usa el `scatter` para muestrear el terreno.

    El orden y la matemática viven en `physics_core`, puro y testeable sin motor; acá sólo se
    traduce actor ↔ pieza, se tiran los rayos y se mueven las cosas.
    """
    from . import physics_core

    if not actores:
        return []

    # Rayo vertical bajo cada pieza, ignorando la propia tanda: si no, una pieza se apoyaría en sí
    # misma y el resultado dependería de en qué orden se tiraron los rayos.
    suelos = []
    for a in actores:
        loc = a.get_actor_location()
        golpe = ue.raycast(loc.x, loc.y, ignorar=list(actores))
        suelos.append((golpe["punto"].z, golpe["actor"] or "el suelo") if golpe["hit"] else None)

    # Los dos caminos se COMPLEMENTAN, y hace falta que sea así:
    #
    # * el AABB de una caja es una aproximación razonable de su tapa, y además funciona cuando el
    #   rayo no puede tirarse (en commandlet `line_trace_single` no pega en nada);
    # * el AABB de un LANDSCAPE es mentira: su caja llega hasta la loma más alta de todo el mapa, y
    #   usarla dejaba cada pieza flotando sobre el terreno real. Del terreno habla el rayo.
    #
    # Así que se descartan los landscapes de la lista por caja y se gana la más alta de las dos.
    if soportes is None:
        # Lo que Jam puso y todavía NO está confirmado —el Preview anterior, fantasmas, gizmos— NO
        # es piso. El Preview es transaccional: el anterior sigue vivo hasta que el nuevo termina
        # bien, así que en este instante está ahí, y una pieza que se apoye en él queda FLOTANDO
        # cuando lo reemplazan. Se vio: un barril en el aire con su sombra abajo.
        #
        # `ue.raycast` ya excluía esto (`ignorar_jam`); faltaba aplicar la MISMA regla a la lista
        # por caja. Excluirla de un camino y no del otro es peor que no excluirla: el resultado
        # depende de cuál de los dos ganó.
        propios = set(actores) | set(ue.actores_de_jam())
        soportes = [a for a in soportes_del_nivel() if a not in propios]
    piezas_soporte = ue.piezas([a for a in soportes if not _es_terreno(a)])

    resultados = physics_core.asentar_tanda(
        ue.piezas(actores), piezas_soporte, suelos=suelos, tol=tol)
    for actor, r in zip(actores, resultados):
        if r["apoyada"] and r["caida"]:
            loc = actor.get_actor_location()
            actor.set_actor_location(unreal.Vector(loc.x, loc.y, loc.z - r["caida"]), False, True)
    return resultados
