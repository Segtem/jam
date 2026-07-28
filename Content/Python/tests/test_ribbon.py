"""Contratos del layout del ribbon: cada verbo en un subgrupo, y el orden que ve el usuario.

La tabla de `jam/ribbon.py` se escribe a mano, así que se desincroniza sola: alguien registra un
verbo nuevo y queda fuera de todos los grupos, o renombra uno y la tabla sigue nombrando al viejo.
Las dos cosas degradan en silencio — el verbo simplemente no aparece donde debería.
"""

from __future__ import annotations

import json
import sys
import types
import unittest

_unreal_fake = sys.modules.setdefault("unreal", types.ModuleType("unreal"))
if not hasattr(_unreal_fake, "TopLevelAssetPath"):
    _unreal_fake.TopLevelAssetPath = lambda package, name: (package, name)

from jam import api, ribbon  # noqa: E402


def spec() -> dict:
    return json.loads(api.spec_all())


class LayoutTests(unittest.TestCase):
    def test_every_verb_lands_in_a_subgroup(self):
        huerfanos = sorted(f"{t['cat']}.{t['verbo']}" for t in spec()["tools"] if not t["grupo"])
        self.assertEqual(huerfanos, [], "sin subgrupo van al final sin etiqueta")

    def test_the_table_does_not_name_verbs_that_no_longer_exist(self):
        existen = {t["verbo"] for t in spec()["tools"]}
        fantasmas = sorted(f"{cat}.{verbo}"
                           for cat, grupos in ribbon.GRUPOS.items()
                           for _, verbos in grupos
                           for verbo in verbos if verbo not in existen)
        self.assertEqual(fantasmas, [], "la tabla nombra verbos inexistentes")

    def test_no_verb_is_listed_twice(self):
        for cat, grupos in ribbon.GRUPOS.items():
            todos = [v for _, verbos in grupos for v in verbos]
            with self.subTest(tab=cat):
                self.assertEqual(len(todos), len(set(todos)), "verbo repetido en dos subgrupos")

    def test_the_table_places_each_verb_in_its_own_tab(self):
        """Un verbo listado bajo el tab equivocado desaparece: el ribbon filtra por `cat` primero."""
        real = {t["verbo"]: t["cat"] for t in spec()["tools"]}
        colados = sorted(f"{verbo}: la tabla lo pone en {cat}, el registro en {real[verbo]}"
                         for cat, grupos in ribbon.GRUPOS.items()
                         for _, verbos in grupos
                         for verbo in verbos if real.get(verbo, cat) != cat)
        self.assertEqual(colados, [])

    def test_the_spec_arrives_in_the_order_the_ribbon_draws(self):
        """El C++ agrupa por orden de aparición sin reordenar, así que el orden llega desde acá."""
        for cat, grupos in ribbon.GRUPOS.items():
            esperado = [v for _, verbos in grupos for v in verbos]
            recibido = [t["verbo"] for t in spec()["tools"] if t["cat"] == cat]
            with self.subTest(tab=cat):
                self.assertEqual(recibido, esperado)

    def test_a_group_is_never_so_big_that_it_defeats_the_grouping(self):
        """Con tres filas, un grupo de más de 18 verbos ya son seis columnas: deja de leerse como
        bloque y vuelve a ser la tira que los subgrupos vinieron a partir."""
        gordos = sorted(f"{cat}.{nombre} ({len(verbos)})"
                        for cat, grupos in ribbon.GRUPOS.items()
                        for nombre, verbos in grupos if len(verbos) > 18)
        self.assertEqual(gordos, [])


if __name__ == "__main__":
    unittest.main()
