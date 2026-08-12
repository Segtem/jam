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
            "F": (frames(3), ["idx", "x", "y", "z", "escala", "tx", "ty", "tz"]),
            "P": (puntos([1.0, 0.5]), ["idx", "x", "y", "z", "peso", "pendiente"]),
            "N[]": (fields.graph_curve(samples=6)["series"], ["idx", "valor"]),
            "S": (curve.bezier(end_z=300)["curve"], ["idx", "puntos", "largo", "escala"]),
        }
        for tipo, (valor, columnas) in esperado.items():
            with self.subTest(tipo=tipo):
                datos = debug.tabla_datos(valor)
                self.assertEqual([c["nombre"] for c in datos["columnas"]], columnas)
                # La posición se abre en x/y/z: una tupla no se puede ordenar de forma útil.
                self.assertTrue(all(c["tipo"] in ("num", "txt") for c in datos["columnas"]))

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

    # ---- ver SÓLO el marcado (Houdini / Substance) ----
    # Antes el flag SUMABA: dibujaba el nodo marcado y el grafo corría igual de punta a punta. Ver
    # una parte obligaba a soportar el resto —incluido lo que coloca actores u hornea assets—.

    @staticmethod
    def _estados(marcados):
        import json
        from jam import graph
        doc = {"nodes": {
            "pts": {"verb": "pts_line", "params": {"count": "4"}, "x": 0, "y": 0,
                    "debug": "pts" in marcados},
            "mv": {"verb": "move", "params": {"dx": "50"}, "x": 300, "y": 0,
                   "debug": "mv" in marcados}},
            "edges": [["pts", "out", "mv", "in"]]}
        return graph.ejecutar_detalle(graph.JamGraph.from_json(json.dumps(doc)))

    def test_marcar_el_de_arriba_deja_de_correr_el_de_abajo(self):
        reporte, por_nodo = self._estados({"pts"})
        self.assertNotIn("MOVE P ✓", reporte)
        self.assertEqual(por_nodo["mv"]["estado"], "omitido")

    def test_el_omitido_DICE_que_no_corrio_en_vez_de_desaparecer(self):
        """Un nodo que se apaga en silencio es indistinguible de uno roto, y el usuario buscaría
        el problema donde no está."""
        _reporte, por_nodo = self._estados({"pts"})
        self.assertIn("mv", por_nodo)
        self.assertIn("otro nodo", por_nodo["mv"]["texto"])

    def test_el_reporte_anuncia_el_corte_y_como_deshacerlo(self):
        reporte, _ = self._estados({"pts"})
        self.assertIn("SOLO ▸ pts", reporte)
        self.assertIn("◉", reporte)

    def test_marcar_el_de_abajo_corre_los_dos(self):
        """Lo que lo alimenta tiene que correr o no habría nada que mostrar."""
        reporte, por_nodo = self._estados({"mv"})
        self.assertIn("PTS LINE P ✓", reporte)
        self.assertNotEqual(por_nodo["pts"]["estado"], "omitido")

    def test_sin_marcar_nada_no_se_omite_nadie(self):
        _reporte, por_nodo = self._estados(set())
        self.assertNotIn("omitido", [v["estado"] for v in por_nodo.values()])


class InspectorTests(unittest.TestCase):
    """El panel de inspección: los datos del último Run, por nodo — el spreadsheet de Jam."""

    GRAFO = {
        "nodes": {
            "pts": {"verb": "pts_rect", "params": {"cols": "3", "rows": "3"}, "x": 0, "y": 0},
            "peso": {"verb": "weight_noise", "params": {}, "x": 300, "y": 0},
            "serie": {"verb": "graph_curve", "params": {"samples": "6"}, "x": 0, "y": 300},
        },
        "edges": [["pts", "out", "peso", "in"]],
    }

    def _correr(self):
        import json
        from jam import graph
        graph.ejecutar_detalle(graph.JamGraph.from_json(json.dumps(self.GRAFO)))

    def test_without_a_run_it_says_so_instead_of_showing_stale_data(self):
        import json
        from jam import api, graph
        graph._ULTIMA_CORRIDA.clear()
        r = json.loads(api.inspect_json())
        self.assertFalse(r["ok"])
        self.assertIn("todavía no corriste", r["error"])
        self.assertEqual(r["nodos"], [])

    def test_it_lists_every_node_with_its_type_and_count(self):
        import json
        from jam import api
        self._correr()
        r = json.loads(api.inspect_json())
        self.assertTrue(r["ok"])
        por_id = {n["id"]: n for n in r["nodos"]}
        self.assertEqual(por_id["pts"]["tipo"], "P")
        self.assertEqual(por_id["pts"]["cantidad"], 9)
        self.assertEqual(por_id["serie"]["tipo"], "N[]")
        self.assertEqual(por_id["serie"]["cantidad"], 6)
        # La CANTIDAD por nodo es lo que delata dónde el conteo cae a cero.
        self.assertTrue(all(n["inspeccionable"] for n in r["nodos"]))

    def test_it_returns_the_rows_of_the_chosen_node(self):
        import json
        from jam import api
        self._correr()
        r = json.loads(api.inspect_json("peso"))
        self.assertTrue(r["ok"])
        self.assertEqual(r["node"], "peso")
        # El encabezado vive en `columnas`, no como primera fila: así el panel puede armar
        # encabezados de verdad —clicables para ordenar— en vez de texto alineado.
        self.assertIn("peso", [c["nombre"] for c in r["columnas"]])
        self.assertEqual(len(r["filas"]), 9)
        self.assertEqual(r["total"], 9)
        # Las celdas llegan ya formateadas: la UI no reimplementa el redondeo.
        self.assertTrue(all(isinstance(c, str) for c in r["filas"][0]))

    def test_the_filter_narrows_the_rows_and_reports_the_new_total(self):
        import json
        from jam import api
        self._correr()
        completo = json.loads(api.inspect_json("pts"))
        filtrado = json.loads(api.inspect_json("pts", filtro="-300.000"))
        self.assertLess(len(filtrado["filas"]), len(completo["filas"]))
        self.assertLess(filtrado["total"], completo["total"])
        # Las columnas no cambian al filtrar: sigue siendo el mismo tipo de dato.
        self.assertEqual(filtrado["columnas"], completo["columnas"])

    def test_sorting_travels_through_the_api(self):
        import json
        from jam import api
        self._correr()
        r = json.loads(api.inspect_json("peso", orden="peso", descendente=True))
        self.assertEqual(r["orden"], "peso")
        self.assertTrue(r["descendente"])
        pesos = [float(f[4]) for f in r["filas"]]
        self.assertEqual(pesos, sorted(pesos, reverse=True))

    def test_an_unknown_node_fails_but_still_lists_the_others(self):
        import json
        from jam import api
        self._correr()
        r = json.loads(api.inspect_json("noexiste"))
        self.assertFalse(r["ok"])
        self.assertIn("no está en el último Run", r["error"])
        self.assertTrue(r["nodos"], "la lista sirve para elegir otro")

    def test_a_new_run_replaces_the_cache_instead_of_accumulating(self):
        import json
        from jam import api, graph
        self._correr()
        primero = {n["id"] for n in json.loads(api.inspect_json())["nodos"]}
        graph.ejecutar_detalle(graph.JamGraph.from_json(json.dumps(
            {"nodes": {"solo": {"verb": "pts_line", "params": {}, "x": 0, "y": 0}}, "edges": []})))
        segundo = {n["id"] for n in json.loads(api.inspect_json())["nodos"]}
        self.assertEqual(segundo, {"solo"})
        self.assertNotEqual(primero, segundo)


class OrdenTests(unittest.TestCase):
    """Ordenar por columna, como los encabezados del Geometry Spreadsheet."""

    def test_sorting_is_type_aware(self):
        datos = debug.tabla_datos(frames(4, escalas=[0.9, 0.2, 0.7, 0.4]),
                                  filas=10, orden="escala")
        self.assertEqual([f[4] for f in datos["filas"]], [0.2, 0.4, 0.7, 0.9])
        self.assertEqual(datos["orden"], "escala")

        desc = debug.tabla_datos(frames(4, escalas=[0.9, 0.2, 0.7, 0.4]),
                                 filas=10, orden="escala", descendente=True)
        self.assertEqual([f[4] for f in desc["filas"]], [0.9, 0.7, 0.4, 0.2])

    def test_sorting_happens_before_truncating(self):
        """El bug clásico: recortar primero y ordenar después sólo ordena lo que ya quedó."""
        muchos = frames(20, escalas=[1.0 - i * 0.05 for i in range(20)])
        datos = debug.tabla_datos(muchos, filas=3, orden="escala")
        self.assertEqual(datos["total"], 20)
        self.assertEqual(len(datos["filas"]), 3)
        # La más chica de las VEINTE, no la más chica de las tres primeras.
        self.assertAlmostEqual(datos["filas"][0][4], 0.05, places=4)

    def test_filtering_also_happens_before_truncating(self):
        datos = debug.tabla_datos(puntos([0.1] * 5 + [0.9] * 5), filas=3, filtro="0.9")
        self.assertEqual(datos["total"], 5)
        self.assertEqual(len(datos["filas"]), 3)

    def test_an_unknown_column_falls_back_to_natural_order(self):
        datos = debug.tabla_datos(frames(3), filas=10, orden="noexiste")
        self.assertEqual(datos["orden"], "")
        self.assertEqual([f[0] for f in datos["filas"]], [0, 1, 2])

    def test_text_columns_sort_lexicographically(self):
        from jam import variants
        seleccion = variants.FrameAssetSelection(
            frames(3), ("/Game/Zeta", "/Game/Alfa", "/Game/Mu"))
        datos = debug.tabla_datos(seleccion, filas=10, orden="variante")
        self.assertEqual([f[4] for f in datos["filas"]], ["Alfa", "Mu", "Zeta"])

    def test_the_text_table_is_built_on_the_structured_one(self):
        # Las columnas de cada tipo se declaran en UN solo lugar; el texto se deriva.
        datos = debug.tabla_datos(frames(3), filas=10)
        texto = debug.tabla(frames(3), filas=10)
        for columna in (c["nombre"] for c in datos["columnas"]):
            self.assertIn(columna, texto[0])
        self.assertEqual(len(texto), 1 + len(datos["filas"]))


class VerticesTests(unittest.TestCase):
    """La pestaña Points del spreadsheet: una malla es el único tipo que necesita el motor."""

    def test_positions_alone_give_the_basic_columns(self):
        cols, filas = debug.columnas_de_vertices([(1.0, 2.0, 3.0), (4.0, 5.0, 6.0)])
        self.assertEqual([c[0] for c in cols], ["idx", "x", "y", "z"])
        self.assertEqual(filas, [[0, 1.0, 2.0, 3.0], [1, 4.0, 5.0, 6.0]])

    def test_normals_and_colors_add_their_own_columns(self):
        cols, filas = debug.columnas_de_vertices(
            [(0.0, 0.0, 0.0)], [(0.0, 0.0, 1.0)], [(0.2, 0.4, 0.6)])
        self.assertEqual([c[0] for c in cols],
                         ["idx", "x", "y", "z", "nx", "ny", "nz", "r", "g", "b"])
        self.assertEqual(filas[0], [0, 0.0, 0.0, 0.0, 0.0, 0.0, 1.0, 0.2, 0.4, 0.6])

    def test_a_mismatched_count_is_ignored_instead_of_corrupting_rows(self):
        # Una malla recién generada puede no tener normales todavía; no se inventan columnas.
        cols, _filas = debug.columnas_de_vertices(
            [(0.0, 0.0, 0.0), (1.0, 1.0, 1.0)], [(0.0, 0.0, 1.0)])
        self.assertEqual([c[0] for c in cols], ["idx", "x", "y", "z"])

    def test_an_empty_mesh_yields_no_table(self):
        self.assertEqual(debug.columnas_de_vertices([]), ([], []))

    def test_the_vertex_table_reuses_the_shared_filter_and_sort(self):
        cols, filas = debug.columnas_de_vertices(
            [(0.0, 0.0, 30.0), (0.0, 0.0, 10.0), (0.0, 0.0, 20.0)])
        datos = debug.armar(cols, filas, filas=2, orden="z", descendente=True)
        self.assertEqual(datos["total"], 3)
        # Ordena sobre las TRES y recién después recorta a dos.
        self.assertEqual([f[3] for f in datos["filas"]], [30.0, 20.0])


if __name__ == "__main__":
    unittest.main()
