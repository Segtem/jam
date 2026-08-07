"""Colocar — el "place" de Dash, grado producción.

Spawnea un StaticMesh con control real de su relación con el entorno:
  · view:       lo pone DONDE MIRA EL VIEWPORT (la mira de Dash); x/y/z pasan a ser offset.
  · superficie: raycast vertical → lo apoya sobre la geometría real bajo (x,y).
  · anchor:     POR QUÉ PUNTO se coloca (base/center/corner/xmin…, ver `jam.pivot`) — a prueba de
                pivotes descentrados o fuera de la malla, como los de KitBash3D. `base` es el atajo.
  · align:      orienta el "arriba" del asset a la NORMAL de la superficie (para pendientes).
  · physics:    tras colocar, lo asienta por caída AABB sobre lo que tenga debajo (apilar).
  · rotación / escala / jitter de yaw.

La verificación (sobre superficie · sin interpenetrar · apoyado) la hacen los oráculos puros
`jam.oracle_placement` / `jam.oracle_physics`; el raycast lo provee `jam.ue`.
"""

from __future__ import annotations

import random

import unreal

from . import library
from .geometry import Vec3


def _actor_sub() -> unreal.EditorActorSubsystem:
    return unreal.get_editor_subsystem(unreal.EditorActorSubsystem)


def _config_destructible(actor) -> bool:
    """Deja un GeometryCollectionActor listo para ROMPER al impacto. Los defaults de umbral de daño
    de Chaos son enormes ({500000,50000,5000}) → sin esto el destructible no se rompe. Verificado en
    el spike del barril (jam/tools/experiments/dataflow_barrel_spike.py)."""
    comp = actor.get_component_by_class(unreal.GeometryCollectionComponent)
    if comp is None:
        return False

    def sp(prop, val):
        try:
            comp.set_editor_property(prop, val)
        except Exception:  # noqa: BLE001
            pass

    try:
        comp.set_simulate_physics(True)
    except Exception:  # noqa: BLE001
        pass
    sp("object_type", getattr(unreal.ObjectStateTypeEnum, "CHAOS_OBJECT_DYNAMIC", None))
    sp("enable_clustering", True)
    sp("max_cluster_level", 100)
    sp("max_simulated_level", 100)
    sp("damage_model",
       getattr(unreal.DamageModelTypeEnum, "CHAOS_DAMAGE_MODEL_USER_DEFINED_DAMAGE_THRESHOLD", None))
    sp("enable_damage_from_collision", True)
    sp("damage_threshold", [0.0])
    return True


def normalizar_agarre(actor, ancla: str = "base") -> bool:
    """Deja el `pivot_offset` del actor en su ancla: el gizmo del editor lo agarra POR AHÍ (y rota
    alrededor de ahí). Es lo que hace que una pieza con el pivote en una esquina se mueva bien.
    Editor-only y por actor: la malla del disco no se toca."""
    from . import pivot as pv
    from . import ue
    try:
        loc = actor.get_actor_location()
        p = pv.punto_ancla(ue.aabb(actor), ancla, Vec3(loc.x, loc.y, loc.z))
        # `pivot_offset` es en espacio LOCAL del actor (el editor lo pasa por su transform), así que
        # el punto del ancla hay que llevarlo al local — si no, falla en cuanto hay rotación o escala.
        local = unreal.MathLibrary.inverse_transform_location(
            actor.get_actor_transform(), unreal.Vector(p.x, p.y, p.z))
        actor.set_editor_property("pivot_offset", local)
        return True
    except Exception:  # noqa: BLE001
        return False


def colocar(
    asset: str | unreal.StaticMesh,
    location=(0.0, 0.0, 0.0),
    rotation=(0.0, 0.0, 0.0),
    scale=(1.0, 1.0, 1.0),
    *,
    surface: bool = False,
    base: bool | None = None,
    anchor: str = "",
    align: bool = False,
    physics: bool = False,
    view: bool = False,
    jitter_yaw: float = 0.0,
    seed: int | None = None,
) -> unreal.Actor | None:
    """Coloca `asset` (ObjectPath o StaticMesh). `location` (cm), `rotation` (roll,pitch,yaw grados),
    `scale`. Con `view` el origen es el punto de mira del viewport (y `location` es un offset); con
    `surface` raycastea en (x,y) y apoya ahí; `base` corre para que la base toque el piso
    (default = `surface`); `align` orienta a la normal; `physics` asienta por caída. Devuelve el
    actor o None."""
    mesh = library.cargar_placeable(asset) if isinstance(asset, str) else asset
    if mesh is None:
        unreal.log_error(f"[Jam] colocar: no se pudo cargar el asset {asset!r}")
        return None
    es_gc = library.es_geometry_collection(mesh)

    rng = random.Random(seed)
    x, y, z = location
    roll, pitch, yaw = rotation

    # `view`: el origen NO es el (0,0,0) del mundo sino DONDE MIRA EL VIEWPORT (la mira de Dash), y
    # location pasa a ser un offset. Sin esto, en un mundo abierto todo aterriza en el origen — a
    # kilómetros de la cámara — y parece que la herramienta "no hizo nada".
    if view:
        from . import ue
        mira = ue.punto_de_mira()
        if mira is not None:
            x += mira["punto"].x
            y += mira["punto"].y
            z += mira["punto"].z
    if jitter_yaw:
        yaw += rng.uniform(-jitter_yaw, jitter_yaw)
    if base is None:
        base = surface

    hit = None
    if surface:
        from . import ue
        hit = ue.raycast(x, y)
        if hit["hit"]:
            z = hit["punto"].z

    # rotación: alineada a la normal (+ yaw) o explícita
    if align and hit and hit["hit"]:
        n = hit["normal"]
        rot = unreal.MathLibrary.compose_rotators(
            unreal.Rotator(0.0, 0.0, yaw),
            unreal.MathLibrary.make_rot_from_z(unreal.Vector(n.x, n.y, n.z)))
    else:
        rot = unreal.Rotator(roll, pitch, yaw)

    actor = _actor_sub().spawn_actor_from_object(mesh, unreal.Vector(x, y, z), rot)
    if actor is None:
        # Callarse acá cuesta una ronda entera de diagnóstico: quien llama recibe None y no tiene
        # forma de saber si el asset no cargó o si el spawn falló. En commandlet SIEMPRE falla
        # (`SpawnActorFromObject` necesita el editor vivo), y sin este renglón parece un bug de Jam.
        unreal.log_error(
            f"[Jam] colocar: spawn_actor_from_object no devolvió actor para "
            f"{mesh.get_name()} — con el editor abierto sí coloca; en commandlet no")
        return None
    if tuple(scale) != (1.0, 1.0, 1.0):
        actor.set_actor_scale3d(unreal.Vector(*scale))

    # Geometry Collection: el `spawn_actor_from_object` ya creó un GeometryCollectionActor con su
    # rest_collection; lo dejamos DESTRUCTIBLE (los umbrales por defecto son enormes → no rompería).
    # Se coloca por ancla igual que una malla (el AABB del actor sirve), pero no se le normaliza el
    # pivote (no aplica a un GC).
    if es_gc:
        _config_destructible(actor)

    # ANCLA: por qué punto de la pieza se coloca. Se mide sobre el AABB REAL (ya rotado y escalado),
    # así que funciona con cualquier pivote — incluso los que vienen fuera de la malla. Si no se pide
    # una, se usa la que el asset tenga NORMALIZADA en el kit (default `base`).
    from . import kit, pivot as pv, ue
    explicita = bool(anchor)
    ruta = asset if isinstance(asset, str) else mesh.get_path_name()
    ancla = anchor or kit.ancla(ruta, "base" if base or base is None else "")
    if ancla and ancla != "pivot":
        loc = actor.get_actor_location()
        actual = Vec3(loc.x, loc.y, loc.z)
        objetivo = Vec3(x, y, z) if explicita or kit.normalizado(ruta) else Vec3(actual.x, actual.y, z)
        nueva = pv.location_para(ue.aabb(actor), actual, ancla, objetivo)
        actor.set_actor_location(unreal.Vector(nueva.x, nueva.y, nueva.z), False, False)

    # NORMALIZAR EL AGARRE: el gizmo del editor toma la pieza por el `pivot_offset` del actor. Sin
    # esto, un asset con el pivote abajo en una esquina (casa_kit) se agarra de la esquina y al
    # rotarlo se va de paseo en vez de girar en su lugar. No se toca la malla del disco.
    # (Un GC no tiene pivot_offset de StaticMeshComponent → se saltea.)
    if not es_gc:
        normalizar_agarre(actor, ancla or "base")

    if physics:
        from . import physics as ph
        ph.soltar(actor)

    actor.set_actor_label(f"Jam_{mesh.get_name()}")
    return actor
