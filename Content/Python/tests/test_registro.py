"""Dónde se ve cada tool, y si su declaración está entera.

El relevamiento de 2026-08-11 encontró que la superficie se decidía en NEGATIVO (`graph_only`,
puesto en 93 de 113 entradas): una tool nueva aparecía en la Dash Bar por olvido y no por decisión.
Estos tests fijan el contrato nuevo y miden la deuda del registro sin frenar el trabajo.
"""

from __future__ import annotations

import sys
import types
import unittest

sys.modules.setdefault("unreal", types.ModuleType("unreal"))

from jam import registro_core  # noqa: E402


class SuperficiesTests(unittest.TestCase):
    def test_lo_declarado_gana(self):
        self.assertEqual(registro_core.superficies_de({"superficies": ("dash",)}),
                         frozenset({"dash"}))

    def test_sin_declarar_se_deriva_del_viejo_graph_only(self):
        """Las 111 tools sin migrar tienen que seguir viéndose donde se veían. Sin esto la
        migración necesitaría una ventana con el ribbon a medias."""
        self.assertEqual(registro_core.superficies_de({"graph_only": True}), frozenset({"graph"}))
        self.assertEqual(registro_core.superficies_de({}), frozenset({"dash", "graph"}))

    def test_lo_declarado_le_gana_a_graph_only(self):
        """Durante la migración las dos formas conviven; si se contradicen, manda la explícita."""
        self.assertEqual(
            registro_core.superficies_de({"graph_only": True, "superficies": ("dash", "graph")}),
            frozenset({"dash", "graph"}))


class AuditoriaDelRegistroTests(unittest.TestCase):
    def sano(self) -> dict:
        return {"t": {"label": "Una tool", "cat": "Place", "doc": "hace algo",
                      "superficies": ("dash",), "params": {"x": 0.0}}}

    def test_un_registro_sano_no_tiene_defectos(self):
        self.assertEqual(registro_core.auditar(self.sano(), categorias_ribbon={"Place"}), [])

    def test_detecta_la_tool_sin_nombre_visible(self):
        r = self.sano()
        del r["t"]["label"]
        self.assertIn("sin `label`", " ".join(registro_core.auditar(r)))

    def test_detecta_la_que_no_se_ve_en_ningun_lado(self):
        r = self.sano()
        r["t"]["superficies"] = ()
        self.assertIn("no se ve en ningún lado", " ".join(registro_core.auditar(r)))

    def test_detecta_la_superficie_inventada(self):
        r = self.sano()
        r["t"]["superficies"] = ("barra_lateral",)
        self.assertIn("superficie desconocida", " ".join(registro_core.auditar(r)))

    def test_detecta_la_categoria_que_el_ribbon_no_conoce(self):
        """Cae en un bloque sin etiqueta y nadie se entera hasta abrir la barra."""
        r = self.sano()
        r["t"]["cat"] = "Inventada"
        self.assertIn("no existe en el ribbon",
                      " ".join(registro_core.auditar(r, categorias_ribbon={"Place"})))

    def test_detecta_el_dominio_sobre_un_parametro_que_no_existe(self):
        """Un dropdown declarado sobre un param inexistente no se dibuja nunca."""
        r = self.sano()
        r["t"]["opciones"] = {"anchor": ["base"]}
        self.assertIn("que no es un parámetro", " ".join(registro_core.auditar(r)))

    def test_detecta_el_tipo_de_pin_desconocido(self):
        r = self.sano()
        r["t"]["params"]["puntos"] = ""
        r["t"]["data_params"] = {"puntos": "Z"}
        self.assertIn("tipo desconocido",
                      " ".join(registro_core.auditar(r, tipos_conocidos={"P", "A"})))


class ElRegistroRealTests(unittest.TestCase):
    """Mide el registro de verdad. NO exige que esté sano todavía: son 113 entradas y arreglarlas
    de golpe sería un cambio enorme sin verificación. Lo que se fija es que la deuda NO CREZCA, que
    es lo que convierte una migración larga en algo que termina."""

    def registro(self):
        from jam import tools

        return tools.REGISTRO

    def test_las_physics_tools_declaran_su_superficie_y_su_nombre(self):
        """El primer target de la migración: son el equivalente del Physics Drop y el Physics Paint
        que Dash pone en su barra bajo Place."""
        registro = self.registro()
        for verbo, etiqueta in (("drop", "Soltar con física"), ("brush", "Pincel de reparto")):
            with self.subTest(verbo=verbo):
                info = registro[verbo]
                self.assertEqual(info.get("label"), etiqueta)
                self.assertIn("dash", registro_core.superficies_de(info))
                self.assertIn("graph", registro_core.superficies_de(info))

    def test_el_pincel_llega_a_la_dash_bar(self):
        """Estaba `graph_only`: el pincel existía en el canvas y no en la barra, mientras Dash sí
        expone su Physics Paint ahí. Es el caso que motivó el relevamiento."""
        import json

        from jam import tools

        barra = json.loads(tools.spec_json())["tools"]
        nombres = {t["verbo"] for t in barra}
        self.assertIn("brush", nombres)
        self.assertIn("drop", nombres)

    def test_la_deuda_de_declaracion_no_crece(self):
        """Cero desde el 2026-09-30 (tarea `labels-tools`): el 2026-08-11 eran 136, y los 136 eran
        `sin label` —categorías, docs, dominios y tipos de pin estaban sanos; la deuda eran los nombres
        visibles, justo lo que se lee en la barra—. Los pusieron agy1, agy2 y Codex, cada uno sobre
        una parte del registro, revisados sin duplicados y sin tocar otro campo.

        Si este test se pone rojo por una tool NUEVA, la tool está incompleta: no le falta al test,
        le falta a la tool.
        """
        from jam import ribbon

        categorias = {cat for _, cats in ribbon.SECCIONES for cat in cats}
        defectos = registro_core.auditar(self.registro(), categorias_ribbon=categorias)
        self.assertEqual(
            len(defectos), 0,
            "creció la deuda de declaración del registro:\n  " + "\n  ".join(defectos[:20]))


if __name__ == "__main__":
    unittest.main()
