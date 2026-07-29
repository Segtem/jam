"""El núcleo declarativo del oráculo, y la prueba de que traducirlo no cambia el veredicto.

La prueba que manda es la DIFERENCIAL: cientos de casos generados, y para cada uno el veredicto
declarado tiene que coincidir con el del oráculo escrito a mano. Si difieren, la traducción cambió
el juicio y eso invalida todo el ejercicio.
"""

from __future__ import annotations

import json
import random
import unittest

from jam import catalogo, geometry, oracle_placement, oracle_snap
from jam.geometry import AABB, Pieza, Vec3
from jam.medida import (EvidenciaIncompleta, Informe, Medida, MedidaMalDeclarada, Umbral,
                        evaluar, inventario, no_medibles, puntos_ciegos)


def _pieza(nombre, cx, cy, cz, ex=50.0, ey=50.0, ez=50.0, yaw=0.0):
    return Pieza(nombre=nombre, aabb=AABB(Vec3(cx, cy, cz), Vec3(ex, ey, ez)),
                 location=Vec3(cx, cy, cz), yaw=yaw)


def _mundo(semilla: int, n: int = 5):
    """Piezas en una grilla chica para que los solapes ocurran seguido y el test tenga qué mirar.

    Siempre incluye una pieza de ESCENOGRAFÍA DE FONDO que envuelve a todas. Sin ella, quitar el
    filtro `es_fondo` del catálogo no rompía ningún test: la regla existía sin estar verificada.
    """
    r = random.Random(semilla)
    piezas = [_pieza(f"p{i}", r.randrange(-200, 200, 25), r.randrange(-200, 200, 25),
                     r.choice([0.0, 25.0, 100.0]), yaw=r.choice([0.0, 45.0, 90.0, 90.4, 91.0]))
              for i in range(n)]
    cielo = _pieza("SkySphere", 0.0, 0.0, 0.0, 60000.0, 60000.0, 60000.0)
    return piezas + [cielo]


class NucleoTests(unittest.TestCase):
    def test_una_medida_sin_alcance_no_se_puede_declarar(self) -> None:
        with self.assertRaises(MedidaMalDeclarada) as e:
            Medida(id="x.y", requiere=(), mide=lambda ev: 0.0, unidad="cm",
                   umbral=Umbral("<=", 1.0), alcance="   ")

        self.assertIn("qué NO ve", str(e.exception))

    def test_un_operador_inventado_no_pasa(self) -> None:
        with self.assertRaises(MedidaMalDeclarada):
            Umbral("≈", 1.0)

    def test_medir_sin_la_evidencia_no_es_lo_mismo_que_medir_mal(self) -> None:
        with self.assertRaises(EvidenciaIncompleta) as e:
            catalogo.INTERPENETRACION.evaluar({"pieza": _pieza("a", 0, 0, 0)})

        self.assertIn("otras", str(e.exception))

    def test_lo_que_no_se_puede_medir_se_saltea_y_SE_DICE(self) -> None:
        # callar una medida no corrida sería el peor Goodhart: verde por no haber preguntado
        informe = evaluar(catalogo.TODAS, {"pieza": _pieza("a", 0, 0, 0)})

        self.assertEqual([v.id for v in informe.veredictos],
                         ["colocacion.bounds", "snap.grilla", "snap.yaw"])
        self.assertEqual(no_medibles(catalogo.TODAS, {"pieza": _pieza("a", 0, 0, 0)}),
                         ["colocacion.interpenetracion"])

    def test_un_informe_verde_igual_declara_lo_que_no_miro(self) -> None:
        informe = evaluar(catalogo.TODAS,
                          {"pieza": _pieza("a", 100, 100, 100), "otras": []})

        texto = informe.texto()
        self.assertTrue(informe.ok)
        self.assertIn("SIN MIRAR", texto)
        self.assertIn("NO ve", texto)
        self.assertNotIn("TODO VERDE", texto)

    def test_todas_las_medidas_tienen_la_misma_forma(self) -> None:
        informe = evaluar(catalogo.TODAS, {"pieza": _pieza("a", 3, 0, 0), "otras": []})

        for m in json.loads(informe.a_json())["medidas"]:
            self.assertEqual(sorted(m), ["alcance", "id", "ok", "testigos", "umbral",
                                         "unidad", "valor"])

    def test_el_inventario_saca_los_umbrales_a_la_luz_con_su_defensa(self) -> None:
        filas = {f["id"]: f for f in inventario(catalogo.TODAS)}

        self.assertEqual(filas["colocacion.bounds"]["umbral"], "> 0.001")
        self.assertIn("degenerada", filas["colocacion.bounds"]["porque"])
        self.assertTrue(all(f["porque"] for f in filas.values()))

    def test_cada_medida_declara_su_punto_ciego(self) -> None:
        for p in puntos_ciegos(catalogo.TODAS):
            self.assertIn("NO ve", p["alcance"])


class DiferencialTests(unittest.TestCase):
    """La traducción no puede cambiar el juicio. 300 mundos generados, veredicto contra veredicto."""

    def test_bounds_coincide_con_el_oraculo_escrito_a_mano(self) -> None:
        casos = [_pieza("a", 0, 0, 0, ex, 50.0, 50.0) for ex in (0.0, 1e-9, 0.001, 1.0, 50.0)]
        for p in casos:
            with self.subTest(extent=p.aabb.extent.x):
                viejo = oracle_placement.verificar(p, [])["bounds_ok"]
                nuevo = catalogo.BOUNDS.evaluar({"pieza": p}).ok
                self.assertEqual(nuevo, viejo)

    def test_interpenetracion_coincide_en_veredicto_y_en_testigos(self) -> None:
        vistos = {True: 0, False: 0}
        for semilla in range(300):
            mundo = _mundo(semilla)
            pieza, otras = mundo[0], mundo[1:]
            viejo = oracle_placement.verificar(pieza, otras)
            nuevo = catalogo.INTERPENETRACION.evaluar({"pieza": pieza, "otras": otras})

            with self.subTest(semilla=semilla):
                self.assertEqual(nuevo.ok, viejo["interpenetra"] == [])
                self.assertEqual(sorted(t.split(":")[0] for t in nuevo.testigos),
                                 sorted(str(c[0]) for c in viejo["interpenetra"]))
            vistos[nuevo.ok] += 1

        # si todos los casos cayeran del mismo lado, el test no estaría comparando nada
        self.assertGreater(vistos[True], 20, "no se generaron casos limpios")
        self.assertGreater(vistos[False], 20, "no se generaron casos con choque")

    def test_grilla_y_yaw_juntos_coinciden_con_el_en_grilla_de_snap(self) -> None:
        # generador propio: el de `_mundo` usa pasos de 25 contra una grilla de 100, así que casi
        # todo cae fuera y el lado verde quedaba sin comparar
        def _snappeable(semilla):
            r = random.Random(semilla)
            c = lambda: r.choice([0.0, 100.0, 200.0, -100.0, 100.5, 137.0])
            # 92.0 da un desvío de 2°: cae ENTRE el umbral real (0.5) y cualquier umbral aflojado,
            # que es la única franja donde un cambio de tolerancia se nota
            return _pieza("a", c(), c(), c(),
                          yaw=r.choice([0.0, 90.0, 180.0, 90.4, 92.0, 45.0]))

        vistos = {True: 0, False: 0}
        for semilla in range(300):
            p = _snappeable(semilla)
            viejo = oracle_snap.verificar_grilla(p)["en_grilla"]
            ev = {"pieza": p}
            nuevo = catalogo.GRILLA.evaluar(ev).ok and catalogo.YAW.evaluar(ev).ok

            with self.subTest(semilla=semilla):
                self.assertEqual(nuevo, viejo)
            vistos[nuevo] += 1

        self.assertGreater(vistos[True], 20)
        self.assertGreater(vistos[False], 20)

    def test_separar_grilla_de_yaw_dice_CUAL_de_las_dos_fallo(self) -> None:
        """Lo que se ganó traduciendo: el oráculo viejo devolvía un solo `en_grilla` para dos
        preguntas distintas, así que un rojo no decía por qué."""
        p = _pieza("a", 100, 100, 100, yaw=45.0)   # en grilla, yaw fuera de paso

        self.assertFalse(oracle_snap.verificar_grilla(p)["en_grilla"])
        self.assertTrue(catalogo.GRILLA.evaluar({"pieza": p}).ok)
        self.assertFalse(catalogo.YAW.evaluar({"pieza": p}).ok)


if __name__ == "__main__":
    unittest.main()
