"""La regla del pipeline: la cadena describe DÓNDE, y UN SOLO nodo lo vuelve escena.

Mientras cada verbo colocaba por su cuenta, encadenar dos era encadenar dos EFECTOS y el resultado
dependía del orden en que corrieran — que es cómo un segundo scatter terminaba exactamente encima
del primero. Es el modelo de Houdini y de Grasshopper: nada toca el mundo hasta el nodo de salida.

Lo que se fija acá es esa regla, no la implementación: si mañana otro verbo empieza a colocar por su
cuenta, este archivo lo dice.
"""

from __future__ import annotations

import inspect
import sys
import types
import unittest

_unreal = sys.modules.setdefault("unreal", types.ModuleType("unreal"))
# `jam.library` construye una ruta de clase al importarse; sin este stub, importar el adaptador de
# scatter falla antes de llegar a lo que se quiere probar.
if not hasattr(_unreal, "TopLevelAssetPath"):
    _unreal.TopLevelAssetPath = lambda package, name: (package, name)

from jam import ribbon, scatter, tools  # noqa: E402


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

    def test_instance_takes_points_and_produces_an_asset(self):
        self.assertEqual(tools.REGISTRO["instance"]["in_name"], "P")
        self.assertEqual(tools.REGISTRO["instance"]["out_name"], "A")

    def test_instance_needs_no_asset_input_of_its_own(self):
        """Su asset va por parámetro o sale del activo de la sesión: pedirlo por cable además
        obligaría a un nodo `asset` colgando de cada `instance`."""
        self.assertFalse(tools.REGISTRO["instance"]["asset_required"])

    def test_the_two_live_next_to_each_other_in_the_ribbon(self):
        """Se usan siempre juntos: separarlos en dos tabs obliga a saber de antemano que hacen falta
        los dos, que es justo lo que alguien nuevo no sabe."""
        grupo_scatter = ribbon.grupo_de("Scatter", "scatter")
        grupo_instance = ribbon.grupo_de("Scatter", "instance")
        self.assertEqual(grupo_scatter, grupo_instance)
        self.assertTrue(grupo_instance, "instance quedó sin subgrupo en el tab Scatter")

    def test_instance_comes_right_after_scatter(self):
        self.assertLess(ribbon.orden_de("Scatter", "scatter"),
                        ribbon.orden_de("Scatter", "instance"))

    def test_a_verb_that_only_computes_says_what_is_missing(self):
        """Un verbo que ya no coloca tiene que decir qué falta, o se siente como un botón roto —
        que es exactamente la queja que en su momento originó `place` centrado en el punto de mira."""
        self.assertIn("instance", tools.PISTA_INSTANCE)
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
        self.assertIn("t_instance", fuente)


if __name__ == "__main__":
    unittest.main()
