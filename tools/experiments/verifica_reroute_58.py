"""Verifica el reroute por el puente REAL: `jam.api.cable_bajo_punto`, el que llama el `.cpp`.

Los tests de `test_layout.py` cubren la geometría pura. Esto comprueba lo que ellos no pueden: que
el payload que arma el C++ a mano con `FString::Printf` sobrevive el viaje, que un doble clic sobre
el fondo devuelve «nada» (y no un error, porque de eso depende que se abra el buscador), y que la
clave `reroutes` que se guarda en el `.jamgraph` no rompe la carga del grafo en Python.

El veredicto queda en `BotOO.log` con el prefijo `JAM_REROUTE_58`.
"""

from __future__ import annotations

import json

import unreal

from jam import api
from jam.graph import JamGraph, validar


def exigir(condicion: bool, mensaje: str) -> None:
    if not condicion:
        raise RuntimeError(mensaje)


try:
    # La forma exacta que arma el C++: tramos con id «arista:segmento».
    payload = json.dumps({"x": 100.0, "y": 0.0, "cables": [
        {"id": "0:0", "ax": 0.0, "ay": 0.0, "bx": 200.0, "by": 0.0}]})
    m = json.loads(api.cable_bajo_punto(payload))
    exigir(m.get("cable") == "0:0", f"no encontró el cable bajo el punto: {m}")
    exigir("x" in m and "y" in m, f"falta el punto sobre la curva: {m}")
    exigir(abs(m["y"]) < 1e-6, f"el punto tendría que caer sobre el cable: {m}")

    # Doble clic en el vacío: objeto VACÍO, no error. De esto depende que se abra el buscador.
    lejos = json.loads(api.cable_bajo_punto(json.dumps(
        {"x": 100.0, "y": 900.0, "cables": [
            {"id": "0:0", "ax": 0.0, "ay": 0.0, "bx": 200.0, "by": 0.0}]})))
    exigir(lejos == {}, f"lejos del cable tendría que devolver {{}}: {lejos}")

    # Basura no puede reventar: lo llama Slate en medio de un gesto.
    exigir(json.loads(api.cable_bajo_punto("no soy json")) == {}, "basura tendría que dar {}")

    # La clave `reroutes` es decoración: Python la ignora y el grafo compila igual.
    g = JamGraph()
    g.add("mesh_box", {}, nid="caja")
    g.add("mesh_normals", {}, nid="norm")
    g.connect("caja", "norm")
    crudo = json.loads(g.to_json())
    crudo["reroutes"] = {"0": [[120.0, -40.0]]}
    con_vias = json.dumps(crudo)
    recargado = JamGraph.from_json(con_vias)
    exigir(len(recargado.edges) == 1, f"la arista se perdió al recargar: {recargado.edges}")
    exigir(validar(recargado) == {}, f"el grafo con reroutes no compila: {validar(recargado)}")

    unreal.log(
        "JAM_REROUTE_58 TODO VERDE — "
        f"cable={m['cable']} punto=({m['x']:.1f}, {m['y']:.1f}) · "
        f"vacio_ok · basura_ok · reroutes_no_rompen_la_carga")
except Exception as exc:  # noqa: BLE001
    unreal.log_error(f"JAM_REROUTE_58 ROJO — {type(exc).__name__}: {exc}")
finally:
    unreal.SystemLibrary.quit_editor()
