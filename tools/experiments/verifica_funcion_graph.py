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

    padre = JamGraph.from_json(json.dumps(colapsado["graph"]))
    instancia = next(nid for nid, n in padre.nodes.items() if n["verb"] == f"fn:{nombre}")
    # La segunda instancia se pone en serie con la primera: el Compile tiene que expandir ambas.
    padre.add(f"fn:{nombre}", {}, nid="f2", x=600, y=20)
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

    spec = json.loads(api.spec_all())
    tool = next((t for t in spec["tools"] if t["verbo"] == f"fn:{nombre}"), None)
    if tool is None or [p["name"] for p in tool.get("inputs", [])] != ["in"] \
            or [p["name"] for p in tool.get("outputs", [])] != ["salida"]:
        raise RuntimeError(f"el ribbon no recibió la firma guardada: {tool}")

    unreal.log("JAM_FUNCION_TEST TODO VERDE — guardar selección + dos instancias + "
               f"Compile {sorted(esperados)}")
finally:
    preset.borrar(nombre)
