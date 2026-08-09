"""Verifica ``mesh_ribbon`` por Compile/Run públicos dentro de UE 5.8.1."""

from __future__ import annotations

import json
import math
import gc

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
        "end_x": 900.0, "end_y": 0.0, "end_z": 80.0,
        "bend_x": 0.0, "bend_y": 320.0, "bend_z": -40.0, "segments": 12,
    }, nid="axis")
    result.add("curve_resample", {"count": 25, "samples": 32}, nid="resample")
    result.add("curve_offset", {
        "distance": 180.0, "side": "left", "plane": "xy", "join": "miter",
        "miter_limit": 2.5, "samples": 32,
    }, nid="offset")
    result.add("mesh_ribbon", {
        "width": 360.0, "plane": "xy", "join": "miter", "miter_limit": 2.5,
        "uv_scale": 200.0, "material_id": 3, "samples": 32,
    }, nid="ribbon")
    result.add("mesh_normals", {
        "angle_weighted": True, "area_weighted": True,
    }, nid="normals")
    result.connect("axis", "resample")
    result.connect("resample", "offset")
    result.connect("offset", "ribbon")
    result.connect("ribbon", "normals")
    return result


try:
    spec = {item["verbo"]: item for item in json.loads(api.spec_all())["tools"]}
    ribbon_spec = spec.get("mesh_ribbon")
    exigir(ribbon_spec is not None, "mesh_ribbon no está en el spec")
    exigir(ribbon_spec["in_name"] == "S" and ribbon_spec["out_name"] == "M",
           f"mesh_ribbon mal tipado: {ribbon_spec}")
    exigir(ribbon_spec["grupo"] == "Barrido", f"grupo inesperado: {ribbon_spec}")

    diagram = graph()
    compiled = json.loads(api.compile_graph_json(diagram.to_json()))
    exigir(compiled.get("ok"), f"Compile rojo: {compiled}")
    run = json.loads(api.run_graph_json(diagram.to_json()))
    exigir(run.get("ok"), f"Run rojo: {run}")
    exigir(all(run["nodes"][nid]["estado"] == "ok" for nid in diagram.nodes),
           f"estados inesperados: {run}")

    dynamic = tools.dato_producido_runtime("mesh_ribbon")
    queries = unreal.GeometryScript_MeshQueries
    vertices = int(queries.get_vertex_count(dynamic))
    triangles = int(queries.get_num_triangle_i_ds(dynamic))
    closed = bool(queries.get_is_closed_mesh(dynamic))
    components = int(queries.get_num_connected_components(dynamic))
    exigir(vertices == 50 and triangles == 48 and not closed and components == 1,
           f"topología inesperada: {vertices=} {triangles=} {closed=} {components=}")

    positions = mesh._posiciones(dynamic)
    widths = [math.dist(positions[index], positions[index + 1])
              for index in range(0, len(positions), 2)]
    # Los extremos están sobre un tramo y deben medir el ancho nominal. En los miter interiores la
    # distancia entre puntas crece con la bisectriz, por diseño.
    width_error = max(abs(widths[0] - 360.0), abs(widths[-1] - 360.0))
    exigir(width_error < 0.01, f"ancho de extremos incorrecto: {width_error:.4f} cm")

    returned_uv = unreal.GeometryScript_UVs.get_mesh_per_vertex_u_vs(dynamic, 0)
    uv_list = returned_uv[1] if isinstance(returned_uv, tuple) else returned_uv
    valid_uv = returned_uv[2] if isinstance(returned_uv, tuple) and len(returned_uv) > 2 else True
    converter = getattr(uv_list, "convert_uv_list_to_array", None)
    raw_uvs = converter() if converter else unreal.GeometryScript_List.convert_uv_list_to_array(uv_list)
    if isinstance(raw_uvs, tuple):
        raw_uvs = raw_uvs[-1]
    uvs = list(raw_uvs)
    exigir(bool(valid_uv) and len(uvs) == 50, f"UV0 inválido: {valid_uv=} n={len(uvs)}")
    exigir(all(abs(uvs[index].y - (index % 2)) < 1e-5 for index in range(len(uvs))),
           "V no alterna 0/1 por borde")
    u_values = [uvs[index].x for index in range(0, len(uvs), 2)]
    exigir(all(after + 1e-6 >= before for before, after in zip(u_values, u_values[1:])),
           "U longitudinal retrocede")
    exigir(u_values[-1] > 1.0, f"U longitudinal no recorrió la cinta: {u_values[-1]}")

    material_ids = mesh._material_ids(dynamic)
    exigir(len(material_ids) == 48 and set(material_ids) == {3},
           f"Material IDs inesperados: {set(material_ids)} ({len(material_ids)})")

    unreal.log(
        "JAM_MESH_RIBBON_58 TODO VERDE — spec + Compile + Run · 25 pares · "
        f"ancho 360 cm (error extremos {width_error:.4f}) · {triangles} tris/{vertices} verts · "
        f"UV0 0..{u_values[-1]:.2f} · Material ID 3 · abierta · 1 pieza")
except Exception as exc:  # noqa: BLE001
    unreal.log_error(f"JAM_MESH_RIBBON_58 ROJO — {type(exc).__name__}: {exc}")
finally:
    api.discard("graph")
    # Los wrappers temporales de listas UV de Geometry Script mantienen weakrefs de Python. Si
    # llegan vivos a ``Py_FinalizeEx`` el commandlet 5.8 puede caer después de haber dado verde.
    # La sonda no necesita conservar la última corrida: suelta explícitamente esos UObjects antes
    # de que el commandlet inicie el cierre automático.
    tools._RUNTIME_DATA_OUTPUTS.clear()
    graph_module._ULTIMA_CORRIDA.clear()
    mesh._MESH_MATERIALS.clear()
    for name in ("dynamic", "positions", "returned_uv", "uv_list", "raw_uvs", "uvs"):
        globals().pop(name, None)
    gc.collect()
