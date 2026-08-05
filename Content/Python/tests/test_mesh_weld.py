"""Soldar bordes abiertos de DynamicMesh: contrato del adaptador y ficha del Graph.

Nace del caso `casa_madera`: un kit con 17932 piezas —una por triángulo, cero vértices
compartidos— donde `mesh_simplify_count` se quedaba muy por debajo de cualquier objetivo porque un
colapso de aristas no toca un borde abierto. Verificado contra el motor real en
`tools/experiments/verifica_info_limpio_58.py` antes de escribir este archivo.
"""

from __future__ import annotations

import json
import sys
import types
import unittest
from unittest import mock


unreal = sys.modules.setdefault("unreal", types.ModuleType("unreal"))
if not hasattr(unreal, "TopLevelAssetPath"):
    unreal.TopLevelAssetPath = lambda package, name: (package, name)

from jam import api, mesh, ribbon, tools  # noqa: E402


class _DynamicMesh:
    pass


class _Options:
    def __init__(self):
        self.values = {}

    def set_editor_property(self, name, value):
        self.values[name] = value


class WeldAdapterTests(unittest.TestCase):
    def _run(self, **params):
        source = _DynamicMesh()
        cloned = []
        calls = []

        class _MeshEdits:
            @staticmethod
            def append_mesh(target, input_mesh, _transform):
                self.assertIs(input_mesh, source)
                self.assertIsNot(target, source)
                cloned.append(target)

        class _MeshRepair:
            @staticmethod
            def weld_mesh_edges(target, options):
                calls.append((target, options))

        with mock.patch.object(unreal, "DynamicMesh", _DynamicMesh, create=True), \
                mock.patch.object(unreal, "GeometryScript_MeshEdits", _MeshEdits, create=True), \
                mock.patch.object(unreal, "GeometryScript_MeshRepair", _MeshRepair, create=True), \
                mock.patch.object(unreal, "GeometryScriptWeldEdgesOptions", _Options,
                                  create=True), \
                mock.patch.object(unreal, "Transform", return_value=object(), create=True), \
                mock.patch.object(mesh, "_info", return_value="17932 triángulos · 224956 vértices"):
            result = mesh.weld(source, **params)
        self.assertEqual(len(cloned), 1)
        return source, cloned[0], result, calls

    def test_clones_and_calls_weld_mesh_edges_with_the_right_options(self):
        source, result_mesh, result, calls = self._run(
            tolerance_cm=0.5, only_unique_pairs=False)

        self.assertIsNot(result["mesh"], source)
        self.assertIs(result["mesh"], result_mesh)
        target, options = calls[0]
        self.assertIs(target, result_mesh)
        self.assertEqual(options.values["tolerance"], 0.5)
        self.assertIs(options.values["only_unique_pairs"], False)

    def test_defaults_are_the_gentle_tolerance_not_ue_practically_zero(self):
        """El default de Geometry Script (1e-6) no perdona el error de punto flotante de piezas
        colocadas a mano. 0,01 cm (0,1 mm) es el que de verdad suelda algo."""
        _source, _result_mesh, _result, calls = self._run()

        _target, options = calls[0]
        self.assertEqual(options.values["tolerance"], 0.01)
        self.assertIs(options.values["only_unique_pairs"], True)

    def test_invalid_tolerance_does_not_clone_or_call_unreal(self):
        with mock.patch.object(mesh, "_clone") as clone:
            cero = mesh.weld(_DynamicMesh(), tolerance_cm=0)
            negativo = mesh.weld(_DynamicMesh(), tolerance_cm=-0.1)
            no_finito = mesh.weld(_DynamicMesh(), tolerance_cm=float("nan"))
        self.assertIn("error", cero)
        self.assertIn("error", negativo)
        self.assertIn("error", no_finito)
        clone.assert_not_called()

    def test_tool_publishes_the_runtime_m_output(self):
        result_mesh = _DynamicMesh()
        result = {"mesh": result_mesh, "info": "17932 triángulos · 224956 vértices · abierta"}
        try:
            with mock.patch.object(mesh, "weld", return_value=result):
                self.assertIn(" M ✓", tools.t_mesh_weld(_DynamicMesh()))
                self.assertIs(tools.dato_producido_runtime("mesh_weld"), result_mesh)
        finally:
            tools.limpiar_asset_producido_runtime("mesh_weld")


class WeldSpecTests(unittest.TestCase):
    def test_node_is_typed_labeled_and_grouped(self):
        graph_tools = {item["verbo"]: item for item in json.loads(api.spec_all())["tools"]}
        tool = graph_tools["mesh_weld"]

        self.assertEqual(tool["label"], "Soldar bordes")
        self.assertEqual(tool["in_name"], "M")
        self.assertEqual(tool["out_name"], "M")
        self.assertFalse(tool["asset_pin"])
        self.assertEqual(tool["grupo"], "Optimizar")
        self.assertEqual(ribbon.grupo_de("Mesh", "mesh_weld"), "Optimizar")
        # Antes de mesh_simplify_count en el ribbon: se suelda ANTES de simplificar.
        orden = ribbon.GRUPOS["Mesh"]
        verbos_optimizar = next(verbos for nombre, verbos in orden if nombre == "Optimizar")
        self.assertEqual(verbos_optimizar[0], "mesh_weld")


if __name__ == "__main__":
    unittest.main()
