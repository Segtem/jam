"""En qué motor corre cada verbo (tarea `fuera-del-motor`; criterio 11 de `dsl-grafos`).

Lo que el motor conectado no tiene se muestra DESHABILITADO —no se esconde— con su porqué (Brian,
2026-09-28), y el Compile no lo deja correr.
"""

from __future__ import annotations

import json
import os
import sys
import types
import unittest
from pathlib import Path
from unittest import mock

_unreal_fake = sys.modules.setdefault("unreal", types.ModuleType("unreal"))
if not hasattr(_unreal_fake, "TopLevelAssetPath"):
    _unreal_fake.TopLevelAssetPath = lambda package, name: (package, name)

from jam import api, graph, registro, tools  # noqa: E402

RAIZ = Path(__file__).resolve().parents[3]


class Declaracion(unittest.TestCase):
    def test_todo_verbo_declara_sus_motores(self):
        sin = [v for v, i in registro.REGISTRO.items() if not i.get("motores")]
        self.assertEqual(sin, [])

    def test_una_op_de_flow_es_pura_y_corre_en_cualquiera(self):
        self.assertEqual(registro.REGISTRO["jitter"]["motores"], ("*",))
        self.assertEqual(registro.disponible("jitter", "godot"), (True, ""))

    def test_lo_que_nunca_sale_de_unreal_dice_por_que(self):
        self.assertEqual(registro.disponible("nanite", "godot"),
                         (False, "Nanite existe sólo en Unreal"))
        self.assertIn("MassEntity", registro.disponible("mass_spawn", "godot")[1])

    def test_lo_demas_dice_que_todavia_no_esta(self):
        self.assertEqual(registro.disponible("pick", "godot"),
                         (False, "todavía no tiene implementación en godot"))

    def test_lo_que_anuncia_el_adaptador_manda_sobre_lo_declarado(self):
        self.assertEqual(registro.disponible("mesh_box", "godot", {"mesh_box"}), (True, ""))
        self.assertFalse(registro.disponible("jitter", "godot", {"mesh_box"})[0])


class ElMotorConectado(unittest.TestCase):
    def test_unreal_implementa_todo_su_registro(self):
        motor, implementados = tools.motor_activo()
        self.assertEqual(motor, "unreal")
        self.assertEqual(set(implementados), set(registro.REGISTRO))

    def test_simular_otro_motor(self):
        with mock.patch.dict(os.environ, {"JAM_MOTOR_SIMULADO": "godot"}):
            self.assertEqual(tools.motor_activo(), ("godot", None))


class Compile(unittest.TestCase):
    def _grafo(self):
        g = graph.JamGraph()
        g.add("pts_line", {}, nid="linea")
        g.add("jitter", {}, nid="ruido")
        g.connect("linea", "ruido")
        g.add("curve_line", {}, nid="curva")
        g.add("mesh_revolve", {}, nid="caja")   # Geometry Script: hoy, sólo el adaptador de Unreal
        g.connect("curva", "caja")
        return g

    def test_en_unreal_compila(self):
        graph.compilar(self._grafo(), registro=registro.REGISTRO, motor="unreal",
                       implementados=set(registro.REGISTRO))

    def test_en_otro_motor_un_verbo_de_unreal_es_error_con_su_porque(self):
        with self.assertRaises(graph.GraphValidationError) as e:
            graph.compilar(self._grafo(), registro=registro.REGISTRO, motor="godot")
        self.assertEqual(list(e.exception.diagnostics), ["caja"], "la cadena de puntos es pura")
        self.assertIn("no disponible en este motor (godot): todavía no tiene implementación",
                      e.exception.diagnostics["caja"][0])


class LoQueVeElCanvas(unittest.TestCase):
    def _spec(self, **kw):
        return {t["verbo"]: t for t in json.loads(registro.spec_json(include_graph_only=True, **kw))["tools"]}

    def test_en_unreal_esta_todo(self):
        spec = self._spec(motor="unreal", implementados=set(registro.REGISTRO))
        self.assertTrue(all(t["disponible"] for t in spec.values()))

    def test_en_godot_se_ven_deshabilitados_no_desaparecen(self):
        spec = self._spec(motor="godot")
        self.assertEqual(len(spec), len(self._spec()), "un verbo no disponible no se esconde")
        self.assertFalse(spec["nanite"]["disponible"])
        self.assertEqual(spec["nanite"]["porque"], "Nanite existe sólo en Unreal")
        self.assertTrue(spec["jitter"]["disponible"])

    def test_la_ayuda_lo_marca(self):
        with mock.patch.dict(os.environ, {"JAM_MOTOR_SIMULADO": "godot"}):
            self.assertIn("[NO DISPONIBLE en godot: Nanite existe sólo en Unreal]",
                          api.ayuda_texto("nanite"))
            self.assertIn("Motor conectado: godot", api.ayuda_texto(""))

    def test_el_cpp_deshabilita_la_ficha_y_el_resultado_del_buscador(self):
        cpp = (RAIZ / "Source/JamEditor/Private/SJamGraphEditor.cpp").read_text(encoding="utf-8")
        modulo = (RAIZ / "Source/JamEditor/Private/JamEditorModule.cpp").read_text(encoding="utf-8")
        self.assertIn('TryGetBoolField(TEXT("disponible"), T.bDisponible)', modulo)
        self.assertEqual(cpp.count(".IsEnabled(T.bDisponible)"), 2, "ficha del ribbon y buscador")
        self.assertIn("if (T.bDisponible) { SearchHits.Add(T.Verb); }", cpp)


if __name__ == "__main__":
    unittest.main()
