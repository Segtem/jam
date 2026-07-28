"""Las tres piezas que le faltaban a Jam para los árboles de TreeGen, medidas como cerebro puro.

TreeGen no hace troncos rectos ni ramas de grosor arbitrario ni follaje que se dobla en bloque, y
esas tres cosas son justo las que el ojo usa para decidir si un árbol está bien. Acá se fija el
COMPORTAMIENTO de cada una, no sus números: los valores se retocan mirando el resultado, las
invariantes no.
"""

from __future__ import annotations

import math
import sys
import types
import unittest

sys.modules.setdefault("unreal", types.ModuleType("unreal"))

from jam import curve, fields  # noqa: E402


def recta(largo=400.0, puntos=11):
    paso = largo / (puntos - 1)
    return curve.CurvePath(tuple((0.0, 0.0, i * paso) for i in range(puntos)))


class DesvioDeCurvaTests(unittest.TestCase):
    def test_the_base_stays_put_when_the_ramp_starts_later(self):
        """Si la base se mueve, el árbol se despega de su raíz — se ve como si flotara."""
        salida = curve.noise(recta(), amplitud=30.0, desde=0.3, seed=1)["curve"]
        self.assertAlmostEqual(math.dist(salida.paths[0].points[0], (0.0, 0.0, 0.0)), 0.0, places=6)

    def test_without_a_ramp_the_base_does_move(self):
        """El contraste que prueba que la rampa hace algo y no que el ruido sea cero ahí."""
        salida = curve.noise(recta(), amplitud=30.0, desde=0.0, seed=1)["curve"]
        self.assertGreater(math.dist(salida.paths[0].points[0], (0.0, 0.0, 0.0)), 1.0)

    def test_amplitude_is_an_upper_bound_and_not_a_suggestion(self):
        for amplitud in (5.0, 20.0, 60.0):
            for seed in range(6):
                salida = curve.noise(recta(), amplitud=amplitud, seed=seed)["curve"]
                peor = max(math.dist(a, b)
                           for a, b in zip(recta().points, salida.paths[0].points))
                with self.subTest(amplitud=amplitud, seed=seed):
                    self.assertLessEqual(peor, amplitud + 1e-9)

    def test_the_noise_vector_is_clamped_by_its_LENGTH_not_per_component(self):
        """La cota se prueba acá y no por `noise`: medido sobre 16000 muestras de `fbm`, el
        combinado nunca pasa de 0.96, así que por la ruta normal no hay entrada que la active.

        Acotar cada componente por separado dejaría (1, 1) intacto —magnitud 1.41— y además le
        daría al ruido forma de cuadrado en vez de círculo."""
        self.assertEqual(curve._acotado(0.3, -0.4), (0.3, -0.4))
        du, dv = curve._acotado(3.0, 4.0)
        self.assertAlmostEqual(math.hypot(du, dv), 1.0)
        self.assertAlmostEqual(du / dv, 3.0 / 4.0, msg="cambió la dirección del desvío")
        du, dv = curve._acotado(1.0, 1.0)
        self.assertAlmostEqual(math.hypot(du, dv), 1.0)

    def test_zero_amplitude_leaves_the_curve_alone(self):
        salida = curve.noise(recta(), amplitud=0.0, seed=9)["curve"]
        for antes, despues in zip(recta().points, salida.paths[0].points):
            self.assertAlmostEqual(math.dist(antes, despues), 0.0, places=9)

    def test_the_same_seed_gives_the_same_curve(self):
        a = curve.noise(recta(), amplitud=20.0, seed=11)["curve"].paths[0].points
        b = curve.noise(recta(), amplitud=20.0, seed=11)["curve"].paths[0].points
        self.assertEqual(a, b)

    def test_different_seeds_give_different_curves(self):
        a = curve.noise(recta(), amplitud=20.0, seed=11)["curve"].paths[0].points
        b = curve.noise(recta(), amplitud=20.0, seed=12)["curve"].paths[0].points
        self.assertNotEqual(a, b)

    def test_the_metadata_survives_the_displacement(self):
        """`pivot_index` y `parent_radius` son lo que después leen el viento y el grosor heredado:
        una curva que los pierde al desviarse rompe los dos nodos de aguas abajo."""
        origen = curve.CurvePath(recta().points, scale=0.7, pivot_index=5, parent_radius=12.5,
                                 source_parent_index=3, source_local_index=2, seed=8)
        salida = curve.noise(origen, amplitud=10.0, seed=2)["curve"].paths[0]
        self.assertEqual(
            (salida.scale, salida.pivot_index, salida.parent_radius,
             salida.source_parent_index, salida.source_local_index, salida.seed),
            (0.7, 5, 12.5, 3, 2, 8))

    def test_a_curve_that_doubles_back_still_gets_a_valid_frame(self):
        """La base perpendicular se arma con el eje MÁS CHICO de la tangente: cualquier eje fijo se
        vuelve paralelo en algún punto de un árbol y ahí el producto cruz colapsa a cero."""
        for direccion in ((1, 0, 0), (0, 1, 0), (0, 0, 1), (1, 1, 1)):
            camino = curve.CurvePath(tuple(
                tuple(c * i * 50.0 for c in direccion) for i in range(6)))
            salida = curve.noise(camino, amplitud=20.0, seed=5)["curve"].paths[0]
            with self.subTest(direccion=direccion):
                movidos = sum(1 for a, b in zip(camino.points, salida.points)
                              if math.dist(a, b) > 1e-6)
                self.assertGreater(movidos, 0, "la base perpendicular colapsó")

    def test_it_refuses_what_it_cannot_do(self):
        self.assertIn("error", curve.noise(recta(), amplitud=-1.0))
        self.assertIn("error", curve.noise(recta(), escala=0.0))
        self.assertIn("error", curve.noise(recta(), amplitud=float("inf")))
        self.assertIn("error", curve.noise(None))


class GradienteTests(unittest.TestCase):
    def test_it_runs_from_zero_at_the_bottom_to_one_at_the_top(self):
        posiciones = [(0.0, 0.0, z) for z in (0.0, 100.0, 200.0)]
        self.assertEqual(fields.gradiente(posiciones), [0.0, 0.5, 1.0])

    def test_it_normalises_to_the_mesh_and_not_to_centimetres(self):
        """El mismo nodo tiene que servir para un arbusto y para un pino de treinta metros."""
        arbusto = fields.gradiente([(0, 0, 0), (0, 0, 50)])
        pino = fields.gradiente([(0, 0, 0), (0, 0, 3000)])
        self.assertEqual(arbusto, pino)

    def test_power_concentrates_the_movement_at_the_tip(self):
        medio = fields.gradiente([(0, 0, 0), (0, 0, 50), (0, 0, 100)], power=2.0)[1]
        self.assertAlmostEqual(medio, 0.25)

    def test_the_window_clamps_outside_its_range(self):
        valores = fields.gradiente([(0, 0, z) for z in range(0, 101, 25)],
                                   desde=0.25, hasta=0.75)
        self.assertEqual(valores, [0.0, 0.0, 0.5, 1.0, 1.0])

    def test_a_flat_mesh_gets_zero_instead_of_an_invented_gradient(self):
        """Inventar un gradiente donde no hay eje sería peor que no ponerlo: el shader movería
        vértices al azar."""
        self.assertEqual(fields.gradiente([(0, 0, 5)] * 4), [0.0, 0.0, 0.0, 0.0])

    def test_it_works_on_any_axis(self):
        posiciones = [(0.0, 0.0, 0.0), (100.0, 0.0, 0.0)]
        self.assertEqual(fields.gradiente(posiciones, eje="x"), [0.0, 1.0])
        self.assertEqual(fields.gradiente(posiciones, eje="z"), [0.0, 0.0])

    def test_it_refuses_what_it_cannot_do(self):
        with self.assertRaises(ValueError):
            fields.gradiente([(0, 0, 0)], eje="w")
        with self.assertRaises(ValueError):
            fields.gradiente([(0, 0, 0)], power=0.0)
        with self.assertRaises(ValueError):
            fields.gradiente([(0, 0, 0)], desde=0.8, hasta=0.2)
        self.assertEqual(fields.gradiente([]), [])


if __name__ == "__main__":
    unittest.main()
