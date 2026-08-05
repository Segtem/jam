"""Nodos matemáticos explícitos: cálculo puro, tipos y paridad entre Graph y Flow."""

from __future__ import annotations

import json
import math
from pathlib import Path
import sys
import types
import unittest
from unittest import mock

_unreal_fake = sys.modules.setdefault("unreal", types.ModuleType("unreal"))
if not hasattr(_unreal_fake, "TopLevelAssetPath"):
    _unreal_fake.TopLevelAssetPath = lambda package, name: (package, name)

from jam import api, debug, flow, graph as graph_module, math_core, panel, ribbon  # noqa: E402
from jam.graph import (GraphValidationError, JamGraph, compilar, ejecutar_detalle,
                       ultima_corrida)  # noqa: E402


REGISTRY = {
    "consume": {
        "source": True, "aridad": 0, "min_inputs": 0, "in_name": "", "out_name": "A",
        "asset_required": False, "asset_pin": False, "asset_row": False,
        "params": {"valor": 0.0},
    },
}


def _grafo_cuenta() -> JamGraph:
    """(7 + 3) × 4 → consume.valor."""
    g = JamGraph()
    g.add("number", {"name": "primero", "value": 7}, nid="n1")
    g.add("number", {"name": "segundo", "value": 3}, nid="n2")
    g.add("math_add", {}, nid="sumar")
    g.add("number", {"name": "factor", "value": 4}, nid="factor")
    g.add("math_multiply", {}, nid="multiplicar")
    g.add("consume", {}, nid="fin")
    g.connect("n1", "sumar", "a")
    g.connect("n2", "sumar", "b")
    g.connect("sumar", "multiplicar", "a")
    g.connect("factor", "multiplicar", "b")
    g.connect("multiplicar", "fin", "valor")
    return g


class RegistroMathTests(unittest.TestCase):
    def test_el_registro_es_la_misma_fuente_para_flow_y_graph(self) -> None:
        self.assertIs(flow.VALOR_KINDS, math_core.VALOR_KINDS)
        self.assertEqual(set(math_core.DEFAULTS), set(math_core.VALORES))
        for verbo in ("math_add", "math_subtract", "math_multiply", "math_divide",
                      "math_negate", "math_absolute", "math_modulo", "math_power",
                      "math_sqrt"):
            self.assertIn(verbo, flow.OPS_META)
            self.assertEqual(math_core.tipo_salida(verbo), "N")
            for pin in math_core.DEFAULTS[verbo]:
                self.assertEqual(math_core.tipo_param(verbo, pin), "N")

    def test_los_pines_no_conmutativos_dicEN_el_orden(self) -> None:
        self.assertEqual(list(math_core.DEFAULTS["math_subtract"]), ["minuendo", "sustraendo"])
        self.assertEqual(list(math_core.DEFAULTS["math_divide"]), ["dividendo", "divisor"])

    def test_el_spec_publica_nombres_humanos_grupo_y_tipos(self) -> None:
        tools = {t["verbo"]: t for t in json.loads(api.spec_all())["tools"]}

        self.assertEqual(tools["math_add"]["label"], "Sumar")
        self.assertEqual(tools["math_subtract"]["label"], "Restar")
        self.assertEqual(tools["math_multiply"]["label"], "Multiplicar")
        self.assertEqual(tools["math_divide"]["label"], "Dividir")
        self.assertEqual(tools["math_negate"]["label"], "Negar")
        self.assertEqual(tools["math_absolute"]["label"], "Absoluto")
        self.assertEqual(tools["math_modulo"]["label"], "Módulo")
        self.assertEqual(tools["math_power"]["label"], "Potencia")
        self.assertEqual(tools["math_sqrt"]["label"], "Raíz cuadrada")
        self.assertEqual(tools["math"]["label"], "Expresión")
        self.assertEqual(tools["math_add"]["grupo"], "Aritmética")
        self.assertEqual(tools["math"]["grupo"], "Avanzado")
        self.assertEqual(tools["math_divide"]["out_name"], "N")
        self.assertEqual(tools["math_divide"]["out_label"], "resultado")
        self.assertEqual([p["nombre"] for p in tools["math_divide"]["params"]],
                         ["dividendo", "divisor"])
        self.assertEqual([p["label"] for p in tools["math_divide"]["params"]],
                         ["dividendo (Número)", "divisor (Número)"])
        self.assertEqual(ribbon.grupo_de("Maths", "math_multiply"), "Aritmética")
        self.assertEqual(ribbon.grupo_de("Maths", "math_negate"), "Signo")
        self.assertEqual(ribbon.grupo_de("Maths", "math_power"), "Resto y potencia")
        self.assertEqual(tools["math_power"]["seccion"], "Datos")

    def test_las_operaciones_explicitas_no_usan_eval(self) -> None:
        def prohibido(*_args):
            raise AssertionError("una suma literal no debe pasar por el evaluador de expresiones")

        self.assertEqual(math_core.evaluar("math_add", {"a": 2, "b": 5}, {}, prohibido), 7)


class CalculoMathTests(unittest.TestCase):
    def test_graph_encadena_valores_y_manda_el_resultado_a_un_parametro(self) -> None:
        plan = compilar(_grafo_cuenta(), registro=REGISTRY)

        self.assertEqual(plan.values_by_node["sumar"], 10.0)
        self.assertEqual(plan.values_by_node["multiplicar"], 40.0)
        self.assertEqual(plan.params["fin"]["valor"], 40.0)

    def test_flow_y_graph_resuelven_la_misma_cuenta(self) -> None:
        f = flow.Flow()
        f.add("number", {"name": "primero", "value": 7}, "n1")
        f.add("number", {"name": "segundo", "value": 3}, "n2")
        f.add("math_add", {}, "sumar")
        f.add("number", {"name": "factor", "value": 4}, "factor")
        f.add("math_multiply", {}, "multiplicar")
        f.connect("n1", "sumar", "a")
        f.connect("n2", "sumar", "b")
        f.connect("sumar", "multiplicar", "a")
        f.connect("factor", "multiplicar", "b")

        f.evaluar()
        plan = compilar(_grafo_cuenta(), registro=REGISTRY)

        self.assertEqual(f.resultados["sumar"]["value"], plan.values_by_node["sumar"])
        self.assertEqual(f.resultados["multiplicar"]["value"],
                         plan.values_by_node["multiplicar"])

    def test_resta_y_division_respetan_el_orden_de_los_pines(self) -> None:
        g = JamGraph()
        g.add("math_subtract", {"minuendo": 10, "sustraendo": 3}, nid="resta")
        g.add("math_divide", {"dividendo": 10, "divisor": 4}, nid="division")

        plan = compilar(g, registro={})

        self.assertEqual(plan.values_by_node["resta"], 7.0)
        self.assertEqual(plan.values_by_node["division"], 2.5)

    def test_signo_resto_potencia_y_raiz(self) -> None:
        literal = lambda *_args: None
        casos = [
            ("math_negate", {"valor": 7.5}, -7.5),
            ("math_absolute", {"valor": -7.5}, 7.5),
            ("math_modulo", {"valor": 17, "modulo": 5}, 2.0),
            ("math_modulo", {"valor": -1, "modulo": 5}, 4.0),
            ("math_power", {"base": 2, "exponente": 10}, 1024.0),
            ("math_sqrt", {"radicando": 81}, 9.0),
        ]
        for verbo, params, esperado in casos:
            with self.subTest(verbo=verbo, params=params):
                self.assertEqual(math_core.evaluar(verbo, params, {}, literal), esperado)

    def test_nuevos_valores_tienen_paridad_flow_graph(self) -> None:
        g = JamGraph()
        g.add("math_absolute", {"valor": -3}, nid="abs")
        g.add("math_power", {"exponente": 3}, nid="potencia")
        g.connect("abs", "potencia", "base")
        f = flow.Flow()
        f.add("math_absolute", {"valor": -3}, "abs")
        f.add("math_power", {"exponente": 3}, "potencia")
        f.connect("abs", "potencia", "base")

        f.evaluar()
        plan = compilar(g, registro={})

        self.assertEqual(plan.values_by_node["potencia"], 27.0)
        self.assertEqual(f.resultados["potencia"]["value"], 27.0)

    def test_las_propiedades_basicas_discriminan_los_operadores(self) -> None:
        literal = lambda *_args: None
        for a in (-7.0, -0.5, 0.0, 2.0, 11.0):
            for b in (-3.0, 0.25, 4.0):
                suma_ab = math_core.evaluar("math_add", {"a": a, "b": b}, {}, literal)
                suma_ba = math_core.evaluar("math_add", {"a": b, "b": a}, {}, literal)
                producto = math_core.evaluar("math_multiply", {"a": a, "b": b}, {}, literal)
                self.assertEqual(suma_ab, suma_ba)
                self.assertEqual(producto, a * b)
                self.assertEqual(
                    math_core.evaluar("math_subtract",
                                      {"minuendo": a, "sustraendo": a}, {}, literal), 0.0)

    def test_expresion_legada_sigue_resolviendo_variables(self) -> None:
        g = JamGraph()
        g.add("number", {"name": "ancho", "value": 5}, nid="ancho")
        g.add("math", {"name": "doble", "expr": "ancho * 2"}, nid="expr")
        g.add("math_add", {"b": 1}, nid="sumar")
        g.connect("expr", "sumar", "a")

        plan = compilar(g, registro={})

        self.assertEqual(plan.values["doble"], 10.0)
        self.assertEqual(plan.values_by_node["sumar"], 11.0)

    def test_run_deja_el_numero_en_el_inspector(self) -> None:
        g = JamGraph()
        g.add("math_add", {"a": 18, "b": 24}, nid="respuesta")
        plan = compilar(g, registro={})

        ejecutar_detalle(g, plan)
        tabla = debug.tabla_datos(ultima_corrida()["respuesta"])

        self.assertEqual(tabla["columnas"], [{"nombre": "valor", "tipo": "num"}])
        self.assertEqual(tabla["filas"], [[42.0]])

    def test_run_de_solo_valores_no_abre_ni_descarta_preview(self) -> None:
        g = JamGraph()
        g.add("math_add", {"a": 57, "b": 31}, nid="sumar")

        with mock.patch.object(
                panel, "_preview", side_effect=AssertionError("Math no debe entrar a Preview")):
            respuesta = json.loads(api.run_graph_json(g.to_json()))

        self.assertTrue(respuesta["ok"])
        self.assertFalse(respuesta["preview"])
        self.assertNotIn("PREVIEW", respuesta["report"])
        self.assertIn("sin efectos en la escena", respuesta["report"])
        self.assertEqual(respuesta["nodes"]["sumar"]["estado"], "ok")
        self.assertEqual(ultima_corrida()["sumar"], 88.0)

    def test_un_grafo_con_geometria_conserva_el_camino_preview(self) -> None:
        g = JamGraph()
        g.add("mesh_box", {}, nid="caja")

        def preview_realista(fn, _widget=None, *, owner="graph"):
            return fn(None) + f"\nPREVIEW [{owner}]"

        with mock.patch.object(graph_module, "compilar", return_value=object()), \
                mock.patch.object(graph_module, "ejecutar_detalle", return_value=(
                    "[caja·mesh_box] creada", {"caja": {"estado": "ok", "texto": "creada"}})), \
                mock.patch.object(panel, "_preview", side_effect=preview_realista) as preview:
            respuesta = json.loads(panel.ejecutar_grafo_json(g.to_json()))

        preview.assert_called_once()
        self.assertTrue(respuesta["preview"])
        self.assertIn("PREVIEW [graph]", respuesta["report"])


class ErroresMathTests(unittest.TestCase):
    def test_dividir_por_cero_es_error_de_compile_en_graph_y_flow(self) -> None:
        g = JamGraph()
        g.add("math_divide", {"dividendo": 10, "divisor": 0}, nid="dividir")
        with self.assertRaises(GraphValidationError) as caught:
            compilar(g, registro={})
        texto_graph = " ".join(caught.exception.diagnostics["dividir"])
        self.assertIn("divisor", texto_graph)
        self.assertIn("cero", texto_graph)

        f = flow.Flow()
        f.add("math_divide", {"dividendo": 10, "divisor": 0}, "dividir")
        diagnosticos = f.validar()
        self.assertIn("cero", " ".join(diagnosticos["dividir"]))

    def test_nan_e_infinito_no_entran_ni_salen(self) -> None:
        for valor in ("nan", "inf", "-inf"):
            g = JamGraph()
            g.add("number", {"value": valor}, nid="numero")
            with self.subTest(valor=valor), self.assertRaises(GraphValidationError) as caught:
                compilar(g, registro={})
            self.assertIn("finito", " ".join(caught.exception.diagnostics["numero"]))

        with self.assertRaises(math_core.ValorError) as caught:
            math_core.evaluar("math_multiply", {"a": 1e308, "b": 1e308}, {}, lambda *_: None)
        self.assertEqual(caught.exception.pin, "resultado")

    def test_texto_no_se_puede_cablear_a_un_sumando(self) -> None:
        g = JamGraph()
        g.add("text", {"value": "dos"}, nid="texto")
        g.add("math_add", {}, nid="sumar")
        g.connect("texto", "sumar", "a")

        with self.assertRaises(GraphValidationError) as caught:
            compilar(g, registro={})

        self.assertIn("esperaba N, recibió T", " ".join(caught.exception.diagnostics["sumar"]))

    def test_compile_publico_rechaza_la_division_antes_de_run(self) -> None:
        g = JamGraph()
        g.add("math_divide", {"dividendo": 1, "divisor": 0}, nid="dividir")

        respuesta = json.loads(api.compile_graph_json(g.to_json()))

        self.assertFalse(respuesta["ok"])
        self.assertIn("cero", respuesta["report"])

    def test_dominios_de_modulo_potencia_y_raiz_fallan_en_el_pin_responsable(self) -> None:
        casos = [
            ("math_modulo", {"valor": 3, "modulo": 0}, "modulo"),
            ("math_power", {"base": -1, "exponente": 0.5}, "base"),
            ("math_sqrt", {"radicando": -1}, "radicando"),
        ]
        for verbo, params, pin in casos:
            g = JamGraph()
            g.add(verbo, params, nid="cuenta")
            with self.subTest(verbo=verbo), self.assertRaises(GraphValidationError) as caught:
                compilar(g, registro={})
            self.assertIn(pin, " ".join(caught.exception.diagnostics["cuenta"]))


class SlateMathContratoTests(unittest.TestCase):
    RAIZ = Path(__file__).resolve().parents[3]

    def test_slate_conserva_nombre_interno_y_muestra_nombre_tipo_completos(self) -> None:
        modulo = (self.RAIZ / "Source/JamEditor/Private/JamEditorModule.cpp").read_text()
        editor = (self.RAIZ / "Source/JamEditor/Private/SJamGraphEditor.cpp").read_text()
        nodo = (self.RAIZ / "Source/JamEditor/Private/SJamGraphNode.cpp").read_text()

        self.assertIn('TryGetStringField(TEXT("out_label"), T.OutLabel)', modulo)
        self.assertIn('TryGetStringField(TEXT("label"), P.Label)', modulo)
        self.assertIn("Param.Label = P.Label", editor)
        self.assertIn('TEXT("%s (%s)"), *T->OutLabel, *DataName(T->OutName)', editor)
        self.assertIn("FText::FromString(Label)", nodo)
        self.assertIn("SLATE_ARGUMENT(FString, OutputPinName)",
                      (self.RAIZ / "Source/JamEditor/Public/SJamGraphNode.h").read_text())
        self.assertIn("SLATE_ARGUMENT(FString, OutputDataType)",
                      (self.RAIZ / "Source/JamEditor/Public/SJamGraphNode.h").read_text())
        self.assertIn(".OutputPinName(TEXT(\"out\"))", editor)
        self.assertIn(".OutputDataType(T->OutName)", editor)
        # El código N es tipo/protocolo: no se vuelve a pintar como si fuera nombre del pin.
        self.assertNotIn("FM2->Measure(OutName", nodo)
        # La identidad de los cables/JSON sigue usando Name y OutName, no las etiquetas traducidas.
        self.assertIn("Node.PinNames.Add(P.Name)", editor)
        self.assertIn('ExecuteIfBound(OutputPinName)', nodo)


class ComparacionesTests(unittest.TestCase):
    """Las comparaciones son los ÚNICOS nodos que producen un booleano.

    Antes de ellas ningún verbo tenía `out_name == "B"`, así que un condicional no tenía a qué
    cablearse: era un checkbox eligiendo rama. Son la pieza que le da sentido al `select`.
    """

    def valor(self, verbo: str, **params):
        g = JamGraph()
        g.add(verbo, {k: str(v) for k, v in params.items()}, nid="c")
        return g.valores()

    def test_greater_and_less_are_strict(self):
        self.assertIs(self.valor("compare_greater", a=3, b=2)["c"], True)
        self.assertIs(self.valor("compare_greater", a=2, b=2)["c"], False)
        self.assertIs(self.valor("compare_less", a=2, b=3)["c"], True)
        self.assertIs(self.valor("compare_less", a=2, b=2)["c"], False)

    def test_the_result_is_a_real_bool_and_not_a_number(self):
        """El camino genérico de `evaluar` pasa todo por `_numero`, que aplastaría el booleano a
        1.0/0.0 — y dejaría de ser un booleano para el resto del sistema. Lo decide `out_name`."""
        v = self.valor("compare_greater", a=3, b=2)["c"]
        self.assertIsInstance(v, bool)
        self.assertNotIsInstance(v, float)

    def test_equality_on_floats_needs_a_tolerance(self):
        """`0.1 + 0.2 == 0.3` es falso en cualquier lenguaje con flotantes, y en un grafo eso se ve
        como «el condicional no funciona»."""
        self.assertIs(self.valor("compare_equal", a=0.1 + 0.2, b=0.3)["c"], True)
        self.assertIs(self.valor("compare_equal", a=0.1 + 0.2, b=0.3, tolerancia=0)["c"], False)
        self.assertIs(self.valor("compare_equal", a=1.0, b=2.0)["c"], False)

    def test_a_negative_tolerance_is_an_error_and_not_always_false(self):
        g = JamGraph()
        g.add("compare_equal", {"a": "1", "b": "1", "tolerancia": "-1"}, nid="c")
        with self.assertRaises(GraphValidationError):
            compilar(g, registro=REGISTRY)

    def test_they_declare_the_boolean_type_so_a_cable_can_be_checked(self):
        """Sin `out_name = B` el cable a un pin booleano no se podría validar en Compile."""
        for verbo in ("compare_greater", "compare_less", "compare_equal"):
            self.assertEqual(math_core.tipo_salida(verbo), "B", verbo)

    def test_a_boolean_never_leaks_into_a_numeric_expression(self):
        """`math` excluye los booleanos de su tabla de variables a propósito: sumarle 1 a «es mayor»
        sería un sinsentido que además pasaría desapercibido."""
        g = JamGraph()
        g.add("compare_greater", {"a": "3", "b": "2", "name": "esMayor"}, nid="cmp")
        g.add("math", {"name": "m", "expr": "esMayor"}, nid="m")
        tabla = g.valores()
        self.assertIs(tabla["cmp"], True)
        # La expresión no resuelve porque `esMayor` no es una variable numérica visible.
        self.assertNotIn("m", tabla)


if __name__ == "__main__":
    unittest.main()
