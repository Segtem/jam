"""Guarda el extractor de `tools/check_unreal_api.py` y los nombres que YA nos mordieron.

El verificador de verdad necesita un editor vivo (`UnrealEditor-Cmd -run=pythonscript`). Lo que sí se
puede probar headless es que el extractor encuentre las llamadas, y que no vuelvan a colarse las
formas mal manglelizadas que rompieron un Run real: `UVs` se parte en `U`+`Vs` y `IDs` en `I`+`Ds`.
"""

from __future__ import annotations

import importlib.util
import sys
import tempfile
import types
import unittest
from pathlib import Path

_unreal_fake = sys.modules.setdefault("unreal", types.ModuleType("unreal"))
if not hasattr(_unreal_fake, "TopLevelAssetPath"):
    _unreal_fake.TopLevelAssetPath = lambda package, name: (package, name)

PLUGIN_ROOT = Path(__file__).resolve().parents[3]
JAM = PLUGIN_ROOT / "Content" / "Python" / "jam"


def _checker():
    ruta = PLUGIN_ROOT / "tools" / "check_unreal_api.py"
    spec = importlib.util.spec_from_file_location("check_unreal_api", ruta)
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo


class ExtractorTests(unittest.TestCase):
    def test_finds_calls_with_their_file_and_line(self):
        checker = _checker()
        encontrado = checker.llamadas(JAM)

        self.assertGreater(len(encontrado), 30)
        self.assertIn(("GeometryScript_UVs", "scale_mesh_u_vs"), encontrado)
        self.assertIn(("GeometryScript_MeshEdits", "append_mesh"), encontrado)
        lugares = encontrado[("GeometryScript_UVs", "scale_mesh_u_vs")]
        self.assertTrue(all(":" in lugar for lugar in lugares), lugares)
        self.assertTrue(any(lugar.startswith("mesh.py:") for lugar in lugares), lugares)

    def test_finds_module_functions_constructors_types_and_enums(self):
        checker = _checker()
        encontrado = checker.simbolos(JAM)

        self.assertGreater(len(encontrado), 50)
        for simbolo in (
                "get_editor_subsystem", "Vector", "DynamicMesh", "TraceTypeQuery"):
            self.assertIn(simbolo, encontrado)
            self.assertTrue(all(":" in lugar for lugar in encontrado[simbolo]))

    def test_ignores_complete_comments(self):
        checker = _checker()
        with tempfile.TemporaryDirectory() as temporal:
            fuente = Path(temporal) / "sonda.py"
            fuente.write_text(
                "# unreal.ClaseInventada.metodo\nvalor = unreal.Vector()\n",
                encoding="utf-8",
            )
            encontrado = checker.simbolos(Path(temporal))

        self.assertNotIn("ClaseInventada", encontrado)
        self.assertIn("Vector", encontrado)


class ManglerTests(unittest.TestCase):
    """Los tres nombres que la suite mockeada dejó pasar y explotaron en un Run real."""

    ROTOS = (
        "scale_mesh_uvs",       # es scale_mesh_u_vs
        "translate_mesh_uvs",   # es translate_mesh_u_vs
        "rotate_mesh_uvs",      # es rotate_mesh_u_vs
        "recompute_mesh_uvs",   # es recompute_mesh_u_vs
        "clear_material_ids",   # es clear_material_i_ds
        "remap_material_ids",   # es remap_material_i_ds
        "compact_material_ids",
        "set_all_triangle_material_ids",
        "get_max_material_id",  # este SÍ es correcto: `ID` suelto no se parte
    )
    # `get_max_material_id` queda fuera: es la forma buena, sirve para no volverse paranoico.
    PROHIBIDOS = tuple(nombre for nombre in ROTOS if nombre != "get_max_material_id")

    def test_no_source_file_uses_a_wrongly_mangled_name(self):
        ofensas = []
        for archivo in sorted(JAM.glob("*.py")):
            texto = archivo.read_text(encoding="utf-8")
            for numero, linea in enumerate(texto.splitlines(), 1):
                if linea.lstrip().startswith("#"):
                    continue
                for malo in self.PROHIBIDOS:
                    if malo in linea:
                        ofensas.append(f"{archivo.name}:{numero} usa «{malo}»")
        self.assertEqual(ofensas, [], "\n".join(ofensas))

    def test_the_stubs_of_the_suite_use_the_same_names_as_the_engine(self):
        # Si un stub se escribe con el nombre malo, el test verde vuelve a mentir.
        tests_dir = Path(__file__).resolve().parent
        ofensas = []
        for archivo in sorted(tests_dir.glob("test_*.py")):
            if archivo.name == Path(__file__).name:
                continue
            for numero, linea in enumerate(
                    archivo.read_text(encoding="utf-8").splitlines(), 1):
                for malo in self.PROHIBIDOS:
                    if malo in linea:
                        ofensas.append(f"{archivo.name}:{numero} usa «{malo}»")
        self.assertEqual(ofensas, [], "\n".join(ofensas))


if __name__ == "__main__":
    unittest.main()
