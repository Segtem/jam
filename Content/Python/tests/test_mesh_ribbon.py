from __future__ import annotations

import math
import unittest

from jam import ribbon_core


class RibbonCoreTests(unittest.TestCase):
    def test_recta_xy_tiene_ancho_winding_normal_y_uv_longitudinal(self):
        result = ribbon_core.ribbon_buffers(
            ((0, 0, 7), (100, 0, 7)), width=20, uv_scale=100)

        self.assertEqual(result["vertices"], (
            (0.0, 10.0, 7.0), (0.0, -10.0, 7.0),
            (100.0, 10.0, 7.0), (100.0, -10.0, 7.0)))
        self.assertEqual(result["triangles"], ((0, 1, 2), (1, 3, 2)))
        self.assertEqual(result["normals"], ((0.0, 0.0, 1.0),) * 4)
        self.assertEqual(result["uv0"], ((0.0, 0.0), (0.0, 1.0),
                                         (1.0, 0.0), (1.0, 1.0)))

    def test_esquina_miter_conserva_ancho_y_conectividad(self):
        result = ribbon_core.ribbon_buffers(
            ((0, 0, 0), (100, 0, 0), (100, 100, 0)), width=20,
            join="miter", miter_limit=2)

        self.assertEqual(len(result["vertices"]), 6)
        self.assertEqual(len(result["triangles"]), 4)
        for index in (0, len(result["vertices"]) - 2):
            self.assertAlmostEqual(
                math.dist(result["vertices"][index], result["vertices"][index + 1]), 20)
        self.assertAlmostEqual(math.dist(result["vertices"][2], result["vertices"][3]),
                               20 * math.sqrt(2))
        self.assertEqual({index for tri in result["triangles"] for index in tri}, set(range(6)))

    def test_bevel_hace_explicito_el_presupuesto_y_mantiene_pares(self):
        result = ribbon_core.ribbon_buffers(
            ((0, 0, 0), (100, 0, 0), (100, 100, 0)), width=20,
            join="miter", miter_limit=1.1)

        self.assertEqual(result["bevels"], 1)
        self.assertEqual(len(result["vertices"]), 8)
        self.assertEqual(len(result["triangles"]), 6)
        self.assertEqual(len(result["uv0"]), 8)

    def test_pendiente_calcula_normales_geometricas_normalizadas(self):
        result = ribbon_core.ribbon_buffers(
            ((0, 0, 0), (100, 0, 100), (200, 50, 120)), width=30)

        for normal in result["normals"]:
            self.assertAlmostEqual(math.sqrt(sum(value * value for value in normal)), 1.0)
        self.assertTrue(any(abs(normal[0]) > 1e-3 or abs(normal[1]) > 1e-3
                            for normal in result["normals"]))

    def test_planos_verticales_tienen_winding_determinista(self):
        xz = ribbon_core.ribbon_buffers(((0, 7, 0), (100, 7, 0)), plane="xz")
        yz = ribbon_core.ribbon_buffers(((7, 0, 0), (7, 100, 0)), plane="yz")
        self.assertEqual(xz["normals"], ((0.0, -1.0, 0.0),) * 4)
        self.assertEqual(yz["normals"], ((1.0, 0.0, 0.0),) * 4)

    def test_rechaza_cerrada_dominio_invalido_y_presupuesto(self):
        line = ((0, 0, 0), (100, 0, 0))
        square = ((0, 0, 0), (100, 0, 0), (100, 100, 0), (0, 0, 0))
        self.assertIn("costura UV", ribbon_core.ribbon_buffers(square)["error"])
        for params in ({"width": 0}, {"uv_scale": 0}, {"plane": "xyz"},
                       {"join": "round"}, {"miter_limit": 0.5}):
            with self.subTest(params=params):
                self.assertIn("error", ribbon_core.ribbon_buffers(line, **params))
        huge = tuple((float(index), float(index % 2), 0.0) for index in range(2049))
        self.assertIn("4096", ribbon_core.ribbon_buffers(huge)["error"])


if __name__ == "__main__":
    unittest.main()
