"""Peldaño 6 de la escalera de Grasshopper Basics: tender una superficie entre curvas.

**Ruled Surface y Loft son el mismo verbo acá.** Grasshopper los separa porque el reglado entre dos
curvas es más barato de resolver en NURBS; en una malla la diferencia desaparece —son las mismas
filas de cuadriláteros— y dos nodos que hacen lo mismo obligan a elegir entre ellos sin criterio.
"""

from __future__ import annotations

import math
import sys
import types
import unittest

sys.modules.setdefault("unreal", types.ModuleType("unreal"))

from jam import loft_core, ribbon_core  # noqa: E402


def normales_z(built):
    """La componente Z de la cara de cada triángulo, con la convención de `_normals`."""
    salida = []
    for triangulo in built["triangles"]:
        a, b, c = (built["vertices"][i] for i in triangulo)
        u = [c[k] - a[k] for k in range(3)]
        v = [b[k] - a[k] for k in range(3)]
        n = [u[1] * v[2] - u[2] * v[1], u[2] * v[0] - u[0] * v[2], u[0] * v[1] - u[1] * v[0]]
        largo = math.sqrt(sum(x * x for x in n)) or 1.0
        salida.append(n[2] / largo)
    return salida


IZQUIERDA = ((0.0, 180.0, 0.0), (500.0, 180.0, 0.0))
DERECHA = ((0.0, -180.0, 0.0), (500.0, -180.0, 0.0))


class WindingCompartidoTests(unittest.TestCase):
    def test_el_loft_mira_para_el_MISMO_lado_que_la_cinta(self) -> None:
        """El control que importa. La cinta ya costó un tutorial invisible y una sesión de
        diagnóstico por tener el winding al revés; si el loft se dibujara con su propia regla,
        podría quedar dado vuelta sin que nada lo relacione con la otra superficie. Por eso la
        convención se IMPORTA de `ribbon_core` en vez de reescribirse."""
        loft = loft_core.loft_buffers([IZQUIERDA, DERECHA], samples=2)
        cinta = ribbon_core.ribbon_buffers([(0.0, 0.0, 0.0), (500.0, 0.0, 0.0)],
                                           width=360.0, plane="xy")
        self.assertEqual([round(x, 6) for x in normales_z(loft)],
                         [round(x, 6) for x in normales_z(cinta)])
        self.assertTrue(all(z > 0 for z in normales_z(loft)))

    def test_invertir_el_orden_de_las_curvas_da_vuelta_la_superficie(self) -> None:
        """Es el comportamiento de Grasshopper y no un defecto: el orden de los cables es lo único
        que puede decir de qué lado mira una superficie tendida entre dos curvas."""
        derecho = normales_z(loft_core.loft_buffers([IZQUIERDA, DERECHA], samples=2))
        alreves = normales_z(loft_core.loft_buffers([DERECHA, IZQUIERDA], samples=2))
        self.assertTrue(all(z > 0 for z in derecho))
        self.assertTrue(all(z < 0 for z in alreves))


class CorrespondenciaTests(unittest.TestCase):
    def test_una_curva_recorrida_al_reves_se_endereza_y_se_INFORMA(self) -> None:
        """Dos curvas trazadas en direcciones distintas son un caso normal, no un error: pedirle al
        usuario que las redibuje sería cobrarle un problema que la herramienta ve sola. Se corrige
        y se avisa, como `miter_limit` cae a bevel en vez de estirar la esquina en silencio."""
        alreves = tuple(reversed(DERECHA))
        built = loft_core.loft_buffers([IZQUIERDA, alreves], samples=2)
        self.assertEqual(built["invertidas"], 1)
        self.assertTrue(all(z > 0 for z in normales_z(built)),
                        "sin enderezarla, la superficie sale cruzada en X")

    def test_curvas_con_distinta_cantidad_de_puntos_tienden_parejo(self) -> None:
        """Se remuestrea por LONGITUD DE ARCO y no por índice: si no, la superficie se amontonaría
        donde una de las curvas tenía más detalle."""
        pocos = ((0.0, 180.0, 0.0), (500.0, 180.0, 0.0))
        muchos = tuple((x, -180.0, 0.0) for x in range(0, 501, 25))
        built = loft_core.loft_buffers([pocos, muchos], samples=8)
        fila_a = built["vertices"][:8]
        fila_b = built["vertices"][8:16]
        for a, b in zip(fila_a, fila_b):
            with self.subTest(x=a[0]):
                self.assertAlmostEqual(a[0], b[0], places=6)

    def test_tres_curvas_son_un_loft_y_dos_son_el_reglado(self) -> None:
        medio = ((0.0, 0.0, 200.0), (500.0, 0.0, 200.0))
        dos = loft_core.loft_buffers([IZQUIERDA, DERECHA], samples=4)
        tres = loft_core.loft_buffers([IZQUIERDA, medio, DERECHA], samples=4)
        self.assertEqual(dos["filas"], 2)
        self.assertEqual(tres["filas"], 3)
        self.assertEqual(len(tres["triangles"]), 2 * len(dos["triangles"]))


class RechazosTests(unittest.TestCase):
    def test_una_sola_curva_no_es_una_superficie(self) -> None:
        self.assertIn("al menos dos curvas", loft_core.loft_buffers([IZQUIERDA])["error"])

    def test_dos_curvas_superpuestas_no_tienen_superficie_entre_ellas(self) -> None:
        """Cada cuadrilátero sería un triángulo de área cero y sus normales las decidiría el
        redondeo — el mismo problema que el moño del bevel, atajado antes de emitirlo."""
        self.assertIn("superpuestas",
                      loft_core.loft_buffers([IZQUIERDA, IZQUIERDA], samples=4)["error"])

    def test_samples_fuera_de_rango(self) -> None:
        self.assertIn("samples", loft_core.loft_buffers([IZQUIERDA, DERECHA], samples=1)["error"])


class UVTests(unittest.TestCase):
    def test_U_recorre_la_curva_y_V_cruza_entre_ellas(self) -> None:
        built = loft_core.loft_buffers([IZQUIERDA, DERECHA], samples=4, uv_scale=100.0)
        uv = built["uv0"]
        self.assertEqual(uv[0], (0.0, 0.0))
        self.assertAlmostEqual(uv[3][0], 5.0)      # 500 cm / escala 100
        self.assertEqual(uv[0][1], 0.0)            # primera curva
        self.assertEqual(uv[-1][1], 1.0)           # última curva


if __name__ == "__main__":
    unittest.main()
