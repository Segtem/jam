"""Alinear, distribuir y el marquee: aritmética de rectángulos, sin editor.

Son las cuentas que decide `jam.layout` y aplica el C++. Testearlas acá es lo que permite que
«alinear a la izquierda» signifique lo mismo con cualquier pan, cualquier zoom y cualquier DPI.
"""

from __future__ import annotations

import sys
import types
import unittest

sys.modules.setdefault("unreal", types.ModuleType("unreal"))

from jam import layout  # noqa: E402


def nodo(i: str, x: float, y: float, w: float = 184.0, h: float = 40.0) -> dict:
    return {"id": i, "x": x, "y": y, "w": w, "h": h}


class AlinearTests(unittest.TestCase):
    def test_left_uses_the_leftmost_edge(self):
        r = layout.alinear([nodo("a", 100, 0), nodo("b", 40, 50), nodo("c", 300, 90)], "izquierda")
        self.assertEqual([r[k][0] for k in ("a", "b", "c")], [40, 40, 40])

    def test_left_does_not_touch_y(self):
        """Alinear en un eje mueve en UN eje. Tocar el otro es el bug clásico de esta función."""
        r = layout.alinear([nodo("a", 100, 7), nodo("b", 40, 55)], "izquierda")
        self.assertEqual(r["a"][1], 7)
        self.assertEqual(r["b"][1], 55)

    def test_right_aligns_the_right_EDGE_not_the_x(self):
        """Con anchos distintos, alinear a la derecha por `x` deja los bordes escalonados: el error
        no se ve con nodos del mismo ancho, y en Jam los anchos son iguales pero las ALTURAS no —
        el mismo error en «abajo» sí se vería. Se cubre acá porque es la misma cuenta."""
        r = layout.alinear([nodo("a", 0, 0, w=100), nodo("b", 10, 50, w=40)], "derecha")
        self.assertEqual(r["a"][0] + 100, 100)   # el borde derecho más lejano es el de `a`
        self.assertEqual(r["b"][0] + 40, 100)
        self.assertNotEqual(r["a"][0], r["b"][0])

    def test_bottom_aligns_the_bottom_edge_with_different_heights(self):
        """El caso real de Jam: un nodo con 6 params es mucho más alto que uno sin params."""
        r = layout.alinear([nodo("a", 0, 0, h=34), nodo("b", 200, 10, h=126)], "abajo")
        self.assertEqual(r["a"][1] + 34, 136)
        self.assertEqual(r["b"][1] + 126, 136)

    def test_center_x_puts_the_centers_in_one_column(self):
        r = layout.alinear([nodo("a", 0, 0, w=100), nodo("b", 200, 50, w=40)], "centro-x")
        self.assertAlmostEqual(r["a"][0] + 50, r["b"][0] + 20)

    def test_aligning_twice_changes_nothing_the_second_time(self):
        """Idempotencia: es la propiedad que hace predecible alinear al borde del cuadro en vez de
        «al último seleccionado». Si el ancla fuera un nodo cualquiera, el segundo alineado podría
        mover todo otra vez."""
        nodos = [nodo("a", 100, 0), nodo("b", 40, 50), nodo("c", 300, 90)]
        una = layout.alinear(nodos, "izquierda")
        otra = layout.alinear(
            [{**n, "x": una[n["id"]][0], "y": una[n["id"]][1]} for n in nodos], "izquierda")
        self.assertEqual(una, otra)

    def test_a_single_node_is_left_alone(self):
        self.assertEqual(layout.alinear([nodo("a", 12, 34)], "izquierda"), {"a": (12.0, 34.0)})

    def test_an_unknown_mode_is_an_error_and_not_a_silent_no_op(self):
        with self.assertRaises(ValueError):
            layout.alinear([nodo("a", 0, 0), nodo("b", 1, 1)], "diagonal")


class DistribuirTests(unittest.TestCase):
    def test_the_gaps_end_up_equal(self):
        nodos = [nodo("a", 0, 0, w=100), nodo("b", 130, 0, w=100), nodo("c", 500, 0, w=100)]
        r = layout.distribuir(nodos, "x")
        ancho = {"a": 100, "b": 100, "c": 100}
        xs = sorted(r.values())
        huecos = [xs[i + 1][0] - (xs[i][0] + 100) for i in range(len(xs) - 1)]
        self.assertAlmostEqual(huecos[0], huecos[1])
        self.assertEqual(len(ancho), 3)

    def test_the_gaps_are_equal_even_with_different_widths(self):
        """Igualar CENTROS pasaría este test sólo si todos midieran lo mismo. Con anchos distintos,
        centros parejos ⇒ huecos disparejos, que es lo que se ve mal."""
        nodos = [nodo("a", 0, 0, w=40), nodo("b", 100, 0, w=200), nodo("c", 600, 0, w=60)]
        r = layout.distribuir(nodos, "x")
        w = {"a": 40, "b": 200, "c": 60}
        orden = sorted(r.items(), key=lambda kv: kv[1][0])
        huecos = [orden[i + 1][1][0] - (orden[i][1][0] + w[orden[i][0]])
                  for i in range(len(orden) - 1)]
        self.assertAlmostEqual(huecos[0], huecos[1])

    def test_the_two_extremes_do_not_move(self):
        nodos = [nodo("a", 0, 0, w=40), nodo("b", 100, 0, w=200), nodo("c", 600, 0, w=60)]
        r = layout.distribuir(nodos, "x")
        self.assertAlmostEqual(r["a"][0], 0)
        self.assertAlmostEqual(r["c"][0] + 60, 660)

    def test_it_does_not_touch_the_other_axis(self):
        nodos = [nodo("a", 0, 5), nodo("b", 100, 15), nodo("c", 600, 25)]
        r = layout.distribuir(nodos, "x")
        self.assertEqual([r[k][1] for k in ("a", "b", "c")], [5, 15, 25])

    def test_two_nodes_have_nothing_to_distribute(self):
        nodos = [nodo("a", 0, 0), nodo("b", 500, 0)]
        self.assertEqual(layout.distribuir(nodos, "x"), {"a": (0.0, 0.0), "b": (500.0, 0.0)})

    def test_it_works_on_y_too(self):
        nodos = [nodo("a", 0, 0, h=20), nodo("b", 0, 30, h=100), nodo("c", 0, 400, h=20)]
        r = layout.distribuir(nodos, "y")
        h = {"a": 20, "b": 100, "c": 20}
        orden = sorted(r.items(), key=lambda kv: kv[1][1])
        huecos = [orden[i + 1][1][1] - (orden[i][1][1] + h[orden[i][0]])
                  for i in range(len(orden) - 1)]
        self.assertAlmostEqual(huecos[0], huecos[1])


class MarqueeTests(unittest.TestCase):
    def setUp(self):
        self.nodos = [nodo("a", 0, 0, w=100, h=50),
                      nodo("b", 200, 0, w=100, h=50),
                      nodo("c", 400, 200, w=100, h=50)]

    def test_crossing_is_enough_no_need_to_contain(self):
        """La convención directa: si el cuadro TOCA el nodo, entra. Exigir contención completa
        obliga a arrastrar por fuera de todo y es lo primero que se siente mal."""
        self.assertEqual(layout.en_marco(self.nodos, 50, 10, 250, 20), ["a", "b"])

    def test_dragging_backwards_selects_the_same(self):
        """Se arrastra tan seguido de derecha a izquierda como al revés."""
        self.assertEqual(layout.en_marco(self.nodos, 250, 20, 50, 10),
                         layout.en_marco(self.nodos, 50, 10, 250, 20))

    def test_a_click_without_dragging_selects_nothing(self):
        """Área cero ⇒ nada. Es lo que hace que un clic en el fondo LIMPIE la selección en vez de
        agarrar lo que esté abajo del cursor."""
        self.assertEqual(layout.en_marco(self.nodos, 10, 10, 10, 10), [])

    def test_touching_only_the_edge_does_not_count(self):
        """Pegado al borde izquierdo de `b` (x=200) sin superponerse: no entra. Con `<=` en vez de
        `<`, arrastrar hasta rozar un nodo lo metería en la selección sin que se vea por qué."""
        self.assertEqual(layout.en_marco(self.nodos, 150, 10, 200, 20), [])

    def test_a_box_over_empty_space_selects_nothing(self):
        self.assertEqual(layout.en_marco(self.nodos, 600, 600, 700, 700), [])


class ReglaDelMarqueeEnElCppTests(unittest.TestCase):
    """El marquee corre en Slate, no en Python: pedirle al cerebro la selección en cada mouse-up
    metería un viaje a Python en medio de un gesto. Pero entonces la regla queda escrita DOS veces,
    y una copia puede cambiar sin la otra sin que nada se queje.

    Se ata igual que la paleta de colores en `test_paleta.py`: el test LEE el `.cpp` y exige que la
    condición siga siendo la misma que `layout.en_marco` — cruce con desigualdad ESTRICTA.
    """

    def condicion(self) -> str:
        import re
        from pathlib import Path

        raiz = Path(__file__).resolve().parents[3]
        cpp = (raiz / "Source" / "JamEditor" / "Private" / "SJamGraphEditor.cpp").read_text(
            encoding="utf-8")
        m = re.search(r"if \(N\.Pos\.X[^)]*?N\.Height[^)]*?\)", cpp, re.S)
        self.assertIsNotNone(m, "no se encontró la condición del marquee en el C++")
        return re.sub(r"\s+", " ", m.group(0))

    def test_the_cpp_compares_all_four_edges(self):
        """Olvidar un eje da un marquee que selecciona una FRANJA infinita en vez de un cuadro."""
        c = self.condicion()
        for lado in ("Max.X", "Min.X", "Max.Y", "Min.Y"):
            self.assertIn(lado, c, f"al marquee del C++ le falta comparar contra {lado}")

    def test_the_cpp_uses_strict_inequalities_like_en_marco(self):
        """`<=` haría que rozar un nodo lo seleccione — el caso que cubre
        `test_touching_only_the_edge_does_not_count`, pero del lado de Slate."""
        c = self.condicion()
        self.assertNotIn("<=", c, "el marquee del C++ cuenta el roce; `en_marco` no")
        self.assertNotIn(">=", c, "el marquee del C++ cuenta el roce; `en_marco` no")

    def test_the_cpp_measures_each_node_with_its_own_height(self):
        """El ancho es fijo (`NodeWidth`) pero el ALTO no: depende de cuántos params tiene el verbo.
        Usar una altura fija dejaría fuera del cuadro nodos que se ven adentro."""
        self.assertIn("N.Height", self.condicion())


class ReglaDeContencionCompartidaEnElCppTests(unittest.TestCase):
    """La condición de contención (Fase 7.1, cajas de comentario/grupo) la usan tanto el marquee
    como el arrastre del cuerpo de una caja: las dos llaman a `NodeIdsTouchingRect`, un único helper
    en `SJamGraphEditor.cpp`. Si alguien copiara la condición a mano para el segundo caso en vez de
    llamar al helper, habría DOS fórmulas que podrían divergir en silencio — y como
    `ReglaDelMarqueeEnElCppTests.condicion()` sólo mira la PRIMERA ocurrencia que encuentra, no se
    enteraría. Este test cuenta TODAS las ocurrencias.
    """

    def cpp(self) -> str:
        from pathlib import Path

        raiz = Path(__file__).resolve().parents[3]
        return (raiz / "Source" / "JamEditor" / "Private" / "SJamGraphEditor.cpp").read_text(
            encoding="utf-8")

    def test_only_one_copy_of_the_containment_condition_exists(self):
        import re

        ocurrencias = re.findall(r"if \(N\.Pos\.X[^)]*?N\.Height[^)]*?\)", self.cpp(), re.S)
        self.assertEqual(len(ocurrencias), 1,
            "la condición de contención aparece más de una vez en el .cpp: "
            "el marquee y el arrastre de comentarios tienen que compartir NodeIdsTouchingRect")

    def test_the_marquee_and_the_comment_drag_both_call_the_shared_helper(self):
        # Definición + el marquee (NodeIdsTouchingRect(Min, Max)) + BeginCommentDrag
        # (NodeIdsTouchingRect(C->Pos, ...)): al menos 3 apariciones de la llamada.
        ocurrencias = self.cpp().count("NodeIdsTouchingRect(")
        self.assertGreaterEqual(ocurrencias, 3,
            "NodeIdsTouchingRect debería aparecer en su definición, en el marquee y en BeginCommentDrag")


class AutoLayoutTests(unittest.TestCase):
    """Acomodar por capas: el flujo se lee de izquierda a derecha, sin cables para atrás."""

    def cadena(self):
        return [nodo("a", 0, 0), nodo("b", 500, 300), nodo("c", 10, 900)]

    def test_a_chain_becomes_three_columns_in_order(self):
        pos = layout.auto(self.cadena(), [("a", "b"), ("b", "c")])
        self.assertLess(pos["a"][0], pos["b"][0])
        self.assertLess(pos["b"][0], pos["c"][0])

    def test_no_cable_ever_points_backwards(self):
        """La propiedad que justifica el feature: si un nodo quedara a la izquierda de algo que lo
        alimenta, el cable iría para atrás y acomodar no habría servido de nada."""
        nodos = [nodo(i, 0, 0) for i in "abcde"]
        aristas = [("a", "c"), ("b", "c"), ("c", "d"), ("a", "d"), ("d", "e")]
        pos = layout.auto(nodos, aristas)
        for origen, destino in aristas:
            self.assertLess(pos[origen][0], pos[destino][0],
                            f"el cable {origen}→{destino} apunta para atrás")

    def test_the_longest_path_decides_the_column_not_the_shortest(self):
        """`a` alimenta a `b` y a `c`, y `b` también alimenta a `c`. Con el camino más CORTO, `c`
        quedaría en la misma columna que `b` y su cable iría en vertical o para atrás."""
        pos = layout.auto([nodo("a", 0, 0), nodo("b", 0, 0), nodo("c", 0, 0)],
                          [("a", "b"), ("a", "c"), ("b", "c")])
        self.assertLess(pos["a"][0], pos["b"][0])
        self.assertLess(pos["b"][0], pos["c"][0])

    def test_nodes_in_one_column_do_not_overlap_even_with_different_heights(self):
        """Los nodos de Jam no miden todos igual: espaciar por una altura fija los encimaría."""
        nodos = [nodo("raiz", 0, 0), nodo("x", 0, 0, h=200), nodo("y", 0, 0, h=40)]
        pos = layout.auto(nodos, [("raiz", "x"), ("raiz", "y")])
        alto = {"x": 200, "y": 40}
        arriba, abajo = sorted(["x", "y"], key=lambda k: pos[k][1])
        self.assertGreaterEqual(pos[abajo][1], pos[arriba][1] + alto[arriba],
                                "dos nodos de la misma columna se encimaron")

    def test_the_graph_stays_where_it_was(self):
        """Acomodar no puede mandar el grafo a mil unidades de donde lo estabas mirando."""
        nodos = [nodo("a", 700, 400), nodo("b", 900, 400)]
        pos = layout.auto(nodos, [("a", "b")])
        x0, y0, _x1, _y1 = layout.marco_de(nodos)
        self.assertEqual(min(p[0] for p in pos.values()), x0)
        self.assertEqual(min(p[1] for p in pos.values()), y0)

    def test_an_edge_with_one_end_outside_the_selection_is_ignored(self):
        """Al acomodar una selección, un cable que sale hacia afuera no dice nada del orden interno."""
        pos = layout.auto([nodo("a", 0, 0), nodo("b", 0, 0)], [("a", "b"), ("b", "afuera")])
        self.assertEqual(set(pos), {"a", "b"})

    def test_a_cycle_does_not_raise(self):
        """El Compile ya rechaza los ciclos, pero acomodar es un gesto de edición y tiene que
        sobrevivir a un grafo a medio cablear."""
        pos = layout.auto([nodo("a", 0, 0), nodo("b", 0, 0)], [("a", "b"), ("b", "a")])
        self.assertEqual(set(pos), {"a", "b"})

    def test_no_nodes_is_not_a_crash(self):
        self.assertEqual(layout.auto([], [("a", "b")]), {})


class AjustarAGrillaTests(unittest.TestCase):
    def test_each_node_lands_on_the_nearest_crossing(self):
        pos = layout.ajustar_a_grilla([nodo("a", 13, -5), nodo("b", 48, 100)])
        self.assertEqual(pos["a"], (24.0, 0.0))
        self.assertEqual(pos["b"], (48.0, 96.0))

    def test_it_snaps_the_corner_and_not_the_centre(self):
        """En Jam la altura depende de cuántos params tiene el verbo. Ajustando el CENTRO, dos nodos
        de distinta altura quedarían con los bordes desalineados — justo lo que uno quiere arreglar."""
        pos = layout.ajustar_a_grilla([nodo("bajo", 0, 0, h=40), nodo("alto", 0, 0, h=200)])
        self.assertEqual(pos["bajo"][1], pos["alto"][1])

    def test_snapping_twice_changes_nothing(self):
        nodos = [nodo("a", 13, -5), nodo("b", 48, 100)]
        una = layout.ajustar_a_grilla(nodos)
        otra = layout.ajustar_a_grilla(
            [{**n, "x": una[n["id"]][0], "y": una[n["id"]][1]} for n in nodos])
        self.assertEqual(una, otra)

    def test_a_step_of_zero_is_an_error_and_not_a_division_by_zero(self):
        with self.assertRaises(ValueError):
            layout.ajustar_a_grilla([nodo("a", 1, 1)], paso=0)


class PasoDeLaGrillaEnElCppTests(unittest.TestCase):
    """El paso vive dos veces: `layout.PASO_GRILLA` y la grilla que dibuja el `.cpp`.

    Se ata como la regla del marquee. Ajustar a una grilla DISTINTA de la que se ve sería peor que
    no ajustar nada: los nodos quedarían prolijamente alineados contra líneas invisibles.
    """

    def test_the_step_matches_the_grid_the_cpp_draws(self):
        import re
        from pathlib import Path

        raiz = Path(__file__).resolve().parents[3]
        cpp = (raiz / "Source" / "JamEditor" / "Private" / "SJamGraphEditor.cpp").read_text(
            encoding="utf-8")
        cuerpo = cpp.split("class SJamGridLayer")[1].split("\n};")[0]
        pasos = {float(x) for x in re.findall(r"([\d.]+)f \* Zoom", cuerpo)}
        self.assertEqual(pasos, {layout.PASO_GRILLA},
                         "el paso del snap no es el de la grilla que se dibuja")


class AgarrarUnCableTests(unittest.TestCase):
    """Qué cable hay bajo el cursor: lo que necesita el reroute para saber dónde insertar el punto.

    Reproduce la MISMA curva que dibuja `SJamWireLayer` —un Hermite con tangentes horizontales— en
    vez de la recta entre las puntas. Con la recta, agarrar un cable por la panza fallaría justo
    donde se lo está viendo.
    """

    def cable(self, ax, ay, bx, by, i="e1"):
        return [{"id": i, "ax": ax, "ay": ay, "bx": bx, "by": by}]

    def test_a_point_on_the_wire_grabs_it(self):
        m = layout.cable_mas_cercano(100, 0, self.cable(0, 0, 200, 0))
        self.assertIsNotNone(m)
        self.assertEqual(m["cable"], "e1")

    def test_a_point_far_away_grabs_nothing(self):
        self.assertIsNone(layout.cable_mas_cercano(100, 500, self.cable(0, 0, 200, 0)))

    def test_the_returned_point_is_on_the_curve_and_not_where_you_clicked(self):
        """El punto de paso tiene que nacer PEGADO al cable: si naciera donde hiciste clic, el cable
        pegaría un salto al insertarlo."""
        m = layout.cable_mas_cercano(100, 6, self.cable(0, 0, 200, 0))
        self.assertIsNotNone(m)
        self.assertAlmostEqual(m["y"], 0.0, places=6)

    def apartamiento(self, ax, ay, bx, by) -> float:
        """Cuánto se aparta la curva de la recta entre sus puntas, en x."""
        return max(
            abs(layout._punto_del_cable(ax, ay, bx, by, i / 40)[0]
                - (ax + (bx - ax) * (i / 40)))
            for i in range(41))

    def test_a_backwards_wire_bulges_far_off_the_straight_line(self):
        """Acá es donde muestrear la curva se paga: en un cable que va HACIA ATRÁS (el destino a la
        izquierda del origen) la panza se aparta mucho más que el radio de agarre, así que un
        hit-test contra la recta fallaría justo donde se ve el cable.

        Y es el caso que importa: los cables hacia atrás son los de un grafo desordenado, que es
        exactamente cuando uno quiere insertar un punto de paso.
        """
        self.assertGreater(self.apartamiento(0, 0, -150, 120), layout.AGARRE_CABLE)

    def test_a_forward_wire_barely_bulges(self):
        """Documentado a propósito: hacia adelante la curva casi no se aparta. Muestrear no es lo
        que salva ese caso —una recta alcanzaría— y conviene que quede escrito para que nadie
        justifique el muestreo con el caso equivocado."""
        self.assertLess(self.apartamiento(0, 0, 200, 0), layout.AGARRE_CABLE)

    def test_with_two_wires_the_closest_one_wins(self):
        """El que gana tiene que ser el que se ve arriba, no el primero de la lista."""
        cables = self.cable(0, 0, 200, 0, "lejos") + self.cable(0, 40, 200, 40, "cerca")
        m = layout.cable_mas_cercano(100, 38, cables)
        self.assertEqual(m["cable"], "cerca")

    def test_no_wires_is_not_a_crash(self):
        self.assertIsNone(layout.cable_mas_cercano(0, 0, []))

    def test_a_grab_radius_of_zero_is_an_error(self):
        with self.assertRaises(ValueError):
            layout.cable_mas_cercano(0, 0, self.cable(0, 0, 1, 1), agarre=0)


class MarcoTests(unittest.TestCase):
    def test_the_aabb_covers_every_node(self):
        nodos = [nodo("a", 10, 20, w=100, h=50), nodo("b", 300, -40, w=100, h=50)]
        self.assertEqual(layout.marco_de(nodos), (10, -40, 400, 70))

    def test_no_nodes_is_not_a_crash(self):
        self.assertEqual(layout.marco_de([]), (0.0, 0.0, 0.0, 0.0))


class SincronizacionDeLaVentanaFlotanteEnElCppTests(unittest.TestCase):
    """Reabrir el Graph en Wayland/KWin dejaba la ventana sin recibir clics.

    Medido el 2026-08-10: `AsegurarVentanaGraphVisible` pidió mover la ventana a `(173, 97)` y
    `GetRectInScreen()` siguió informando `(0, 0)` en el mismo frame. Slate conserva ese rectángulo
    para el hit-test mientras KWin dibuja en el otro, así que los clics caen corridos por la
    diferencia y la ventana parece muerta. Sólo se destrababa redimensionando a mano.

    Esto no se puede testear sin motor —es geometría de un compositor real— así que se ata igual que
    el marquee: el test LEE el `.cpp` y exige que las tres decisiones que hacen al arreglo sigan ahí.
    La verificación de que funciona es el gesto en el editor, y su evidencia es la línea de log
    `ventana Graph resincronizada — alineada=…`.
    """

    def modulo(self) -> str:
        from pathlib import Path

        raiz = Path(__file__).resolve().parents[3]
        return (raiz / "Source" / "JamEditor" / "Private" / "JamEditorModule.cpp").read_text(
            encoding="utf-8")

    def test_una_flotante_reubicada_se_resincroniza(self):
        """Sin la llamada, reubicar deja el hit-test corrido: es el defecto original."""
        cpp = self.modulo()
        self.assertIn("static void SincronizarGeometriaFlotante", cpp)
        self.assertIn("SincronizarGeometriaFlotante(Ventana.ToSharedRef()", cpp)

    def test_el_empujon_cambia_el_tamano_de_verdad(self):
        """El corazón del arreglo. Un `ReshapeWindow` al MISMO tamaño puede no generar ningún
        `configure` del compositor, y sin ese evento Slate nunca actualiza su geometría: el arreglo
        se volvería un no-op silencioso que igual loguea. El primer paso tiene que pedir un tamaño
        distinto del final."""
        self.assertIn("TamPedido - FVector2D(1.0f, 1.0f)", self.modulo())

    def test_la_resincronizacion_es_diferida_y_no_en_el_mismo_frame(self):
        """Hacerlo en el frame de la apertura reproduce el estado que se intenta reparar: el
        compositor todavía no confirmó nada. Van dos ticks, como en la ventana principal."""
        import re

        cpp = self.modulo()
        cuerpo = cpp[cpp.index("static void SincronizarGeometriaFlotante"):]
        cuerpo = cuerpo[:cuerpo.index("\n/**")]
        # El paréntesis es parte del patrón a propósito: sin él, `AddTicker` matchea también el
        # prefijo de cualquier identificador más largo y el test deja pasar la mutación que buscaba.
        self.assertEqual(len(re.findall(r"AddTicker\(", cuerpo)), 2,
                         "la resincronización de la flotante dejó de ser dos ticks diferidos")

    def test_el_log_publica_si_quedo_alineada(self):
        """Sin esta medida, «se arregló» dependería de que alguien intente un clic y lo reporte."""
        cpp = self.modulo()
        self.assertIn("ventana Graph resincronizada", cpp)
        self.assertIn("bAlineada", cpp)


if __name__ == "__main__":
    unittest.main()


class DropDelRibbonAlLienzoEnElCppTests(unittest.TestCase):
    """Arrastrar una ficha del ribbon al lienzo rompía el editor cada tanto.

    El stack del assert lo ubica: `SWidget::Prepass_Internal` → `ForEachWidget` →
    `GetChildRefAt` con un índice fuera de rango. `OnDrop` llamaba a `AddNode`, que agrega slots al
    canvas, en medio del recorrido que Slate estaba haciendo sobre esos mismos hijos. Que fuera
    intermitente es coherente: depende de que el drop caiga dentro de ese recorrido.

    Esto no se puede testear sin motor —es un gesto de mouse en Slate— así que se ata leyendo el
    `.cpp`, igual que el marquee. La verificación de que el crash desapareció es el gesto real.
    """

    def modulo(self) -> str:
        from pathlib import Path

        raiz = Path(__file__).resolve().parents[3]
        return (raiz / "Source" / "JamEditor" / "Private" / "SJamGraphEditor.cpp").read_text(
            encoding="utf-8")

    def cuerpo_de_ondrop(self) -> str:
        cpp = self.modulo()
        inicio = cpp.index("FReply SJamGraphEditor::OnDrop")
        return cpp[inicio:cpp.index("\n}", inicio)]

    def test_el_drop_no_crea_el_nodo_dentro_del_evento(self):
        """La regresión que importa: volver a llamar `AddNode` desde `OnDrop` devuelve el crash."""
        self.assertNotIn("AddNode(", self.cuerpo_de_ondrop(),
                         "OnDrop volvió a crear el nodo durante el manejo del evento")

    def test_el_drop_difiere_la_creacion_a_un_timer(self):
        cuerpo = self.cuerpo_de_ondrop()
        self.assertIn("RegisterActiveTimer", cuerpo)
        self.assertIn("CrearNodoDiferido", cuerpo)

    def test_el_pendiente_se_limpia_antes_de_crear(self):
        """Sin esto, un `AddNode` que falle deja el pendiente vivo y lo reintenta cada frame."""
        cpp = self.modulo()
        inicio = cpp.index("EActiveTimerReturnType SJamGraphEditor::CrearNodoDiferido")
        cuerpo = cpp[inicio:cpp.index("\n}\n", inicio)]
        self.assertLess(cuerpo.index("DropPendienteVerbo.Reset()"), cuerpo.index("AddNode("),
                        "el pendiente se limpia después de crear: un fallo lo reintenta para siempre")


class IndiceDelSwitcherDelNodoEnElCppTests(unittest.TestCase):
    """El `SWidgetSwitcher` de la ficha elegía su columna con un lambda que capturaba `this` crudo.

    Un nodo destruido mientras su switcher todavía se dibujaba hacía leer `bCompacto` sobre memoria
    liberada, y el editor moría en `DrawPrepass` con «Array index out of bounds: 254 into an array of
    size 2». El 254 es la firma del bug: con optimización el compilador sabe que un `bool` sólo vale
    0 o 1, así que `bCompacto ? 1 : 0` compila como una carga directa del byte, sin rama; sobre
    memoria liberada ese byte es basura y entra tal cual como índice de slot.

    No se puede testear sin motor —hace falta destruir un widget vivo— así que se ata leyendo el
    `.cpp`, como el marquee. La confirmación de que no vuelve es el gesto real.
    """

    def lambda_de_la_columna(self) -> str:
        from pathlib import Path

        raiz = Path(__file__).resolve().parents[3]
        cpp = (raiz / "Source" / "JamEditor" / "Private" / "SJamGraphNode.cpp").read_text(
            encoding="utf-8")
        # Anclado a la columna central por su ancho: hay otros SOverlay en el archivo.
        inicio = cpp.index("AnchoColumnaCentral()); }))")
        bloque = cpp[inicio:cpp.index("// centro: icono", inicio)]
        # Sin comentarios: el de acá al lado EXPLICA el bug y menciona `[this]`, así que juzgarlo
        # junto con el código haría que el test se atrape a sí mismo. Pasó en el primer intento.
        return "\n".join(linea for linea in bloque.splitlines()
                          if not linea.strip().startswith("//"))

    def test_la_columna_no_se_elige_con_un_lambda(self):
        """Con la visibilidad por atributo, el nodo quedaba mostrando la columna compacta con el
        TAMAÑO de la normal, y el botón ya no lo devolvía: invalidar no alcanza para que Slate
        reevalúe una visibilidad cacheada. Se prende y apaga a mano en `SetCompacto`."""
        cuerpo = self.lambda_de_la_columna()
        self.assertNotIn("Visibility_Lambda", cuerpo)
        self.assertNotIn("[this]", cuerpo)

    def test_las_dos_columnas_se_guardan_para_poder_alternarlas(self):
        cuerpo = self.lambda_de_la_columna()
        self.assertIn("SAssignNew(ColumnaParams", cuerpo)
        self.assertIn("SAssignNew(ColumnaLetras", cuerpo)

    def test_alternar_cambia_la_visibilidad_de_las_dos(self):
        """Tocar una sola deja las dos visibles o las dos ocultas."""
        from pathlib import Path

        raiz = Path(__file__).resolve().parents[3]
        cpp = (raiz / "Source" / "JamEditor" / "Private" / "SJamGraphNode.cpp").read_text(
            encoding="utf-8")
        inicio = cpp.index("void SJamGraphNode::SetCompacto")
        cuerpo = cpp[inicio:cpp.index("\n}\n", inicio)]
        self.assertIn("ColumnaParams->SetVisibility", cuerpo)
        self.assertIn("ColumnaLetras->SetVisibility", cuerpo)

    def test_la_ficha_no_elige_su_columna_por_indice(self):
        """El experimento que discrimina de quién es el crash.

        Arreglar el índice dos veces —diferir la creación, y cambiar `[this]` por un puntero débil
        con clamp— no lo evitó. Así que se saca el índice: dos hijos con `Visibility` hacen lo mismo
        y no hay entero que pueda quedar fuera de rango. Si el editor SIGUE cayendo en un
        `TOneDynamicChildBase<…, TSlateAttribute<int>>`, el switcher culpable no es de Jam, porque
        este era el único que había, y hay que buscarlo en el editor.
        """
        from pathlib import Path

        raiz = Path(__file__).resolve().parents[3]
        fuentes = list((raiz / "Source").rglob("*.cpp")) + list((raiz / "Source").rglob("*.h"))
        con_switcher = [f.name for f in fuentes
                        if "SNew(SWidgetSwitcher)" in f.read_text(encoding="utf-8")]
        self.assertEqual(con_switcher, [],
                         f"volvió a aparecer un SWidgetSwitcher en Slate: {con_switcher}")


class ArgumentosDelNodoInicializadosTests(unittest.TestCase):
    """Los `SLATE_ARGUMENT` de tipo POD nacen SIN INICIALIZAR.

    Son miembros crudos de la struct de args: quien no los pasa se lleva lo que hubiera en la pila.
    `AddNode` nunca pasaba `Compacto`, así que un nodo recién creado leía un `bool` basura y salía en
    tamaño normal pero con las letras del modo compacto.

    Ese mismo bool causó el crash que costó tres intentos: con optimización `bCompacto ? 1 : 0`
    compila como una carga directa del byte, así que un 254 de basura entraba tal cual como índice
    de slot y volteaba el editor. No era un use-after-free como se creyó dos veces: era esto.
    """

    def begin_args(self) -> str:
        from pathlib import Path

        raiz = Path(__file__).resolve().parents[3]
        cabecera = (raiz / "Source" / "JamEditor" / "Public" / "SJamGraphNode.h").read_text(
            encoding="utf-8")
        inicio = cabecera.index("SLATE_BEGIN_ARGS(SJamGraphNode)")
        return cabecera[inicio:cabecera.index("SLATE_END_ARGS", inicio)]

    def test_todo_bool_de_los_args_arranca_con_un_valor(self):
        """Sin esto el bug vuelve en silencio y encima no determinista."""
        import re

        bloque = self.begin_args()
        declarados = set(re.findall(r"SLATE_ARGUMENT\(bool,\s*(\w+)\)", bloque))
        inicializados = set(re.findall(r"_(\w+)\((?:true|false)\)", bloque))
        faltan = declarados - inicializados
        self.assertEqual(faltan, set(),
                         f"estos bool de SLATE_ARGUMENT quedan sin inicializar: {sorted(faltan)}")
