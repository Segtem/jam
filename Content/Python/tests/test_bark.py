"""Relieve de corteza: ruido determinista, estirado a lo largo del eje, sobre las normales."""

from __future__ import annotations

import math
import sys
import types
import unittest

_unreal_fake = sys.modules.setdefault("unreal", types.ModuleType("unreal"))
if not hasattr(_unreal_fake, "TopLevelAssetPath"):
    _unreal_fake.TopLevelAssetPath = lambda package, name: (package, name)

from jam import bark  # noqa: E402


def cilindro(*, radio=20.0, alto=200.0, lados=16, anillos=20):
    """Posiciones y normales de un cilindro: el caso real de un tronco."""
    posiciones, normales = [], []
    for anillo in range(anillos):
        z = alto * anillo / (anillos - 1)
        for k in range(lados):
            angulo = 2.0 * math.pi * k / lados
            nx, ny = math.cos(angulo), math.sin(angulo)
            posiciones.append((radio * nx, radio * ny, z))
            normales.append((nx, ny, 0.0))
    return posiciones, normales


class RuidoTests(unittest.TestCase):
    def test_noise_is_deterministic_and_bounded(self):
        muestras = [bark.ruido(x * 0.37, x * 0.11, x * 0.73, seed=5) for x in range(400)]
        self.assertEqual(muestras, [bark.ruido(x * 0.37, x * 0.11, x * 0.73, seed=5)
                                    for x in range(400)])
        self.assertTrue(all(-1.0 <= v <= 1.0 for v in muestras), (min(muestras), max(muestras)))
        # No es una constante ni un escalón: varía de verdad.
        self.assertGreater(max(muestras) - min(muestras), 0.5)

    def test_the_seed_changes_the_field(self):
        a = [bark.ruido(x * 0.3, 0.0, 0.0, seed=1) for x in range(60)]
        b = [bark.ruido(x * 0.3, 0.0, 0.0, seed=2) for x in range(60)]
        self.assertNotEqual(a, b)

    def test_noise_is_continuous_between_cells(self):
        # Sin interpolación suave el ruido salta en cada frontera entera y se ven bandas.
        saltos = [abs(bark.ruido(1.0 + d, 0.5, 0.5) - bark.ruido(1.0 - d, 0.5, 0.5))
                  for d in (1e-3, 1e-4)]
        self.assertLess(max(saltos), 0.05, saltos)

    def test_fbm_stays_bounded_and_adds_detail(self):
        una = [bark.fbm(x * 0.2, 0.0, 0.0, octavas=1, seed=3) for x in range(200)]
        cuatro = [bark.fbm(x * 0.2, 0.0, 0.0, octavas=4, seed=3) for x in range(200)]
        self.assertTrue(all(-1.0 <= v <= 1.0 for v in cuatro))
        # Más octavas ⇒ más variación de alta frecuencia entre muestras vecinas.
        rugosidad = lambda s: sum(abs(b - a) for a, b in zip(s, s[1:]))  # noqa: E731
        self.assertGreater(rugosidad(cuatro), rugosidad(una))


class CortezaTests(unittest.TestCase):
    def test_the_field_is_stretched_along_the_axis(self):
        """El corazón de que parezca corteza: surcos LARGOS a lo alto, angostos alrededor."""
        kw = dict(escala=0.06, alargue=0.2, octavas=2, surcos=0.6, seed=7)
        variacion = lambda puntos: sum(  # noqa: E731
            abs(bark.relieve_corteza(*b, **kw) - bark.relieve_corteza(*a, **kw))
            for a, b in zip(puntos, puntos[1:]))

        # Recorrer 100cm alrededor del tronco cambia mucho más que recorrer 100cm hacia arriba.
        alrededor = [(x, 0.0, 0.0) for x in range(0, 100, 2)]
        a_lo_largo = [(0.0, 0.0, z) for z in range(0, 100, 2)]
        self.assertGreater(variacion(alrededor), 3.0 * variacion(a_lo_largo))

    def test_grooves_bias_the_field_towards_ridges(self):
        puntos = [(x * 0.7, x * 0.3, x * 0.11) for x in range(500)]
        liso = [bark.relieve_corteza(*p, escala=0.06, alargue=0.25, octavas=3,
                                     surcos=0.0, seed=7) for p in puntos]
        marcado = [bark.relieve_corteza(*p, escala=0.06, alargue=0.25, octavas=3,
                                        surcos=1.0, seed=7) for p in puntos]
        self.assertTrue(all(-1.0 <= v <= 1.0 for v in marcado))
        # La corteza real es asimétrica: grietas angostas y profundas entre lomos anchos, así que
        # el modo ridged corre la media hacia arriba (más superficie en lomo que en surco).
        self.assertGreater(sum(marcado) / len(marcado), sum(liso) / len(liso))

    def test_displacement_moves_each_vertex_along_its_own_normal(self):
        posiciones, normales = cilindro()
        movidas = bark.desplazar(posiciones, normales, amplitud=3.0, seed=7)

        self.assertEqual(len(movidas), len(posiciones))
        for (x, y, z), (mx, my, mz), (nx, ny, nz) in zip(posiciones, movidas, normales):
            d = math.dist((x, y, z), (mx, my, mz))
            self.assertLessEqual(d, 3.0 + 1e-6)
            if d > 1e-9:
                # El desplazamiento es paralelo a la normal (mismo sentido o el opuesto).
                direccion = ((mx - x) / d, (my - y) / d, (mz - z) / d)
                punto = sum(a * b for a, b in zip(direccion, (nx, ny, nz)))
                self.assertAlmostEqual(abs(punto), 1.0, places=6)
        # Un tronco vertical no debería cambiar de altura: sus normales son horizontales.
        self.assertEqual([round(p[2], 6) for p in posiciones],
                         [round(p[2], 6) for p in movidas])

    def test_displacement_is_deterministic_and_seed_dependent(self):
        posiciones, normales = cilindro()
        a = bark.desplazar(posiciones, normales, seed=7)
        self.assertEqual(a, bark.desplazar(posiciones, normales, seed=7))
        self.assertNotEqual(a, bark.desplazar(posiciones, normales, seed=8))

    def test_zero_amplitude_leaves_the_mesh_untouched(self):
        posiciones, normales = cilindro()
        self.assertEqual(bark.desplazar(posiciones, normales, amplitud=0.0), posiciones)

    def test_displacement_validates_its_inputs(self):
        posiciones, normales = cilindro(lados=4, anillos=2)
        with self.assertRaises(ValueError):
            bark.desplazar(posiciones, normales[:-1])
        with self.assertRaises(ValueError):
            bark.desplazar([], [])
        with self.assertRaises(ValueError):
            bark.desplazar(posiciones, normales, escala=0.0)
        with self.assertRaises(ValueError):
            bark.desplazar(posiciones, normales, alargue=-1.0)
        with self.assertRaises(ValueError):
            bark.desplazar(posiciones, normales, octavas=0)
        with self.assertRaises(ValueError):
            bark.desplazar(posiciones, normales, amplitud=float("inf"))


if __name__ == "__main__":
    unittest.main()
