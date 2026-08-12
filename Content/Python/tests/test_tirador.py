"""El tirador de números: el «Digit Scroller» del tab Params de Grasshopper.

Jam tiene **505 parámetros numéricos** y hasta hoy todos se tipeaban: el campo de un param es un
cuadro de texto pelado, sin arrastre. Eso NO fue un descuido —cualquier param numérico puede llevar
una expresión (`=radio * 2`, o el nombre pelado de una variable) y un spinbox no puede contenerla—
pero deja al usuario tecleando para probar un valor, que es lo contrario de tantear.

El tirador va AL LADO del campo, como la perilla y como el desplegable de `expr`: el texto sigue
aceptando expresiones y valores exactos, y el tirador agrega lo único que faltaba.
"""

from __future__ import annotations

import re
import sys
import types
import unittest
from pathlib import Path

sys.modules.setdefault("unreal", types.ModuleType("unreal"))

from jam import tools  # noqa: E402

RAIZ = Path(__file__).resolve().parents[3]
SCRUB = RAIZ / "Source" / "JamEditor" / "Private" / "SJamScrub.cpp"
NODO = RAIZ / "Source" / "JamEditor" / "Private" / "SJamGraphNode.cpp"


def codigo(ruta: Path) -> str:
    texto = re.sub(r"/\*.*?\*/", "", ruta.read_text(encoding="utf-8"), flags=re.S)
    return "\n".join(l for l in texto.splitlines() if not l.strip().startswith("//"))


class PorQueExisteTests(unittest.TestCase):
    def test_hay_cientos_de_params_numericos(self) -> None:
        """Si fueran veinte, el tirador sería un adorno. Son cientos: por eso va en la fila y no
        como un control que hay que pedir."""
        numericos = sum(1 for i in tools.REGISTRO.values() for d in i.get("params", {}).values()
                        if isinstance(d, (int, float)) and not isinstance(d, bool))
        self.assertGreater(numericos, 200, f"quedaron {numericos} params numéricos")

    def test_un_param_numerico_PUEDE_llevar_una_expresion(self) -> None:
        """La razón por la que el campo sigue siendo texto y el tirador va al lado. Si esto dejara
        de ser cierto, el diseño entero podría simplificarse a un spinbox."""
        from jam import graph
        tabla = {"radio": 12.0}
        valor, error = graph._resolver_parametro("=radio * 2", 0.0, tabla)
        self.assertIsNone(error)
        self.assertEqual(valor, 24.0)


class NoRompeExpresionesTests(unittest.TestCase):
    """La regla que más importa: arrastrar sobre `=radio * 2` lo reemplazaría por un número y
    rompería en silencio un vínculo que alguien armó a propósito — y el nodo seguiría dando un
    resultado plausible, que es lo que lo vuelve caro de encontrar."""

    def cuerpo(self, funcion: str) -> str:
        fuente = codigo(SCRUB)
        desde = fuente.index(f"FReply SJamScrub::{funcion}")
        resto = fuente[desde + 10:]
        fin = resto.index("\nFReply SJamScrub::") if "\nFReply SJamScrub::" in resto else len(resto)
        return fuente[desde:desde + 10 + fin]

    def test_no_agarra_si_el_campo_tiene_una_expresion(self) -> None:
        cuerpo = self.cuerpo("OnMouseButtonDown")
        self.assertIn("EsNumeroPelado", cuerpo)
        self.assertIn("return FReply::Unhandled();", cuerpo,
                      "sin devolver Unhandled, el arrastre empieza igual")

    def test_una_expresion_NO_es_un_numero_pelado(self) -> None:
        """El `=` al principio y el nombre suelto de una variable son las dos formas."""
        fuente = codigo(SCRUB)
        self.assertIn('StartsWith(TEXT("="))', fuente)
        self.assertIn("IsNumeric()", fuente)


class ArrastreTests(unittest.TestCase):
    def cuerpo(self, funcion: str) -> str:
        fuente = codigo(SCRUB)
        desde = fuente.index(f"FReply SJamScrub::{funcion}")
        resto = fuente[desde + 10:]
        fin = resto.index("\nFReply SJamScrub::") if "\nFReply SJamScrub::" in resto else len(resto)
        return fuente[desde:desde + 10 + fin]

    def test_arrastra_por_DELTA_desde_donde_se_agarro(self) -> None:
        """Igual que la perilla: el valor no salta al tocarlo."""
        self.assertIn("XAlAgarrar", self.cuerpo("OnMouseButtonDown"))
        self.assertIn("ValorAlAgarrar =", self.cuerpo("OnMouseButtonDown"))

    def test_captura_el_mouse(self) -> None:
        """El tirador mide 9 px: sin capturar, el arrastre se cortaría apenas se sale de él."""
        self.assertIn("CaptureMouse", self.cuerpo("OnMouseButtonDown"))
        self.assertIn("ReleaseMouseCapture", self.cuerpo("OnMouseButtonUp"))

    def test_un_param_int_NUNCA_produce_decimales(self) -> None:
        """Arrastrar `count` hasta 7,4 no significa nada, y el nodo lo truncaría después sin
        decirlo — el usuario vería 7,4 en la ficha y 7 en el resultado."""
        cuerpo = self.cuerpo("OnMouseMove")
        self.assertIn("bEntero || Event.IsShiftDown()", cuerpo)
        self.assertIn("FMath::RoundToFloat(Nuevo)", cuerpo)

    def test_Shift_acomoda_igual_que_en_la_perilla(self) -> None:
        """La misma tecla tiene que significar lo mismo en los dos controles: llevar a valores
        redondos. Si en uno afinara y en el otro acomodara, no habría regla que recordar."""
        self.assertIn("IsShiftDown()", self.cuerpo("OnMouseMove"))
        self.assertNotIn("IsShiftDown()", self.cuerpo("OnMouseButtonDown"))

    def test_avisa_por_frame_y_una_vez_al_soltar(self) -> None:
        self.assertIn("OnValueChanged.ExecuteIfBound", self.cuerpo("OnMouseMove"))
        self.assertIn("OnValueCommitted.ExecuteIfBound", self.cuerpo("OnMouseButtonUp"))


class EnLaFichaTests(unittest.TestCase):
    def bloque(self) -> str:
        fuente = codigo(NODO)
        desde = fuente.index("const bool bNumerico")
        return fuente[desde:fuente.index('if (P.Unidad == TEXT("grados"))', desde)]

    def test_el_campo_sigue_ocupando_su_ranura(self) -> None:
        """El tirador ACOMPAÑA al campo. Sin la ranura, lo reemplazaría y se perderían las
        expresiones y el valor exacto."""
        self.assertIn("[ Field ]", self.bloque())

    def test_solo_en_params_numericos(self) -> None:
        self.assertIn('P.Type == TEXT("float") || P.Type == TEXT("int")', self.bloque())

    def test_NO_aparece_donde_ya_hay_perilla(self) -> None:
        """Un ángulo no necesita dos controles."""
        self.assertIn('P.Unidad != TEXT("grados")', self.bloque())

    def test_el_tooltip_anuncia_las_dos_cosas(self) -> None:
        """Shift, y que el campo sigue aceptando expresiones: si no se dice, nadie va a probar
        escribir `=radio * 2` en un campo que ahora parece un control."""
        bloque = self.bloque()
        self.assertIn("Shift", bloque)
        self.assertIn("radio * 2", bloque)


class ContrasteTests(unittest.TestCase):
    """El mismo criterio que la perilla: 3:1 contra el cuerpo de la ficha (WCAG 1.4.11)."""

    FICHA = (0.76, 0.77, 0.78)

    def test_las_rayitas_se_ven(self) -> None:
        patron = (r"FLinearColor(?:\s+\w+)?\(([\d.]+)f,\s*([\d.]+)f,\s*"
                  r"([\d.]+)f(?:,\s*([\d.]+)f)?\)")
        colores = list(re.finditer(patron, codigo(SCRUB)))
        self.assertTrue(colores, "no se encontró ningún color: el patrón dejó de matchear")
        for m in colores:
            color = tuple(float(m.group(i)) for i in (1, 2, 3))
            alfa = float(m.group(4)) if m.group(4) else 1.0
            mezclado = tuple(color[i] * alfa + self.FICHA[i] * (1 - alfa) for i in range(3))
            lum = lambda c: 0.2126 * c[0] + 0.7152 * c[1] + 0.0722 * c[2]
            a, b = lum(mezclado), lum(self.FICHA)
            ratio = (max(a, b) + 0.05) / (min(a, b) + 0.05)
            with self.subTest(color=color, alfa=alfa):
                self.assertGreaterEqual(ratio, 3.0, f"{ratio:.2f}:1 contra la ficha")


if __name__ == "__main__":
    unittest.main()
