"""La consola no acepta verbos que no puede correr.

El hueco declarado: `dsl.py` lee `tools.REGISTRO` directo, así que la consola aceptaba los 166
verbos —incluidos los 86 que sólo tienen sentido con un cable— y `mesh_extrude` como comando suelto
terminaba en «biblioteca vacía» o en un error de tipo. Dos mensajes que mandan a buscar el problema
donde no está.

El corte se DERIVA de lo que el registro ya sabe (`min_inputs` + `in_name`) y no de una lista a
mano: etiquetar 166 verbos sería inventar 166 oportunidades de equivocarse, y el que agregue el 167
no se enteraría. Estos tests fijan el criterio y lo cruzan contra el REGISTRO REAL, que es donde un
criterio lindo se rompe.
"""

from __future__ import annotations

import sys
import types
import unittest

sys.modules.setdefault("unreal", types.ModuleType("unreal"))

from jam import dsl, registro_core, tools  # noqa: E402


class CableQueFaltaTests(unittest.TestCase):
    def test_sin_entradas_obligatorias_corre_en_la_consola(self):
        self.assertEqual(registro_core.cable_que_falta({"min_inputs": 0, "in_name": "P"}), "")

    def test_una_entrada_de_tipo_asset_se_puede_escribir(self):
        """`drop SM_Barrel` es una línea válida: un asset tiene nombre."""
        self.assertEqual(registro_core.cable_que_falta({"min_inputs": 1, "in_name": "A"}), "")

    def test_sin_tipo_de_entrada_tampoco_falta_nada(self):
        self.assertEqual(registro_core.cable_que_falta({"min_inputs": 1, "in_name": ""}), "")

    def test_una_malla_dinamica_no_se_puede_escribir(self):
        """Una `M` nace y muere adentro de una corrida del Graph: no hay nombre que tipear."""
        self.assertEqual(registro_core.cable_que_falta({"min_inputs": 1, "in_name": "M"}), "M")

    def test_devuelve_el_TIPO_y_no_un_booleano(self):
        """El mensaje al usuario nombra lo que falta; un `True` no alcanza para escribirlo."""
        self.assertEqual(registro_core.cable_que_falta({"min_inputs": 2, "in_name": "S"}), "S")

    def test_dos_cables_tambien_faltan(self):
        self.assertEqual(registro_core.cable_que_falta({"min_inputs": 2, "in_name": "M"}), "M")

    def test_un_registro_incompleto_no_revienta(self):
        """Una entrada a medio declarar tiene que dejar pasar, no tirar: la consola no es el lugar
        donde se descubre que falta un campo — para eso está `auditar`."""
        self.assertEqual(registro_core.cable_que_falta({}), "")
        self.assertEqual(registro_core.cable_que_falta({"min_inputs": None, "in_name": None}), "")

    def test_corre_en_consola_es_la_negacion(self):
        self.assertTrue(registro_core.corre_en_consola({"min_inputs": 1, "in_name": "A"}))
        self.assertFalse(registro_core.corre_en_consola({"min_inputs": 1, "in_name": "M"}))


class ContraElRegistroRealTests(unittest.TestCase):
    """Un criterio se rompe contra los datos de verdad, no contra los tres casos que uno inventó."""

    def falta(self, verbo):
        return registro_core.cable_que_falta(tools.REGISTRO[verbo])

    def test_los_verbos_de_la_consola_siguen_corriendo(self):
        """La regresión que más importa: si esto se rompe, la consola deja de servir."""
        for verbo in ("place", "drop", "spline", "scatter", "pick", "asset", "mesh_from_asset"):
            with self.subTest(verbo=verbo):
                self.assertEqual(self.falta(verbo), "",
                                 f"«{verbo}» es un comando de toda la vida y quedó afuera")

    def test_scatter_pasa_aunque_su_entrada_sea_P(self):
        """Su entrada de puntos es OPCIONAL (`min_inputs` 0): sin cable reparte en un área. Es el
        caso que un criterio basado sólo en el TIPO de entrada habría roto."""
        self.assertEqual(tools.REGISTRO["scatter"]["in_name"], "P")
        self.assertEqual(self.falta("scatter"), "")

    def test_los_verbos_de_grafo_quedan_afuera_con_su_tipo(self):
        for verbo, tipo in (("mesh_extrude", "M"), ("mesh_ribbon", "S"), ("mesh_merge", "M")):
            with self.subTest(verbo=verbo):
                self.assertEqual(self.falta(verbo), tipo)

    def test_el_corte_parte_el_registro_en_dos_grupos_no_vacios(self):
        """Si un día todo cae de un lado, el criterio dejó de discriminar y nadie se entera."""
        corren = [n for n, i in tools.REGISTRO.items() if registro_core.corre_en_consola(i)]
        no = [n for n, i in tools.REGISTRO.items() if not registro_core.corre_en_consola(i)]
        self.assertGreater(len(corren), 20, "casi nada corre en la consola: el criterio se pasó")
        self.assertGreater(len(no), 20, "casi todo corre en la consola: el criterio no ataja nada")


class AssetComoEntradaTests(unittest.TestCase):
    """A dónde va el token suelto de la línea. Un bug que la sonda del camino real destapó: la
    consola le pasaba el asset a `scatter` en el slot de PUNTOS, y como es un string el verbo lo
    iteraba letra por letra («'str' object has no attribute 'pos'»). Era el ejemplo que encabeza el
    docstring del DSL."""

    def test_un_slot_de_asset_lo_recibe(self):
        self.assertTrue(registro_core.acepta_asset_como_entrada({"in_name": "A"}))

    def test_un_verbo_sin_entrada_lo_recibe(self):
        """`asset SM_Rock` no declara entrada y necesita el nombre igual: sacárselo lo rompería."""
        self.assertTrue(registro_core.acepta_asset_como_entrada({"in_name": ""}))

    def test_un_slot_de_puntos_NO_lo_recibe(self):
        self.assertFalse(registro_core.acepta_asset_como_entrada({"in_name": "P"}))

    def test_scatter_contra_el_registro_real(self):
        """El caso exacto que explotaba."""
        self.assertFalse(registro_core.acepta_asset_como_entrada(tools.REGISTRO["scatter"]))

    def test_los_comandos_de_asset_contra_el_registro_real(self):
        """Y la regresión del otro lado: si dejaran de recibirlo, `drop SM_Barrel` deja de colocar
        lo que se le pidió y coloca cualquier cosa."""
        for verbo in ("drop", "place", "asset", "spline"):
            with self.subTest(verbo=verbo):
                self.assertTrue(
                    registro_core.acepta_asset_como_entrada(tools.REGISTRO[verbo]),
                    f"«{verbo}» dejó de recibir el asset que se le escribe")


class AyudaTests(unittest.TestCase):
    def test_no_ofrece_lo_que_no_anda(self):
        texto = dsl.ayuda()
        self.assertNotIn("mesh_extrude", texto)
        self.assertNotIn("mesh_ribbon", texto)

    def test_sigue_ofreciendo_lo_que_si_anda(self):
        texto = dsl.ayuda()
        for verbo in ("drop", "scatter"):
            with self.subTest(verbo=verbo):
                self.assertIn(verbo, texto)

    def test_dice_que_los_otros_existen_y_donde(self):
        """Esconderlos sin decirlo sería contestar que no existen, que es otra mentira."""
        texto = dsl.ayuda()
        self.assertIn("Graph", texto)
        self.assertRegex(texto, r"\(\d+ verbos más viven sólo en el Graph")


if __name__ == "__main__":
    unittest.main()
