"""Ayudantes visuales: ver un stream en vez de sólo medirlo."""

from __future__ import annotations

import math
import sys
import types
import unittest

_unreal_fake = sys.modules.setdefault("unreal", types.ModuleType("unreal"))
if not hasattr(_unreal_fake, "TopLevelAssetPath"):
    _unreal_fake.TopLevelAssetPath = lambda package, name: (package, name)

from jam import curve, debug, scatter_core, tools  # noqa: E402


def frames(n=3, *, escalas=None):
    return curve.FrameSet(tuple(
        curve.CurveFrame(
            (float(i) * 100.0, 0.0, 0.0), (0.0, 0.0, 1.0), (1.0, 0.0, 0.0),
            i / max(n - 1, 1), local_index=i,
            scale=1.0 if escalas is None else escalas[i],
        )
        for i in range(n)
    ), parent_count=1)


def puntos(pesos):
    from jam.geometry import Vec3
    return [
        scatter_core.Sample(pos=Vec3(float(i) * 50.0, 0.0, 0.0), normal=Vec3(0.0, 0.0, 1.0),
                            slope=0.0, seed=i, uv=(0.0, 0.0), weight=w)
        for i, w in enumerate(pesos)
    ]


class EjesTests(unittest.TestCase):
    def test_three_axes_per_frame_follow_the_frame_basis(self):
        ejes = debug.ejes_de_frames(frames(2).frames, largo=10.0)

        self.assertEqual(len(ejes), 6)
        primero = [e for e in ejes if e.origen == (0.0, 0.0, 0.0)]
        self.assertEqual(len(primero), 3)
        por_eje = {e.eje: e for e in primero}
        # X = tangente, Z = outward, Y = el lateral que los cierra. Es la misma convención que usa
        # `make_rot_from_xz` en los verbos de malla, para que lo que se ve sea lo que se orienta.
        self.assertEqual(por_eje[0].direccion, (0.0, 0.0, 1.0))
        self.assertEqual(por_eje[2].direccion, (1.0, 0.0, 0.0))
        producto = sum(a * b for a, b in zip(por_eje[1].direccion, por_eje[0].direccion))
        self.assertAlmostEqual(producto, 0.0, places=6)

    def test_the_axis_length_follows_the_frame_scale(self):
        """Ver la escala es la mitad del valor: se nota si cae en cascada o si la maneja una máscara."""
        ejes = debug.ejes_de_frames(frames(3, escalas=[0.5, 1.0, 2.0]).frames, largo=10.0)
        tangentes = [e.largo for e in ejes if e.eje == 0]
        self.assertEqual(tangentes, [5.0, 10.0, 20.0])

        fijos = debug.ejes_de_frames(frames(3, escalas=[0.5, 1.0, 2.0]).frames,
                                     largo=10.0, escalar_con_frame=False)
        self.assertEqual({e.largo for e in fijos if e.eje == 0}, {10.0})

    def test_only_tangent_mode_draws_one_axis(self):
        ejes = debug.ejes_de_frames(frames(4).frames, solo_tangente=True)
        self.assertEqual(len(ejes), 4)
        self.assertEqual({e.eje for e in ejes}, {0})

    def test_a_degenerate_basis_still_produces_perpendicular_axes(self):
        # tangente y outward paralelos: hay que elegir una perpendicular estable en vez de fallar.
        roto = curve.FrameSet((curve.CurveFrame(
            (0.0, 0.0, 0.0), (0.0, 0.0, 1.0), (0.0, 0.0, 1.0), 0.0),), parent_count=1)
        ejes = debug.ejes_de_frames(roto.frames, largo=10.0)
        self.assertEqual(len(ejes), 3)
        direcciones = {e.eje: e.direccion for e in ejes}
        for a, b in ((0, 1), (0, 2), (1, 2)):
            producto = sum(x * y for x, y in zip(direcciones[a], direcciones[b]))
            self.assertAlmostEqual(producto, 0.0, places=6, msg=f"ejes {a} y {b} no perpendiculares")

    def test_it_validates_its_input(self):
        with self.assertRaises(ValueError):
            debug.ejes_de_frames([])
        with self.assertRaises(ValueError):
            debug.ejes_de_frames(frames(2).frames, largo=0.0)
        # Un frame sin tangente no se puede dibujar; si no queda ninguno, se avisa.
        sin_tangente = curve.FrameSet((curve.CurveFrame(
            (0.0, 0.0, 0.0), (0.0, 0.0, 0.0), (1.0, 0.0, 0.0), 0.0),), parent_count=1)
        with self.assertRaises(ValueError):
            debug.ejes_de_frames(sin_tangente.frames)
        with self.assertRaises(ValueError):
            debug.ejes_de_frames(frames(2000).frames)


class MarcadoresTests(unittest.TestCase):
    def test_the_mask_weight_becomes_the_marker_size(self):
        ms = debug.marcadores_de_puntos(puntos([1.0, 0.5, 0.25]), tamano=20.0)
        self.assertEqual([m.tamano for m in ms], [20.0, 10.0, 5.0])
        # El peso original se conserva para poder reportarlo aunque el tamaño esté acotado.
        self.assertEqual([m.peso for m in ms], [1.0, 0.5, 0.25])

    def test_a_zero_weight_point_stays_visible(self):
        """Distinguir «la máscara lo apagó» de «nunca estuvo» es justamente para lo que sirve."""
        ms = debug.marcadores_de_puntos(puntos([0.0]), tamano=20.0, minimo=0.15)
        self.assertAlmostEqual(ms[0].tamano, 3.0)
        self.assertGreater(ms[0].tamano, 0.0)
        self.assertEqual(ms[0].peso, 0.0)

    def test_weights_above_one_do_not_blow_up_the_marker(self):
        ms = debug.marcadores_de_puntos(puntos([5.0]), tamano=20.0)
        self.assertEqual(ms[0].tamano, 20.0)

    def test_scaling_can_be_turned_off(self):
        ms = debug.marcadores_de_puntos(puntos([1.0, 0.2]), tamano=8.0, escalar_con_peso=False)
        self.assertEqual({m.tamano for m in ms}, {8.0})

    def test_it_validates_its_input(self):
        with self.assertRaises(ValueError):
            debug.marcadores_de_puntos([])
        with self.assertRaises(ValueError):
            debug.marcadores_de_puntos(puntos([1.0]), tamano=-1.0)
        with self.assertRaises(ValueError):
            debug.marcadores_de_puntos(puntos([1.0]), minimo=2.0)
        with self.assertRaises(ValueError):
            debug.marcadores_de_puntos([object()])


class ContratoDeGrafoTests(unittest.TestCase):
    def test_a_single_debug_verb_accepts_any_cable(self):
        """Un verbo por tipo obligaba a saber de antemano cuál conectar. Ahora es uno solo."""
        info = tools.REGISTRO["debug"]
        self.assertEqual(info["in_name"], "*")
        # Sale por M: se mergea, hornea o coloca como cualquier malla, y participa del
        # Preview/Discard sin necesitar un camino aparte.
        self.assertEqual(info["out_name"], "M")
        self.assertEqual(info["cat"], "Debug")
        self.assertTrue(info["graph_only"])
        self.assertFalse(info["asset_required"])
        # Los verbos tipados ya no existen: había que elegir entre ellos sin saber cuál.
        for viejo in ("debug_frames", "debug_points"):
            self.assertNotIn(viejo, tools.REGISTRO)

    def test_debug_has_its_own_tab(self):
        self.assertIn("Debug", tools.CATEGORIAS)

    def test_the_wildcard_accepts_every_stream_type_in_the_preflight(self):
        import json
        from unittest import mock
        from jam import api, graph

        # Cada tipo del grafo enchufado al mismo nodo de debug tiene que compilar.
        casos = {
            "P": {"verb": "pts_line", "params": {}},
            "S": {"verb": "curve_bezier", "params": {}},
            "N[]": {"verb": "graph_curve", "params": {}},
            "M": {"verb": "mesh_sphere", "params": {}},
        }
        for tipo, fuente in casos.items():
            with self.subTest(tipo=tipo):
                doc = {"nodes": {"src": dict(fuente, x=0, y=0),
                                 "ver": {"verb": "debug", "params": {}, "x": 300, "y": 0}},
                       "edges": [["src", "out", "ver", "in"]]}
                with mock.patch.object(graph, "_resolver_asset_runtime", side_effect=lambda p: p):
                    r = json.loads(api.compile_graph_json(json.dumps(doc)))
                self.assertTrue(r["ok"], f"{tipo}: {r['report']}")

    def test_the_wildcard_does_not_disable_the_rest_of_the_type_system(self):
        import json
        from unittest import mock
        from jam import api, graph

        # El comodín es del pin de Debug, no una amnistía general: los demás siguen exigiendo.
        doc = {"nodes": {"src": {"verb": "pts_line", "params": {}, "x": 0, "y": 0},
                         "pipe": {"verb": "mesh_pipe", "params": {}, "x": 300, "y": 0}},
               "edges": [["src", "out", "pipe", "in"]]}
        with mock.patch.object(graph, "_resolver_asset_runtime", side_effect=lambda p: p):
            r = json.loads(api.compile_graph_json(json.dumps(doc)))
        self.assertFalse(r["ok"])
        self.assertIn("esperaba S, recibió P", r["nodes"]["pipe"]["texto"])


class EjemplosCargablesTests(unittest.TestCase):
    """Todo ejemplo empaquetado tiene que poder ABRIRSE, no sólo compilar.

    `SJamGraphEditor::LoadGraphJson` valida cada arista por su cuenta antes de reemplazar el canvas.
    Esa regla vivía duplicada con la de `CanConnect`, así que agregar el comodín en una sola dejó el
    otro camino rechazando lo que la UI aceptaba: el ejemplo de Debug se armaba a mano pero no se
    podía abrir («edge 1 tiene pines o tipos incompatibles»). Este test recorre los mismos pasos que
    el cargador sobre cada archivo distribuido.
    """

    @staticmethod
    def _tipo_entrada_del_cargador(verb, pin, registro):
        from jam import graph
        info = registro.get(verb)
        if not info:
            return ""
        if pin == "in":
            return "" if info["source"] or info["aridad"] == 0 else info["in_name"]
        if pin == "asset":
            return "A" if info["asset_pin"] else ""
        return graph._tipo_entrada(verb, pin, registro) or ""

    def test_every_bundled_example_passes_the_loader_edge_check(self):
        import json
        from pathlib import Path
        from jam import graph

        ejemplos = sorted((Path(__file__).resolve().parents[3] / "Resources" / "Examples")
                          .glob("*.jamgraph"))
        self.assertGreaterEqual(len(ejemplos), 5)
        for ruta in ejemplos:
            with self.subTest(ejemplo=ruta.name):
                documento = json.loads(ruta.read_text(encoding="utf-8"))
                nodos = documento["nodes"]
                for indice, arista in enumerate(documento["edges"]):
                    origen, pin_origen, destino, pin_destino = arista
                    self.assertIn(origen, nodos, f"edge {indice}")
                    self.assertIn(destino, nodos, f"edge {indice}")
                    salida = graph._tipo_salida(nodos[origen]["verb"], tools.REGISTRO) \
                        if pin_origen == "out" else ""
                    entrada = self._tipo_entrada_del_cargador(
                        nodos[destino]["verb"], pin_destino, tools.REGISTRO)
                    # La misma regla que `JamTiposCompatibles` en C++, comodín incluido.
                    self.assertTrue(
                        salida and entrada and (entrada == "*" or salida == entrada),
                        f"{ruta.name}: edge {indice} {origen}.{pin_origen}({salida}) → "
                        f"{destino}.{pin_destino}({entrada}) sería rechazado al abrir")

class TablaTests(unittest.TestCase):
    """El «geometry spreadsheet» de Jam: los datos como números, no como dibujo."""

    def test_each_stream_type_renders_its_own_columns(self):
        from jam import fields
        esperado = {
            "F": (frames(3), "escala"),
            "P": (puntos([1.0, 0.5]), "peso"),
            "N[]": (fields.graph_curve(samples=6)["series"], "valor"),
            "S": (curve.bezier(end_z=300)["curve"], "largo"),
        }
        for tipo, (valor, columna) in esperado.items():
            with self.subTest(tipo=tipo):
                filas = debug.tabla(valor)
                self.assertTrue(filas, f"{tipo} no produjo tabla")
                self.assertIn(columna, filas[0])
                self.assertIn("idx", filas[0])

    def test_long_streams_are_truncated_with_a_count(self):
        filas = debug.tabla(frames(50), filas=4)
        self.assertEqual(len(filas), 6)          # encabezado + 4 + el resumen
        self.assertIn("y 46 más", filas[-1])

    def test_an_unknown_value_yields_no_table_instead_of_failing(self):
        self.assertEqual(debug.tabla(object()), [])
        self.assertEqual(debug.tabla([]), [])

    def test_the_values_shown_are_the_real_ones(self):
        filas = debug.tabla(frames(3, escalas=[0.25, 0.5, 0.75]))
        self.assertIn("0.250", filas[1])
        self.assertIn("0.750", filas[3])


class FlagPorNodoTests(unittest.TestCase):
    """El display flag de Houdini / la tecla D de PCG: se prende el nodo que YA está."""

    @staticmethod
    def _correr(marcados):
        import json
        from jam import graph
        doc = {"nodes": {
            "pts": {"verb": "pts_line", "params": {"count": "4"}, "x": 0, "y": 0,
                    "debug": "pts" in marcados},
            "mv": {"verb": "move", "params": {"dx": "50"}, "x": 300, "y": 0,
                   "debug": "mv" in marcados}},
            "edges": [["pts", "out", "mv", "in"]]}
        reporte, _ = graph.ejecutar_detalle(graph.JamGraph.from_json(json.dumps(doc)))
        return reporte

    def test_the_flag_travels_in_the_graph_json(self):
        import json
        from jam import graph
        g = graph.JamGraph.from_json(json.dumps(
            {"nodes": {"a": {"verb": "pts_line", "params": {}, "x": 0, "y": 0, "debug": True},
                       "b": {"verb": "pts_line", "params": {}, "x": 0, "y": 0}}, "edges": []}))
        self.assertTrue(g.nodes["a"]["debug"])
        # Un .jamgraph viejo sin el campo carga con el flag apagado, no rompe.
        self.assertFalse(g.nodes["b"]["debug"])

    def test_a_flagged_node_dumps_its_data_into_the_report(self):
        reporte = self._correr({"pts"})
        self.assertIn("PTS LINE P ✓", reporte)
        self.assertIn("idx", reporte)
        self.assertIn("peso", reporte)

    def test_an_unflagged_graph_reports_exactly_as_before(self):
        limpio = self._correr(set())
        self.assertNotIn("idx", limpio)
        self.assertNotIn("DEBUG", limpio)
        # El conteo por nodo sigue estando SIEMPRE: es el «recorrer y ver dónde cae a cero» de PCG.
        self.assertIn("PTS LINE P ✓ — 4 puntos", limpio)
        self.assertIn("MOVE P ✓ — 4 puntos", limpio)

    def test_the_debug_flag_never_breaks_the_run(self):
        """Sin motor no se puede dibujar; el grafo tiene que seguir corriendo igual."""
        reporte = self._correr({"pts", "mv"})
        self.assertIn("PTS LINE P ✓", reporte)
        self.assertIn("MOVE P ✓", reporte)
        # Informa el fallo del dibujo en vez de tirar la excepción hacia arriba.
        self.assertIn("DEBUG ✗", reporte)


if __name__ == "__main__":
    unittest.main()
