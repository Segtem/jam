"""Multi-salida: un verbo con más de un pin de salida (el patrón Deconstruct de Grasshopper).

Lo que estos tests fijan, en orden de importancia:

1. **La propiedad aditiva.** Un verbo SIN `outs` se comporta exactamente como antes de que esto
   existiera. Es lo que hace seguro el cambio: los usos de `out_name` repartidos por el árbol no se
   tocaron, y si esta propiedad se rompe, se rompe todo el resto del Graph a la vez.
2. Dos salidas del mismo nodo entregan valores DISTINTOS a destinos distintos.
3. El nodo corre UNA sola vez aunque se le lean las dos salidas — la razón por la que las salidas
   extra son rebanadas del resultado y no cómputos aparte.
4. Compile rechaza un pin de salida que no existe, y lo dice con el nombre adentro.
5. Lo viejo sigue andando: `domain_min`/`domain_max` no se tocaron.
"""
from __future__ import annotations

import json
import sys
import types
import unittest

_unreal_fake = sys.modules.setdefault("unreal", types.ModuleType("unreal"))
if not hasattr(_unreal_fake, "TopLevelAssetPath"):
    _unreal_fake.TopLevelAssetPath = lambda package, name: (package, name)

from jam import api, graph as G, math_core
from jam.graph import GraphValidationError, JamGraph


class SalidasExtraDeclaradas(unittest.TestCase):
    def test_el_pin_principal_se_llama_igual_en_los_dos_modulos(self):
        # `math_core` repite la constante en vez de importarla de `graph` (ciclo). Si alguien
        # renombra una de las dos, las salidas extra dejarían de resolverse en los nodos de valor y
        # el síntoma sería un `None` silencioso, no un error.
        self.assertEqual(math_core.PIN_SALIDA, G.PIN_OUT)

    def test_casi_ningun_verbo_declara_salidas_extra(self):
        from jam import tools
        con_extra = [v for v in tools.REGISTRO if G.salidas_extra(v, tools.REGISTRO)]
        self.assertEqual(con_extra, [], "ningún verbo de herramienta las declara todavía")

    def test_el_dominio_declara_sus_dos_extremos(self):
        extra = math_core.salidas_extra("domain_construct")
        self.assertEqual([(pin, tipo) for pin, tipo, _e, _c in extra],
                         [("desde", "N"), ("hasta", "N")])

    def test_ninguna_salida_extra_puede_llamarse_out(self):
        # «out» es la principal. Una extra con ese nombre la taparía y el nodo devolvería su
        # rebanada donde el resto del Graph espera el resultado entero.
        for verbo in math_core.VALORES:
            for pin, _t, _e, _c in math_core.salidas_extra(verbo):
                self.assertNotEqual(pin, G.PIN_OUT, f"{verbo} declara una salida llamada «out»")

    def test_la_rebanada_es_invocable_y_saca_la_parte_que_dice(self):
        extra = dict((pin, corte) for pin, _t, _e, corte in
                     math_core.salidas_extra("domain_construct"))
        self.assertEqual(extra["desde"]((10.0, 90.0)), 10.0)
        self.assertEqual(extra["hasta"]((10.0, 90.0)), 90.0)


class ElTipoSaleDelPin(unittest.TestCase):
    def test_sin_pin_devuelve_el_de_la_salida_principal(self):
        # La firma histórica: quien no sabe de pines pregunta lo mismo y recibe lo mismo.
        self.assertEqual(G._tipo_salida("domain_construct", {}), "D")

    def test_con_pin_devuelve_el_de_esa_salida(self):
        self.assertEqual(G._tipo_salida("domain_construct", {}, "desde"), "N")
        self.assertEqual(G._tipo_salida("domain_construct", {}, "hasta"), "N")

    def test_un_pin_inexistente_no_tiene_tipo(self):
        self.assertIsNone(G._tipo_salida("domain_construct", {}, "medio"))


def _dominio_a_dos_destinos(pin_a="desde", pin_b="hasta"):
    g = JamGraph()
    g.add("domain_construct", {"desde": 10.0, "hasta": 90.0}, nid="dom")
    g.add("math_add", {"a": 0.0, "b": 0.0}, nid="suma")
    g.connect("dom", "suma", "a", origen_pin=pin_a)
    g.connect("dom", "suma", "b", origen_pin=pin_b)
    return g


class DosSalidasCableadas(unittest.TestCase):
    def test_cada_pin_entrega_su_parte(self):
        g = _dominio_a_dos_destinos()
        _rep, por_nodo = G.ejecutar_detalle(g, G.compilar(g))
        # 10 + 90: si las dos salidas entregaran lo mismo daría 20 o 180, y si entregaran el
        # dominio entero no resolvería. Es el assert que distingue las tres cosas de una vez.
        self.assertIn("100.0", por_nodo["suma"]["texto"])

    def test_las_dos_salidas_no_son_intercambiables(self):
        # Cruzar los cables tiene que dar el MISMO número acá (la suma es conmutativa), así que la
        # discriminación se hace con una resta, donde el orden importa.
        g = JamGraph()
        g.add("domain_construct", {"desde": 10.0, "hasta": 90.0}, nid="dom")
        g.add("math_subtract", {"minuendo": 0.0, "sustraendo": 0.0}, nid="resta")
        g.connect("dom", "resta", "minuendo", origen_pin="hasta")
        g.connect("dom", "resta", "sustraendo", origen_pin="desde")
        _rep, por_nodo = G.ejecutar_detalle(g, G.compilar(g))
        self.assertIn("80.0", por_nodo["resta"]["texto"])

    def test_la_salida_principal_sigue_dando_el_dominio_entero(self):
        g = JamGraph()
        g.add("domain_construct", {"desde": 10.0, "hasta": 90.0}, nid="dom")
        g.add("domain_length", {}, nid="largo")
        g.connect("dom", "largo", "dominio")  # sin origen_pin: la principal
        _rep, por_nodo = G.ejecutar_detalle(g, G.compilar(g))
        self.assertIn("80.0", por_nodo["largo"]["texto"])

    def _evaluaciones(self, g):
        """Cuántas veces se evalúa `domain_construct` al correr `g`."""
        vueltas = []
        original = math_core.VALORES["domain_construct"]["operacion"]

        def contando(desde, hasta):
            vueltas.append((desde, hasta))
            return original(desde, hasta)

        math_core.VALORES["domain_construct"]["operacion"] = contando
        try:
            G.ejecutar_detalle(g, G.compilar(g))
        finally:
            math_core.VALORES["domain_construct"]["operacion"] = original
        return len(vueltas)

    def test_leer_dos_salidas_no_cuesta_mas_que_leer_una(self):
        """La razón de que las salidas extra sean REBANADAS y no cómputos aparte.

        ⚠️ Se pregunta CONTRA UN CONTROL y no por un número absoluto. La primera versión de este
        test exigía «corre una sola vez» y salió roja con 2 — pero el control mostró que un nodo de
        valor se evalúa dos veces **siempre**, por el punto fijo de `math_core.resolver`, aun estando
        solo en el grafo y sin ninguna salida extra. Exigir el absoluto habría fijado en un test una
        propiedad ajena a esto, y arreglar el «defecto» habría sido tocar el resolver sin motivo.
        Lo que de verdad hay que impedir es que el costo ESCALE con la cantidad de pines leídos: con
        un verbo que escribe assets, una ejecución por pin sería catastrófica y silenciosa.
        """
        una = self._evaluaciones(self._una_salida())
        dos = self._evaluaciones(_dominio_a_dos_destinos())
        self.assertEqual(dos, una,
                         f"leer dos salidas costó {dos} evaluaciones contra {una} leyendo una")

    @staticmethod
    def _una_salida():
        g = JamGraph()
        g.add("domain_construct", {"desde": 10.0, "hasta": 90.0}, nid="dom")
        g.add("domain_length", {}, nid="largo")
        g.connect("dom", "largo", "dominio")
        return g


class ElEjecutorTambienRebana(unittest.TestCase):
    """El otro camino, y no es el mismo código.

    Un nodo de VALOR (`domain_construct`) resuelve por `math_core.resolver`; un verbo de
    HERRAMIENTA resuelve por `graph.ejecutar_detalle`, que sirve los cables con
    `valor_por_el_cable`. Las dos mitades tienen que rebanar igual.

    ⚠️ Este caso no estaba, y lo delató una mutación: neutralizar `valor_por_el_cable` —hacerle
    devolver siempre la salida principal— dejaba los 20 tests en VERDE, porque todos pasaban por
    nodos de valor. El agujero estaba en los tests, no en el código. Es además el camino que va a
    usar Matrix, que es un verbo de herramienta y no un valor.
    """

    def setUp(self):
        from jam import tools
        self.tools = tools
        self.registro_original = dict(tools.REGISTRO)

        def parte(entrada, **kw):
            # Como cualquier verbo real que produce un dato rico: lo publica en el runtime.
            tools._RUNTIME_DATA_OUTPUTS["falso_par"] = (7.0, 11.0)
            return "par ✓"

        self.recibido = {}

        def anota(entrada, **kw):
            self.recibido.update(kw)
            return f"anotado {kw}"

        tools.REGISTRO["falso_par"] = {
            "source": True, "aridad": 0, "min_inputs": 0, "in_name": "", "out_name": "D",
            "asset_required": False, "asset_pin": False, "asset_row": False,
            "params": {}, "fn": parte, "doc": "",
            "outs": (("desde", "N", "desde", lambda p: p[0]),
                     ("hasta", "N", "hasta", lambda p: p[1])),
        }
        tools.REGISTRO["falso_anota"] = {
            "source": True, "aridad": 0, "min_inputs": 0, "in_name": "", "out_name": "T",
            "asset_required": False, "asset_pin": False, "asset_row": False,
            "params": {"uno": 0.0, "otro": 0.0}, "fn": anota, "doc": "",
            "data_params": {"uno": "N", "otro": "N"},
        }

    def tearDown(self):
        self.tools.REGISTRO.clear()
        self.tools.REGISTRO.update(self.registro_original)
        self.tools._RUNTIME_DATA_OUTPUTS.pop("falso_par", None)

    def test_cada_pin_de_un_verbo_de_herramienta_entrega_su_parte(self):
        g = JamGraph()
        g.add("falso_par", {}, nid="par")
        g.add("falso_anota", {}, nid="anota")
        g.connect("par", "anota", "uno", origen_pin="desde")
        g.connect("par", "anota", "otro", origen_pin="hasta")
        G.ejecutar_detalle(g, G.compilar(g))
        self.assertEqual(self.recibido.get("uno"), 7.0)
        self.assertEqual(self.recibido.get("otro"), 11.0)

    def test_la_salida_principal_de_un_verbo_de_herramienta_sigue_entera(self):
        from jam import tools
        tools.REGISTRO["falso_entero"] = dict(
            tools.REGISTRO["falso_anota"], data_params={"uno": "D"}, params={"uno": ""})
        g = JamGraph()
        g.add("falso_par", {}, nid="par")
        g.add("falso_entero", {}, nid="entero")
        g.connect("par", "entero", "uno")  # sin origen_pin
        G.ejecutar_detalle(g, G.compilar(g))
        self.assertEqual(self.recibido.get("uno"), (7.0, 11.0))


class CompileRechazaLoQueNoExiste(unittest.TestCase):
    def test_un_pin_de_salida_inventado_es_error(self):
        g = JamGraph()
        g.add("domain_construct", {}, nid="dom")
        g.add("math_add", {}, nid="suma")
        g.connect("dom", "suma", "a", origen_pin="medio")
        with self.assertRaises(GraphValidationError) as caja:
            G.compilar(g)
        mensaje = " ".join(caja.exception.diagnostics["dom"])
        self.assertIn("medio", mensaje, "el error tiene que nombrar el pin que falló")
        # Y las que sí existen, porque el que se equivocó de nombre casi siempre quería una de ésas.
        self.assertIn("desde", mensaje)
        self.assertIn("hasta", mensaje)

    def test_un_verbo_sin_salidas_extra_lo_dice(self):
        g = JamGraph()
        g.add("number", {"value": 3.0}, nid="n")
        g.add("math_add", {}, nid="suma")
        g.connect("n", "suma", "a", origen_pin="parte")
        with self.assertRaises(GraphValidationError) as caja:
            G.compilar(g)
        self.assertIn("sólo tiene", " ".join(caja.exception.diagnostics["n"]))

    def test_el_tipo_de_la_salida_extra_se_verifica(self):
        # `desde` es N. Cablearla a un pin que espera otra cosa tiene que fallar por TIPO, no
        # pasar porque el nodo de origen «es un dominio».
        g = JamGraph()
        g.add("domain_construct", {}, nid="dom")
        g.add("domain_length", {}, nid="largo")
        g.connect("dom", "largo", "dominio", origen_pin="desde")
        with self.assertRaises(GraphValidationError) as caja:
            G.compilar(g)
        self.assertIn("N", " ".join(caja.exception.diagnostics["dom"]))


class PorLaPUERTAPublica(unittest.TestCase):
    """Por `api.compile_graph_json`, que es por donde entra el editor.

    ⚠️ Estos tests nacieron de un rojo del camino real con los 22 puros en VERDE. Un grafo de puros
    nodos de valor **no entra por `graph.compilar`**: entra por el preflight de `flow.py`, que es una
    validación PARALELA con su propio `_tipo_salida`. Enseñarle multi-salida a un lado y no al otro
    dejaba el Compile rechazando «pin de salida desconocido: desde» mientras los tests que llamaban
    a `compilar` directo seguían pasando. Llamar a la función es el ATAJO; la puerta pública es el
    camino, y es la que ejercen las dos mitades a la vez.
    """

    def compilar(self, g):
        return json.loads(api.compile_graph_json(g.to_json()))

    def correr(self, g):
        return json.loads(api.run_graph_json(g.to_json()))

    def test_las_dos_salidas_compilan_y_corren_por_la_api(self):
        g = _dominio_a_dos_destinos()
        c = self.compilar(g)
        self.assertTrue(c.get("ok"), c)
        r = self.correr(g)
        self.assertTrue(r.get("ok"), r)
        self.assertIn("100", r.get("report", ""))

    def test_el_pin_inventado_se_rechaza_por_la_api(self):
        g = JamGraph()
        g.add("domain_construct", {}, nid="dom")
        g.add("math_add", {}, nid="suma")
        g.connect("dom", "suma", "a", origen_pin="medio")
        c = self.compilar(g)
        self.assertFalse(c.get("ok"), c)
        self.assertIn("medio", json.dumps(c, ensure_ascii=False))

    def test_un_grafo_de_siempre_sigue_igual_por_la_api(self):
        g = JamGraph()
        g.add("number", {"name": "ancho", "value": 30.0}, nid="n")
        g.add("math_multiply", {"a": 0.0, "b": 2.0}, nid="doble")
        g.connect("n", "doble", "a")
        r = self.correr(g)
        self.assertTrue(r.get("ok"), r)
        self.assertIn("60", r.get("report", ""))


class LoAditivo(unittest.TestCase):
    """La propiedad que hace seguro todo lo demás."""

    def test_un_grafo_sin_salidas_extra_compila_y_corre_igual(self):
        g = JamGraph()
        g.add("number", {"name": "ancho", "value": 30.0}, nid="n")
        g.add("math_multiply", {"a": 0.0, "b": 2.0}, nid="doble")
        g.connect("n", "doble", "a")
        _rep, por_nodo = G.ejecutar_detalle(g, G.compilar(g))
        self.assertIn("60.0", por_nodo["doble"]["texto"])

    def test_los_verbos_viejos_del_dominio_siguen_andando(self):
        # Borrarlos rompería diagramas guardados; la capacidad nueva no los reemplaza todavía.
        for verbo, esperado in (("domain_min", "10.0"), ("domain_max", "90.0")):
            g = JamGraph()
            g.add("domain_construct", {"desde": 10.0, "hasta": 90.0}, nid="dom")
            g.add(verbo, {}, nid="extremo")
            g.connect("dom", "extremo", "dominio")
            _rep, por_nodo = G.ejecutar_detalle(g, G.compilar(g))
            self.assertIn(esperado, por_nodo["extremo"]["texto"], verbo)


class ElSpecLasPublica(unittest.TestCase):
    def test_el_spec_trae_las_salidas_extra_del_dominio(self):
        spec = json.loads(api.spec_all())
        porverbo = {t["verbo"]: t for t in spec["tools"]}
        # La clave es `name`, no `pin`: es la MISMA forma que ya usan `inputs`/`outputs` en el
        # spec, así que el C++ los lee con el mismo `LeerPines` en vez de una segunda ruta paralela.
        self.assertEqual(porverbo["domain_construct"]["outs"],
                         [{"name": "desde", "tipo": "N", "label": "desde"},
                          {"name": "hasta", "tipo": "N", "label": "hasta"}])

    def test_todos_los_demas_publican_una_lista_vacia(self):
        # Vacía y PRESENTE: si la clave faltara, el C++ tendría que distinguir «no hay» de «no vino»
        # y ésa es exactamente la clase de diferencia que se olvida en uno de los dos specs.
        spec = json.loads(api.spec_all())
        sin_clave = [t["verbo"] for t in spec["tools"] if "outs" not in t]
        self.assertEqual(sin_clave, [], "todo verbo publica «outs», aunque sea vacío")

    def test_la_rebanada_no_viaja_en_el_spec(self):
        # Es un invocable: si alguien lo metiera en el JSON, `json.dumps` reventaría. El test lo
        # fija para que el contrato quede escrito y no dependa de que el serializador se queje.
        spec = json.loads(api.spec_all())
        porverbo = {t["verbo"]: t for t in spec["tools"]}
        for salida in porverbo["domain_construct"]["outs"]:
            self.assertEqual(set(salida), {"name", "tipo", "label"})


class ElCppDibujaLosNubs(unittest.TestCase):
    """Lo que Slate tiene que hacer, leído del `.cpp`. No reemplaza mirarlo con los ojos."""

    from pathlib import Path
    RAIZ = Path(__file__).resolve().parents[3]

    def cpp(self, rel):
        return (self.RAIZ / rel).read_text(encoding="utf-8")

    def test_los_TRES_lugares_que_parsean_el_spec_leen_outs(self):
        # El spec se parsea en tres sitios distintos. Leerlo en uno solo deja la mitad de los nodos
        # sin sus pines extra según por dónde se los haya creado — es la trampa que ya costó que la
        # perilla de ángulos no apareciera, con la unidad agregada a un solo lado.
        modulo = self.cpp("Source/JamEditor/Private/JamEditorModule.cpp")
        editor = self.cpp("Source/JamEditor/Private/SJamGraphEditor.cpp")
        self.assertEqual(modulo.count('LeerPines(TEXT("outs")'), 1)
        self.assertEqual(editor.count('LeerPines(TEXT("outs")'), 2)

    def test_la_salida_principal_se_agrega_PRIMERA_y_explicita(self):
        # Las extras ACOMPAÑAN a `out`, no la reemplazan. El nub del header se apaga solo cuando hay
        # filas de salida, así que sin esta línea `domain_construct` perdería su pin `out` y todo
        # diagrama guardado que lo cablea se quedaría sin origen.
        editor = self.cpp("Source/JamEditor/Private/SJamGraphEditor.cpp")
        self.assertIn("T->OutputPins.Num() == 0 && T->SalidasExtra.Num() > 0", editor)
        principal = editor.index('NamedOutputs.Add(FJamNodePin{TEXT("out"), T->OutName')
        extras = editor.index("for (const FJamTool::FPin& P : T->SalidasExtra)")
        self.assertLess(principal, extras, "«out» va primera: su fila es la de arriba")

    def test_el_rotulo_del_header_se_apaga_cuando_hay_filas_de_salida(self):
        # Una palabra sin nub al lado se lee como una salida que no se puede cablear.
        nodo = self.cpp("Source/JamEditor/Private/SJamGraphNode.cpp")
        self.assertIn("InArgs._OutputPins.Num() == 0\n\t\t\t\t\t? InArgs._OutputLabel : FString()",
                      nodo)

    def test_el_tipo_de_salida_se_busca_en_UN_solo_lugar(self):
        # Antes había dos búsquedas parecidas en el .cpp; ahora las dos llaman al mismo helper.
        editor = self.cpp("Source/JamEditor/Private/SJamGraphEditor.cpp")
        self.assertEqual(editor.count("TipoDeSalida("), 2)
        self.assertNotIn("OutputPins.FindByPredicate", editor,
                         "la búsqueda de salida vive en FJamTool::TipoDeSalida, no suelta acá")


if __name__ == "__main__":
    unittest.main()
