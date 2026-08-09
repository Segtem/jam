from __future__ import annotations

import math
import sys
import types
import unittest
from unittest import mock


unreal = sys.modules.setdefault("unreal", types.ModuleType("unreal"))
if not hasattr(unreal, "TopLevelAssetPath"):
    unreal.TopLevelAssetPath = lambda package, name: (package, name)

from jam import mesh, mesh_noise_core, tools  # noqa: E402


class ContratoPerlinTests(unittest.TestCase):
    def test_configuracion_valida_conserva_la_semantica_publica(self):
        config = mesh_noise_core.configurar(
            amplitud=140.0, frecuencia=0.003, seed=1977, por_normal=True)
        self.assertEqual(config.amplitud, 140.0)
        self.assertEqual(config.frecuencia, 0.003)
        self.assertEqual(config.seed, 1977)
        self.assertTrue(config.por_normal)

    def test_rechaza_parametros_que_geometry_script_no_puede_defender(self):
        for params in (
            {"amplitud": -1.0},
            {"amplitud": math.inf},
            {"frecuencia": 0.0},
            {"frecuencia": math.nan},
            {"seed": 2 ** 31},
        ):
            with self.subTest(params=params), self.assertRaises(ValueError):
                mesh_noise_core.configurar(**params)


class AdaptadorPerlinTests(unittest.TestCase):
    class Options:
        def __init__(self):
            self.values = {}

        def set_editor_property(self, name, value):
            self.values[name] = value

    class Mesh:
        def __init__(self):
            self.calls = []

        def apply_perlin_noise_to_mesh2(self, selection, options):
            self.calls.append((selection, options))

    def test_usa_la_api_corregida_de_58_y_no_modifica_la_entrada(self):
        source = object()
        clone = self.Mesh()
        recomputed = []

        class Normals:
            @staticmethod
            def recompute_normals(target, options):
                recomputed.append((target, options))

        with mock.patch.object(mesh, "_clone", return_value=clone), \
             mock.patch.object(mesh, "_info", return_value="malla"), \
             mock.patch.object(unreal, "GeometryScriptPerlinNoiseLayerOptions",
                               self.Options, create=True), \
             mock.patch.object(unreal, "GeometryScriptPerlinNoiseOptions",
                               self.Options, create=True), \
             mock.patch.object(unreal, "GeometryScriptMeshSelection", object, create=True), \
             mock.patch.object(unreal, "GeometryScriptCalculateNormalsOptions", object,
                               create=True), \
             mock.patch.object(unreal, "GeometryScript_Normals", Normals, create=True):
            result = mesh.noise(
                source, amplitud=20.0, frecuencia=0.02, seed=31, por_normal=False)

        self.assertIs(result["mesh"], clone)
        self.assertEqual(len(clone.calls), 1)
        _, options = clone.calls[0]
        layer = options.values["base_layer"]
        self.assertEqual(layer.values,
                         {"magnitude": 20.0, "frequency": 0.02, "random_seed": 31})
        self.assertFalse(options.values["apply_along_normal"])
        self.assertEqual(recomputed[0][0], clone)

    def test_el_verbo_publica_m_a_m_sin_asset(self):
        info = tools.REGISTRO["mesh_noise"]
        self.assertEqual(info["in_name"], "M")
        self.assertEqual(info["out_name"], "M")
        self.assertFalse(info["asset_required"])
        self.assertEqual(info["params"]["frecuencia"], 0.003)


if __name__ == "__main__":
    unittest.main()
