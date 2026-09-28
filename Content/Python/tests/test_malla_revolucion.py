"""Tests de las primitivas de revolución de la base común: cilindro, cono y esfera.

Comprueba todos los casos del fixture `fixtures/primitivas_unreal.json` contra el juez
`fixtures_primitivas.py` (tarea `base-comun`).
"""

from __future__ import annotations

import inspect
import math
import unittest

from jam import malla_core, malla_revolucion, registro
import fixtures_primitivas


class TestFixtureJuez(unittest.TestCase):
    """Evalúa cada caso volcado del motor Unreal contra las funciones del núcleo."""

    def test_cilindro_casos_del_fixture(self):
        casos = fixtures_primitivas.casos("mesh_cylinder")
        self.assertGreater(len(casos), 0, "debe haber casos de mesh_cylinder en el fixture")
        for caso in casos:
            with self.subTest(params=caso["params"]):
                if "error" in caso:
                    dif = fixtures_primitivas.juzgar_error(malla_revolucion.cilindro, caso)
                    self.assertEqual(dif, [])
                else:
                    malla = malla_revolucion.cilindro(**caso["params"])
                    dif = fixtures_primitivas.juzgar(malla, caso)
                    self.assertEqual(dif, [])

    def test_cono_casos_del_fixture(self):
        casos = fixtures_primitivas.casos("mesh_cone")
        self.assertGreater(len(casos), 0, "debe haber casos de mesh_cone en el fixture")
        for caso in casos:
            with self.subTest(params=caso["params"]):
                if "error" in caso:
                    dif = fixtures_primitivas.juzgar_error(malla_revolucion.cono, caso)
                    self.assertEqual(dif, [])
                else:
                    malla = malla_revolucion.cono(**caso["params"])
                    # Con top_radius=0 Geometry Script deja un vértice por lado en el ápice: la cuenta
                    # CRUDA difiere, las posiciones no. El juez compara posiciones desde que agy2 lo
                    # encontró (el volcador guarda las dos), así que el cono se juzga entero.
                    self.assertEqual(fixtures_primitivas.juzgar(malla, caso), [])

    def test_esfera_casos_del_fixture(self):
        casos = fixtures_primitivas.casos("mesh_sphere")
        self.assertGreater(len(casos), 0, "debe haber casos de mesh_sphere en el fixture")
        for caso in casos:
            with self.subTest(params=caso["params"]):
                if "error" in caso:
                    dif = fixtures_primitivas.juzgar_error(malla_revolucion.esfera, caso)
                    self.assertEqual(dif, [])
                else:
                    malla = malla_revolucion.esfera(**caso["params"])
                    dif = fixtures_primitivas.juzgar(malla, caso)
                    self.assertEqual(dif, [])


class TestPropiedadesGeometricas(unittest.TestCase):
    """Comprueba las firmas, normales, winding y UVs."""

    def test_firmas_y_defaults_coinciden_con_registro(self):
        mapeo = {
            "mesh_cylinder": malla_revolucion.cilindro,
            "mesh_cone": malla_revolucion.cono,
            "mesh_sphere": malla_revolucion.esfera,
        }
        for verbo, fn in mapeo.items():
            esperados = registro.REGISTRO[verbo]["params"]
            sig = inspect.signature(fn)
            self.assertEqual(list(sig.parameters), list(esperados), f"Parámetros distintos en {verbo}")
            for nombre, default in esperados.items():
                self.assertEqual(sig.parameters[nombre].default, default, f"Default distinto en {verbo}.{nombre}")

    def test_cilindro_winding_y_normales(self):
        m = malla_revolucion.cilindro(radius=50.0, height=200.0, sides=8, height_steps=2, capped=True)
        # Toda cara frontal apunta hacia afuera
        for tri in m.triangulos:
            f = malla_core.cara_frontal(m.vertices, tri)
            centro_tri = [sum(m.vertices[i][k] for i in tri) / 3.0 for k in range(3)]
            if abs(centro_tri[2] - 0.0) < 1e-4:
                # Tapa inferior: normal hacia -Z
                self.assertLess(f[2], 0.0)
            elif abs(centro_tri[2] - 200.0) < 1e-4:
                # Tapa superior: normal hacia +Z
                self.assertGreater(f[2], 0.0)
            else:
                # Costado: normal radial hacia afuera (f_x * x + f_y * y > 0)
                prod = f[0] * centro_tri[0] + f[1] * centro_tri[1]
                self.assertGreater(prod, 0.0)

    def test_cono_winding_y_normales(self):
        m = malla_revolucion.cono(base_radius=40.0, top_radius=20.0, height=100.0, sides=8, height_steps=2, capped=True)
        for tri in m.triangulos:
            f = malla_core.cara_frontal(m.vertices, tri)
            centro_tri = [sum(m.vertices[i][k] for i in tri) / 3.0 for k in range(3)]
            if abs(centro_tri[2] - 0.0) < 1e-4:
                self.assertLess(f[2], 0.0)
            elif abs(centro_tri[2] - 100.0) < 1e-4:
                self.assertGreater(f[2], 0.0)
            else:
                prod = f[0] * centro_tri[0] + f[1] * centro_tri[1]
                self.assertGreater(prod, 0.0)

    def test_esfera_winding_y_normales(self):
        m = malla_revolucion.esfera(radius=80.0, latitude_steps=6, longitude_steps=8)
        for tri in m.triangulos:
            f = malla_core.cara_frontal(m.vertices, tri)
            centro_tri = [sum(m.vertices[i][k] for i in tri) / 3.0 for k in range(3)]
            # En la esfera centrada en (0,0,0), el vector hacia afuera es centro_tri
            prod = sum(f[k] * centro_tri[k] for k in range(3))
            self.assertGreater(prod, 0.0)

    def test_uv0_en_rango(self):
        for m in (
            malla_revolucion.cilindro(),
            malla_revolucion.cono(),
            malla_revolucion.esfera(),
        ):
            for u, v in m.uv0:
                self.assertTrue(0.0 <= u <= 1.0 + 1e-6, f"u={u} fuera de [0, 1]")
                self.assertTrue(0.0 <= v <= 1.0 + 1e-6, f"v={v} fuera de [0, 1]")

    def test_serializacion_dict(self):
        for m in (
            malla_revolucion.cilindro(),
            malla_revolucion.cono(),
            malla_revolucion.esfera(),
        ):
            d = malla_core.a_dict(m)
            self.assertEqual(set(d), {"vertices", "triangulos", "normales", "uv0"})
            self.assertEqual(len(d["vertices"]), len(d["normales"]))
            self.assertEqual(len(d["vertices"]), len(d["uv0"]))


if __name__ == "__main__":
    unittest.main()
