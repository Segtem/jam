from __future__ import annotations

import json
import math
import sys
import types
import unittest


unreal = sys.modules.setdefault("unreal", types.ModuleType("unreal"))
if not hasattr(unreal, "TopLevelAssetPath"):
    unreal.TopLevelAssetPath = lambda package, name: (package, name)

from jam import api, fields, graph, tools  # noqa: E402


class SeriesCoreTests(unittest.TestCase):
    def test_range_incluye_ambos_extremos_y_puede_descender(self):
        ascendente = fields.series_range(start=2.0, end=10.0, count=5)["series"]
        descendente = fields.series_range(start=1.0, end=-1.0, count=3)["series"]
        self.assertEqual(ascendente.values, (2.0, 4.0, 6.0, 8.0, 10.0))
        self.assertEqual(descendente.values, (1.0, 0.0, -1.0))

    def test_range_rechaza_limites_y_no_finitos(self):
        for params in ({"count": 1}, {"count": 4097}, {"start": math.inf}):
            with self.subTest(params=params):
                self.assertIn("error", fields.series_range(**params))

    def test_remap_limita_o_extrapola_sin_mutar_la_serie(self):
        source = fields.ScalarSeries((-1.0, 0.0, 0.5, 1.0, 2.0), "entrada")
        limitado = fields.series_remap(
            source, source_min=0.0, source_max=1.0,
            target_min=10.0, target_max=20.0, clamp=True)["series"]
        libre = fields.series_remap(
            source, source_min=0.0, source_max=1.0,
            target_min=10.0, target_max=20.0, clamp=False)["series"]
        self.assertEqual(limitado.values, (10.0, 10.0, 15.0, 20.0, 20.0))
        self.assertEqual(libre.values, (0.0, 10.0, 15.0, 20.0, 30.0))
        self.assertEqual(source.values, (-1.0, 0.0, 0.5, 1.0, 2.0))

    def test_remap_admite_dominios_invertidos_y_rechaza_el_degenerado(self):
        source = fields.ScalarSeries((1.0, 0.5, 0.0))
        result = fields.series_remap(
            source, source_min=1.0, source_max=0.0,
            target_min=0.0, target_max=100.0)["series"]
        self.assertEqual(result.values, (0.0, 50.0, 100.0))
        self.assertIn("error", fields.series_remap(source, source_min=1.0, source_max=1.0))
        self.assertIn("error", fields.series_remap(None))


class SeriesGraphTests(unittest.TestCase):
    def tearDown(self):
        tools.limpiar_asset_producido_runtime("series_range")
        tools.limpiar_asset_producido_runtime("series_remap")

    def test_spec_publica_la_fuente_y_el_operador_tipados(self):
        spec = {item["verbo"]: item for item in json.loads(api.spec_all())["tools"]}
        rango, remap = spec["series_range"], spec["series_remap"]
        self.assertTrue(rango["source"])
        self.assertEqual(rango["out_name"], "N[]")
        self.assertFalse(rango["asset_pin"])
        self.assertEqual(rango["grupo"], "Series")
        self.assertFalse(remap["source"])
        self.assertEqual(remap["in_name"], "N[]")
        self.assertEqual(remap["out_name"], "N[]")
        self.assertFalse(remap["asset_pin"])
        self.assertEqual(remap["grupo"], "Series")

    def test_compile_y_runtime_encadenan_range_con_remap(self):
        g = graph.JamGraph()
        g.add("series_range", {"start": -1.0, "end": 1.0, "count": 5}, nid="rango")
        g.add("series_remap", {
            "source_min": -1.0, "source_max": 1.0,
            "target_min": 0.0, "target_max": 10.0, "clamp": True,
        }, nid="remap")
        g.connect("rango", "remap")

        compilado = json.loads(api.compile_graph_json(g.to_json()))
        self.assertTrue(compilado["ok"], compilado)
        reporte, estados = graph.ejecutar_detalle(g)
        self.assertEqual(estados["rango"]["estado"], "ok", reporte)
        self.assertEqual(estados["remap"]["estado"], "ok", reporte)
        self.assertEqual(
            tools.dato_producido_runtime("series_remap").values,
            (0.0, 2.5, 5.0, 7.5, 10.0),
        )

    def test_compile_rechaza_un_cable_numerico_en_vez_de_serie(self):
        g = graph.JamGraph()
        g.add("number", {"name": "uno", "value": 1.0}, nid="numero")
        g.add("series_remap", {}, nid="remap")
        g.connect("numero", "remap")
        compilado = json.loads(api.compile_graph_json(g.to_json()))
        self.assertFalse(compilado["ok"])
        self.assertIn("esperaba N[], recibió N", compilado["nodes"]["remap"]["texto"])


if __name__ == "__main__":
    unittest.main()
