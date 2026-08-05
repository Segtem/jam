"""Verifica el contrato del visor 2D contra UE 5.8.1: lo que el panel de Slate espera recibir.

`test_preview2d.py` ya cubre el dibujo (PNG, rampa, islas de UV) con datos de mentira. Esto
comprueba lo que ellos no pueden: que `api.preview_2d` —corriendo sobre una corrida REAL— devuelve
las claves que lee `SJamGraphEditor::RefreshPreview2D`, y que el archivo que promete existe de
verdad en el disco.

También fija el caso «no hay nada que dibujar»: el panel muestra ese texto en lugar de la imagen,
así que si viniera vacío el usuario vería un cuadro en blanco sin explicación.

El veredicto queda en `BotOO.log` con el prefijo `JAM_PREVIEW_2D_58`.
"""

from __future__ import annotations

import json
import os

import unreal

from jam import api
from jam.graph import JamGraph, ejecutar_detalle


def exigir(condicion: bool, mensaje: str) -> None:
    if not condicion:
        raise RuntimeError(mensaje)


try:
    # Una malla con UVs de verdad: `mesh_box` las trae, así que el desplegado tiene qué dibujar.
    g = JamGraph()
    g.add("mesh_box", {"size_x": "100", "size_y": "100", "size_z": "100"}, nid="caja")
    _reporte, estados = ejecutar_detalle(g)
    exigir(estados["caja"]["estado"] != "error", f"no pude generar la malla: {estados['caja']}")

    res = json.loads(api.preview_2d("caja", 128, 128, 0))
    exigir(res.get("ok"), f"el visor no pudo dibujar la malla: {res}")
    for clave in ("ruta", "tipo", "detalle"):
        exigir(clave in res, f"falta la clave «{clave}» que lee el panel: {sorted(res)}")
    ruta = res["ruta"]
    exigir(os.path.isfile(ruta), f"el visor dijo que escribió «{ruta}» y el archivo no está")
    exigir(os.path.getsize(ruta) > 0, f"el PNG salió vacío: {ruta}")

    # Un nodo que no dejó datos: tiene que explicar POR QUÉ, no devolver ok con un PNG vacío.
    sin_datos = json.loads(api.preview_2d("no_existe", 128, 128, 0))
    exigir(not sin_datos.get("ok"), "un nodo inexistente no puede dar ok")
    exigir(bool(sin_datos.get("error")),
           "sin texto de error el panel mostraría un cuadro en blanco sin explicación")

    # Miniaturas de TODOS los nodos en un viaje (lo que alimenta el canvas estilo Substance).
    todos = json.loads(api.preview_2d_todos(64, 0))
    exigir(todos.get("ok"), f"preview_2d_todos falló: {todos}")
    thumbs = todos.get("thumbs") or {}
    exigir("caja" in thumbs, f"la malla debería tener miniatura: {sorted(thumbs)}")
    exigir(os.path.isfile(thumbs["caja"]), f"la miniatura prometida no está: {thumbs['caja']}")
    # La miniatura NO puede pisar el PNG grande del panel: comparten carpeta y nombre de nodo, y
    # Slate cachea la textura por nombre de archivo — si fueran el mismo, una mostraría a la otra.
    exigir(thumbs["caja"] != ruta,
           f"la miniatura y el dibujo del panel escriben el MISMO archivo: {ruta}")

    # El PNG del popup a resolución grande: tercer sufijo, tercer archivo. Los tres conviven en la
    # misma carpeta y Slate cachea por nombre — si dos coincidieran, uno mostraría al otro.
    full = json.loads(api.preview_2d("caja", 256, 256, 0, sufijo="_full"))
    exigir(full.get("ok"), f"el visor grande falló: {full}")
    exigir(os.path.isfile(full["ruta"]), f"el PNG grande no está: {full['ruta']}")
    rutas = {ruta: nombre for nombre, ruta in
             (("panel", ruta), ("miniatura", thumbs["caja"]), ("popup", full["ruta"]))}
    exigir(len(rutas) == 3,
           f"dos de los tres dibujos escriben el MISMO archivo: {sorted(rutas)}")

    unreal.log(
        "JAM_PREVIEW_2D_58 TODO VERDE — "
        f"tipo={res['tipo']} · detalle={res['detalle']} · "
        f"bytes={os.path.getsize(ruta)} · miniaturas={len(thumbs)} · rutas_distintas={len(rutas)} · sin_datos=«{sin_datos['error'][:50]}»")
except Exception as exc:  # noqa: BLE001
    unreal.log_error(f"JAM_PREVIEW_2D_58 ROJO — {type(exc).__name__}: {exc}")
finally:
    unreal.SystemLibrary.quit_editor()
