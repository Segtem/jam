"""Letras de pin del modo compacto: únicas, estables y legibles."""

from __future__ import annotations

import sys
import types
import unittest

_unreal_fake = sys.modules.setdefault("unreal", types.ModuleType("unreal"))
if not hasattr(_unreal_fake, "TopLevelAssetPath"):
    _unreal_fake.TopLevelAssetPath = lambda package, name: (package, name)

from jam import tools  # noqa: E402
from jam.letras import letras_de_pines  # noqa: E402


class LetrasTests(unittest.TestCase):
    def test_an_axis_suffix_wins_over_the_initial(self):
        """En `size_x` lo que distingue es el eje: la inicial choca con `size_y` y `size_z`."""
        self.assertEqual(letras_de_pines(["size_x", "size_y", "size_z"]),
                         {"size_x": "X", "size_y": "Y", "size_z": "Z"})

    def test_a_second_axis_group_gets_initial_plus_axis(self):
        """`mesh_box` tiene `size_*` y `steps_*`. Sin esto el segundo grupo caía en letras sueltas
        de «steps» (S, T, E) que no dicen cuál es cuál."""
        r = letras_de_pines(["size_x", "size_y", "size_z", "steps_x", "steps_y", "steps_z"])
        self.assertEqual(r["steps_x"], "SX")
        self.assertEqual(r["steps_z"], "SZ")

    def test_plain_names_use_the_initial(self):
        self.assertEqual(letras_de_pines(["malla", "asset"]), {"malla": "M", "asset": "A"})

    def test_a_collision_takes_the_next_candidate(self):
        """El de arriba se queda la letra, igual que en Grasshopper."""
        r = letras_de_pines(["surface", "sink"])
        self.assertEqual(r["surface"], "S")
        self.assertNotEqual(r["sink"], "S")

    def test_the_result_depends_only_on_the_order(self):
        """Estabilidad: la misma letra en cada apertura del grafo. Si dependiera de algo más, un pin
        cambiaría de letra entre sesiones y no se podría aprender."""
        pines = ["surface", "sink", "scale"]
        self.assertEqual(letras_de_pines(pines), letras_de_pines(list(pines)))

    def test_no_pin_is_left_without_a_letter(self):
        r = letras_de_pines(["", "  ", "x"])
        self.assertEqual(len(r), 3)
        self.assertTrue(all(v for v in r.values()))

    def test_no_verb_in_the_real_catalogue_has_two_pins_with_the_same_letter(self):
        """LA propiedad del feature: en modo compacto la letra es lo ÚNICO que se ve, así que dos
        pines con la misma letra serían dos pines indistinguibles.

        Se corre sobre los 140 verbos reales y no sobre ejemplos inventados, que es donde aparecen
        los nombres que nadie previó.
        """
        for verbo, info in tools.REGISTRO.items():
            pines = list(info.get("params", {}))
            pines += [p for p in info.get("data_params", {}) if p not in pines]
            if len(pines) < 2:
                continue
            letras = letras_de_pines(pines)
            with self.subTest(verbo=verbo):
                repetidas = sorted(
                    l for l in letras.values() if list(letras.values()).count(l) > 1)
                self.assertEqual(repetidas, [], f"pines indistinguibles en «{verbo}»: {letras}")


if __name__ == "__main__":
    unittest.main()
