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


class DiagnosticoDeVariablesTests(unittest.TestCase):
    """Escribir variables a mano sin autocompletado hace que el TYPO sea la falla típica.

    `valor o expresión sin resolver` era verdad pero inservible: no decía cuál nombre estaba mal ni
    contra qué comparar. El diagnóstico tiene que resolver el typo sin salir del nodo.
    """

    def error_de(self, expr: str, variables: dict | None = None) -> str:
        g = JamGraph()
        for i, (nombre, valor) in enumerate((variables or {}).items()):
            g.add("number", {"name": nombre, "value": str(valor)}, nid=f"v{i}")
        g.add("math", {"name": "r", "expr": expr}, nid="m")
        return graph_module.validar(g)["m"][0]

    def test_it_names_the_variable_that_does_not_exist(self):
        msg = self.error_de("radioo * 2", {"radio": 50})
        self.assertIn("«radioo»", msg)

    def test_it_lists_what_is_available_so_the_typo_is_obvious(self):
        msg = self.error_de("radioo * 2", {"radio": 50, "alto": 10})
        self.assertIn("«radio»", msg)
        self.assertIn("«alto»", msg)

    def test_a_function_is_not_reported_as_a_missing_variable(self):
        """`sqrt(x)` menciona `sqrt`, que el evaluador provee: reportarlo mandaría a buscar una
        variable que no tiene que existir."""
        msg = self.error_de("sqrt(nada)")
        self.assertNotIn("«sqrt»", msg)
        self.assertIn("«nada»", msg)

    def test_with_no_variables_it_says_so_instead_of_an_empty_list(self):
        self.assertIn("ninguna todavía", self.error_de("nada + 1"))

    def test_a_boolean_is_not_offered_as_an_alternative(self):
        """Un booleano no es usable en una expresión numérica (ver `evaluar`), así que ofrecerlo
        mandaría a quien lee directo a un segundo error."""
        g = JamGraph()
        g.add("compare_greater", {"a": "3", "b": "2", "name": "esMayor"}, nid="cmp")
        g.add("number", {"name": "radio", "value": "50"}, nid="n")
        g.add("math", {"name": "r", "expr": "nada + 1"}, nid="m")
        msg = graph_module.validar(g)["m"][0]
        self.assertIn("«radio»", msg)
        self.assertNotIn("esMayor", msg)


class VariablesParaElDesplegableTests(unittest.TestCase):
    """`api.variables` alimenta el desplegable del nodo `math`.

    Sale de `JamGraph.valores()`, o sea del MISMO código que después resuelve la expresión: así el
    desplegable no puede ofrecer un nombre que el evaluador vaya a rechazar. Una lista construida
    aparte se desincronizaría el día que cambie qué cuenta como variable.
    """

    def nombres(self, g: JamGraph) -> list:
        return json.loads(api.variables(g.to_json()))["variables"]

    def test_it_lists_the_named_value_nodes(self):
        g = JamGraph()
        g.add("number", {"name": "radio", "value": "50"}, nid="n")
        g.add("number", {"name": "alto", "value": "10"}, nid="n2")
        self.assertEqual(self.nombres(g), ["alto", "radio"])

    def test_a_node_that_is_not_a_variable_is_not_offered(self):
        g = JamGraph()
        g.add("number", {"name": "radio", "value": "50"}, nid="n")
        g.add("mesh_box", {}, nid="caja")
        self.assertEqual(self.nombres(g), ["radio"])

    def test_a_boolean_is_not_offered(self):
        """Un booleano no es usable en una expresión: ofrecerlo mandaría a quien lo elige directo a
        un error. Es la misma regla que aplica el mensaje de «variable desconocida»."""
        g = JamGraph()
        g.add("compare_greater", {"a": "3", "b": "2"}, nid="cmp")
        self.assertEqual(self.nombres(g), [])

    def test_an_empty_graph_answers_ok_with_an_empty_list(self):
        """El menú distingue «no hay variables» de «falló la consulta»: con `ok:false` mostraría un
        error donde en realidad sólo falta agregar un `number`."""
        res = json.loads(api.variables(JamGraph().to_json()))
        self.assertTrue(res["ok"])
        self.assertEqual(res["variables"], [])

    def test_garbage_does_not_raise(self):
        """Lo llama Slate al desplegar un menú: una excepción ahí se lleva puesto el gesto."""
        res = json.loads(api.variables("no soy json"))
        self.assertFalse(res["ok"])

    def test_everything_offered_actually_resolves_in_an_expression(self):
        """La propiedad que justifica derivarlo de `valores()`: cada nombre del desplegable tiene
        que poder usarse tal cual en una expresión."""
        def armar() -> JamGraph:
            g = JamGraph()
            g.add("number", {"name": "radio", "value": "50"}, nid="n")
            g.add("math", {"name": "doble", "expr": "radio * 2"}, nid="m")
            return g

        ofrecidas = self.nombres(armar())
        # `doble` es la salida de un `math`: también es una variable, y encadenar expresiones es
        # justo para lo que sirve.
        self.assertEqual(ofrecidas, ["doble", "radio"])
        for nombre in ofrecidas:
            with self.subTest(variable=nombre):
                # El MISMO grafo más una sonda: reconstruirlo sin sus nodos probaría otra cosa.
                sonda = armar()
                sonda.add("math", {"name": "prueba", "expr": nombre}, nid="p")
                self.assertNotIn("p", graph_module.validar(sonda),
                                 f"«{nombre}» se ofrece pero no resuelve")


if __name__ == "__main__":
    unittest.main()


class RangoMezclaRedondeoYAngulosTests(unittest.TestCase):
    """El tercer lote de la Fase 1: Rango, Mezcla, Redondeo, Trigonometría y las dos comparaciones
    que faltaban. Lo que se fija acá no es «que la suma sume» sino las DECISIONES: qué pasa en los
    bordes, dónde se falla y con qué pin."""

    def evaluar(self, verbo, params):
        return math_core.evaluar(verbo, params, {}, lambda *_a: None)

    def test_rango(self) -> None:
        self.assertEqual(self.evaluar("math_min", {"a": 3, "b": 7}), 3)
        self.assertEqual(self.evaluar("math_max", {"a": 3, "b": 7}), 7)
        self.assertEqual(self.evaluar("math_clamp", {"valor": 9, "minimo": 0, "maximo": 5}), 5)
        self.assertEqual(self.evaluar("math_clamp", {"valor": -9, "minimo": 0, "maximo": 5}), 0)
        self.assertEqual(self.evaluar("math_clamp", {"valor": 3, "minimo": 0, "maximo": 5}), 3)

    def test_un_rango_dado_vuelta_es_error_y_no_se_acomoda_solo(self) -> None:
        """Intercambiar mínimo y máximo en silencio deja pasar un cable mal conectado produciendo
        números plausibles: no hay síntoma hasta que alguien mira la geometría."""
        with self.assertRaises(math_core.ValorError) as caso:
            self.evaluar("math_clamp", {"valor": 3, "minimo": 5, "maximo": 0})
        self.assertEqual(caso.exception.pin, "minimo")

    def test_saturar_es_limitar_a_cero_uno(self) -> None:
        for entrada, esperado in ((-2, 0.0), (0.25, 0.25), (5, 1.0)):
            with self.subTest(entrada=entrada):
                self.assertEqual(self.evaluar("math_saturate", {"valor": entrada}), esperado)

    def test_interpolar_NO_acota_el_factor(self) -> None:
        """Extrapolar es útil y acotarlo en silencio se la sacaría a quien la busca; para acotar
        está `math_saturate`, que se ve en el grafo."""
        self.assertEqual(self.evaluar("math_lerp", {"desde": 0, "hasta": 10, "factor": 0.5}), 5)
        self.assertEqual(self.evaluar("math_lerp", {"desde": 0, "hasta": 10, "factor": 1.5}), 15)
        self.assertEqual(self.evaluar("math_lerp", {"desde": 0, "hasta": 10, "factor": -1}), -10)

    def test_interpolar_llega_EXACTO_al_destino(self) -> None:
        """Con `desde*(1-f) + hasta*f` el factor 1 puede errarle por redondeo. Con esta forma, no."""
        self.assertEqual(self.evaluar("math_lerp", {"desde": 0.1, "hasta": 0.3, "factor": 1.0}), 0.3)

    def test_remapear(self) -> None:
        self.assertEqual(self.evaluar("math_remap", {
            "valor": 5, "desde_min": 0, "desde_max": 10,
            "hasta_min": 0, "hasta_max": 100}), 50)
        # Fuera del rango de origen se extrapola, igual que interpolar.
        self.assertEqual(self.evaluar("math_remap", {
            "valor": 20, "desde_min": 0, "desde_max": 10,
            "hasta_min": 0, "hasta_max": 100}), 200)

    def test_un_origen_vacio_al_remapear_es_error(self) -> None:
        """Todo el origen es un punto: no hay proporción que calcular y devolver el mínimo del
        destino sería inventar una respuesta."""
        with self.assertRaises(math_core.ValorError) as caso:
            self.evaluar("math_remap", {"valor": 5, "desde_min": 2, "desde_max": 2,
                                        "hasta_min": 0, "hasta_max": 100})
        self.assertEqual(caso.exception.pin, "desde_max")

    def test_piso_y_techo_con_negativos(self) -> None:
        """El caso donde la intuición falla: piso se ALEJA del cero y techo se le acerca."""
        self.assertEqual(self.evaluar("math_floor", {"valor": -2.1}), -3)
        self.assertEqual(self.evaluar("math_ceil", {"valor": -2.9}), -2)
        self.assertEqual(self.evaluar("math_floor", {"valor": 2.9}), 2)
        self.assertEqual(self.evaluar("math_ceil", {"valor": 2.1}), 3)

    def test_redondear_aleja_el_medio_del_cero_y_NO_al_par(self) -> None:
        """`round()` de Python redondea el medio al par: `round(0.5)` da 0 y `round(2.5)` da 2. Es
        correcto para estadística y desconcertante en un grafo, y encima el error no es constante,
        así que se ve como «a veces redondea mal». Acá 0,5 da 1."""
        self.assertEqual(self.evaluar("math_round", {"valor": 0.5}), 1)
        self.assertEqual(self.evaluar("math_round", {"valor": 1.5}), 2)
        self.assertEqual(self.evaluar("math_round", {"valor": 2.5}), 3)
        self.assertEqual(self.evaluar("math_round", {"valor": -0.5}), -1)
        self.assertEqual(self.evaluar("math_round", {"valor": -2.5}), -3)
        self.assertNotEqual(self.evaluar("math_round", {"valor": 2.5}), round(2.5))

    def test_angulos_van_en_radianes_y_la_conversion_es_explicita(self) -> None:
        self.assertAlmostEqual(self.evaluar("math_radians", {"grados": 180}), math.pi)
        self.assertAlmostEqual(self.evaluar("math_degrees", {"radianes": math.pi}), 180)
        self.assertAlmostEqual(self.evaluar("math_sin", {"radianes": math.pi / 2}), 1.0)
        self.assertAlmostEqual(self.evaluar("math_cos", {"radianes": 0}), 1.0)
        self.assertAlmostEqual(self.evaluar("math_tan", {"radianes": math.pi / 4}), 1.0)

    def test_la_tangente_cerca_del_polo_da_un_numero_enorme_y_NO_es_error(self) -> None:
        """En π/2 la tangente no existe, pero ese punto exacto no se alcanza en flotantes: lo que
        llega son valores cercanos donde la tangente realmente vale millones. Un umbral que los
        rechazara inventaría un límite que la matemática no tiene."""
        enorme = self.evaluar("math_tan", {"radianes": math.pi / 2})
        self.assertGreater(abs(enorme), 1e15)
        self.assertTrue(math.isfinite(enorme))

    def test_las_comparaciones_nuevas_producen_booleano(self) -> None:
        for verbo in ("compare_greater_equal", "compare_less_equal"):
            with self.subTest(verbo=verbo):
                self.assertEqual(math_core.tipo_salida(verbo), "B")
        self.assertTrue(self.evaluar("compare_greater_equal", {"a": 3, "b": 3}))
        self.assertFalse(self.evaluar("compare_greater", {"a": 3, "b": 3}))
        self.assertTrue(self.evaluar("compare_less_equal", {"a": 3, "b": 3}))
        self.assertFalse(self.evaluar("compare_less", {"a": 3, "b": 3}))

    def test_todo_el_lote_esta_en_flow_y_en_el_ribbon(self) -> None:
        """Un verbo que existe en el registro pero no en el ribbon no se puede agregar con el mouse:
        queda escrito y no existe para el que usa la herramienta."""
        grupos = {
            "Rango": ["math_min", "math_max", "math_clamp", "math_saturate"],
            "Mezcla": ["math_lerp", "math_remap"],
            "Redondeo": ["math_floor", "math_ceil", "math_round"],
            "Trigonometría": ["math_radians", "math_degrees", "math_sin", "math_cos", "math_tan"],
            "Comparar": ["compare_greater_equal", "compare_less_equal"],
        }
        for grupo, verbos in grupos.items():
            for verbo in verbos:
                with self.subTest(verbo=verbo):
                    self.assertIn(verbo, flow.OPS_META)
                    self.assertEqual(ribbon.grupo_de("Maths", verbo), grupo)

    def test_el_lote_resuelve_encadenado_en_el_Graph(self) -> None:
        """Por el ejecutor de verdad y no verbo por verbo: remapear 5 de 0..10 a 0..100, saturar
        eso a 0..1 y redondearlo tiene que dar 1."""
        g = JamGraph()
        g.add("math_remap", {"valor": 5, "desde_min": 0, "desde_max": 10,
                             "hasta_min": 0, "hasta_max": 100}, nid="mapa")
        g.add("math_saturate", {}, nid="sat")
        g.add("math_round", {}, nid="red")
        g.connect("mapa", "sat", "valor")
        g.connect("sat", "red", "valor")
        plan = compilar(g)
        self.assertEqual(plan.values_by_node["mapa"], 50.0)
        self.assertEqual(plan.values_by_node["sat"], 1.0)
        self.assertEqual(plan.values_by_node["red"], 1.0)
