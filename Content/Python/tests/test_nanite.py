from __future__ import annotations

import json
import sys
import types
import unittest
from unittest import mock


unreal = sys.modules.setdefault("unreal", types.ModuleType("unreal"))
if not hasattr(unreal, "TopLevelAssetPath"):
    unreal.TopLevelAssetPath = lambda package, name: (package, name)

from jam import api, graph as graph_module, library, nanite, panel, tools  # noqa: E402
from jam.graph import JamGraph  # noqa: E402


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
    def __init__(self, path, enabled=False, *, vertices=0, triangles=0, uv_channels=1, lods=1):
        self.path = path
        self.settings = _Settings(enabled)
        self.vertices = vertices
        self.triangles = triangles
        self.uv_channels = uv_channels
        self.lods = lods

    def get_path_name(self):
        return self.path

    def get_name(self):
        return self.path.rsplit("/", 1)[-1].split(".", 1)[0]

    def get_editor_property(self, name):
        if name != "nanite_settings":
            raise AttributeError(name)
        return self.settings

    def get_num_nanite_vertices(self):
        return self.vertices

    def get_num_nanite_triangles(self):
        return self.triangles

    def get_num_tex_coords(self, lod):
        if lod < 0 or lod >= self.lods:
            raise ValueError("LOD fuera de rango")
        return self.uv_channels

    def get_num_lods(self):
        return self.lods


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

    def test_analysis_reads_the_public_58_counts_without_modifying_the_mesh(self):
        source_path = "/Game/Props/SM_Rock.SM_Rock"
        source = _Mesh(source_path, enabled=True, vertices=81, triangles=123,
                       uv_channels=2, lods=3)
        with mock.patch.object(library, "cargar_malla", return_value=source), \
                mock.patch.object(
                    unreal, "get_editor_subsystem",
                    side_effect=AssertionError("la lectura 5.8 no necesita subsistema"), create=True):
            result = nanite.analizar(source_path, lod=1)

        self.assertEqual(result, {
            "asset": source_path, "enabled": True, "vertices": 81, "triangles": 123,
            "uv_channels": 2, "lods": 3, "lod": 1,
        })
        self.assertTrue(source.settings.enabled)

    def test_validation_distinguishes_disabled_empty_and_built_nanite(self):
        subsystem = _StaticMeshSubsystem()
        cases = (
            (_Mesh("/Game/Off.Off", enabled=False), False, "deshabilitado"),
            (_Mesh("/Game/Empty.Empty", enabled=True), False, "no tiene vértices"),
            (_Mesh("/Game/Good.Good", enabled=True, vertices=80, triangles=120), True, ""),
        )
        for source, expected, message in cases:
            with self.subTest(asset=source.path), \
                    mock.patch.object(unreal, "StaticMeshEditorSubsystem", object(), create=True), \
                    mock.patch.object(unreal, "get_editor_subsystem", return_value=subsystem, create=True):
                result = nanite.validar(source)
            self.assertIs(result["valido"], expected)
            self.assertIn(message, " ".join(result["diagnosticos"]))

    def test_invalid_lod_is_an_explicit_measurement_error(self):
        source = _Mesh("/Game/Props/SM_Rock.SM_Rock", enabled=True,
                       vertices=81, triangles=123, lods=1)
        with mock.patch.object(unreal, "StaticMeshEditorSubsystem", object(), create=True), \
                mock.patch.object(unreal, "get_editor_subsystem",
                                  return_value=_StaticMeshSubsystem(), create=True):
            result = nanite.analizar(source, lod=3)
        self.assertIn("error", result)
        self.assertIn("LOD fuera de rango", result["error"])

    def test_graph_nodes_are_read_only_asset_passthroughs_with_a_visible_lod(self):
        for verb in ("nanite_analyze", "nanite_validate"):
            with self.subTest(verb=verb):
                info = tools.REGISTRO[verb]
                self.assertEqual(info["in_name"], "A")
                self.assertEqual(info["out_name"], "A")
                self.assertEqual(info["params"], {"lod": 0})
                self.assertTrue(info["asset_required"])
                self.assertIn(verb, tools.SIN_SPAWN)
                self.assertTrue(info["read_only"])

        graph = JamGraph()
        graph.add("asset", {"name": "/Game/Props/SM_Rock.SM_Rock"}, nid="asset")
        graph.add("nanite_analyze", {}, nid="analyze")
        graph.add("nanite_validate", {}, nid="validate")
        graph.connect("asset", "analyze")
        graph.connect("analyze", "validate")
        self.assertTrue(panel._sin_efectos(graph))

        graph.add("nanite", {}, nid="convert")
        graph.connect("validate", "convert")
        self.assertFalse(panel._sin_efectos(graph))

    def test_analyze_publishes_the_same_asset_and_validate_blocks_a_defect(self):
        path = "/Game/Props/SM_Rock.SM_Rock"
        measured = {"asset": path, "enabled": True, "vertices": 80, "triangles": 120,
                    "uv_channels": 2, "lods": 1, "lod": 0}
        with mock.patch.object(nanite, "analizar", return_value=measured):
            text = tools.t_nanite_analyze(path)
        self.assertIn("NANITE ANÁLISIS", text)
        self.assertEqual(tools.dato_producido_runtime("nanite_analyze"), path)

        invalid = {**measured, "enabled": False, "valido": False,
                   "diagnosticos": ["Nanite está deshabilitado"]}
        with mock.patch.object(nanite, "validar", return_value=invalid), \
                self.assertRaisesRegex(RuntimeError, "deshabilitado"):
            tools.t_nanite_validate(path)

    def test_a_read_only_validation_failure_does_not_open_or_replace_preview(self):
        graph = JamGraph()
        graph.add("nanite_validate", {}, nid="validate")

        with mock.patch.object(graph_module, "compilar", return_value=object()), \
                mock.patch.object(
                    graph_module, "ejecutar_detalle",
                    return_value=("[validate] NANITE ✗ — apagado",
                                  {"validate": {"estado": "error", "texto": "apagado"}})), \
                mock.patch.object(
                    panel, "_preview", side_effect=AssertionError("no debe abrir Preview")):
            result = json.loads(api.run_graph_json(graph.to_json()))

        self.assertFalse(result["ok"])
        self.assertFalse(result["preview"])
        self.assertEqual(result["nodes"]["validate"]["estado"], "error")
        self.assertIn("RUN sin efectos", result["report"])


if __name__ == "__main__":
    unittest.main()
