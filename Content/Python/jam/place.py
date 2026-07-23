"""Colocar — el "place" de Dash, grado producción.

Spawnea un StaticMesh con control real de su relación con el entorno:
  · superficie: raycast vertical → lo apoya sobre la geometría real bajo (x,y).
  · base:       corre el actor para que su BASE (no el pivote) toque esa superficie (a prueba de
                pivotes descentrados de KitBash3D).
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


def _actor_sub() -> unreal.EditorActorSubsystem:
    return unreal.get_editor_subsystem(unreal.EditorActorSubsystem)


def colocar(
    asset: str | unreal.StaticMesh,
    location=(0.0, 0.0, 0.0),
    rotation=(0.0, 0.0, 0.0),
    scale=(1.0, 1.0, 1.0),
    *,
    surface: bool = False,
    base: bool | None = None,
    align: bool = False,
    physics: bool = False,
    jitter_yaw: float = 0.0,
    seed: int | None = None,
) -> unreal.Actor | None:
    """Coloca `asset` (ObjectPath o StaticMesh). `location` (cm), `rotation` (roll,pitch,yaw grados),
    `scale`. Con `surface` raycastea en (x,y) y apoya ahí; `base` corre para que la base toque el
    piso (default = `surface`); `align` orienta a la normal; `physics` asienta por caída. Devuelve el
    actor o None. Además deja `actor.jam_surface` = dict del raycast (para el oráculo del tool)."""
    mesh = library.cargar_malla(asset) if isinstance(asset, str) else asset
    if mesh is None:
        unreal.log_error(f"[Jam] colocar: no se pudo cargar el asset {asset!r}")
        return None

    rng = random.Random(seed)
    x, y, z = location
    roll, pitch, yaw = rotation
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
        return None
    if tuple(scale) != (1.0, 1.0, 1.0):
        actor.set_actor_scale3d(unreal.Vector(*scale))

    # base sobre la superficie/z objetivo (mide el AABB REAL ya rotado+escalado → a prueba de pivote)
    if base:
        o, e = actor.get_actor_bounds(False)
        dz = z - (o.z - e.z)
        loc = actor.get_actor_location()
        actor.set_actor_location(unreal.Vector(loc.x, loc.y, loc.z + dz), False, False)

    if physics:
        from . import physics as ph
        ph.soltar(actor)

    actor.set_actor_label(f"Jam_{mesh.get_name()}")
    return actor
