"""El live view: recocinar mientras se arrastra, como Houdini.

La lógica vive en Slate C++ porque el gesto es de la UI —quién avisa, cada cuánto, y qué NO entra en
el historial—. Estos tests LEEN el `.cpp` y el `.h` para que esas decisiones no se pierdan en
silencio en un refactor: son reglas que costaron mediciones, no detalles de implementación.

Se filtran las líneas de comentario antes de juzgar. Un comentario que EXPLICA una regla suele
nombrar el patrón que la regla prohíbe, y sin filtrar el test se atrapa a sí mismo.
"""

from __future__ import annotations

import re
import sys
import types
import unittest
from pathlib import Path

sys.modules.setdefault("unreal", types.ModuleType("unreal"))

ROOT = Path(__file__).resolve().parents[3]
EDITOR_CPP = ROOT / "Source/JamEditor/Private/SJamGraphEditor.cpp"
EDITOR_H = ROOT / "Source/JamEditor/Public/SJamGraphEditor.h"
NODO_CPP = ROOT / "Source/JamEditor/Private/SJamGraphNode.cpp"
NODO_H = ROOT / "Source/JamEditor/Public/SJamGraphNode.h"


def codigo(ruta: Path) -> str:
    """El fuente SIN comentarios: lo que el compilador ve, no lo que explica el autor."""
    texto = ruta.read_text(encoding="utf-8")
    texto = re.sub(r"/\*.*?\*/", "", texto, flags=re.S)
    return "\n".join(l for l in texto.splitlines() if not l.strip().startswith("//"))


class DosAvisosDistintosTests(unittest.TestCase):
    """Confirmar un parámetro y estar arrastrándolo son dos cosas y necesitan dos avisos.

    Con uno solo hay que elegir: o el aviso llega al soltar —y el live view deja de ser live— o
    llega por frame —y el historial se llena de un paso por cada frame del arrastre—.
    """

    def test_el_nodo_declara_el_aviso_de_arrastre_aparte_del_de_confirmacion(self):
        header = codigo(NODO_H)
        self.assertIn("SLATE_EVENT(FSimpleDelegate, OnParamLive)", header)
        self.assertIn("SLATE_EVENT(FSimpleDelegate, OnParamChanged)", header)

    def test_el_slider_avisa_por_frame_al_live_y_al_soltar_al_historial(self):
        fuente = codigo(NODO_CPP)
        self.assertIn("OnValueChanged_Lambda", fuente)
        self.assertIn("OnParamLiveDelegate.ExecuteIfBound()", fuente)
        self.assertIn("OnValueCommitted_Lambda", fuente)

    def test_el_aviso_de_arrastre_NO_toca_el_historial(self):
        """Es la razón de que existan dos avisos. Si `OnParamLive` marcase historial, arrastrar un
        slider dejaría decenas de pasos de Undo y habría que apretar Ctrl+Z cien veces."""
        fuente = codigo(EDITOR_CPP)
        vivo = re.search(r"\.OnParamLive_Lambda\(\[this\]\(\)\s*\{([^}]*)\}", fuente)
        self.assertIsNotNone(vivo, "el editor tiene que escuchar OnParamLive")
        self.assertNotIn("Marcar()", vivo.group(1))
        # `false` = el gesto SIGUE en curso. Es lo que le permite a `PedirRecoccion` no cocinar
        # mientras alguien arrastra un grafo caro; sin el argumento volvería el bug de la perilla.
        self.assertIn("PedirRecoccion(false)", vivo.group(1))

    def test_confirmar_un_parametro_SI_marca_historial_y_ademas_recocina(self):
        fuente = codigo(EDITOR_CPP)
        confirmado = re.search(r"\.OnParamChanged_Lambda\(\[this\]\(\)\s*\{([^}]*)\}", fuente)
        self.assertIsNotNone(confirmado)
        self.assertIn("Marcar()", confirmado.group(1))
        self.assertIn("PedirRecoccion()", confirmado.group(1))


class AmortiguadorTests(unittest.TestCase):
    """Un arrastre avisa decenas de veces por segundo; el grafo se corre ocho."""

    def test_pedir_recoccion_no_cocina_sino_que_levanta_una_bandera(self):
        """Cocinar en el aviso sería cocinar una vez POR FRAME, que es justo lo que se evita."""
        fuente = codigo(EDITOR_CPP)
        cuerpo = fuente.split("void SJamGraphEditor::PedirRecoccion(")[1].split("\n}")[0]
        self.assertIn("bRecoccionPendiente = true", cuerpo)
        self.assertNotIn("RunGraph()", cuerpo)

    def test_no_se_registra_un_temporizador_por_cada_aviso(self):
        """Sin esta guarda, un arrastre deja decenas de temporizadores latiendo sobre el mismo
        grafo, y cada uno lo corre entero."""
        fuente = codigo(EDITOR_CPP)
        cuerpo = fuente.split("void SJamGraphEditor::PedirRecoccion(")[1].split("\n}")[0]
        self.assertIn("if (!TemporizadorLive.IsValid())", cuerpo)

    def test_el_temporizador_es_de_UN_SOLO_TIRO(self):
        """Cocina una vez y se suelta; lo vuelve a armar el pedido siguiente.

        ⚠️ Antes devolvía `Continue` y ésa era la mitad del bug que Brian reportó: el temporizador
        seguía disparando cada 125 ms MIENTRAS el arrastre estaba en curso, y como cada vuelta de
        `RunGraph` cuesta 258–539 ms, el game thread no paraba nunca de cocinar y la perilla no se
        podía mover. Un temporizador que se apaga y se re-arma sólo corre cuando alguien pidió algo.
        """
        fuente = codigo(EDITOR_CPP)
        cuerpo = fuente.split("EActiveTimerReturnType SJamGraphEditor::CocinarSiHayPendiente")[1]
        cuerpo = cuerpo.split("\n}")[0]
        self.assertIn("EActiveTimerReturnType::Stop", cuerpo)
        self.assertNotIn("EActiveTimerReturnType::Continue", cuerpo)
        self.assertIn("TemporizadorLive.Reset()", cuerpo)

    def test_la_bandera_se_baja_ANTES_de_cocinar(self):
        """Bajarla después se come el aviso que llegue mientras corre el grafo, y el live view se
        queda mostrando el penúltimo valor del arrastre — un error que sólo se ve al soltar."""
        fuente = codigo(EDITOR_CPP)
        cuerpo = fuente.split("EActiveTimerReturnType SJamGraphEditor::CocinarSiHayPendiente")[1]
        cuerpo = cuerpo.split("\n}")[0]
        self.assertLess(cuerpo.index("bRecoccionPendiente = false"), cuerpo.index("RunGraph()"))

    def test_el_periodo_deja_al_menos_seis_recocciones_por_segundo(self):
        """Debajo de eso un arrastre se lee a saltos.

        ⚠️ La justificación que estaba acá —«la vuelta entera cuesta 3,7 ms, así que el techo lo
        pone la percepción y no el costo»— era FALSA por partida doble: esos 3,7 ms eran del
        commandlet (22,0 con el editor andando) y además medían la vuelta viva, no `RunGraph()`, que
        es lo que el live view realmente llama y cuesta 258–539 ms. El período sigue siendo el mismo
        número, pero ahora es un TECHO de cadencia, no una promesa: quien decide si se cocina
        durante el arrastre es `SegundosUltimaCoccion`."""
        header = EDITOR_H.read_text(encoding="utf-8")
        m = re.search(r"LiveDebounceSegundos\s*=\s*([0-9.]+)f", header)
        self.assertIsNotNone(m, "el período del amortiguador tiene que ser una constante nombrada")
        self.assertLessEqual(float(m.group(1)), 1.0 / 6.0)


class ElArrastreMandaTests(unittest.TestCase):
    """El bug que reportó Brian: arrastrar la perilla o el tirador se trababa.

    La causa no era la cadencia sino la PREMISA. El live view llama a `RunGraph()` —el Run público
    entero: ida y vuelta a Python, inspector y miniaturas—, medido en **258–539 ms** con el editor
    andando, contra un temporizador de 125 ms. Cada cocción tardaba de 2 a 4 veces más que el
    intervalo entre pedidos, así que el game thread cocinaba sin parar y los eventos del mouse no
    llegaban a mover la aguja.

    El arreglo no elige de antemano entre «vivo» y «al soltar»: lo decide **midiendo** cuánto costó
    la vuelta anterior de ESE grafo. Uno de pura matemática entra en el presupuesto y se sigue
    viendo en vivo; uno que cocina malla no entra, y ahí el arrastre manda y se cocina al soltar.
    """

    def cuerpo_pedir(self):
        return codigo(EDITOR_CPP).split("void SJamGraphEditor::PedirRecoccion(")[1].split("\n}")[0]

    def test_un_aviso_de_arrastre_no_cocina_si_la_vuelta_anterior_no_entro(self):
        cuerpo = self.cuerpo_pedir()
        self.assertIn("if (!bFinDeGesto && SegundosUltimaCoccion > LiveDebounceSegundos)", cuerpo)
        # Y sale ANTES de armar el temporizador: si saliera después, quedaría uno armado igual.
        self.assertLess(cuerpo.index("SegundosUltimaCoccion > LiveDebounceSegundos"),
                        cuerpo.index("RegisterActiveTimer"))

    def test_soltar_cocina_SIEMPRE_por_caro_que_sea(self):
        """Es la garantía que hace que el arreglo no sea «a veces no se actualiza»."""
        cuerpo = self.cuerpo_pedir()
        # La guarda que saltea sólo puede disparar con `!bFinDeGesto`.
        self.assertIn("!bFinDeGesto &&", cuerpo)
        self.assertNotRegex(cuerpo, r"if\s*\(\s*SegundosUltimaCoccion\s*>")

    def test_el_pedido_pendiente_sobrevive_al_salteo(self):
        """Saltear la cocción NO puede perder el pedido: lo tiene que cobrar el soltar. Por eso la
        bandera se levanta antes de la guarda y no después."""
        cuerpo = self.cuerpo_pedir()
        self.assertLess(cuerpo.index("bRecoccionPendiente = true"),
                        cuerpo.index("!bFinDeGesto &&"))

    def test_soltar_espera_menos_que_arrastrar(self):
        """Al soltar se cocina enseguida; durante el arrastre, a lo sumo cada `LiveDebounce`."""
        cuerpo = self.cuerpo_pedir()
        self.assertIn("bFinDeGesto ? LiveAsentarSegundos : LiveDebounceSegundos", cuerpo)
        header = EDITOR_H.read_text(encoding="utf-8")
        asentar = float(re.search(r"LiveAsentarSegundos\s*=\s*([0-9.]+)f", header).group(1))
        debounce = float(re.search(r"LiveDebounceSegundos\s*=\s*([0-9.]+)f", header).group(1))
        self.assertLess(asentar, debounce)
        # Y que se note como respuesta al gesto, no como otro arrastre: menos de un décimo.
        self.assertLess(asentar, 0.1)

    def test_el_costo_se_mide_alrededor_de_RunGraph(self):
        cuerpo = codigo(EDITOR_CPP).split(
            "EActiveTimerReturnType SJamGraphEditor::CocinarSiHayPendiente")[1].split("\n}")[0]
        self.assertLess(cuerpo.index("const double Inicio = FPlatformTime::Seconds()"),
                        cuerpo.index("RunGraph()"))
        self.assertLess(cuerpo.index("RunGraph()"),
                        cuerpo.index("SegundosUltimaCoccion = FPlatformTime::Seconds() - Inicio"))

    def test_el_costo_se_mide_TAMBIEN_cuando_la_coccion_viene_de_soltar(self):
        """Un grafo que se abarató —alguien borró el nodo que horneaba— tiene que poder volver a
        verse en vivo sin reabrir el panel. Si la medición sólo corriera durante el arrastre, el
        grafo quedaría marcado como caro para siempre."""
        cuerpo = codigo(EDITOR_CPP).split(
            "EActiveTimerReturnType SJamGraphEditor::CocinarSiHayPendiente")[1].split("\n}")[0]
        self.assertEqual(cuerpo.count("SegundosUltimaCoccion ="), 1,
                         "una sola asignación, sin condicionarla al tipo de pedido")
        self.assertNotIn("if (bFinDeGesto", cuerpo)

    def test_la_primera_vuelta_de_un_gesto_corre_aunque_no_se_sepa_que_cuesta(self):
        """Arranca en cero, así que la guarda no dispara hasta haber medido una vez. Suponer «caro»
        de entrada le sacaría el vivo a los grafos que sí lo pueden pagar."""
        header = EDITOR_H.read_text(encoding="utf-8")
        self.assertRegex(header, r"double\s+SegundosUltimaCoccion\s*=\s*0\.0\s*;")


class ApagadoPorOmisionTests(unittest.TestCase):
    def test_el_live_view_arranca_apagado(self):
        """Correr el grafo tiene efectos en la escena: que se prenda solo sería que rozar un slider
        empiece a colocar cosas sin que nadie lo haya pedido."""
        header = codigo(EDITOR_H)
        self.assertRegex(header, r"bool\s+bLiveView\s*=\s*false\s*;")

    def test_prenderlo_cocina_de_una(self):
        """Si no, queda «prendido» mostrando el resultado viejo hasta que alguien toque algo, y no
        hay forma de distinguir eso de que no anda."""
        fuente = codigo(EDITOR_CPP)
        cuerpo = fuente.split("void SJamGraphEditor::AlternarLiveView()")[1].split("\n}\n")[0]
        self.assertIn("PedirRecoccion()", cuerpo)

    def test_hay_un_interruptor_en_la_barra(self):
        fuente = codigo(EDITOR_CPP)
        self.assertIn("AlternarLiveView()", fuente)
        self.assertIn('LOCTEXT("LiveView"', fuente)

    def test_un_grafo_vacio_no_dispara_el_temporizador(self):
        fuente = codigo(EDITOR_CPP)
        cuerpo = fuente.split("void SJamGraphEditor::PedirRecoccion(")[1].split("\n}")[0]
        self.assertIn("Nodes.Num() == 0", cuerpo)


if __name__ == "__main__":
    unittest.main()
