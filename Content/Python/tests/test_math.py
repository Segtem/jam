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
        """Toma DOS DOMINIOS y no cuatro números sueltos. Con los cuatro, dos pines eran del rango
        de origen y dos del de destino sin nada que lo dijera: cablear el máximo de uno en el mínimo
        del otro era un error de un pin de distancia y sin síntoma, porque el número que sale sigue
        siendo plausible."""
        self.assertEqual(self.evaluar("math_remap", {
            "valor": 5, "origen": (0, 10), "destino": (0, 100)}), 50)
        # Fuera del dominio de origen se extrapola, igual que interpolar.
        self.assertEqual(self.evaluar("math_remap", {
            "valor": 20, "origen": (0, 10), "destino": (0, 100)}), 200)

    def test_un_destino_al_reves_da_vuelta_el_rango(self) -> None:
        """La capacidad que un rango partido en números sueltos no tenía nombre para expresar."""
        self.assertEqual(self.evaluar("math_remap", {
            "valor": 0.25, "origen": (0, 1), "destino": (100, 0)}), 75.0)

    def test_un_origen_vacio_al_remapear_es_error(self) -> None:
        """Todo el origen es un punto: no hay proporción que calcular y devolver el mínimo del
        destino sería inventar una respuesta."""
        with self.assertRaises(math_core.ValorError) as caso:
            self.evaluar("math_remap", {"valor": 5, "origen": (2, 2), "destino": (0, 100)})
        self.assertEqual(caso.exception.pin, "origen")

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
        g.add("math_remap", {"valor": 5, "origen": "0,10", "destino": "0,100"}, nid="mapa")
        g.add("math_saturate", {}, nid="sat")
        g.add("math_round", {}, nid="red")
        g.connect("mapa", "sat", "valor")
        g.connect("sat", "red", "valor")
        plan = compilar(g)
        self.assertEqual(plan.values_by_node["mapa"], 50.0)
        self.assertEqual(plan.values_by_node["sat"], 1.0)
        self.assertEqual(plan.values_by_node["red"], 1.0)


class InterruptorBooleanoTests(unittest.TestCase):
    """El literal booleano: peldaño 0 de la escalera de Grasshopper Basics.

    El hueco medido antes de existir: **43 verbos con 70 parámetros booleanos y CERO nodos capaces
    de producir un booleano**. Las comparaciones producían `B` pero no había de dónde sacar un «sí»
    constante, así que esos 70 parámetros sólo se podían tocar a mano en cada ficha, nunca manejar
    desde el lienzo. Es el «Boolean Toggle» que el tutorial usa para cerrar una polilínea.
    """

    def evaluar(self, valor):
        return math_core.evaluar("boolean", {"value": valor}, {}, lambda *_a: None)

    def test_produce_un_booleano_de_verdad_y_no_un_numero(self) -> None:
        self.assertEqual(math_core.tipo_salida("boolean"), "B")
        self.assertIs(self.evaluar(True), True)
        self.assertIs(self.evaluar(False), False)

    def test_el_texto_falso_NO_es_verdadero(self) -> None:
        """`bool("false")` en Python es True, porque toda cadena no vacía lo es. El canvas y los
        `.jamgraph` guardan los params como TEXTO, así que sin esta conversión un interruptor
        apagado se leería prendido al abrir el archivo — y el nodo se dibujaría bien igual."""
        self.assertIs(self.evaluar("false"), False)
        self.assertIs(self.evaluar("False"), False)
        self.assertIs(self.evaluar("0"), False)
        self.assertIs(bool("false"), True)

    def test_las_formas_de_decir_que_si(self) -> None:
        for texto in ("true", "True", "1", "si", "sí", "yes", "on", "verdadero"):
            with self.subTest(texto=texto):
                self.assertIs(self.evaluar(texto), True)

    def test_esta_en_flow_y_en_el_ribbon_con_sus_hermanos(self) -> None:
        self.assertIn("boolean", flow.OPS_META)
        self.assertEqual(ribbon.grupo_de("Params", "boolean"), "Valores")

    def test_maneja_un_parametro_booleano_de_otro_nodo(self) -> None:
        """La razón de existir: cablearlo a uno de los 70 params booleanos del registro."""
        g = JamGraph()
        g.add("boolean", {"value": True}, nid="cerrar")
        g.add("mesh_cone", {"base_radius": 50.0}, nid="cono")
        g.connect("cerrar", "cono", "capped")
        plan = compilar(g)
        self.assertIs(plan.values_by_node["cerrar"], True)


class AngulosInversosYTiempoTests(unittest.TestCase):
    """Los dos grupos que Brian pidió mirando el tab Maths de Grasshopper: Trig y Time.

    Del panel Trig faltaba lo que de verdad agrega capacidad —las inversas—; del panel Time,
    horas/minutos/segundos. Las funciones recíprocas (Secante, Cosecante, Cotangente) NO se
    agregaron a propósito: son `1/cos`, `1/sen` y `1/tan`, el grafo ya las puede escribir con
    Dividir, y triplicarían el grupo sin capacidad nueva.
    """

    def evaluar(self, verbo, params):
        return math_core.evaluar(verbo, params, {}, lambda *_a: None)

    def test_las_inversas_deshacen_a_las_directas(self) -> None:
        for angulo in (0.0, 0.3, 1.0, -0.7):
            with self.subTest(angulo=angulo):
                seno = self.evaluar("math_sin", {"radianes": angulo})
                self.assertAlmostEqual(self.evaluar("math_asin", {"seno": seno}), angulo)

    def test_fuera_del_dominio_falla_nombrando_el_pin(self) -> None:
        """`math.asin(2)` tira un ValueError con texto del intérprete que no dice DÓNDE está el
        problema, que es lo único accionable en un grafo de 30 nodos."""
        for verbo, pin in (("math_asin", "seno"), ("math_acos", "coseno")):
            with self.subTest(verbo=verbo):
                with self.assertRaises(math_core.ValorError) as caso:
                    self.evaluar(verbo, {pin: 2.0})
                self.assertEqual(caso.exception.pin, pin)

    def test_el_angulo_de_un_vector_conserva_el_CUADRANTE(self) -> None:
        """Es la diferencia entre `atan2` y `atan(y/x)`: la segunda confunde arriba con abajo y
        explota mirando en vertical, que es justo el caso de apuntar."""
        casos = ((1, 1, 45.0), (1, -1, 135.0), (-1, -1, -135.0), (-1, 1, -45.0), (1, 0, 90.0))
        for y, x, grados in casos:
            with self.subTest(y=y, x=x):
                radianes = self.evaluar("math_atan2", {"y": y, "x": x})
                self.assertAlmostEqual(self.evaluar("math_degrees", {"radianes": radianes}), grados)

    def test_el_angulo_de_un_vector_vertical_no_explota(self) -> None:
        self.assertAlmostEqual(self.evaluar("math_atan2", {"y": 5, "x": 0}), math.pi / 2)

    def test_armar_un_tiempo_no_normaliza(self) -> None:
        """Sumar es exactamente lo que alguien quiere al escribir «dos horas y 90 minutos».
        Normalizarlo a 3h30 sería decidir por el otro."""
        self.assertEqual(self.evaluar("time_construct",
                                      {"horas": 2, "minutos": 90, "segundos": 0}), 12600.0)
        self.assertEqual(self.evaluar("time_construct",
                                      {"horas": 1, "minutos": 30, "segundos": 45}), 5445.0)

    def test_las_partes_de_una_duracion(self) -> None:
        for unidad, esperado in (("horas", 1.0), ("minutos", 30.0), ("segundos", 45.0)):
            with self.subTest(unidad=unidad):
                self.assertEqual(self.evaluar(f"time_{unidad}", {"total": 5445.0}), esperado)

    def test_una_duracion_negativa_se_lee_como_reloj_y_no_como_modulo(self) -> None:
        """Con el `//` de Python, -5445 daría «-2 h 30 m»: correcto como módulo euclídeo y absurdo
        leído como reloj. Truncar hacia el CERO da «-1 h 30 m», que es lo que dice un contador que
        se pasó."""
        self.assertEqual(self.evaluar("time_horas", {"total": -5445.0}), -1.0)
        self.assertEqual(self.evaluar("time_minutos", {"total": -5445.0}), -30.0)
        self.assertEqual(self.evaluar("time_segundos", {"total": -5445.0}), -45.0)

    def test_ida_y_vuelta_por_el_ejecutor_real(self) -> None:
        """Armar 1h30m45s y volver a sacarle las horas tiene que dar 1, encadenado."""
        g = JamGraph()
        g.add("time_construct", {"horas": 1, "minutos": 30, "segundos": 45}, nid="dur")
        g.add("time_horas", {}, nid="h")
        g.connect("dur", "h", "total")
        plan = compilar(g)
        self.assertEqual(plan.values_by_node["dur"], 5445.0)
        self.assertEqual(plan.values_by_node["h"], 1.0)

    def test_todos_estan_en_flow_y_en_el_ribbon(self) -> None:
        grupos = {
            "Trigonometría": ["math_asin", "math_acos", "math_atan", "math_atan2"],
            "Tiempo": ["time_construct", "time_horas", "time_minutos", "time_segundos"],
        }
        for grupo, verbos in grupos.items():
            for verbo in verbos:
                with self.subTest(verbo=verbo):
                    self.assertIn(verbo, flow.OPS_META)
                    self.assertEqual(ribbon.grupo_de("Maths", verbo), grupo)


class TipoVectorTests(unittest.TestCase):
    """Peldaño 1 de la escalera: el tipo `V`.

    Es el que desbloquea Line SDL, Move con dirección y las matrices — y el que el tutorial de
    Harmon necesita ya en su SEGUNDA figura (Unit X / Unit Z). Se eligió TIPO PROPIO y no un `N[]`
    de tres: la compatibilidad del Graph es por letra exacta, así que un tipo propio regala la
    guarda —un número o una serie de siete no entran en un pin de dirección— y un `N[]` la perdería
    justo donde más duele, porque el error se vería recién en la geometría.
    """

    def evaluar(self, verbo, params):
        return math_core.evaluar(verbo, params, {}, lambda *_a: None)

    def test_un_vector_son_tres_numeros_finitos(self) -> None:
        self.assertEqual(math_core._vector((1, 2, 3), "p"), (1.0, 2.0, 3.0))
        self.assertEqual(math_core._vector("0,0,1", "p"), (0.0, 0.0, 1.0))
        self.assertEqual(math_core._vector("1 2 3", "p"), (1.0, 2.0, 3.0))

    def test_el_texto_es_el_caso_REAL_y_no_una_comodidad(self) -> None:
        """Un pin `V` sin cable recibe lo que quedó guardado en el `.jamgraph`, que es TEXTO. Es el
        mismo motivo por el que `_booleano` existe."""
        self.assertEqual(math_core._vector("(0, 0, 1)", "p"), (0.0, 0.0, 1.0))

    def test_un_numero_suelto_NO_es_un_vector(self) -> None:
        """(n,n,n) y (n,0,0) son las dos lecturas posibles: elegir una en silencio haría que la
        mitad de las veces apunte a otro lado."""
        with self.assertRaises(math_core.ValorError) as caso:
            math_core._vector("5", "direccion")
        self.assertEqual(caso.exception.pin, "direccion")

    def test_el_vector_cero_no_tiene_direccion(self) -> None:
        """Devolver (0,0,0) propagaría «para ningún lado» adentro de una cadena que va a orientar
        algo: la pieza queda con su rotación anterior y el síntoma aparece a diez nodos de la causa."""
        with self.assertRaises(math_core.ValorError):
            self.evaluar("vector_normalize", {"vector": (0, 0, 0)})

    def test_los_unitarios_son_los_ejes_de_unreal(self) -> None:
        self.assertEqual(self.evaluar("vector_unit_x", {"largo": 1}), (1.0, 0.0, 0.0))
        self.assertEqual(self.evaluar("vector_unit_y", {"largo": 1}), (0.0, 1.0, 0.0))
        self.assertEqual(self.evaluar("vector_unit_z", {"largo": 5}), (0.0, 0.0, 5.0))

    def test_construir_medir_y_normalizar(self) -> None:
        self.assertEqual(self.evaluar("vector_construct", {"x": 3, "y": 4, "z": 0}), (3.0, 4.0, 0.0))
        self.assertEqual(self.evaluar("vector_length", {"vector": (3, 4, 0)}), 5.0)
        self.assertEqual(self.evaluar("vector_normalize", {"vector": (3, 4, 0)}), (0.6, 0.8, 0.0))

    def test_las_componentes_son_la_descomposicion(self) -> None:
        """Tres verbos y no uno porque ningún verbo de Jam tiene más de una salida: el patrón
        «Deconstruct» de Grasshopper no se puede expresar todavía."""
        for verbo, esperado in (("vector_x", 3.0), ("vector_y", 4.0), ("vector_z", 5.0)):
            with self.subTest(verbo=verbo):
                self.assertEqual(self.evaluar(verbo, {"vector": (3, 4, 5)}), esperado)

    def test_punto_y_cruz(self) -> None:
        self.assertEqual(self.evaluar("vector_dot", {"a": (1, 0, 0), "b": (1, 0, 0)}), 1.0)
        self.assertEqual(self.evaluar("vector_dot", {"a": (1, 0, 0), "b": (0, 1, 0)}), 0.0)
        # X cruz Y da Z: la regla de la mano derecha, que es la de Unreal.
        self.assertEqual(self.evaluar("vector_cross", {"a": (1, 0, 0), "b": (0, 1, 0)}), (0.0, 0.0, 1.0))

    def test_el_producto_punto_de_unitarios_es_el_coseno(self) -> None:
        a = self.evaluar("vector_normalize", {"vector": (1, 1, 0)})
        coseno = self.evaluar("vector_dot", {"a": a, "b": (1, 0, 0)})
        self.assertAlmostEqual(self.evaluar("math_degrees",
                                            {"radianes": self.evaluar("math_acos",
                                                                      {"coseno": coseno})}), 45.0)

    def test_el_tipo_viaja_en_los_pines(self) -> None:
        self.assertEqual(math_core.tipo_salida("vector_construct"), "V")
        self.assertEqual(math_core.tipo_salida("vector_length"), "N")
        self.assertEqual(math_core.tipo_param("vector_length", "vector"), "V")
        self.assertEqual(math_core.tipo_param("vector_construct", "x"), "N")

    def test_el_Graph_RECHAZA_cablear_un_numero_donde_va_un_vector(self) -> None:
        """La razón entera de que `V` sea un tipo propio y no un `N[]`."""
        g = JamGraph()
        g.add("number", {"value": 5}, nid="n")
        g.add("vector_length", {}, nid="largo")
        g.connect("n", "largo", "vector")
        with self.assertRaises(GraphValidationError):
            compilar(g)

    def test_una_cadena_de_vectores_por_el_ejecutor_real(self) -> None:
        """Unitario Z por 10, sumarle X por 10, y medir: √200 ≈ 14,14."""
        g = JamGraph()
        g.add("vector_unit_z", {"largo": 10}, nid="arriba")
        g.add("vector_unit_x", {"largo": 10}, nid="adelante")
        g.add("vector_add", {}, nid="suma")
        g.add("vector_length", {}, nid="largo")
        g.connect("arriba", "suma", "a")
        g.connect("adelante", "suma", "b")
        g.connect("suma", "largo", "vector")
        plan = compilar(g)
        self.assertEqual(plan.values_by_node["suma"], (10.0, 0.0, 10.0))
        self.assertAlmostEqual(plan.values_by_node["largo"], math.sqrt(200.0))


class TipoDominioTests(unittest.TestCase):
    """El tipo `D`: un rango con nombre, en vez de dos números sueltos que hay que no cruzar.

    Del tab Maths de Grasshopper, el panel Domain. Lo que lo justifica no son verbos nuevos sino lo
    que ARREGLA: Jam tenía cuatro verbos cargando un rango cada uno —`math_remap` con cuatro pines,
    `math_clamp`, `series_range`, `series_remap` con otros cuatro— y ninguno compartía nada. Con los
    pines sueltos, cablear el máximo del origen en el mínimo del destino es un error de un pin de
    distancia y **sin síntoma**, porque el número que sale sigue siendo plausible.
    """

    def evaluar(self, verbo, params):
        return math_core.evaluar(verbo, params, {}, lambda *_a: None)

    def test_un_dominio_son_dos_numeros(self) -> None:
        self.assertEqual(math_core._dominio((0, 100), "p"), (0.0, 100.0))
        self.assertEqual(math_core._dominio("0,100", "p"), (0.0, 100.0))
        self.assertEqual(math_core._dominio("0 100", "p"), (0.0, 100.0))

    def test_un_numero_suelto_no_es_un_dominio(self) -> None:
        with self.assertRaises(math_core.ValorError) as caso:
            math_core._dominio("5", "rango")
        self.assertEqual(caso.exception.pin, "rango")

    def test_un_dominio_AL_REVES_es_valido(self) -> None:
        """Remapear hacia un destino invertido es exactamente cómo se da vuelta un rango. Rechazarlo
        sacaría una capacidad real para prevenir un error que no existe: nadie escribe «de 100 a 0»
        sin querer."""
        self.assertEqual(math_core._dominio("100,0", "p"), (100.0, 0.0))
        self.assertEqual(self.evaluar("domain_length", {"dominio": (100, 0)}), 100.0)

    def test_armar_y_desarmar(self) -> None:
        """Dos verbos para desarmar y no uno con dos salidas: ningún verbo de Jam tiene más de una
        salida todavía. Es el mismo límite que obliga a `time_horas`/`time_minutos`."""
        self.assertEqual(self.evaluar("domain_construct", {"desde": 0, "hasta": 360}), (0.0, 360.0))
        self.assertEqual(self.evaluar("domain_min", {"dominio": (0, 360)}), 0.0)
        self.assertEqual(self.evaluar("domain_max", {"dominio": (0, 360)}), 360.0)

    def test_esta_adentro_INCLUYE_los_extremos(self) -> None:
        """Incluirlos es lo que hace que sirva para partir un recorrido en tramos sin que el punto
        de la juntura se caiga de los dos lados."""
        for valor, esperado in ((0, True), (45, True), (360, True), (-1, False), (361, False)):
            with self.subTest(valor=valor):
                self.assertIs(self.evaluar("domain_includes",
                                           {"dominio": (0, 360), "valor": valor}), esperado)

    def test_esta_adentro_no_se_confunde_con_un_dominio_al_reves(self) -> None:
        self.assertIs(self.evaluar("domain_includes", {"dominio": (360, 0), "valor": 45}), True)

    def test_el_tipo_viaja_en_los_pines(self) -> None:
        self.assertEqual(math_core.tipo_salida("domain_construct"), "D")
        self.assertEqual(math_core.tipo_salida("domain_length"), "N")
        self.assertEqual(math_core.tipo_salida("domain_includes"), "B")
        self.assertEqual(math_core.tipo_param("math_remap", "origen"), "D")

    def test_el_Graph_RECHAZA_un_numero_donde_va_un_dominio(self) -> None:
        """La razón entera de que sea un tipo: con cuatro números sueltos, cruzarlos compilaba."""
        g = JamGraph()
        g.add("number", {"value": 5}, nid="n")
        g.add("domain_length", {}, nid="largo")
        g.connect("n", "largo", "dominio")
        with self.assertRaises(GraphValidationError):
            compilar(g)

    def test_una_cadena_de_dominios_por_el_ejecutor_real(self) -> None:
        """Armar 0..360, preguntar si 45 está adentro, y remapear 45 a 0..1."""
        g = JamGraph()
        g.add("domain_construct", {"desde": 0, "hasta": 360}, nid="vuelta")
        g.add("domain_includes", {"valor": 45}, nid="adentro")
        g.add("math_remap", {"valor": 45, "destino": "0,1"}, nid="normalizado")
        g.connect("vuelta", "adentro", "dominio")
        g.connect("vuelta", "normalizado", "origen")
        plan = compilar(g)
        self.assertEqual(plan.values_by_node["vuelta"], (0.0, 360.0))
        self.assertIs(plan.values_by_node["adentro"], True)
        self.assertAlmostEqual(plan.values_by_node["normalizado"], 0.125)

    def test_todos_estan_en_flow_y_en_el_ribbon(self) -> None:
        for verbo in ("domain_construct", "domain_min", "domain_max", "domain_length",
                      "domain_includes"):
            with self.subTest(verbo=verbo):
                self.assertIn(verbo, flow.OPS_META)
                self.assertEqual(ribbon.grupo_de("Maths", verbo), "Dominio")
