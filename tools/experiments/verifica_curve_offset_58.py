"""Verifica curve_offset por Compile/Run públicos dentro de UE 5.8.1.

El marcador ``JAM_CURVE_OFFSET_58`` queda en ``BotOO.log``. El error lateral se mide contra las dos
rectas incidentes de cada esquina; comparar sólo punto contra punto confundiría un miter válido con
una distancia excesiva.
"""

from __future__ import annotations

import json
import math
import os

import unreal

from jam import api, curve, tools
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
    result.add("mesh_pipe", {
        "radius_start": 22.0, "radius_end": 22.0, "sides": 10, "samples": 32,
        "capped": True, "profile_rotation": 0.0, "miter_limit": 2.5,
        "radius_from_parent": 0.0, "pivot_uvs": False,
    }, nid="pipe")
    result.connect("axis", "resample")
    result.connect("resample", "offset")
    result.connect("offset", "pipe")
    return result


try:
    spec = {item["verbo"]: item for item in json.loads(api.spec_all())["tools"]}
    offset_spec = spec.get("curve_offset")
    exigir(offset_spec is not None, "curve_offset no está en el spec")
    exigir(offset_spec["in_name"] == "S" and offset_spec["out_name"] == "S",
           f"curve_offset mal tipado: {offset_spec}")
    exigir(offset_spec["grupo"] == "Curvas", f"grupo inesperado: {offset_spec}")

    root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    example_path = os.path.join(root, "Resources", "Examples", "Borde-de-camino.jamgraph")
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

    source = tools.dato_producido_runtime("curve_resample")
    displaced = tools.dato_producido_runtime("curve_offset")
    dynamic = tools.dato_producido_runtime("mesh_pipe")
    exigir(isinstance(source, curve.CurvePath) and isinstance(displaced, curve.CurvePath),
           "Resample/Offset no publicaron CurvePath")
    exigir(len(source.points) == len(displaced.points) == 25,
           f"cardinalidad inesperada: {len(source.points)}→{len(displaced.points)}")

    signed_distances = []
    for index, (point, shifted) in enumerate(zip(source.points, displaced.points)):
        displacement = (shifted[0] - point[0], shifted[1] - point[1])
        adjacent = []
        if index > 0:
            adjacent.append((source.points[index - 1], point))
        if index < len(source.points) - 1:
            adjacent.append((point, source.points[index + 1]))
        for start, end in adjacent:
            dx, dy = end[0] - start[0], end[1] - start[1]
            length = math.hypot(dx, dy)
            signed_distances.append((dx * displacement[1] - dy * displacement[0]) / length)
    max_error = max(abs(value - 180.0) for value in signed_distances)
    exigir(max_error < 0.01, f"distancia/lado de Offset incorrectos: error {max_error:.4f} cm")

    queries = unreal.GeometryScript_MeshQueries
    vertices = int(queries.get_vertex_count(dynamic))
    triangles = int(queries.get_num_triangle_i_ds(dynamic))
    closed = bool(queries.get_is_closed_mesh(dynamic))
    components = int(queries.get_num_connected_components(dynamic))
    exigir(vertices > 0 and triangles > 0 and closed and components == 1,
           f"cordón inválido: {vertices=} {triangles=} {closed=} {components=}")

    unreal.log(
        "JAM_CURVE_OFFSET_58 TODO VERDE — spec + tutorial + Compile + Run · "
        f"25→25 puntos · izquierda 180 cm (error máx. {max_error:.4f}) · "
        f"{triangles} tris/{vertices} verts · cerrada · 1 pieza")
except Exception as exc:  # noqa: BLE001
    unreal.log_error(f"JAM_CURVE_OFFSET_58 ROJO — {type(exc).__name__}: {exc}")
finally:
    api.discard("graph")
    unreal.SystemLibrary.quit_editor()
