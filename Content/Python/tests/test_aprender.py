"""El tab «Aprender» es un CAMINO, no una estantería.

Antes eran 19 tutoriales en una fila horizontal, con insignia de 42 px y título debajo: la tira se
iba de largo y había que recorrerla entera para ver qué había, con 19 puertas del mismo tamaño
diciendo que daba igual por cuál entrar. Y no daba igual.

Ahora seis forman un camino ordenado —cada paso estrena una idea y usa la del anterior— y los otros
trece quedan agrupados por tema para cuando alguien busca algo puntual.

Estos tests miran las dos mitades: el CATÁLOGO (dato, `examples.json`) con tests de verdad, y las
reglas que quedaron en Slate leyendo el `.cpp`, que es como se atan acá las reglas duplicadas en C++.
"""

from __future__ import annotations

import collections
import json
import re
import unittest
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[3]
CATALOGO = RAIZ / "Resources" / "Examples" / "examples.json"
SLATE = RAIZ / "Source" / "JamEditor" / "Private" / "SJamGraphEditor.cpp"


def catalogo() -> list[dict]:
    return json.loads(CATALOGO.read_text(encoding="utf-8"))["ejemplos"]


def codigo() -> str:
    """El `.cpp` sin comentarios.

    Un comentario que EXPLICA una regla suele nombrar el patrón que la regla prohíbe, y el test se
    atrapa a sí mismo. Ya pasó en esta base.
    """
    texto = SLATE.read_text(encoding="utf-8")
    texto = re.sub(r"/\*.*?\*/", "", texto, flags=re.S)
    return "\n".join(l for l in texto.splitlines() if not l.strip().startswith("//"))


class ElCaminoTests(unittest.TestCase):
    def camino(self):
        return sorted((e for e in catalogo() if e.get("paso")), key=lambda e: e["paso"])

    def test_los_pasos_son_1_a_N_sin_huecos_ni_repetidos(self) -> None:
        """Un hueco o un empate rompen el «paso 3 de 6» y el orden de las fichas, y son la clase de
        error que se cuela al agregar un tutorial al medio."""
        pasos = [e["paso"] for e in self.camino()]
        self.assertEqual(pasos, list(range(1, len(pasos) + 1)),
                         f"el camino no es 1..N: {pasos}")

    def test_el_camino_es_CORTO(self) -> None:
        """La razón de que exista: 19 puertas iguales no son un camino. Si alguien agrega el
        décimo paso, este test lo obliga a decidir qué es camino y qué es referencia."""
        self.assertLessEqual(len(self.camino()), 8,
                             "un camino de más de 8 pasos volvió a ser una lista")
        self.assertGreaterEqual(len(self.camino()), 3)

    def test_cada_paso_dice_POR_QUE_esta_ahi_en_una_linea(self) -> None:
        """`porque` es lo que se lee en la ficha; `doc` es el texto largo del tooltip. Sin el
        primero, la ficha vuelve a ser un nombre suelto y el orden parece arbitrario."""
        for e in self.camino():
            with self.subTest(paso=e["paso"]):
                porque = str(e.get("porque", "")).strip()
                self.assertTrue(porque, f"el paso {e['paso']} no dice por qué está en el camino")
                self.assertLessEqual(len(porque), 90,
                                     "el «porqué» es de UNA línea; lo largo va en `doc`")
                self.assertNotIn("\n", porque)

    def test_el_primer_paso_es_la_cadena_minima(self) -> None:
        self.assertEqual(self.camino()[0]["archivo"], "Primeros-pasos.jamgraph")

    def test_todos_los_archivos_del_camino_existen(self) -> None:
        """Un paso que apunta a un `.jamgraph` que no está deja el camino cortado en la mitad."""
        for e in self.camino():
            with self.subTest(archivo=e["archivo"]):
                self.assertTrue((CATALOGO.parent / e["archivo"]).exists())


class ElRestoTests(unittest.TestCase):
    def test_lo_que_no_es_camino_sigue_agrupado_por_tema(self) -> None:
        resto = [e for e in catalogo() if not e.get("paso")]
        self.assertGreater(len(resto), 0, "si todo es camino, no hay referencia")
        for e in resto:
            with self.subTest(archivo=e["archivo"]):
                self.assertTrue(str(e.get("grupo", "")).strip(),
                                "sin grupo, la ficha cae suelta y no se encuentra")

    def test_ningun_tutorial_se_perdio_al_partir_el_catalogo(self) -> None:
        """La regresión que más importa: partir en dos no es tirar la mitad."""
        total = len(catalogo())
        camino = sum(1 for e in catalogo() if e.get("paso"))
        resto = sum(1 for e in catalogo() if not e.get("paso"))
        self.assertEqual(camino + resto, total)
        self.assertEqual(total, 19, "cambió la cantidad de tutoriales; actualizá este número")


class ReglasDeSlateTests(unittest.TestCase):
    """Lo que quedó en C++ y no se puede probar de otra forma sin abrir el editor."""

    def test_el_proximo_paso_es_el_PRIMERO_sin_hacer(self) -> None:
        """Y no el siguiente al último marcado: quien saltea el 3 y hace el 4 tiene el 3 pendiente,
        y decirle que va por el 5 sería mentirle."""
        fuente = codigo()
        self.assertIn("Proximo == nullptr", fuente,
                      "el próximo dejó de calcularse como «el primero sin marcar»")

    def test_el_progreso_va_al_ini_del_EDITOR_y_no_al_del_proyecto(self) -> None:
        """Es de la persona, no del juego: dos personas en el mismo repo aprenden por su cuenta y
        el progreso de una no tiene por qué aparecerle a la otra en un diff."""
        fuente = codigo()
        self.assertIn("GEditorPerProjectIni", fuente)
        self.assertIn("JamAprender", fuente)

    def test_se_guardan_los_ARCHIVOS_vistos_y_no_un_contador(self) -> None:
        """Con un contador, reordenar el camino dejaría el progreso sin sentido: el paso 3 de hoy
        puede ser el 4 de mañana."""
        fuente = codigo()
        self.assertIn("TSet<FString>& JamVistos", fuente)

    def test_la_insignia_del_camino_es_CHICA(self) -> None:
        """El pedido concreto: los iconos de 42 px con título debajo son los que hacían la tira
        infinita. En el camino se lee el nombre, no el dibujo."""
        fuente = codigo()
        self.assertNotIn('TEXT("EJ"), 42.0f', fuente, "volvió la insignia grande del tab Aprender")
        self.assertIn('TEXT("EJ"), 20.0f', fuente)

    def test_el_tab_se_redibuja_al_abrir_un_tutorial(self) -> None:
        """Un progreso que aparece recién al reabrir el tab no se lee como progreso."""
        fuente = codigo()
        bloque = fuente[fuente.index("void SJamGraphEditor::RebuildLearnTab"):]
        bloque = bloque[:bloque.index("const FJamTool* SJamGraphEditor::FindTool")]
        self.assertIn("JamMarcarVisto", bloque)
        self.assertIn("RebuildTabContent", bloque)

    def test_el_orden_del_camino_NO_esta_en_el_cpp(self) -> None:
        """Vive en el manifiesto. Reordenar lo que alguien aprende primero no debería necesitar
        recompilar el plugin — es la misma razón por la que los tutoriales dejaron de ser cinco
        funciones C++ que sólo se diferenciaban en un nombre de archivo."""
        fuente = codigo()
        for archivo in (e["archivo"] for e in catalogo() if e.get("paso")):
            with self.subTest(archivo=archivo):
                self.assertNotIn(archivo, fuente,
                                 "el C++ nombra un tutorial del camino: el orden volvió al código")


if __name__ == "__main__":
    unittest.main()
