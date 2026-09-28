"""Tests de la primitiva de tubo (mesh_pipe) de la base común contra el fixture de Unreal.

Comprueba tubo con el juez de primitivas (`fixtures_primitivas.py`), que compara triángulo por
triángulo, posiciones y caras frontales contra lo que produjo Unreal Engine 5.8.1 en
`fixtures/pipe_unreal.json`.
"""

from __future__ import annotations

import json
from pathlib import Path
import unittest

import fixtures_primitivas
from jam import curve, malla_core, malla_tubo

FIXTURE_PIPE = Path(__file__).resolve().parent / "fixtures" / "pipe_unreal.json"


class TestMallaTubo(unittest.TestCase):
    def test_fixture_pipe_unreal(self):
        """Ejecuta TODOS los casos del fixture de pipe_unreal.json contra el juez de primitivas."""
        self.assertTrue(FIXTURE_PIPE.is_file(), f"no existe {FIXTURE_PIPE}")
        datos = json.loads(FIXTURE_PIPE.read_text(encoding="utf-8"))
        casos = datos.get("casos", [])
        self.assertGreater(len(casos), 0, "el fixture pipe_unreal.json debe tener casos")

        for idx, caso in enumerate(casos):
            sub_id = f"caso_{idx}_{caso.get('curva')}_{caso.get('params')}"
            with self.subTest(sub_id):
                curva = curve.CurvePath(tuple(map(tuple, caso["puntos"])))
                if "error" in caso:
                    def _invocar(**params):
                        return malla_tubo.tubo(curva, **params)
                    dif = fixtures_primitivas.juzgar_error(_invocar, caso)
                else:
                    m = malla_tubo.tubo(curva, **caso["params"])
                    dif = fixtures_primitivas.juzgar(m, caso)
                self.assertEqual(dif, [], f"diferencias con el motor en {sub_id}: {dif}")

    def test_radius_from_parent(self):
        """Verifica que radius_from_parent escale el radio inicial respetando la razón de taper."""
        puntos = ((0.0, 0.0, 0.0), (0.0, 0.0, 100.0))
        # Curva con parent_radius = 50.0
        curva_hija = curve.CurvePath(puntos, parent_radius=50.0)
        # radius_start=30, radius_end=15 (razon 0.5)
        # con radius_from_parent=0.8 -> base = 50 * 0.8 = 40.0, punta = 40.0 * 0.5 = 20.0
        m = malla_tubo.tubo(curva_hija, radius_start=30.0, radius_end=15.0, sides=8,
                            radius_from_parent=0.8, capped=True)
        h = malla_core.hechos(m)
        self.assertAlmostEqual(h["min"][0], -40.0, places=2)
        self.assertAlmostEqual(h["max"][0], 40.0, places=2)

    def test_pivot_uvs_param(self):
        """Acepta pivot_uvs=True sin error para compatibilidad de firma con mesh.pipe."""
        curva = curve.CurvePath(((0.0, 0.0, 0.0), (0.0, 0.0, 100.0)))
        m = malla_tubo.tubo(curva, pivot_uvs=True)
        self.assertIsInstance(m, malla_core.Malla)
        self.assertGreater(len(m.triangulos), 0)

    def test_multi_paths_curveset(self):
        """Verifica que un CurveSet con múltiples curvas genere una malla combinada."""
        c1 = curve.CurvePath(((0.0, 0.0, 0.0), (0.0, 0.0, 100.0)))
        c2 = curve.CurvePath(((200.0, 0.0, 0.0), (200.0, 0.0, 100.0)))
        cset = curve.CurveSet((c1, c2))
        m1 = malla_tubo.tubo(c1, sides=6, capped=False)
        m_ambos = malla_tubo.tubo(cset, sides=6, capped=False)
        self.assertEqual(len(m_ambos.triangulos), len(m1.triangulos) * 2)
        self.assertEqual(len(m_ambos.vertices), len(m1.vertices) * 2)

    def test_validaciones_parametros(self):
        curva = curve.CurvePath(((0.0, 0.0, 0.0), (0.0, 0.0, 100.0)))
        with self.assertRaises(malla_core.MallaError):
            malla_tubo.tubo(curva, radius_start=0.0)
        with self.assertRaises(malla_core.MallaError):
            malla_tubo.tubo(curva, radius_start=-5.0)
        with self.assertRaises(malla_core.MallaError):
            malla_tubo.tubo(curva, radius_end=-1.0)
        with self.assertRaises(malla_core.MallaError):
            malla_tubo.tubo(curva, sides=2)
        with self.assertRaises(malla_core.MallaError):
            malla_tubo.tubo(curva, samples=1)
        with self.assertRaises(malla_core.MallaError):
            malla_tubo.tubo(curva, miter_limit=0.5)
        with self.assertRaises(malla_core.MallaError):
            malla_tubo.tubo(curva, radius_from_parent=-0.1)

    def test_curva_invalida(self):
        curva_cero = curve.CurvePath(((10.0, 10.0, 10.0), (10.0, 10.0, 10.0)))
        with self.assertRaises(malla_core.MallaError):
            malla_tubo.tubo(curva_cero)
        with self.assertRaises(malla_core.MallaError):
            malla_tubo.tubo(None)


if __name__ == "__main__":
    unittest.main()
