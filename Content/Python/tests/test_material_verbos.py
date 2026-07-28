"""Contratos de los verbos genéricos de material: armar un shader nodo por nodo desde el canvas.

Lo que hace posible el verbo `material_node` es que la firma de los 409 `MaterialExpression` esté
DERIVADA del motor y no escrita a mano (`jam/shader_firmas.py`, generado). Sin eso, el verificador
tendría que rechazar como «tipo desconocido» todo lo que Jam no usara todavía, que es justo lo que
un verbo genérico existe para permitir.

El otro contrato es el que un test de topología no ve: que un error de armado **se detenga acá**, en
Python, con un mensaje que diga qué había que poner. Un grafo mal cableado que llega a Unreal no
falla: crea un asset con nodos sueltos y el problema aparece —si aparece— en un log de compilación
de shaders.
"""

from __future__ import annotations

import sys
import types
import unittest

sys.modules.setdefault("unreal", types.ModuleType("unreal"))

from jam import shader, shader_firmas, tools  # noqa: E402


class FirmasDelMotorTests(unittest.TestCase):
    def test_the_table_covers_the_whole_engine_and_not_just_what_jam_uses(self):
        """Cuarenta y pico de tipos alcanzaban mientras los grafos los escribiera Jam. Un verbo que
        acepta cualquier nodo necesita los 409, y a mano no se mantienen."""
        self.assertGreater(len(shader.ENTRADAS), 400)

    def test_the_generated_table_has_no_junk_entries(self):
        """`MaterialExpression` a secas es la clase base: sin filtrarla entra un tipo con nombre
        vacío que el verificador aceptaría como válido."""
        self.assertNotIn("", shader_firmas.ENTRADAS)
        self.assertTrue(all(t and t[0].isupper() for t in shader_firmas.ENTRADAS),
                        "hay nombres de tipo que no parecen nombres de tipo")

    def test_the_hand_written_table_agrees_with_the_engine(self):
        """La tabla escrita a mano queda como documentación de lo que `shader.py` usa. Si dijera
        algo distinto del motor, sería documentación que miente."""
        discrepan = {t: (mano, shader_firmas.ENTRADAS[t])
                     for t, mano in shader._ESCRITAS_A_MANO.items()
                     if t in shader_firmas.ENTRADAS and mano != shader_firmas.ENTRADAS[t]}
        self.assertEqual(discrepan, {})
        self.assertEqual([t for t in shader._ESCRITAS_A_MANO if t not in shader_firmas.ENTRADAS],
                         [], "tipos escritos a mano que el motor no tiene")

    def test_no_alias_shadows_a_type_that_actually_exists(self):
        """El caso que casi se cuela: `Mask` existe en el motor (es un blend de MaterialX), así que
        aliasarlo a `ComponentMask` habría dado EN SILENCIO otro nodo que el que dice el campo.
        Un alias sólo puede nombrar algo que no existe."""
        pisados = sorted(a for a in shader.ALIAS if a in shader_firmas.ENTRADAS)
        self.assertEqual(pisados, [], "estos alias tapan tipos reales del motor")

    def test_every_alias_points_at_a_type_that_exists(self):
        rotos = {a: d for a, d in shader.ALIAS.items() if d not in shader_firmas.ENTRADAS}
        self.assertEqual(rotos, {})

    def test_single_input_nodes_call_their_input_None(self):
        """El detalle que se adivina mal: `OneMinus` no es un nodo SIN entradas, su entrada se
        llama «None». Quien lo lea como «no tiene» va a cablearlo por índice y va a fallar."""
        self.assertEqual(shader.entradas_de("OneMinus"), ("None",))
        self.assertEqual(shader.entradas_de("Constant"), ())


class ConstructoresTests(unittest.TestCase):
    def test_adding_a_node_leaves_the_original_graph_untouched(self):
        """Por el cable viaja un VALOR. Si `con_nodo` mutara, un nodo del canvas que alimenta dos
        ramas le pisaría el grafo a la otra según el orden en que se evaluaran."""
        base = shader.vacio("M")
        antes = len(base.nodos)
        con_uno, _ = shader.con_nodo(base, "Constant", props={"r": 1.0})
        con_otro, _ = shader.con_nodo(base, "Multiply")
        self.assertEqual(len(base.nodos), antes)
        self.assertEqual([n.tipo for n in con_uno.nodos], ["Constant"])
        self.assertEqual([n.tipo for n in con_otro.nodos], ["Multiply"])

    def test_the_generated_ids_are_predictable(self):
        """`material_connect` referencia los nodos por id: con ids impredecibles habría que mirar
        el log para saber cómo se llamó el nodo que uno acaba de crear."""
        g = shader.vacio("M")
        g, a = shader.con_nodo(g, "Multiply")
        g, b = shader.con_nodo(g, "Multiply")
        g, c = shader.con_nodo(g, "Constant")
        self.assertEqual([a, b, c], ["multiply1", "multiply2", "constant1"])

    def test_it_refuses_a_duplicate_id(self):
        g, _ = shader.con_nodo(shader.vacio("M"), "Constant", id="uno")
        with self.assertRaises(ValueError):
            shader.con_nodo(g, "Multiply", id="uno")

    def test_the_editor_name_of_a_node_resolves_to_its_class_name(self):
        """«Lerp» no es un typo: es como se llama el nodo en la paleta de UE, y su clase es
        `LinearInterpolate`. Buscarlo por parecido no lo encuentra —no es ni subcadena—, así que
        rechazarlo sería mandar a alguien a adivinar el nombre interno."""
        g, creado = shader.con_nodo(shader.vacio("M"), "Lerp")
        self.assertEqual(g.nodo(creado).tipo, "LinearInterpolate",
                         "el IR tiene que guardar el nombre de CLASE: es el que busca el emisor")
        self.assertEqual(shader.entradas_de("Lerp"), ("A", "B", "Alpha"))

    def test_an_unknown_type_says_what_it_could_have_meant(self):
        """Con 408 tipos, «no existe» no alcanza: el error tiene que acercar al nombre correcto."""
        with self.assertRaises(ValueError) as caso:
            shader.con_nodo(shader.vacio("M"), "Noize")
        self.assertIn("no es un MaterialExpression", str(caso.exception))
        with self.assertRaises(ValueError) as parcial:
            shader.con_nodo(shader.vacio("M"), "Interpolate")
        self.assertIn("LinearInterpolate", str(parcial.exception))

    def test_a_wrong_input_name_lists_the_right_ones(self):
        g, _ = shader.con_nodo(shader.vacio("M"), "Constant", id="c")
        with self.assertRaises(ValueError) as caso:
            shader.con_nodo(g, "Power", entradas={"A": "c"})
        self.assertIn("Base", str(caso.exception))
        self.assertIn("Exp", str(caso.exception))

    def test_wiring_to_a_node_that_does_not_exist_is_caught_here(self):
        with self.assertRaises(ValueError) as caso:
            shader.con_nodo(shader.vacio("M"), "OneMinus", entradas={"None": "fantasma"})
        self.assertIn("fantasma", str(caso.exception))

    def test_a_channel_can_be_picked_with_a_dot(self):
        """`VertexColor.R` — un nodo con varias salidas se cablea eligiendo cuál."""
        g, _ = shader.con_nodo(shader.vacio("M"), "VertexColor", id="col")
        g, _ = shader.con_nodo(g, "OneMinus", id="inv", entradas={"None": "col.R"})
        arista = [a for a in g.aristas if a.hasta == "inv"][0]
        self.assertEqual((arista.desde, arista.salida), ("col", "R"))

    def test_connect_infers_the_input_when_there_is_only_one(self):
        g, _ = shader.con_nodo(shader.vacio("M"), "Constant", id="c")
        g, _ = shader.con_nodo(g, "Abs", id="a")
        g = shader.con_cable(g, "c", "a")
        self.assertEqual([a.entrada for a in g.aristas], ["None"])

    def test_connect_refuses_to_guess_when_there_are_several_inputs(self):
        """Adivinar acá sería elegir por el usuario cuál de las dos entradas de un `Add` quiso."""
        g, _ = shader.con_nodo(shader.vacio("M"), "Constant", id="c")
        g, _ = shader.con_nodo(g, "Add", id="s")
        with self.assertRaises(ValueError) as caso:
            shader.con_cable(g, "c", "s")
        self.assertIn("cuál", str(caso.exception))

    def test_an_output_that_is_not_a_material_output_is_refused(self):
        g, _ = shader.con_nodo(shader.vacio("M"), "Constant", id="c")
        with self.assertRaises(ValueError):
            shader.con_salida(g, "c", "MP_INVENTADA")


class ParseoTests(unittest.TestCase):
    def test_it_splits_on_the_first_equals_only(self):
        self.assertEqual(shader.parsear_pares("a=b=c"), {"a": "b=c"})

    def test_a_trailing_comma_is_someone_typing_not_an_error(self):
        self.assertEqual(shader.parsear_pares("A=uno, B=dos, "), {"A": "uno", "B": "dos"})

    def test_a_pair_without_equals_is_an_error(self):
        with self.assertRaises(ValueError):
            shader.parsear_pares("A=uno, dos")

    def test_props_type_the_obvious_literals_and_leave_the_rest_alone(self):
        """Números y booleanos se convierten acá porque el IR tiene que poder evaluarse sin Unreal.
        Lo demás queda en texto a propósito: el adaptador lo resuelve preguntándole a la propiedad
        qué tipo tiene, que es cómo llegan bien un enum y un color en hex."""
        self.assertEqual(
            shader.parsear_props("levels=3, scale=2.5, turbulence=false, "
                                 "noise_function=NOISEFUNCTION_VALUE_ALU"),
            {"levels": 3, "scale": 2.5, "turbulence": False,
             "noise_function": "NOISEFUNCTION_VALUE_ALU"})

    def test_a_negative_number_is_still_a_number(self):
        self.assertEqual(shader.parsear_props("r=-1, g=-0.5"), {"r": -1, "g": -0.5})


class VerbosTests(unittest.TestCase):
    """Por el camino del ejecutor: `fn(entrada, **params)`, con TODO lo que declara el registro."""

    def setUp(self):
        for verbo in ("material_node", "material_connect", "material_output"):
            tools.limpiar_asset_producido_runtime(verbo)

    def correr(self, verbo, entrada=None, **params):
        info = tools.REGISTRO[verbo]
        completos = dict(info["params"])
        completos.update(params)
        texto = info["fn"](entrada, **completos)
        return texto, tools.dato_producido_runtime(verbo)

    def test_the_first_node_starts_a_graph_without_an_input(self):
        """`material_node` tiene pin de entrada pero `min_inputs=0`: el primer nodo de una cadena
        no tiene de dónde venir, y obligar a un verbo `material_new` aparte sería un nodo de puro
        trámite en el canvas."""
        self.assertEqual(tools.REGISTRO["material_node"]["min_inputs"], 0)
        texto, grafo = self.correr("material_node", None, type="Constant", id="uno",
                                   props="r=0.5")
        self.assertIn("MATERIAL NODE", texto)
        self.assertEqual([n.id for n in grafo.nodos], ["uno"])
        self.assertEqual(grafo.nodo("uno").props, {"r": 0.5})

    def test_a_whole_material_can_be_built_by_chaining_the_verbs(self):
        """La prueba de que los cuatro verbos componen: se arma un material entero y se comprueba
        que CALCULA lo que tiene que calcular, no sólo que tenga los nodos."""
        _, g = self.correr("material_node", None, type="VertexNormalWS", id="n")
        _, g = self.correr("material_node", g, type="ComponentMask", id="nz",
                           inputs="None=n", props="r=false, g=false, b=true, a=false")
        _, g = self.correr("material_node", g, type="Abs", id="pos", inputs="None=nz")
        _, g = self.correr("material_node", g, type="ScalarParameter", id="k",
                           props="parameter_name=Dureza, default_value=3.0")
        _, g = self.correr("material_node", g, type="Power", id="p", inputs="Base=pos, Exp=k")
        _, g = self.correr("material_output", g, node="p", target="MP_ROUGHNESS")

        self.assertEqual(shader.verificar(g), [])
        self.assertEqual(shader.firma(g)["parametros"], ["Dureza"])
        # normal (0,0,0.5) → |0.5| elevado a 3 = 0.125
        valores = shader.evaluar(g, {"normal": (0.0, 0.0, 0.5)})
        self.assertAlmostEqual(valores["p"][0], 0.125, places=6)

    def test_connect_wires_two_nodes_that_already_exist(self):
        _, g = self.correr("material_node", None, type="Constant", id="a", props="r=2.0")
        _, g = self.correr("material_node", g, type="Constant", id="b", props="r=3.0")
        _, g = self.correr("material_node", g, type="Add", id="s")
        _, g = self.correr("material_connect", g, from_node="a", to_node="s", to_input="A")
        _, g = self.correr("material_connect", g, from_node="b", to_node="s", to_input="B")
        self.assertEqual(shader.evaluar(g, {})["s"][0], 5.0)

    def test_a_half_built_graph_is_reported_but_not_refused(self):
        """Mientras se encadenan nodos el grafo no alimenta ninguna salida. Plantarse ahí haría
        imposible armar nada de a poco; lo que corresponde es avisar y dejar seguir."""
        texto, g = self.correr("material_node", None, type="Constant", id="c")
        self.assertIn("pendiente", texto)
        self.assertNotEqual(shader.verificar(g), [])

    def test_build_refuses_a_graph_that_does_not_verify(self):
        """`material_build` es el que sí se planta: es el único que crea un asset.

        Se exige el mensaje del VERBO y no un «no es válido» cualquiera, porque `materials.emitir`
        también verifica: sin distinguir cuál de los dos rechazó, sacarle la verificación al verbo
        no rompía ningún test y el grafo llegaba a buscar y cargar el asset antes de frenar.
        """
        _, g = self.correr("material_node", None, type="Constant", id="c")
        with self.assertRaises(RuntimeError) as caso:
            tools.REGISTRO["material_build"]["fn"](g, **tools.REGISTRO["material_build"]["params"])
        self.assertIn("el grafo del material no es válido", str(caso.exception))

    def test_an_input_that_is_not_a_material_graph_says_so(self):
        with self.assertRaises(RuntimeError) as caso:
            self.correr("material_connect", "no soy un grafo", from_node="a", to_node="b")
        self.assertIn("grafo de material", str(caso.exception))

    def test_the_output_dropdown_and_the_verifier_share_one_list(self):
        """Si el desplegable ofreciera una salida que el verificador rechaza, el nodo se podría
        configurar desde la UI a un estado que nunca compila."""
        self.assertEqual(tuple(tools.REGISTRO["material_output"]["opciones"]["target"]),
                         shader.SALIDAS)


class RegistroTests(unittest.TestCase):
    def test_the_material_graph_travels_on_its_own_pin_type(self):
        """`MT` no es `M`: una malla y un grafo de material no se pueden enchufar entre sí."""
        for verbo in ("material_node", "material_connect", "material_output", "material_build"):
            self.assertEqual(tools.REGISTRO[verbo]["in_name"], "MT", verbo)
        for verbo in ("material_node", "material_connect", "material_output"):
            self.assertEqual(tools.REGISTRO[verbo]["out_name"], "MT", verbo)
        self.assertEqual(tools.REGISTRO["material_build"]["out_name"], "A",
                         "lo que sale de Build es un asset, no un grafo")


if __name__ == "__main__":
    unittest.main()
