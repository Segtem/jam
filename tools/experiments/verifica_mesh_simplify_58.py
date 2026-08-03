"""Verifica los simplificadores M → M por el contrato público dentro de UE 5.8.1.

Cada caso parte de la misma esfera densa, pasa por Compile, Run e Inspector —el camino que consume
Slate— y exige que el resultado tenga menos vértices que la entrada. También comprueba los nombres
reales del enum cuyo significado cambió en 5.8. El veredicto queda en ``BotOO.log`` con el prefijo
``JAM_MESH_SIMPLIFY_58``.
"""

from __future__ import annotations

import json

import unreal

from jam import api
from jam.graph import JamGraph


def exigir(condicion: bool, mensaje: str) -> None:
    if not condicion:
        raise RuntimeError(mensaje)


def ejecutar(verbo: str, params: dict) -> tuple[int, int, str]:
    grafo = JamGraph()
    grafo.add(
        "mesh_sphere",
        {"radius": 100.0, "latitude_steps": 32, "longitude_steps": 64},
        nid="densa",
    )
    grafo.add(verbo, params, nid="reducida")
    grafo.connect("densa", "reducida")

    compilado = json.loads(api.compile_graph_json(grafo.to_json()))
    exigir(compilado.get("ok"), f"Compile rojo en {verbo}: {compilado}")

    corrida = json.loads(api.run_graph_json(grafo.to_json()))
    exigir(corrida.get("ok"), f"Run rojo en {verbo}: {corrida}")
    estados = {nid: dato.get("estado") for nid, dato in corrida.get("nodes", {}).items()}
    exigir(estados == {"densa": "ok", "reducida": "ok"},
           f"estados inesperados en {verbo}: {estados}")

    inspector = json.loads(api.inspect_json())
    exigir(inspector.get("ok"), f"Inspector rojo en {verbo}: {inspector}")
    cantidades = {nodo["id"]: int(nodo["cantidad"]) for nodo in inspector["nodos"]}
    antes, despues = cantidades["densa"], cantidades["reducida"]
    exigir(antes > 0 and 0 < despues < antes,
           f"{verbo} no redujo vértices: {antes} → {despues}")

    # Los tres grafos son puramente transitorios, pero hoy el runner histórico abre una transacción
    # Preview para cualquier verbo Mesh. Descartarla mantiene limpia la sesión de certificación.
    api.discard("graph")
    return antes, despues, corrida["nodes"]["reducida"]["texto"]


try:
    spec = {item["verbo"]: item for item in json.loads(api.spec_all())["tools"]}
    for verbo, label in (
        ("mesh_simplify_count", "Simplificar por triángulos"),
        ("mesh_simplify_tolerance", "Simplificar por tolerancia"),
        ("mesh_simplify_edge_length", "Simplificar por arista"),
    ):
        exigir(verbo in spec, f"el spec no publicó {verbo}")
        exigir(spec[verbo]["label"] == label, f"label inesperado: {spec[verbo]}")
        exigir(spec[verbo]["in_name"] == "M" and spec[verbo]["out_name"] == "M",
               f"firma inesperada: {spec[verbo]}")
        exigir(spec[verbo]["grupo"] == "Optimizar", f"grupo inesperado: {spec[verbo]}")

    enum = unreal.GeometryScriptRemoveMeshSimplificationType
    for member in ("STANDARD_QEM", "VOLUME_PRESERVING", "ATTRIBUTE_AWARE",
                   "ATTRIBUTE_AWARE_V2"):
        exigir(hasattr(enum, member), f"UE 5.8.1 no expuso {member}")
    simplifier = unreal.GeometryScript_MeshSimplification
    for method in ("apply_simplify_to_triangle_count", "apply_simplify_to_tolerance",
                   "apply_simplify_to_edge_length"):
        exigir(hasattr(simplifier, method), f"UE 5.8.1 no expuso {method}")

    resultados = {
        "count": ejecutar("mesh_simplify_count", {"target_triangles": 400}),
        "tolerance": ejecutar("mesh_simplify_tolerance", {"tolerance_cm": 5.0}),
        "edge": ejecutar("mesh_simplify_edge_length", {"edge_length_cm": 20.0}),
    }
    resumen = " · ".join(
        f"{nombre} {antes}→{despues} vértices"
        for nombre, (antes, despues, _texto) in resultados.items()
    )
    unreal.log(
        "JAM_MESH_SIMPLIFY_58 TODO VERDE — "
        f"spec + Compile + Run + Inspector + enums/métodos reales · {resumen}")
except Exception as exc:  # noqa: BLE001
    unreal.log_error(f"JAM_MESH_SIMPLIFY_58 ROJO — {type(exc).__name__}: {exc}")
finally:
    unreal.SystemLibrary.quit_editor()
