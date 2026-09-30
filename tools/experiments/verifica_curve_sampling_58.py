"""Verifica preparación de paths y Polyline → Smooth → Resample → Pipe en UE 5.8.1.

El marcador ``JAM_CURVE_SAMPLING_58`` queda en ``BotOO.log``. Mide además que el barrido resuelva
el problema explícito de Cylinder Strip: una única pieza cerrada, no cilindros separados por tramo.
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


def separaciones(points) -> tuple[float, float, float]:
    distances = [math.dist(a, b) for a, b in zip(points, points[1:])]
    return min(distances), max(distances), max(distances) / min(distances)


def rugosidad(points) -> float:
    return sum(math.dist(
        points[index],
        tuple((points[index - 1][axis] + points[index + 1][axis]) * 0.5
              for axis in range(3)),
    ) for index in range(1, len(points) - 1))


def grafo() -> JamGraph:
    g = JamGraph()
    g.add("series_range", {"start": 0.0, "end": 720.0, "count": 7}, nid="x")
    g.add("graph_curve", {
        "start_value": 0.0, "end_value": 0.0, "shape": "custom", "power": 2.0,
        "midpoint": 0.48, "mid_value": 240.0, "samples": 7,
    }, nid="y")
    g.add("graph_curve", {
        "start_value": 0.0, "end_value": 180.0, "shape": "custom", "power": 2.0,
        "midpoint": 0.62, "mid_value": -80.0, "samples": 7,
    }, nid="z")
    g.add("curve_polyline", {"x": "", "y": "", "z": ""}, nid="polyline")
    g.add("curve_smooth", {
        "iterations": 3, "strength": 0.45, "preserve_ends": True, "samples": 32,
    }, nid="smooth")
    g.add("curve_resample", {"count": 31, "samples": 32}, nid="resample")
    g.add("mesh_pipe", {
        "radius_start": 26.0, "radius_end": 26.0, "sides": 12, "samples": 32,
        "capped": True, "profile_rotation": 0.0, "miter_limit": 2.5,
        "radius_from_parent": 0.0, "pivot_uvs": False,
    }, nid="pipe")
    g.connect("x", "polyline", "x")
    g.connect("y", "polyline", "y")
    g.connect("z", "polyline", "z")
    g.connect("polyline", "smooth")
    g.connect("smooth", "resample")
    g.connect("resample", "pipe")
    return g


try:
    spec = {item["verbo"]: item for item in json.loads(api.spec_all())["tools"]}
    polyline, fuse, subdivide, smooth, resample = (
        spec.get("curve_polyline"), spec.get("curve_fuse_collinear"),
        spec.get("curve_subdivide"), spec.get("curve_smooth"),
        spec.get("curve_resample"))
    exigir(all(item is not None for item in (polyline, fuse, subdivide, smooth, resample)),
           "faltan verbos de preparación de curvas en el spec")
    exigir(polyline["source"] and polyline["out_name"] == "S", f"Polyline mal tipado: {polyline}")
    exigir(resample["in_name"] == "S" and resample["out_name"] == "S",
           f"Resample mal tipado: {resample}")
    exigir(smooth["in_name"] == "S" and smooth["out_name"] == "S",
           f"Smooth mal tipado: {smooth}")
    exigir(fuse["in_name"] == "S" and fuse["out_name"] == "S",
           f"Fuse mal tipado: {fuse}")
    exigir(subdivide["in_name"] == "S" and subdivide["out_name"] == "S",
           f"Subdivide mal tipado: {subdivide}")
    # Sólo los que son PIN: `closed` (2026-08-12) es un parámetro sin cable y no cuenta acá.
    data_types = {item["nombre"]: item["data_type"] for item in polyline["params"]
                  if item["data_type"]}
    exigir(data_types == {"x": "N[]", "y": "N[]", "z": "N[]"},
           f"pines de Polyline inesperados: {data_types}")

    root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    example_path = os.path.join(root, "Resources", "Examples", "Cylinder-Strip.jamgraph")
    with open(example_path, encoding="utf-8") as file:
        tutorial = json.loads(api.compile_graph_json(file.read()))
    exigir(tutorial.get("ok"), f"tutorial rojo: {tutorial}")

    prepare_path = os.path.join(root, "Resources", "Examples", "Preparar-una-curva.jamgraph")
    with open(prepare_path, encoding="utf-8") as file:
        prepare_json = file.read()
    prepare_compile = json.loads(api.compile_graph_json(prepare_json))
    exigir(prepare_compile.get("ok"), f"Compile de Preparar una curva rojo: {prepare_compile}")
    prepare_run = json.loads(api.run_graph_json(prepare_json))
    exigir(prepare_run.get("ok"), f"Run de Preparar una curva rojo: {prepare_run}")
    prepared = [tools.dato_producido_runtime(verb) for verb in (
        "curve_polyline", "curve_fuse_collinear", "curve_subdivide",
        "curve_smooth", "curve_resample")]
    exigir(all(isinstance(item, curve.CurvePath) for item in prepared),
           "la cadena de preparación no publicó cinco CurvePath")
    prepare_counts = tuple(len(item.points) for item in prepared)
    exigir(prepare_counts == (7, 2, 5, 5, 13),
           f"conteos de preparación inesperados: {prepare_counts}")
    exigir(prepared[1].points == (prepared[0].points[0], prepared[0].points[-1]),
           "Fuse no conservó exactamente los extremos")
    exigir(all(point in prepared[2].points for point in prepared[1].points),
           "Subdivide perdió un vértice original")

    g = grafo()
    compiled = json.loads(api.compile_graph_json(g.to_json()))
    exigir(compiled.get("ok"), f"Compile rojo: {compiled}")
    run = json.loads(api.run_graph_json(g.to_json()))
    exigir(run.get("ok"), f"Run rojo: {run}")
    exigir(all(run["nodes"][nid]["estado"] == "ok" for nid in g.nodes),
           f"estados inesperados: {run}")

    original = tools.dato_producido_runtime("curve_polyline")
    smoothed = tools.dato_producido_runtime("curve_smooth")
    sampled = tools.dato_producido_runtime("curve_resample")
    dynamic = tools.dato_producido_runtime("mesh_pipe")
    exigir(all(isinstance(item, curve.CurvePath) for item in (original, smoothed, sampled)),
           "Polyline/Smooth/Resample no publicaron CurvePath")
    exigir(len(original.points) == 7 and len(sampled.points) == 31,
           f"conteos inesperados: {len(original.points)}→{len(sampled.points)}")
    exigir(sampled.points[0] == original.points[0] and sampled.points[-1] == original.points[-1],
           "Resample movió un extremo")
    exigir(smoothed.points[0] == original.points[0]
           and smoothed.points[-1] == original.points[-1], "Smooth movió un extremo preservado")
    rough_before, rough_after = rugosidad(original.points), rugosidad(smoothed.points)
    exigir(rough_after < rough_before * 0.5,
           f"Smooth no redujo bastante los quiebres: {rough_before:.2f}→{rough_after:.2f}")
    _source_min, _source_max, source_ratio = separaciones(original.points)
    spacing_min, spacing_max, spacing_ratio = separaciones(sampled.points)
    exigir(spacing_ratio < source_ratio and spacing_ratio < 1.11,
           f"Resample no uniformó el recorrido: {source_ratio:.3f}→{spacing_ratio:.3f}")

    queries = unreal.GeometryScript_MeshQueries
    vertices = int(queries.get_vertex_count(dynamic))
    triangles = int(queries.get_num_triangle_i_ds(dynamic))
    closed = bool(queries.get_is_closed_mesh(dynamic))
    components = int(queries.get_num_connected_components(dynamic))
    exigir(vertices > 0 and triangles > 0, "Pipe produjo una malla vacía")
    exigir(closed, "Cylinder Strip quedó abierto en alguna junta o tapa")
    exigir(components == 1, f"Cylinder Strip produjo {components} piezas desconectadas")

    unreal.log(
        "JAM_CURVE_SAMPLING_58 TODO VERDE — spec + tutorial + Compile + Run · "
        f"preparar 7→2→5→5→13 · 7 puntos suavizados {rough_before:.2f}→{rough_after:.2f} · "
        "7→31 muestras · "
        f"separación {spacing_min:.2f}..{spacing_max:.2f}cm "
        f"(ratio {source_ratio:.3f}→{spacing_ratio:.3f}) · "
        f"{triangles} tris/{vertices} verts · cerrada · 1 pieza")
except Exception as exc:  # noqa: BLE001
    unreal.log_error(f"JAM_CURVE_SAMPLING_58 ROJO — {type(exc).__name__}: {exc}")
finally:
    api.discard("graph")
    unreal.SystemLibrary.quit_editor()
