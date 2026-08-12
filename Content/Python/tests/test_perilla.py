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


class LosDosLectoresDelSpecTests(unittest.TestCase):
    """El spec de una ficha se lee en DOS lugares del C++, y se desfasaron dos veces.

    · `LoadSpec` (`JamEditorModule.cpp`) lee todas las tools al arrancar, y es de ahí que el Graph
      recibe las suyas.
    · `JamLeerParamsDeFicha` (`SJamGraphEditor.cpp`) las lee cuando se instala una función EN VIVO.

    El docstring del segundo dice que existe porque «había TRES lectores de ficha escritos a mano y
    sólo el primero leía `params`», con la consecuencia de que una función instalada en vivo perdía
    sus perillas hasta reiniciar — «el peor síntoma posible (funciona a veces)».

    Y volvió a pasar dos veces: la perilla de ángulos se agregó sólo al segundo lector, así que no
    aparecía en ningún nodo del Graph (**lo encontró Brian con una captura de un `place`**); y
    `etiquetas_opciones` estaba sólo en el primero, así que una función instalada en vivo mostraba
    los valores crudos de sus desplegables en vez de las etiquetas humanas.

    Este test compara qué campos del JSON lee cada uno. No prueba que los usen bien —para eso están
    los otros— pero sí que ninguno se olvide de uno.
    """

    #: `params` es la LLAVE CONTENEDORA de la lista, no un campo del parámetro: el lector del Graph
    #: la abre adentro de la misma función y el del módulo, un scope más arriba.
    CONTENEDOR = {"params"}

    def campos_leidos(self, texto: str) -> set:
        return set(re.findall(
            r'(?:TryGet|Get)(?:String|Array|Number|Bool)Field\(TEXT\("([^"]+)"\)', texto))

    def test_los_dos_lectores_leen_los_MISMOS_campos(self) -> None:
        modulo = (RAIZ / "Source" / "JamEditor" / "Private" / "JamEditorModule.cpp").read_text(
            encoding="utf-8")
        editor = (RAIZ / "Source" / "JamEditor" / "Private" / "SJamGraphEditor.cpp").read_text(
            encoding="utf-8")

        bloque_modulo = modulo[modulo.index("FJamParam P;"):modulo.index("T.Params.Add(P);")]
        bloque_editor = editor[editor.index("static void JamLeerParamsDeFicha"):]
        bloque_editor = bloque_editor[:bloque_editor.index("\n}")]

        a = self.campos_leidos(bloque_modulo) - self.CONTENEDOR
        b = self.campos_leidos(bloque_editor) - self.CONTENEDOR
        self.assertEqual(a, b,
                         f"los dos lectores del spec se desfasaron · sólo LoadSpec: {sorted(a - b)} "
                         f"· sólo JamLeerParamsDeFicha: {sorted(b - a)}")

    def test_los_dos_leen_la_unidad(self) -> None:
        """El campo que faltaba, nombrado: sin él en `LoadSpec`, la perilla no aparece en NINGÚN
        nodo del Graph, porque de ahí salen sus tools."""
        for archivo in ("JamEditorModule.cpp", "SJamGraphEditor.cpp"):
            with self.subTest(archivo=archivo):
                fuente = (RAIZ / "Source" / "JamEditor" / "Private" / archivo).read_text(
                    encoding="utf-8")
                self.assertIn('TEXT("unidad")', fuente)

class ShiftAcomodaTests(unittest.TestCase):
    """Con Shift apretado, la perilla salta de a 5°.

    Pedido de Brian. «De a 5» tiene dos lecturas que eligen cosas distintas: caer en MÚLTIPLOS de 5
    —45, 90, 135— o avanzar de a 5 desde donde se agarró —258,8 → 263,8—. Se eligió la primera,
    porque la gracia de acomodar un ángulo es justamente sacarse el decimal feo de encima; la
    segunda lo conserva para siempre.
    """

    def cuerpo(self, funcion: str) -> str:
        fuente = codigo(KNOB)
        desde = fuente.index(f"FReply SJamKnob::{funcion}")
        resto = fuente[desde + 10:]
        fin = resto.index("\nFReply SJamKnob::") if "\nFReply SJamKnob::" in resto else len(resto)
        return fuente[desde:desde + 10 + fin]

    def test_el_paso_es_de_CINCO_grados(self) -> None:
        """Cinco divide a 45, 90 y 360: las posiciones que alguien busca a mano —los ejes y las
        diagonales— caen todas adentro de la grilla."""
        self.assertIn("constexpr float PasoConShift = 5.0f;", codigo(KNOB))

    def test_acomoda_el_VALOR_y_no_el_avance(self) -> None:
        """Redondear el avance conservaría el decimal de donde se agarró, que es lo que se quería
        sacar. Se redondea el valor final contra la grilla absoluta."""
        cuerpo = self.cuerpo("OnMouseMove")
        self.assertIn("FMath::RoundToFloat(Nuevo / PasoConShift) * PasoConShift", cuerpo)
        self.assertNotIn("RoundToFloat(Delta", cuerpo, "se está acomodando el avance, no el valor")

    def test_se_pregunta_en_CADA_movimiento_y_no_al_agarrar(self) -> None:
        """Para poder apretar y soltar Shift a mitad del arrastre: acercarse rápido y después
        afinar es cómo se usa una perilla. Preguntándolo al agarrar, el modo quedaría congelado."""
        self.assertIn("IsShiftDown()", self.cuerpo("OnMouseMove"))
        self.assertNotIn("IsShiftDown()", self.cuerpo("OnMouseButtonDown"),
                         "el modo se decide al agarrar: Shift dejaría de poder soltarse a mitad")

    def test_sin_Shift_el_giro_sigue_siendo_continuo(self) -> None:
        """La regresión que importa: acomodar SIEMPRE sacaría el medio grado, que es justo lo que
        la perilla tiene que poder hacer cuando no se le pide lo contrario."""
        cuerpo = self.cuerpo("OnMouseMove")
        antes = cuerpo.index("float Nuevo = ValorAlAgarrar + Delta;")
        acomoda = cuerpo.index("PasoConShift")
        self.assertIn("if (Event.IsShiftDown())", cuerpo[antes:acomoda],
                      "el acomodado no está detrás de la guarda de Shift")

    def test_el_tooltip_lo_ANUNCIA(self) -> None:
        """Un gesto con tecla que no está escrito en ningún lado no existe: nadie prueba Shift por
        las dudas."""
        nodo = codigo(NODO)
        bloque = nodo[nodo.index('P.Unidad == TEXT("grados")'):]
        bloque = bloque[:bloque.index('if (Key == TEXT("expr"))')]
        self.assertIn("Shift", bloque)
        self.assertIn("5", bloque)


class ContrasteTests(unittest.TestCase):
    """La perilla tiene que VERSE sobre el cuerpo de la ficha.

    La primera versión no se veía: el aro iba en gris medio a 55% de alfa sobre un cuerpo gris claro
    —**1,17:1**— así que de la perilla sólo asomaba la aguja, un guioncito suelto al lado del campo.
    Brian lo reportó con una captura.

    El umbral no es una opinión: **3:1 es el mínimo de WCAG 1.4.11 («Non-text Contrast») para un
    control de interfaz**, y es el mismo criterio con el que se juzga cualquier botón. Se mide sobre
    los valores LINEALES —que es como Slate declara sus colores— y **contando el alfa**, porque
    mezclar 55% de gris con el fondo es casi el fondo: ignorarlo fue justamente el error.
    """

    #: El cuerpo de la ficha, de `SJamGraphNode.cpp`.
    FICHA = (0.76, 0.77, 0.78)
    MINIMO = 3.0

    def luminancia(self, c) -> float:
        return 0.2126 * c[0] + 0.7152 * c[1] + 0.0722 * c[2]

    def contraste(self, color, alfa) -> float:
        mezclado = tuple(color[i] * alfa + self.FICHA[i] * (1 - alfa) for i in range(3))
        a, b = self.luminancia(mezclado), self.luminancia(self.FICHA)
        return (max(a, b) + 0.05) / (min(a, b) + 0.05)

    def colores(self, texto: str):
        """Todos los `FLinearColor(r, g, b, a)` literales de un archivo."""
        # `FLinearColor(...)` y también `FLinearColor Tinta(...)`: la segunda forma es una
        # declaración con nombre y el patrón sin ella se saltea justo el color del aro, que es el
        # que había quedado invisible.
        patron = (r"FLinearColor(?:\s+\w+)?\(([\d.]+)f,\s*([\d.]+)f,\s*"
                  r"([\d.]+)f(?:,\s*([\d.]+)f)?\)")
        for m in re.finditer(patron, texto):
            r, g, b = (float(m.group(i)) for i in (1, 2, 3))
            yield (r, g, b), float(m.group(4)) if m.group(4) else 1.0

    def test_el_cuerpo_de_la_ficha_sigue_siendo_el_que_se_midio(self) -> None:
        """Si el fondo cambia, todos los contrastes de abajo dejan de significar lo que dicen."""
        nodo = (RAIZ / "Source" / "JamEditor" / "Private" / "SJamGraphNode.cpp").read_text(
            encoding="utf-8")
        self.assertIn("FLinearColor(0.76f, 0.77f, 0.78f, 1.0f)", nodo,
                      "cambió el cuerpo de la ficha: hay que volver a medir la perilla")

    def test_todo_lo_que_dibuja_la_perilla_se_ve(self) -> None:
        fuentes = {
            "SJamKnob.cpp": (RAIZ / "Source" / "JamEditor" / "Private" / "SJamKnob.cpp"),
            "SJamKnob.h": (RAIZ / "Source" / "JamEditor" / "Public" / "SJamKnob.h"),
        }
        vistos = 0
        for nombre, ruta in fuentes.items():
            for color, alfa in self.colores(ruta.read_text(encoding="utf-8")):
                vistos += 1
                with self.subTest(archivo=nombre, color=color, alfa=alfa):
                    ratio = self.contraste(color, alfa)
                    self.assertGreaterEqual(
                        ratio, self.MINIMO,
                        f"{color} al {alfa:.0%} da {ratio:.2f}:1 contra la ficha; "
                        f"el mínimo para un control es {self.MINIMO}:1")
        self.assertGreater(vistos, 1, "no se encontró ningún color: el patrón dejó de matchear")

if __name__ == "__main__":
    unittest.main()
