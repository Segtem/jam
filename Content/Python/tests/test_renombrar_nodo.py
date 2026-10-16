"""Renombrar un nodo en el editor web: escenarios rn1–rn2 del cambio 20261015-221410-renombrar-nodo.

El editor corre de verdad en node (`editor_en_node.js`): LiteGraph, `web/renombrar.js` y `web/editor.js`
reales, con un DOM mínimo de prueba y el servidor del núcleo (`jam.servidor`) detrás, así que F2, el
diálogo, la serialización (`aJam`) y el Compile son los del editor. La función pura se prueba además
sola, también con node.
"""

from __future__ import annotations

import http.server
import json
import shutil
import subprocess
import sys
import threading
import types
import unittest
from pathlib import Path

sys.modules.setdefault("unreal", types.ModuleType("unreal"))

from jam import registro, servidor  # noqa: E402

WEB = Path(servidor.WEB)
NODE = shutil.which("node")
ARNES = Path(__file__).resolve().parent / "editor_en_node.js"


def renombrar(nodo: dict, nuevo, usados) -> dict:
    """Lo que devuelve `JamRenombrar.renombrar` de web/renombrar.js, sola."""
    programa = ("const {renombrar} = require(process.argv[1]);"
                "const [n, nuevo, usados] = JSON.parse(process.argv[2]);"
                "process.stdout.write(JSON.stringify(renombrar(n, nuevo, usados)));")
    salida = subprocess.run([NODE, "-e", programa, str(WEB / "renombrar.js"), json.dumps([nodo, nuevo, list(usados)])],
                            capture_output=True, text=True, check=True).stdout
    return json.loads(salida)


@unittest.skipUnless(NODE, "hace falta node para correr el editor web")
class RenombrarNodo(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), servidor._handler(servidor.Nucleo("godot")))
        threading.Thread(target=cls.srv.serve_forever, daemon=True).start()
        cls.base = f"http://127.0.0.1:{cls.srv.server_address[1]}"

    @classmethod
    def tearDownClass(cls):
        cls.srv.shutdown()
        cls.srv.server_close()

    def editor(self, escenario: str) -> dict:
        p = subprocess.run([NODE, str(ARNES), str(WEB), self.base, escenario], capture_output=True, text=True, timeout=90)
        self.assertEqual(p.returncode, 0, p.stderr[-2000:])
        return json.loads(p.stdout)

    # --- rn1: F2 renombra el nodo seleccionado ----------------------------------------------------------------------
    def test_rn1_renombrar_con_f2(self):
        r = self.editor("f2")
        self.assertTrue(r["evitado"])            # F2 no siguió al navegador
        self.assertEqual(r["pedidos"], ["caja"])  # el diálogo se abrió con el nombre actual
        self.assertEqual(sorted(r["grafo"]["nodes"]), ["cubo", "ver"])
        self.assertEqual(r["grafo"]["edges"], [["cubo", "out", "ver", "in"]])  # el cable siguió al nodo
        self.assertTrue(r["compilado"]["ok"], r["compilado"])
        # Escribiendo en un campo, o con dos nodos seleccionados, F2 no abre nada.
        r = self.editor("f2_sin_disparar")
        self.assertEqual((r["pedidos"], r["nombres"]), ([], ["caja", "ver"]))

    def test_rn1_un_nombre_invalido_o_repetido(self):
        r = self.editor("invalido_o_repetido")
        for nombre, motivo in (("1cubo", "«1cubo» no es un nombre: letras, dígitos y «_», sin empezar por dígito"),
                               ("ver", "ya hay un nodo «ver»")):
            self.assertEqual(sorted(r[nombre]["grafo"]["nodes"]), ["caja", "ver"], nombre)  # el nodo quedó como estaba
            self.assertEqual(r[nombre]["grafo"]["edges"], [["caja", "out", "ver", "in"]], nombre)
            self.assertEqual(r[nombre]["reporte"], motivo)
        for nuevo in (None, "", "caja"):  # cancelar o dejar el mismo nombre: sin cambio y sin error
            self.assertEqual(renombrar({"nombre": "caja", "valor": False, "conName": False, "name": ""}, nuevo, ["caja"]),
                             {"ok": False, "error": ""})

    # --- rn2: la variable de un valor conserva su nombre al renombrar el nodo -----------------------------------------
    def test_rn2_un_valor_sin_name_propio(self):
        r = self.editor("valor_sin_name")
        # Cargado sin name, se llama como su nodo (no «n», el default de su parámetro): la variable de la expresión.
        self.assertEqual(r["cargado"]["nodes"]["ancho"]["params"]["name"], "ancho")
        self.assertEqual(r["grafo"]["nodes"]["ancho_total"]["params"]["name"], "ancho")  # renombrado, la conserva
        self.assertTrue(r["compilado"]["ok"], r["compilado"])  # «ancho * 2» sigue resolviendo la misma variable
        # Si el name se vació, renombrar le fija el nombre viejo.
        self.assertEqual(renombrar({"nombre": "ancho", "valor": True, "conName": True, "name": ""}, "otro", ["ancho"])["name"], "ancho")

    def test_rn2_nodos_de_valor_nuevos(self):
        r = self.editor("valores_nuevos")
        nodos = r["grafo"]["nodes"]
        self.assertEqual(sorted(nodos), ["number", "number_2"])
        self.assertEqual({n: d["params"]["name"] for n, d in nodos.items()}, {"number": "number", "number_2": "number_2"})
        self.assertTrue(r["compilado"]["ok"], r["compilado"])  # sin «nombre de variable duplicado: «n»»

    def test_rn2_un_valor_con_name_propio(self):
        r = self.editor("valor_con_name")
        self.assertEqual(r["grafo"]["nodes"]["ancho_total"]["params"]["name"], "medida")
        r = renombrar({"nombre": "caja", "valor": False, "conName": True, "name": ""}, "caja2", ["caja"])  # no es variable
        self.assertEqual((r["ok"], r["name"], r["variableSinName"]), (True, "", False))

    def test_rn2_una_operacion_que_una_expresion_usa(self):
        r = self.editor("operacion")
        self.assertEqual(sorted(r["usada"]["grafo"]["nodes"]), ["c", "libre", "s"])  # «s» la usa «c»: no se renombra
        self.assertEqual(r["usada"]["reporte"], "no renombré «s»: es una variable sin name y la usa «c»; cambiá primero esa expresión")
        # Con otra variable que ya faltaba en la misma expresión, el Compile habla en plural: tampoco se renombra.
        self.assertEqual(sorted(r["plural"]["grafo"]["nodes"]), ["c2", "s"])
        self.assertEqual(r["plural"]["reporte"], "no renombré «s»: es una variable sin name y la usa «c2»; cambiá primero esa expresión")
        self.assertEqual(sorted(r["libre"]["grafo"]["nodes"]), ["c", "otra", "s"])  # «libre» no la usa nadie: se renombra
        self.assertTrue(r["compilado"]["ok"], r["compilado"])
        spec = {t["verbo"]: t for t in registro.spec_canvas("godot")["tools"]}  # el spec dice qué nodos son variables
        self.assertEqual((spec["number"]["valor"], spec["math_add"]["valor"], spec["asset"]["valor"]), (True, True, False))


if __name__ == "__main__":
    unittest.main()
