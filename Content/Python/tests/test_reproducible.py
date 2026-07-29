"""Un grafo tiene que dar el MISMO resultado cada vez que corre.

EL BUG: dos Run seguidos no ponían el modelo en el mismo lugar. La causa no era aleatoriedad sino
que el nodo miraba la CÁMARA: `view=True` hace que la posición sea «donde estoy mirando ahora», así
que mover el viewport un pixel entre corridas movía el resultado.

Como comando eso es exactamente lo que se quiere —`place SM_Rock` pone la piedra donde mirás, y por
eso `view` existe—. Como nodo de un grafo es un error de categoría: un grafo es una DESCRIPCIÓN, y
una descripción que depende de dónde estaba la cámara no describe nada.

La regla que se fija acá: ningún parámetro de grafo puede tomar su valor del estado vivo del editor.
"""

from __future__ import annotations

import inspect
import sys
import types
import unittest

_unreal = sys.modules.setdefault("unreal", types.ModuleType("unreal"))
if not hasattr(_unreal, "TopLevelAssetPath"):
    _unreal.TopLevelAssetPath = lambda package, name: (package, name)

from jam import tools  # noqa: E402


# Params cuyo valor sale del editor en vivo (cámara, selección) y no del grafo.
DEPENDEN_DEL_EDITOR = ("view",)


class ReproducibleTests(unittest.TestCase):
    def test_no_graph_param_reads_the_live_editor_by_default(self):
        """Con cualquiera de éstos prendido, correr dos veces el mismo grafo da dos resultados."""
        culpables = sorted(
            f"{verbo}.{param}"
            for verbo, info in tools.REGISTRO.items()
            for param in DEPENDEN_DEL_EDITOR
            if info.get("params", {}).get(param) is True)
        self.assertEqual(culpables, [],
                         "estos nodos apuntan a la cámara viva: el grafo deja de ser reproducible")

    def test_the_command_still_places_where_you_are_looking(self):
        """Lo otro no se puede romper para arreglar esto: desde la Dash Bar, `place` sin argumentos
        tiene que seguir poniendo la pieza en el punto de mira. Si no, todo aterriza en el origen
        del mundo —a kilómetros de la cámara— y parece que la herramienta no hizo nada."""
        for verbo in ("place", "scatter", "fracture", "pcg"):
            with self.subTest(verbo=verbo):
                defecto = inspect.signature(tools.REGISTRO[verbo]["fn"]).parameters["view"].default
                self.assertIs(defecto, True,
                              "el default de la FUNCIÓN es el que usa el comando")

    def test_the_two_defaults_are_deliberately_different(self):
        """No es una inconsistencia: son dos contextos con reglas distintas. El grafo pasa TODOS
        los params —así que manda el del registro— y el comando sólo los tipeados —así que manda el
        de la función—. Que sea gratis no lo hace accidental."""
        for verbo in ("place", "scatter", "fracture", "pcg"):
            with self.subTest(verbo=verbo):
                self.assertIs(tools.REGISTRO[verbo]["params"]["view"], False)
                self.assertIs(
                    inspect.signature(tools.REGISTRO[verbo]["fn"]).parameters["view"].default, True)

    def test_the_graph_passes_every_param_and_the_command_only_what_was_typed(self):
        """La mecánica de la que depende todo lo anterior. Si el comando empezara a pasar los
        defaults del registro, `place` volvería a aterrizar en el origen del mundo."""
        from jam import graph, panel

        del_grafo = inspect.getsource(graph.ejecutar_detalle)
        self.assertIn("plan.params.get(nid", del_grafo)
        del_comando = inspect.getsource(panel.ejecutar_dsl)
        self.assertIn('coaccionar(verbo, r["params"])', del_comando)


if __name__ == "__main__":
    unittest.main()


class CapturaDeLaMiraTests(unittest.TestCase):
    """La salida de la tensión: capturar el punto de mira UNA vez, al crear el nodo.

    Leer la cámara en cada Run da «aparece donde miro» y rompe «dos Run, el mismo resultado».
    Capturarla al crear el nodo da las dos, y deja las coordenadas a la vista para editarlas — que
    es lo que hace Houdini cuando soltás un nodo.
    """

    def test_every_captured_field_exists_in_the_verb(self):
        """Una captura que escribe en un param inexistente no falla: no hace nada, y el nodo sigue
        naciendo en el origen del mundo sin que nadie se entere."""
        rotos = {verbo: [c for c in campos if c not in tools.REGISTRO[verbo]["params"]]
                 for verbo, campos in tools.CAPTURA_LA_MIRA.items()}
        self.assertEqual({v: c for v, c in rotos.items() if c}, {})

    def test_every_captured_verb_exists(self):
        faltan = [v for v in tools.CAPTURA_LA_MIRA if v not in tools.REGISTRO]
        self.assertEqual(faltan, [])

    def test_the_captured_verbs_are_the_ones_that_place_things(self):
        """Capturar la mira sólo tiene sentido donde la posición importa. En un nodo que no coloca,
        escribirle coordenadas sería ruido."""
        for verbo in tools.CAPTURA_LA_MIRA:
            with self.subTest(verbo=verbo):
                self.assertIn(tools.REGISTRO[verbo]["cat"], ("Place", "Scatter"))

    def test_a_verb_that_captures_does_not_also_read_the_camera_at_run_time(self):
        """Las dos cosas juntas serían lo peor de ambas: se captura al crear Y se pisa en cada Run,
        o sea que la captura no sirve para nada y el grafo sigue sin ser reproducible."""
        for verbo in tools.CAPTURA_LA_MIRA:
            with self.subTest(verbo=verbo):
                self.assertIs(tools.REGISTRO[verbo]["params"].get("view"), False)
