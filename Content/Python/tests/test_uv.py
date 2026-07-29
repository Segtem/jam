"""El veredicto de un desplegado de UVs: que los números signifiquen lo que dicen.

Unas UVs no se juzgan mirando el checker. Se juzgan por tres cosas medibles, y la parte delicada no
es medirlas sino REDACTARLAS sin mentir — la primera versión de esta métrica informaba «100% del
atlas usado» justo en el caso peor (una proyección cúbica con las seis caras encimadas), porque
medía la caja que ocupan las islas en vez de lo que cubren.

Las funciones que tocan Unreal se verifican en `tools/experiments/verifica_uv_procedural.py`; acá
está la lógica del veredicto, que es pura.
"""

from __future__ import annotations

import sys
import types
import unittest

sys.modules.setdefault("unreal", types.ModuleType("unreal"))

from jam import mesh  # noqa: E402


def medida(**cambios) -> dict:
    base = {"valido": True, "sin_uv": False, "area_malla": 10000.0, "area_uv": 0.6,
            "densidad": 0.77, "cobertura": 0.85, "caja": (0.9, 0.8), "dentro_01": True}
    base.update(cambios)
    return base


class VeredictoTests(unittest.TestCase):
    def test_a_good_unwrap_reads_as_good(self):
        texto = mesh._veredicto_uv(medida(), 0)
        self.assertIn("85%", texto)
        self.assertNotIn("⚠", texto)

    def test_overlapping_islands_are_reported_as_a_defect(self):
        """El caso que la primera métrica daba por bueno: una proyección cúbica apila las seis caras
        en el mismo cuadrado. La caja da 1×1 —parece lleno— y en realidad está todo encimado, que
        rompe lightmaps y horneados."""
        texto = mesh._veredicto_uv(medida(cobertura=5.1), 0)
        self.assertIn("ENCIMADAS", texto)
        self.assertIn("5.1", texto)
        self.assertNotIn("aprovechado", texto,
                         "no se puede hablar de aprovechamiento cuando las islas se pisan")

    def test_uvs_outside_the_unit_square_are_reported(self):
        """Afuera del 0..1 la textura se repite: sirve para tileado, no para un atlas ni para
        hornear. Es una decisión, pero tiene que ser una decisión y no una sorpresa."""
        self.assertIn("se sale del 0..1", mesh._veredicto_uv(medida(dentro_01=False), 0))

    def test_triangles_without_uvs_are_reported(self):
        self.assertIn("SIN UV", mesh._veredicto_uv(medida(sin_uv=True), 0))

    def test_a_channel_that_does_not_exist_says_so(self):
        texto = mesh._veredicto_uv(medida(valido=False), 3)
        self.assertIn("UV3", texto)
        self.assertIn("NO existe", texto)

    def test_an_empty_channel_is_not_the_same_as_a_missing_one(self):
        """Distinguirlos importa: un canal que no existe se crea; uno vacío está creado y sin
        proyectar, que es un paso olvidado en la cadena."""
        vacio = mesh._veredicto_uv(medida(area_uv=0.0), 2)
        self.assertIn("VACÍO", vacio)
        self.assertNotIn("NO existe", vacio)

    def test_every_problem_shows_up_together(self):
        """Los avisos no se pisan entre sí: un desplegado puede estar mal de varias formas a la vez
        y quien lo lea tiene que enterarse de todas, no de la primera."""
        texto = mesh._veredicto_uv(medida(cobertura=3.0, dentro_01=False, sin_uv=True), 0)
        for esperado in ("ENCIMADAS", "se sale del 0..1", "SIN UV"):
            self.assertIn(esperado, texto)


class MetricaTests(unittest.TestCase):
    """La cuenta, separada de Unreal justamente para poder probarla."""

    def test_stacked_islands_measure_above_one(self):
        """Una proyección cúbica apila las seis caras en el mismo cuadrado: el área de triángulos
        supera la de la caja. Medido en el editor sobre una escalera: 5.1×."""
        m = mesh._metrica_uv(10000.0, 5.1, (0.0, 0.0), (1.0, 1.0), True, False)
        self.assertGreater(m["cobertura"], 1.0)

    def test_a_well_packed_layout_measures_just_under_one(self):
        m = mesh._metrica_uv(10000.0, 0.84, (0.0, 0.0), (1.0, 1.0), True, False)
        self.assertAlmostEqual(m["cobertura"], 0.84, places=6)

    def test_coverage_is_area_over_box_and_not_the_box_itself(self):
        """El bug original: medir la caja y llamarla «aprovechado». Con la caja llena y las islas
        ocupando una décima parte, la respuesta correcta es 10%, no 100%."""
        m = mesh._metrica_uv(10000.0, 0.1, (0.0, 0.0), (1.0, 1.0), True, False)
        self.assertAlmostEqual(m["cobertura"], 0.1, places=6)
        self.assertNotAlmostEqual(m["cobertura"], 1.0, places=3)

    def test_density_is_linear_and_not_areal(self):
        """Lo que se compara al mirar un checker son LADOS. Cuatro veces el área UV es el doble de
        densidad lineal, no el cuádruple."""
        poca = mesh._metrica_uv(10000.0, 1.0, (0.0, 0.0), (1.0, 1.0), True, False)
        mucha = mesh._metrica_uv(10000.0, 4.0, (0.0, 0.0), (1.0, 1.0), True, False)
        self.assertAlmostEqual(mucha["densidad"] / poca["densidad"], 2.0, places=6)

    def test_a_box_outside_the_unit_square_is_detected(self):
        self.assertFalse(mesh._metrica_uv(1.0, 0.5, (-0.2, 0.0), (1.0, 1.0), True, False)["dentro_01"])
        self.assertFalse(mesh._metrica_uv(1.0, 0.5, (0.0, 0.0), (1.4, 1.0), True, False)["dentro_01"])
        self.assertTrue(mesh._metrica_uv(1.0, 0.5, (0.0, 0.0), (1.0, 1.0), True, False)["dentro_01"])

    def test_a_degenerate_box_does_not_divide_by_zero(self):
        """Un canal vacío da caja de área cero. Sin la guarda, medir un desplegado que no existe
        tira una excepción en vez de un veredicto."""
        m = mesh._metrica_uv(10000.0, 0.0, (0.0, 0.0), (0.0, 0.0), True, True)
        self.assertEqual(m["cobertura"], 0.0)
        self.assertEqual(m["densidad"], 0.0)


class RegistroTests(unittest.TestCase):
    def test_the_three_uv_verbs_take_and_return_a_mesh(self):
        from jam import tools

        for verbo in ("mesh_uv_box", "mesh_uv_unwrap", "mesh_uv_pack"):
            self.assertEqual(tools.REGISTRO[verbo]["in_name"], "M", verbo)
            self.assertEqual(tools.REGISTRO[verbo]["out_name"], "M", verbo)

    def test_the_unwrap_methods_offered_are_the_ones_the_engine_has(self):
        """Los tres del enum `GeometryScriptUVFlattenMethod`, medidos: si el desplegable ofreciera
        otro, el verbo fallaría recién al correr."""
        from jam import tools

        self.assertEqual(sorted(tools.REGISTRO["mesh_uv_unwrap"]["opciones"]["method"]),
                         ["conformal", "exp_map", "spectral_conformal"])


if __name__ == "__main__":
    unittest.main()
