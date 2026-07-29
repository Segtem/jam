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


class MarcoTests(unittest.TestCase):
    def test_the_aabb_covers_every_node(self):
        nodos = [nodo("a", 10, 20, w=100, h=50), nodo("b", 300, -40, w=100, h=50)]
        self.assertEqual(layout.marco_de(nodos), (10, -40, 400, 70))

    def test_no_nodes_is_not_a_crash(self):
        self.assertEqual(layout.marco_de([]), (0.0, 0.0, 0.0, 0.0))


if __name__ == "__main__":
    unittest.main()
