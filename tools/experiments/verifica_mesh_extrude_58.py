"""Verifica ``mesh_extrude`` por Compile/Run públicos dentro de UE 5.8.1."""

from __future__ import annotations

import gc
import json
import os

import unreal

from jam import api, graph as graph_module, mesh, tools
from jam.graph import JamGraph


def exigir(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def graph() -> JamGraph:
    result = JamGraph()
    result.add("curve_bezier", {
        "start_x": 0.0, "start_y": 0.0, "start_z": 0.0,
        "end_x": 900.0, "end_y": 0.0, "end_z": 0.0,
        "bend_x": 0.0, "bend_y": 260.0, "bend_z": 0.0, "segments": 12,
    }, nid="path")
    result.add("curve_resample", {"count": 25, "samples": 32}, nid="resample")
    result.add("mesh_ribbon", {
        "width": 30.0, "plane": "xy", "join": "miter", "miter_limit": 2.5,
        "uv_scale": 100.0, "material_id": 3, "samples": 32,
    }, nid="ribbon")
    result.add("mesh_extrude", {
        "distance": 300.0, "direction_x": 0.0, "direction_y": 0.0,
        "direction_z": 2.0, "uv_scale": 100.0,
    }, nid="extrude")
    result.connect("path", "resample")
    result.connect("resample", "ribbon")
    result.connect("ribbon", "extrude")
    return result


try:
    spec = {item["verbo"]: item for item in json.loads(api.spec_all())["tools"]}
    extrude_spec = spec.get("mesh_extrude")
    exigir(extrude_spec is not None, "mesh_extrude no está en el spec")
    exigir(extrude_spec["in_name"] == "M" and extrude_spec["out_name"] == "M",
           f"mesh_extrude mal tipado: {extrude_spec}")
    exigir(extrude_spec["grupo"] == "Modelar", f"grupo inesperado: {extrude_spec}")

    root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    example_path = os.path.join(root, "Resources", "Examples", "Muro-sobre-spline.jamgraph")
    with open(example_path, encoding="utf-8") as file:
        example_compile = json.loads(api.compile_graph_json(file.read()))
    exigir(example_compile.get("ok"), f"tutorial rojo: {example_compile}")

    diagram = graph()
    compiled = json.loads(api.compile_graph_json(diagram.to_json()))
    exigir(compiled.get("ok"), f"Compile rojo: {compiled}")
    run = json.loads(api.run_graph_json(diagram.to_json()))
    exigir(run.get("ok"), f"Run rojo: {run}")
    exigir(all(run["nodes"][nid]["estado"] == "ok" for nid in diagram.nodes),
           f"estados inesperados: {run}")

    ribbon = tools.dato_producido_runtime("mesh_ribbon")
    solid = tools.dato_producido_runtime("mesh_extrude")
    queries = unreal.GeometryScript_MeshQueries
    ribbon_vertices = int(queries.get_vertex_count(ribbon))
    ribbon_triangles = int(queries.get_num_triangle_i_ds(ribbon))
    vertices = int(queries.get_vertex_count(solid))
    triangles = int(queries.get_num_triangle_i_ds(solid))
    closed = bool(queries.get_is_closed_mesh(solid))
    components = int(queries.get_num_connected_components(solid))
    exigir((ribbon_vertices, ribbon_triangles) == (50, 48),
           f"ribbon inesperada: {ribbon_triangles} tris/{ribbon_vertices} verts")
    exigir((vertices, triangles, closed, components) == (100, 196, True, 1),
           f"sólido inesperado: {vertices=} {triangles=} {closed=} {components=}")

    bounds = queries.get_mesh_bounding_box(solid)
    height = float(bounds.max.z - bounds.min.z)
    exigir(abs(height - 300.0) < 0.01, f"altura incorrecta: {height:.4f} cm")
    uv = mesh._medir_uv(solid, 0)
    exigir(uv["valido"] and not uv["sin_uv"] and uv["area_uv"] > 0.0,
           f"UV0 incompleto: {uv}")
    material_ids = mesh._material_ids(solid)
    exigir(len(material_ids) == 196 and set(material_ids) == {3},
           f"Material IDs no se conservaron: {set(material_ids)} ({len(material_ids)})")

    unreal.log(
        "JAM_MESH_EXTRUDE_58 TODO VERDE — spec + tutorial + Compile + Run · "
        f"{ribbon_triangles}→{triangles} tris/{ribbon_vertices}→{vertices} verts · "
        f"altura {height:.2f} cm · UV0 completo · Material ID 3 · cerrada · 1 pieza")
except Exception as exc:  # noqa: BLE001
    unreal.log_error(f"JAM_MESH_EXTRUDE_58 ROJO — {type(exc).__name__}: {exc}")
finally:
    api.discard("graph")
    tools._RUNTIME_DATA_OUTPUTS.clear()
    graph_module._ULTIMA_CORRIDA.clear()
    mesh._MESH_MATERIALS.clear()
    for name in ("ribbon", "solid", "bounds"):
        globals().pop(name, None)
    gc.collect()
