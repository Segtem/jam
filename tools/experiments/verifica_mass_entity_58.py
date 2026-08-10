"""Verifica Fase 0 y ciclo Preview de MS/MH por el camino público de UE 5.8.1."""

from __future__ import annotations

import json
from pathlib import Path

import unreal

from jam import api, graph as graph_module, mass_core, tools, ue
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


def graph_phase1() -> JamGraph:
    result = graph()
    result.nodes.pop("mass")
    result.edges = [edge for edge in result.edges if edge[2] != "mass"]
    result.add("mass_spec", {"config_path": "", "seed": 19, "budget": 128}, nid="spec")
    result.add("mass_spawn", {}, nid="spawn")
    result.add("mass_inspect", {}, nid="inspect")
    result.connect("frames", "spec")
    result.connect("spec", "spawn")
    result.connect("spawn", "inspect")
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
    tutorial_phase1 = (root / "Resources/Examples/Poblacion-MassEntity-Temporal.jamgraph").read_text(
        encoding="utf-8")
    exigir(json.loads(api.compile_graph_json(tutorial_phase1)).get("ok"),
           "tutorial MS/MH no compiló")

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

    phase1 = graph_phase1()
    compiled_phase1 = json.loads(api.compile_graph_json(phase1.to_json()))
    exigir(compiled_phase1.get("ok"), f"Compile MS/MH rojo: {compiled_phase1}")

    first = json.loads(api.run_graph_json(phase1.to_json()))
    exigir(first.get("ok") and first.get("preview"), f"primer Run MS/MH rojo: {first}")
    handle1 = tools.dato_producido_runtime("mass_inspect")
    exigir(isinstance(handle1, mass_core.MassHandle), f"no produjo MH: {handle1!r}")
    exigir(ue.mass_inspect(handle1).get("valid") == 37, "la primera población no quedó viva")

    second = json.loads(api.run_graph_json(phase1.to_json()))
    exigir(second.get("ok") and second.get("preview"), f"segundo Run MS/MH rojo: {second}")
    handle2 = tools.dato_producido_runtime("mass_inspect")
    exigir(handle2.population_id != handle1.population_id, "el segundo Run recicló identidad")
    exigir(not ue.mass_inspect(handle1).get("ok"), "reemplazar Preview no limpió la población anterior")
    exigir(ue.mass_inspect(handle2).get("valid") == 37, "la segunda población no quedó viva")

    discard = api.discard("graph")
    exigir("1 efecto(s) runtime liberado(s)" in discard, f"Discard no informó Mass: {discard}")
    exigir(not ue.mass_inspect(handle2).get("ok"), "Discard dejó viva la segunda población")

    third = json.loads(api.run_graph_json(phase1.to_json()))
    exigir(third.get("ok"), f"tercer Run MS/MH rojo: {third}")
    handle3 = tools.dato_producido_runtime("mass_inspect")
    confirm = api.confirm("graph")
    exigir("población(es) runtime quedan vivas" in confirm, f"Bake Mass ambiguo: {confirm}")
    exigir(ue.mass_inspect(handle3).get("valid") == 37, "Bake destruyó la población confirmada")
    clear = mass_core.judge_clear(handle3, ue.mass_clear(handle3))
    exigir(clear["ok"], f"Clear explícito rojo: {clear}")
    repetir = mass_core.judge_clear(handle3, ue.mass_clear(handle3))
    exigir(repetir["ok"], f"Clear no fue idempotente: {repetir}")

    fourth = json.loads(api.run_graph_json(phase1.to_json()))
    exigir(fourth.get("ok"), f"cuarto Run MS/MH rojo: {fourth}")
    handle4 = tools.dato_producido_runtime("mass_inspect")
    api.confirm("graph")
    new_world = unreal.EditorLoadingAndSavingUtils.new_blank_map(False)
    exigir(new_world is not None, "Unreal no creó el mapa vacío para probar OnWorldCleanup")
    after_map = ue.mass_inspect(handle4)
    exigir(not after_map.get("ok") and "inexistente" in str(after_map.get("error", "")),
           f"OnWorldCleanup no retiró la población del mapa anterior: {after_map}")

    unreal.log(
        "JAM_MASS_ENTITY_58 TODO VERDE — Fase 0 + MS/MH + tutorial + Compile + Run · "
        "37 entidades válidas · 1 arquetipo FTransformFragment · transforms conservados · "
        "Preview reemplaza · Discard destruye · Bake conserva · Clear idempotente · "
        "cambio de mapa limpia · 0 vivas")
except Exception as exc:  # noqa: BLE001
    unreal.log_error(f"JAM_MASS_ENTITY_58 ROJO — {type(exc).__name__}: {exc}")
finally:
    api.discard("graph")
    panel_effects = __import__("jam.panel", fromlist=["_PREVIEW_EFFECTS_BY_OWNER"])
    panel_effects._PREVIEW_EFFECTS_BY_OWNER.clear()
    tools._RUNTIME_DATA_OUTPUTS.clear()
    graph_module._ULTIMA_CORRIDA.clear()
