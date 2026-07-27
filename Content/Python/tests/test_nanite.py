from __future__ import annotations

import sys
import types
import unittest
from unittest import mock


unreal = sys.modules.setdefault("unreal", types.ModuleType("unreal"))
if not hasattr(unreal, "TopLevelAssetPath"):
    unreal.TopLevelAssetPath = lambda package, name: (package, name)

from jam import library, nanite, panel  # noqa: E402


class _Settings:
    def __init__(self, enabled=False):
        self.enabled = bool(enabled)

    def get_editor_property(self, name):
        if name != "enabled":
            raise AttributeError(name)
        return self.enabled

    def set_editor_property(self, name, value):
        if name != "enabled":
            raise AttributeError(name)
        self.enabled = bool(value)


class _Mesh:
    def __init__(self, path, enabled=False):
        self.path = path
        self.settings = _Settings(enabled)

    def get_path_name(self):
        return self.path

    def get_name(self):
        return self.path.rsplit("/", 1)[-1].split(".", 1)[0]


class _StaticMeshSubsystem:
    def get_nanite_settings(self, mesh):
        return mesh.settings

    def set_nanite_settings(self, mesh, settings, apply_changes):
        if not apply_changes:
            raise AssertionError("la conversión debe aplicar el rebuild")
        mesh.settings = settings


class _AssetLibrary:
    def __init__(self):
        self.assets = {}
        self.saved = []

    def does_asset_exist(self, path):
        return path in self.assets

    def delete_asset(self, path):
        self.assets.pop(path, None)
        return True

    def duplicate_asset(self, source, destination):
        if source not in self.assets or destination in self.assets:
            return None
        duplicate = _Mesh(destination, enabled=self.assets[source].settings.enabled)
        self.assets[destination] = duplicate
        return duplicate

    def save_asset(self, path, only_if_is_dirty=False):
        self.saved.append((path, only_if_is_dirty))
        return path in self.assets


class NaniteTests(unittest.TestCase):
    def test_non_nanite_mesh_is_duplicated_and_rebuilt_in_preview(self):
        source_path = "/Game/Props/SM_Rock.SM_Rock"
        temp_path = "/Game/JamPreview/graph/PV_test_SM_Rock_Nanite"
        source = _Mesh(source_path, enabled=False)
        assets = _AssetLibrary()
        assets.assets[source_path] = source
        subsystem = _StaticMeshSubsystem()

        with mock.patch.object(library, "cargar_malla", return_value=source), \
                mock.patch.object(panel, "preview_asset_path", return_value=temp_path), \
                mock.patch.object(panel, "register_preview_asset") as register, \
                mock.patch.object(unreal, "StaticMeshEditorSubsystem", object(), create=True), \
                mock.patch.object(unreal, "get_editor_subsystem", return_value=subsystem, create=True), \
                mock.patch.object(unreal, "EditorAssetLibrary", assets, create=True):
            result = nanite.convertir(source_path)

        self.assertNotIn("error", result)
        self.assertFalse(result["already"])
        self.assertEqual(result["ruta"], temp_path)
        self.assertTrue(result["mesh"].settings.enabled)
        self.assertFalse(source.settings.enabled)
        register.assert_called_once_with(temp_path)

    def test_mesh_that_already_uses_nanite_is_a_passthrough(self):
        source_path = "/Game/Props/SM_Rock.SM_Rock"
        source = _Mesh(source_path, enabled=True)
        assets = _AssetLibrary()
        assets.assets[source_path] = source
        subsystem = _StaticMeshSubsystem()

        with mock.patch.object(library, "cargar_malla", return_value=source), \
                mock.patch.object(unreal, "StaticMeshEditorSubsystem", object(), create=True), \
                mock.patch.object(unreal, "get_editor_subsystem", return_value=subsystem, create=True), \
                mock.patch.object(unreal, "EditorAssetLibrary", assets, create=True):
            result = nanite.convertir(source_path)

        self.assertTrue(result["already"])
        self.assertEqual(result["ruta"], source_path)
        self.assertEqual(set(assets.assets), {source_path})

    def test_final_path_is_stable_and_sanitized(self):
        self.assertEqual(
            nanite.asset_path_for("/Game/My Props/Rock-01.Rock-01"),
            "/Game/Jam/Nanite/Rock_01_Nanite",
        )


if __name__ == "__main__":
    unittest.main()
