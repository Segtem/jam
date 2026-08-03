"""Copia Static/Skeletal A → M: contrato puro, adaptador 5.8 y fichas."""

from __future__ import annotations

import json
import sys
import types
import unittest
from unittest import mock

unreal = sys.modules.setdefault("unreal", types.ModuleType("unreal"))
if not hasattr(unreal, "TopLevelAssetPath"):
    unreal.TopLevelAssetPath = lambda package, name: (package, name)

from jam import api, mesh, mesh_copy_core as core, ribbon, tools  # noqa: E402


class _DynamicMesh:
    pass


class _StaticMesh:
    def get_name(self):
        return "StaticFixture"


class _SkeletalMesh:
    def get_name(self):
        return "SkeletalFixture"


class _Struct:
    def __init__(self):
        self.values = {}

    def set_editor_property(self, name, value):
        self.values[name] = value


class _LODType:
    MAX_AVAILABLE = "MAX_AVAILABLE"
    HI_RES_SOURCE_MODEL = "HI_RES_SOURCE_MODEL"
    SOURCE_MODEL = "SOURCE_MODEL"
    RENDER_DATA = "RENDER_DATA"


class CopyCoreTests(unittest.TestCase):
    def test_normalizes_lod_and_options(self):
        result = core.options(lod_type="render", lod_index=2, request_tangents=False)
        self.assertEqual((result.lod_member, result.lod_index), ("RENDER_DATA", 2))
        self.assertFalse(result.request_tangents)

    def test_rejects_invalid_index_and_skeletal_hi_res(self):
        with self.assertRaises(ValueError):
            core.options(lod_index=-1)
        with self.assertRaisesRegex(ValueError, "Static Mesh"):
            core.options(lod_type="hi_res", skeletal=True)


class CopyAdapterTests(unittest.TestCase):
    def _patches(self, utils):
        return (
            mock.patch.object(unreal, "DynamicMesh", _DynamicMesh, create=True),
            mock.patch.object(unreal, "StaticMesh", _StaticMesh, create=True),
            mock.patch.object(unreal, "SkeletalMesh", _SkeletalMesh, create=True),
            mock.patch.object(unreal, "GeometryScript_AssetUtils", utils, create=True),
            mock.patch.object(unreal, "GeometryScriptCopyMeshFromAssetOptions", _Struct,
                              create=True),
            mock.patch.object(unreal, "GeometryScriptMeshReadLOD", _Struct, create=True),
            mock.patch.object(unreal, "GeometryScriptLODType", _LODType, create=True),
            mock.patch.object(mesh, "_info", return_value="24 verts · 44 tris"),
        )

    def test_static_uses_v2_section_materials_and_keeps_sidecar(self):
        calls = []

        class _Utils:
            @staticmethod
            def copy_mesh_from_static_mesh_v2(asset, target, options, lod,
                                              use_section_materials=True):
                calls.append((asset, target, options, lod, use_section_materials))
                return target, "SUCCESS"

            @staticmethod
            def get_section_material_list_from_static_mesh(asset, lod):
                return ["Bark", "Leaf"], [0, 1], ["Bark", "Leaf"], "SUCCESS"

        patches = self._patches(_Utils)
        with patches[0], patches[1], patches[2], patches[3], patches[4], patches[5], \
                patches[6], patches[7]:
            result = mesh.copy_static(_StaticMesh(), lod_type="source", lod_index=2)
            try:
                self.assertNotIn("error", result)
                self.assertTrue(calls[0][-1])
                self.assertEqual(calls[0][3].values["lod_type"], "SOURCE_MODEL")
                self.assertEqual(calls[0][3].values["lod_index"], 2)
                self.assertEqual(mesh._materials(result["mesh"]), ("Bark", "Leaf"))
            finally:
                mesh._MESH_MATERIALS.pop(id(result.get("mesh")), None)

    def test_skeletal_uses_lod_materials_and_wrapper_publishes_m(self):
        class _Utils:
            @staticmethod
            def copy_mesh_from_skeletal_mesh(asset, target, options, lod):
                return target, "SUCCESS"

            @staticmethod
            def get_lod_material_list_from_skeletal_mesh(asset, lod):
                return ["Body"], [0], ["Body"], "SUCCESS"

        patches = self._patches(_Utils)
        with patches[0], patches[1], patches[2], patches[3], patches[4], patches[5], \
                patches[6], patches[7]:
            try:
                text = tools.t_mesh_copy_skeletal(_SkeletalMesh())
                produced = tools.dato_producido_runtime("mesh_copy_skeletal")
                self.assertIn("COPIAR SKELETAL M ✓", text)
                self.assertIsInstance(produced, _DynamicMesh)
                self.assertEqual(mesh._materials(produced), ("Body",))
            finally:
                if tools.dato_producido_runtime("mesh_copy_skeletal") is not None:
                    mesh._MESH_MATERIALS.pop(
                        id(tools.dato_producido_runtime("mesh_copy_skeletal")), None)
                tools.limpiar_asset_producido_runtime("mesh_copy_skeletal")


class CopySpecTests(unittest.TestCase):
    def test_new_nodes_are_typed_and_the_old_id_remains_compatible(self):
        spec = {item["verbo"]: item for item in json.loads(api.spec_all())["tools"]}
        for verb, label in (("mesh_copy_static", "Copiar Static Mesh"),
                            ("mesh_copy_skeletal", "Copiar Skeletal Mesh")):
            self.assertEqual(spec[verb]["label"], label)
            self.assertEqual((spec[verb]["in_name"], spec[verb]["out_name"]), ("A", "M"))
            self.assertEqual(ribbon.grupo_de("Mesh", verb), "Hornear")
        self.assertIn("mesh_from_asset", tools.REGISTRO)
        self.assertEqual(ribbon.grupo_de("Mesh", "mesh_from_asset"), "Compatibilidad")


if __name__ == "__main__":
    unittest.main()
