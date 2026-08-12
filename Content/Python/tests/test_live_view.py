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
        self.assertIn("PedirRecoccion()", vivo.group(1))

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
        cuerpo = fuente.split("void SJamGraphEditor::PedirRecoccion()")[1].split("\n}")[0]
        self.assertIn("bRecoccionPendiente = true", cuerpo)
        self.assertNotIn("RunGraph()", cuerpo)

    def test_no_se_registra_un_temporizador_por_cada_aviso(self):
        """Sin esta guarda, un arrastre deja decenas de temporizadores latiendo sobre el mismo
        grafo, y cada uno lo corre entero."""
        fuente = codigo(EDITOR_CPP)
        cuerpo = fuente.split("void SJamGraphEditor::PedirRecoccion()")[1].split("\n}")[0]
        self.assertIn("if (!TemporizadorLive.IsValid())", cuerpo)

    def test_el_temporizador_se_apaga_solo_cuando_no_queda_nada(self):
        """Un temporizador que sigue latiendo con el grafo quieto es trabajo por nada, para siempre."""
        fuente = codigo(EDITOR_CPP)
        cuerpo = fuente.split("EActiveTimerReturnType SJamGraphEditor::CocinarSiHayPendiente")[1]
        cuerpo = cuerpo.split("\n}")[0]
        self.assertIn("EActiveTimerReturnType::Stop", cuerpo)
        self.assertIn("EActiveTimerReturnType::Continue", cuerpo)
        self.assertIn("TemporizadorLive.Reset()", cuerpo)

    def test_la_bandera_se_baja_ANTES_de_cocinar(self):
        """Bajarla después se come el aviso que llegue mientras corre el grafo, y el live view se
        queda mostrando el penúltimo valor del arrastre — un error que sólo se ve al soltar."""
        fuente = codigo(EDITOR_CPP)
        cuerpo = fuente.split("EActiveTimerReturnType SJamGraphEditor::CocinarSiHayPendiente")[1]
        cuerpo = cuerpo.split("\n}")[0]
        self.assertLess(cuerpo.index("bRecoccionPendiente = false"), cuerpo.index("RunGraph()"))

    def test_el_periodo_deja_al_menos_seis_recocciones_por_segundo(self):
        """Debajo de eso un arrastre se lee a saltos. Medido: la vuelta entera cuesta 3,7 ms, así
        que el techo lo pone la percepción y no el costo."""
        header = EDITOR_H.read_text(encoding="utf-8")
        m = re.search(r"LiveDebounceSegundos\s*=\s*([0-9.]+)f", header)
        self.assertIsNotNone(m, "el período del amortiguador tiene que ser una constante nombrada")
        self.assertLessEqual(float(m.group(1)), 1.0 / 6.0)


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
        cuerpo = fuente.split("void SJamGraphEditor::PedirRecoccion()")[1].split("\n}")[0]
        self.assertIn("Nodes.Num() == 0", cuerpo)


if __name__ == "__main__":
    unittest.main()
