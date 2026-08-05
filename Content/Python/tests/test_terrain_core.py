from __future__ import annotations

import unittest
from pathlib import Path

from jam import terrain_core


class TerrainCoreTests(unittest.TestCase):
    def test_the_brain_does_not_import_unreal(self):
        source = Path(terrain_core.__file__).read_text(encoding="utf-8")
        self.assertNotIn("import unreal", source)

    def test_a_definition_with_material_is_valid_and_reports_priorities(self):
        data = terrain_core.medida(
            asset="/Game/Terrain/T_Canyon.T_Canyon",
            material="/Game/Materials/M_Rock.M_Rock",
            modifier_priorities=["Erosion", "Noise", "Smooth"])

        self.assertTrue(terrain_core.es_valido(data))
        text = terrain_core.texto_analisis(data)
        self.assertIn("M_Rock", text)
        self.assertIn("3 prioridad(es) de modificador", text)

    def test_no_material_is_a_defect_but_no_modifiers_is_not(self):
        sin_material = terrain_core.medida(
            asset="off", material=None, modifier_priorities=[])
        sin_modificadores = terrain_core.medida(
            asset="on", material="/Game/M.M", modifier_priorities=[])

        self.assertEqual(
            terrain_core.diagnosticar(sin_material), ["la definición no tiene material asignado"])
        self.assertEqual(terrain_core.diagnosticar(sin_modificadores), [])

    def test_a_repeated_modifier_priority_is_corrupt_data_not_a_content_defect(self):
        with self.assertRaisesRegex(ValueError, "Erosion"):
            terrain_core.medida(
                asset="bad", material="/Game/M.M",
                modifier_priorities=["Erosion", "Noise", "Erosion"])

    def test_the_verdict_declares_success_only_with_a_material_assigned(self):
        good = terrain_core.medida(
            asset="good", material="/Game/M.M", modifier_priorities=[])
        bad = terrain_core.medida(
            asset="bad", material=None, modifier_priorities=[])

        self.assertIn("TERRAIN ✓", terrain_core.texto_validacion(good))
        self.assertIn("TERRAIN ✗", terrain_core.texto_validacion(bad))


if __name__ == "__main__":
    unittest.main()
