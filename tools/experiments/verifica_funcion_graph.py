"""Verificación por el camino real de la Fase 5 del Graph.

Corre dentro de Unreal: guarda una selección como función local, la instancia dos veces y pide el
Compile público del canvas. El ``finally`` borra únicamente el preset efímero de esta corrida.
El veredicto confiable queda en ``BotOO/Saved/Logs/BotOO.log`` con el prefijo ``JAM_FUNCION_TEST``.
"""

from __future__ import annotations

import json
import time

import unreal

from jam import api, preset
from jam.graph import JamGraph


nombre = f"Verifica función {time.time_ns()}"
funcion_id = ""

try:
    plano = JamGraph()
    plano.add("mesh_cylinder", {"radius": 30.0}, nid="cil", x=0, y=20)
    plano.add("mesh_transform", {"scale_x": 2.0, "scale_y": 2.0, "scale_z": 2.0},
              nid="t1", x=200, y=20)
    plano.add("mesh_normals", {}, nid="n1", x=400, y=20)
    plano.add("mesh_to_static", {"name": "JamFuncionTest"}, nid="fin", x=800, y=20)
    plano.connect("cil", "t1")
    plano.connect("t1", "n1")
    plano.connect("n1", "fin")

    colapsado = json.loads(api.collapse_function(
        nombre, plano.to_json(), json.dumps(["t1", "n1"])))
    if not colapsado.get("ok"):
        raise RuntimeError(colapsado.get("report", "collapse_function falló sin reporte"))
    verbo = colapsado["tool"]["verbo"]
    funcion_id = verbo.removeprefix("fn:")

    padre = JamGraph.from_json(json.dumps(colapsado["graph"]))
    instancia = next(nid for nid, n in padre.nodes.items() if n["verb"] == verbo)
    # La segunda instancia se pone en serie con la primera: el Compile tiene que expandir ambas.
    padre.add(verbo, {}, nid="f2", x=600, y=20)
    padre.edges = [e for e in padre.edges if not (e[0] == instancia and e[2] == "fin")]
    padre.connect(instancia, "f2", "in", "salida")
    padre.connect("f2", "fin", "in", "salida")

    compilado = json.loads(api.compile_graph_json(padre.to_json()))
    esperados = {f"{instancia}__t1", f"{instancia}__n1", "f2__t1", "f2__n1"}
    vistos = set(compilado.get("nodes", {}))
    if not compilado.get("ok") or not esperados <= vistos:
        raise RuntimeError(
            f"Compile no probó las dos expansiones: esperados={sorted(esperados)} "
            f"vistos={sorted(vistos)} reporte={compilado.get('report')}")

    obtenido = json.loads(api.function_manage("get", verbo))
    if not obtenido.get("ok"):
        raise RuntimeError(f"ABM get falló: {obtenido}")
    nombre_nuevo = nombre + " renombrada"
    renombrado = json.loads(api.function_manage("rename", verbo, nombre_nuevo))
    if not renombrado.get("ok") or renombrado.get("tool", {}).get("verbo") != verbo:
        raise RuntimeError(f"ABM rename cambió identidad o falló: {renombrado}")
    actualizado = json.loads(api.function_manage(
        "update", verbo, json.dumps(obtenido["graph"])))
    if not actualizado.get("ok") or actualizado.get("tool", {}).get("label") != nombre_nuevo:
        raise RuntimeError(f"ABM update perdió metadata o falló: {actualizado}")

    spec = json.loads(api.spec_all())
    tool = next((t for t in spec["tools"] if t["verbo"] == verbo), None)
    if tool is None or [p["name"] for p in tool.get("inputs", [])] != ["in"] \
            or [p["name"] for p in tool.get("outputs", [])] != ["salida"]:
        raise RuntimeError(f"el ribbon no recibió la firma guardada: {tool}")

    borrado = json.loads(api.function_manage("delete", verbo))
    if not borrado.get("ok"):
        raise RuntimeError(f"ABM delete falló: {borrado}")
    funcion_id = ""

    unreal.log("JAM_FUNCION_TEST TODO VERDE — ABM completo + dos instancias + "
               f"identidad estable + Compile {sorted(esperados)}")
finally:
    if funcion_id:
        preset.borrar_funcion(funcion_id)
