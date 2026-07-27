"""Contratos de los presets: el `kind` sale del grafo y aplicar usa ese mismo runner.

Guardar cualquier canvas como preset lo marcaba siempre `flow`, así que un grafo de verbos —Place,
Mesh, TreeGen— se aplicaba con el evaluador de Flow, donde cada verbo es una op desconocida. Estas
pruebas fijan la detección, el ruteo y el round-trip completo canvas → preset → aplicar.
"""

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

from jam import api, preset  # noqa: E402


PLUGIN_ROOT = Path(__file__).resolve().parents[3]

FLOW_GRAPH = {
    "nodes": {
        "src": {"kind": "pts_line", "params": {"count": "5"}},
        "mv": {"kind": "move", "params": {"dx": "10"}},
    },
    "edges": [["src", "out", "mv", "in"]],
}

TOOL_GRAPH = {
    "nodes": {
        "a": {"verb": "asset", "params": {"name": "SM_Cube"}, "x": 0, "y": 0},
        "p": {"verb": "place", "params": {"asset": ""}, "x": 300, "y": 0},
    },
    "edges": [["a", "out", "p", "in"]],
}


class PresetKindTests(unittest.TestCase):
    def test_kind_comes_from_the_graph_not_from_the_button(self):
        self.assertEqual(preset.kind_de_grafo(FLOW_GRAPH), "flow")
        self.assertEqual(preset.kind_de_grafo(TOOL_GRAPH), "graph")
        # Acepta dict o el JSON crudo que manda Slate.
        self.assertEqual(preset.kind_de_grafo(json.dumps(TOOL_GRAPH)), "graph")
        # Un grafo mixto no es flow: cae al runner de verbos, donde Compile lo rechaza con nombre.
        mixed = {
            "nodes": dict(FLOW_GRAPH["nodes"]) | dict(TOOL_GRAPH["nodes"]),
            "edges": [],
        }
        self.assertEqual(preset.kind_de_grafo(mixed), "graph")

    def test_desde_grafo_marks_each_kind_and_keeps_the_metadata(self):
        flow_preset = preset.desde_grafo(
            "Cadena de puntos", FLOW_GRAPH, categoria="test", tags=["a"], scope="global")
        tool_preset = preset.desde_grafo("Colocar cubo", TOOL_GRAPH, categoria="test")

        self.assertEqual(flow_preset["kind"], "flow")
        self.assertEqual(tool_preset["kind"], "graph")
        self.assertEqual(tool_preset["graph"], TOOL_GRAPH)
        self.assertEqual(flow_preset["scope"], "global")
        self.assertEqual(tool_preset["scope"], "local")
        self.assertEqual(flow_preset["tags"], ["a"])

    def test_slug_transliterates_accents_instead_of_dropping_them(self):
        self.assertEqual(preset._slug("Árbol TreeGen dos niveles"), "arbol-treegen-dos-niveles")
        self.assertEqual(preset._slug("Diseño Ñandú"), "diseno-nandu")
        self.assertEqual(preset._slug("Muro de piedra 3m"), "muro-de-piedra-3m")


class PresetApplyTests(unittest.TestCase):
    def _aplicar(self, item):
        """Aplica capturando a qué runner fue y con qué owner, sin tocar Unreal."""
        from jam import panel

        calls = []

        def flow_runner(graph_json, widget=None, *, owner="graph"):
            calls.append(("flow", json.loads(graph_json), owner))
            return json.dumps({"report": "FLOW ✓ — 5 puntos", "nodes": {}})

        def graph_runner(graph_json, widget=None, *, owner="graph"):
            calls.append(("graph", json.loads(graph_json), owner))
            return json.dumps({"report": "PLACE ✓ — 1 pieza", "nodes": {}})

        with mock.patch.object(panel, "ejecutar_flow_json", flow_runner), \
                mock.patch.object(panel, "ejecutar_grafo_json", graph_runner), \
                mock.patch.object(panel, "ejecutar_dsl", lambda *a, **k: "DSL ✓"):
            result = preset.aplicar(item)
        return result, calls

    def test_a_tool_graph_preset_runs_the_graph_runner_as_dash(self):
        result, calls = self._aplicar(preset.desde_grafo("Colocar cubo", TOOL_GRAPH))

        self.assertTrue(result["ok"], result)
        self.assertEqual([call[0] for call in calls], ["graph"])
        self.assertEqual(calls[0][1], TOOL_GRAPH)
        # Aplicado desde la Dash Bar: su Confirmar/Descartar tiene que resolverlo.
        self.assertEqual(calls[0][2], "dash")
        self.assertIn("PLACE ✓", result["texto"])

    def test_a_flow_preset_still_runs_the_flow_runner(self):
        result, calls = self._aplicar(preset.desde_grafo("Cadena", FLOW_GRAPH))

        self.assertTrue(result["ok"], result)
        self.assertEqual([call[0] for call in calls], ["flow"])
        self.assertEqual(calls[0][2], "dash")

    def test_a_legacy_flow_preset_holding_verbs_is_rerouted_by_content(self):
        # Presets guardados antes de la corrección declaran `flow` aunque contengan verbos.
        legacy = {"kind": "flow", "nombre": "Viejo", "graph": TOOL_GRAPH, "oraculo": {}}
        result, calls = self._aplicar(legacy)

        self.assertEqual([call[0] for call in calls], ["graph"])
        self.assertTrue(result["ok"], result)

    def test_a_command_preset_is_untouched(self):
        _, calls = self._aplicar(
            preset.desde_comando("Muro", "spline axis=x anchor=base"))
        self.assertEqual(calls, [])

    def test_a_graph_preset_without_graph_fails_instead_of_running_anything(self):
        result, calls = self._aplicar({"kind": "graph", "nombre": "Roto"})
        self.assertFalse(result["ok"])
        self.assertIn("no trae grafo", result["texto"])
        self.assertEqual(calls, [])


class BundledPresetTests(unittest.TestCase):
    """Los presets de fábrica versionados en el repo del plugin."""

    @staticmethod
    def _bundled():
        return [
            (path, json.loads(path.read_text(encoding="utf-8")))
            for path in sorted((PLUGIN_ROOT / "presets").glob("*.json"))
        ]

    def test_every_bundled_preset_declares_the_kind_its_content_needs(self):
        bundled = self._bundled()
        self.assertGreaterEqual(len(bundled), 6)
        for path, item in bundled:
            with self.subTest(preset=path.name):
                self.assertIn(item["kind"], ("tool", "flow", "graph"))
                self.assertTrue(item.get("nombre"))
                self.assertEqual(item.get("scope"), "global")
                if item["kind"] == "tool":
                    self.assertTrue(item.get("command"))
                else:
                    self.assertEqual(preset.kind_de_grafo(item["graph"]), item["kind"])

    def test_bundled_names_are_unique_after_slugging(self):
        # `cargar()` resuelve por slug del nombre: dos presets que colapsen al mismo slug se pisan.
        slugs = [preset._slug(item["nombre"]) for _path, item in self._bundled()]
        self.assertEqual(sorted(slugs), sorted(set(slugs)))

    def test_the_treegen_presets_carry_the_bundled_examples_and_compile(self):
        from jam import graph

        pares = {
            "arbol-treegen-dos-niveles": "TreeGen-Two-Level.jamgraph",
            "arbol-treegen-un-nivel": "TreeGen-Curve-Frames.jamgraph",
        }
        for slug, ejemplo in pares.items():
            with self.subTest(preset=slug):
                item = json.loads(
                    (PLUGIN_ROOT / "presets" / f"{slug}.json").read_text(encoding="utf-8"))
                ejemplo_json = json.loads(
                    (PLUGIN_ROOT / "Resources" / "Examples" / ejemplo).read_text(encoding="utf-8"))

                self.assertEqual(item["kind"], "graph")
                # El preset es el ejemplo: editar uno sin el otro tiene que romper esta prueba.
                self.assertEqual(item["graph"]["nodes"], ejemplo_json["nodes"])
                self.assertEqual(item["graph"]["edges"], ejemplo_json["edges"])

                with mock.patch.object(graph, "_resolver_asset_runtime", side_effect=lambda p: p):
                    compiled = json.loads(api.compile_graph_json(json.dumps(item["graph"])))
                self.assertTrue(compiled["ok"], compiled["report"])


if __name__ == "__main__":
    unittest.main()
