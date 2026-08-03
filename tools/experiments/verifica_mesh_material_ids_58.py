"""Verifica reasignación y limpieza de Material IDs por el Graph público en UE 5.8.1.

Construye dos ramas con materiales distintos, las mergea, fusiona ID 1→0 y compacta slots. Así
prueba simultáneamente geometría, IDs y el sidecar que ``Mesh to Static`` necesita. El marcador
confiable queda en ``BotOO.log`` como ``JAM_MESH_MATERIAL_IDS_58``.
"""

from __future__ import annotations

import json

import unreal

from jam import api, graph, mesh
from jam.graph import JamGraph


def exigir(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


try:
    spec = {item["verbo"]: item for item in json.loads(api.spec_all())["tools"]}
    for verb, label in (
        ("mesh_remap_materials", "Reasignar IDs de material"),
        ("mesh_clean_material_ids", "Limpiar IDs de material"),
    ):
        exigir(verb in spec, f"el spec no publicó {verb}")
        exigir(spec[verb]["label"] == label, f"label inesperado: {spec[verb]}")
        exigir(spec[verb]["in_name"] == "M" and spec[verb]["out_name"] == "M",
               f"firma inesperada: {spec[verb]}")
        exigir(spec[verb]["grupo"] == "Materiales", f"grupo inesperado: {spec[verb]}")

    g = JamGraph()
    g.add("mesh_box", {"size_x": 100, "size_y": 100, "size_z": 100}, nid="box")
    g.add("mesh_material", {
        "material": "/Engine/EngineMaterials/DefaultMaterial.DefaultMaterial"}, nid="mat_a")
    g.add("mesh_sphere", {"radius": 60, "latitude_steps": 8, "longitude_steps": 12},
          nid="sphere")
    g.add("mesh_material", {
        "material": "/Engine/EngineDebugMaterials/VertexColorMaterial.VertexColorMaterial"},
        nid="mat_b")
    g.add("mesh_merge", {}, nid="merge")
    g.add("mesh_remap_materials", {"from_id": 1, "to_id": 0}, nid="remap")
    g.add("mesh_clean_material_ids", {"remove_duplicate_materials": True}, nid="clean")
    g.connect("box", "mat_a")
    g.connect("sphere", "mat_b")
    g.connect("mat_a", "merge")
    g.connect("mat_b", "merge")
    g.connect("merge", "remap")
    g.connect("remap", "clean")

    compiled = json.loads(api.compile_graph_json(g.to_json()))
    exigir(compiled.get("ok"), f"Compile rojo: {compiled}")
    run = json.loads(api.run_graph_json(g.to_json()))
    exigir(run.get("ok"), f"Run rojo: {run}")
    exigir(all(item.get("estado") == "ok" for item in run.get("nodes", {}).values()),
           f"nodos rojos: {run}")

    runtime = graph.ultima_corrida()
    merged, remapped, cleaned = runtime["merge"], runtime["remap"], runtime["clean"]
    exigir(set(mesh._material_ids(merged)) == {0, 1},
           f"Merge no produjo dos IDs: {set(mesh._material_ids(merged))}")
    exigir(set(mesh._material_ids(remapped)) == {0},
           f"Remap no fusionó 1→0: {set(mesh._material_ids(remapped))}")
    exigir(set(mesh._material_ids(cleaned)) == {0},
           f"Clean dejó IDs inesperados: {set(mesh._material_ids(cleaned))}")
    exigir(len(mesh._materials(merged)) == 2 and len(mesh._materials(remapped)) == 2,
           "Merge o Remap perdió los dos slots antes de compactar")
    exigir(len(mesh._materials(cleaned)) == 1,
           f"Clean no compactó slots: {len(mesh._materials(cleaned))}")
    exigir("2→1 IDs usados" in run["nodes"]["remap"]["texto"],
           f"Remap no publicó medida: {run['nodes']['remap']}")
    exigir("slots 2→1" in run["nodes"]["clean"]["texto"],
           f"Clean no publicó medida: {run['nodes']['clean']}")

    api.discard("graph")
    unreal.log(
        "JAM_MESH_MATERIAL_IDS_58 TODO VERDE — spec + Compile + Run · "
        "Merge IDs {0,1}/2 slots → Remap {0}/2 slots → Clean {0}/1 slot")
except Exception as exc:  # noqa: BLE001
    unreal.log_error(f"JAM_MESH_MATERIAL_IDS_58 ROJO — {type(exc).__name__}: {exc}")
finally:
    unreal.SystemLibrary.quit_editor()
