"""Renombrar un nodo en el editor web: escenarios rn1–rn2 del cambio 20261015-221410-renombrar-nodo.

La lógica está en `web/renombrar.js`, una función pura que el editor usa y que acá se corre con node.
Que una variable conserve su nombre se comprueba compilando un grafo real con `graph.compilar`.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
import sys
import types
import unittest
from pathlib import Path

sys.modules.setdefault("unreal", types.ModuleType("unreal"))

from jam import graph, registro, servidor  # noqa: E402

WEB = Path(servidor.WEB)
NODE = shutil.which("node")


def renombrar(nodo: dict, nuevo, usados) -> dict:
    """Lo que devuelve `JamRenombrar.renombrar` de web/renombrar.js, corrido con node."""
    programa = ("const {renombrar} = require(process.argv[1]);"
                "const [n, nuevo, usados] = JSON.parse(process.argv[2]);"
                "process.stdout.write(JSON.stringify(renombrar(n, nuevo, usados)));")
    salida = subprocess.run([NODE, "-e", programa, str(WEB / "renombrar.js"), json.dumps([nodo, nuevo, list(usados)])],
                            capture_output=True, text=True, check=True).stdout
    return json.loads(salida)


def compilar(nodos: dict, edges=()):
    g = graph.JamGraph.from_json(json.dumps({"schema_version": 1, "nodes": nodos, "edges": [list(e) for e in edges]}))
    return graph.compilar(g, registro=registro.REGISTRO, motor="godot")


def aplicar(nodos: dict, edges, viejo: str, r: dict):
    """Lo que hace el editor con el resultado: el nodo cambia de nombre, sus cables lo siguen (el JSON los arma por
    nombre, `aJam`) y el valor de su `name` es el que devolvió renombrar."""
    nodos = {(r["nombre"] if k == viejo else k): dict(v, params=dict(v["params"])) for k, v in nodos.items()}
    if "name" in nodos[r["nombre"]]["params"]:
        nodos[r["nombre"]]["params"]["name"] = r["name"]
    edges = [[r["nombre"] if x == viejo else x for x in e] for e in edges]
    return nodos, edges


@unittest.skipUnless(NODE, "hace falta node para correr web/renombrar.js")
class RenombrarNodo(unittest.TestCase):
    def editor(self) -> str:
        return (WEB / "editor.js").read_text(encoding="utf-8")

    # --- rn1: F2 renombra el nodo seleccionado ----------------------------------------------------------------------
    def test_rn1_renombrar_con_f2(self):
        editor = self.editor()
        # F2 con un solo nodo seleccionado abre el mismo diálogo que «Renombrar…», y no mientras se escribe en un campo.
        f2 = re.search(r'addEventListener\("keydown", \(e\) => \{(.*?)\n\}\);', editor, re.S)
        self.assertTrue(f2, "no hay un manejador de teclas")
        cuerpo = f2.group(1)
        self.assertIn('e.key !== "F2"', cuerpo)
        self.assertIn("INPUT|TEXTAREA|SELECT", cuerpo)
        self.assertIn("seleccionados.length !== 1", cuerpo)
        self.assertIn("renombrar(seleccionados[0])", cuerpo)
        self.assertIn('{ content: "Renombrar…", callback: () => renombrar(nodo) }', editor)  # el mismo que el menú
        html = (WEB / "editor.html").read_text(encoding="utf-8")
        self.assertLess(html.index('src="renombrar.js"'), html.index('src="editor.js"'))
        # Un nodo que alimenta a otro, renombrado: el cable sigue conectado con el nombre nuevo y el grafo compila.
        nodos = {"cubo": {"verb": "number", "params": {"name": "lado", "value": "2"}},
                 "suma": {"verb": "math_add", "params": {}}}
        edges = [("cubo", "out", "suma", "a")]
        compilar(nodos, edges)
        r = renombrar({"nombre": "cubo", "valor": True, "conName": True, "name": "lado"}, "caja", nodos)
        self.assertEqual((r["ok"], r["nombre"]), (True, "caja"))
        nuevos, cables = aplicar(nodos, edges, "cubo", r)
        self.assertEqual(cables, [["caja", "out", "suma", "a"]])
        compilar(nuevos, cables)

    def test_rn1_un_nombre_invalido_o_repetido(self):
        nodo = {"nombre": "cubo", "valor": False, "conName": False, "name": ""}
        for nuevo, error in (("1cubo", "no es un nombre"), ("cubo-2", "no es un nombre"), ("cubo grande", "no es un nombre"),
                             ("esfera", "ya hay un nodo «esfera»")):
            r = renombrar(nodo, nuevo, ["cubo", "esfera"])
            self.assertFalse(r["ok"], nuevo)
            self.assertIn(error, r["error"], nuevo)
            self.assertNotIn("nombre", r)  # nada que aplicar: el nodo queda como estaba
        for nuevo in (None, "", "cubo"):  # cancelar o dejar el mismo: sin cambio y sin error
            self.assertEqual(renombrar(nodo, nuevo, ["cubo"]), {"ok": False, "error": ""})
        # En el editor, un resultado que no es ok se informa y vuelve antes de tocar el nodo.
        editor = self.editor()
        i = editor.index("function renombrar(nodo)")
        cuerpo = editor[i:editor.index("\n}\n", i)]
        self.assertLess(cuerpo.index("if (!r.ok) return r.error ? reportar(r.error"), cuerpo.index("nodo.properties.nombre = r.nombre"))

    # --- rn2: la variable de un valor conserva su nombre al renombrar el nodo -----------------------------------------
    def test_rn2_un_valor_sin_name_propio(self):
        nodos = {"ancho": {"verb": "number", "params": {"name": "", "value": "3"}},
                 "calc": {"verb": "math", "params": {"name": "doble", "expr": "ancho * 2"}}}
        compilar(nodos)  # la expresión usa la variable «ancho», que es el nombre del nodo
        r = renombrar({"nombre": "ancho", "valor": True, "conName": True, "name": ""}, "ancho_total", nodos)
        self.assertEqual((r["ok"], r["nombre"], r["name"], r["aviso"]), (True, "ancho_total", "ancho", ""))
        nuevos, _ = aplicar(nodos, [], "ancho", r)
        compilar(nuevos)  # la expresión sigue resolviendo la misma variable
        sin_arreglo = dict(nuevos, ancho_total={"verb": "number", "params": {"name": "", "value": "3"}})
        with self.assertRaisesRegex(graph.GraphValidationError, "«ancho», que no es una variable"):
            compilar(sin_arreglo)  # sin fijar name, se rompía

    def test_rn2_un_valor_con_name_propio(self):
        r = renombrar({"nombre": "ancho", "valor": True, "conName": True, "name": "medida"}, "ancho_total", ["ancho"])
        self.assertEqual((r["ok"], r["name"], r["aviso"]), (True, "medida", ""))
        # Un nodo que no es de valor no tiene variable: nada que conservar ni avisar.
        r = renombrar({"nombre": "caja", "valor": False, "conName": True, "name": ""}, "caja2", ["caja"])
        self.assertEqual((r["ok"], r["name"], r["aviso"]), (True, "", ""))
        # Una variable sin parámetro name (una op math_*): su nombre cambia, y el editor lo avisa.
        r = renombrar({"nombre": "suma", "valor": True, "conName": False, "name": ""}, "total", ["suma"])
        self.assertTrue(r["ok"])
        self.assertIn("las expresiones que la nombraban así ahora tienen que decir «total»", r["aviso"])
        # El spec del editor dice qué nodos son variables.
        spec = {t["verbo"]: t for t in registro.spec_canvas("godot")["tools"]}
        self.assertEqual((spec["number"]["valor"], spec["math_add"]["valor"], spec["asset"]["valor"]), (True, True, False))


if __name__ == "__main__":
    unittest.main()
