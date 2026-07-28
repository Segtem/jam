"""Contratos de la paleta: cada verbo con su icono, y el ribbon sin texto.

El ribbon muestra SÓLO el icono y el nombre en el tooltip (el modelo de Grasshopper), así que un
verbo sin entrada en el mapa cae al código corto y uno con icono repetido se vuelve indistinguible
de otro. Las dos cosas degradan en silencio: sin un test, se descubren mirando.
"""

from __future__ import annotations

import collections
import json
import sys
import types
import unittest
from pathlib import Path

_unreal_fake = sys.modules.setdefault("unreal", types.ModuleType("unreal"))
if not hasattr(_unreal_fake, "TopLevelAssetPath"):
    _unreal_fake.TopLevelAssetPath = lambda package, name: (package, name)

from jam import api, tools  # noqa: E402


RAIZ = Path(__file__).resolve().parents[3]
ICONOS = RAIZ / "Resources" / "Icons" / "Lucide"


def mapa() -> dict:
    return json.loads((ICONOS / "icon-map.json").read_text(encoding="utf-8"))


class IconosTests(unittest.TestCase):
    def test_every_verb_has_an_icon(self):
        faltan = sorted(v for v in tools.REGISTRO if v not in mapa())
        self.assertEqual(faltan, [], f"sin icono caen al código corto: {faltan}")

    def test_every_mapping_points_at_a_file_that_exists(self):
        rotos = sorted(f"{v} → {i}.svg" for v, i in mapa().items()
                       if not (ICONOS / f"{i}.svg").exists())
        self.assertEqual(rotos, [])

    def test_every_svg_is_well_formed_and_slate_tintable(self):
        import xml.dom.minidom
        for svg in sorted(ICONOS.glob("*.svg")):
            with self.subTest(icono=svg.name):
                xml.dom.minidom.parse(str(svg))
                # Slate tiñe el brush entero: el trazo tiene que ser blanco, no `currentColor`.
                self.assertIn('stroke="#FFFFFF"', svg.read_text(encoding="utf-8"))

    def test_the_icon_collisions_do_not_grow(self):
        """Sin texto en la ficha, dos verbos con el mismo icono se ven idénticos.

        No se exige cero —hay una deuda declarada en el README— pero sí que no empeore.
        """
        spec = json.loads(api.spec_all())
        iconos = mapa()
        por_cat = collections.defaultdict(lambda: collections.defaultdict(list))
        for herramienta in spec["tools"]:
            por_cat[herramienta["cat"]][iconos.get(herramienta["verbo"], "?")].append(
                herramienta["verbo"])
        afectados = sum(len(vs) for cat in por_cat.values()
                        for vs in cat.values() if len(vs) > 1)
        self.assertLessEqual(afectados, 21,
                             "creciste las colisiones de icono; asigná uno propio o actualizá el README")


class RibbonTests(unittest.TestCase):
    def test_the_tooltip_has_everything_the_tile_no_longer_shows(self):
        """Sin nombre bajo el icono, el tooltip es la ÚNICA forma de saber qué es un verbo."""
        spec = json.loads(api.spec_all())
        for herramienta in spec["tools"]:
            with self.subTest(verbo=herramienta["verbo"]):
                # nombre, firma de tipos y descripción: los tres los arma Slate con estos campos.
                self.assertTrue(herramienta["verbo"])
                self.assertTrue(herramienta["doc"], "un verbo sin doc deja el tooltip a medias")
                self.assertIsNotNone(herramienta["out_name"])
                if not herramienta["source"]:
                    self.assertTrue(herramienta["in_name"],
                                    "un consumidor sin in_name no puede mostrar su firma")


if __name__ == "__main__":
    unittest.main()
