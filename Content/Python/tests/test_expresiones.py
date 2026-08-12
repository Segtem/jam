"""Constantes con nombre en las expresiones, y por qué falla una que no resuelve.

Pedido de Brian: que anden `=radio * 2`, `= PI * 3`, `EULER`, `φ`, `= 5/9`. La aritmética y las
funciones ya andaban; faltaban las constantes en las grafías con que la gente las escribe —sólo
existían `pi` y `e` en minúscula— y, sobre todo, faltaba **decir qué salió mal**: `=PI * 3` y
`=radioo * 2` daban el MISMO mensaje, «expresión sin resolver», y con eso no se puede saber si el
error está en la idea o en una letra.
"""

from __future__ import annotations

import math
import sys
import types
import unittest

sys.modules.setdefault("unreal", types.ModuleType("unreal"))

from jam import flow, graph  # noqa: E402


class ConstantesTests(unittest.TestCase):
    def evaluar(self, expr, tabla=None):
        return flow._eval_expr(expr, tabla or {})

    def test_las_tres_grafias_son_la_misma_constante(self) -> None:
        """Quien viene de una calculadora escribe `PI`, quien viene de Python `pi`, y quien viene de
        un plano `π`. Ninguna es más correcta que las otras."""
        for grafias, esperado in (
                (("PI", "pi", "π"), math.pi),
                (("TAU", "tau", "τ"), math.tau),
                (("E", "e", "EULER", "euler"), math.e),
                (("PHI", "phi", "φ"), (1 + math.sqrt(5)) / 2)):
            for g in grafias:
                with self.subTest(grafia=g):
                    self.assertAlmostEqual(self.evaluar(g), esperado)

    def test_los_ejemplos_que_pidio_Brian(self) -> None:
        self.assertAlmostEqual(self.evaluar("radio * 2", {"radio": 21.0}), 42.0)
        self.assertAlmostEqual(self.evaluar("PI * 3"), math.pi * 3)
        self.assertAlmostEqual(self.evaluar("5/9"), 5 / 9)
        self.assertAlmostEqual(self.evaluar("φ * 100"), 161.8033988749895)

    def test_una_VARIABLE_del_grafo_le_gana_a_la_constante(self) -> None:
        """Lo que uno define en su propio grafo manda sobre lo que trae la herramienta. Al revés,
        alguien que llamara `PHI` a un número suyo vería otro valor sin entender por qué."""
        self.assertEqual(self.evaluar("PHI", {"PHI": 7.0}), 7.0)

    def test_phi_es_la_proporcion_aurea_y_no_otra_cosa(self) -> None:
        """φ² = φ + 1 la define; sin esa comprobación, cualquier número cerca de 1,6 pasaría."""
        phi = self.evaluar("PHI")
        self.assertAlmostEqual(phi * phi, phi + 1.0)

    def test_tau_es_dos_pi(self) -> None:
        self.assertAlmostEqual(self.evaluar("TAU"), self.evaluar("2 * PI"))


class DiagnosticoTests(unittest.TestCase):
    """La mitad que más se usa: qué dice cuando NO resuelve."""

    def diagnosticar(self, expr, tabla=None):
        return flow.diagnosticar_expresion(expr, tabla if tabla is not None else {"radio": 21.0})

    def test_un_nombre_desconocido_se_NOMBRA(self) -> None:
        self.assertIn("«radioo»", self.diagnosticar("radioo * 2"))

    def test_y_se_sugiere_el_parecido(self) -> None:
        """Es la diferencia entre «algo falló» y «te faltó una letra»."""
        self.assertIn("radio", self.diagnosticar("radioo * 2"))

    def test_sin_variables_dice_COMO_crear_una(self) -> None:
        """Un mensaje que sólo dice que algo no existe deja al usuario sin próximo paso."""
        mensaje = self.diagnosticar("altura * 2", {})
        self.assertIn("number", mensaje)

    def test_cada_falla_dice_lo_SUYO(self) -> None:
        casos = (("5/0", "división por cero"), ("2 +* 3", "no se entiende"),
                 ("sqrt(-1)", "número real"))
        for expr, esperado in casos:
            with self.subTest(expr=expr):
                self.assertIn(esperado, self.diagnosticar(expr))

    def test_una_expresion_que_ANDA_no_inventa_una_causa(self) -> None:
        """Devolver vacío es decir «acá no hay nada que explicar». Inventar una causa para algo que
        funciona es peor que no decir nada, porque manda a buscar un problema que no existe."""
        self.assertEqual(self.diagnosticar("PI * 3"), "")

    def test_el_diagnostico_espeja_al_evaluador(self) -> None:
        """Los dos hacen `float(eval(...))`. Sin el `float`, una expresión que da un complejo
        resolvería en el diagnóstico y fallaría en el evaluador, y el mensaje diría que está bien
        algo que no anda."""
        # `pow(-1, 0.5)` es la raíz de un negativo escrita como potencia: Python devuelve un
        # COMPLEJO y `float()` lo rechaza. Es la sonda correcta porque evalúa bien y sólo rompe al
        # convertir — con `complex(0,1)` el test pasaba por la razón equivocada, porque `complex`
        # ni siquiera existe en el espacio de nombres y fallaba en las dos versiones.
        self.assertIsNone(flow._eval_expr("pow(-1, 0.5)", {}))
        self.assertNotEqual(self.diagnosticar("pow(-1, 0.5)"), "")


class ElMensajeDelGrafoTests(unittest.TestCase):
    def resolver(self, texto, tabla=None):
        return graph._resolver_parametro(texto, 0.0, tabla or {"radio": 21.0})

    def test_las_constantes_ahora_resuelven_en_un_param(self) -> None:
        valor, error = self.resolver("=PI * 3")
        self.assertIsNone(error)
        self.assertAlmostEqual(valor, math.pi * 3)

    def test_el_error_del_param_LLEVA_la_causa(self) -> None:
        _valor, error = self.resolver("=radioo * 2")
        self.assertIn("expresión sin resolver", error)
        self.assertIn("no conozco «radioo»", error)

    def test_dos_fallas_distintas_dan_mensajes_distintos(self) -> None:
        """La regresión que importa: antes `=PI * 3` y `=radioo * 2` daban el mismo texto."""
        _v1, e1 = self.resolver("=radioo * 2")
        _v2, e2 = self.resolver("=5/0")
        self.assertNotEqual(e1, e2)

    def test_sin_el_igual_tambien_anda_en_un_campo_numerico(self) -> None:
        """Un campo numérico trata cualquier texto que no sea número como expresión, sin el «=»."""
        valor, error = self.resolver("PI * 2")
        self.assertIsNone(error)
        self.assertAlmostEqual(valor, math.tau)


if __name__ == "__main__":
    unittest.main()
