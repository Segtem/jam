"""Colocar — spawnea un asset de la biblioteca en la escena (el "place" de Dash).

Toma un StaticMesh (por ruta o cargado) y lo instancia como StaticMeshActor en una transform.
Devuelve el actor spawneado. La verificación de que quedó bien colocado la hace
`jam.oracle_placement` (bounds válidos, sin interpenetrar) — el twist de Jam sobre Dash.
"""

from __future__ import annotations

import unreal

from . import library


def _actor_sub() -> unreal.EditorActorSubsystem:
    return unreal.get_editor_subsystem(unreal.EditorActorSubsystem)


def colocar(
    asset: str | unreal.StaticMesh,
    location=(0.0, 0.0, 0.0),
    rotation=(0.0, 0.0, 0.0),
    scale=(1.0, 1.0, 1.0),
) -> unreal.Actor | None:
    """Spawnea el StaticMesh en `location` (cm). rotation = (roll,pitch,yaw) en grados.
    `asset` puede ser una ruta ObjectPath o un StaticMesh ya cargado. None si falla."""
    mesh = library.cargar_malla(asset) if isinstance(asset, str) else asset
    if mesh is None:
        unreal.log_error(f"[Jam] colocar: no se pudo cargar el asset {asset!r}")
        return None
    loc = unreal.Vector(*location)
    rot = unreal.Rotator(*rotation)
    actor = _actor_sub().spawn_actor_from_object(mesh, loc, rot)
    if actor is None:
        return None
    if scale != (1.0, 1.0, 1.0):
        actor.set_actor_scale3d(unreal.Vector(*scale))
    actor.set_actor_label(f"Jam_{mesh.get_name()}")
    return actor
