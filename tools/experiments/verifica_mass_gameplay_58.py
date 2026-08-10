"""Verifica la primera vertical MassGameplay por el camino público de Jam y UE 5.8.1.

Crea un ``UMassEntityConfigAsset`` temporal, le agrega el trait espacial de Jam, y ejecuta:
``mass_config (MC) -> mass_spec (MS) -> mass_spawn (MH) -> mass_inspect``.
El asset y la población se eliminan aun cuando la sonda queda roja.
"""

from __future__ import annotations

import json
from pathlib import Path
import uuid

import unreal

from jam import api, graph as graph_module, mass_core, tools, ue
from jam.graph import JamGraph


ASSET_NAME = f"MC_JamMassGameplay_{uuid.uuid4().hex[:8]}"
ASSET_PACKAGE = f"/Game/Jam/_Sonda/{ASSET_NAME}"


def exigir(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def crear_config() -> unreal.MassEntityConfigAsset:
    if unreal.EditorAssetLibrary.does_asset_exist(ASSET_PACKAGE):
        unreal.EditorAssetLibrary.delete_asset(ASSET_PACKAGE)
    factory = unreal.DataAssetFactory()
    factory.set_editor_property("data_asset_class", unreal.MassEntityConfigAsset)
    asset = unreal.AssetToolsHelpers.get_asset_tools().create_asset(
        ASSET_NAME, "/Game/Jam/_Sonda", unreal.MassEntityConfigAsset, factory)
    exigir(asset is not None, "AssetTools no creó el UMassEntityConfigAsset temporal")
    prepared = json.loads(str(unreal.JamMassLibrary.prepare_transform_config(asset)))
    exigir(prepared.get("ok"), f"no se agregó el trait espacial: {prepared}")
    exigir(unreal.EditorAssetLibrary.save_loaded_asset(asset), "no se guardó el config temporal")
    return asset


def graph(config_path: str) -> JamGraph:
    result = JamGraph()
    result.add("mass_config", {"path": config_path}, nid="config")
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
    result.add("mass_spec", {"seed": 19, "budget": 128}, nid="spec")
    result.add("mass_spawn", {}, nid="spawn")
    result.add("mass_inspect", {}, nid="inspect")
    result.connect("path", "frames")
    result.connect("frames", "spec")
    result.connect("config", "spec", destino_pin="config")
    result.connect("spec", "spawn")
    result.connect("spawn", "inspect")
    return result


try:
    config_asset = crear_config()
    config_path = config_asset.get_path_name()
    diagram = graph(config_path)

    compiled = json.loads(api.compile_graph_json(diagram.to_json()))
    exigir(compiled.get("ok"), f"Compile MC→MS→MH rojo: {compiled}")
    run = json.loads(api.run_graph_json(diagram.to_json()))
    exigir(run.get("ok") and run.get("preview"), f"Run MassGameplay rojo: {run}")
    exigir(all(run["nodes"][nid]["estado"] == "ok" for nid in diagram.nodes),
           f"estados inesperados: {run}")

    config = tools.dato_producido_runtime("mass_config")
    spec = tools.dato_producido_runtime("mass_spec")
    handle = tools.dato_producido_runtime("mass_inspect")
    exigir(isinstance(config, mass_core.MassConfig), f"mass_config no produjo MC: {config!r}")
    exigir(isinstance(spec, mass_core.MassSpec), f"mass_spec no produjo MS: {spec!r}")
    exigir(isinstance(handle, mass_core.MassHandle), f"mass_inspect no produjo MH: {handle!r}")
    exigir(config.config_path == spec.config_path == config_path,
           "MC y MS no conservaron la identidad del config asset")

    facts = ue.mass_inspect(handle)
    exigir(facts.get("ok") and facts.get("valid") == 37, f"población incompleta: {facts}")
    exigir(facts.get("config_path") == config_path, f"config no trazable: {facts}")
    exigir(facts.get("spawner_class") == "JamMassSpawner", f"spawner incorrecto: {facts}")
    exigir(facts.get("transform_mismatches") == 0, f"frames no conservados: {facts}")

    discarded = api.discard("graph")
    exigir("1 efecto(s) runtime liberado(s)" in discarded, f"Discard ambiguo: {discarded}")
    exigir(not ue.mass_inspect(handle).get("ok"), "Discard dejó viva la población configurada")

    root = Path(__file__).resolve().parents[2]
    tutorial = (root / "Resources/Examples/Poblacion-MassGameplay-Ambiental.jamgraph").read_text(
        encoding="utf-8")
    tutorial_run = json.loads(api.run_graph_json(tutorial))
    exigir(tutorial_run.get("ok"), f"el tutorial con MC_JamSpatial no corrió: {tutorial_run}")
    tutorial_handle = tools.dato_producido_runtime("mass_inspect")
    tutorial_facts = ue.mass_inspect(tutorial_handle)
    exigir(tutorial_facts.get("valid") == 37, f"tutorial portable incompleto: {tutorial_facts}")
    api.discard("graph")
    exigir(not ue.mass_inspect(tutorial_handle).get("ok"),
           "el tutorial portable dejó su población viva")

    unreal.log(
        "JAM_MASS_GAMEPLAY_58 TODO VERDE — MC→MS→MH por Graph público · "
        "UMassEntityConfigAsset + UJamMassTransformTrait · AJamMassSpawner · "
        "37 entidades · transforms conservados · tutorial portable · Discard deja 0 vivas")
except Exception as exc:  # noqa: BLE001
    unreal.log_error(f"JAM_MASS_GAMEPLAY_58 ROJO — {type(exc).__name__}: {exc}")
finally:
    api.discard("graph")
    panel_effects = __import__("jam.panel", fromlist=["_PREVIEW_EFFECTS_BY_OWNER"])
    panel_effects._PREVIEW_EFFECTS_BY_OWNER.clear()
    tools._RUNTIME_DATA_OUTPUTS.clear()
    graph_module._ULTIMA_CORRIDA.clear()
    if unreal.EditorAssetLibrary.does_asset_exist(ASSET_PACKAGE):
        unreal.EditorAssetLibrary.delete_asset(ASSET_PACKAGE)
