"""Verifica Nanite Analyze/Validate por el contrato público dentro de UE 5.8.1.

Busca una malla apagada y otra con representación construida. No crea ni modifica assets: Compile y
Run pasan por la misma API que consume Slate. El veredicto queda en ``BotOO.log`` con el prefijo
``JAM_NANITE_DIAGNOSTICS_58``.
"""

from __future__ import annotations

import json

import unreal

from jam import api, nanite
from jam.graph import JamGraph


def exigir(condicion: bool, mensaje: str) -> None:
    if not condicion:
        raise RuntimeError(mensaje)


def grafo(ruta: str) -> JamGraph:
    g = JamGraph()
    g.add("asset", {"name": ruta}, nid="asset")
    g.add("nanite_analyze", {}, nid="analyze")
    g.add("nanite_validate", {}, nid="validate")
    g.connect("asset", "analyze")
    g.connect("analyze", "validate")
    return g


def muestras():
    registry = unreal.AssetRegistryHelpers.get_asset_registry()
    clase = unreal.TopLevelAssetPath("/Script/Engine", "StaticMesh")
    apagada = None
    construida = None
    for data in registry.get_assets_by_class(clase, True):
        mesh = data.get_asset()
        if mesh is None:
            continue
        lectura = nanite.analizar(mesh)
        if lectura.get("error"):
            continue
        if not lectura["enabled"] and apagada is None:
            apagada = mesh
        if lectura["enabled"] and lectura["vertices"] > 0 and lectura["triangles"] > 0:
            construida = mesh
        if apagada is not None and construida is not None:
            return apagada, construida
    raise RuntimeError(
        f"faltan muestras discriminantes: apagada={apagada is not None} construida={construida is not None}")


try:
    mesh_off, mesh_on = muestras()
    g = grafo(mesh_off.get_path_name())
    compile_result = json.loads(api.compile_graph_json(g.to_json()))
    exigir(compile_result.get("ok"), f"Compile rojo: {compile_result}")

    disabled = json.loads(api.run_graph_json(g.to_json()))
    exigir(disabled.get("ok") is False and disabled.get("preview") is False,
           f"Validate apagado no fue rojo/sin Preview: {disabled}")
    exigir(disabled.get("nodes", {}).get("analyze", {}).get("estado") == "ok",
           f"Analyze no pudo medir Nanite apagado: {disabled}")
    exigir(disabled.get("nodes", {}).get("validate", {}).get("estado") == "error",
           f"Validate aceptó Nanite apagado: {disabled}")

    enabled = json.loads(api.run_graph_json(grafo(mesh_on.get_path_name()).to_json()))
    exigir(enabled.get("ok") is True and enabled.get("preview") is False,
           f"Run habilitado no fue verde/sin Preview: {enabled}")
    exigir(enabled.get("nodes", {}).get("analyze", {}).get("estado") == "ok"
           and enabled.get("nodes", {}).get("validate", {}).get("estado") == "ok",
           f"Analyze o Validate quedó rojo: {enabled}")
    analysis_text = enabled["nodes"]["analyze"]["texto"]
    exigir("triángulos" in analysis_text and "vértices" in analysis_text,
           f"Analyze no publicó conteos: {analysis_text}")

    unreal.log(
        "JAM_NANITE_DIAGNOSTICS_58 TODO VERDE — "
        "spec + Compile + apagado rechazado + habilitado validado + Run sin Preview · "
        f"off={mesh_off.get_path_name()} on={mesh_on.get_path_name()} · {analysis_text}")
except Exception as exc:  # noqa: BLE001
    unreal.log_error(f"JAM_NANITE_DIAGNOSTICS_58 ROJO — {type(exc).__name__}: {exc}")
finally:
    unreal.SystemLibrary.quit_editor()
