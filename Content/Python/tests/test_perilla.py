"""La perilla de ángulos: el «Control Knob» del tab Params de Grasshopper.

Jam tiene **~50 parámetros que son rotaciones** —yaw/pitch/roll, ángulos de rama, `start_angle`,
`degrees`— y todos se editaban tipeando o arrastrando un número horizontal. Un ángulo no es una
cantidad cualquiera: es una DIRECCIÓN, y una aguja dice hacia dónde apunta de un vistazo mientras que
«137.5» hay que imaginárselo.

Estos tests miran las dos mitades: la DECLARACIÓN (qué params son ángulos, dato puro y testeable) y
las reglas que quedaron en Slate, leyendo el `.cpp`.
"""

from __future__ import annotations

import json
import re
import sys
import types
import unittest
from pathlib import Path

sys.modules.setdefault("unreal", types.ModuleType("unreal"))

from jam import tools  # noqa: E402

RAIZ = Path(__file__).resolve().parents[3]
KNOB = RAIZ / "Source" / "JamEditor" / "Private" / "SJamKnob.cpp"
NODO = RAIZ / "Source" / "JamEditor" / "Private" / "SJamGraphNode.cpp"


def codigo(ruta: Path) -> str:
    texto = re.sub(r"/\*.*?\*/", "", ruta.read_text(encoding="utf-8"), flags=re.S)
    return "\n".join(l for l in texto.splitlines() if not l.strip().startswith("//"))


class DeclaracionTests(unittest.TestCase):
    def test_hay_bastantes_params_angulares_para_que_valga_la_pena(self) -> None:
        """Si fueran tres, la perilla sería un adorno. Son ~50: por eso va en la FICHA y no como un
        nodo suelto, que es como la tiene Grasshopper (allá los params son nodos)."""
        total = sum(len(pins) for pins in tools.PARAMS_ANGULARES.values())
        self.assertGreater(total, 30, "quedaron muy pocos params declarados como ángulo")

    def test_todo_param_declarado_EXISTE_y_es_un_numero(self) -> None:
        """Un ángulo declarado sobre un pin que no existe es una perilla que nunca aparece; sobre un
        booleano, un control que enseña una mentira sobre el parámetro."""
        from jam import math_core
        for verbo, pins in tools.PARAMS_ANGULARES.items():
            # Los nodos de VALOR viven en otro registro: `math_radians` es uno de ellos.
            info = tools.REGISTRO.get(verbo) or math_core.VALORES.get(verbo)
            with self.subTest(verbo=verbo):
                self.assertIsNotNone(info, f"«{verbo}» no está en ningún registro")
                for pin in pins:
                    self.assertIn(pin, info["params"], f"{verbo}.{pin} no existe")
                    valor = info["params"][pin]
                    self.assertNotIsInstance(valor, bool, f"{verbo}.{pin} es un booleano")
                    self.assertIsInstance(valor, (int, float), f"{verbo}.{pin} no es un número")

    def test_NO_se_declaran_los_que_miden_en_radianes(self) -> None:
        """`math_sin/cos/tan` toman radianes. Convertirlos para la aguja agregaría un camino de ida
        y vuelta cuyo único consumidor son tres verbos, y para pasar de grados a radianes ya está
        `math_radians`, que es un nodo que se ve."""
        for verbo in ("math_sin", "math_cos", "math_tan", "math_degrees"):
            with self.subTest(verbo=verbo):
                self.assertNotIn(verbo, tools.PARAMS_ANGULARES)

    def test_los_falsos_positivos_del_nombre_quedaron_afuera(self) -> None:
        """La razón de declararlo en vez de derivarlo del nombre: estos cinco lo contienen y no son
        ángulos —tres son booleanos y dos sólo comparten letras—."""
        casos = (("mesh_uv_pack", "optimize_rotation"), ("mesh_normals", "angle_weighted"),
                 ("points_to_frames", "giro_al_azar"), ("mesh_simplify_count", "target_triangles"),
                 ("mesh_compare", "triangulos"))
        for verbo, pin in casos:
            with self.subTest(verbo=verbo, pin=pin):
                self.assertNotIn(pin, tools.PARAMS_ANGULARES.get(verbo, ()))

    def test_la_unidad_viaja_en_el_spec(self) -> None:
        """El C++ no puede derivarla: tiene que venir dada, como la letra del modo compacto."""
        spec = json.loads(tools.spec_json(include_graph_only=True))
        con_unidad = [(t["verbo"], p["nombre"]) for t in spec["tools"] for p in t["params"]
                      if p.get("unidad") == "grados"]
        self.assertGreater(len(con_unidad), 30)
        self.assertIn(("place", "yaw"), con_unidad)

    def test_unidad_de_contesta_vacio_para_lo_que_no_es_angulo(self) -> None:
        self.assertEqual(tools.unidad_de("place", "yaw"), "grados")
        self.assertEqual(tools.unidad_de("place", "x"), "")
        self.assertEqual(tools.unidad_de("verbo_inexistente", "yaw"), "")


class ReglasDeSlateTests(unittest.TestCase):
    def test_la_perilla_ACOMPAÑA_al_numero_y_no_lo_reemplaza(self) -> None:
        """Una perilla sola sacaría la capacidad de escribir 137,5 exacto y dejaría al usuario
        peleando con el mouse por medio grado. Es además la postura de riesgo correcta para un
        widget dibujado a mano: si la aguja pinta mal, el campo sigue funcionando."""
        fuente = codigo(NODO)
        bloque = fuente[fuente.index('P.Unidad == TEXT("grados")'):]
        bloque = bloque[:bloque.index('if (Key == TEXT("expr"))')]
        # Que el nombre `Field` aparezca no alcanza: aparece igual dentro de las lambdas de la
        # perilla. Lo que hay que exigir es que OCUPE UNA RANURA del layout — sacarle la ranura y
        # dejar las lambdas pasaba este test cuando estaba escrito así. Lo destapó una mutación.
        self.assertIn("[ Field ]", bloque, "el campo dejó de ocupar una ranura: la perilla lo reemplazó")
        self.assertIn("SJamKnob", bloque)

    def test_el_campo_es_la_UNICA_fuente_de_verdad(self) -> None:
        """La perilla lo lee para pintarse y lo escribe al arrastrar. Con un holder propio habría
        dos estados del mismo valor y uno se desincronizaría."""
        fuente = codigo(NODO)
        bloque = fuente[fuente.index('P.Unidad == TEXT("grados")'):]
        bloque = bloque[:bloque.index('if (Key == TEXT("expr"))')]
        self.assertIn("Field->GetText()", bloque)
        self.assertIn("Field->SetText", bloque)

    def test_avisa_por_frame_al_girar_y_UNA_vez_al_soltar(self) -> None:
        """Los dos avisos separados, igual que los sliders: uno alimenta el live view y el otro deja
        UN paso de historial por arrastre en vez de uno por frame."""
        fuente = codigo(NODO)
        bloque = fuente[fuente.index('P.Unidad == TEXT("grados")'):]
        bloque = bloque[:bloque.index('if (Key == TEXT("expr"))')]
        self.assertIn("OnParamLiveDelegate", bloque)
        self.assertIn("OnParamChangedDelegate", bloque)

    def test_el_arrastre_captura_el_mouse(self) -> None:
        """El círculo mide 24 px: sin capturar, salirse de él suelta la perilla a mitad de gesto,
        que es lo que pasaría siempre."""
        self.assertIn("CaptureMouse", codigo(KNOB))
        self.assertIn("ReleaseMouseCapture", codigo(KNOB))

    def test_gira_por_DELTA_y_no_salta_al_angulo_del_puntero(self) -> None:
        """Es la diferencia entre una perilla y un selector: al tocarla, la aguja no debe saltar a
        donde está el mouse."""
        # Acotado al CUERPO de OnMouseButtonDown: que los nombres existan en el archivo no dice
        # nada —siguen declarados y usados al mover—, y borrar justo estas dos asignaciones pasaba
        # el test cuando miraba el archivo entero.
        fuente = codigo(KNOB)
        cuerpo = fuente[fuente.index("FReply SJamKnob::OnMouseButtonDown"):]
        cuerpo = cuerpo[:cuerpo.index("FReply SJamKnob::OnMouseMove")]
        self.assertIn("AnguloAlAgarrar =", cuerpo,
                      "no se guarda dónde se agarró: la aguja salta al ángulo del puntero")
        self.assertIn("ValorAlAgarrar =", cuerpo)

    def test_el_valor_NO_se_acota_ni_se_envuelve(self) -> None:
        """Un yaw de 720° son dos vueltas y significa algo distinto de 0° en cuanto alguien lo
        acumula o lo anima. La AGUJA muestra el resto de 360; el número, todo."""
        fuente = codigo(KNOB)
        self.assertIn("FMath::Fmod(Angle.Get(), 360.0f)", fuente,
                      "la aguja dejó de mostrar el resto de 360")
        self.assertNotIn("FMath::Clamp(Nuevo", fuente, "el valor se acotó: se perdieron las vueltas")


if __name__ == "__main__":
    unittest.main()
