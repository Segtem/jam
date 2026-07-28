"""Compila TODOS los tutoriales del tab «Aprender» en el editor real, como lo haría quien los abre.

`tests/test_ejemplos.py` cubre lo estructural sin editor: verbos que existen, params, tipos, ciclos.
Lo que no puede es resolver ASSETS —necesita el registro de Unreal—, y ése es justamente el modo en
que un ejemplo se pudre: alguien mueve o renombra una malla y el tutorial queda rojo para el próximo
que lo abra, que va a creer que se equivocó él.

Esto corre el mismo Compile del canvas (`api.compile_graph_json`) sobre cada `.jamgraph` del
catálogo, con el proyecto cargado.

    UnrealEditor-Cmd <proyecto>.uproject -run=pythonscript \\
        -script=<plugin>/tools/experiments/verifica_ejemplos.py \\
        -RenderOffScreen -unattended -nosplash -stdout

Salida en Saved/Logs/<proyecto>.log.
"""

from __future__ import annotations

import json
import os

import unreal

from jam import api


FALLAS = []

# .../Jam/tools/experiments/este.py → tres niveles hasta la raíz del plugin.
RAIZ = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
EJEMPLOS = os.path.join(RAIZ, "Resources", "Examples")


def log(mensaje: str) -> None:
    unreal.log(f"[EJEMPLOS] {mensaje}")


def exigir(condicion: bool, descripcion: str) -> None:
    log(("  OK   " if condicion else "  FALLA") + f" · {descripcion}")
    if not condicion:
        FALLAS.append(descripcion)


def main() -> None:
    log("=" * 70)
    with open(os.path.join(EJEMPLOS, "examples.json"), encoding="utf-8") as f:
        catalogo = json.load(f)["ejemplos"]
    log(f"catálogo: {len(catalogo)} tutorial(es) en "
        f"{len({e['grupo'] for e in catalogo})} grupo(s)")

    for entrada in catalogo:
        ruta = os.path.join(EJEMPLOS, entrada["archivo"])
        if not os.path.exists(ruta):
            exigir(False, f"{entrada['archivo']}: el archivo no existe")
            continue
        with open(ruta, encoding="utf-8") as f:
            grafo_json = f.read()
        reporte = json.loads(api.compile_graph_json(grafo_json))
        malos = {nid: estado["texto"] for nid, estado in reporte["nodes"].items()
                 if estado["estado"] == "error"}
        exigir(reporte["ok"],
               f"{entrada['titulo']:26s} ({entrada['archivo']}) compila"
               + (f" · {malos}" if malos else ""))

    log("=" * 70)
    log("VEREDICTO: " + ("TODO VERDE" if not FALLAS else f"{len(FALLAS)} FALLA(S): {FALLAS}"))


main()
