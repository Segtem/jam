"""Tests de las primitivas planas de la base común contra el fixture del motor.

Comprueba quad, grid y disc con el juez de primitivas (`fixtures_primitivas.py`), que compara
triángulo por triángulo y cara frontal contra lo que produjo Unreal Engine 5.8.1.
"""

from __future__ import annotations

import unittest

import fixtures_primitivas
from jam import malla_core, malla_plana


class TestMallaPlana(unittest.TestCase):
    def test_quad_fixture(self):
        casos = fixtures_primitivas.casos("mesh_quad")
        self.assertGreater(len(casos), 0, "debe haber casos de mesh_quad en el fixture")
        for caso in casos:
            with self.subTest(caso.get("nombre") or str(caso.get("params"))):
                if "error" in caso:
                    dif = fixtures_primitivas.juzgar_error(malla_plana.quad, caso)
                else:
                    m = malla_plana.quad(**caso["params"])
                    dif = fixtures_primitivas.juzgar(m, caso)
                self.assertEqual(dif, [])

    def test_grid_fixture(self):
        casos = fixtures_primitivas.casos("mesh_grid")
        self.assertGreater(len(casos), 0, "debe haber casos de mesh_grid en el fixture")
        for caso in casos:
            with self.subTest(caso.get("nombre") or str(caso.get("params"))):
                if "error" in caso:
                    dif = fixtures_primitivas.juzgar_error(malla_plana.grid, caso)
                else:
                    m = malla_plana.grid(**caso["params"])
                    dif = fixtures_primitivas.juzgar(m, caso)
                self.assertEqual(dif, [])

    def test_disc_fixture(self):
        casos = fixtures_primitivas.casos("mesh_disc")
        self.assertGreater(len(casos), 0, "debe haber casos de mesh_disc en el fixture")
        for caso in casos:
            with self.subTest(caso.get("nombre") or str(caso.get("params"))):
                if "error" in caso:
                    dif = fixtures_primitivas.juzgar_error(malla_plana.disc, caso)
                else:
                    m = malla_plana.disc(**caso["params"])
                    dif = fixtures_primitivas.juzgar(m, caso)
                self.assertEqual(dif, [])

    def test_parametros_invalidos_quad_y_grid(self):
        with self.assertRaises(malla_core.MallaError):
            malla_plana.quad(width=0.0)
        with self.assertRaises(malla_core.MallaError):
            malla_plana.quad(height=-10.0)
        with self.assertRaises(malla_core.MallaError):
            malla_plana.grid(columns=1)
        with self.assertRaises(malla_core.MallaError):
            malla_plana.grid(rows=0)

    def test_parametros_invalidos_disc(self):
        with self.assertRaises(malla_core.MallaError):
            malla_plana.disc(radius=0.0)
        with self.assertRaises(malla_core.MallaError):
            malla_plana.disc(sides=2)
        with self.assertRaises(malla_core.MallaError):
            malla_plana.disc(hole_radius=100.0, radius=50.0)
        with self.assertRaises(malla_core.MallaError):
            malla_plana.disc(start_angle=180.0, end_angle=0.0)

    def test_normales_y_uvs_consistentes(self):
        for m in (malla_plana.quad(), malla_plana.grid(), malla_plana.disc(),
                  malla_plana.disc(hole_radius=30.0)):
            self.assertEqual(len(m.vertices), len(m.normales))
            self.assertEqual(len(m.vertices), len(m.uv0))
            for n in m.normales:
                self.assertEqual(n, (0.0, 0.0, 1.0))
            for u, v in m.uv0:
                self.assertTrue(0.0 <= u <= 1.0, f"u={u} fuera de rango")
                self.assertTrue(0.0 <= v <= 1.0, f"v={v} fuera de rango")


if __name__ == "__main__":
    unittest.main()
