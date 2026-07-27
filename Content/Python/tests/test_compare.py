"""Oráculo de forma: medición pura y diff contra una referencia."""

from __future__ import annotations

import math
import sys
import types
import unittest

_unreal_fake = sys.modules.setdefault("unreal", types.ModuleType("unreal"))
if not hasattr(_unreal_fake, "TopLevelAssetPath"):
    _unreal_fake.TopLevelAssetPath = lambda package, name: (package, name)

from jam import compare  # noqa: E402


def columna(alturas, x=0.0, y=0.0):
    return [(x, y, z) for z in alturas]


def solido(radio_por_altura, *, franjas=8, por_franja=12):
    """Nube de puntos con el radio que dicte `radio_por_altura(u)` para u en 0..1.

    Sirve para fabricar un cono, un cilindro o cualquier silueta y compararlos.
    """
    puntos = []
    for banda in range(franjas):
        u = banda / (franjas - 1) if franjas > 1 else 0.0
        z = u * 100.0
        radio = radio_por_altura(u)
        for k in range(por_franja):
            angulo = 2.0 * math.pi * k / por_franja
            puntos.append((radio * math.cos(angulo), radio * math.sin(angulo), z))
    return puntos


class MedirTests(unittest.TestCase):
    def test_measures_bounds_and_normalizes_the_profile_by_relative_height(self):
        m = compare.medir(columna([0, 25, 50, 75, 100]), triangulos=8, secciones=2, franjas=4)

        self.assertEqual(m.vertices, 5)
        self.assertEqual(m.triangulos, 8)
        self.assertEqual(m.secciones, 2)
        self.assertAlmostEqual(m.alto, 100.0)
        self.assertAlmostEqual(m.base_z, 0.0)
        # z=100 cae en la última franja, no fuera del rango.
        self.assertEqual(sum(m.perfil), 1.0)
        self.assertAlmostEqual(m.perfil[-1], 2 / 5)

    def test_the_profile_is_scale_invariant(self):
        chico = compare.medir(columna([0, 10, 20, 30]), triangulos=2, secciones=1, franjas=4)
        grande = compare.medir(columna([0, 100, 200, 300]), triangulos=2, secciones=1, franjas=4)

        # Misma silueta a distinto tamaño ⇒ mismo perfil. Eso permite comparar FORMA sin escala.
        self.assertEqual(chico.perfil, grande.perfil)
        self.assertNotAlmostEqual(chico.alto, grande.alto)

    def test_width_uses_the_widest_horizontal_axis(self):
        puntos = [(-30.0, -5.0, 0.0), (30.0, 5.0, 100.0)]
        m = compare.medir(puntos, triangulos=1, secciones=1)
        self.assertAlmostEqual(m.ancho, 60.0)

    def test_flat_and_empty_meshes_are_handled(self):
        plano = compare.medir([(0.0, 0.0, 7.0)] * 4, triangulos=2, secciones=1, franjas=4)
        self.assertAlmostEqual(plano.alto, 0.0)
        self.assertEqual(plano.perfil, (1.0, 0.0, 0.0, 0.0))

        with self.assertRaises(ValueError):
            compare.medir([], triangulos=0, secciones=1)
        with self.assertRaises(ValueError):
            compare.medir([(0.0, 0.0, float("nan"))], triangulos=0, secciones=1)


class SiluetaYEsbeltezTests(unittest.TestCase):
    """Las dos métricas que faltaban cuando un pino salió como un poste con muñones."""

    def test_a_cone_and_a_cylinder_have_the_same_vertical_profile(self):
        # Éste es el agujero que motivó la silueta: los dos reparten la masa igual a lo largo del
        # eje, así que el perfil vertical no puede distinguirlos.
        cono = compare.medir(solido(lambda u: 1.0 - 0.9 * u), triangulos=1, secciones=1)
        cilindro = compare.medir(solido(lambda _u: 1.0), triangulos=1, secciones=1)

        self.assertEqual(cono.perfil, cilindro.perfil)
        self.assertAlmostEqual(compare.distancia_perfil(cono.perfil, cilindro.perfil), 0.0)
        # Pero la silueta sí los separa.
        self.assertGreater(compare.distancia_silueta(cono.silueta, cilindro.silueta), 0.3)

    def test_the_silhouette_follows_the_radius_and_is_scale_invariant(self):
        cono = compare.medir(solido(lambda u: 1.0 - 0.9 * u), triangulos=1, secciones=1)
        # Radio decreciente ⇒ silueta decreciente, normalizada a 1 en la franja más ancha.
        self.assertAlmostEqual(cono.silueta[0], 1.0)
        self.assertLess(cono.silueta[-1], 0.2)
        self.assertEqual(list(cono.silueta), sorted(cono.silueta, reverse=True))

        grande = compare.medir(solido(lambda u: 50.0 * (1.0 - 0.9 * u)), triangulos=1, secciones=1)
        for a, b in zip(cono.silueta, grande.silueta):
            self.assertAlmostEqual(a, b)

    def test_slenderness_is_height_over_width(self):
        alto = compare.medir(solido(lambda _u: 1.0), triangulos=1, secciones=1)
        # El sólido mide 100 de alto y 2 de ancho (radio 1).
        self.assertAlmostEqual(alto.esbeltez, 50.0, places=3)
        # Sin ancho (una columna de puntos) la esbeltez no explota: queda en 0.
        self.assertEqual(compare.medir(columna([0, 50, 100]), triangulos=1, secciones=1).esbeltez, 0.0)

    def test_slenderness_catches_what_height_and_width_pass_separately(self):
        # Alto 0.93× y ancho 0.73×: cada uno dentro de su tolerancia, pero la proporción se va.
        referencia = compare.medir(solido(lambda _u: 1.0), triangulos=1, secciones=1)
        estirado = compare.medir(
            [(x * 0.73, y * 0.73, z * 0.93) for x, y, z in solido(lambda _u: 1.0)],
            triangulos=1, secciones=1)
        r = compare.comparar(estirado, referencia)

        self.assertTrue(next(f for f in r["filas"] if f["metrica"] == "alto")["ok"])
        self.assertTrue(next(f for f in r["filas"] if f["metrica"] == "ancho")["ok"])
        esbeltez = next(f for f in r["filas"] if f["metrica"] == "esbeltez")
        self.assertFalse(esbeltez["ok"])
        self.assertAlmostEqual(esbeltez["razon"], 0.93 / 0.73, places=2)

    def test_silhouette_distance_is_bounded_and_symmetric(self):
        a, b = (1.0, 0.0), (0.0, 1.0)
        self.assertAlmostEqual(compare.distancia_silueta(a, b), 1.0)
        self.assertAlmostEqual(compare.distancia_silueta(b, a), 1.0)
        self.assertAlmostEqual(compare.distancia_silueta(a, a), 0.0)
        with self.assertRaises(ValueError):
            compare.distancia_silueta((1.0,), (0.5, 0.5))
        with self.assertRaises(ValueError):
            compare.distancia_silueta((), ())

    def test_a_cone_fails_against_a_cylinder_and_the_report_names_it(self):
        cono = compare.medir(solido(lambda u: 1.0 - 0.9 * u), triangulos=1, secciones=1)
        cilindro = compare.medir(solido(lambda _u: 1.0), triangulos=1, secciones=1)
        r = compare.comparar(cilindro, cono)

        self.assertFalse(r["ok"])
        self.assertIn(r["peor"], ("silueta", "ancho", "esbeltez"))
        self.assertFalse(next(f for f in r["filas"] if f["metrica"] == "silueta")["ok"])
        self.assertIn("silueta", r["texto"])
        self.assertIn("radio de cada franja", r["texto"])


class CompararTests(unittest.TestCase):
    def _par(self, izq, der, **kw):
        return compare.comparar(
            compare.medir(izq, triangulos=len(izq), secciones=2, franjas=4),
            compare.medir(der, triangulos=len(der), secciones=2, franjas=4), **kw)

    def test_an_identical_mesh_passes_every_metric(self):
        puntos = columna([0, 25, 50, 75, 100])
        r = self._par(puntos, puntos)
        self.assertTrue(r["ok"], r["texto"])
        self.assertIsNone(r["peor"])
        self.assertTrue(all(f["ok"] for f in r["filas"]))

    def test_a_missing_material_section_fails_without_tolerance(self):
        base = compare.medir(columna([0, 50, 100]), triangulos=3, secciones=1)
        ref = compare.medir(columna([0, 50, 100]), triangulos=3, secciones=2)
        r = compare.comparar(base, ref)

        self.assertFalse(r["ok"])
        # Una sección menos = falta un material entero; en un árbol, típicamente el follaje.
        secciones = next(f for f in r["filas"] if f["metrica"] == "secciones")
        self.assertFalse(secciones["ok"])
        self.assertEqual(secciones["limite"], 0.0)

    def test_the_worst_metric_is_reported_first(self):
        # Mismo perfil y ancho, pero cinco veces más bajo: el alto tiene que encabezar.
        r = self._par(columna([0, 25, 50, 75, 100]), columna([0, 125, 250, 375, 500]))
        self.assertFalse(r["ok"])
        self.assertEqual(r["peor"], "alto")
        self.assertEqual(r["filas"][0]["metrica"], "alto")
        self.assertAlmostEqual(r["filas"][0]["razon"], 0.2)

    def test_the_profile_catches_mass_missing_at_the_bottom(self):
        # Misma altura y mismos conteos; la generada no tiene nada en la mitad de abajo.
        arriba = [(0.0, 0.0, z) for z in (60, 70, 80, 90, 0, 100)]
        pareja = [(0.0, 0.0, z) for z in (10, 35, 60, 85, 0, 100)]
        r = self._par(arriba, pareja)

        self.assertFalse(r["ok"])
        perfil = next(f for f in r["filas"] if f["metrica"] == "perfil")
        self.assertFalse(perfil["ok"])
        self.assertGreater(perfil["desvio"], 0.15)

    def test_tolerances_are_configurable(self):
        corta = columna([0, 50, 100])
        larga = columna([0, 60, 120])
        self.assertFalse(self._par(corta, larga, tolerancias={"alto": 0.05})["ok"])
        self.assertTrue(self._par(corta, larga, tolerancias={"alto": 0.5})["ok"])

    def test_profile_distance_is_bounded_and_symmetric(self):
        a, b = (1.0, 0.0), (0.0, 1.0)
        self.assertAlmostEqual(compare.distancia_perfil(a, b), 1.0)
        self.assertAlmostEqual(compare.distancia_perfil(b, a), 1.0)
        self.assertAlmostEqual(compare.distancia_perfil(a, a), 0.0)
        with self.assertRaises(ValueError):
            compare.distancia_perfil((1.0,), (0.5, 0.5))

    def test_the_report_shows_both_profiles(self):
        r = self._par(columna([0, 50, 100]), columna([0, 50, 100]))
        self.assertIn("masa por franja de altura", r["texto"])
        self.assertIn("generada", r["texto"])
        self.assertIn("referencia", r["texto"])


if __name__ == "__main__":
    unittest.main()
