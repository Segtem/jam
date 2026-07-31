"""La sombra de Jam consume Oracle por su fachada pública, no por internals del vendor."""

from __future__ import annotations

import importlib.util
import json
import unittest
from pathlib import Path


RAIZ = Path(__file__).resolve().parents[3]


def _cargar_vault():
    spec = importlib.util.spec_from_file_location("jam_tools_vault", RAIZ / "tools" / "vault.py")
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo


class OracleEmbeddingTests(unittest.TestCase):
    def test_la_sombra_del_vault_usa_el_motor_instalado_en_vendor(self) -> None:
        vault = _cargar_vault()

        informe, motivo = vault.veredicto_del_oraculo()

        self.assertIsNone(motivo)
        self.assertTrue(informe.ok)
        self.assertEqual(10, len(informe.veredictos))
        self.assertTrue(all(v.id.startswith("vault.") for v in informe.veredictos))

    def test_los_fixtures_firman_el_codigo_de_las_escalares(self) -> None:
        for ruta in sorted((RAIZ / "medidas" / "diferencial").glob("*.json")):
            with self.subTest(fixture=ruta.name):
                datos = json.loads(ruta.read_text(encoding="utf-8"))
                self.assertIn(
                    "medidas/escalares.py",
                    datos["frescura"]["fuentes"]["emisor"],
                )


if __name__ == "__main__":
    unittest.main()
