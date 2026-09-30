"""Las instancias de función en el texto van por su NOMBRE y con sus perillas en el orden de su
firma (tarea `dsl-grafos`, «instancias fn: por etiqueta»). La biblioteca es del usuario, así que el
núcleo la recibe de quien llama (`api._vocab`); sin ella, todo sigue por id como antes."""

import sys
import unittest

sys.modules.setdefault("unreal", None)

from jam import texto  # noqa: E402

FICHAS = [
    {"verbo": "fn:f1", "label": "Cilindro redondeado",
     "params": [{"nombre": "radio", "default": "50"}, {"nombre": "alto", "default": "200"}]},
    {"verbo": "fn:f2", "label": "Poste", "params": []},
]


def _vocab(fichas=FICHAS):
    return texto.vocabulario(fichas)


class PorNombre(unittest.TestCase):
    def test_se_escribe_por_nombre_con_la_firma_en_orden_y_vuelve_al_mismo_id(self):
        g = texto.leer('a = fn:f1 alto=300 radio=20\nb = fn:f2 base=@a\n', _vocab())
        t = texto.imprimir(g, _vocab())
        self.assertEqual(t, 'a = "fn:Cilindro redondeado" radio=20 alto=300\n'
                            'b = fn:Poste base=@a\n')
        releido = texto.leer(t, _vocab())
        self.assertEqual({n: x["verb"] for n, x in releido.nodes.items()},
                         {"a": "fn:f1", "b": "fn:f2"})
        self.assertEqual(texto.imprimir(releido, _vocab()), t, "punto fijo")

    def test_un_nombre_mal_escrito_sugiere_el_parecido(self):
        with self.assertRaisesRegex(texto.ErrorTexto, "¿quisiste decir «fn:Poste»"):
            texto.leer("a = fn:Postes\n", _vocab())

    def test_el_id_se_sigue_aceptando(self):
        self.assertEqual(texto.leer("a = fn:f2\n", _vocab()).nodes["a"]["verb"], "fn:f2")


class LoQueNoSePuedeEscribirPorNombre(unittest.TestCase):
    def test_dos_funciones_con_el_mismo_nombre_van_por_id_y_leer_el_nombre_es_error(self):
        fichas = FICHAS + [{"verbo": "fn:f3", "label": "Poste", "params": []}]
        g = texto.leer("a = fn:f2\n", _vocab(fichas))
        self.assertEqual(texto.imprimir(g, _vocab(fichas)), "a = fn:f2\n")
        with self.assertRaisesRegex(texto.ErrorTexto, "hay 2 funciones «Poste»"):
            texto.leer("a = fn:Poste\n", _vocab(fichas))

    def test_un_nombre_igual_a_otro_id_va_por_id(self):
        # Leer «fn:f2» daría la OTRA función: escribirlo por nombre rompería la ida y vuelta.
        fichas = [{"verbo": "fn:f1", "label": "f2", "params": []},
                  {"verbo": "fn:f2", "label": "Poste", "params": []}]
        g = texto.leer("a = fn:f1\n", _vocab(fichas))
        self.assertEqual(texto.imprimir(g, _vocab(fichas)), "a = fn:f1\n")

    def test_sin_biblioteca_todo_va_por_id_como_antes(self):
        g = texto.leer("a = fn:Lo_que_sea x=1\n")
        self.assertEqual(g.nodes["a"]["verb"], "fn:Lo_que_sea")
        self.assertEqual(texto.imprimir(g), "a = fn:Lo_que_sea x=1\n")


if __name__ == "__main__":
    unittest.main()
