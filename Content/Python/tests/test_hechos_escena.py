"""`jam.hechos_escena`: la escena después de colocar, como la leen las medidas de colocación. El
escenario es el del plan (`commander/docs/AURA-PROPIO-CORTE-1.md`): dos cajas contra un muro."""

import sys
import unittest

sys.modules.setdefault("unreal", None)

from jam import hechos_escena, oracle_shadow  # noqa: E402
from jam.geometry import AABB, Pieza, Vec3  # noqa: E402

COLOCACION = ("colocacion.bounds", "colocacion.interpenetracion", "physics.tiene_suelo",
              "physics.apoyado", "physics.tanda_completa", "physics.tanda_sin_interpenetracion")


def _caja(nombre, x, y, z, ex=50, ey=50, ez=50):
    return Pieza(nombre, AABB(Vec3(x, y, z), Vec3(ex, ey, ez)), Vec3(x, y, z), 0.0)


ESCENA = [_caja("Suelo", 0, 0, -10, 1000, 1000, 10), _caja("Muro_Norte", 0, 0, 100, 200, 10, 100)]


def _juzgar(tanda):
    informe = oracle_shadow.motor_geometria().evaluar(hechos_escena.hechos(tanda, ESCENA))
    return {v.id: v.ok for v in informe.veredictos if v.id in COLOCACION}


class Bolsas(unittest.TestCase):
    def test_la_tanda_no_es_vecina_de_si_misma(self):
        h = hechos_escena.hechos([_caja("A", 0, 60, 50)], ESCENA)
        self.assertEqual([p["id"] for p in h["pieza"]], ["A"])
        self.assertEqual([v["id"] for v in h["vecina"]], ["Suelo", "Muro_Norte"])
        self.assertEqual(h["asentamiento"][0]["soporte"], "Suelo")

    def test_una_pieza_sobre_otra_de_la_tanda_se_apoya_en_ella(self):
        h = hechos_escena.hechos([_caja("A", 0, 60, 50), _caja("B", 0, 60, 150)], ESCENA)
        b = next(x for x in h["asentada"] if x["id"] == "B")
        self.assertEqual((b["soporte"], b["sobre_hermana"]), ("A", True))


class ComoLoJuzgaOracle(unittest.TestCase):
    def test_mal_colocadas_da_rojo_en_lo_que_esta_mal(self):
        r = _juzgar([_caja("Caja_A", -60, 50, 50), _caja("Caja_B", -30, 70, 50)])
        self.assertEqual({m for m, ok in r.items() if not ok},
                         {"colocacion.interpenetracion", "physics.tanda_sin_interpenetracion"})

    def test_corregidas_da_verde(self):
        r = _juzgar([_caja("Caja_A", -60, 60, 50), _caja("Caja_B", 40, 60, 50)])
        self.assertEqual(set(r), set(COLOCACION))
        self.assertTrue(all(r.values()), r)


if __name__ == "__main__":
    unittest.main()
