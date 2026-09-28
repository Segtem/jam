"""El instalador (`tools/instalar.py`): reconoce el motor y deja el proyecto configurado, sin pisar
nada y sin duplicar al correrlo dos veces."""

from __future__ import annotations

import importlib.util
import tempfile
import unittest
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[3]
_spec = importlib.util.spec_from_file_location("instalar", RAIZ / "tools" / "instalar.py")
instalar = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(instalar)

GODOT = 'config_version=5\n\n[application]\n\nconfig/name="P"\n'


class Godot(unittest.TestCase):
    def test_activa_el_plugin_y_escribe_la_seccion_jam(self):
        t = instalar.configurar_godot(GODOT, "/n", "/usr/bin/python3")
        self.assertIn('enabled=PackedStringArray("res://addons/jam/plugin.cfg")', t)
        self.assertIn('nucleo_python="/n"', t)
        self.assertIn('python="/usr/bin/python3"', t)

    def test_dos_veces_da_lo_mismo(self):
        una = instalar.configurar_godot(GODOT, "/n", "/p")
        self.assertEqual(instalar.configurar_godot(una, "/n", "/p"), una)

    def test_respeta_otros_plugins(self):
        t = GODOT + '\n[editor_plugins]\n\nenabled=PackedStringArray("res://addons/otro/plugin.cfg")\n'
        r = instalar.configurar_godot(t, "/n", "/p")
        self.assertIn('"res://addons/otro/plugin.cfg", "res://addons/jam/plugin.cfg"', r)

    def test_cambiar_la_ruta_la_reemplaza(self):
        r = instalar.configurar_godot(instalar.configurar_godot(GODOT, "/viejo", "/p"), "/nuevo", "/p")
        self.assertNotIn("/viejo", r)
        self.assertEqual(r.count("nucleo_python="), 1)


class Deteccion(unittest.TestCase):
    def test_reconoce_los_tres_motores_y_rechaza_lo_demas(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d)
            with self.assertRaises(instalar.ErrorInstalacion):
                instalar.motor_de(p)
            (p / "X.uproject").write_text("{}")
            self.assertEqual(instalar.motor_de(p), "unreal")
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / "project.godot").write_text(GODOT)
            self.assertEqual(instalar.motor_de(Path(d)), "godot")
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / "ProjectSettings").mkdir()
            (Path(d) / "ProjectSettings" / "ProjectVersion.txt").write_text("m_EditorVersion: 6000.3")
            self.assertEqual(instalar.motor_de(Path(d)), "unity")

    def test_no_pisa_una_carpeta_con_contenido(self):
        with tempfile.TemporaryDirectory() as d:
            destino = Path(d) / "addons" / "jam"
            destino.mkdir(parents=True)
            (destino / "algo.txt").write_text("mío")
            with self.assertRaises(instalar.ErrorInstalacion):
                instalar.enlazar(RAIZ / "Godot" / "addons" / "jam", destino, copiar=False)
            self.assertEqual((destino / "algo.txt").read_text(), "mío")


if __name__ == "__main__":
    unittest.main()
