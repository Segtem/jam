"""Matrices 4×4: la cuenta, el tipo `MX`, y el reparto de las salidas extra por los cables.

Es el consumidor por el que se hizo multi-salida. `matrix_decompose` publica CINCO valores de una
sola cuenta —traslación, escala y los tres ejes— y es el primer verbo cuyo resultado guardado no es
lo que muestra ningún pin, ni siquiera el principal.

Convención bajo prueba, fijada en `math_core` y en un solo lugar: almacenamiento por FILAS, vectores
COLUMNA, traslación en la última columna, y por lo tanto `a × b` aplica primero `b`.
"""

from __future__ import annotations

import json
import math
import re
import sys
import types
import unittest
from pathlib import Path

_unreal_fake = sys.modules.setdefault("unreal", types.ModuleType("unreal"))
if not hasattr(_unreal_fake, "TopLevelAssetPath"):
    _unreal_fake.TopLevelAssetPath = lambda package, name: (package, name)

from jam import api, flow, graph, math_core, ribbon, tools  # noqa: E402


RAIZ = Path(__file__).resolve().parents[3]

I = math_core._IDENTIDAD


def val(verbo: str, **params):
    """Corre un verbo de valor por el camino de `evaluar`, que es el que usan Graph y Flow."""
    defaults = dict(math_core.VALORES[verbo]["params"])
    defaults.update(params)
    return math_core.evaluar(verbo, defaults, {}, lambda *_a, **_k: None)


def casi(a, b, sitio=1e-9):
    return all(abs(x - y) <= sitio for x, y in zip(a, b))


class LaCuentaTests(unittest.TestCase):
    def test_la_identidad_no_hace_nada(self):
        self.assertEqual(val("matrix_identity"), I)
        self.assertEqual(val("matrix_multiply", a=I, b=I), I)
        m = val("matrix_translation", **{"traslación": (10, 20, 30)})
        self.assertEqual(val("matrix_multiply", a=m, b=I), m)
        self.assertEqual(val("matrix_multiply", a=I, b=m), m)

    def test_la_traslacion_vive_en_la_ULTIMA_COLUMNA(self):
        """La convención entera cuelga de esto. Con vectores fila iría en la última FILA, y la
        matriz se vería «bien» hasta que alguien la usara: transformaría sin mover nada."""
        m = val("matrix_translation", **{"traslación": (10, 20, 30)})
        self.assertEqual((m[3], m[7], m[11]), (10.0, 20.0, 30.0))
        self.assertEqual((m[12], m[13], m[14], m[15]), (0.0, 0.0, 0.0, 1.0))

    def test_multiplicar_NO_es_conmutativo_y_aplica_primero_la_de_la_derecha(self):
        """El error clásico de la familia, y el único que no da error: da la posición equivocada.

        Mover (10,0,0) y después escalar ×2 deja el punto en 20. Escalar ×2 y después mover lo deja
        en 10. Son las dos lecturas de `a × b` y sólo una es la de la convención.
        """
        t = val("matrix_translation", **{"traslación": (10, 0, 0)})
        s = val("matrix_scale_matrix", escala=(2, 2, 2))
        escalar_despues = val("matrix_multiply", a=s, b=t)
        mover_despues = val("matrix_multiply", a=t, b=s)
        self.assertNotEqual(escalar_despues, mover_despues, "salió conmutativa: la cuenta está mal")
        self.assertTrue(casi(val("matrix_transform_point", matriz=escalar_despues, punto=(0, 0, 0)),
                             (20.0, 0.0, 0.0)))
        self.assertTrue(casi(val("matrix_transform_point", matriz=mover_despues, punto=(0, 0, 0)),
                             (10.0, 0.0, 0.0)))

    def test_una_rotacion_de_90_sobre_Z_lleva_X_a_Y(self):
        m = val("matrix_rotation", eje=(0, 0, 1), **{"ángulo": 90.0})
        self.assertTrue(casi(val("matrix_transform_direction", matriz=m, **{"dirección": (1, 0, 0)}),
                             (0.0, 1.0, 0.0), 1e-12))

    def test_el_eje_de_rotacion_se_normaliza_solo(self):
        """Sin normalizar, el largo del eje se cuela como escala y la «rotación» deforma."""
        corto = val("matrix_rotation", eje=(0, 0, 1), **{"ángulo": 37.0})
        largo = val("matrix_rotation", eje=(0, 0, 9), **{"ángulo": 37.0})
        self.assertTrue(casi(corto, largo, 1e-12))

    def test_el_eje_cero_no_tiene_direccion_y_es_error(self):
        with self.assertRaises(math_core.ValorError):
            val("matrix_rotation", eje=(0, 0, 0), **{"ángulo": 37.0})

    def test_un_punto_arrastra_la_traslacion_y_una_direccion_NO(self):
        """Es la diferencia entre los dos verbos y la razón de que sean dos.

        Mover el mundo entero no cambia hacia dónde apunta una normal. Pasar una dirección por el
        verbo de punto es lo que deja la iluminación rota sin que nada falle.
        """
        m = val("matrix_translation", **{"traslación": (5, 0, 0)})
        self.assertTrue(casi(val("matrix_transform_point", matriz=m, punto=(1, 0, 0)), (6.0, 0, 0)))
        self.assertTrue(casi(
            val("matrix_transform_direction", matriz=m, **{"dirección": (1, 0, 0)}), (1.0, 0, 0)))

    def test_el_determinante_es_cuanto_agranda_el_volumen(self):
        self.assertAlmostEqual(val("matrix_determinant", matriz=I), 1.0)
        s = val("matrix_scale_matrix", escala=(2, 3, 4))
        self.assertAlmostEqual(val("matrix_determinant", matriz=s), 24.0)
        # Una rotación no cambia el volumen, sea cual sea el eje.
        r = val("matrix_rotation", eje=(1, 2, 3), **{"ángulo": 61.0})
        self.assertAlmostEqual(val("matrix_determinant", matriz=r), 1.0, places=12)

    def test_transponer_dos_veces_devuelve_la_misma_matriz(self):
        m = val("matrix_multiply",
                a=val("matrix_translation", **{"traslación": (1, 2, 3)}),
                b=val("matrix_rotation", eje=(0, 1, 0), **{"ángulo": 33.0}))
        self.assertTrue(casi(val("matrix_transpose", matriz=val("matrix_transpose", matriz=m)), m))

    def test_la_inversa_deshace_la_transformacion(self):
        m = val("matrix_multiply",
                a=val("matrix_translation", **{"traslación": (10, -4, 7)}),
                b=val("matrix_multiply",
                      a=val("matrix_rotation", eje=(1, 1, 0), **{"ángulo": 47.0}),
                      b=val("matrix_scale_matrix", escala=(2, 0.5, 3))))
        inv = val("matrix_inverse", matriz=m)
        self.assertTrue(casi(val("matrix_multiply", a=m, b=inv), I, 1e-12))
        punto = (3.0, -8.0, 1.5)
        ida = val("matrix_transform_point", matriz=m, punto=punto)
        self.assertTrue(casi(val("matrix_transform_point", matriz=inv, punto=ida), punto, 1e-11))

    def test_una_matriz_singular_es_ERROR_y_no_la_identidad(self):
        """Devolver identidad ante una singular es el defecto silencioso más caro de la familia: la
        cadena sigue corriendo, todo queda sin transformar, y el síntoma aparece diez nodos después.
        """
        aplasta = val("matrix_scale_matrix", escala=(1, 1, 0))
        self.assertAlmostEqual(val("matrix_determinant", matriz=aplasta), 0.0)
        with self.assertRaises(math_core.ValorError) as caso:
            val("matrix_inverse", matriz=aplasta)
        self.assertIn("singular", str(caso.exception))

    def test_el_determinante_y_la_inversa_salen_de_la_misma_cuenta(self):
        """Si discreparan, discreparían justo en el borde singular, que es el único lugar donde el
        determinante decide algo. Se comprueba sobre matrices casi degeneradas."""
        for e in (1e-6, 1e-9, 1e-12):
            m = val("matrix_scale_matrix", escala=(1, 1, e))
            with self.subTest(escala_z=e):
                det = val("matrix_determinant", matriz=m)
                if det == 0.0:
                    with self.assertRaises(math_core.ValorError):
                        val("matrix_inverse", matriz=m)
                else:
                    val("matrix_inverse", matriz=m)


class ElTextoDeUnPinTests(unittest.TestCase):
    """Un pin `MX` sin cable recibe lo que quedó guardado en el `.jamgraph`, que es TEXTO."""

    def test_acepta_comas_espacios_y_renglones(self):
        tira = ",".join(str(c) for c in I)
        renglones = "\n".join(" ".join(str(c) for c in I[f * 4:f * 4 + 4]) for f in range(4))
        self.assertEqual(val("matrix_transpose", matriz=tira), I)
        self.assertEqual(val("matrix_transpose", matriz=renglones), I)

    def test_quince_numeros_no_son_una_matriz(self):
        with self.assertRaises(math_core.ValorError) as caso:
            val("matrix_transpose", matriz=",".join(str(c) for c in I[:15]))
        self.assertIn("dieciséis", str(caso.exception))

    def test_una_componente_infinita_es_error(self):
        with self.assertRaises(math_core.ValorError):
            val("matrix_transpose", matriz=(float("inf"),) + I[1:])

    def test_el_default_de_todo_pin_MX_es_una_matriz_valida(self):
        """Un default que no parsea deja el nodo en error apenas se lo crea, sin haber tocado nada."""
        for verbo, meta in math_core.VALORES.items():
            for pin, tipo in (meta.get("tipos") or {}).items():
                if tipo == "MX":
                    with self.subTest(verbo=verbo, pin=pin):
                        math_core._matriz(meta["params"][pin], pin)


class DescomponerTests(unittest.TestCase):
    def test_abre_una_matriz_afin_en_sus_cinco_partes(self):
        m = val("matrix_multiply",
                a=val("matrix_translation", **{"traslación": (10, 20, 30)}),
                b=val("matrix_multiply",
                      a=val("matrix_rotation", eje=(0, 0, 1), **{"ángulo": 90.0}),
                      b=val("matrix_scale_matrix", escala=(2, 3, 4))))
        traslacion, escala, ex, ey, ez = val("matrix_decompose", matriz=m)
        self.assertTrue(casi(traslacion, (10.0, 20.0, 30.0)))
        self.assertTrue(casi(escala, (2.0, 3.0, 4.0), 1e-12))
        # Girada 90° sobre Z: el eje X apunta a +Y y el Y a −X.
        self.assertTrue(casi(ex, (0.0, 1.0, 0.0), 1e-12))
        self.assertTrue(casi(ey, (-1.0, 0.0, 0.0), 1e-12))
        self.assertTrue(casi(ez, (0.0, 0.0, 1.0), 1e-12))

    def test_los_tres_ejes_vuelven_a_armar_la_misma_matriz(self):
        """La prueba de que la descomposición no perdió nada: se rearma y tiene que dar lo mismo."""
        m = val("matrix_multiply",
                a=val("matrix_translation", **{"traslación": (-3, 8, 1)}),
                b=val("matrix_multiply",
                      a=val("matrix_rotation", eje=(1, 2, 3), **{"ángulo": 41.0}),
                      b=val("matrix_scale_matrix", escala=(1.5, 2.5, 0.5))))
        t, s, ex, ey, ez = val("matrix_decompose", matriz=m)
        rearmada = (ex[0] * s[0], ey[0] * s[1], ez[0] * s[2], t[0],
                    ex[1] * s[0], ey[1] * s[1], ez[1] * s[2], t[1],
                    ex[2] * s[0], ey[2] * s[1], ez[2] * s[2], t[2],
                    0.0, 0.0, 0.0, 1.0)
        self.assertTrue(casi(rearmada, m, 1e-12))

    def test_una_matriz_con_proyeccion_no_se_descompone(self):
        con_perspectiva = I[:12] + (0.0, 0.0, -0.5, 1.0)
        with self.assertRaises(math_core.ValorError) as caso:
            val("matrix_decompose", matriz=con_perspectiva)
        self.assertIn("afín", str(caso.exception))

    def test_una_escala_cero_deja_un_eje_sin_direccion(self):
        with self.assertRaises(math_core.ValorError) as caso:
            val("matrix_decompose", matriz=val("matrix_scale_matrix", escala=(1, 0, 1)))
        self.assertIn("Y", str(caso.exception))

    def test_una_matriz_que_ESPEJA_se_niega_en_vez_de_perder_el_volteo(self):
        """Tres ejes unitarios formarían una terna derecha, o sea que devolverlos perdería el
        espejo sin decirlo. Repartir el signo entre escalas negativas admite tres respuestas y
        elegir una callada es peor que negarse."""
        espejo = val("matrix_scale_matrix", escala=(-1, 1, 1))
        with self.assertRaises(math_core.ValorError) as caso:
            val("matrix_decompose", matriz=espejo)
        self.assertIn("espeja", str(caso.exception))


class LasCincoSalidasTests(unittest.TestCase):
    def test_publica_cuatro_salidas_ADEMAS_de_la_principal(self):
        extras = graph.salidas_extra("matrix_decompose", tools.REGISTRO)
        self.assertEqual([n for n, _t, _e, _c in extras], ["escala", "eje_x", "eje_y", "eje_z"])
        self.assertEqual({t for _n, t, _e, _c in extras}, {"V"})

    def test_el_pin_principal_entrega_la_TRASLACION_y_no_la_tupla_entera(self):
        """Primer verbo con `corte_principal`: el valor guardado son los cinco vectores y ningún
        pin lo muestra tal cual. Sin el corte, `out` diría «vector» y entregaría cinco."""
        m = val("matrix_translation", **{"traslación": (7, 8, 9)})
        entero = val("matrix_decompose", matriz=m)
        self.assertEqual(len(entero), 5)
        salida = graph._valor_del_pin("matrix_decompose", "out", entero, tools.REGISTRO)
        self.assertEqual(salida, (7.0, 8.0, 9.0))

    def test_cada_salida_extra_entrega_su_parte(self):
        m = val("matrix_scale_matrix", escala=(2, 3, 4))
        entero = val("matrix_decompose", matriz=m)
        cortes = {pin: graph._valor_del_pin("matrix_decompose", pin, entero, tools.REGISTRO)
                  for pin in ("escala", "eje_x", "eje_y", "eje_z")}
        self.assertEqual(cortes["escala"], (2.0, 3.0, 4.0))
        self.assertEqual(cortes["eje_x"], (1.0, 0.0, 0.0))
        self.assertEqual(cortes["eje_y"], (0.0, 1.0, 0.0))
        self.assertEqual(cortes["eje_z"], (0.0, 0.0, 1.0))

    def test_el_corte_principal_tambien_manda_en_el_resolvedor_de_valores(self):
        """⚠️ `math_core._rebanar` es OTRA implementación del mismo reparto —la que sirve los cables
        entre nodos de VALOR— y una mutación que la neutraliza dejaba todo en verde: los tests
        entraban por `graph._valor_del_pin`. Es la trampa de siempre, llamar a la función es el
        ATAJO. Acá se entra por `resolver`, que es lo que corre cuando el grafo se compila.

        Sin el corte, el largo recibiría los cinco vectores y `_vector` se quejaría de que «un
        vector son tres números; llegaron 5».
        """
        nodos = {"m": {"verb": "matrix_translation", "params": {"traslación": "7,8,9"}},
                 "d": {"verb": "matrix_decompose", "params": {}},
                 "l": {"verb": "vector_length", "params": {}}}
        enlaces = [("m", "out", "d", "matriz"), ("d", "out", "l", "vector")]
        _tabla, por_nodo, errores = math_core.resolver(
            nodos, enlaces, campo_verbo="verb", eval_expr=lambda *_a, **_k: None)
        self.assertEqual(errores, {}, "el corte principal no llegó por el cable")
        self.assertAlmostEqual(por_nodo["l"], math.sqrt(7 ** 2 + 8 ** 2 + 9 ** 2))

    def test_una_salida_extra_tambien_viaja_por_el_resolvedor_de_valores(self):
        nodos = {"m": {"verb": "matrix_scale_matrix", "params": {"escala": "3,4,0"}},
                 "d": {"verb": "matrix_decompose", "params": {}},
                 "l": {"verb": "vector_length", "params": {}}}
        # Escala (3,4,0) no se descompone —un eje sin dirección—, así que se usa (3,4,12).
        nodos["m"]["params"]["escala"] = "3,4,12"
        enlaces = [("m", "out", "d", "matriz"), ("d", "escala", "l", "vector")]
        _tabla, por_nodo, errores = math_core.resolver(
            nodos, enlaces, campo_verbo="verb", eval_expr=lambda *_a, **_k: None)
        self.assertEqual(errores, {})
        self.assertAlmostEqual(por_nodo["l"], 13.0)

    def test_un_pin_que_no_existe_no_devuelve_el_valor_entero(self):
        entero = val("matrix_decompose", matriz=I)
        self.assertIsNone(graph._valor_del_pin("matrix_decompose", "eje_w", entero, tools.REGISTRO))

    def test_leer_las_cinco_no_cuesta_mas_que_leer_una(self):
        """Contra un CONTROL, no contra un absoluto: un nodo de valor se evalúa dos veces SIEMPRE
        —punto fijo de `resolver`— aun solo en el grafo, así que exigir «una sola vez» fijaría en un
        test una propiedad ajena a multi-salida."""
        cuenta = {"n": 0}
        original = math_core._mx_partes

        def contando(m):
            cuenta["n"] += 1
            return original(m)

        math_core.VALORES["matrix_decompose"]["operacion"] = contando
        try:
            nodos = {"m": {"verb": "matrix_decompose", "params": {"matriz": I}}}
            math_core.resolver(nodos, [], campo_verbo="verb", eval_expr=lambda *_a, **_k: None)
            control = cuenta["n"]
            cuenta["n"] = 0
            consumidores = {f"c{i}": {"verb": "vector_length", "params": {"vector": "0,0,1"}}
                            for i in range(5)}
            enlaces = [("m", pin, f"c{i}", "vector") for i, pin in enumerate(
                ("out", "escala", "eje_x", "eje_y", "eje_z"))]
            math_core.resolver({**nodos, **consumidores}, enlaces, campo_verbo="verb",
                               eval_expr=lambda *_a, **_k: None)
            self.assertLessEqual(cuenta["n"], control,
                                 "leer los cinco pines recalculó la descomposición")
        finally:
            math_core.VALORES["matrix_decompose"]["operacion"] = original

    def test_cada_pin_se_valida_al_CALCULAR_y_no_al_leer_el_cable(self):
        """`_rebanar` corre FUERA del `try` de `resolver`: un corte que levante allá no cuelga del
        nodo culpable — voltea la resolución del grafo entero. Por eso la validación por pin está
        adentro de `evaluar`, donde el error queda atado a su nodo."""
        meta = math_core.VALORES["matrix_decompose"]
        original = meta["outs"]
        meta["outs"] = (("escala", "V", "escala", lambda p: (1.0, 2.0)),) + original[1:]
        try:
            with self.assertRaises(math_core.ValorError):
                val("matrix_decompose", matriz=I)
        finally:
            meta["outs"] = original




class ElTipoMXTests(unittest.TestCase):
    def cpp(self, rel: str) -> str:
        return (RAIZ / rel).read_text(encoding="utf-8")

    def tabla(self, funcion: str, variable: str) -> set:
        editor = self.cpp("Source/JamEditor/Private/SJamGraphEditor.cpp")
        cuerpo = editor[editor.index(f"SJamGraphEditor::{funcion}"):]
        cuerpo = cuerpo[:cuerpo.index("\n}\n")]
        return set(re.findall(variable + r' == TEXT\("([^"]+)"\)', cuerpo))

    def tipos_de_los_verbos_de_valor(self) -> set:
        usados = set()
        for meta in math_core.VALORES.values():
            usados |= set((meta.get("tipos") or {}).values())
            if meta.get("out_name"):
                usados.add(meta["out_name"])
            usados |= {t for _n, t, _e, _c in meta.get("outs", ())}
        return usados

    def test_todo_tipo_de_un_verbo_de_valor_tiene_color_y_NOMBRE(self):
        """`test_paleta` sólo mira `tools.REGISTRO`, donde los verbos de valor NO están: por eso
        `V` y `D` pudieron entrar sin nombre y mostrar la letra cruda del protocolo. Este cierra
        ese lado, que es justo por donde entró `MX`."""
        usados = self.tipos_de_los_verbos_de_valor()
        self.assertIn("MX", usados, "no se leyó la tabla de verbos de valor")
        self.assertEqual(sorted(usados - self.tabla("DataColor", "OutName")), [],
                         "tipos de valor sin color: el cable saldría del gris neutro")
        self.assertEqual(sorted(usados - self.tabla("DataName", "Type")), [],
                         "tipos de valor sin nombre: el pin mostraría la letra del protocolo")

    def test_todo_tipo_COMPUESTO_tiene_su_coaccion(self):
        """Un tipo sin entrada en `COACCION` cae a `_numero`, que aplasta a un float cualquier cosa
        compuesta SIN AVISAR: un vector pierde dos componentes y una matriz catorce. Era una cadena
        de `if`/`elif` repetida en la entrada y en la salida, y olvidarse de un lado no falla."""
        faltan = sorted(t for t in self.tipos_de_los_verbos_de_valor()
                        if t not in ("N", "T") and t not in math_core.COACCION)
        self.assertEqual(faltan, [], "tipos compuestos que `_numero` aplastaría")

    def test_MX_no_le_pisa_el_codigo_a_ningun_tipo_que_ya_existia(self):
        self.assertEqual(math_core.tipo_salida("matrix_identity"), "MX")
        self.assertNotEqual(math_core.tipo_salida("matrix_identity"),
                            math_core.tipo_salida("vector_construct"))

    def test_el_color_de_la_matriz_es_de_la_FAMILIA_del_vector(self):
        """Mismo criterio que la familia ámbar (`N`/`N[]`/`D`): lo que separa a dos parientes es la
        luminosidad, no un tono nuevo. Una matriz es lo que le pasa a un vector."""
        editor = self.cpp("Source/JamEditor/Private/SJamGraphEditor.cpp")

        def color(tipo: str) -> tuple:
            m = re.search(r'OutName == TEXT\("' + re.escape(tipo)
                          + r'"\)\) \{ return FLinearColor\(([\d.]+)f, ([\d.]+)f, ([\d.]+)f',
                          editor)
            self.assertIsNotNone(m, f"no encontré el color de {tipo}")
            return tuple(float(x) for x in m.groups())

        v, mx = color("V"), color("MX")
        self.assertAlmostEqual(v[0], v[1], msg="el índigo del vector dejó de ser índigo")
        self.assertAlmostEqual(mx[0], mx[1], msg="la matriz se fue de la familia índigo")
        self.assertLess(sum(mx), sum(v), "la matriz tiene que ser el escalón OSCURO de la familia")


class EnElRibbonTests(unittest.TestCase):
    def test_los_once_verbos_tienen_grupo_y_ninguno_quedo_suelto(self):
        """Un verbo sin grupo cae al final del tab, lejos de sus parientes y sin que nada avise."""
        matrices = sorted(v for v in math_core.VALORES if v.startswith("matrix_"))
        self.assertEqual(len(matrices), 11)
        for verbo in matrices:
            with self.subTest(verbo=verbo):
                self.assertEqual(ribbon.grupo_de("Maths", verbo), "Matriz")

    def test_el_grupo_no_promete_verbos_que_no_existen(self):
        declarados = dict(ribbon.GRUPOS["Maths"])["Matriz"]
        self.assertEqual(sorted(set(declarados) - set(math_core.VALORES)), [])

    def test_cada_uno_lleva_su_propio_icono(self):
        mapa = json.loads((RAIZ / "Resources" / "Icons" / "Lucide"
                           / "icon-map.json").read_text(encoding="utf-8"))
        iconos = [mapa.get(v) for v in math_core.VALORES if v.startswith("matrix_")]
        self.assertNotIn(None, iconos, "un verbo sin icono cae al código corto")
        self.assertEqual(len(set(iconos)), len(iconos), "dos matrices con el mismo icono")

    def test_los_SVG_en_disco_son_los_que_produce_el_generador(self):
        """⚠️ Lo destapó una mutación que sobrevivió: cambiarle la CLAVE a un icono en el generador
        —de modo que uno se escriba dos veces y otro no se escriba nunca— dejaba todo en verde,
        porque el `.svg` viejo seguía en disco y el mapa lo seguía encontrando.

        `iconos_jam.py` es la fuente y los `.svg` son su salida commiteada; si se despegan, editar
        el generador deja de tener efecto y nadie se entera. Cubre los 157 que el generador
        declara: los que se escribieron a mano antes no son suyos y no se juzgan acá.
        """
        import importlib.util

        spec = importlib.util.spec_from_file_location("iconos_jam", RAIZ / "tools" / "iconos_jam.py")
        generador = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(generador)
        destino = RAIZ / "Resources" / "Icons" / "Lucide"
        self.assertIn("jam-matrix-decompose", generador.ICONOS,
                      "las matrices dejaron de salir del generador")
        distintos = [n for n, contenido in generador.ICONOS.items()
                     if not (destino / f"{n}.svg").exists()
                     or (destino / f"{n}.svg").read_text(encoding="utf-8") != contenido]
        self.assertEqual(distintos, [], "corré `python tools/iconos_jam.py`")

    def test_no_hay_dos_iconos_con_el_MISMO_dibujo(self):
        """El otro lado de lo mismo, y el que de verdad mata la mutación: si a un icono del
        generador le cambian la clave por la de otro, la salida se pisa y los dos verbos quedan con
        el dibujo idéntico. Los NOMBRES siguen siendo distintos, así que la unicidad por nombre no
        ve nada — en el ribbon, que sólo muestra el icono, son el mismo verbo.
        """
        import collections

        destino = RAIZ / "Resources" / "Icons" / "Lucide"
        por_dibujo = collections.defaultdict(list)
        for svg in sorted(destino.glob("jam-*.svg")):
            por_dibujo[svg.read_text(encoding="utf-8")].append(svg.stem)
        repetidos = sorted(v for v in por_dibujo.values() if len(v) > 1)
        self.assertEqual(repetidos, [], "estos verbos se ven idénticos en el ribbon")


class ElSpecQueLeeSlateTests(unittest.TestCase):
    def ficha(self, verbo: str) -> dict:
        for h in json.loads(api.spec_all())["tools"]:
            if h["verbo"] == verbo:
                return h
        self.fail(f"{verbo} no está en el spec")

    def test_las_cuatro_salidas_extra_viajan_en_el_spec(self):
        """La clave es `name`, la misma que `inputs`/`outputs`, para que el C++ las lea con el
        mismo `LeerPines`. Si no coincidiera, el parser no levantaría ningún pin y el nodo se
        dibujaría con un solo nub — sin error y sin log."""
        outs = self.ficha("matrix_decompose")["outs"]
        self.assertEqual([o["name"] for o in outs], ["escala", "eje_x", "eje_y", "eje_z"])
        for o in outs:
            self.assertEqual(set(o), {"name", "tipo", "label"})
            self.assertEqual(o["tipo"], "V")
            self.assertTrue(o["label"])

    def test_los_otros_diez_no_publican_salidas_extra(self):
        """El diseño es ADITIVO y ésa es toda su seguridad: un verbo sin `outs` se comporta
        exactamente como antes de que multi-salida existiera."""
        for verbo in math_core.VALORES:
            if verbo.startswith("matrix_") and verbo != "matrix_decompose":
                with self.subTest(verbo=verbo):
                    self.assertEqual(self.ficha(verbo)["outs"], [])

    def test_toda_etiqueta_de_param_entra_en_su_columna(self):
        """Una etiqueta más larga que la columna deja el campo con ancho cero: el control existe y
        es imposible de tocar. El ancho se lee del `.h` para que ensancharla relaje el test solo."""
        alto = (RAIZ / "Source" / "JamEditor" / "Public" / "SJamGraphNode.h").read_text(
            encoding="utf-8")
        ancho = float(re.search(r"ParamColW = ([\d.]+)f", alto).group(1))
        for verbo, meta in math_core.VALORES.items():
            if not verbo.startswith("matrix_"):
                continue
            for pin in meta["params"]:
                etiqueta = meta.get("etiquetas_params", {}).get(pin, pin)
                with self.subTest(verbo=verbo, pin=pin):
                    self.assertGreaterEqual(ancho - len(etiqueta) * 4, 24,
                                            f"«{etiqueta}» no deja lugar para su campo")


if __name__ == "__main__":
    unittest.main()
