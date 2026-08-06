"""Verifica el auto-layout por el puente REAL: `jam.api.acomodar`, el mismo que llama el C++.

Los tests de `test_layout.py` cubren el algoritmo puro. Esto comprueba lo que ellos no pueden: que
la forma nueva del payload —`{"nodos": [...], "edges": [...]}`, la única que lleva las aristas—
sobrevive el viaje por `api.acomodar`, y que la forma vieja (una lista pelada) sigue funcionando
para alinear y distribuir.

Es el `.cpp` el que arma ese JSON a mano con `FString::Printf`, así que un typo ahí no lo atrapa
ningún test de Python: acá al menos se fija el contrato del lado que sí se puede correr.

El veredicto queda en `BotOO.log` con el prefijo `JAM_AUTO_LAYOUT_58`.
"""

from __future__ import annotations

import json

import unreal

from jam import api


def exigir(condicion: bool, mensaje: str) -> None:
    if not condicion:
        raise RuntimeError(mensaje)


try:
    nodos = [{"id": "a", "x": 0, "y": 0, "w": 184, "h": 40},
             {"id": "b", "x": 500, "y": 300, "w": 184, "h": 60},
             {"id": "c", "x": 10, "y": 900, "w": 184, "h": 40}]

    # Forma NUEVA (con aristas), tal como la arma el C++ para `auto`.
    payload = json.dumps({"nodos": nodos, "edges": [["a", "b"], ["b", "c"]]})
    res = json.loads(api.acomodar(payload, "auto"))
    exigir(res.get("ok"), f"auto falló: {res}")
    pos = res["pos"]
    exigir(set(pos) == {"a", "b", "c"}, f"faltan nodos en la respuesta: {sorted(pos)}")
    exigir(pos["a"][0] < pos["b"][0] < pos["c"][0],
           f"la cadena no quedó en orden de izquierda a derecha: {pos}")

    # Forma VIEJA (lista pelada): alinear y distribuir no pueden haberse roto.
    viejo = json.loads(api.acomodar(json.dumps(nodos), "izquierda"))
    exigir(viejo.get("ok"), f"alinear falló con la forma vieja: {viejo}")
    exigir(len({tuple(v)[0] for v in viejo["pos"].values()}) == 1,
           f"alinear a la izquierda no dejó una sola x: {viejo['pos']}")

    # Un grafo sin aristas no es un error: son N columnas de uno, o una sola. No debe reventar.
    suelto = json.loads(api.acomodar(json.dumps({"nodos": nodos, "edges": []}), "auto"))
    exigir(suelto.get("ok"), f"auto sin aristas falló: {suelto}")

    # `snap` viaja por el MISMO puente y con la forma vieja del payload (no necesita aristas).
    ajustado = json.loads(api.acomodar(json.dumps(nodos), "snap"))
    exigir(ajustado.get("ok"), f"snap falló: {ajustado}")
    for nid, (x, y) in ajustado["pos"].items():
        exigir(x % 24 == 0 and y % 24 == 0,
               f"«{nid}» quedó fuera de la grilla de 24: ({x}, {y})")

    unreal.log(
        "JAM_AUTO_LAYOUT_58 TODO VERDE — "
        f"auto={ {k: [round(v[0]), round(v[1])] for k, v in pos.items()} } · "
        f"forma_vieja=ok · sin_aristas=ok · snap={ {k: [int(v[0]), int(v[1])] for k, v in ajustado['pos'].items()} }")
except Exception as exc:  # noqa: BLE001
    unreal.log_error(f"JAM_AUTO_LAYOUT_58 ROJO — {type(exc).__name__}: {exc}")
finally:
    unreal.SystemLibrary.quit_editor()
