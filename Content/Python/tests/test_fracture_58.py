"""Contratos de migración del Dataflow de Fracture a Unreal 5.8.

La autoría de Dataflow cuelga headless y por eso la prueba real es GUI. Este test no la reemplaza:
ata las decisiones forzosamente expresadas en el adaptador para que una refactorización no vuelva
en silencio a los nodos deprecados ni al parche que conservaba sólo el primer material.
"""

from pathlib import Path
import unittest


class Fracture58ContratoTests(unittest.TestCase):
    FUENTE = (Path(__file__).resolve().parents[1] / "jam" / "fracture.py").read_text()

    def test_dataflow_v2_lleva_materiales_hasta_el_terminal(self) -> None:
        # Dos caminos: fuente sólida y metadata paralela de la fuente hueca.
        self.assertEqual(self.FUENTE.count('"FStaticMeshToCollectionDataflowNode_v2"'), 2)
        self.assertIn('"FGeometryCollectionTerminalDataflowNode_v2"', self.FUENTE)
        self.assertIn('_conn(df, meta, "Materials", term, "Materials")', self.FUENTE)
        self.assertNotIn('gc.set_editor_property("materials", [m0, m0])', self.FUENTE)

    def test_la_geometry_collection_hereda_nanite_de_la_malla(self) -> None:
        self.assertIn('gc.set_editor_property("enable_nanite", _usa_nanite(mesh))', self.FUENTE)
        self.assertIn("get_nanite_settings(mesh)", self.FUENTE)


if __name__ == "__main__":
    unittest.main()
