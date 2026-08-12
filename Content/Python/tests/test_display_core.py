"""El display flag: ver SÓLO el nodo marcado, como Houdini y Substance Designer.

Antes el flag SUMABA —dibujaba el nodo marcado además de todo lo que el grafo hiciera igual—. Estos
tests fijan lo que faltaba: que marcar un nodo RECORTE lo que corre.
"""

from __future__ import annotations

import sys
import types
import unittest

sys.modules.setdefault("unreal", types.ModuleType("unreal"))

from jam import display_core  # noqa: E402


def nodos(*ids, marcados=()):
    return {i: {"verb": "x", "debug": i in marcados} for i in ids}


def cable(a, b):
    return (a, "out", b, "in")


class RecorteTests(unittest.TestCase):
    def test_sin_ningun_marcado_corre_TODO(self):
        """La propiedad que permite agregar esto sin tocar lo que ya andaba: un grafo sin display
        flag se comporta exactamente como antes."""
        marcas, permitidos = display_core.recorte(nodos("a", "b", "c"), [cable("a", "b"), cable("b", "c")])
        self.assertEqual(marcas, [])
        self.assertEqual(permitidos, {"a", "b", "c"})

    def test_marcar_el_del_medio_deja_afuera_lo_de_aguas_abajo(self):
        """Es el pedido entero: ver el nodo del medio sin que corra el terminal que coloca cosas."""
        _marcas, permitidos = display_core.recorte(
            nodos("a", "b", "c", marcados=("b",)), [cable("a", "b"), cable("b", "c")])
        self.assertEqual(permitidos, {"a", "b"})

    def test_lo_que_alimenta_al_marcado_SI_corre_aunque_este_lejos(self):
        _marcas, permitidos = display_core.recorte(
            nodos("a", "b", "c", "d", marcados=("d",)),
            [cable("a", "b"), cable("b", "c"), cable("c", "d")])
        self.assertEqual(permitidos, {"a", "b", "c", "d"})

    def test_una_rama_paralela_que_no_lo_alimenta_no_corre(self):
        """El caso que más se nota: dos ramas, mirás una, la otra no debería tocar la escena."""
        _marcas, permitidos = display_core.recorte(
            nodos("raiz", "izq", "der", marcados=("izq",)),
            [cable("raiz", "izq"), cable("raiz", "der")])
        self.assertEqual(permitidos, {"raiz", "izq"})

    def test_las_dos_ramas_de_un_diamante_alimentan_al_marcado(self):
        _marcas, permitidos = display_core.recorte(
            nodos("raiz", "izq", "der", "junta", marcados=("junta",)),
            [cable("raiz", "izq"), cable("raiz", "der"),
             cable("izq", "junta"), cable("der", "junta")])
        self.assertEqual(permitidos, {"raiz", "izq", "der", "junta"})

    def test_un_marcado_sin_entradas_corre_solo_el(self):
        _marcas, permitidos = display_core.recorte(
            nodos("a", "b", marcados=("a",)), [cable("a", "b")])
        self.assertEqual(permitidos, {"a"})

    def test_con_varios_marcados_corre_la_UNION_de_sus_ancestros(self):
        """Sin desempate arbitrario, y sin romper los diagramas guardados con dos marcados."""
        _marcas, permitidos = display_core.recorte(
            nodos("raiz", "izq", "der", "final", marcados=("izq", "der")),
            [cable("raiz", "izq"), cable("raiz", "der"), cable("izq", "final")])
        self.assertEqual(permitidos, {"raiz", "izq", "der"})

    def test_un_ciclo_no_cuelga(self):
        """Compile rechaza los ciclos, pero esto corre sobre lo que haya: no puede confiar en que
        lo llamen bien. Sin el conjunto de vistos, esto se cuelga para siempre."""
        _marcas, permitidos = display_core.recorte(
            nodos("a", "b", marcados=("b",)), [cable("a", "b"), cable("b", "a")])
        self.assertEqual(permitidos, {"a", "b"})

    def test_una_arista_a_un_nodo_que_no_existe_no_rompe(self):
        _marcas, permitidos = display_core.recorte(
            nodos("a", marcados=("a",)), [cable("fantasma", "a")])
        self.assertEqual(permitidos, {"a"})

    def test_acepta_la_forma_suelta_de_arista(self):
        """El formato viejo `[origen, destino]` sigue vivo en diagramas guardados."""
        _marcas, permitidos = display_core.recorte(
            nodos("a", "b", "c", marcados=("b",)), [("a", "b"), ("b", "c")])
        self.assertEqual(permitidos, {"a", "b"})


class AvisoTests(unittest.TestCase):
    """Un nodo que dejó de correr sin aviso es indistinguible de un nodo roto."""

    def test_los_omitidos_se_pueden_nombrar(self):
        self.assertEqual(display_core.omitidos(nodos("a", "b", "c"), {"a", "b"}), ["c"])

    def test_el_reporte_dice_QUE_se_ve_y_CUANTO_no_corrio(self):
        texto = display_core.resumen(["cinta"], 2)
        self.assertIn("cinta", texto)
        self.assertIn("2", texto)

    def test_el_reporte_dice_como_volver_atras(self):
        """Sin esto, alguien que marcó sin querer no tiene forma de saber qué apagar."""
        self.assertIn("◉", display_core.resumen(["cinta"], 2))

    def test_sin_marcados_no_hay_linea_de_reporte(self):
        self.assertEqual(display_core.resumen([], 0), "")

    def test_si_no_se_omitio_nada_lo_dice_distinto(self):
        """Marcar el terminal no recorta nada, y decir «0 nodos no corrieron» sería ruido."""
        self.assertNotIn("0 nodo", display_core.resumen(["fin"], 0))


class ReglasDeSlateTests(unittest.TestCase):
    """Lo que el recorte necesita de la UI, leído del `.cpp`.

    Se filtran los comentarios antes de juzgar: un comentario que explica una regla nombra el patrón
    que la regla prohíbe, y sin filtrar el test se atrapa a sí mismo.
    """

    import re as _re
    from pathlib import Path as _Path

    RAIZ = _Path(__file__).resolve().parents[3]

    @classmethod
    def codigo(cls, relativa: str) -> str:
        texto = (cls.RAIZ / relativa).read_text(encoding="utf-8")
        texto = cls._re.sub(r"/\*.*?\*/", "", texto, flags=cls._re.S)
        return "\n".join(l for l in texto.splitlines() if not l.strip().startswith("//"))

    def test_el_flag_se_MUEVE_en_vez_de_acumularse(self):
        """La regla de Houdini. Sin ella «ver sólo esto» pasa a significar «ver esto y aquello»."""
        fuente = self.codigo("Source/JamEditor/Private/SJamGraphEditor.cpp")
        cuerpo = fuente.split("void SJamGraphEditor::SoloVerNodo")[1].split("\n}\n")[0]
        self.assertIn("SetDebugEnabled(false)", cuerpo)
        self.assertIn("N.Id != Id", cuerpo)

    def test_mover_el_flag_vuelve_a_cocinar(self):
        """Marcar cambia QUÉ nodos corren: es un cambio de resultado, no de vista."""
        fuente = self.codigo("Source/JamEditor/Private/SJamGraphEditor.cpp")
        cuerpo = fuente.split("void SJamGraphEditor::SoloVerNodo")[1].split("\n}\n")[0]
        self.assertIn("PedirRecoccion()", cuerpo)
        self.assertIn("Marcar()", cuerpo)

    def test_el_nodo_le_avisa_al_editor_al_tocar_el_flag(self):
        nodo = self.codigo("Source/JamEditor/Private/SJamGraphNode.cpp")
        self.assertIn("OnDebugChangedDelegate.ExecuteIfBound()", nodo)
        self.assertIn("SLATE_EVENT(FSimpleDelegate, OnDebugChanged)",
                      self.codigo("Source/JamEditor/Public/SJamGraphNode.h"))

    def test_omitido_tiene_glifo_PROPIO_y_no_queda_como_sin_veredicto(self):
        """«Nunca corrió» y «fue excluido a propósito» son dos cosas distintas. Con el mismo aspecto,
        nadie puede saber si su nodo está roto o simplemente apagado."""
        nodo = self.codigo("Source/JamEditor/Private/SJamGraphNode.cpp")
        glifos = nodo.split("FString SJamGraphNode::StateGlyph")[1].split("\n}")[0]
        self.assertIn('ResultState == TEXT("omitido")', glifos)
        colores = nodo.split("FLinearColor SJamGraphNode::StateColor")[1].split("\n}")[0]
        self.assertIn('ResultState == TEXT("omitido")', colores)

    def test_el_estado_que_emite_el_cerebro_es_el_que_pinta_slate(self):
        """El contrato entre los dos lados. Si uno lo renombra, el nodo se pinta como si nunca
        hubiera corrido y el defecto es mudo."""
        from jam import graph  # noqa: F401 — se usa abajo, importado acá para no cargarlo si no corre

        self.assertIn('"omitido"', (self.RAIZ / "Content/Python/jam/graph.py").read_text(
            encoding="utf-8"))
        self.assertIn('TEXT("omitido")', self.codigo(
            "Source/JamEditor/Private/SJamGraphNode.cpp"))


if __name__ == "__main__":
    unittest.main()
