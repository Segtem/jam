"""Salidas instanciadas del Graph para follaje y piezas repetidas de alta cantidad."""

from __future__ import annotations

import math

import unreal


def _actor_sub():
    return unreal.get_editor_subsystem(unreal.EditorActorSubsystem)


def _add_hism_component(actor, name: str):
    subsystem = unreal.get_engine_subsystem(unreal.SubobjectDataSubsystem)
    handles = subsystem.k2_gather_subobject_data_for_instance(actor)
    params = unreal.AddNewSubobjectParams()
    params.set_editor_property("parent_handle", handles[0])
    params.set_editor_property("new_class", unreal.HierarchicalInstancedStaticMeshComponent)
    handle, fail = subsystem.add_new_subobject(params)
    if fail and str(fail):
        raise RuntimeError(str(fail))
    subsystem.rename_subobject(handle, unreal.Text(name))
    components = actor.get_components_by_class(unreal.HierarchicalInstancedStaticMeshComponent)
    if not components:
        raise RuntimeError("Unreal no creó el componente HISM")
    return components[-1]


def from_selection(selection, *, name: str = "TreeGen_Foliage",
                   asset_offset_x: float = 0.0, asset_offset_y: float = 0.0,
                   asset_offset_z: float = 0.0, asset_pitch: float = 0.0,
                   asset_yaw: float = 0.0, asset_roll: float = 0.0,
                   asset_scale: float = 1.0, inherit_scale: bool = True) -> dict:
    """Crea un actor con un HISM por variante de ``AF`` y una instancia por frame."""
    from . import variants

    if not isinstance(selection, variants.FrameAssetSelection) or not selection.frames.frames:
        return {"error": "hism_output necesita una selección AF válida."}
    numeric = (asset_offset_x, asset_offset_y, asset_offset_z, asset_pitch,
               asset_yaw, asset_roll, asset_scale)
    try:
        numeric = tuple(float(item) for item in numeric)
    except (TypeError, ValueError):
        return {"error": "los parámetros de hism_output deben ser numéricos."}
    if not all(math.isfinite(item) for item in numeric) or float(asset_scale) <= 0.0:
        return {"error": "transform y asset_scale de hism_output deben ser finitos y positivos."}
    if len(selection.frames.frames) > 65536:
        return {"error": "hism_output no puede crear más de 65536 instancias por nodo."}

    actor = _actor_sub().spawn_actor_from_class(
        unreal.Actor, unreal.Vector(0.0, 0.0, 0.0), unreal.Rotator(0.0, 0.0, 0.0))
    if actor is None:
        return {"error": "Unreal no pudo crear el actor HISM."}
    actor.set_actor_label("Jam_HISM_" + str(name or "Instances"))

    paths = tuple(dict.fromkeys(selection.assets))
    components = {}
    try:
        for index, path in enumerate(paths):
            asset = unreal.load_asset(path)
            if asset is None:
                raise RuntimeError(f"no pude cargar el StaticMesh «{path}»")
            component = _add_hism_component(actor, f"HISM_{index}_{asset.get_name()}")
            component.set_static_mesh(asset)
            components[path] = component

        correction = unreal.Rotator(
            pitch=float(asset_pitch), yaw=float(asset_yaw), roll=float(asset_roll))
        offset = unreal.Vector(float(asset_offset_x), float(asset_offset_y), float(asset_offset_z))
        for frame, path in zip(selection.frames.frames, selection.assets):
            inherited = frame.scale if bool(inherit_scale) else 1.0
            scale = float(asset_scale) * inherited
            base_rotation = unreal.MathLibrary.make_rot_from_xz(
                unreal.Vector(*frame.tangent), unreal.Vector(*frame.outward))
            rotation = unreal.MathLibrary.compose_rotators(correction, base_rotation)
            location = unreal.Vector(
                frame.position[0] + offset.x,
                frame.position[1] + offset.y,
                frame.position[2] + offset.z,
            )
            transform = unreal.Transform(
                location=location, rotation=rotation, scale=unreal.Vector(scale, scale, scale))
            components[path].add_instance(transform, world_space=True)
    except Exception as exc:  # noqa: BLE001
        _actor_sub().destroy_actor(actor)
        return {"error": f"falló HISM: {type(exc).__name__}: {exc}"}

    return {
        "actor": actor,
        "info": (f"{len(selection.frames.frames)} instancias · {len(components)} HISM · "
                 f"{', '.join(path.rsplit('/', 1)[-1].split('.', 1)[0] for path in paths)}"),
    }
