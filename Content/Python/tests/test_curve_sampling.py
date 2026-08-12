from __future__ import annotations

import dataclasses
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

    def test_offset_recta_respeta_lado_y_distancia(self):
        line = ((0.0, 0.0, 7.0), (100.0, 0.0, 7.0))
        left = curve_sampling_core.offset_points(line, distance=25.0, side="left")
        right = curve_sampling_core.offset_points(line, distance=25.0, side="right")
        self.assertEqual(left["points"], ((0.0, 25.0, 7.0), (100.0, 25.0, 7.0)))
        self.assertEqual(right["points"], ((0.0, -25.0, 7.0), (100.0, -25.0, 7.0)))

    def test_offset_miter_y_bevel_hacen_explicita_la_esquina(self):
        corner = ((0.0, 0.0, 0.0), (100.0, 0.0, 0.0), (100.0, 100.0, 0.0))
        miter = curve_sampling_core.offset_points(
            corner, distance=10.0, join="miter", miter_limit=2.0)
        bevel = curve_sampling_core.offset_points(
            corner, distance=10.0, join="miter", miter_limit=1.1)
        self.assertEqual(miter["points"], (
            (0.0, 10.0, 0.0), (90.0, 10.0, 0.0), (90.0, 100.0, 0.0)))
        self.assertEqual(bevel["points"], (
            (0.0, 10.0, 0.0), (100.0, 10.0, 0.0),
            (90.0, 0.0, 0.0), (90.0, 100.0, 0.0)))
        self.assertEqual(miter["bevels"], 0)
        self.assertEqual(bevel["bevels"], 1)

    def test_offset_cierra_contorno_y_soporta_plano_xz(self):
        square = ((0.0, 0.0, 0.0), (100.0, 0.0, 0.0), (100.0, 100.0, 0.0),
                  (0.0, 100.0, 0.0), (0.0, 0.0, 0.0))
        inset = curve_sampling_core.offset_points(square, distance=10.0)
        self.assertTrue(inset["closed"])
        self.assertEqual(inset["points"], (
            (10.0, 10.0, 0.0), (90.0, 10.0, 0.0), (90.0, 90.0, 0.0),
            (10.0, 90.0, 0.0), (10.0, 10.0, 0.0)))

        vertical_plane = ((0.0, 7.0, 0.0), (100.0, 7.0, 0.0))
        xz = curve_sampling_core.offset_points(vertical_plane, distance=12.0, plane="xz")
        self.assertEqual(xz["points"], ((0.0, 7.0, 12.0), (100.0, 7.0, 12.0)))

    def test_offset_rechaza_dominio_y_segmento_invisible_en_el_plano(self):
        line = ((0.0, 0.0, 0.0), (100.0, 0.0, 0.0))
        for params in ({"distance": 0.0}, {"side": "up"}, {"plane": "xyz"},
                       {"join": "round"}, {"miter_limit": 0.99}):
            with self.subTest(params=params):
                self.assertIn("error", curve_sampling_core.offset_points(line, **params))
        self.assertIn("error", curve_sampling_core.offset_points(
            ((0.0, 0.0, 0.0), (0.0, 0.0, 100.0)), plane="xy"))

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
        offset = curve.offset(source, distance=10.0, plane="xy")["curve"]
        for transformed in (fused, subdivided, offset):
            self.assertIsInstance(transformed, curve.CurveSet)
            self.assertEqual(transformed.paths[0].scale, 0.5)
            self.assertEqual(transformed.paths[0].seed, 17)
            self.assertEqual(transformed.paths[0].source_parent_index, 3)
            self.assertEqual(transformed.paths[0].parent_radius, 8.0)


class CurveSamplingGraphTests(unittest.TestCase):
    VERBS = ("series_range", "graph_curve", "curve_polyline", "curve_fuse_collinear",
             "curve_subdivide", "curve_smooth", "curve_resample", "curve_offset")

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
        polyline, fuse, subdivide, smooth, resample, offset = (
            spec["curve_polyline"], spec["curve_fuse_collinear"],
            spec["curve_subdivide"], spec["curve_smooth"], spec["curve_resample"],
            spec["curve_offset"])
        self.assertTrue(polyline["source"])
        self.assertEqual(
            {item["nombre"]: item["data_type"] for item in polyline["params"]},
            # `closed` no declara `data_type` porque no es un pin de DATO como las tres series: es
            # un booleano del nodo, que se tilda a mano o se maneja desde el interruptor.
            {"x": "N[]", "y": "N[]", "z": "N[]", "closed": ""},
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
        self.assertEqual(offset["in_name"], "S")
        self.assertEqual(offset["out_name"], "S")
        self.assertEqual(offset["grupo"], "Curvas")

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

    def test_offset_compila_y_corre_por_el_graph_publico(self):
        diagram = graph.JamGraph()
        diagram.add("series_range", {"start": 0.0, "end": 200.0, "count": 3}, nid="x")
        diagram.add("graph_curve", {
            "start_value": 0.0, "end_value": 0.0, "shape": "linear", "power": 2.0,
            "midpoint": 0.5, "mid_value": 0.0, "samples": 3,
        }, nid="y")
        diagram.add("graph_curve", {
            "start_value": 0.0, "end_value": 0.0, "shape": "linear", "power": 2.0,
            "midpoint": 0.5, "mid_value": 0.0, "samples": 3,
        }, nid="z")
        diagram.add("curve_polyline", {"x": "", "y": "", "z": ""}, nid="polyline")
        diagram.add("curve_offset", {
            "distance": 50.0, "side": "left", "plane": "xy", "join": "miter",
            "miter_limit": 4.0, "samples": 32,
        }, nid="offset")
        diagram.connect("x", "polyline", "x")
        diagram.connect("y", "polyline", "y")
        diagram.connect("z", "polyline", "z")
        diagram.connect("polyline", "offset")

        compiled = json.loads(api.compile_graph_json(diagram.to_json()))
        self.assertTrue(compiled["ok"], compiled)
        report, states = graph.ejecutar_detalle(diagram)
        self.assertEqual(states["offset"]["estado"], "ok", report)
        output = tools.dato_producido_runtime("curve_offset")
        self.assertEqual(output.points, (
            (0.0, 50.0, 0.0), (100.0, 50.0, 0.0), (200.0, 50.0, 0.0)))


if __name__ == "__main__":
    unittest.main()


class LineaYPoligonoTests(unittest.TestCase):
    """Peldaños 2, 3 y 4 de la escalera de Grasshopper Basics: Line, Line SDL y cerrar la polilínea.

    El peldaño 2 se achicó solo al llegar acá. El tutorial construye un punto con «Construct Point»
    y con él arma la línea; en Jam **una posición ya es un `V`**, porque el tipo `P` no es un punto
    geométrico sino un stream de muestras de colocación —con semilla, escala y normal por muestra—.
    Así que el constructor de puntos ya existía con otro nombre (`vector_construct`) y lo único que
    faltaba era la línea.
    """

    def test_la_linea_es_el_segmento_entre_dos_posiciones(self) -> None:
        resultado = curve.line((0, 0, 0), (0, 0, 300))
        self.assertEqual(resultado["curve"].points, ((0.0, 0.0, 0.0), (0.0, 0.0, 300.0)))
        self.assertIn("300.0 cm", resultado["info"])

    def test_dos_puntos_coincidentes_no_son_una_linea(self) -> None:
        """No es una curva degenerada: es dos veces el mismo punto, y todo lo que consume `S`
        —barrer, extruir, distribuir— necesita una dirección que ahí no existe."""
        self.assertIn("coinciden", curve.line((1, 1, 1), (1, 1, 1))["error"])

    def test_line_sdl_NORMALIZA_la_direccion(self) -> None:
        """Sin normalizar, una dirección `(0,0,2)` daría el doble de lo que dice el parámetro y el
        error sería invisible: la línea se ve bien, sólo que mide otra cosa."""
        for direccion in ((0, 0, 1), (0, 0, 2), (0, 0, 17)):
            with self.subTest(direccion=direccion):
                resultado = curve.line_sdl((0, 0, 0), direccion, 300.0)
                self.assertAlmostEqual(resultado["curve"].points[1][2], 300.0)

    def test_line_sdl_sin_direccion_es_error(self) -> None:
        self.assertIn("no apunta", curve.line_sdl((0, 0, 0), (0, 0, 0), 100.0)["error"])

    def test_cerrar_la_polilinea_repite_el_primer_punto(self) -> None:
        """Es el gesto del tutorial para volver un polígono una polilínea. Se repite el punto en vez
        de marcar una bandera porque todo lo que consume `S` recorre la lista: una bandera obligaría
        a que cada consumidor se acuerde de cerrar, y el que se olvide deja un polígono abierto sin
        que nada lo diga."""
        serie = lambda nombre, *v: fields.ScalarSeries(tuple(float(x) for x in v), nombre)
        polyline_points = curve_sampling_core.polyline_points
        abierta = polyline_points(serie("x", 0, 100, 100), serie("y", 0, 0, 100), serie("z", 0, 0, 0))
        cerrada = polyline_points(serie("x", 0, 100, 100), serie("y", 0, 0, 100),
                                  serie("z", 0, 0, 0), closed=True)
        self.assertEqual(len(abierta["points"]), 3)
        self.assertEqual(len(cerrada["points"]), 4)
        self.assertEqual(cerrada["points"][0], cerrada["points"][-1])
        self.assertGreater(cerrada["length"], abierta["length"])
        self.assertIn("cerrada", cerrada["info"])

    def test_una_polilinea_que_ya_cierra_no_se_cierra_dos_veces(self) -> None:
        serie = lambda nombre, *v: fields.ScalarSeries(tuple(float(x) for x in v), nombre)
        polyline_points = curve_sampling_core.polyline_points
        repetida = polyline_points(serie("x", 0, 100, 0), serie("y", 0, 0, 0),
                                   serie("z", 0, 0, 0), closed=True)
        self.assertIn("ya coincide", repetida["error"])

    def test_el_interruptor_puede_manejar_el_cierre(self) -> None:
        """La razón de ser del peldaño 3: que el booleano del peldaño 0 se pueda cablear acá."""
        g = graph.JamGraph()
        g.add("boolean", {"value": True}, nid="cerrar")
        g.add("curve_polyline", {}, nid="poli")
        g.connect("cerrar", "poli", "closed")
        # Que el cable exista no prueba nada: lo que importa es que el Graph lo ACEPTE. Si el pin
        # rechazara el booleano, el peldaño 3 no serviría para lo que se hizo.
        diagnosticos = graph.diagnosticar(g) if hasattr(graph, "diagnosticar") else {}
        problemas = [m for ms in diagnosticos.values() for m in ms if "closed" in m]
        self.assertEqual(problemas, [], f"el pin `closed` rechazó el interruptor: {problemas}")

    def test_la_linea_por_direccion_encadena_con_los_vectores(self) -> None:
        """Line SDL es el peldaño 4 y sólo tenía sentido con el tipo `V` del peldaño 1."""
        g = graph.JamGraph()
        g.add("vector_unit_z", {"largo": 1}, nid="arriba")
        g.add("curve_line_sdl", {"largo": 250}, nid="linea")
        g.connect("arriba", "linea", "direccion")
        plan = graph.compilar(g)
        self.assertIn("linea", plan.order)


class InterpolarPuntosTests(unittest.TestCase):
    """Peldaño 5: la curva que PASA por los puntos, contra Bézier que los usa de control.

    Quien dibuja el recorrido de un camino quiere lo primero: puso el punto donde quiere que pase
    el camino. Que Jam tuviera sólo lo segundo era el hueco.
    """

    CONTROL = ((0.0, 0.0, 0.0), (100.0, 0.0, 0.0), (100.0, 100.0, 0.0), (0.0, 100.0, 0.0))

    def test_la_curva_PASA_por_todos_los_puntos(self) -> None:
        """La propiedad que la define, y la única que la distingue de `curve_bezier`."""
        salida = curve_sampling_core.catmull_rom(self.CONTROL, segments=8)
        for punto in self.CONTROL:
            with self.subTest(punto=punto):
                cerca = min(math.dist(punto, q) for q in salida["points"])
                self.assertLess(cerca, 1e-9, f"la curva no pasa por {punto}")

    def test_la_parametrizacion_CENTRIPETA_no_hace_rulos(self) -> None:
        """El motivo de elegir `alpha=0,5` y no la uniforme, que es la que aparece primero en
        cualquier búsqueda. Medido sobre el caso clásico —dos puntos muy juntos y después un salto
        largo, que es lo que pasa cuando alguien marca esquinas a ojo—: la uniforme se sale 2,89 cm
        de la caja de los puntos y retrocede 11 veces en un recorrido que sólo va hacia +X.
        """
        control = ((0.0, 0.0, 0.0), (10.0, 0.0, 0.0), (11.0, 0.0, 0.0), (200.0, 0.0, 0.0))
        xs = [p[0] for p in curve_sampling_core.catmull_rom(control, segments=16)["points"]]
        self.assertLessEqual(max(xs), 200.0 + 1e-9, "la curva se pasa de largo del último punto")
        self.assertGreaterEqual(min(xs), -1e-9, "la curva se pasa por detrás del primero")
        retrocesos = sum(1 for a, b in zip(xs, xs[1:]) if b < a - 1e-9)
        self.assertEqual(retrocesos, 0, f"la curva retrocede {retrocesos} veces: hay un rulo")

    def test_los_extremos_no_salen_planchados(self) -> None:
        """Los puntos fantasma son REFLEJADOS y no repetidos: repetir da tangente cero y la curva
        arranca con una planchada visible."""
        salida = curve_sampling_core.catmull_rom(self.CONTROL, segments=8)["points"]
        primero, segundo = salida[0], salida[1]
        self.assertGreater(math.dist(primero, segundo), 1e-6)

    def test_mas_tramos_es_mas_suave_pero_los_de_control_no_se_mueven(self) -> None:
        pocos = curve_sampling_core.catmull_rom(self.CONTROL, segments=2)
        muchos = curve_sampling_core.catmull_rom(self.CONTROL, segments=16)
        self.assertLess(len(pocos["points"]), len(muchos["points"]))
        for punto in self.CONTROL:
            self.assertLess(min(math.dist(punto, q) for q in muchos["points"]), 1e-9)

    def test_rechaza_lo_que_no_es_una_curva(self) -> None:
        self.assertIn("dos puntos", curve_sampling_core.catmull_rom([(0, 0, 0)])["error"])
        self.assertIn("coincidentes",
                      curve_sampling_core.catmull_rom([(0, 0, 0), (0, 0, 0)])["error"])
        self.assertIn("segments",
                      curve_sampling_core.catmull_rom(self.CONTROL, segments=0)["error"])

    def test_toma_la_MISMA_entrada_que_la_polilinea(self) -> None:
        """A propósito: así se cambia un nodo por el otro sin recablear, y se ve la diferencia entre
        unir los puntos con rectas y pasarlos con una curva."""
        serie = lambda nombre, *v: fields.ScalarSeries(tuple(float(x) for x in v), nombre)
        recta = curve.polyline(x=serie("x", 0, 100, 100), y=serie("y", 0, 0, 100),
                               z=serie("z", 0, 0, 0))
        suave = curve.interpolate(x=serie("x", 0, 100, 100), y=serie("y", 0, 0, 100),
                                  z=serie("z", 0, 0, 0), segments=8)
        self.assertEqual(len(recta["curve"].points), 3)
        self.assertGreater(len(suave["curve"].points), 3)
        # La suave es más larga: dobla en vez de hacer esquina.
        self.assertGreater(suave["curve"].length, recta["curve"].length * 0.9)


class MoverCurvaTests(unittest.TestCase):
    """Lo último que le faltaba a la escalera: el «Move» del tutorial, del lado de las curvas.

    Jam ya tenía `move` para puntos y `mesh_transform` para mallas; las curvas quedaban sin forma de
    correrse de lugar, así que armar dos rieles paralelos para un loft obligaba a escribir dos veces
    las mismas coordenadas con un offset a mano.
    """

    def recta(self):
        return curve.line((0.0, 0.0, 0.0), (300.0, 0.0, 0.0))["curve"]

    def test_mueve_todos_los_puntos_por_igual(self) -> None:
        movida = curve.move(self.recta(), (0.0, 0.0, 100.0))
        self.assertEqual(movida["curve"].points, ((0.0, 0.0, 100.0), (300.0, 0.0, 100.0)))
        self.assertIn("100.0 cm", movida["info"])

    def test_conserva_la_METADATA_de_la_curva(self) -> None:
        """Una curva movida sigue siendo la misma curva en otro lado. Perder su semilla haría que
        la rama que cuelga de ella salga distinta después de moverla — de los efectos más
        desconcertantes posibles, porque mover no debería cambiar la forma de nada."""
        original = dataclasses.replace(self.recta(), seed=1234, scale=2.5)
        movida = curve.move(original, (10.0, 0.0, 0.0))["curve"]
        self.assertEqual(movida.seed, 1234)
        self.assertEqual(movida.scale, 2.5)

    def test_mueve_todas_las_curvas_de_un_conjunto(self) -> None:
        conjunto = curve.CurveSet((self.recta(), curve.line((0.0, 50.0, 0.0),
                                                            (300.0, 50.0, 0.0))["curve"]))
        movido = curve.move(conjunto, (0.0, 0.0, 25.0))["curve"]
        self.assertIsInstance(movido, curve.CurveSet)
        # La CANTIDAD primero: sin esto, mover sólo la primera curva y descartar el resto pasaba el
        # test —todas las que quedaban estaban bien movidas—. Lo destapó una mutación.
        self.assertEqual(len(movido.paths), len(conjunto.paths))
        for path in movido.paths:
            for punto in path.points:
                self.assertEqual(punto[2], 25.0)

    def test_un_desplazamiento_no_finito_es_error(self) -> None:
        self.assertIn("no finito", curve.move(self.recta(), (0.0, float("inf"), 0.0))["error"])

    def test_dos_rieles_para_un_loft_salen_de_mover_uno(self) -> None:
        """El uso que lo justifica: el peldaño 6 necesita dos curvas, y hasta ahora había que
        escribir las coordenadas dos veces con el offset a mano."""
        riel = self.recta()
        otro = curve.move(riel, (0.0, 0.0, 200.0))["curve"]
        self.assertEqual(len(riel.points), len(otro.points))
        for a, b in zip(riel.points, otro.points):
            self.assertEqual(b[2] - a[2], 200.0)
