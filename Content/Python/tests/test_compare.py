"""Oráculo de forma: medición pura y diff contra una referencia."""

from __future__ import annotations

import sys
import types
import unittest

_unreal_fake = sys.modules.setdefault("unreal", types.ModuleType("unreal"))
if not hasattr(_unreal_fake, "TopLevelAssetPath"):
    _unreal_fake.TopLevelAssetPath = lambda package, name: (package, name)

from jam import compare  # noqa: E402


def columna(alturas, x=0.0, y=0.0):
    return [(x, y, z) for z in alturas]


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
