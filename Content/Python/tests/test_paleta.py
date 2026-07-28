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

from jam import api, flow, tools  # noqa: E402


RAIZ = Path(__file__).resolve().parents[3]
ICONOS = RAIZ / "Resources" / "Icons" / "Lucide"


def mapa() -> dict:
    return json.loads((ICONOS / "icon-map.json").read_text(encoding="utf-8"))


class IconosTests(unittest.TestCase):
    def test_every_verb_has_an_icon(self):
        faltan = sorted(v for v in tools.REGISTRO if v not in mapa())
        self.assertEqual(faltan, [], f"sin icono caen al código corto: {faltan}")

    def test_every_flow_op_has_an_icon_too(self):
        """El canvas dibuja las ops de flow con el mismo ribbon que los verbos.

        Estaba cubierto sólo `tools.REGISTRO`, así que una op nueva del flow entraba sin icono y sin
        que nada se quejara — pasó con `weight_material`. Son dos registros distintos y hacen falta
        las dos comprobaciones.
        """
        faltan = sorted(k for k in flow.OPS_META if k not in mapa())
        self.assertEqual(faltan, [], f"ops de flow sin icono: {faltan}")

    def test_every_mapping_points_at_a_file_that_exists(self):
        rotos = sorted(f"{v} → {i}.svg" for v, i in mapa().items()
                       if not (ICONOS / f"{i}.svg").exists())
        self.assertEqual(rotos, [])

    def test_every_svg_is_well_formed(self):
        import xml.dom.minidom
        for svg in sorted(ICONOS.glob("*.svg")):
            with self.subTest(icono=svg.name):
                xml.dom.minidom.parse(str(svg))

    def test_lucide_icons_are_white_masks_and_jam_icons_are_not(self):
        """Las dos familias tienen contratos OPUESTOS, y `MakeBadge` las separa por el prefijo.

        Un icono de Lucide es una máscara que Slate tiñe de tinta, así que su trazo tiene que ser
        blanco. Uno propio de Jam trae los colores del sistema de tipos —el icono enseña la firma
        del verbo— así que teñirlo lo arruinaría.
        """
        for svg in sorted(ICONOS.glob("*.svg")):
            texto = svg.read_text(encoding="utf-8")
            with self.subTest(icono=svg.name):
                self.assertNotIn("currentColor", texto, "sin adaptar: Slate no lo tiñe bien")
                if svg.name.startswith("jam-"):
                    self.assertNotIn('stroke="#FFFFFF"', texto,
                                     "un icono propio no puede ser una máscara blanca")
                else:
                    self.assertIn('stroke="#FFFFFF"', texto)

    def test_jam_icons_use_the_type_palette(self):
        """El vocabulario visual son los colores de los pines: si un icono inventa colores, deja
        de enseñar el sistema de tipos y vuelve a ser una metáfora suelta."""
        import re
        paleta = {"#65B1D1", "#F6C86F", "#7CBF90", "#90CEA2", "#A6D490", "#6FBCB5",
                  "#CBAD69", "#DA90B8", "#50C8CE", "#EAB559", "#BF95D4", "#DD6F81",
                  "#DDDDE2", "#2A2E33"}
        for svg in sorted(ICONOS.glob("jam-*.svg")):
            with self.subTest(icono=svg.name):
                usados = set(re.findall(r"#[0-9A-Fa-f]{6}", svg.read_text(encoding="utf-8")))
                self.assertTrue(usados, "un icono propio sin color no se distingue de una máscara")
                self.assertEqual(usados - paleta, set(),
                                 "colores fuera de la paleta de tipos")

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
        self.assertLessEqual(afectados, 0,
                             "creciste las colisiones de icono; asigná uno propio")

    def test_every_verb_draws_its_own_data(self):
        """Todos los tabs pasaron al vocabulario de tipos; ninguno queda con una metáfora de Lucide.

        No es cosmética: el icono es lo ÚNICO que muestra la ficha del ribbon, así que es donde el
        usuario lee la firma del verbo antes de conectarlo.
        """
        ajenos = sorted(f"{v} → {i}" for v, i in mapa().items() if not i.startswith("jam-"))
        self.assertEqual(ajenos, [], f"vuelven a un pictograma que no diagrama el dato: {ajenos}")

    def test_no_icon_uses_an_element_unreal_cannot_rasterize(self):
        """Unreal rasteriza SVG con **nanosvg**, que ignora en silencio lo que no entiende.

        Un `<text>` se parsea sin error y el icono sale EN BLANCO: no hay forma de notarlo desde
        Python. La lista es la que enumera `nanosvg.h` al recorrer los elementos.
        """
        import xml.etree.ElementTree as ET
        soportados = {"svg", "g", "path", "rect", "circle", "ellipse", "line",
                      "polygon", "polyline", "defs", "stop", "style",
                      "linearGradient", "radialGradient", "title", "desc"}
        for svg in sorted(ICONOS.glob("*.svg")):
            with self.subTest(icono=svg.name):
                usados = {n.tag.rsplit("}", 1)[-1] for n in ET.parse(str(svg)).iter()}
                self.assertEqual(usados - soportados, set(),
                                 "nanosvg lo ignora y el icono sale en blanco")


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
