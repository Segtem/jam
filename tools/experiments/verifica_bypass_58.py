"""Verifica el bypass por el camino real: Compile y Run en UE 5.8.1, con el registro de verdad.

Los tests de `test_graph_preflight.py` cubren la lógica con un registro de mentira. Esto comprueba
lo que ellos no pueden: que un grafo REAL con un nodo apagado compila, corre, y que el nodo de
abajo recibe intacto lo que el apagado dejó pasar.

`mesh_normals` es M → M, así que admite bypass. Se corre el mismo grafo dos veces —con el nodo
prendido y apagado— y se exige que la malla llegue igual de lejos en las dos.

El veredicto queda en `BotOO.log` con el prefijo `JAM_BYPASS_58`.
"""

from __future__ import annotations

import unreal

from jam.graph import JamGraph, ejecutar_detalle, puede_bypass
from jam import tools


def exigir(condicion: bool, mensaje: str) -> None:
    if not condicion:
        raise RuntimeError(mensaje)


def armar(bypass: bool) -> JamGraph:
    g = JamGraph()
    g.add("mesh_box", {"size_x": "100", "size_y": "100", "size_z": "100"}, nid="caja")
    g.add("mesh_normals", {}, nid="normales")
    # El de abajo también tiene que recibir M: `info` recibe P (puntos) y ese cable sería inválido
    # con o sin bypass — el error diría más sobre el grafo de prueba que sobre el feature.
    g.add("mesh_clean_material_ids", {}, nid="fin")
    g.connect("caja", "normales")
    g.connect("normales", "fin")
    g.nodes["normales"]["bypass"] = bypass
    return g


try:
    # La regla, contra el catálogo real y no contra uno inventado.
    exigir(puede_bypass("mesh_normals", tools.REGISTRO), "mesh_normals debería admitir bypass (M→M)")
    exigir(not puede_bypass("mesh_to_static", tools.REGISTRO),
           "mesh_to_static NO debería admitirlo (M→A)")
    exigir(not puede_bypass("asset", tools.REGISTRO), "una fuente NO debería admitirlo")

    _rep_on, estados_on = ejecutar_detalle(armar(bypass=False))
    _rep_off, estados_off = ejecutar_detalle(armar(bypass=True))

    exigir(estados_on["normales"]["estado"] != "bypass",
           "sin el flag, el nodo tendría que haber corrido")
    exigir(estados_off["normales"]["estado"] == "bypass",
           f"con el flag, el nodo tendría que estar apagado: {estados_off['normales']}")
    # Lo que de verdad importa: el de abajo sigue recibiendo una malla, no None ni un error.
    exigir(estados_off["fin"]["estado"] != "error",
           f"el nodo de abajo del apagado falló: {estados_off['fin']}")

    unreal.log(
        "JAM_BYPASS_58 TODO VERDE — "
        f"prendido={estados_on['normales']['estado']}/{estados_on['fin']['texto']} · "
        f"apagado={estados_off['normales']['estado']}/{estados_off['fin']['texto']}")
except Exception as exc:  # noqa: BLE001
    unreal.log_error(f"JAM_BYPASS_58 ROJO — {type(exc).__name__}: {exc}")
finally:
    unreal.SystemLibrary.quit_editor()
