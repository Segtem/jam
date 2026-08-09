"""Verifica `mass_probe` por Spec → Compile → Run dentro de UE 5.8.1."""

from __future__ import annotations

import json
from pathlib import Path

import unreal

from jam import api, graph as graph_module, tools
from jam.graph import JamGraph


def exigir(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def graph() -> JamGraph:
    result = JamGraph()
    result.add("curve_bezier", {
        "start_x": -300.0, "start_y": 40.0, "start_z": 15.0,
        "end_x": 900.0, "end_y": 500.0, "end_z": 215.0,
        "bend_x": 120.0, "bend_y": -180.0, "bend_z": 80.0, "segments": 12,
    }, nid="path")
    result.add("curve_frames", {
        "count": 37, "start": 0.0, "end": 1.0,
        "radial_offset": 25.0, "turns": 1.5, "angle_offset": 17.0,
        "radius_start": 0.0, "radius_end": 0.0, "samples": 64, "seed": 19,
    }, nid="frames")
    result.add("mass_probe", {}, nid="mass")
    result.connect("path", "frames")
    result.connect("frames", "mass")
    return result


try:
    spec = {item["verbo"]: item for item in json.loads(api.spec_all())["tools"]}
    probe_spec = spec.get("mass_probe")
    exigir(probe_spec is not None, "mass_probe no está en el spec público")
    exigir((probe_spec["in_name"], probe_spec["out_name"]) == ("F", "F"),
           f"mass_probe mal tipado: {probe_spec}")
    exigir((probe_spec["seccion"], probe_spec["cat"], probe_spec["grupo"]) ==
           ("Distribución", "Mass", "Diagnóstico"),
           f"mass_probe quedó fuera de Distribución/Mass: {probe_spec}")

    root = Path(__file__).resolve().parents[2]
    tutorial = (root / "Resources/Examples/Prueba-MassEntity.jamgraph").read_text(
        encoding="utf-8")
    tutorial_compile = json.loads(api.compile_graph_json(tutorial))
    exigir(tutorial_compile.get("ok"), f"tutorial Mass rojo: {tutorial_compile}")

    diagram = graph()
    compiled = json.loads(api.compile_graph_json(diagram.to_json()))
    exigir(compiled.get("ok"), f"Compile rojo: {compiled}")
    run = json.loads(api.run_graph_json(diagram.to_json()))
    exigir(run.get("ok"), f"Run rojo: {run}")
    exigir(all(run["nodes"][nid]["estado"] == "ok" for nid in diagram.nodes),
           f"estados inesperados: {run}")
    exigir("37 entidades · 1 arquetipo · transforms conservados · limpieza completa"
           in run["nodes"]["mass"]["texto"], f"medición ausente: {run['nodes']['mass']}")

    output = tools.dato_producido_runtime("mass_probe")
    exigir(output is tools.dato_producido_runtime("curve_frames"),
           "mass_probe no dejó pasar el mismo F")
    exigir(len(output.frames) == 37, f"salida inesperada: {len(output.frames)} frames")

    unreal.log(
        "JAM_MASS_ENTITY_58 TODO VERDE — Spec + tutorial + Compile + Run · "
        "37 entidades válidas · 1 arquetipo FTransformFragment · transforms conservados · "
        "37/37 destruidas · salida F idéntica")
except Exception as exc:  # noqa: BLE001
    unreal.log_error(f"JAM_MASS_ENTITY_58 ROJO — {type(exc).__name__}: {exc}")
finally:
    api.discard("graph")
    tools._RUNTIME_DATA_OUTPUTS.clear()
    graph_module._ULTIMA_CORRIDA.clear()
