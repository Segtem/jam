"""Mide repetibilidad de ``ApplyUniformRemesh`` en UE 5.8.1.

Epic marca esta API como potencialmente no determinista. La sonda no la convierte en estable aunque
dé verde: sólo registra si ocho ejecuciones idénticas de esta build producen la misma topología y
las mismas posiciones. El hash también permite comparar procesos separados en ``BotOO.log``.
"""

from __future__ import annotations

import hashlib

import unreal


def fingerprint(dynamic) -> tuple[str, int, int]:
    positions_result = unreal.GeometryScript_MeshQueries.get_all_vertex_positions(dynamic, True)
    position_list = positions_result[1] if isinstance(positions_result, tuple) else positions_result
    converted = position_list.convert_vector_list_to_array()
    positions = converted[-1] if isinstance(converted, tuple) else converted

    triangle_count = unreal.GeometryScript_MeshQueries.get_num_triangle_i_ds(dynamic)
    chunks = []
    for position in positions:
        chunks.append(f"v{position.x:.17g},{position.y:.17g},{position.z:.17g};")
    for triangle_id in range(triangle_count):
        result = unreal.GeometryScript_MeshQueries.get_triangle_indices(dynamic, triangle_id)
        triangle = result[0] if isinstance(result, tuple) else result
        valid = result[1] if isinstance(result, tuple) and len(result) > 1 else True
        if valid:
            chunks.append(f"t{triangle.x},{triangle.y},{triangle.z};")
    digest = hashlib.sha256("".join(chunks).encode("ascii")).hexdigest()
    return digest, len(positions), int(triangle_count)


def sample() -> tuple[str, int, int]:
    dynamic = unreal.DynamicMesh()
    unreal.GeometryScript_Primitives.append_sphere_lat_long(
        dynamic, unreal.GeometryScriptPrimitiveOptions(), unreal.Transform(),
        radius=100.0, steps_phi=32, steps_theta=64,
        origin=unreal.GeometryScriptPrimitiveOriginMode.CENTER)

    remesh = unreal.GeometryScriptRemeshOptions()
    remesh.set_editor_property("discard_attributes", False)
    remesh.set_editor_property("reproject_to_input_mesh", True)
    remesh.set_editor_property("remesh_iterations", 12)
    remesh.set_editor_property("auto_compact", True)
    uniform = unreal.GeometryScriptUniformRemeshOptions()
    uniform.set_editor_property(
        "target_type", unreal.GeometryScriptUniformRemeshTargetType.TRIANGLE_COUNT)
    uniform.set_editor_property("target_triangle_count", 600)
    unreal.GeometryScript_Remeshing.apply_uniform_remesh(dynamic, remesh, uniform)
    return fingerprint(dynamic)


try:
    results = [sample() for _ in range(8)]
    unique = sorted({digest for digest, _vertices, _triangles in results})
    marker = "REPETIBLE_EN_ESTA_SONDA" if len(unique) == 1 else "VARIA"
    digest, vertices, triangles = results[0]
    unreal.log(
        "JAM_REMESH_DETERMINISMO_58 "
        f"{marker} — 8 corridas · {len(unique)} hash(es) · {vertices} vértices · "
        f"{triangles} triángulos · sha256={digest}")
except Exception as exc:  # noqa: BLE001
    unreal.log_error(
        f"JAM_REMESH_DETERMINISMO_58 ROJO — {type(exc).__name__}: {exc}")
finally:
    unreal.SystemLibrary.quit_editor()
