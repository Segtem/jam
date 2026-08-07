"""El pincel como fuente de puntos: dónde nacen los centros y por qué arriba."""

from __future__ import annotations

import sys
import types
import unittest

_unreal_fake = sys.modules.setdefault("unreal", types.ModuleType("unreal"))
if not hasattr(_unreal_fake, "TopLevelAssetPath"):
    _unreal_fake.TopLevelAssetPath = lambda package, name: (package, name)

from jam import tools  # noqa: E402
from jam.brush_core import centros, semilla_por_centro  # noqa: E402


class CentrosTests(unittest.TestCase):
    def test_one_centre_per_selected_actor(self):
        self.assertEqual(len(centros([(0, 0, 0), (500, 100, 50)])), 2)

    def test_the_height_lifts_the_point_over_the_pivot(self):
        """No es un detalle: para pintar CON FÍSICA las cosas tienen que nacer arriba y caer. Con
        alto=0 nacen dentro del piso y la simulación las expulsa para cualquier lado."""
        self.assertEqual(centros([(0, 0, 0)], alto=200)[0], (0.0, 0.0, 200.0))

    def test_it_only_touches_z(self):
        """Levantar el punto no puede moverlo de lugar: el pincel marca DÓNDE, y eso es x/y."""
        x, y, _z = centros([(123.0, -45.0, 10.0)], alto=200)[0]
        self.assertEqual((x, y), (123.0, -45.0))

    def test_no_actors_no_centres(self):
        self.assertEqual(centros([]), [])

    def test_the_seed_is_stable_for_the_same_centre(self):
        """Dos corridas del mismo grafo tienen que dar lo mismo — es la regla del oráculo. Si la
        semilla cambiara, mover el pincel y volver atrás daría otro reparto."""
        self.assertEqual(semilla_por_centro(7, 100, 200), semilla_por_centro(7, 100, 200))

    def test_two_centres_get_different_seeds(self):
        """Si no, dos pinceles repartirían el MISMO patrón y se vería copiado."""
        self.assertNotEqual(semilla_por_centro(7, 0, 0), semilla_por_centro(7, 500, 100))


class ContratoDelVerboTests(unittest.TestCase):
    def test_it_is_a_source_that_produces_points(self):
        """Fuente porque los centros salen de la SELECCIÓN del nivel, no de un cable."""
        info = tools.REGISTRO["brush"]
        self.assertTrue(info["source"])
        self.assertEqual(info["out_name"], "P")
        self.assertEqual(info["aridad"], 0)

    def test_it_does_not_need_an_asset(self):
        self.assertFalse(tools.REGISTRO["brush"]["asset_required"])

    def test_it_can_feed_a_scatter(self):
        """La composición que justifica el diseño: el pincel marca los centros y `scatter` reparte
        alrededor. Si los tipos no coincidieran, habría que duplicar el repartidor adentro."""
        self.assertEqual(tools.REGISTRO["brush"]["out_name"],
                         tools.REGISTRO["scatter"]["in_name"])

    def test_it_can_be_pinned_to_a_named_actor(self):
        """Sin nombre, el pincel depende de qué haya quedado ELEGIDO en el nivel: el grafo no es
        autocontenido y una herramienta publicada no puede depender de eso. El nombre lo fija.

        Es además el único camino verificable sin GUI: comprobado que en commandlet
        `set_selected_level_actors` no vuelve por `get_selected_level_actors`.
        """
        self.assertIn("actor", tools.REGISTRO["brush"]["params"])
        self.assertEqual(tools.REGISTRO["brush"]["params"]["actor"], "",
                         "vacío tiene que significar «usá la selección»")

    def test_it_does_not_scatter_by_itself(self):
        """El pincel NO reparte: sus únicos params son de posición. Si tuviera «cantidad» o
        «patrón» sería un segundo repartidor que mantener en sincronía con `scatter`."""
        self.assertEqual(set(tools.REGISTRO["brush"]["params"]), {"actor", "alto"})


if __name__ == "__main__":
    unittest.main()
