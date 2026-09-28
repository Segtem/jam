"""Tests de los operadores de mallas de la base común contra el fixture del motor.

Comprueba transformar y juntar con el juez de primitivas (`fixtures_primitivas.py`), que compara
triángulo por triángulo y cara frontal contra lo que produjo Unreal Engine 5.8.1.
"""

from __future__ import annotations

import unittest

import fixtures_primitivas
from jam import malla_core, malla_ops


class TestMallaOps(unittest.TestCase):
    def setUp(self):
        self.caja_fixture = malla_core.caja(size_x=100.0, size_y=60.0, size_z=40.0)

    def test_transform_fixture(self):
        casos = fixtures_primitivas.casos("mesh_transform")
        self.assertGreater(len(casos), 0, "debe haber casos de mesh_transform en el fixture")
        for caso in casos:
            with self.subTest(caso.get("nombre") or str(caso.get("params"))):
                if "error" in caso:
                    dif = fixtures_primitivas.juzgar_error(
                        lambda **kw: malla_ops.transformar(self.caja_fixture, **kw), caso)
                else:
                    m = malla_ops.transformar(self.caja_fixture, **caso["params"])
                    dif = fixtures_primitivas.juzgar(m, caso)
                self.assertEqual(dif, [])

    def test_merge_fixture(self):
        casos = fixtures_primitivas.casos("mesh_merge")
        self.assertGreater(len(casos), 0, "debe haber casos de mesh_merge en el fixture")
        otra = malla_ops.transformar(self.caja_fixture, x=200.0, yaw=30.0)
        for caso in casos:
            with self.subTest(caso.get("nombre") or str(caso.get("params"))):
                m = malla_ops.juntar([self.caja_fixture, otra])
                dif = fixtures_primitivas.juzgar(m, caso)
                self.assertEqual(dif, [])

    def test_transform_escala_negativa_mantiene_caras_hacia_afuera(self):
        """Una escala negativa (reflexión) invierte el winding para que no mire hacia adentro."""
        invertida = malla_ops.transformar(self.caja_fixture, scale_x=-1.0)
        centro = (0.0, 0.0, 20.0)
        for tri in invertida.triangulos:
            n = malla_core.cara_frontal(invertida.vertices, tri)
            c = [sum(invertida.vertices[i][k] for i in tri) / 3 - centro[k] for k in range(3)]
            self.assertGreater(sum(n[k] * c[k] for k in range(3)), 0.0,
                               "la cara frontal quedó apuntando hacia adentro tras la reflexión")

    def test_transform_parametros_invalidos(self):
        with self.assertRaises(malla_core.MallaError):
            malla_ops.transformar(self.caja_fixture, scale_y=0.0)
        with self.assertRaises(malla_core.MallaError):
            malla_ops.transformar(self.caja_fixture, z=float("nan"))
        with self.assertRaises(malla_core.MallaError):
            malla_ops.transformar("no_es_malla")  # type: ignore

    def test_juntar_parametros_invalidos(self):
        with self.assertRaises(malla_core.MallaError):
            malla_ops.juntar([])
        with self.assertRaises(malla_core.MallaError):
            malla_ops.juntar([self.caja_fixture])
        with self.assertRaises(malla_core.MallaError):
            malla_ops.juntar([self.caja_fixture, "no_es_malla"])  # type: ignore


if __name__ == "__main__":
    unittest.main()
