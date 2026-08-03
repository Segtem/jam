"""Material IDs: validación pura, sidecar de slots y contrato del Graph."""

from __future__ import annotations

import json
import sys
import types
import unittest
from unittest import mock


unreal = sys.modules.setdefault("unreal", types.ModuleType("unreal"))
if not hasattr(unreal, "TopLevelAssetPath"):
    unreal.TopLevelAssetPath = lambda package, name: (package, name)

from jam import api, mesh, mesh_material_ids_core as core, ribbon, tools  # noqa: E402


class _DynamicMesh:
    pass


class MaterialIDsCoreTests(unittest.TestCase):
    def test_remap_requires_two_existing_different_ids(self):
        plan = core.remap_plan(3, 0, [0, 3, 3])
        self.assertEqual(plan.used_before, (0, 3))
        self.assertEqual(plan.used_after, (0,))
        with self.assertRaises(ValueError):
            core.remap_plan(3, 3, [0, 3])
        with self.assertRaises(ValueError):
            core.remap_plan(2, 0, [0, 3])
        with self.assertRaises(ValueError):
            core.remap_plan(3, 1, [0, 3])

    def test_compaction_maps_sparse_ids_to_a_dense_range(self):
        self.assertEqual(core.compact_mapping([7, 2, 7, 4]), {2: 0, 4: 1, 7: 2})
        with self.assertRaises(ValueError):
            core.compact_mapping([])


class MaterialIDsAdapterTests(unittest.TestCase):
    def _world(self, ids, compacted_slots=None):
        source = _DynamicMesh()
        cloned = []
        remaps = []
        compactions = []

        class _MeshEdits:
            @staticmethod
            def append_mesh(target, input_mesh, _transform):
                self.assertIs(input_mesh, source)
                cloned.append(target)

        class _IndexList:
            pass

        index_list = _IndexList()

        class _Materials:
            @staticmethod
            def get_all_triangle_material_i_ds(target):
                self.assertIs(target, source)
                return target, index_list, True

            @staticmethod
            def remap_material_i_ds(target, from_id, to_id):
                remaps.append((target, from_id, to_id))

            @staticmethod
            def compact_material_i_ds(target, slots, remove_duplicates):
                compactions.append((target, list(slots), remove_duplicates))
                return target, list(compacted_slots or [])

        class _List:
            @staticmethod
            def convert_index_list_to_array(value):
                self.assertIs(value, index_list)
                return list(ids)

        patches = (
            mock.patch.object(unreal, "DynamicMesh", _DynamicMesh, create=True),
            mock.patch.object(unreal, "GeometryScript_MeshEdits", _MeshEdits, create=True),
            mock.patch.object(unreal, "GeometryScript_Materials", _Materials, create=True),
            mock.patch.object(unreal, "GeometryScript_List", _List, create=True),
            mock.patch.object(unreal, "Transform", return_value=object(), create=True),
            mock.patch.object(mesh, "_info", return_value="Triangles count 24"),
        )
        return source, cloned, remaps, compactions, patches

    def test_remap_clones_and_keeps_the_material_sidecar(self):
        source, cloned, remaps, _compactions, patches = self._world([0, 1, 1])
        material_a, material_b = object(), object()
        mesh._MESH_MATERIALS[id(source)] = (material_a, material_b)
        try:
            with patches[0], patches[1], patches[2], patches[3], patches[4], patches[5]:
                result = mesh.reassign_material_ids(source, from_id=1, to_id=0)
                result_slots = mesh._materials(result.get("mesh"))
        finally:
            mesh._MESH_MATERIALS.pop(id(source), None)
            if cloned:
                mesh._MESH_MATERIALS.pop(id(cloned[0]), None)

        self.assertNotIn("error", result)
        self.assertIsNot(result["mesh"], source)
        self.assertEqual(remaps, [(cloned[0], 1, 0)])
        self.assertEqual(result_slots, (material_a, material_b))
        self.assertIn("2→1 IDs usados", result["info"])

    def test_clean_compacts_ids_and_the_corresponding_slots(self):
        material_a, unused, material_b = object(), object(), object()
        source, cloned, _remaps, compactions, patches = self._world(
            [0, 2, 2], compacted_slots=[material_a, material_b])
        mesh._MESH_MATERIALS[id(source)] = (material_a, unused, material_b)
        try:
            with patches[0], patches[1], patches[2], patches[3], patches[4], patches[5]:
                result = mesh.clean_material_ids(source)
                result_slots = mesh._materials(result.get("mesh"))
        finally:
            mesh._MESH_MATERIALS.pop(id(source), None)
            if cloned:
                mesh._MESH_MATERIALS.pop(id(cloned[0]), None)

        self.assertNotIn("error", result)
        self.assertEqual(compactions, [(cloned[0], [material_a, unused, material_b], True)])
        self.assertEqual(result_slots, (material_a, material_b))
        self.assertIn("IDs [0, 2]→[0, 1]", result["info"])
        self.assertIn("slots 3→2", result["info"])

    def test_invalid_remap_does_not_clone_or_mutate(self):
        with mock.patch.object(mesh, "_material_ids", return_value=[0, 2]), \
                mock.patch.object(mesh, "_clone") as clone, \
                mock.patch.object(unreal, "GeometryScript_Materials", create=True) as materials:
            result = mesh.reassign_material_ids(_DynamicMesh(), from_id=2, to_id=1)
        self.assertIn("error", result)
        clone.assert_not_called()
        materials.remap_material_i_ds.assert_not_called()

    def test_wrappers_publish_runtime_m_outputs(self):
        output = _DynamicMesh()
        try:
            with mock.patch.object(mesh, "reassign_material_ids",
                                   return_value={"mesh": output, "info": "ok"}):
                self.assertIn(" M ✓", tools.t_mesh_remap_materials(_DynamicMesh()))
                self.assertIs(tools.dato_producido_runtime("mesh_remap_materials"), output)
            with mock.patch.object(mesh, "clean_material_ids",
                                   return_value={"mesh": output, "info": "ok"}):
                self.assertIn(" M ✓", tools.t_mesh_clean_material_ids(_DynamicMesh()))
                self.assertIs(tools.dato_producido_runtime("mesh_clean_material_ids"), output)
        finally:
            tools.limpiar_asset_producido_runtime("mesh_remap_materials")
            tools.limpiar_asset_producido_runtime("mesh_clean_material_ids")


class MaterialIDsSpecTests(unittest.TestCase):
    def test_nodes_are_m_to_m_and_live_in_materials(self):
        spec = {item["verbo"]: item for item in json.loads(api.spec_all())["tools"]}
        expected = {
            "mesh_remap_materials": "Reasignar IDs de material",
            "mesh_clean_material_ids": "Limpiar IDs de material",
        }
        for verb, label in expected.items():
            with self.subTest(verb=verb):
                tool = spec[verb]
                self.assertEqual(tool["label"], label)
                self.assertEqual((tool["in_name"], tool["out_name"]), ("M", "M"))
                self.assertFalse(tool["asset_pin"])
                self.assertEqual(tool["grupo"], "Materiales")
                self.assertEqual(ribbon.grupo_de("Mesh", verb), "Materiales")
        self.assertEqual(ribbon.grupo_de("Mesh", "mesh_material"), "Materiales")


if __name__ == "__main__":
    unittest.main()
