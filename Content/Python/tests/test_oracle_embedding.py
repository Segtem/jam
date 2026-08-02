"""La sombra de Jam consume Oracle por su fachada pública, no por internals del vendor."""

from __future__ import annotations

import importlib.util
import io
import json
import re
import sys
import unittest
from contextlib import redirect_stdout
from unittest import mock
from pathlib import Path

from jam import bridge, oracle_placement, oracle_shadow, oracle_snap
from jam.geometry import AABB, Pieza, Vec3


RAIZ = Path(__file__).resolve().parents[3]


def _cargar_vault():
    spec = importlib.util.spec_from_file_location("jam_tools_vault", RAIZ / "tools" / "vault.py")
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo


def _cargar_relevo():
    spec = importlib.util.spec_from_file_location("jam_tools_relevo", RAIZ / "tools" / "relevo.py")
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo


class OracleEmbeddingTests(unittest.TestCase):
    def test_el_proyecto_pide_el_catalogo_base_que_usa_relevo(self) -> None:
        configuracion = json.loads((RAIZ / "medidas" / "oracle.json").read_text())
        fixture = json.loads(
            (RAIZ / "medidas" / "diferencial" / "relevo.json").read_text())

        self.assertTrue(configuracion["catalogo_base"])
        self.assertIn("proceso.verificacion_vigente", fixture["medidas"])

    def test_el_puente_centraliza_las_dos_raices_de_oraculos(self) -> None:
        bridge.ensure_oraculo_on_path()

        self.assertIn(str(bridge.ORACULO_ROOT), sys.path)
        self.assertIn(str(bridge.ORACLE_PACKAGE_ROOT), sys.path)

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

    def test_placement_y_snap_coinciden_por_la_fachada_publica(self) -> None:
        pieza = Pieza(
            "sujeto",
            AABB(Vec3(3.0, 0.0, 0.0), Vec3(50.0, 50.0, 50.0)),
            Vec3(3.0, 0.0, 0.0),
            45.0,
        )
        vecina = Pieza(
            "vecina",
            AABB(Vec3(20.0, 0.0, 0.0), Vec3(50.0, 50.0, 50.0)),
            Vec3(20.0, 0.0, 0.0),
            0.0,
        )

        placement = oracle_placement.verificar(pieza, [vecina])
        snap = oracle_snap.verificar_grilla(pieza)
        sombra_placement = oracle_shadow.comparar_placement(pieza, [vecina], placement)
        sombra_snap = oracle_shadow.comparar_snap(pieza, snap)

        self.assertTrue(sombra_placement.coincide, sombra_placement)
        self.assertTrue(sombra_snap.coincide, sombra_snap)
        self.assertEqual(
            {
                "colocacion.bounds",
                "colocacion.interpenetracion",
                "snap.grilla",
                "snap.yaw",
            },
            {v.id for v in sombra_placement.informe.veredictos},
        )

    def test_un_desacuerdo_de_la_sombra_no_se_disfraza_de_verde(self) -> None:
        pieza = Pieza(
            "sujeto",
            AABB(Vec3(0.0, 0.0, 0.0), Vec3(50.0, 50.0, 50.0)),
            Vec3(0.0, 0.0, 0.0),
            0.0,
        )
        referencia_adulterada = oracle_snap.verificar_grilla(pieza) | {"yaw_ok": False}

        sombra = oracle_shadow.comparar_snap(pieza, referencia_adulterada)

        self.assertFalse(sombra.coincide)
        self.assertEqual(
            ("snap.yaw: referencia=False, Motor=True",),
            sombra.diferencias,
        )

    def test_una_grilla_no_declarada_no_se_compara_con_el_default(self) -> None:
        pieza = Pieza(
            "sujeto",
            AABB(Vec3(50.0, 0.0, 0.0), Vec3(10.0, 10.0, 10.0)),
            Vec3(50.0, 0.0, 0.0),
            0.0,
        )
        referencia = oracle_snap.verificar_grilla(pieza, grilla=50.0)

        sombra = oracle_shadow.comparar_snap(pieza, referencia, grilla=50.0)

        self.assertTrue(referencia["en_grilla"])
        self.assertFalse(sombra.coincide)
        self.assertIn("configuración no declarada", sombra.error)

    def test_un_fallo_del_motor_es_un_error_observable(self) -> None:
        pieza = Pieza(
            "sujeto",
            AABB(Vec3(0.0, 0.0, 0.0), Vec3(10.0, 10.0, 10.0)),
            Vec3(0.0, 0.0, 0.0),
            0.0,
        )
        referencia = oracle_snap.verificar_grilla(pieza)

        with mock.patch.object(
            oracle_shadow,
            "motor_geometria",
            side_effect=RuntimeError("motor roto deliberadamente"),
        ):
            sombra = oracle_shadow.comparar_snap(pieza, referencia)

        self.assertFalse(sombra.coincide)
        self.assertEqual("RuntimeError: motor roto deliberadamente", sombra.error)

    def test_al_ras_distingue_contacto_hueco_clavado_y_diagonal(self) -> None:
        pieza = Pieza(
            "sujeto",
            AABB(Vec3(0.0, 0.0, 0.0), Vec3(50.0, 50.0, 50.0)),
            Vec3(0.0, 0.0, 0.0),
            0.0,
        )
        casos = (
            ("al_ras", Vec3(100.0, 0.0, 0.0)),
            ("hueco", Vec3(102.0, 0.0, 0.0)),
            ("clavado", Vec3(98.0, 0.0, 0.0)),
            ("desalineado", Vec3(100.0, 99.0, 0.0)),
        )

        for estado, centro in casos:
            with self.subTest(estado=estado):
                objetivo = Pieza(
                    "objetivo",
                    AABB(centro, Vec3(50.0, 50.0, 50.0)),
                    centro,
                    0.0,
                )
                referencia = oracle_snap.verificar_ras(pieza, objetivo, "x")
                sombra = oracle_shadow.comparar_al_ras(
                    pieza, objetivo, "x", referencia)

                self.assertEqual(estado, referencia["estado"])
                self.assertTrue(sombra.coincide, sombra)
                self.assertTrue(
                    {"snap.al_ras", "snap.comparte_cara"}.issubset(
                        {v.id for v in sombra.informe.veredictos}))

    def test_al_ras_no_esta_hardcodeado_al_eje_x(self) -> None:
        extension = Vec3(10.0, 20.0, 30.0)
        pieza = Pieza(
            "sujeto",
            AABB(Vec3(0.0, 0.0, 0.0), extension),
            Vec3(0.0, 0.0, 0.0),
            0.0,
        )

        for eje, centro in (
            ("x", Vec3(20.0, 0.0, 0.0)),
            ("y", Vec3(0.0, 40.0, 0.0)),
            ("z", Vec3(0.0, 0.0, 60.0)),
        ):
            with self.subTest(eje=eje):
                objetivo = Pieza("objetivo", AABB(centro, extension), centro, 0.0)
                referencia = oracle_snap.verificar_ras(pieza, objetivo, eje)
                sombra = oracle_shadow.comparar_al_ras(
                    pieza, objetivo, eje, referencia)

                self.assertEqual("al_ras", referencia["estado"])
                self.assertTrue(sombra.coincide, sombra)

    def test_el_adaptador_no_importa_internals_del_vendor(self) -> None:
        fuente = (RAIZ / "Content" / "Python" / "jam" / "oracle_shadow.py").read_text(
            encoding="utf-8")

        self.assertNotIn("from nucleo", fuente)
        self.assertNotIn("from catalogos", fuente)

    def test_todo_el_runtime_respeta_la_fachada_publica_de_oracle(self) -> None:
        runtime = RAIZ / "Content" / "Python" / "jam"
        import_interno = re.compile(r"^\s*(?:from|import)\s+(?:nucleo|catalogos|perfiles)\b", re.M)

        for archivo in sorted(runtime.glob("*.py")):
            fuente = archivo.read_text(encoding="utf-8")
            with self.subTest(archivo=archivo.name):
                self.assertIsNone(import_interno.search(fuente))
                if archivo.name != "bridge.py":
                    self.assertNotIn("vendor/oracle", fuente)


class PuertaRelevoOracleTests(unittest.TestCase):
    @staticmethod
    def _fm() -> dict:
        return {
            "turno": "2026-01-01 · codex → claude-code",
            "saliente": "codex",
            "entrante": "claude-code",
            "desde": "2026-01-01",
            "verde_editor": "abc123",
            "verde_editor_fecha": "2026-01-01",
        }

    def test_codigo_vivo_nombra_runtime_y_no_la_suite(self) -> None:
        relevo = _cargar_relevo()

        self.assertEqual(
            ("Source", "Content/Python/init_unreal.py", "Content/Python/jam", "oraculo"),
            relevo.VIVO,
        )

    def test_la_apertura_rechaza_un_diferencial_vencido(self) -> None:
        relevo = _cargar_relevo()
        with mock.patch.object(relevo, "revisar_testigo", return_value=(self._fm(), [])), \
             mock.patch.object(relevo, "tags_de_relevo", return_value=[]), \
             mock.patch.object(relevo, "tests", return_value=[]), \
             mock.patch.object(relevo, "vault", return_value=[]), \
             mock.patch.object(relevo, "oracle_diferencial", return_value=["fixture vencido"]), \
             mock.patch.object(relevo, "verde_editor_vigente", return_value=[]), \
             redirect_stdout(io.StringIO()) as salida:
            codigo = relevo.abrir()

        self.assertEqual(1, codigo)
        self.assertIn("fixture vencido", salida.getvalue())

    def test_el_cierre_rechaza_un_diferencial_vencido(self) -> None:
        relevo = _cargar_relevo()
        with mock.patch.object(relevo, "revisar_testigo", return_value=(self._fm(), [])), \
             mock.patch.object(relevo, "arbol_limpio_y_empujado", return_value=[]), \
             mock.patch.object(relevo, "tests", return_value=[]), \
             mock.patch.object(relevo, "vault", return_value=[]), \
             mock.patch.object(relevo, "oracle_diferencial", return_value=["fixture vencido"]), \
             mock.patch.object(relevo, "verde_editor_vigente", return_value=[]), \
             redirect_stdout(io.StringIO()) as salida:
            codigo = relevo.cerrar()

        self.assertEqual(1, codigo)
        self.assertIn("fixture vencido", salida.getvalue())


if __name__ == "__main__":
    unittest.main()
