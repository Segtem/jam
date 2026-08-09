"""Verifica Range y Remap N[] por el camino público de Graph dentro de UE 5.8.1.

El marcador ``JAM_SERIES_FLOW_58`` queda en ``BotOO.log``.
"""

from __future__ import annotations

import json
import os

import unreal

from jam import api, fields, tools
from jam.graph import JamGraph


def exigir(condicion: bool, mensaje: str) -> None:
    if not condicion:
        raise RuntimeError(mensaje)


try:
    spec = {item["verbo"]: item for item in json.loads(api.spec_all())["tools"]}
    rango, remap = spec.get("series_range"), spec.get("series_remap")
    exigir(rango is not None and remap is not None, "faltan Range/Remap en el spec")
    exigir(rango["source"] and rango["out_name"] == "N[]", f"Range mal tipado: {rango}")
    exigir(not remap["source"] and remap["in_name"] == "N[]"
           and remap["out_name"] == "N[]", f"Remap mal tipado: {remap}")
    exigir(rango["grupo"] == remap["grupo"] == "Series", "layout de Series inesperado")

    g = JamGraph()
    g.add("series_range", {"start": -1.0, "end": 1.0, "count": 5}, nid="rango")
    g.add("series_remap", {"source_min": -1.0, "source_max": 1.0,
                           "target_min": 0.0, "target_max": 10.0,
                           "clamp": True}, nid="remap")
    g.add("debug", {}, nid="ver")
    g.connect("rango", "remap")
    g.connect("remap", "ver")

    compilado = json.loads(api.compile_graph_json(g.to_json()))
    exigir(compilado.get("ok"), f"Compile rojo: {compilado}")
    corrida = json.loads(api.run_graph_json(g.to_json()))
    exigir(corrida.get("ok"), f"Run rojo: {corrida}")
    estados = {nid: dato["estado"] for nid, dato in corrida["nodes"].items()}
    exigir(estados == {"rango": "ok", "remap": "ok", "ver": "ok"},
           f"estados inesperados: {estados}")
    salida = tools.dato_producido_runtime("series_remap")
    exigir(isinstance(salida, fields.ScalarSeries), f"salida no es N[]: {salida!r}")
    exigir(salida.values == (0.0, 2.5, 5.0, 7.5, 10.0),
           f"valores inesperados: {salida.values}")

    raiz = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    ruta = os.path.join(raiz, "Resources", "Examples", "Series-Range-Remap.jamgraph")
    with open(ruta, encoding="utf-8") as archivo:
        tutorial = json.loads(api.compile_graph_json(archivo.read()))
    exigir(tutorial.get("ok"), f"tutorial rojo: {tutorial}")

    unreal.log(
        "JAM_SERIES_FLOW_58 TODO VERDE — spec + Compile + Run + tutorial · "
        "N[] (-1..1) → (0, 2.5, 5, 7.5, 10) · Debug M")
except Exception as exc:  # noqa: BLE001
    unreal.log_error(f"JAM_SERIES_FLOW_58 ROJO — {type(exc).__name__}: {exc}")
finally:
    api.discard("graph")
    unreal.SystemLibrary.quit_editor()
