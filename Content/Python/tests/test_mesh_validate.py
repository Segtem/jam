"""Diagnóstico de malla: hechos puros, sensor UE y ficha M → M."""

from __future__ import annotations

import json
import sys
import types
import unittest
from unittest import mock

unreal = sys.modules.setdefault("unreal", types.ModuleType("unreal"))
if not hasattr(unreal, "TopLevelAssetPath"):
    unreal.TopLevelAssetPath = lambda package, name: (package, name)

from jam import api, mesh, mesh_validate_core as core, ribbon, tools  # noqa: E402


class _DynamicMesh:
    pass


class ValidateCoreTests(unittest.TestCase):
    FACTS = core.MeshFacts(24, 44, True, False, 1, False, 1, 1, (0,), 1)

    def test_defaults_accept_a_healthy_open_mesh(self):
        self.assertEqual(core.judge(self.FACTS), ())
        self.assertIn("24 verts", core.summary(self.FACTS))

    def test_each_explicit_requirement_discriminates(self):
        self.assertIn("malla abierta", core.judge(self.FACTS, require_closed=True)[0])
        self.assertIn("componentes", core.judge(
            self.FACTS.__class__(**{**self.FACTS.__dict__, "components": 3}),
            max_components=1)[0])
        no_uv = self.FACTS.__class__(**{**self.FACTS.__dict__, "uv_channels": 0})
        self.assertIn("sin canales UV", core.judge(no_uv, require_uv=True))
        no_material = self.FACTS.__class__(
            **{**self.FACTS.__dict__, "material_ids": (), "material_slots": 0})
        self.assertIn("sin Material IDs/slots verificables",
                      core.judge(no_material, require_materials=True))


class ValidateAdapterTests(unittest.TestCase):
    def test_sensor_passes_the_same_mesh_and_reports_facts(self):
        dynamic = _DynamicMesh()

        class _Queries:
            get_vertex_count = staticmethod(lambda _m: 24)
            get_num_triangle_i_ds = staticmethod(lambda _m: 44)
            get_is_dense_mesh = staticmethod(lambda _m: True)
            get_is_closed_mesh = staticmethod(lambda _m: False)
            get_num_open_border_loops = staticmethod(lambda _m: (1, False))
            get_num_connected_components = staticmethod(lambda _m: 1)
            get_num_uv_sets = staticmethod(lambda _m: 1)

        with mock.patch.object(unreal, "DynamicMesh", _DynamicMesh, create=True), \
                mock.patch.object(unreal, "GeometryScript_MeshQueries", _Queries, create=True), \
                mock.patch.object(mesh, "_material_ids", return_value=[0]), \
                mock.patch.object(mesh, "_materials", return_value=(object(),)):
            result = mesh.validate(dynamic)
            closed = mesh.validate(dynamic, require_closed=True)

        self.assertTrue(result["ok"])
        self.assertIs(result["mesh"], dynamic)
        self.assertFalse(closed["ok"])
        self.assertIn("malla abierta", closed["defects"][0])

    def test_wrapper_marks_a_failed_requirement_and_publishes_m(self):
        dynamic = _DynamicMesh()
        response = {"mesh": dynamic, "ok": False, "defects": ("malla abierta",),
                    "info": "24 verts"}
        try:
            with mock.patch.object(mesh, "validate", return_value=response):
                text = tools.t_mesh_validate(dynamic, require_closed=True)
            self.assertIn("VALIDAR M ✗", text)
            self.assertIs(tools.dato_producido_runtime("mesh_validate"), dynamic)
        finally:
            tools.limpiar_asset_producido_runtime("mesh_validate")


class ValidateSpecTests(unittest.TestCase):
    def test_node_is_labeled_typed_and_grouped(self):
        tool = next(item for item in json.loads(api.spec_all())["tools"]
                    if item["verbo"] == "mesh_validate")
        self.assertEqual(tool["label"], "Validar malla")
        self.assertEqual((tool["in_name"], tool["out_name"]), ("M", "M"))
        self.assertEqual(tool["grupo"], "Hornear")
        self.assertEqual(ribbon.grupo_de("Mesh", "mesh_validate"), "Hornear")


if __name__ == "__main__":
    unittest.main()
