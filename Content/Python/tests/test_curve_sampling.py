from __future__ import annotations

import json
import math
import sys
import types
import unittest


unreal = sys.modules.setdefault("unreal", types.ModuleType("unreal"))
if not hasattr(unreal, "TopLevelAssetPath"):
    unreal.TopLevelAssetPath = lambda package, name: (package, name)

from jam import api, curve, curve_sampling_core, fields, graph, tools  # noqa: E402


class CurveSamplingCoreTests(unittest.TestCase):
    def test_polyline_combina_tres_series_sin_ocultar_remuestreo(self):
        x = fields.ScalarSeries((0.0, 100.0, 200.0), "x")
        y = fields.ScalarSeries((0.0, 80.0, 0.0), "y")
        z = fields.ScalarSeries((0.0, 20.0, 60.0), "z")

        result = curve_sampling_core.polyline_points(x, y, z)

        self.assertEqual(result["points"], (
            (0.0, 0.0, 0.0), (100.0, 80.0, 20.0), (200.0, 0.0, 60.0)))
        self.assertGreater(result["length"], 200.0)

    def test_polyline_rechaza_series_desparejas_coincidentes_y_no_finitas(self):
        two = fields.ScalarSeries((0.0, 1.0))
        three = fields.ScalarSeries((0.0, 1.0, 2.0))
        repeated = fields.ScalarSeries((0.0, 0.0))
        infinite = fields.ScalarSeries((0.0, math.inf))

        self.assertIn("error", curve_sampling_core.polyline_points(two, two, three))
        self.assertIn("error", curve_sampling_core.polyline_points(repeated, repeated, repeated))
        self.assertIn("error", curve_sampling_core.polyline_points(two, two, infinite))
        self.assertIn("error", curve_sampling_core.polyline_points(None, two, two))

    def test_resample_usa_longitud_incluye_extremos_y_elimina_duplicados(self):
        result = curve_sampling_core.resample_points(
            ((0, 0, 0), (10, 0, 0), (10, 0, 0), (100, 0, 0)), count=6)

        self.assertEqual(result["points"], tuple((float(x), 0.0, 0.0) for x in range(0, 101, 20)))
        self.assertEqual(result["spacing"], 20.0)
        self.assertEqual(result["points"][0], (0.0, 0.0, 0.0))
        self.assertEqual(result["points"][-1], (100.0, 0.0, 0.0))

    def test_resample_rechaza_limites_y_curva_degenerada(self):
        line = ((0.0, 0.0, 0.0), (1.0, 0.0, 0.0))
        self.assertIn("error", curve_sampling_core.resample_points(line, count=1))
        self.assertIn("error", curve_sampling_core.resample_points(line, count=4097))
        self.assertIn("error", curve_sampling_core.resample_points((line[0], line[0]), count=2))

    def test_smooth_reduce_quiebres_preserva_extremos_y_no_muta(self):
        source = ((0.0, 0.0, 0.0), (100.0, 180.0, 0.0), (200.0, -160.0, 0.0),
                  (300.0, 170.0, 0.0), (400.0, 0.0, 0.0))

        result = curve_sampling_core.smooth_points(
            source, iterations=3, strength=0.5, preserve_ends=True)["points"]

        def roughness(points):
            return sum(math.dist(
                points[index],
                tuple((points[index - 1][axis] + points[index + 1][axis]) * 0.5
                      for axis in range(3)),
            ) for index in range(1, len(points) - 1))

        self.assertLess(roughness(result), roughness(source) * 0.25)
        self.assertEqual(result[0], source[0])
        self.assertEqual(result[-1], source[-1])
        self.assertEqual(len(result), len(source))
        self.assertEqual(source[1], (100.0, 180.0, 0.0))

    def test_smooth_rechaza_dominio_y_puede_liberar_extremos(self):
        source = ((0.0, 0.0, 0.0), (100.0, 100.0, 0.0), (200.0, 0.0, 0.0))
        free = curve_sampling_core.smooth_points(
            source, iterations=1, strength=1.0, preserve_ends=False)["points"]
        self.assertNotEqual(free[0], source[0])
        for params in ({"iterations": 0}, {"iterations": 65}, {"strength": 0.0},
                       {"strength": 1.01}):
            with self.subTest(params=params):
                self.assertIn("error", curve_sampling_core.smooth_points(source, **params))

    def test_fuse_collinear_quita_rectas_y_colocalizados_sin_comerse_esquinas(self):
        source = ((0.0, 0.0, 0.0), (25.0, 0.0, 0.0), (50.0, 0.0, 0.0),
                  (50.001, 0.001, 0.0), (50.0, 40.0, 0.0), (50.0, 80.0, 0.0))

        result = curve_sampling_core.fuse_collinear_points(
            source, angle_tolerance=0.1, distance_tolerance=0.01)

        self.assertEqual(result["points"], (
            (0.0, 0.0, 0.0), (50.0, 0.0, 0.0), (50.0, 80.0, 0.0)))
        self.assertEqual(result["removed"], 3)
        self.assertEqual(result["points"][0], source[0])
        self.assertEqual(result["points"][-1], source[-1])

    def test_fuse_collinear_respeta_umbral_y_rechaza_dominio(self):
        bent = ((0.0, 0.0, 0.0), (100.0, 0.0, 0.0), (200.0, 5.0, 0.0))
        strict = curve_sampling_core.fuse_collinear_points(
            bent, angle_tolerance=1.0, distance_tolerance=0.0)
        permissive = curve_sampling_core.fuse_collinear_points(
            bent, angle_tolerance=3.0, distance_tolerance=0.0)
        self.assertEqual(len(strict["points"]), 3)
        self.assertEqual(len(permissive["points"]), 2)
        for params in ({"angle_tolerance": -0.1}, {"angle_tolerance": 91.0},
                       {"distance_tolerance": -0.1}):
            with self.subTest(params=params):
                self.assertIn("error", curve_sampling_core.fuse_collinear_points(bent, **params))

    def test_fuse_collinear_admite_recorridos_cerrados(self):
        square = ((0.0, 0.0, 0.0), (50.0, 0.0, 0.0), (100.0, 0.0, 0.0),
                  (100.0, 100.0, 0.0), (0.0, 100.0, 0.0), (0.0, 0.0, 0.0))
        result = curve_sampling_core.fuse_collinear_points(square, angle_tolerance=0.1)
        self.assertEqual(result["points"], (
            (0.0, 0.0, 0.0), (100.0, 0.0, 0.0), (100.0, 100.0, 0.0),
            (0.0, 100.0, 0.0), (0.0, 0.0, 0.0)))

    def test_subdivide_por_distancia_conserva_vertices_y_cota_segmentos(self):
        source = ((0.0, 0.0, 0.0), (100.0, 0.0, 0.0), (100.0, 60.0, 0.0))

        result = curve_sampling_core.subdivide_points(
            source, mode="distance", distance=30.0, count=1)

        self.assertEqual(len(result["points"]), 7)
        self.assertIn(source[1], result["points"])
        self.assertEqual(result["points"][0], source[0])
        self.assertEqual(result["points"][-1], source[-1])
        self.assertLessEqual(result["max_segment"], 30.0)
        self.assertEqual(result["inserted"], 4)

    def test_subdivide_por_cantidad_y_rechaza_explosion(self):
        source = ((0.0, 0.0, 0.0), (90.0, 0.0, 0.0), (90.0, 60.0, 0.0))
        result = curve_sampling_core.subdivide_points(
            source, mode="count", distance=100.0, count=2)
        self.assertEqual(len(result["points"]), 7)
        self.assertIn(source[1], result["points"])
        self.assertIn("error", curve_sampling_core.subdivide_points(
            source, mode="otro", distance=100.0, count=1))
        self.assertIn("error", curve_sampling_core.subdivide_points(
            source, mode="count", distance=100.0, count=0))
        huge = tuple((float(index), 0.0, 0.0) for index in range(66))
        self.assertIn("error", curve_sampling_core.subdivide_points(
            huge, mode="count", distance=100.0, count=64))

    def test_resample_preserva_metadata_de_cada_curva_treegen(self):
        source = curve.CurveSet((
            curve.CurvePath(((0, 0, 0), (100, 0, 0)), scale=0.5, seed=17,
                            source_parent_index=3, parent_radius=8.0),
            curve.CurvePath(((0, 20, 0), (0, 120, 0)), scale=0.25, seed=19,
                            source_parent_index=4, parent_radius=4.0),
        ))

        result = curve.resample(source, count=5)["curve"]

        self.assertIsInstance(result, curve.CurveSet)
        self.assertEqual([len(path.points) for path in result.paths], [5, 5])
        self.assertEqual(result.paths[0].scale, 0.5)
        self.assertEqual(result.paths[0].seed, 17)
        self.assertEqual(result.paths[0].source_parent_index, 3)
        self.assertEqual(result.paths[0].parent_radius, 8.0)

        smoothed = curve.smooth(source, iterations=2, strength=0.4)["curve"]
        self.assertIsInstance(smoothed, curve.CurveSet)
        self.assertEqual(smoothed.paths[0].scale, 0.5)
        self.assertEqual(smoothed.paths[0].seed, 17)
        self.assertEqual(smoothed.paths[0].source_parent_index, 3)
        self.assertEqual(smoothed.paths[0].parent_radius, 8.0)

        fused = curve.fuse_collinear(source, angle_tolerance=1.0)["curve"]
        subdivided = curve.subdivide(source, mode="count", count=1)["curve"]
        for transformed in (fused, subdivided):
            self.assertIsInstance(transformed, curve.CurveSet)
            self.assertEqual(transformed.paths[0].scale, 0.5)
            self.assertEqual(transformed.paths[0].seed, 17)
            self.assertEqual(transformed.paths[0].source_parent_index, 3)
            self.assertEqual(transformed.paths[0].parent_radius, 8.0)


class CurveSamplingGraphTests(unittest.TestCase):
    VERBS = ("series_range", "graph_curve", "curve_polyline", "curve_fuse_collinear",
             "curve_subdivide", "curve_smooth", "curve_resample")

    def tearDown(self):
        for verb in self.VERBS:
            tools.limpiar_asset_producido_runtime(verb)

    def _graph(self):
        diagram = graph.JamGraph()
        diagram.add("series_range", {"start": 0.0, "end": 600.0, "count": 7}, nid="x")
        diagram.add("graph_curve", {
            "start_value": 0.0, "end_value": 0.0, "shape": "custom", "power": 2.0,
            "midpoint": 0.5, "mid_value": 220.0, "samples": 7,
        }, nid="y")
        diagram.add("graph_curve", {
            "start_value": 0.0, "end_value": 140.0, "shape": "smooth", "power": 2.0,
            "midpoint": 0.5, "mid_value": 70.0, "samples": 7,
        }, nid="z")
        diagram.add("curve_polyline", {"x": "", "y": "", "z": ""}, nid="polyline")
        diagram.add("curve_fuse_collinear", {
            "angle_tolerance": 0.1, "distance_tolerance": 0.01, "samples": 32,
        }, nid="fuse")
        diagram.add("curve_subdivide", {
            "mode": "count", "distance": 100.0, "count": 1, "samples": 32,
        }, nid="subdivide")
        diagram.add("curve_smooth", {
            "iterations": 3, "strength": 0.45, "preserve_ends": True, "samples": 32,
        }, nid="smooth")
        diagram.add("curve_resample", {"count": 25, "samples": 32}, nid="resample")
        diagram.connect("x", "polyline", "x")
        diagram.connect("y", "polyline", "y")
        diagram.connect("z", "polyline", "z")
        diagram.connect("polyline", "fuse")
        diagram.connect("fuse", "subdivide")
        diagram.connect("subdivide", "smooth")
        diagram.connect("smooth", "resample")
        return diagram

    def test_spec_publica_pines_nombrados_y_cadena_s_a_s(self):
        spec = {item["verbo"]: item for item in json.loads(api.spec_all())["tools"]}
        polyline, fuse, subdivide, smooth, resample = (
            spec["curve_polyline"], spec["curve_fuse_collinear"],
            spec["curve_subdivide"], spec["curve_smooth"], spec["curve_resample"])
        self.assertTrue(polyline["source"])
        self.assertEqual(
            {item["nombre"]: item["data_type"] for item in polyline["params"]},
            {"x": "N[]", "y": "N[]", "z": "N[]"},
        )
        self.assertEqual(polyline["out_name"], "S")
        self.assertEqual(polyline["grupo"], "Curvas")
        self.assertEqual(fuse["in_name"], "S")
        self.assertEqual(fuse["out_name"], "S")
        self.assertEqual(subdivide["in_name"], "S")
        self.assertEqual(subdivide["out_name"], "S")
        self.assertEqual(smooth["in_name"], "S")
        self.assertEqual(smooth["out_name"], "S")
        self.assertEqual(smooth["grupo"], "Curvas")
        self.assertEqual(resample["in_name"], "S")
        self.assertEqual(resample["out_name"], "S")
        self.assertEqual(resample["grupo"], "Curvas")

    def test_compile_y_runtime_encadenan_series_polyline_y_resample(self):
        diagram = self._graph()

        compiled = json.loads(api.compile_graph_json(diagram.to_json()))
        self.assertTrue(compiled["ok"], compiled)
        report, states = graph.ejecutar_detalle(diagram)
        self.assertEqual(states["polyline"]["estado"], "ok", report)
        self.assertEqual(states["fuse"]["estado"], "ok", report)
        self.assertEqual(states["subdivide"]["estado"], "ok", report)
        self.assertEqual(states["smooth"]["estado"], "ok", report)
        self.assertEqual(states["resample"]["estado"], "ok", report)
        output = tools.dato_producido_runtime("curve_resample")
        fused = tools.dato_producido_runtime("curve_fuse_collinear")
        subdivided = tools.dato_producido_runtime("curve_subdivide")
        self.assertIsInstance(fused, curve.CurvePath)
        self.assertIsInstance(subdivided, curve.CurvePath)
        self.assertGreater(len(subdivided.points), len(fused.points))
        self.assertIsInstance(output, curve.CurvePath)
        self.assertEqual(len(output.points), 25)
        self.assertEqual(output.points[0], (0.0, 0.0, 0.0))
        self.assertEqual(output.points[-1], (600.0, 0.0, 140.0))

    def test_compile_exige_los_tres_pines_y_rechaza_tipo_incompatible(self):
        missing = graph.JamGraph()
        missing.add("series_range", {}, nid="x")
        missing.add("curve_polyline", {"x": "", "y": "", "z": ""}, nid="polyline")
        missing.connect("x", "polyline", "x")
        result = json.loads(api.compile_graph_json(missing.to_json()))
        self.assertFalse(result["ok"])
        self.assertIn("requiere conexión N[] en «y»", result["nodes"]["polyline"]["texto"])

        wrong = graph.JamGraph()
        wrong.add("number", {"name": "x", "value": 1.0}, nid="number")
        wrong.add("curve_polyline", {"x": "", "y": "", "z": ""}, nid="polyline")
        wrong.connect("number", "polyline", "x")
        result = json.loads(api.compile_graph_json(wrong.to_json()))
        self.assertFalse(result["ok"])
        self.assertIn("x esperaba N[], recibió N", result["nodes"]["polyline"]["texto"])


if __name__ == "__main__":
    unittest.main()
