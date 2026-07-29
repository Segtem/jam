"""La regla del pipeline: la cadena describe DÓNDE, y UN SOLO nodo lo vuelve escena.

Mientras cada verbo colocaba por su cuenta, encadenar dos era encadenar dos EFECTOS y el resultado
dependía del orden en que corrieran — que es cómo un segundo scatter terminaba exactamente encima
del primero. Es el modelo de Houdini y de Grasshopper: nada toca el mundo hasta el nodo de salida.

Lo que se fija acá es esa regla, no la implementación: si mañana otro verbo empieza a colocar por su
cuenta, este archivo lo dice.
"""

from __future__ import annotations

import inspect
import pathlib
import sys
import types
import unittest

_unreal = sys.modules.setdefault("unreal", types.ModuleType("unreal"))
# `jam.library` construye una ruta de clase al importarse; sin este stub, importar el adaptador de
# scatter falla antes de llegar a lo que se quiere probar.
if not hasattr(_unreal, "TopLevelAssetPath"):
    _unreal.TopLevelAssetPath = lambda package, name: (package, name)

from jam import ribbon, scatter, tools  # noqa: E402

RAIZ_CPP = pathlib.Path(__file__).resolve().parents[3] / "Source" / "JamEditor" / "Private"


class UnSoloInstanciadorTests(unittest.TestCase):
    def test_only_one_function_puts_new_geometry_in_the_world(self):
        """`scatter.instanciar_puntos` es la única que spawnea a partir de puntos.

        Se comprueba sobre el MÓDULO y no sobre una lista escrita a mano: si alguien agrega otra
        función que llame a `place.colocar` en un bucle, aparece acá.
        """
        fuente = inspect.getsource(scatter)
        cuerpos = {
            nombre: inspect.getsource(fn)
            for nombre, fn in vars(scatter).items()
            if inspect.isfunction(fn) and fn.__module__ == scatter.__name__
        }
        colocan = sorted(n for n, c in cuerpos.items() if "place.colocar(" in c)
        self.assertEqual(colocan, ["esparcir", "instanciar_puntos"],
                         "hay funciones nuevas que colocan por su cuenta; "
                         "el único que debería es `instanciar_puntos`")
        self.assertIn("place.colocar(", fuente)

    def test_scatter_produces_points_and_not_actors(self):
        """El cambio de contrato: `scatter` describe dónde, no coloca."""
        self.assertEqual(tools.REGISTRO["scatter"]["out_name"], "P")

    def test_scatter_does_not_ask_for_an_asset_it_does_not_use(self):
        """Lo único que `scatter` hacía con el asset era medir su huella para separar. Eso ahora se
        hace al COLOCAR, que es donde el tamaño importa y donde el asset ya está.

        Pedirlo igual dejaba un diagrama absurdo: el asset entraba, salía convertido en punto, y
        había que volver a traerlo al nodo siguiente. Un nodo que pide algo que no necesita confunde
        sobre qué hace.
        """
        self.assertNotEqual(tools.REGISTRO["scatter"]["in_name"], "A",
                            "su entrada es de PUNTOS, no un asset")
        self.assertFalse(tools.REGISTRO["scatter"]["asset_required"],
                         "y tampoco puede EXIGIRLO por otro lado: sin esto el nodo no compila")

    def test_scatter_can_multiply_points_or_fill_an_area(self):
        """Las dos cosas con el mismo nodo: sin cable reparte en un área; con puntos, alrededor de
        cada uno. Por eso su entrada es OPCIONAL — exigirla obligaría a un nodo de relleno para el
        caso más común."""
        self.assertEqual(tools.REGISTRO["scatter"]["in_name"], "P")
        self.assertEqual(tools.REGISTRO["scatter"]["out_name"], "P")
        self.assertEqual(tools.REGISTRO["scatter"]["min_inputs"], 0)

    def test_place_is_the_one_that_puts_things_in_the_world(self):
        """No hace falta un verbo nuevo: `place` YA es «poné esto acá». Con puntos, los «acá» son
        muchos. Un `instance` aparte era el mismo verbo con otro nombre."""
        self.assertNotIn("instance", tools.REGISTRO,
                         "`instance` es `place` con varios puntos: no son dos verbos")
        self.assertEqual(tools.REGISTRO["place"]["data_params"], {"points": "P"})
        self.assertIn("points", tools.REGISTRO["place"]["optional_data_params"])

    def test_place_still_works_without_points(self):
        """Su contrato viejo no cambia: A → A. Los grafos que ya existían siguen andando."""
        self.assertEqual(tools.REGISTRO["place"]["in_name"], "A")
        self.assertEqual(tools.REGISTRO["place"]["out_name"], "A")

    def test_a_verb_that_only_computes_says_what_is_missing(self):
        """Un verbo que ya no coloca tiene que decir qué falta, o se siente como un botón roto —
        que es exactamente la queja que en su momento originó `place` centrado en el punto de mira."""
        self.assertIn("place", tools.PISTA_INSTANCE)
        self.assertTrue(tools.PISTA_INSTANCE.strip(), "la pista no puede quedar vacía")


class ComandoTests(unittest.TestCase):
    """Desde la Dash Bar, «scatter SM_Rock» tiene que seguir poniendo piedras."""

    def test_the_decision_to_compose_is_made_by_TYPE_and_not_by_name(self):
        """El día que otro verbo pase a producir puntos, la Dash Bar tiene que componerlo sola. Con
        una lista de nombres, ese verbo dejaría de colocar en silencio."""
        # Se exige sobre TODO el registro y no sobre unos pocos casos: mirando sólo `scatter`, un
        # predicado escrito como `verbo in ("scatter",)` da las mismas respuestas y pasa igual.
        for verbo, info in tools.REGISTRO.items():
            with self.subTest(verbo=verbo):
                self.assertEqual(tools.necesita_instanciar(verbo),
                                 info.get("out_name") == "P")
        self.assertTrue(tools.necesita_instanciar("scatter"))
        self.assertFalse(tools.necesita_instanciar("no_existe"))

    def test_the_command_path_uses_that_predicate(self):
        """La composición vive en UN solo lugar —el despacho del DSL— y no repartida por verbo."""
        from jam import panel

        fuente = inspect.getsource(panel.ejecutar_dsl)
        self.assertIn("necesita_instanciar", fuente)
        self.assertIn("t_place", fuente,
                      "el comando compone con `place`, que es el que coloca")


class ScatterMultiplicadorTests(unittest.TestCase):
    """El scatter que toma puntos y reparte alrededor de cada uno."""

    def setUp(self):
        tools.limpiar_asset_producido_runtime("scatter")

    def puntos(self, n, separacion=1000.0):
        from jam.geometry import Vec3
        from jam import scatter_core as sc
        return [sc.Sample(Vec3(i * separacion, 0.0, 0.0), Vec3(0.0, 0.0, 1.0), 0.0,
                          sc.semilla_de(0, i * separacion, 0.0), (0.5, 0.5))
                for i in range(n)]

    def test_each_incoming_point_becomes_its_own_cluster(self):
        """«Scatter de scatter» con un significado obvio: matas alrededor de cada árbol. Antes eran
        dos repartos superpuestos y el resultado dependía del orden."""
        params = dict(tools.REGISTRO["scatter"]["params"])
        params.update({"count": 5, "area": 200.0, "surface": False})
        tools.REGISTRO["scatter"]["fn"](self.puntos(3), **params)
        salida = tools.dato_producido_runtime("scatter")
        self.assertGreater(len(salida), 3, "cada punto tiene que multiplicarse")

    def test_the_clusters_are_centred_on_the_points_that_made_them(self):
        params = dict(tools.REGISTRO["scatter"]["params"])
        params.update({"count": 4, "area": 150.0, "surface": False})
        tools.REGISTRO["scatter"]["fn"](self.puntos(2, separacion=5000.0), **params)
        xs = [p.pos.x for p in tools.dato_producido_runtime("scatter")]
        cerca_del_primero = [x for x in xs if abs(x - 0.0) < 400.0]
        cerca_del_segundo = [x for x in xs if abs(x - 5000.0) < 400.0]
        self.assertTrue(cerca_del_primero and cerca_del_segundo,
                        f"los racimos no siguieron a sus puntos: {sorted(xs)[:6]}")

    def test_two_clusters_are_not_identical(self):
        """La semilla de cada racimo sale del punto que lo origina. Con una sola semilla, todos los
        racimos salían calcados y el reparto se veía artificial."""
        params = dict(tools.REGISTRO["scatter"]["params"])
        params.update({"count": 6, "area": 300.0, "surface": False})
        tools.REGISTRO["scatter"]["fn"](self.puntos(2, separacion=5000.0), **params)
        puntos = tools.dato_producido_runtime("scatter")
        a = sorted(round(p.pos.x, 2) for p in puntos if p.pos.x < 2500.0)
        b = sorted(round(p.pos.x - 5000.0, 2) for p in puntos if p.pos.x >= 2500.0)
        self.assertNotEqual(a, b, "los dos racimos son idénticos")

    def test_it_is_deterministic(self):
        """Dos corridas del mismo grafo, el mismo resultado — la regla que costó tres bugs."""
        params = dict(tools.REGISTRO["scatter"]["params"])
        params.update({"count": 5, "area": 200.0, "surface": False})
        entrada = self.puntos(3)
        tools.REGISTRO["scatter"]["fn"](entrada, **params)
        una = [(round(p.pos.x, 3), round(p.pos.y, 3)) for p in tools.dato_producido_runtime("scatter")]
        tools.limpiar_asset_producido_runtime("scatter")
        tools.REGISTRO["scatter"]["fn"](entrada, **params)
        otra = [(round(p.pos.x, 3), round(p.pos.y, 3)) for p in tools.dato_producido_runtime("scatter")]
        self.assertEqual(una, otra)

    def test_without_points_it_still_fills_an_area(self):
        """El caso común no se rompe: sin cable, reparte en su área."""
        params = dict(tools.REGISTRO["scatter"]["params"])
        params.update({"count": 6, "area": 400.0, "surface": False})
        tools.REGISTRO["scatter"]["fn"](None, **params)
        self.assertTrue(tools.dato_producido_runtime("scatter"))


class UnaEntradaPorCosaTests(unittest.TestCase):
    """Una entrada, un pin, y ese pin dice su nombre.

    El nodo `place` llegó a tener DOS entradas para el asset: un nub anónimo en el header y una
    fila `asset`. El duplicado no era la fila —que es la buena: tiene nombre, tiene campo para
    escribir, y se grisea sola cuando le entra un cable— sino tener las dos. Se queda la que dice
    qué es; el punto de color se oculta.
    """

    def test_everything_that_consumes_an_asset_shows_a_row_for_it(self):
        """La fila es la que se puede leer y la que se puede tipear. Sin ella, la entrada vuelve a
        ser un punto de color, que no se puede identificar sin memorizar la paleta."""
        sin_fila = sorted(v for v, i in tools.REGISTRO.items()
                          if i.get("asset_pin") and not i.get("asset_row"))
        self.assertEqual(sin_fila, [], "consumen un asset y no muestran dónde ponerlo")

    def test_the_header_nub_is_hidden_when_the_row_IS_the_main_input(self):
        """La regla vive en el C++ porque es de dibujo. Se comprueba leyéndola: sin esto vuelven los
        dos pines, que es exactamente el bug que se estuvo arreglando."""
        cpp = (RAIZ_CPP / "SJamGraphEditor.cpp").read_text(encoding="utf-8")
        self.assertIn('bFilaEsLaEntrada = (T->InName == TEXT("A") && T->bAssetRow)', cpp)
        self.assertIn("bHasInput = !T->bSource && !bFilaEsLaEntrada", cpp)

    def test_a_verb_that_takes_something_else_keeps_its_header_nub(self):
        """No es «sacar el nub»: `mesh_leaf` recibe una CURVA por el header y un asset en la fila.
        Ahí son dos entradas distintas de verdad y las dos tienen que estar."""
        self.assertEqual(tools.REGISTRO["mesh_leaf"]["in_name"], "S")
        self.assertTrue(tools.REGISTRO["mesh_leaf"]["asset_row"])

    def test_a_cabled_asset_row_greys_out_like_any_other_param(self):
        """Que el campo se deshabilite al cablearlo no es cosmética: es lo que dice de dónde está
        saliendo el valor. Ya existía para todo param cableado, y la fila `asset` es uno más."""
        cpp = (RAIZ_CPP / "SJamGraphNode.cpp").read_text(encoding="utf-8")
        self.assertIn("!CabledPins.Contains(Key)", cpp)


if __name__ == "__main__":
    unittest.main()
