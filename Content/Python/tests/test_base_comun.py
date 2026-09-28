"""La base común (tarea `base-comun`): la geometría se calcula en el núcleo, igual para los tres
motores. La referencia es el MOTOR: los números de acá los midió Unreal sobre su propia caja
(`tools/experiments/verifica_caja_comun_58.py`), no se dedujeron del código que se prueba.
"""

from __future__ import annotations

import unittest

from jam import comun, malla_core, registro

#: (params, triángulos, vértices distintos) medidos por Geometry Script el 2026-09-28.
MEDIDO = [
    (dict(size_x=100, size_y=100, size_z=100), 12, 8),
    (dict(size_x=200, size_y=80, size_z=50, steps_x=2, steps_y=1, steps_z=3), 20, 12),
    (dict(size_x=37.5, size_y=410, size_z=12, steps_x=0, steps_y=4, steps_z=0), 28, 16),
]


class Caja(unittest.TestCase):
    def test_coincide_con_lo_que_mide_el_motor(self):
        for params, tris, verts in MEDIDO:
            with self.subTest(params):
                h = malla_core.hechos(malla_core.caja(**params))
                self.assertEqual((h["triangulos"], h["posiciones"]), (tris, verts))

    def test_pivote_en_la_base_y_medidas(self):
        h = malla_core.hechos(malla_core.caja(size_x=200, size_y=80, size_z=50))
        self.assertEqual((h["min"], h["max"]), ([-100, -40, 0], [100, 40, 50]))
        self.assertEqual(h["area"], 2 * (200 * 80 + 200 * 50 + 80 * 50))

    def test_toda_cara_frontal_mira_afuera(self):
        """El winding de Unreal (`ribbon_core`): la cara dibujada es `(c-a)×(b-a)`. Al revés, la caja
        se vería desde adentro —el defecto que ya costó un tutorial invisible."""
        m = malla_core.caja(size_x=200, size_y=80, size_z=50, steps_x=3, steps_y=4, steps_z=5)
        centro = (0.0, 0.0, 25.0)
        for tri in m.triangulos:
            n = malla_core.cara_frontal(m.vertices, tri)
            c = [sum(m.vertices[i][k] for i in tri) / 3 - centro[k] for k in range(3)]
            self.assertGreater(sum(n[k] * c[k] for k in range(3)), 0.0, tri)

    def test_la_normal_de_cada_vertice_es_la_de_su_cara(self):
        m = malla_core.caja()
        for tri in m.triangulos:
            f = malla_core.cara_frontal(m.vertices, tri)
            for i in tri:
                self.assertGreater(sum(f[k] * m.normales[i][k] for k in range(3)), 0.0)

    def test_parametros_invalidos(self):
        with self.assertRaises(malla_core.MallaError):
            malla_core.caja(size_x=0)
        with self.assertRaises(malla_core.MallaError):
            malla_core.caja(steps_y=-1)

    def test_viaja_como_json(self):
        d = malla_core.a_dict(malla_core.caja())
        self.assertEqual(set(d), {"vertices", "triangulos", "normales", "uv0"})
        self.assertEqual(len(d["vertices"]), len(d["normales"]))


class Registro(unittest.TestCase):
    def test_comunes_y_sus_implementaciones_no_se_separan(self):
        self.assertEqual(registro.COMUNES, frozenset(comun.IMPLEMENTA))

    def test_un_comun_corre_en_cualquier_motor(self):
        for verbo in registro.COMUNES:
            self.assertEqual(registro.disponible(verbo, "godot"), (True, ""))

    def test_mismo_nombre_mismos_params(self):
        """El verbo común conserva la firma que tenía en Unreal: un grafo guardado no cambia."""
        import inspect
        for verbo, fn in comun.IMPLEMENTA.items():
            firma = [n for n, p in inspect.signature(fn).parameters.items()
                     if p.kind is inspect.Parameter.KEYWORD_ONLY]
            self.assertEqual(firma, list(registro.REGISTRO[verbo]["params"]), verbo)


if __name__ == "__main__":
    unittest.main()
