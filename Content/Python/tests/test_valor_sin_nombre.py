"""Un nodo de valor sin `name` se llama como el nodo, en el Compile y en la tabla (tarea `valor-sin-nombre`).

Antes `math_core.resolver` tomaba el default del param («n») y el Compile el id: dos `number` sin
nombre compilaban en verde y el segundo pisaba al primero en la tabla, así que `=n` recibía 7 sin
aviso. El texto de un grafo (`jam.texto`) omite el `name` igual al id, así que esta regla es la suya.
"""

from __future__ import annotations

import unittest

from jam import graph


class ValorSinNombre(unittest.TestCase):
    def _grafo(self):
        g = graph.JamGraph()
        g.add("number", {"value": "3"}, nid="a")
        g.add("number", {"value": "7"}, nid="b")
        return g

    def test_cada_valor_sin_nombre_se_llama_como_su_nodo(self):
        self.assertEqual(self._grafo().valores(), {"a": 3.0, "b": 7.0})

    def test_una_expresion_con_el_nombre_viejo_ya_no_recibe_el_ultimo(self):
        g = self._grafo()
        g.add("math", {"expr": "n * 2"}, nid="doble")
        self.assertNotIn(14.0, g.valores().values(), "«n * 2» resolvió con el último valor sin nombre")

    def test_un_nombre_escrito_sigue_mandando(self):
        g = self._grafo()
        g.nodes["a"]["params"]["name"] = "alto"
        self.assertEqual(g.valores(), {"alto": 3.0, "b": 7.0})


if __name__ == "__main__":
    unittest.main()
