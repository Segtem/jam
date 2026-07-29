"""Contratos del tab «Aprender»: el catálogo de tutoriales tiene que apuntar a cosas que existen.

Los ejemplos son lo primero que abre alguien que llega a Jam, y son la única parte del plugin que
falla de la peor manera: en silencio y frente a un principiante. Un archivo renombrado deja una
ficha que no hace nada; un grafo que ya no compila —porque un verbo cambió de params— deja a alguien
mirando errores rojos en su primer minuto y creyendo que hizo algo mal.

Nada de esto lo ve el C++, que se limita a leer el JSON y cargar el archivo que diga.
"""

from __future__ import annotations

import json
import sys
import types
import unittest
from pathlib import Path

sys.modules.setdefault("unreal", types.ModuleType("unreal"))

from jam import graph  # noqa: E402


RAIZ = Path(__file__).resolve().parents[3]
EJEMPLOS = RAIZ / "Resources" / "Examples"
ICONOS = RAIZ / "Resources" / "Icons" / "Lucide"


def catalogo() -> list[dict]:
    return json.loads((EJEMPLOS / "examples.json").read_text(encoding="utf-8"))["ejemplos"]


class CatalogoTests(unittest.TestCase):
    def test_every_entry_points_at_a_file_that_exists(self):
        faltan = sorted(e["archivo"] for e in catalogo()
                        if not (EJEMPLOS / e["archivo"]).exists())
        self.assertEqual(faltan, [], "fichas que cargarían un archivo inexistente")

    def test_every_bundled_graph_is_in_the_catalogue(self):
        """Al revés también: un .jamgraph distribuido y no listado es un tutorial invisible."""
        listados = {e["archivo"] for e in catalogo()}
        sueltos = sorted(p.name for p in EJEMPLOS.glob("*.jamgraph") if p.name not in listados)
        self.assertEqual(sueltos, [], "ejemplos que nadie puede abrir desde la UI")

    def test_every_entry_has_an_icon_file(self):
        rotos = sorted(f"{e['archivo']} → {e['icono']}.svg" for e in catalogo()
                       if not (ICONOS / f"{e['icono']}.svg").exists())
        self.assertEqual(rotos, [])

    def test_every_entry_says_what_to_do_next(self):
        """Un grafo cargado que nadie corre parece que no hizo nada. El mensaje del Output es la
        única señal de que pasó algo, así que tiene que decir el paso siguiente."""
        for e in catalogo():
            with self.subTest(ejemplo=e["archivo"]):
                self.assertTrue(e.get("titulo"), "sin título la ficha no dice qué es")
                self.assertTrue(e.get("grupo"), "sin grupo no cae en ningún panel del ribbon")
                self.assertIn("Run", e.get("mensaje", ""),
                              "el mensaje tiene que decir que hay que correr el grafo")

    def test_the_first_group_is_the_starting_point(self):
        """El orden del JSON es el orden de los paneles: lo de empezar va primero."""
        self.assertEqual(catalogo()[0]["grupo"], "Empezar")


class GrafosTests(unittest.TestCase):
    def test_every_bundled_graph_compiles(self):
        """El Compile del canvas sobre cada tutorial, en lo que se puede comprobar sin editor.

        Cubre lo que rompe un cambio de código: verbos que ya no existen, params renombrados, tipos
        incompatibles, ciclos, aridades. NO cubre si los assets que referencia el grafo EXISTEN en
        el proyecto — eso necesita el registro de Unreal y lo verifica
        `tools/experiments/verifica_ejemplos.py`.

        Lo que se filtra es sólo eso, y por su texto exacto. El primer filtro descartaba cualquier
        mensaje con la palabra «asset», y así se comió un «requiere asset explícito» —que es
        estructural y este test SÍ puede juzgar— dejando pasar dos tutoriales que no corrían en el
        canvas. Un filtro ancho no es prudencia: es un test que se calla.
        """
        solo_del_editor = ("no pude resolver asset", "asset no encontrado")
        for archivo in sorted(EJEMPLOS.glob("*.jamgraph")):
            with self.subTest(ejemplo=archivo.name):
                g = graph.JamGraph.from_json(archivo.read_text(encoding="utf-8"))
                estructurales = {
                    nid: [m for m in mensajes
                          if not any(p in m.lower() for p in solo_del_editor)]
                    for nid, mensajes in graph.validar(g).items()
                }
                estructurales = {n: m for n, m in estructurales.items() if m}
                self.assertEqual(estructurales, {},
                                 f"{archivo.name} no compila: alguien lo va a abrir y ver rojo")

    def test_the_starting_example_is_short_enough_to_read(self):
        """El primer grafo que ve alguien tiene que caber en la cabeza de una sola mirada."""
        g = graph.JamGraph.from_json(
            (EJEMPLOS / "Primeros-pasos.jamgraph").read_text(encoding="utf-8"))
        self.assertLessEqual(len(g.nodes), 5, "«Primeros pasos» se está volviendo un ejemplo más")

    def test_the_starting_example_ends_in_something_visible(self):
        """Termina en `place`: si el ejemplo introductorio no pone nada en el nivel, quien lo corra
        no tiene forma de saber si funcionó."""
        g = graph.JamGraph.from_json(
            (EJEMPLOS / "Primeros-pasos.jamgraph").read_text(encoding="utf-8"))
        self.assertIn("place", [n.get("verb") for n in g.nodes.values()])


if __name__ == "__main__":
    unittest.main()
