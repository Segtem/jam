"""El texto de un grafo en la API (tarea `dsl-grafos`, tramo 2): unión con el canvas y Run por texto."""

from __future__ import annotations

import json
import sys
import types
import unittest
from pathlib import Path
from unittest import mock

_unreal_fake = sys.modules.setdefault("unreal", types.ModuleType("unreal"))
if not hasattr(_unreal_fake, "TopLevelAssetPath"):
    _unreal_fake.TopLevelAssetPath = lambda package, name: (package, name)

from jam import api, panel, texto  # noqa: E402

RAIZ = Path(__file__).resolve().parents[3]
CYLINDER = (RAIZ / "Resources/Examples/Cylinder-Strip.jamgraph").read_text(encoding="utf-8")


class Aplicar(unittest.TestCase):
    def setUp(self):
        self.base = json.loads(CYLINDER)
        self.texto = json.loads(api.graph_text(CYLINDER))["texto"]

    def test_un_nodo_que_sobrevive_conserva_su_lugar(self):
        g = texto.aplicar(self.texto, CYLINDER)
        for nid, viejo in self.base["nodes"].items():
            self.assertEqual((g["nodes"][nid]["x"], g["nodes"][nid]["y"]), (viejo["x"], viejo["y"]))

    def test_un_nodo_nuevo_va_a_la_derecha_de_su_fuente_y_no_encima_de_nadie(self):
        t = self.texto.replace("normals = mesh_normals @pipe",
                               "weld = mesh_weld @pipe\nnormals = mesh_normals @weld")
        nodos = texto.aplicar(t, CYLINDER)["nodes"]
        self.assertEqual(nodos["weld"]["x"], nodos["pipe"]["x"] + texto.PASO_X)
        posiciones = [(n["x"], n["y"]) for n in nodos.values()]
        self.assertEqual(len(posiciones), len(set(posiciones)), "dos nodos en el mismo lugar")

    def test_el_canvas_recibe_todos_los_params(self):
        """El texto omite los defaults; el canvas los guarda todos (BuildJson), así que se completan."""
        nodos = texto.aplicar(self.texto, CYLINDER)["nodes"]
        self.assertEqual(set(nodos["pipe"]["params"]), set(self.base["nodes"]["pipe"]["params"]))
        self.assertEqual(nodos["pipe"]["params"]["capped"], "true")

    def test_los_reroutes_siguen_a_su_cable_aunque_cambie_el_indice(self):
        base = dict(self.base)
        indice = base["edges"].index(["pipe", "out", "normals", "in"])
        base["reroutes"] = {str(indice): [[10, 20]]}
        base["comments"] = {"c1": {"title": "tubo"}}
        # El texto pone el cable en otro orden: `normals` recibe de `pipe` al final.
        t = "\n".join(l for l in self.texto.splitlines() if not l.startswith("normals ")) + \
            "\nnormals = mesh_normals @pipe\n"
        t = t.replace("hornear = mesh_to_static @normals", "hornear = mesh_to_static @normals")
        g = texto.aplicar(t, json.dumps(base))
        nuevo = g["edges"].index(["pipe", "out", "normals", "in"])
        self.assertNotEqual(nuevo, indice)
        self.assertEqual(g["reroutes"], {str(nuevo): [[10, 20]]})
        self.assertEqual(g["comments"], {"c1": {"title": "tubo"}})

    def test_el_literal_tapado_por_un_cable_no_se_pierde(self):
        """Si después se desconecta, vuelve lo que el humano escribió, no el default."""
        base = json.loads(CYLINDER)
        base["nodes"]["polyline"]["params"]["x"] = "0,5,10"
        g = texto.aplicar(self.texto, json.dumps(base))
        self.assertEqual(g["nodes"]["polyline"]["params"]["x"], "0,5,10")

    def test_sin_base_el_layout_sale_de_layout_auto(self):
        nodos = texto.aplicar("a = mesh_box\nb = mesh_normals @a\n")["nodes"]
        self.assertLess(nodos["a"]["x"], nodos["b"]["x"])


class GraphFromText(unittest.TestCase):
    def test_un_error_de_lectura_no_arma_grafo_y_dice_la_linea(self):
        r = json.loads(api.graph_from_text("a = mesh_box\nb = mesh_normals @z\n"))
        self.assertIsNone(r["graph"])
        self.assertEqual((r["errores"][0]["linea"], r["errores"][0]["columna"]), (2, 18))

    def test_un_error_de_compile_queda_en_la_linea_de_su_nodo(self):
        r = json.loads(api.graph_from_text("a = mesh_box\nb = mesh_normals @a cownt=3\n"))
        self.assertFalse(r["ok"])
        self.assertIsNotNone(r["graph"], "el grafo se devuelve igual, para mirarlo en el canvas")
        self.assertEqual([(e["linea"], e["nodo"]) for e in r["errores"]], [(2, "b")])
        self.assertIn("«cownt»", r["errores"][0]["mensaje"])

    def test_devuelve_el_texto_canonico(self):
        r = json.loads(api.graph_from_text("a=mesh_box\nb = mesh_normals   @a\n"))
        self.assertTrue(r["ok"], r["errores"])
        self.assertEqual(r["canonico"], "a = mesh_box\nb = mesh_normals @a\n")


class RunPorTexto(unittest.TestCase):
    def test_un_documento_corre_por_el_run_del_canvas_y_el_reporte_dice_la_linea(self):
        visto = {}

        def run_graph_json(g):
            visto["grafo"] = json.loads(g)
            return json.dumps({"ok": True, "report": "[a·mesh_box] BOX M ✓\n[b·mesh_normals] ✓",
                               "nodes": {"a": {"estado": "ok"}, "b": {"estado": "ok"}}})

        with mock.patch.object(api, "run_graph_json", run_graph_json):
            r = json.loads(api.run_text("a = mesh_box\nb = mesh_normals @a\n"))
        self.assertEqual(set(visto["grafo"]["nodes"]), {"a", "b"})
        self.assertIn("línea 2 [b·mesh_normals]", r["report"])
        self.assertEqual(r["lineas"], {"a": 1, "b": 2})

    def test_un_texto_con_errores_no_corre(self):
        with mock.patch.object(api, "run_graph_json", side_effect=AssertionError("corrió")):
            r = json.loads(api.run_text("a = mesh_box\nb = mesh_normals @a cownt=3\n"))
        self.assertFalse(r["ok"])
        self.assertIn("línea 2 (b)", r["report"])

    def test_api_run_distingue_documento_de_comando(self):
        with mock.patch.object(api, "run_text", lambda t: json.dumps({"report": "DOC"})), \
                mock.patch.object(panel, "ejecutar_dsl", lambda t, w=None: "CONSOLA"):
            self.assertEqual(api.run("a = mesh_box"), "DOC")
            self.assertEqual(api.run("scatter SM_Rock count=20"), "CONSOLA")


if __name__ == "__main__":
    unittest.main()
