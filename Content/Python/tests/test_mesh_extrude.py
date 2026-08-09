from __future__ import annotations

import math
import sys
import types
import unittest
from unittest import mock


unreal = sys.modules.setdefault("unreal", types.ModuleType("unreal"))
if not hasattr(unreal, "TopLevelAssetPath"):
    unreal.TopLevelAssetPath = lambda package, name: (package, name)

from jam import mesh, mesh_extrude_core, tools  # noqa: E402


class ExtrudeCoreTests(unittest.TestCase):
    def test_normaliza_direccion_y_convierte_cm_por_uv(self):
        config = mesh_extrude_core.configurar(
            distance=300, direction_x=0, direction_y=0, direction_z=2, uv_scale=100)
        self.assertEqual(config.distance, 300.0)
        self.assertEqual(config.direction, (0.0, 0.0, 1.0))
        self.assertEqual(config.uv_factor, 0.01)

    def test_rechaza_distancia_uv_y_direccion_sin_dominio(self):
        for params in (
            {"distance": 0}, {"distance": math.inf}, {"uv_scale": 0},
            {"direction_x": 0, "direction_y": 0, "direction_z": 0},
            {"direction_x": math.nan},
        ):
            with self.subTest(params=params), self.assertRaises(ValueError):
                mesh_extrude_core.configurar(**params)


class ExtrudeAdapterTests(unittest.TestCase):
    class Options:
        def __init__(self):
            self.values = {}

        def set_editor_property(self, name, value):
            self.values[name] = value

    class Queries:
        closed = False

        @classmethod
        def get_is_closed_mesh(cls, _mesh):
            return cls.closed

        @staticmethod
        def get_num_triangle_i_ds(_mesh):
            return 12

    class Modeling:
        calls = []

        @classmethod
        def apply_mesh_linear_extrude_faces(cls, target, options, selection):
            cls.calls.append((target, options, selection))
            ExtrudeAdapterTests.Queries.get_num_triangle_i_ds = staticmethod(lambda _mesh: 52)
            ExtrudeAdapterTests.Queries.closed = True
            return target

    def setUp(self):
        self.Queries.closed = False
        self.Queries.get_num_triangle_i_ds = staticmethod(lambda _mesh: 12)
        self.Modeling.calls = []

    def test_clona_y_traduce_el_contrato_a_geometry_script_58(self):
        source, clone = object(), object()
        normals_calls = []
        enums_direction = types.SimpleNamespace(FIXED_DIRECTION="fixed")
        enums_area = types.SimpleNamespace(ENTIRE_SELECTION="entire")
        with mock.patch.object(mesh, "_clone", return_value=clone), \
             mock.patch.object(mesh, "_info", return_value="malla"), \
             mock.patch.object(unreal, "GeometryScript_MeshQueries", self.Queries, create=True), \
             mock.patch.object(unreal, "GeometryScriptMeshLinearExtrudeOptions",
                               self.Options, create=True), \
             mock.patch.object(unreal, "GeometryScriptLinearExtrudeDirection",
                               enums_direction, create=True), \
             mock.patch.object(unreal, "GeometryScriptPolyOperationArea", enums_area, create=True), \
             mock.patch.object(unreal, "GeometryScriptMeshSelection", object, create=True), \
             mock.patch.object(unreal, "GeometryScript_MeshModeling",
                               self.Modeling, create=True), \
             mock.patch.object(unreal, "Vector", lambda *xyz: xyz, create=True), \
             mock.patch.object(unreal, "GeometryScriptCalculateNormalsOptions", object, create=True), \
             mock.patch.object(unreal, "GeometryScript_Normals",
                               types.SimpleNamespace(
                                   recompute_normals=lambda *args: normals_calls.append(args)),
                               create=True):
            result = mesh.extrude(
                source, distance=250, direction_x=0, direction_y=0, direction_z=5,
                uv_scale=50)

        self.assertIs(result["mesh"], clone)
        self.assertEqual(result["triangles_before"], 12)
        self.assertEqual(result["triangles_after"], 52)
        self.assertEqual(len(self.Modeling.calls), 1)
        target, options, _selection = self.Modeling.calls[0]
        self.assertIs(target, clone)
        self.assertEqual(options.values["distance"], 250.0)
        self.assertEqual(options.values["direction"], (0.0, 0.0, 1.0))
        self.assertEqual(options.values["uv_scale"], 0.02)
        self.assertEqual(options.values["direction_mode"], "fixed")
        self.assertEqual(options.values["area_mode"], "entire")
        self.assertTrue(options.values["solids_to_shells"])
        self.assertEqual(normals_calls[0][0], clone)

    def test_rechaza_malla_cerrada_sin_llamar_la_operacion_ambigua(self):
        self.Queries.closed = True
        with mock.patch.object(mesh, "_clone", return_value=object()), \
             mock.patch.object(unreal, "GeometryScript_MeshQueries", self.Queries, create=True):
            result = mesh.extrude(object())
        self.assertIn("superficie abierta", result["error"])
        self.assertEqual(self.Modeling.calls, [])

    def test_el_verbo_publica_m_a_m_sin_asset(self):
        info = tools.REGISTRO["mesh_extrude"]
        self.assertEqual(info["in_name"], "M")
        self.assertEqual(info["out_name"], "M")
        self.assertFalse(info["asset_required"])
        self.assertEqual(info["params"]["distance"], 300.0)


if __name__ == "__main__":
    unittest.main()
