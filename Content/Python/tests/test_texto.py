"""El texto de un grafo (`jam.texto`, tarea `dsl-grafos`): la segunda vista del mismo JamGraph.

La prueba que manda es la ida y vuelta sobre los grafos REALES —los 19 ejemplos y los presets de
grafo—, juzgada tres veces: la forma normal, el texto (imprimir∘leer es la identidad sobre el texto
canónico) y, como control independiente de la forma normal, el PLAN del Compile: orden, parámetros
resueltos y assets tienen que ser los mismos para el grafo original y para el releído del texto.
"""

from __future__ import annotations

import json
import sys
import types
import unittest
from pathlib import Path

_unreal_fake = sys.modules.setdefault("unreal", types.ModuleType("unreal"))
if not hasattr(_unreal_fake, "TopLevelAssetPath"):
    _unreal_fake.TopLevelAssetPath = lambda package, name: (package, name)

from jam import graph, registro, texto  # noqa: E402

RAIZ = Path(__file__).resolve().parents[3]
VOCAB = texto.vocabulario()


def _grafos_reales():
    for f in sorted((RAIZ / "Resources" / "Examples").glob("*.jamgraph")):
        yield f.name, graph.JamGraph.from_json(f.read_text(encoding="utf-8"))
    for f in sorted((RAIZ / "presets").glob("*.json")):
        d = json.loads(f.read_text(encoding="utf-8"))
        if "graph" in d:
            yield f.name, graph.JamGraph.from_json(json.dumps(d["graph"]))


def _plan(g):
    try:
        p = graph.compilar(g, registro=registro.REGISTRO)
        return ("ok", p.order, p.params, p.input_assets)
    except graph.GraphValidationError as e:
        return ("error", {k: sorted(m) for k, m in e.diagnostics.items()})


def _ida_y_vuelta(t):
    return texto.imprimir(texto.leer(t, VOCAB), VOCAB)


CYLINDER = """\
x = series_range end=720 count=7
y = graph_curve start_value=0 end_value=0 midpoint=0.48 mid_value=240 samples=7
z = graph_curve start_value=0 end_value=180 midpoint=0.62 mid_value=-80 samples=7
polyline = curve_polyline x=@x y=@y z=@z
smooth = curve_smooth @polyline iterations=3 strength=0.45
uniformar = curve_resample @smooth count=31
pipe = mesh_pipe @uniformar radius_start=26 radius_end=26 sides=12 samples=32 miter_limit=2.5
normals = mesh_normals @pipe
hornear = mesh_to_static @normals name=SM_JamCylinderStrip
colocar = place @hornear view=true
"""


class IdaYVueltaSobreGrafosReales(unittest.TestCase):
    def test_hay_grafos_que_mirar(self):
        # Un verificador sobre el conjunto vacío da verde (ver AGENTS.md).
        self.assertGreaterEqual(len(list(_grafos_reales())), 22)

    def test_grafo_texto_grafo_da_la_misma_forma_normal(self):
        for nombre, g in _grafos_reales():
            with self.subTest(nombre):
                g2 = texto.leer(texto.imprimir(g, VOCAB), VOCAB)
                self.assertEqual(texto.normal(g2, VOCAB), texto.normal(g, VOCAB))

    def test_el_texto_canonico_es_un_punto_fijo(self):
        for nombre, g in _grafos_reales():
            with self.subTest(nombre):
                t = texto.imprimir(g, VOCAB)
                self.assertEqual(_ida_y_vuelta(t), t)

    def test_el_compile_ve_el_mismo_plan(self):
        """El control que no depende de `normal`: si la forma normal perdiera algo que importa, el
        plan —parámetros resueltos, orden, assets— lo delataría."""
        for nombre, g in _grafos_reales():
            with self.subTest(nombre):
                self.assertEqual(_plan(texto.leer(texto.imprimir(g, VOCAB), VOCAB)), _plan(g))

    def test_cylinder_strip_se_escribe_como_lo_transcribio_el_diseno(self):
        """La transcripción a mano de la propuesta elegida (investigacion/claude.md), carácter por
        carácter: los params que quedan son exactamente los que difieren del default."""
        g = graph.JamGraph.from_json(
            (RAIZ / "Resources/Examples/Cylinder-Strip.jamgraph").read_text(encoding="utf-8"))
        self.assertEqual(texto.imprimir(g, VOCAB), CYLINDER)


class FormaCanonica(unittest.TestCase):
    def test_lo_no_canonico_se_lleva_a_la_forma_unica(self):
        suelto = ("x  =   series_range count=7 end=720.0 start=0\n"
                  "\n"
                  "s = curve_smooth   @x strength=0.450 iterations=3 preserve_ends=true\n")
        self.assertEqual(_ida_y_vuelta(suelto),
                         "x = series_range end=720 count=7\n"
                         "s = curve_smooth @x iterations=3 strength=0.45\n")

    def test_un_numero_largo_no_pierde_precision(self):
        """`repr` y no `.6g` (el de `texto_de_valor`): 123.456789 impreso con 6 cifras sería 123.457,
        y un grafo del canvas cambiaría al pasar por el texto."""
        g = graph.JamGraph()
        g.add("series_range", {"end": "123.456789", "start": "0.1"}, nid="x")
        t = texto.imprimir(g, VOCAB)
        self.assertEqual(t, "x = series_range start=0.1 end=123.456789\n")
        self.assertEqual(texto.normal(texto.leer(t, VOCAB), VOCAB), texto.normal(g, VOCAB))

    def test_una_expresion_implicita_se_escribe_con_igual(self):
        # En un pin numérico, texto no numérico YA es una expresión para el Compile.
        self.assertEqual(_ida_y_vuelta("a = series_range count=n*2\n"),
                         'a = series_range count="=n*2"\n')


class LaFormaNormalDiscrimina(unittest.TestCase):
    """Si `normal` fuera laxa, la ida y vuelta daría verde con cualquier cosa."""

    def _n(self, t):
        return texto.normal(texto.leer(t, VOCAB), VOCAB)

    def test_un_parametro_distinto(self):
        self.assertNotEqual(self._n("x = series_range count=7\n"), self._n("x = series_range count=8\n"))

    def test_el_orden_de_un_variadico_cuenta(self):
        base = "a = mesh_box\nb = mesh_sphere\n"
        self.assertNotEqual(self._n(base + "m = mesh_merge @a @b\n"),
                            self._n(base + "m = mesh_merge @b @a\n"))

    def test_el_orden_de_los_parametros_no_cuenta(self):
        self.assertEqual(self._n("x = series_range count=7 end=720\n"),
                         self._n("x = series_range end=720 count=7\n"))

    def test_bypass_y_debug_cuentan(self):
        base = "a = mesh_box\nn = mesh_normals @a"
        self.assertNotEqual(self._n(base + "\n"), self._n(base + " +bypass\n"))
        self.assertNotEqual(self._n(base + "\n"), self._n(base + " +debug\n"))

    def test_un_default_escrito_es_lo_mismo_que_omitido(self):
        self.assertEqual(self._n("x = series_range start=0\n"), self._n("x = series_range\n"))

    def test_el_pin_de_origen_cuenta(self):
        base = "m = matrix_identity\nd = matrix_decompose matriz=@m\n"
        self.assertNotEqual(self._n(base + "c = curve_line_sdl direccion=@d.eje_z\n"),
                            self._n(base + "c = curve_line_sdl direccion=@d.eje_x\n"))


class Rasgos(unittest.TestCase):
    PROPIO = """\
radio = number 40 max=200
alto = number 600 max=2000
mueve = matrix_translation traslación=(0, 0, 150)
deco = matrix_decompose matriz=@mueve
tallo = curve_line_sdl direccion=@deco.eje_z largo="=alto * 0.9"
movida = curve_move @tallo desplazamiento=@deco
suave = curve_smooth @movida iterations=3 +bypass
tubo = mesh_pipe @suave radius_start=@radio radius_end="=radio / 4"
hojas = fn:hojas_de_pino cantidad=24 curva=@suave
todo = mesh_merge @tubo @hojas.malla
horno = mesh_to_static @todo name=SM_Tallo +debug
"""

    def test_el_ejemplo_propio_del_diseno_es_canonico(self):
        """Salida extra, valor cableado a un parámetro, expresiones, función, bypass y variádico."""
        self.assertEqual(_ida_y_vuelta(self.PROPIO), self.PROPIO)

    def test_lo_que_arma_el_ejemplo_propio(self):
        g = texto.leer(self.PROPIO, VOCAB)
        self.assertIn(("deco", "eje_z", "tallo", "direccion"), g.edges)
        self.assertIn(("radio", "out", "tubo", "radius_start"), g.edges)
        self.assertEqual([e for e in g.edges if e[2] == "todo"],
                         [("tubo", "out", "todo", "in"), ("hojas", "malla", "todo", "in")])
        self.assertEqual(g.nodes["mueve"]["params"]["traslación"], "0,0,150")  # como el canvas
        self.assertEqual(g.nodes["tallo"]["params"]["largo"], "=alto * 0.9")
        self.assertEqual(g.nodes["radio"]["params"], {"value": "40", "max": "200", "name": "radio"})
        self.assertTrue(g.nodes["suave"]["bypass"])
        self.assertEqual(g.nodes["hojas"]["verb"], "fn:hojas_de_pino")

    def test_el_asset_es_posicional(self):
        g = texto.leer("p = place SM_Rock\n", VOCAB)
        self.assertEqual(g.nodes["p"]["params"]["asset"], "SM_Rock")
        self.assertEqual(_ida_y_vuelta("p = place /Game/Props/SM_Rock.SM_Rock\n"),
                         "p = place /Game/Props/SM_Rock.SM_Rock\n")

    def test_un_parametro_desconocido_no_se_pierde(self):
        """El texto no lo descarta en silencio: lo conserva y el Compile dice qué quiso decir."""
        t = "x = series_range cownt=7\n"
        self.assertEqual(_ida_y_vuelta(t), t)
        self.assertIn("¿quisiste decir «count»?", str(_plan(texto.leer(t, VOCAB))))

    def test_un_texto_que_parece_numero_sigue_siendo_texto(self):
        """El tipo lo decide el pin, no la forma: `name=123` y `name="123"` son el mismo texto."""
        g = texto.leer('a = mesh_box\nh = mesh_to_static @a name="123"\n', VOCAB)
        self.assertEqual(g.nodes["h"]["params"]["name"], "123")
        self.assertEqual(texto.imprimir(g, VOCAB), "a = mesh_box\nh = mesh_to_static @a name=123\n")

    def test_la_consola_de_una_linea_no_es_un_documento(self):
        with self.assertRaises(texto.ErrorTexto) as e:
            texto.leer("scatter SM_Rock count=20\n", VOCAB)
        self.assertIn("nombre = verbo", str(e.exception))


class Errores(unittest.TestCase):
    def _error(self, t):
        with self.assertRaises(texto.ErrorTexto) as e:
            texto.leer(t, VOCAB)
        return e.exception

    def test_una_referencia_mal_escrita_sugiere_y_dice_la_linea(self):
        e = self._error("suave = curve_bezier\ntubo = mesh_pipe @suve\n")
        self.assertEqual((e.linea, e.columna), (2, 18))
        self.assertIn("¿quisiste decir «suave»?", e.mensaje)

    def test_un_nombre_repetido(self):
        e = self._error("a = mesh_box\na = mesh_sphere\n")
        self.assertEqual(e.linea, 2)
        self.assertIn("línea 1", e.mensaje)

    def test_un_verbo_desconocido_sugiere(self):
        e = self._error("a = mesh_boxx\n")
        self.assertIn("¿quisiste decir «mesh_box»?", e.mensaje)

    def test_una_tupla_sin_cerrar(self):
        e = self._error("m = matrix_translation traslación=(0, 0, 150\n")
        self.assertEqual(e.linea, 1)
        self.assertIn("no cierra", e.mensaje)

    def test_un_valor_suelto_donde_no_hay_posicional(self):
        e = self._error("s = curve_smooth iterations\n")
        self.assertIn("¿quisiste escribir «clave=iterations»?", e.mensaje)

    def test_no_hay_comentarios(self):
        self.assertIn("comentarios", self._error("a = mesh_box # caja\n").mensaje)


class Diffs(unittest.TestCase):
    """Criterio 5: una edición en el canvas toca sólo las líneas del nodo que cambió."""

    def _lineas(self, g):
        return texto.imprimir(g, VOCAB).splitlines()

    def test_cambiar_un_parametro_cambia_una_linea(self):
        g = texto.leer(CYLINDER, VOCAB)
        antes = self._lineas(g)
        g.nodes["pipe"]["params"]["sides"] = "16"
        despues = self._lineas(g)
        self.assertEqual(sum(a != b for a, b in zip(antes, despues)), 1)

    def test_insertar_un_nodo_agrega_una_linea_y_recablea_otra(self):
        g = texto.leer(CYLINDER, VOCAB)
        antes = self._lineas(g)
        g.add("mesh_weld", {}, nid="mesh_weld")
        g.edges = [("mesh_weld", "out", "normals", "in") if e == ("pipe", "out", "normals", "in")
                   else e for e in g.edges] + [("pipe", "out", "mesh_weld", "in")]
        despues = self._lineas(g)
        self.assertEqual(despues[:len(antes)][:7], antes[:7])
        self.assertEqual(despues[-1], "mesh_weld = mesh_weld @pipe")
        self.assertEqual(sum(a != b for a, b in zip(antes, despues)), 1)   # la de `normals`


class Ayuda(unittest.TestCase):
    def test_la_firma_se_escribe_en_la_misma_sintaxis(self):
        linea = texto.ayuda("curve_smooth", VOCAB)
        self.assertTrue(linea.startswith("curve_smooth @S → S · iterations=2"), linea)


if __name__ == "__main__":
    unittest.main()
