from __future__ import annotations

import unittest
from pathlib import Path

from jam import nanite_core


class NaniteCoreTests(unittest.TestCase):
    def test_the_brain_does_not_import_unreal(self):
        source = Path(nanite_core.__file__).read_text(encoding="utf-8")
        self.assertNotIn("import unreal", source)

    def test_a_built_representation_is_valid_and_reports_all_counts(self):
        data = nanite_core.medida(
            asset="/Game/Props/SM_Rock.SM_Rock", enabled=True,
            vertices=80, triangles=120, uv_channels=2, lods=3, lod=1)

        self.assertTrue(nanite_core.es_valido(data))
        text = nanite_core.texto_analisis(data)
        self.assertIn("120 triángulos", text)
        self.assertIn("80 vértices", text)
        self.assertIn("2 canal(es) UV", text)
        self.assertIn("3 LOD(s)", text)

    def test_disabled_and_empty_are_different_defects(self):
        disabled = nanite_core.medida(
            asset="off", enabled=False, vertices=0, triangles=0, uv_channels=1, lods=1)
        empty = nanite_core.medida(
            asset="empty", enabled=True, vertices=0, triangles=0, uv_channels=1, lods=1)

        self.assertEqual(nanite_core.diagnosticar(disabled), ["Nanite está deshabilitado"])
        self.assertEqual(len(nanite_core.diagnosticar(empty)), 2)

    def test_impossible_engine_counts_are_not_misreported_as_content_defects(self):
        with self.assertRaisesRegex(ValueError, "negativos"):
            nanite_core.medida(
                asset="bad", enabled=True, vertices=-1, triangles=2,
                uv_channels=1, lods=1)
        with self.assertRaisesRegex(ValueError, "fuera de rango"):
            nanite_core.medida(
                asset="bad", enabled=True, vertices=1, triangles=2,
                uv_channels=1, lods=1, lod=1)

    def test_the_verdict_declares_success_only_with_real_nanite_data(self):
        good = nanite_core.medida(
            asset="good", enabled=True, vertices=3, triangles=1, uv_channels=0, lods=1)
        bad = nanite_core.medida(
            asset="bad", enabled=True, vertices=0, triangles=0, uv_channels=0, lods=1)

        self.assertIn("NANITE ✓", nanite_core.texto_validacion(good))
        self.assertIn("NANITE ✗", nanite_core.texto_validacion(bad))


if __name__ == "__main__":
    unittest.main()
