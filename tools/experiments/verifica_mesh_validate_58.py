"""Verifica ``Validar malla`` por Compile + Run públicos dentro de UE 5.8.1.

La esfera debe satisfacer un requisito estricto de cierre; la grilla debe quedar naranja al exigirlo.
El marcador confiable queda en ``BotOO.log`` como ``JAM_MESH_VALIDATE_58``.
"""

from __future__ import annotations

import json

import unreal

from jam import api, graph
from jam.graph import JamGraph


def exigir(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def correr(source_verb: str, source_params: dict, *, closed: bool) -> tuple[dict, object, object]:
    g = JamGraph()
    g.add(source_verb, source_params, nid="source")
    g.add("mesh_validate", {
        "require_closed": closed,
        "max_components": 1,
        "require_uv": True,
        "require_materials": False,
    }, nid="validate")
    g.connect("source", "validate")

    compiled = json.loads(api.compile_graph_json(g.to_json()))
    exigir(compiled.get("ok"), f"Compile rojo para {source_verb}: {compiled}")
    run = json.loads(api.run_graph_json(g.to_json()))
    exigir(run.get("ok"), f"Run rojo para {source_verb}: {run}")
    runtime = graph.ultima_corrida()
    return run, runtime["source"], runtime["validate"]


try:
    spec = {item["verbo"]: item for item in json.loads(api.spec_all())["tools"]}
    ficha = spec.get("mesh_validate")
    exigir(ficha is not None, "el spec no publicó mesh_validate")
    exigir(ficha["label"] == "Validar malla", f"label inesperado: {ficha}")
    exigir(ficha["in_name"] == "M" and ficha["out_name"] == "M",
           f"firma inesperada: {ficha}")
    exigir(ficha["grupo"] == "Hornear", f"grupo inesperado: {ficha}")

    valid, sphere, sphere_out = correr(
        "mesh_sphere", {"radius": 80, "latitude_steps": 8, "longitude_steps": 12},
        closed=True)
    exigir(valid["nodes"]["validate"]["estado"] == "ok", f"esfera no pasó: {valid}")
    exigir("VALIDAR M ✓" in valid["nodes"]["validate"]["texto"],
           f"veredicto ausente: {valid}")
    exigir(sphere is sphere_out, "Validar malla clonó o sustituyó la entrada M")

    rejected, grid, grid_out = correr(
        "mesh_grid", {"width": 200, "height": 200, "columns": 4, "rows": 4},
        closed=True)
    exigir(rejected["nodes"]["validate"]["estado"] == "warn",
           f"la grilla abierta no quedó naranja: {rejected}")
    exigir("malla abierta" in rejected["nodes"]["validate"]["texto"],
           f"la causa no fue observable: {rejected}")
    exigir(grid is grid_out, "el caso rechazado no dejó pasar la misma M")

    api.discard("graph")
    unreal.log(
        "JAM_MESH_VALIDATE_58 TODO VERDE — spec + Compile + Run · "
        "esfera cerrada verde · grilla abierta naranja · M pasa por identidad")
except Exception as exc:  # noqa: BLE001
    unreal.log_error(f"JAM_MESH_VALIDATE_58 ROJO — {type(exc).__name__}: {exc}")
finally:
    unreal.SystemLibrary.quit_editor()
