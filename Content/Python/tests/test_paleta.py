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


NODO_CPP = RAIZ / "Source" / "JamEditor" / "Private" / "SJamGraphNode.cpp"


def _luminancia(c: tuple) -> float:
    """Luminancia relativa WCAG. Slate guarda los colores en LINEAL, que es exactamente el espacio
    en el que WCAG define la fórmula — no hace falta convertir nada."""
    return 0.2126 * c[0] + 0.7152 * c[1] + 0.0722 * c[2]


def contraste(a: tuple, b: tuple) -> float:
    la, lb = _luminancia(a), _luminancia(b)
    alto, bajo = max(la, lb), min(la, lb)
    return (alto + 0.05) / (bajo + 0.05)


def _relleno_del_estado(estado: str) -> tuple:
    """El color de relleno que `RebuildBodyBrush` le pone al cuerpo para ese veredicto."""
    import re

    cuerpo = NODO_CPP.read_text(encoding="utf-8").split(
        "void SJamGraphNode::RebuildBodyBrush")[1].split("\n}")[0]
    m = re.search(
        r'ResultState == TEXT\("' + estado + r'"\).{0,400}?Fill = FLinearColor\('
        r"([\d.]+)f, ([\d.]+)f, ([\d.]+)f", cuerpo, re.S)
    assert m, f"no encontré el relleno del estado «{estado}» en el C++"
    return tuple(float(x) for x in m.groups())


class GlifosQueLaFuenteTieneTests(unittest.TestCase):
    """Un glifo que ninguna fuente cubre se dibuja como un rombo con «?».

    Pasó de verdad: el botón de bypass usaba `⏻` (U+23FB) y **ninguna** fuente del motor lo tiene,
    ni siquiera las de respaldo. El botón funcionaba y no se entendía qué era.

    Roboto —la fuente base de Slate— no trae NINGUNO de estos símbolos; los que se ven salen de
    `DroidSansFallback`, que es la de respaldo que Slate tiene en la cadena. Por eso la lista de
    permitidos es «lo que cubre DroidSansFallback», verificado a mano contra el .ttf del motor.

    El test no lee el .ttf: la ruta del motor no existe en cualquier máquina y la suite tiene que
    correr headless en cualquier lado. Lo que hace es obligar a que agregar un glifo nuevo sea una
    decisión CONSCIENTE — si no está en la lista, hay que verificarlo y sumarlo acá.
    """

    #: Verificados contra `Engine/Content/Slate/Fonts/DroidSansFallback.ttf` (UE 5.8.1).
    PERMITIDOS = set("○◉■□▲△●◯⊗⊙✓✗✕‼◐↑")

    def glifos_del_nodo(self) -> set:
        import re

        texto = NODO_CPP.read_text(encoding="utf-8")
        usados = set()
        for literal in re.findall(r'TEXT\("([^"]*)"\)', texto):
            # Desde U+2190 (flechas) para arriba: los bloques de SÍMBOLOS. Debajo de ahí está la
            # puntuación general —la raya «—», las comillas angulares— que es tipografía de los
            # textos en castellano, está en Roboto y no es el problema.
            usados |= {c for c in literal if 0x2190 <= ord(c) <= 0x2BFF}
        return usados

    def test_every_symbol_the_node_draws_has_a_font(self):
        fuera = sorted(self.glifos_del_nodo() - self.PERMITIDOS)
        self.assertEqual(
            fuera, [],
            "estos símbolos no están verificados contra DroidSansFallback y pueden salir como «?»: "
            + " ".join(f"{c} (U+{ord(c):04X})" for c in fuera))

    def test_the_allowlist_is_not_empty(self):
        """Si el regex dejara de encontrar literales, el test anterior pasaría sin mirar nada."""
        self.assertGreater(len(self.glifos_del_nodo()), 3,
                           "no se encontraron los glifos del nodo: ¿cambió la forma de los literales?")


class EtiquetasQueEntranTests(unittest.TestCase):
    """Una etiqueta de parámetro demasiado larga deja el campo sin lugar, y el control desaparece.

    Pasó de verdad: «valor por defecto (vacío = pin)» mide ~124 px a fuente 7 y la columna entera
    son 104 px. El campo existía y se dibujaba con ancho cero — desde el editor era imposible
    escribir el valor, y no había ninguna señal de por qué.

    El ancho de columna se LEE del `.cpp`: si alguien la ensancha, este test se relaja solo.
    """

    #: ~4 px por carácter a la fuente 7 de las filas de parámetro. Aproximado a propósito: sirve
    #: para atajar una etiqueta desproporcionada, no para predecir el pixel exacto.
    PX_POR_CARACTER = 4
    #: Lo mínimo que hace usable un campo de texto o un spinner.
    CAMPO_MINIMO_PX = 24

    def ancho_de_columna(self) -> float:
        import re

        texto = (RAIZ / "Source" / "JamEditor" / "Public" / "SJamGraphNode.h").read_text(
            encoding="utf-8")
        m = re.search(r"ParamColW = ([\d.]+)f", texto)
        self.assertIsNotNone(m, "no encontré ParamColW en el .h")
        return float(m.group(1))

    def test_every_param_label_leaves_room_for_its_field(self):
        from jam import funcion

        ancho = self.ancho_de_columna()
        fichas = list(tools.REGISTRO.items())
        largas = []
        for verbo, info in fichas:
            etiquetas = info.get("etiquetas_params", {})
            for nombre in info.get("params", {}):
                etiqueta = etiquetas.get(nombre, nombre)
                libre = ancho - len(etiqueta) * self.PX_POR_CARACTER
                if libre < self.CAMPO_MINIMO_PX:
                    largas.append(f"{verbo}.{nombre}: «{etiqueta}» deja {libre:.0f} px")
        # Los bordes de función viajan por otro camino que `REGISTRO`, y son los que fallaron.
        for ficha in funcion.herramientas({}):
            for p in ficha.get("params", []):
                etiqueta = p.get("label", p["nombre"])
                libre = ancho - len(etiqueta) * self.PX_POR_CARACTER
                if libre < self.CAMPO_MINIMO_PX:
                    largas.append(f"{ficha['verbo']}.{p['nombre']}: «{etiqueta}» deja {libre:.0f} px")
        self.assertEqual(largas, [], "etiquetas que no dejan lugar al campo:\n  " + "\n  ".join(largas))


class ContrasteDelCableTests(unittest.TestCase):
    """Un cable tiene que verse contra el lienzo.

    Los 14 colores de tipo dan entre 1.14:1 y 2.64:1 contra el fondo del canvas — ninguno llega al
    3:1 que pide un elemento gráfico. Y NO se pueden oscurecer: están atados a los iconos por
    `IconosTests.test_jam_icons_use_the_type_palette`, así que tocarlos obligaría a rehacer la
    paleta entera.

    Lo que sí resuelve es el HALO que va debajo. Era blanco al 55% «para levantar el contraste sobre
    el lienzo gris», pero el lienzo es CLARO: lo aclaraba más. Oscuro, le da a cualquier cable un
    contorno legible sin tocar un solo color de tipo.
    """

    MINIMO_GRAFICO = 3.0

    def _del_cpp(self, patron: str) -> tuple:
        import re

        cpp = DATA_COLOR.read_text(encoding="utf-8")
        m = re.search(patron, cpp, re.S)
        self.assertIsNotNone(m, f"no encontré en el .cpp: {patron}")
        return tuple(float(x) for x in m.groups())

    def fondo(self) -> tuple:
        """El gris del lienzo, leído de `SJamGridLayer`."""
        return self._del_cpp(
            r"Fondo del canvas.{0,400}?FLinearColor\(([\d.]+)f, ([\d.]+)f, ([\d.]+)f")

    def halo(self) -> tuple:
        """Color y alfa del halo que va debajo del cable."""
        return self._del_cpp(
            r"Halo OSCURO.{0,900}?FLinearColor\(([\d.]+)f, ([\d.]+)f, ([\d.]+)f, ([\d.]+)f")

    def test_the_halo_is_dark_enough_to_outline_any_wire(self):
        r, g, b, a = self.halo()
        fondo = self.fondo()
        # El halo es translúcido: lo que se ve es su mezcla con el lienzo.
        mezcla = tuple(a * c + (1 - a) * f for c, f in zip((r, g, b), fondo))
        self.assertGreaterEqual(contraste(mezcla, fondo), self.MINIMO_GRAFICO,
                                "el halo no le da contorno legible a un cable")

    def test_the_halo_is_darker_than_the_canvas(self):
        """La regla en una línea: sobre un lienzo CLARO el contorno va oscuro. Un halo más claro que
        el fondo —como el blanco original— no puede separar nada de él."""
        r, g, b, _a = self.halo()
        self.assertLess(_luminancia((r, g, b)), _luminancia(self.fondo()))


class ContrasteDelNodoTests(unittest.TestCase):
    """El texto del nodo tiene que LEERSE, no sólo estar.

    Es la otra mitad de la regla de accesibilidad: los pines dicen su nombre y los estados traen su
    símbolo, pero si el texto no contrasta con el fondo nada de eso sirve. WCAG AA pide 4.5:1 para
    texto normal.

    Los colores se LEEN del `.cpp` en vez de copiarse: una paleta duplicada se desincroniza callada,
    y este test existe justamente para atajar un cambio de color que rompa la legibilidad.

    El hallazgo que lo motivó: los dos estados que avisan de un problema —REVISAR y ERROR— eran los
    MENOS legibles del nodo (4.44 y 2.62). Un rojo saturado no llega a AA con ninguna tinta: da 2.62
    con la tinta oscura y 2.66 con blanca, así que había que aclararlo.
    """

    #: La tinta oscura con la que el nodo escribe todo (`JamInk` en el .cpp).
    TINTA = (0.10, 0.10, 0.11)
    MINIMO_AA = 4.5

    def test_every_verdict_body_can_be_read(self):
        for estado in ("aviso", "warn", "error"):
            with self.subTest(estado=estado):
                relleno = _relleno_del_estado(estado)
                self.assertGreaterEqual(
                    contraste(self.TINTA, relleno), self.MINIMO_AA,
                    f"el cuerpo «{estado}» no llega a WCAG AA con la tinta del nodo")

    def test_the_ink_matches_the_cpp(self):
        """Si `JamInk` cambia, el resto de este test estaría midiendo contra un color que ya no se
        usa — y pasaría en verde mientras el nodo se vuelve ilegible."""
        import re

        texto = NODO_CPP.read_text(encoding="utf-8")
        m = re.search(r"const FLinearColor JamInk\(([\d.]+)f, ([\d.]+)f, ([\d.]+)f", texto)
        self.assertIsNotNone(m, "no encontré JamInk en el C++")
        self.assertEqual(tuple(float(x) for x in m.groups()), self.TINTA)

    def colores_de_los_botones(self) -> dict:
        """Los colores «prendido» de los tres botones de vista, leídos del `.cpp`."""
        import re

        texto = NODO_CPP.read_text(encoding="utf-8")
        salida = {}
        for bandera, nombre in (("bCompacto", "comprimir"), ("bBypassed", "bypass"),
                                ("bDebugEnabled", "debug")):
            m = re.search(
                r"return " + bandera + r" \? FSlateColor\(FLinearColor\("
                r"([\d.]+)f, ([\d.]+)f, ([\d.]+)f", texto)
            if m:
                salida[nombre] = tuple(float(x) for x in m.groups())
        return salida

    def test_the_view_buttons_can_be_read_on_the_node(self):
        """Los tres botones de arriba a la derecha se dibujan sobre el cuerpo del nodo.

        Fallaron en producción: verde 1.39:1, azul 1.40:1, naranja 1.15:1 — o sea invisibles, que
        fue exactamente el reporte. Eran tonos CLAROS sobre un cuerpo claro.
        """
        colores = self.colores_de_los_botones()
        self.assertEqual(len(colores), 3, "no pude leer los tres botones del .cpp")
        for nombre, color in colores.items():
            with self.subTest(boton=nombre):
                self.assertGreaterEqual(
                    contraste(color, (0.76, 0.77, 0.78)), self.MINIMO_AA,
                    f"el botón «{nombre}» prendido no se lee sobre el cuerpo del nodo")

    def test_the_pin_type_labels_can_be_read(self):
        """El nombre del tipo es LO QUE reemplaza al color como identificador de un pin.

        Estaba en 2.28:1 — o sea que el texto puesto ahí para no depender del color era, él mismo,
        el menos legible del nodo. Es el mismo error que los botones, en el peor lugar posible.
        """
        import re

        texto = NODO_CPP.read_text(encoding="utf-8")
        m = re.search(
            r"InArgs\._InputLabel.{0,400}?ColorAndOpacity\(FSlateColor\(FLinearColor\("
            r"([\d.]+)f, ([\d.]+)f, ([\d.]+)f", texto, re.S)
        self.assertIsNotNone(m, "no encontré el color de la etiqueta de tipo en el .cpp")
        color = tuple(float(x) for x in m.groups())
        self.assertGreaterEqual(contraste(color, (0.76, 0.77, 0.78)), self.MINIMO_AA,
                                "la etiqueta de tipo del pin no se lee sobre el cuerpo del nodo")

    def test_the_neutral_body_can_be_read_too(self):
        """El caso normal, que es el que más se mira."""
        self.assertGreaterEqual(contraste(self.TINTA, (0.76, 0.77, 0.78)), self.MINIMO_AA)


class VeredictoDelOraculoTests(unittest.TestCase):
    """El estado de un nodo tampoco puede identificarse sólo por su color.

    Es la misma regla que `NombresDePinTests`, aplicada al otro lugar donde el color decía algo
    solo: hasta el 2026-08-05 el veredicto vivía ÚNICAMENTE en el color del cuerpo del nodo —y en
    un tooltip que había que hoverear para leer—. Ahora cada estado trae su símbolo, los mismos
    que `jam.graph` ya emite en el texto del reporte.
    """

    def glifos_del_cpp(self) -> dict:
        import re

        cpp = (RAIZ / "Source" / "JamEditor" / "Private" / "SJamGraphNode.cpp").read_text(
            encoding="utf-8")
        cuerpo = cpp.split("FString SJamGraphNode::StateGlyph")[1].split("\n}")[0]
        return dict(re.findall(
            r'ResultState == TEXT\("([^"]+)"\)\s*\)?\s*\{ return TEXT\("([^"]+)"\)', cuerpo))

    def test_every_verdict_has_a_symbol(self):
        """Los cuatro escalones que distingue `jam.graph._estado`. Si uno se queda sin símbolo,
        vuelve a distinguirse sólo por color."""
        glifos = self.glifos_del_cpp()
        faltan = sorted({"ok", "aviso", "warn", "error"} - set(glifos))
        self.assertEqual(faltan, [], "estados sin símbolo en StateGlyph")

    def test_no_two_verdicts_share_a_symbol(self):
        """Si dos compartieran glifo, el color volvería a ser el único canal para separarlos y no
        habríamos ganado nada."""
        glifos = self.glifos_del_cpp()
        repetidos = sorted({g for g in glifos.values() if list(glifos.values()).count(g) > 1})
        self.assertEqual(repetidos, [], "dos estados usan el mismo símbolo")

    def test_the_symbols_are_not_empty(self):
        glifos = self.glifos_del_cpp()
        vacios = sorted(k for k, v in glifos.items() if not v.strip())
        self.assertEqual(vacios, [], "estos estados tienen un símbolo vacío")
