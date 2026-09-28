"""Tests de las formas de la base común: triángulo, cápsula, toro, rectángulo
redondeado, escalera lineal, escalera curva y esfera de topología cúbica.

Comprueba todos los casos del fixture `fixtures/primitivas_unreal.json` contra el juez
`fixtures_primitivas.py` (tarea `base-comun`).
"""

from __future__ import annotations

import inspect
import math
import unittest

from jam import malla_core, malla_formas, registro
import fixtures_primitivas


class TestFixtureJuez(unittest.TestCase):
    """Evalúa cada caso volcado del motor Unreal contra las funciones del núcleo."""

    def test_triangulo_casos_del_fixture(self):
        casos = fixtures_primitivas.casos("mesh_triangle")
        self.assertGreater(len(casos), 0, "debe haber casos de mesh_triangle en el fixture")
        for caso in casos:
            with self.subTest(params=caso["params"]):
                if "error" in caso:
                    dif = fixtures_primitivas.juzgar_error(malla_formas.triangulo, caso)
                    self.assertEqual(dif, [])
                else:
                    malla = malla_formas.triangulo(**caso["params"])
                    dif = fixtures_primitivas.juzgar(malla, caso)
                    self.assertEqual(dif, [])

    def test_capsula_casos_del_fixture(self):
        casos = fixtures_primitivas.casos("mesh_capsule")
        self.assertGreater(len(casos), 0, "debe haber casos de mesh_capsule en el fixture")
        for caso in casos:
            with self.subTest(params=caso["params"]):
                if "error" in caso:
                    dif = fixtures_primitivas.juzgar_error(malla_formas.capsula, caso)
                    self.assertEqual(dif, [])
                else:
                    malla = malla_formas.capsula(**caso["params"])
                    dif = fixtures_primitivas.juzgar(malla, caso)
                    self.assertEqual(dif, [])

    def test_toro_casos_del_fixture(self):
        casos = fixtures_primitivas.casos("mesh_torus")
        self.assertGreater(len(casos), 0, "debe haber casos de mesh_torus en el fixture")
        for caso in casos:
            with self.subTest(params=caso["params"]):
                if "error" in caso:
                    dif = fixtures_primitivas.juzgar_error(malla_formas.toro, caso)
                    self.assertEqual(dif, [])
                else:
                    malla = malla_formas.toro(**caso["params"])
                    dif = fixtures_primitivas.juzgar(malla, caso)
                    self.assertEqual(dif, [])

    def test_rect_redondeado_casos_del_fixture(self):
        casos = fixtures_primitivas.casos("mesh_round_rect")
        self.assertGreater(len(casos), 0, "debe haber casos de mesh_round_rect en el fixture")
        for caso in casos:
            with self.subTest(params=caso["params"]):
                if "error" in caso:
                    dif = fixtures_primitivas.juzgar_error(malla_formas.rect_redondeado, caso)
                    self.assertEqual(dif, [])
                else:
                    malla = malla_formas.rect_redondeado(**caso["params"])
                    dif = fixtures_primitivas.juzgar(malla, caso)
                    self.assertEqual(dif, [])

    def test_escalera_casos_del_fixture(self):
        casos = fixtures_primitivas.casos("mesh_stairs")
        self.assertGreater(len(casos), 0, "debe haber casos de mesh_stairs en el fixture")
        for caso in casos:
            with self.subTest(params=caso["params"]):
                if "error" in caso:
                    dif = fixtures_primitivas.juzgar_error(malla_formas.escalera, caso)
                    self.assertEqual(dif, [])
                else:
                    malla = malla_formas.escalera(**caso["params"])
                    dif = fixtures_primitivas.juzgar(malla, caso)
                    self.assertEqual(dif, [])

    def test_escalera_curva_casos_del_fixture(self):
        casos = fixtures_primitivas.casos("mesh_stairs_curved")
        self.assertGreater(len(casos), 0, "debe haber casos de mesh_stairs_curved en el fixture")
        for caso in casos:
            with self.subTest(params=caso["params"]):
                if "error" in caso:
                    dif = fixtures_primitivas.juzgar_error(malla_formas.escalera_curva, caso)
                    self.assertEqual(dif, [])
                else:
                    malla = malla_formas.escalera_curva(**caso["params"])
                    dif = fixtures_primitivas.juzgar(malla, caso)
                    self.assertEqual(dif, [])

    def test_esfera_caja_casos_del_fixture(self):
        casos = fixtures_primitivas.casos("mesh_sphere_box")
        self.assertGreater(len(casos), 0, "debe haber casos de mesh_sphere_box en el fixture")
        for caso in casos:
            with self.subTest(params=caso["params"]):
                if "error" in caso:
                    dif = fixtures_primitivas.juzgar_error(malla_formas.esfera_caja, caso)
                    self.assertEqual(dif, [])
                else:
                    malla = malla_formas.esfera_caja(**caso["params"])
                    dif = fixtures_primitivas.juzgar(malla, caso)
                    self.assertEqual(dif, [])


class TestPropiedadesGeometricas(unittest.TestCase):
    """Comprueba las firmas, normales, winding y UVs."""

    def test_firmas_y_defaults_coinciden_con_registro(self):
        mapeo = {
            "mesh_triangle": malla_formas.triangulo,
            "mesh_capsule": malla_formas.capsula,
            "mesh_torus": malla_formas.toro,
            "mesh_round_rect": malla_formas.rect_redondeado,
            "mesh_stairs": malla_formas.escalera,
            "mesh_stairs_curved": malla_formas.escalera_curva,
            "mesh_sphere_box": malla_formas.esfera_caja,
        }
        for verbo, fn in mapeo.items():
            esperados = registro.REGISTRO[verbo]["params"]
            sig = inspect.signature(fn)
            self.assertEqual(list(sig.parameters), list(esperados), f"Parámetros distintos en {verbo}")
            for nombre, default in esperados.items():
                self.assertEqual(sig.parameters[nombre].default, default, f"Default distinto en {verbo}.{nombre}")

    def test_triangulo_winding_y_normal(self):
        m = malla_formas.triangulo(size=50.0)
        self.assertEqual(len(m.triangulos), 1)
        f = malla_core.cara_frontal(m.vertices, m.triangulos[0])
        self.assertGreater(f[2], 0.0)

    def test_capsula_winding(self):
        m = malla_formas.capsula(radius=20.0, length=50.0, hemisphere_steps=3, sides=8)
        for tri in m.triangulos:
            f = malla_core.cara_frontal(m.vertices, tri)
            c = [sum(m.vertices[i][k] for i in tri) / 3.0 for k in range(3)]
            # Si está en el casquete superior (z > 70)
            if c[2] > 70.0:
                self.assertGreater(f[2], 0.0)
            elif c[2] < 20.0:
                self.assertLess(f[2], 0.0)
            else:
                self.assertGreater(f[0] * c[0] + f[1] * c[1], 0.0)

    def test_toro_winding(self):
        m = malla_formas.toro(major_radius=50.0, minor_radius=15.0, major_steps=8, minor_steps=6)
        for tri in m.triangulos:
            f = malla_core.cara_frontal(m.vertices, tri)
            c = [sum(m.vertices[i][k] for i in tri) / 3.0 for k in range(3)]
            th = math.atan2(c[1], c[0])
            c_tubo = (50.0 * math.cos(th), 50.0 * math.sin(th), 0.0)
            radial = [c[k] - c_tubo[k] for k in range(3)]
            self.assertGreater(malla_core._punto(f, radial), 0.0)

    def test_esfera_caja_winding(self):
        m = malla_formas.esfera_caja(radius=50.0, steps=3)
        for tri in m.triangulos:
            f = malla_core.cara_frontal(m.vertices, tri)
            c = [sum(m.vertices[i][k] for i in tri) / 3.0 for k in range(3)]
            self.assertGreater(malla_core._punto(f, c), 0.0)

    def test_uv0_en_rango(self):
        mallas = [
            malla_formas.triangulo(),
            malla_formas.capsula(),
            malla_formas.toro(),
            malla_formas.rect_redondeado(),
            malla_formas.escalera(),
            malla_formas.escalera_curva(),
            malla_formas.esfera_caja(),
        ]
        for m in mallas:
            for u, v in m.uv0:
                self.assertTrue(-1e-6 <= u <= 1.0 + 1e-6, f"u={u} fuera de [0, 1]")
                self.assertTrue(-1e-6 <= v <= 1.0 + 1e-6, f"v={v} fuera de [0, 1]")

    def test_serializacion_dict(self):
        mallas = [
            malla_formas.triangulo(),
            malla_formas.capsula(),
            malla_formas.toro(),
            malla_formas.rect_redondeado(),
            malla_formas.escalera(),
            malla_formas.escalera_curva(),
            malla_formas.esfera_caja(),
        ]
        for m in mallas:
            d = malla_core.a_dict(m)
            self.assertEqual(set(d), {"vertices", "triangulos", "normales", "uv0"})
            self.assertEqual(len(d["vertices"]), len(d["normales"]))
            self.assertEqual(len(d["vertices"]), len(d["uv0"]))


if __name__ == "__main__":
    unittest.main()
