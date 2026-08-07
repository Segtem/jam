"""El oráculo mide la tanda Y la escena. El segundo chequeo es el que faltaba.

Medir la propia tanda y llamarlo veredicto es el oráculo haciéndose trampa al solitario: dos scatter
seguidos con los mismos parámetros caen exactamente uno encima del otro, y cada uno informa
«REPARTO SANO · 0 clavados» —porque dentro de cada tanda, efectivamente, nadie se pisa—.

No es un error: colocar encima de algo puede ser lo que uno quiere. Por eso sale como AVISO
(amarillo), un escalón entre «✓ salió bien» y «✗ revisá esto».
"""

from __future__ import annotations

import sys
import types
import unittest

sys.modules.setdefault("unreal", types.ModuleType("unreal"))

from jam import graph, oracle_scatter  # noqa: E402
from jam.geometry import AABB, Pieza, Vec3  # noqa: E402


def pieza(nombre: str, x: float, y: float, radio: float = 50.0) -> Pieza:
    return Pieza(nombre, AABB(Vec3(x, y, 0.0), Vec3(radio, radio, radio)),
                 Vec3(x, y, 0.0), 0.0)


def tanda(prefijo: str, xs) -> list:
    return [pieza(f"{prefijo}{i}", x, 0.0) for i, x in enumerate(xs)]


class ContraLaEscenaTests(unittest.TestCase):
    def test_two_identical_batches_are_reported_as_stacked(self):
        """EL BUG: dos scatter con los mismos parámetros dan las mismas posiciones. La tanda sola
        dice que está perfecta; el segundo chequeo tiene que delatar que está toda encima."""
        primera = tanda("a", [0.0, 300.0, 600.0])
        segunda = tanda("b", [0.0, 300.0, 600.0])
        r = oracle_scatter.contra_la_escena(segunda, primera)
        self.assertEqual(len(r["pisadas"]), 3)
        self.assertEqual(r["limpias"], 0)

    def test_the_batch_check_alone_says_everything_is_fine(self):
        """La prueba de que el segundo chequeo hacía falta: sobre la MISMA situación, el oráculo de
        la tanda no tiene nada que objetar."""
        segunda = tanda("b", [0.0, 300.0, 600.0])
        r = oracle_scatter.verificar(segunda, (300.0, 0.0), (400.0, 400.0), 3, cobertura_min=0.0)
        self.assertEqual(r["interpenetra"], [], "dentro de su tanda nadie se pisa: por eso mentía")

    def test_a_batch_that_lands_in_free_space_reports_clean(self):
        lejos = tanda("b", [5000.0, 5300.0])
        r = oracle_scatter.contra_la_escena(lejos, tanda("a", [0.0, 300.0]))
        self.assertEqual(r["pisadas"], [])
        self.assertEqual(r["limpias"], 2)

    def test_each_new_piece_is_counted_once_even_if_it_hits_several(self):
        """Lo que importa es CUÁNTAS piezas nuevas pisan algo, no cuántos pares hay: con «3 de 12
        pisados» se decide; con «17 pares» no."""
        vieja = [pieza("v1", 0.0, 0.0), pieza("v2", 40.0, 0.0), pieza("v3", 80.0, 0.0)]
        r = oracle_scatter.contra_la_escena([pieza("nueva", 40.0, 0.0)], vieja)
        self.assertEqual(len(r["pisadas"]), 1)

    def test_with_nothing_in_the_scene_there_is_no_second_verdict(self):
        """Sin nada con qué chocar, el renglón no se escribe: un veredicto que siempre dice lo mismo
        deja de leerse."""
        r = oracle_scatter.contra_la_escena(tanda("b", [0.0]), [])
        self.assertEqual(oracle_scatter.texto_contra_la_escena(r, 1), "")


class TextoTests(unittest.TestCase):
    def test_the_warning_says_the_two_numbers_that_matter(self):
        r = oracle_scatter.contra_la_escena(tanda("b", [0.0, 300.0]), tanda("a", [0.0, 300.0]))
        texto = oracle_scatter.texto_contra_la_escena(r, 2)
        self.assertIn("2 colocados", texto)
        self.assertIn("2 pisados contra lo que ya estaba", texto)

    def test_the_warning_carries_the_symbol_that_paints_it_yellow(self):
        """El símbolo lo pone el ORÁCULO, no el ejecutor: quien sabe si algo es «indeseado pero
        aceptable» es quien midió."""
        r = oracle_scatter.contra_la_escena(tanda("b", [0.0]), tanda("a", [0.0]))
        self.assertIn(graph.AVISO, oracle_scatter.texto_contra_la_escena(r, 1))

    def test_a_clean_landing_is_reported_as_a_tick_and_not_as_a_warning(self):
        r = oracle_scatter.contra_la_escena(tanda("b", [9000.0]), tanda("a", [0.0]))
        texto = oracle_scatter.texto_contra_la_escena(r, 1)
        self.assertIn("✓", texto)
        self.assertNotIn(graph.AVISO, texto)


class EstadoTests(unittest.TestCase):
    """El escalón AMARILLO: entre «salió bien» y «revisá esto»."""

    def test_a_warning_paints_the_node_yellow(self):
        self.assertEqual(graph._estado(f"SCATTER ✓ — 12 colocados\n  {graph.AVISO} 12 pisados"),
                         "aviso")

    def test_yellow_wins_over_the_tick(self):
        """Un texto trae las dos cosas: el verbo hizo lo suyo Y hay algo que mirar. Si ganara el ✓,
        el aviso se pintaría de VERDE y sería justamente lo que hacía falta ver."""
        self.assertEqual(graph._estado(f"✓ todo bien {graph.AVISO} pero mirá esto"), "aviso")

    def test_the_oracle_saying_REVISAR_still_wins_over_yellow(self):
        """Naranja es «el resultado NO sirve»; amarillo es «sirve, pero costó algo». Si el amarillo
        tapara al naranja, un reparto roto se vería como uno aceptable."""
        self.assertEqual(graph._estado(f"✗ cobertura insuficiente {graph.AVISO} y además pisa"),
                         "warn")

    def test_an_error_still_wins_over_everything(self):
        self.assertEqual(graph._estado(f"[error] reventó {graph.AVISO} ✓"), "error")

    def test_a_clean_run_is_still_green(self):
        self.assertEqual(graph._estado("SCATTER ✓ — 12 colocados, ninguno pisa nada"), "ok")


if __name__ == "__main__":
    unittest.main()


class LaEscenografiaDeFondoNoCuentaTests(unittest.TestCase):
    """La SkySphere envuelve el mapa, así que TODA pieza colocada está «adentro» de ella.

    Sin filtrarla el aviso saltaba 24 de 24 veces, con penetraciones de 16 km contra
    `SM_SkySphere`. Un aviso que salta siempre no lo lee nadie: deja de distinguir el caso que
    importa —haber colocado encima de algo real— del ruido.

    `oracle_placement.verificar` ya aplicaba este filtro. Faltaba acá; no es una regla nueva.
    """

    @staticmethod
    def _cielo() -> Pieza:
        # Semi-extensión de 1 km por lado: muy por encima de `geometry.MAX_VECINO_CM` (500 m).
        return Pieza("SM_SkySphere",
                     AABB(Vec3(0.0, 0.0, 0.0), Vec3(100000.0, 100000.0, 100000.0)),
                     Vec3(0.0, 0.0, 0.0), 0.0)

    def test_the_sky_sphere_does_not_count_as_something_stepped_on(self):
        r = oracle_scatter.contra_la_escena(tanda("nueva", [0.0, 300.0, 600.0]), [self._cielo()])
        self.assertEqual(r["pisadas"], [],
                         "el cielo envuelve todo; pisarlo no significa nada")
        self.assertEqual(r["limpias"], 3)

    def test_the_sky_is_not_counted_as_a_neighbour_either(self):
        """«0 pisados (1 pieza en la zona)» contando el cielo sería igual de engañoso."""
        r = oracle_scatter.contra_la_escena(tanda("nueva", [0.0]), [self._cielo()])
        self.assertEqual(r["existentes"], 0)

    def test_a_real_neighbour_is_still_caught_with_the_sky_present(self):
        """El filtro no puede tapar lo que sí importa: con cielo Y un vecino real, delata el real."""
        vecino = pieza("caja_que_ya_estaba", 40.0, 0.0)
        r = oracle_scatter.contra_la_escena([pieza("nueva", 0.0, 0.0)], [self._cielo(), vecino])
        self.assertEqual([p[1] for p in r["pisadas"]], ["caja_que_ya_estaba"])
        self.assertEqual(r["existentes"], 1)

    def test_it_reuses_the_background_rule_instead_of_a_second_threshold(self):
        """Un segundo umbral escrito acá se separaría del de `geometry` sin que nadie lo note."""
        import inspect

        from jam import geometry
        fuente = inspect.getsource(oracle_scatter.contra_la_escena)
        self.assertIn("geometry.es_fondo(", fuente)
        self.assertNotIn(str(geometry.MAX_VECINO_CM), fuente,
                         "el umbral tiene que vivir en `geometry`, no copiado acá")
