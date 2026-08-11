"""El almacén de resultados: qué se reusa, qué se tira y qué NUNCA se devuelve.

La parte peligrosa del caché no es guardar: es devolver. Un resultado viejo entregado «por las
dudas» se ve como «a veces el muro sale mal», que es el peor síntoma posible para depurar.
"""

from __future__ import annotations

import sys
import types
import unittest

sys.modules.setdefault("unreal", types.ModuleType("unreal"))

from jam.cache import Almacen  # noqa: E402


class AlmacenTests(unittest.TestCase):
    def test_guarda_y_devuelve_por_huella_exacta(self):
        a = Almacen()
        a.guardar("h1", "malla")
        self.assertEqual(a.obtener("h1"), "malla")

    def test_una_huella_distinta_es_un_fallo_y_no_un_parecido(self):
        """Si la huella no coincide exacto, se recocina. Nunca «lo más parecido»."""
        a = Almacen()
        a.guardar("h1", "malla")
        self.assertIsNone(a.obtener("h2"))

    def test_no_guarda_resultados_nulos(self):
        """`None` significa «no lo tengo». Guardar un nulo lo volvería ambiguo."""
        a = Almacen()
        a.guardar("h1", None)
        self.assertEqual(a.tamano, 0)

    def test_desaloja_el_menos_usado_recientemente(self):
        """Sin tope, una sesión larga de live view se come la memoria y el editor muere por una
        causa que nadie va a relacionar con esto."""
        a = Almacen(capacidad=2)
        a.guardar("h1", 1)
        a.guardar("h2", 2)
        a.obtener("h1")          # h1 pasa a ser el más reciente
        a.guardar("h3", 3)       # desaloja h2
        self.assertIsNotNone(a.obtener("h1"))
        self.assertIsNone(a.obtener("h2"))
        self.assertIsNotNone(a.obtener("h3"))

    def test_respeta_la_capacidad(self):
        a = Almacen(capacidad=3)
        for i in range(10):
            a.guardar(f"h{i}", i)
        self.assertEqual(a.tamano, 3)

    def test_una_capacidad_absurda_es_un_error_y_no_un_cero_silencioso(self):
        with self.assertRaises(ValueError):
            Almacen(capacidad=0)

    def test_invalidar_dice_cuantas_habia(self):
        a = Almacen()
        a.guardar("h1", 1)
        a.guardar("h2", 2)
        self.assertEqual(a.invalidar(["h1", "h9"]), 1)
        self.assertIsNone(a.obtener("h1"))

    def test_el_plan_separa_lo_que_se_reusa_de_lo_que_hay_que_cocinar(self):
        """Se calcula ANTES de tocar el motor, para poder mostrar «8 de 11 reusados» en vez de que
        el ahorro sea una mejora invisible que nadie sabe si funciona."""
        a = Almacen()
        a.guardar("hb", "malla")
        plan = a.plan({"a": "ha", "b": "hb", "c": "hc"})
        self.assertEqual(plan, {"reusa": ["b"], "cocina": ["a", "c"]})

    def test_las_estadisticas_cuentan_aciertos_y_fallos(self):
        a = Almacen()
        a.guardar("h1", 1)
        a.obtener("h1")
        a.obtener("h2")
        e = a.estadisticas()
        self.assertEqual((e["aciertos"], e["fallos"]), (1, 1))
        self.assertAlmostEqual(e["tasa"], 0.5)

    def test_limpiar_lo_deja_vacio(self):
        """Un Bake no puede arrastrar restos del Preview anterior."""
        a = Almacen()
        a.guardar("h1", 1)
        a.limpiar()
        self.assertEqual(a.tamano, 0)


class QueSePuedeReusarTests(unittest.TestCase):
    """La pregunta NO es «¿es puro?» sino «¿saltearlo deja el mundo igual?».

    Un verbo que spawnea actores puede devolver el mismo dato dos veces y aun así no se lo puede
    saltear: la segunda corrida tiene que volver a poner los actores.
    """

    def test_una_malla_transitoria_del_canvas_se_reusa(self):
        from jam import cache_core

        self.assertTrue(cache_core.es_cacheable({"out_name": "M", "graph_only": True}))

    def test_una_salida_de_dato_NO_alcanza_si_el_verbo_toca_la_escena(self):
        """Lo encontró este mismo test contra el registro real: `scatter` produce puntos Y spawnea.
        Reusarlo devolvería los mismos puntos y dejaría la escena vacía."""
        from jam import cache_core

        self.assertFalse(cache_core.es_cacheable({"out_name": "P"}))

    def test_un_verbo_que_produce_un_asset_no(self):
        """Escribir en Content es un efecto: reusarlo saltearía la escritura."""
        from jam import cache_core

        self.assertFalse(cache_core.es_cacheable({"out_name": "A"}))

    def test_un_verbo_sin_salida_de_dato_no(self):
        """`place` y compañía dejan actores en el nivel; saltearlos los haría desaparecer."""
        from jam import cache_core

        self.assertFalse(cache_core.es_cacheable({"out_name": ""}))

    def test_los_verbos_reales_de_geometria_son_cacheables(self):
        """Contra el registro de verdad, no contra un dict inventado."""
        from jam import cache_core, tools

        for verbo in ("mesh_ribbon", "mesh_extrude", "curve_bezier"):
            with self.subTest(verbo=verbo):
                self.assertTrue(cache_core.es_cacheable(tools.REGISTRO[verbo]))

    def test_los_verbos_reales_que_tocan_la_escena_no(self):
        from jam import cache_core, tools

        for verbo in ("place", "drop", "scatter"):
            with self.subTest(verbo=verbo):
                self.assertFalse(cache_core.es_cacheable(tools.REGISTRO[verbo]))


class IntegracionConElEjecutorTests(unittest.TestCase):
    def test_el_ejecutor_sigue_igual_sin_almacen(self):
        """La integración es opt-in: sin almacén, el camino real no cambia en nada."""
        import inspect

        from jam import graph

        firma = inspect.signature(graph.ejecutar_detalle)
        self.assertIsNone(firma.parameters["almacen"].default)

    def test_no_se_cachea_un_nodo_que_fallo(self):
        """Cachear un error lo volvería permanente hasta que alguien cambie un parámetro, y el
        usuario vería el mismo fallo sin entender por qué."""
        from pathlib import Path

        fuente = (Path(__file__).resolve().parents[1] / "jam" / "graph.py").read_text(
            encoding="utf-8")
        i = fuente.index("almacen.guardar(huella_nodo")
        contexto = fuente[max(0, i - 400):i]
        self.assertIn('estado != "error"', contexto)
