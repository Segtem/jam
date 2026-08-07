"""Verifica el ciclo entero de una herramienta: publicar → exportar → borrar → importar.

Es el ciclo que hace que Jam Graph sea un taller y la Dash un estante: se construye, se publica,
se pasa el archivo, y del otro lado aparece. Cada paso se comprueba mirando lo que ve la DASH
(`api.spec()`), no el estado interno — si la herramienta no llega ahí, no sirve de nada.

Deja el proyecto como lo encontró. El veredicto queda en `BotOO.log` con el prefijo
`JAM_PUBLICAR_58`.
"""
from __future__ import annotations

import json
import os
import tempfile

import unreal

from jam import api


def exigir(condicion: bool, mensaje: str) -> None:
    if not condicion:
        raise RuntimeError(mensaje)


def en_la_dash(verbo: str) -> bool:
    return any(t["verbo"] == verbo for t in json.loads(api.spec())["tools"])


ID, archivo = "", ""
try:
    creado = json.loads(api.function_manage("create", "", "HerramientaDePrueba"))
    exigir(creado.get("ok"), f"no pude crear: {creado}")
    verbo = creado["tool"]["verbo"]
    ID = verbo.split(":", 1)[1]

    cuerpo = {"nodes": {
        "k": {"verb": "input", "params": {"name": "cantidad", "type": "N", "default": "24"},
              "x": 0, "y": 0},
        "s": {"verb": "scatter", "params": {}, "x": 200, "y": 0},
        "o": {"verb": "output", "params": {"name": "pts", "type": "P"}, "x": 400, "y": 0}},
        "edges": [["k", "out", "s", "count"], ["s", "out", "o", "in"]]}
    exigir(json.loads(api.function_manage("update", ID, json.dumps(cuerpo)))["ok"], "no guardó")

    # 1. Nace PUBLICADA: construir la biblioteca puebla la Dash sola.
    exigir(en_la_dash(verbo), "una función nueva tendría que aparecer en la Dash")

    # 2. Despublicar la saca; publicar la devuelve. El cuerpo no se toca.
    exigir(json.loads(api.function_manage("publish", ID, "false"))["ok"], "no despublicó")
    exigir(not en_la_dash(verbo), "despublicada NO tendría que estar en la Dash")
    exigir(json.loads(api.function_manage("publish", ID, "true"))["ok"], "no publicó")
    exigir(en_la_dash(verbo), "publicada tendría que volver a la Dash")

    # 3. Exportar a un archivo portable.
    archivo = os.path.join(tempfile.gettempdir(), "prueba.jamtool")
    exp = json.loads(api.tool_export(ID, archivo))
    exigir(exp.get("ok"), f"no exportó: {exp}")
    exigir(os.path.getsize(archivo) > 0, "el .jamtool salió vacío")

    # 4. Borrarla del proyecto: se va de la Dash.
    exigir(json.loads(api.function_manage("delete", ID))["ok"], "no borró")
    exigir(not en_la_dash(verbo), "borrada no puede seguir en la Dash")

    # 5. Importar el archivo la devuelve, con su identidad y sus perillas.
    imp = json.loads(api.tool_import(archivo))
    exigir(imp.get("ok"), f"no importó: {imp}")
    exigir(imp["verbo"] == verbo, f"la identidad cambió al importar: {imp['verbo']} != {verbo}")
    ficha = next((t for t in json.loads(api.spec())["tools"] if t["verbo"] == verbo), None)
    exigir(ficha is not None, "la importada no llegó a la Dash")
    exigir([p["nombre"] for p in ficha["params"]] == ["cantidad"],
           f"las perillas no sobrevivieron el viaje: {ficha['params']}")

    # 6. Basura no puede reventar: lo llama la UI con lo que el usuario elija.
    exigir(not json.loads(api.tool_import(__file__)).get("ok"),
           "un archivo que no es una herramienta tendría que dar error, no explotar")

    unreal.log(
        "JAM_PUBLICAR_58 TODO VERDE — nace_publicada · despublicar_la_saca · publicar_la_devuelve "
        f"· exportó({os.path.getsize(archivo)} bytes) · borrar_la_saca · importó con identidad "
        f"y perillas={[p['nombre'] for p in ficha['params']]} · basura_avisa")
except Exception as exc:  # noqa: BLE001
    unreal.log_error(f"JAM_PUBLICAR_58 ROJO — {type(exc).__name__}: {exc}")
finally:
    if ID:
        try:
            api.function_manage("delete", ID)
        except Exception:  # noqa: BLE001
            pass
    if archivo and os.path.exists(archivo):
        os.remove(archivo)
    unreal.SystemLibrary.quit_editor()
