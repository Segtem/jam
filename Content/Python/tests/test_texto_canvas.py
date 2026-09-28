"""El texto del grafo en el canvas (tarea `dsl-grafos`, tramo 3): nombres legibles, buzón y el
contrato con el C++ del Graph.

Lo que se dibuja se juzga en el editor; acá se ata lo que puede separarse en silencio: la regla del
nombre vive en Python y el C++ la pide; las funciones de `jam.api` que el `.cpp` llama por nombre
tienen que existir; y los ganchos que publican el grafo tienen que estar donde pasa cada cambio.
"""

from __future__ import annotations

import json
import re
import sys
import types
import unittest
from pathlib import Path
from unittest import mock

_unreal_fake = sys.modules.setdefault("unreal", types.ModuleType("unreal"))
if not hasattr(_unreal_fake, "TopLevelAssetPath"):
    _unreal_fake.TopLevelAssetPath = lambda package, name: (package, name)

from jam import api, texto  # noqa: E402

RAIZ = Path(__file__).resolve().parents[3]
EDITOR = RAIZ / "Source/JamEditor/Private/SJamGraphEditor.cpp"


def _sin_comentarios(ruta: Path) -> str:
    # Los comentarios cuentan (AGENTS.md): uno que EXPLICA un patrón lo nombraría.
    return "\n".join(l for l in ruta.read_text(encoding="utf-8").splitlines()
                     if not l.strip().startswith("//"))


def _cuerpo(fuente: str, firma: str) -> str:
    return fuente.split(firma, 1)[1].split("\n}\n", 1)[0]


class NombreNuevo(unittest.TestCase):
    def test_el_nombre_es_el_verbo(self):
        self.assertEqual(texto.nombre_nuevo("mesh_weld", []), "mesh_weld")

    def test_si_existe_lleva_sufijo_y_no_renombra_a_nadie(self):
        self.assertEqual(texto.nombre_nuevo("mesh_weld", ["mesh_weld"]), "mesh_weld_2")
        self.assertEqual(texto.nombre_nuevo("mesh_weld", ["mesh_weld", "mesh_weld_2"]), "mesh_weld_3")

    def test_una_funcion_no_arrastra_su_id_opaco(self):
        self.assertEqual(texto.nombre_nuevo("fn:f_0a1b2c", []), "funcion")

    def test_todo_nombre_nuevo_es_escribible_en_el_texto(self):
        for verbo in list(texto.vocabulario())[:200] + ["fn:x-y", "9raro"]:
            with self.subTest(verbo):
                self.assertRegex(texto.nombre_nuevo(verbo, []), texto.IDENT)

    def test_la_api_lo_devuelve_como_json(self):
        r = json.loads(api.nombre_de_nodo_nuevo("mesh_box", json.dumps(["mesh_box"])))
        self.assertEqual(r, {"nombre": "mesh_box_2"})


class Buzon(unittest.TestCase):
    def setUp(self):
        self._canvas, self._pendiente = dict(api._CANVAS), dict(api._PENDIENTE)
        api._CANVAS["json"] = ""
        api._PENDIENTE.update({"version": 0, "json": "", "visto": 0})

    def tearDown(self):
        api._CANVAS.clear(); api._CANVAS.update(self._canvas)
        api._PENDIENTE.clear(); api._PENDIENTE.update(self._pendiente)

    def test_el_texto_sin_argumento_es_el_del_canvas_publicado(self):
        api.canvas_publicar(json.dumps({"nodes": {"caja": {"verb": "mesh_box", "params": {}}},
                                        "edges": []}))
        self.assertEqual(json.loads(api.graph_text())["texto"], "caja = mesh_box\n")

    def test_lo_que_corre_por_texto_queda_en_el_buzon_con_el_layout_del_canvas(self):
        api.canvas_publicar(json.dumps({"nodes": {"caja": {"verb": "mesh_box", "params": {},
                                                           "x": 700, "y": 40}}, "edges": []}))
        antes = api._PENDIENTE["version"]
        with mock.patch.object(api, "run_graph_json",
                               lambda g: json.dumps({"ok": True, "report": "", "nodes": {}})):
            api.run_text("caja = mesh_box\nn = mesh_normals @caja\n")
        pendiente = json.loads(api.canvas_pendiente(str(antes)))
        self.assertEqual(pendiente["version"], antes + 1)
        grafo = json.loads(pendiente["graph"])
        self.assertEqual((grafo["nodes"]["caja"]["x"], grafo["nodes"]["caja"]["y"]), (700, 40))
        self.assertEqual(set(grafo["nodes"]), {"caja", "n"})

    def test_sin_nada_nuevo_el_buzon_no_devuelve_grafo(self):
        v = api._PENDIENTE["version"]
        self.assertIsNone(json.loads(api.canvas_pendiente(str(v)))["graph"])

    def test_un_texto_ilegible_no_llega_al_canvas(self):
        antes = api._PENDIENTE["version"]
        api.run_text("caja = mesh_box\nn = mesh_normals @cajaa\n")
        self.assertEqual(api._PENDIENTE["version"], antes)


class ContratoConElGraph(unittest.TestCase):
    """El `.cpp` y el cerebro, atados."""

    @classmethod
    def setUpClass(cls):
        cls.cpp = _sin_comentarios(EDITOR)

    def test_las_funciones_de_la_api_que_llama_el_cpp_existen(self):
        llamadas = set(re.findall(r'LlamarApi\(\s*TEXT\("(\w+)"\)', self.cpp))
        self.assertGreaterEqual(llamadas, {"nombre_de_nodo_nuevo", "graph_text", "graph_from_text",
                                           "canvas_publicar", "canvas_pendiente"})
        faltan = sorted(n for n in llamadas if not callable(getattr(api, n, None)))
        self.assertEqual(faltan, [])

    def test_un_nodo_nuevo_pide_su_nombre_a_python(self):
        add = _cuerpo(self.cpp, "FString SJamGraphEditor::AddNode(")
        self.assertIn("NombreDeNodoNuevo(Verb)", add)
        self.assertNotIn('TEXT("n%d")', add, "el nombre opaco volvió a AddNode")

    def test_la_ficha_recibe_su_nombre(self):
        self.assertIn(".NodeName(Id)", _cuerpo(self.cpp, "FString SJamGraphEditor::AddNode("))

    def test_cada_cambio_publica_el_grafo(self):
        """Marcar y RestaurarSnapshot son los dos lugares por donde pasa todo cambio del canvas."""
        self.assertIn("AlCambiarGrafo()", _cuerpo(self.cpp, "void SJamGraphEditor::Marcar()"))
        self.assertIn("AlCambiarGrafo()",
                      _cuerpo(self.cpp, "void SJamGraphEditor::RestaurarSnapshot("))

    def test_aplicar_y_el_buzon_cargan_diferido(self):
        """Cargar un grafo adentro de un clic muta los widgets mientras Slate los recorre: es el
        crash de `Prepass_Internal` (ver `CrearNodoDiferido`)."""
        pedir = _cuerpo(self.cpp, "void SJamGraphEditor::PedirAplicarTexto()")
        self.assertIn("RegisterActiveTimer", pedir)
        self.assertNotIn("LoadGraphJson", pedir)
        self.assertIn("SondearBuzon", _cuerpo(self.cpp, "void SJamGraphEditor::Construct("))

    def test_lo_tipeado_sin_aplicar_no_se_pisa(self):
        self.assertIn("!bTextoEditado", _cuerpo(self.cpp, "void SJamGraphEditor::AlCambiarGrafo()"))


if __name__ == "__main__":
    unittest.main()
