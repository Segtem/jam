"""Simplificación de DynamicMesh: contrato puro, adaptador UE y ficha del Graph."""

from __future__ import annotations

import json
import sys
import types
import unittest
from unittest import mock


unreal = sys.modules.setdefault("unreal", types.ModuleType("unreal"))
if not hasattr(unreal, "TopLevelAssetPath"):
    unreal.TopLevelAssetPath = lambda package, name: (package, name)

from jam import api, mesh, mesh_simplify_core as core, ribbon, tools  # noqa: E402


class _DynamicMesh:
    pass


class _Options:
    def __init__(self):
        self.values = {}

    def set_editor_property(self, name, value):
        self.values[name] = value


class SimplifyCoreTests(unittest.TestCase):
    def test_ue_58_methods_are_explicit_and_attribute_v2_is_the_default(self):
        self.assertEqual(core.options().method_member, "ATTRIBUTE_AWARE_V2")
        self.assertEqual(core.options(method="normals").method_member, "ATTRIBUTE_AWARE")
        self.assertEqual(core.options(method="volume").method_member, "VOLUME_PRESERVING")
        self.assertEqual(core.options(method="standard").method_member, "STANDARD_QEM")

    def test_contract_rejects_ambiguous_or_non_finite_targets(self):
        for value in (0, -1, True, 2.5, float("inf")):
            with self.subTest(value=value), self.assertRaises(ValueError):
                core.triangle_target(value)
        for value in (0, -0.1, float("nan"), float("inf")):
            with self.subTest(value=value), self.assertRaises(ValueError):
                core.distance(value, "tolerance_cm")
        with self.assertRaises(ValueError):
            core.options(method="magic")
        with self.assertRaises(ValueError):
            core.options(regularize=10.1)


class SimplifyAdapterTests(unittest.TestCase):
    def _run(self, function, **params):
        source = _DynamicMesh()
        cloned = []
        calls = []

        class _MeshEdits:
            @staticmethod
            def append_mesh(target, input_mesh, _transform):
                self.assertIs(input_mesh, source)
                self.assertIsNot(target, source)
                cloned.append(target)

        class _Simplification:
            @staticmethod
            def apply_simplify_to_triangle_count(target, value, options):
                calls.append(("count", target, value, options))

            @staticmethod
            def apply_simplify_to_tolerance(target, value, options):
                calls.append(("tolerance", target, value, options))

            @staticmethod
            def apply_simplify_to_edge_length(target, value, options):
                calls.append(("edge", target, value, options))

        enum = types.SimpleNamespace(
            STANDARD_QEM="standard", VOLUME_PRESERVING="volume",
            ATTRIBUTE_AWARE="normals", ATTRIBUTE_AWARE_V2="attributes")
        with mock.patch.object(unreal, "DynamicMesh", _DynamicMesh, create=True), \
                mock.patch.object(unreal, "GeometryScript_MeshEdits", _MeshEdits, create=True), \
                mock.patch.object(unreal, "GeometryScript_MeshSimplification", _Simplification,
                                  create=True), \
                mock.patch.object(unreal, "GeometryScriptSimplifyMeshOptions", _Options,
                                  create=True), \
                mock.patch.object(unreal, "GeometryScriptRemoveMeshSimplificationType", enum,
                                  create=True), \
                mock.patch.object(unreal, "Transform", return_value=object(), create=True), \
                mock.patch.object(mesh, "_info", return_value="Triangles count 40"):
            result = function(source, **params)
        self.assertEqual(len(cloned), 1)
        return source, cloned[0], result, calls

    def test_all_three_operations_clone_and_call_the_matching_ue_api(self):
        cases = (
            (mesh.simplify_count, {"target_triangles": 40}, "count", 40),
            (mesh.simplify_tolerance, {"tolerance_cm": 1.5}, "tolerance", 1.5),
            (mesh.simplify_edge_length, {"edge_length_cm": 7.5}, "edge", 7.5),
        )
        for function, params, operation, expected in cases:
            with self.subTest(operation=operation):
                source, result_mesh, result, calls = self._run(function, **params)
                self.assertIsNot(result["mesh"], source)
                self.assertIs(result["mesh"], result_mesh)
                self.assertEqual(calls[0][0:3], (operation, result_mesh, expected))
                options = calls[0][3].values
                self.assertEqual(options["method"], "attributes")
                self.assertFalse(options["allow_seam_collapse"])
                self.assertFalse(options["allow_seam_smoothing"])
                self.assertFalse(options["allow_seam_splits"])
                self.assertTrue(options["auto_compact"])

    def test_invalid_parameters_do_not_clone_or_call_unreal(self):
        with mock.patch.object(mesh, "_clone") as clone:
            result = mesh.simplify_count(_DynamicMesh(), target_triangles=0)
            bad_method = mesh.simplify_tolerance(_DynamicMesh(), method="magic")
            bad_distance = mesh.simplify_edge_length(_DynamicMesh(), edge_length_cm=0)
        self.assertIn("error", result)
        self.assertIn("error", bad_method)
        self.assertIn("error", bad_distance)
        clone.assert_not_called()

    def test_tools_publish_each_runtime_m_output(self):
        result_mesh = _DynamicMesh()
        result = {"mesh": result_mesh, "info": "Triangles count 40"}
        cases = (
            ("mesh_simplify_count", tools.t_mesh_simplify_count, "simplify_count"),
            ("mesh_simplify_tolerance", tools.t_mesh_simplify_tolerance, "simplify_tolerance"),
            ("mesh_simplify_edge_length", tools.t_mesh_simplify_edge_length,
             "simplify_edge_length"),
        )
        try:
            for verb, wrapper, adapter in cases:
                with self.subTest(verb=verb), mock.patch.object(mesh, adapter,
                                                               return_value=result):
                    self.assertIn(" M ✓", wrapper(_DynamicMesh()))
                    self.assertIs(tools.dato_producido_runtime(verb), result_mesh)
        finally:
            for verb, _wrapper, _adapter in cases:
                tools.limpiar_asset_producido_runtime(verb)


class SimplifySpecTests(unittest.TestCase):
    VERBS = ("mesh_simplify_count", "mesh_simplify_tolerance",
             "mesh_simplify_edge_length")

    def test_nodes_are_typed_labeled_and_grouped(self):
        graph_tools = {item["verbo"]: item for item in json.loads(api.spec_all())["tools"]}
        expected_labels = {
            "mesh_simplify_count": "Simplificar por triángulos",
            "mesh_simplify_tolerance": "Simplificar por tolerancia",
            "mesh_simplify_edge_length": "Simplificar por arista",
        }
        for verb in self.VERBS:
            with self.subTest(verb=verb):
                tool = graph_tools[verb]
                self.assertEqual(tool["label"], expected_labels[verb])
                self.assertEqual(tool["in_name"], "M")
                self.assertEqual(tool["out_name"], "M")
                self.assertFalse(tool["asset_pin"])
                self.assertEqual(tool["grupo"], "Optimizar")
                self.assertEqual(ribbon.grupo_de("Mesh", verb), "Optimizar")
                method = next(p for p in tool["params"] if p["nombre"] == "method")
                self.assertEqual(method["label"], "métrica")
                self.assertEqual(method["opciones"],
                                 ["attributes", "normals", "volume", "standard"])


if __name__ == "__main__":
    unittest.main()
