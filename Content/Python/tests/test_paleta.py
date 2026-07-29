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


DATA_COLOR = RAIZ / "Source" / "JamEditor" / "Private" / "SJamGraphEditor.cpp"
TINTA = "#2A2E33"   # el trazo neutro de lo estructural; no es un tipo, no sale de DataColor


def mapa() -> dict:
    return json.loads((ICONOS / "icon-map.json").read_text(encoding="utf-8"))


def colores_de_los_pines() -> set:
    """Los colores de tipo, leídos de `SJamGraphEditor::DataColor` y pasados a sRGB.

    El C++ los escribe en LINEAL (que es como Slate los quiere) y los SVG en sRGB (que es como los
    quiere un navegador). La conversión de acá reproduce exactamente los valores que estaban
    escritos a mano, así que la tabla del C++ puede ser la única definición.
    """
    import re

    texto = DATA_COLOR.read_text(encoding="utf-8")
    cuerpo = texto.split("FLinearColor SJamGraphEditor::DataColor")[1].split("\n}")[0]

    def a_srgb(c: float) -> int:
        v = c / 12.92 if c <= 0.0031308 else 1.055 * (c ** (1 / 2.4)) - 0.055
        return round(v * 255)

    encontrados = set()
    for m in re.finditer(r"FLinearColor\(([\d.]+)f, ([\d.]+)f, ([\d.]+)f", cuerpo):
        r, g, b = (float(x) for x in m.groups())
        encontrados.add(f"#{a_srgb(r):02X}{a_srgb(g):02X}{a_srgb(b):02X}")
    return encontrados


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
        de enseñar el sistema de tipos y vuelve a ser una metáfora suelta.

        La paleta se DERIVA de `SJamGraphEditor::DataColor`, que es donde se decide de qué color
        sale un cable. Copiada a mano se desincronizaba callada: un tipo nuevo entraba con un color
        que el icono usaba y el pin no, o al revés.
        """
        import re
        paleta = colores_de_los_pines() | {TINTA}
        self.assertGreaterEqual(len(paleta), 12, "no se pudo leer la tabla de colores del C++")
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


class NombresDePinTests(unittest.TestCase):
    """Un pin no puede identificarse sólo por su color.

    Un punto verde y uno celeste no son una etiqueta: hay que haber memorizado la paleta, y con
    daltonismo o un monitor malo directamente no se puede. El color acompaña —ayuda a seguir un
    cable de un vistazo— pero el que identifica es el NOMBRE.
    """

    def nombres_del_cpp(self) -> set:
        import re

        cpp = (RAIZ / "Source" / "JamEditor" / "Private" / "SJamGraphEditor.cpp").read_text(
            encoding="utf-8")
        cuerpo = cpp.split("FString SJamGraphEditor::DataName")[1].split("\n}")[0]
        return set(re.findall(r'Type == TEXT\("([^"]+)"\)', cuerpo))

    def test_every_type_in_use_has_a_readable_name(self):
        """Si un tipo no está en la tabla, su pin se dibuja con el código crudo («N[]») o vacío, y
        vuelve a hacer falta adivinar."""
        usados = {t for i in tools.REGISTRO.values()
                  for t in (i.get("in_name"), i.get("out_name")) if t}
        sin_nombre = sorted(usados - self.nombres_del_cpp())
        self.assertEqual(sin_nombre, [], "tipos sin nombre legible en DataName")

    def test_the_names_are_words_and_not_codes(self):
        """«A» no es un nombre: es el mismo código que ya estaba y no agrega nada."""
        import re

        cpp = (RAIZ / "Source" / "JamEditor" / "Private" / "SJamGraphEditor.cpp").read_text(
            encoding="utf-8")
        cuerpo = cpp.split("FString SJamGraphEditor::DataName")[1].split("\n}")[0]
        pares = re.findall(r'Type == TEXT\("([^"]+)"\)\s*\)?\s*\{ return TEXT\("([^"]+)"\)', cuerpo)
        self.assertTrue(pares, "no se pudo leer la tabla de nombres")
        iguales = [t for t, n in pares if t == n]
        self.assertEqual(iguales, [], "estos «nombres» son el código de tipo otra vez")
