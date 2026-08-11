"""Qué se puede reusar de una cocción anterior y qué hay que rehacer.

Medido en UE 5.8.1: compilar cuesta 0,1–0,3 ms y correr 167–498 ms. El caché no es del compile —que
ya es gratis— sino de los resultados del motor. Estos tests fijan el criterio de reuso, que es la
parte peligrosa: un caché que devuelve un resultado viejo es un bug silencioso y carísimo.
"""

from __future__ import annotations

import sys
import types
import unittest

sys.modules.setdefault("unreal", types.ModuleType("unreal"))

from jam import cache_core  # noqa: E402


def cadena():
    nodos = {"a": {"verb": "curve_bezier", "params": {"segments": "12"}},
             "b": {"verb": "mesh_ribbon", "params": {"width": "360"}},
             "c": {"verb": "mesh_to_static", "params": {}}}
    return nodos, [["a", "out", "b", "in"], ["b", "out", "c", "in"]]


class HuellaTests(unittest.TestCase):
    def test_lo_mismo_da_la_misma_huella(self):
        self.assertEqual(cache_core.huella("x", {"a": 1}, []), cache_core.huella("x", {"a": 1}, []))

    def test_el_numero_y_su_texto_son_lo_mismo(self):
        """El canvas manda «20» y un archivo manda 20. Dos huellas distintas para el mismo grafo
        harían que el caché falle justo cuando más se lo necesita."""
        self.assertEqual(cache_core.huella("x", {"n": 20}, []), cache_core.huella("x", {"n": "20"}, []))

    def test_cambiar_un_param_cambia_la_huella(self):
        self.assertNotEqual(cache_core.huella("x", {"a": 1}, []), cache_core.huella("x", {"a": 2}, []))

    def test_cambiar_la_entrada_cambia_la_huella(self):
        """Es lo que hace que ensuciar se propague solo, sin recorrer el grafo a mano."""
        self.assertNotEqual(cache_core.huella("x", {}, ["h1"]), cache_core.huella("x", {}, ["h2"]))


class PropagacionTests(unittest.TestCase):
    def test_tocar_el_medio_no_ensucia_lo_de_arriba(self):
        """El caso que justifica todo: hoy se recomputan los 3, con caché sólo 2."""
        nodos, aristas = cadena()
        antes = cache_core.huellas_del_grafo(nodos, aristas)
        nodos["b"] = {"verb": "mesh_ribbon", "params": {"width": "400"}}
        self.assertEqual(cache_core.sucios(antes, cache_core.huellas_del_grafo(nodos, aristas)),
                         ["b", "c"])

    def test_tocar_la_fuente_ensucia_todo_lo_que_cuelga(self):
        nodos, aristas = cadena()
        antes = cache_core.huellas_del_grafo(nodos, aristas)
        nodos["a"] = {"verb": "curve_bezier", "params": {"segments": "20"}}
        self.assertEqual(cache_core.sucios(antes, cache_core.huellas_del_grafo(nodos, aristas)),
                         ["a", "b", "c"])

    def test_sin_cambios_no_hay_nada_sucio(self):
        nodos, aristas = cadena()
        h = cache_core.huellas_del_grafo(nodos, aristas)
        self.assertEqual(cache_core.sucios(h, cache_core.huellas_del_grafo(nodos, aristas)), [])

    def test_un_nodo_nuevo_esta_sucio(self):
        nodos, aristas = cadena()
        antes = cache_core.huellas_del_grafo(nodos, aristas)
        nodos["d"] = {"verb": "place", "params": {}}
        self.assertIn("d", cache_core.sucios(antes, cache_core.huellas_del_grafo(nodos, aristas)))

    def test_un_ciclo_no_recibe_huella(self):
        """Sin un orden no hay identidad estable, y darle una cualquiera sería inventar que su
        resultado se puede reusar."""
        nodos = {"a": {"verb": "x", "params": {}}, "b": {"verb": "y", "params": {}}}
        huellas = cache_core.huellas_del_grafo(nodos, [["a", "o", "b", "i"], ["b", "o", "a", "i"]])
        self.assertEqual(huellas, {})

    def test_dos_ramas_hermanas_no_se_ensucian_entre_si(self):
        """Tocar una rama no puede invalidar la otra: es la mitad del ahorro en un grafo ancho."""
        nodos = {"raiz": {"verb": "curve_bezier", "params": {}},
                 "izq": {"verb": "mesh_ribbon", "params": {"width": "100"}},
                 "der": {"verb": "mesh_pipe", "params": {"radio": "10"}}}
        aristas = [["raiz", "out", "izq", "in"], ["raiz", "out", "der", "in"]]
        antes = cache_core.huellas_del_grafo(nodos, aristas)
        nodos["izq"] = {"verb": "mesh_ribbon", "params": {"width": "200"}}
        self.assertEqual(cache_core.sucios(antes, cache_core.huellas_del_grafo(nodos, aristas)),
                         ["izq"])
