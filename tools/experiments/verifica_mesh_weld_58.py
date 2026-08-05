"""Verifica `mesh_weld` por el camino real: spec, Compile y Run en UE 5.8.1, sobre `casa_madera`.

El veredicto queda en `BotOO.log` con el prefijo `JAM_MESH_WELD_58`.
"""
from __future__ import annotations

import json

import unreal

from jam import api
from jam.graph import JamGraph

ASSET = "/Game/KitCasas/casa_madera/casa_madera.casa_madera"


def exigir(condicion: bool, mensaje: str) -> None:
    if not condicion:
        raise RuntimeError(mensaje)


try:
    g = JamGraph()
    g.add("asset", {"name": ASSET}, nid="asset")
    g.add("mesh_copy_static", {}, nid="copia")
    g.add("mesh_weld", {"tolerance_cm": 0.01}, nid="weld")
    g.connect("asset", "copia")
    g.connect("copia", "weld")

    compile_result = json.loads(api.compile_graph_json(g.to_json()))
    exigir(compile_result.get("ok"), f"Compile rojo: {compile_result}")

    corrida = json.loads(api.run_graph_json(g.to_json()))
    exigir(corrida.get("ok") is True, f"Run no fue verde: {corrida}")
    texto_weld = corrida["nodes"]["weld"]["texto"]
    exigir("triángulos" in texto_weld and "vértices" in texto_weld,
           f"weld no publicó el reporte limpio: {texto_weld}")

    unreal.log(f"JAM_MESH_WELD_58 TODO VERDE — {texto_weld}")
except Exception as exc:  # noqa: BLE001
    unreal.log_error(f"JAM_MESH_WELD_58 ROJO — {type(exc).__name__}: {exc}")
finally:
    unreal.SystemLibrary.quit_editor()
