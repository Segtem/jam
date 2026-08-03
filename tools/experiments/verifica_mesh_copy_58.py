"""Verifica copia Static/Skeletal A → M por el Graph público en UE 5.8.1.

No crea assets: usa un Static Mesh del motor y Quinn de BotOO. El marcador confiable queda en
``BotOO.log`` como ``JAM_MESH_COPY_58``.
"""

from __future__ import annotations

import json

import unreal

from jam import api, graph, mesh
from jam.graph import JamGraph


STATIC = "/Engine/EngineMeshes/Sphere.Sphere"
SKELETAL = "/Game/Characters/Mannequins/Meshes/SKM_Quinn_Simple.SKM_Quinn_Simple"


def exigir(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


try:
    spec = {item["verbo"]: item for item in json.loads(api.spec_all())["tools"]}
    for verb, label in (("mesh_copy_static", "Copiar Static Mesh"),
                        ("mesh_copy_skeletal", "Copiar Skeletal Mesh")):
        ficha = spec.get(verb)
        exigir(ficha is not None, f"el spec no publicó {verb}")
        exigir(ficha["label"] == label, f"label inesperado: {ficha}")
        exigir(ficha["in_name"] == "A" and ficha["out_name"] == "M",
               f"firma inesperada: {ficha}")
        exigir(ficha["grupo"] == "Hornear", f"grupo inesperado: {ficha}")

    g = JamGraph()
    g.add("mesh_copy_static", {}, asset=STATIC, nid="static")
    g.add("mesh_validate", {"require_uv": True, "require_materials": True},
          nid="static_validate")
    g.add("mesh_copy_skeletal", {}, asset=SKELETAL, nid="skeletal")
    g.connect("static", "static_validate")

    compiled = json.loads(api.compile_graph_json(g.to_json()))
    exigir(compiled.get("ok"), f"Compile rojo: {compiled}")
    run = json.loads(api.run_graph_json(g.to_json()))
    exigir(run.get("ok"), f"Run rojo: {run}")
    exigir(run["nodes"]["static"]["estado"] == "ok"
           and run["nodes"]["static_validate"]["estado"] == "ok",
           f"Static o su validación fallaron: {run}")
    exigir(run["nodes"]["skeletal"]["estado"] == "ok", f"Skeletal falló: {run}")

    runtime = graph.ultima_corrida()
    static = runtime["static"]
    skeletal = runtime["skeletal"]
    static_vertices = unreal.GeometryScript_MeshQueries.get_vertex_count(static)
    skeletal_vertices = unreal.GeometryScript_MeshQueries.get_vertex_count(skeletal)
    static_materials = len(mesh._materials(static))
    skeletal_materials = len(mesh._materials(skeletal))
    exigir(static_vertices > 0 and skeletal_vertices > 0,
           f"alguna copia quedó vacía: Static={static_vertices}, Skeletal={skeletal_vertices}")
    exigir(static_materials > 0 and skeletal_materials > 0,
           f"materiales perdidos: Static={static_materials}, Skeletal={skeletal_materials}")

    # El alias no se reimplementa: debe usar exactamente la nueva ruta Static y conservar materiales.
    legacy = mesh.from_asset(STATIC)
    exigir("error" not in legacy and len(mesh._materials(legacy["mesh"])) == static_materials,
           f"mesh_from_asset dejó de ser compatible: {legacy}")

    api.discard("graph")
    unreal.log(
        "JAM_MESH_COPY_58 TODO VERDE — spec + Compile + Run + Discard · "
        f"Static {static_vertices} verts/{static_materials} materiales · "
        f"Skeletal {skeletal_vertices} verts/{skeletal_materials} materiales · alias compatible")
except Exception as exc:  # noqa: BLE001
    unreal.log_error(f"JAM_MESH_COPY_58 ROJO — {type(exc).__name__}: {exc}")
finally:
    unreal.SystemLibrary.quit_editor()
