from __future__ import annotations

import math
import unittest

from jam import ribbon_core


class RibbonCoreTests(unittest.TestCase):
    def test_recta_xy_tiene_ancho_winding_normal_y_uv_longitudinal(self):
        result = ribbon_core.ribbon_buffers(
            ((0, 0, 7), (100, 0, 7)), width=20, uv_scale=100)

        self.assertEqual(result["vertices"], (
            (0.0, 10.0, 7.0), (0.0, -10.0, 7.0),
            (100.0, 10.0, 7.0), (100.0, -10.0, 7.0)))
        self.assertEqual(result["triangles"], ((0, 2, 1), (1, 2, 3)))
        self.assertEqual(result["normals"], ((0.0, 0.0, 1.0),) * 4)
        self.assertEqual(result["uv0"], ((0.0, 0.0), (0.0, 1.0),
                                         (1.0, 0.0), (1.0, 1.0)))

    def test_esquina_miter_conserva_ancho_y_conectividad(self):
        result = ribbon_core.ribbon_buffers(
            ((0, 0, 0), (100, 0, 0), (100, 100, 0)), width=20,
            join="miter", miter_limit=2)

        self.assertEqual(len(result["vertices"]), 6)
        self.assertEqual(len(result["triangles"]), 4)
        for index in (0, len(result["vertices"]) - 2):
            self.assertAlmostEqual(
                math.dist(result["vertices"][index], result["vertices"][index + 1]), 20)
        self.assertAlmostEqual(math.dist(result["vertices"][2], result["vertices"][3]),
                               20 * math.sqrt(2))
        self.assertEqual({index for tri in result["triangles"] for index in tri}, set(range(6)))

    def test_bevel_hace_explicito_el_presupuesto_y_mantiene_pares(self):
        result = ribbon_core.ribbon_buffers(
            ((0, 0, 0), (100, 0, 0), (100, 100, 0)), width=20,
            join="miter", miter_limit=1.1)

        self.assertEqual(result["bevels"], 1)
        self.assertEqual(len(result["vertices"]), 8)
        self.assertEqual(len(result["triangles"]), 6)
        self.assertEqual(len(result["uv0"]), 8)

    def test_pendiente_calcula_normales_geometricas_normalizadas(self):
        result = ribbon_core.ribbon_buffers(
            ((0, 0, 0), (100, 0, 100), (200, 50, 120)), width=30)

        for normal in result["normals"]:
            self.assertAlmostEqual(math.sqrt(sum(value * value for value in normal)), 1.0)
        self.assertTrue(any(abs(normal[0]) > 1e-3 or abs(normal[1]) > 1e-3
                            for normal in result["normals"]))

    def test_planos_verticales_tienen_winding_determinista(self):
        xz = ribbon_core.ribbon_buffers(((0, 7, 0), (100, 7, 0)), plane="xz")
        yz = ribbon_core.ribbon_buffers(((7, 0, 0), (7, 100, 0)), plane="yz")
        self.assertEqual(xz["normals"], ((0.0, -1.0, 0.0),) * 4)
        self.assertEqual(yz["normals"], ((1.0, 0.0, 0.0),) * 4)


class CaraVisibleEnUnrealTests(unittest.TestCase):
    """La cinta tiene que quedar VISIBLE desde arriba, y eso no lo deciden las normales.

    Los tests de arriba miran `normals`, que es el sombreado que se envía aparte en los buffers. El
    backface culling ignora ese array y mira el ORDEN DE LOS ÍNDICES. Por eso los 790 tests estaban
    en verde mientras «Borde de camino» se veía transparente en el viewport y «Muro sobre spline»
    aparecía dado vuelta: ninguna medida miraba el winding.

    Medido en UE 5.8.1 el 2026-08-10 con `tools/experiments/investiga_winding_ribbon_58.py`: con el
    orden anterior el motor reportaba 48/48 triángulos hacia -Z, contra un `mesh_box` nativo que
    daba su tapa hacia +Z. Estos tests fijan el criterio del motor para que nadie lo revierta.
    """

    def normal_de_cara_segun_unreal(self, vertices, triangle):
        """La normal que computa Unreal para un triángulo, dada su terna de índices.

        Es el cross en el orden `(c-a) × (b-a)`: el opuesto al matemático habitual. La constante de
        este test es empírica, no teórica — sale de comparar contra una malla nativa en el motor.
        """
        a, b, c = (vertices[index] for index in triangle)
        u = tuple(c[axis] - a[axis] for axis in range(3))
        v = tuple(b[axis] - a[axis] for axis in range(3))
        n = (u[1] * v[2] - u[2] * v[1],
             u[2] * v[0] - u[0] * v[2],
             u[0] * v[1] - u[1] * v[0])
        largo = math.sqrt(sum(componente * componente for componente in n))
        return tuple(componente / largo for componente in n)

    def test_una_cinta_horizontal_le_muestra_la_cara_de_arriba_al_motor(self):
        """El defecto original: la calzada existía pero el motor dibujaba su reverso."""
        result = ribbon_core.ribbon_buffers(((0, 0, 0), (500, 0, 0), (1000, 0, 0)), width=360)
        for triangle in result["triangles"]:
            normal = self.normal_de_cara_segun_unreal(result["vertices"], triangle)
            self.assertGreater(normal[2], 0.9,
                               f"el triángulo {triangle} le muestra a Unreal la cara de abajo")

    def test_tambien_al_curvar_y_al_subir(self):
        """El tutorial no usa una recta: curva en Y y sube en Z. La cara no puede darse vuelta
        en el medio del recorrido."""
        result = ribbon_core.ribbon_buffers(
            ((0, 0, 0), (225, 120, 10), (450, 200, 30), (675, 180, 55), (900, 0, 80)), width=360)
        for triangle in result["triangles"]:
            normal = self.normal_de_cara_segun_unreal(result["vertices"], triangle)
            self.assertGreater(normal[2], 0.0,
                               f"el triángulo {triangle} se dio vuelta al curvar")

    def test_una_curva_cerrada_angosta_la_cinta_en_vez_de_plegarla(self):
        """El defecto que encontró `malla.cara_visible` en su primer uso.

        Doblar más cerrado que la media anchura cruzaba el borde interior consigo mismo y daba
        vuelta las caras de ese tramo. No existe una cinta de ese ancho sobre esa curva, así que se
        angosta ahí y se informa —como `miter_limit` cae a bevel— en vez de entregar geometría
        plegada en silencio.
        """
        # Una U de casi 180° con una cinta de 300 cm sobre tramos de ~400: el borde interior no
        # entra. Los números salen de probar la geometría, no de elegirlos para que el test pase.
        result = ribbon_core.ribbon_buffers(
            ((0, 0, 0), (400, 0, 0), (380, 120, 0), (0, 140, 0)), width=300)
        self.assertNotIn("error", result)
        for triangle in result["triangles"]:
            normal = self.normal_de_cara_segun_unreal(result["vertices"], triangle)
            self.assertGreater(normal[2], 0.0,
                               f"el triángulo {triangle} quedó plegado en la curva cerrada")
        self.assertGreater(result["angostados"], 0,
                           "la cinta se angostó pero no lo declaró en «angostados»")

    def test_una_curva_suave_no_se_angosta(self):
        """El remedio no puede cobrarse ancho donde no hacía falta: sería peor que el defecto."""
        result = ribbon_core.ribbon_buffers(
            ((0, 0, 0), (500, 0, 0), (1000, 120, 0), (1500, 260, 0)), width=200)
        self.assertEqual(result["angostados"], 0)

    def test_la_cara_visible_y_la_normal_de_sombreado_miran_para_el_mismo_lado(self):
        """Si se corrigiera sólo el winding, la cinta se vería pero iluminada por detrás. Las dos
        mitades del arreglo tienen que moverse juntas."""
        result = ribbon_core.ribbon_buffers(((0, 0, 0), (500, 0, 0)), width=200)
        for triangle in result["triangles"]:
            cara = self.normal_de_cara_segun_unreal(result["vertices"], triangle)
            for indice in triangle:
                sombreado = result["normals"][indice]
                producto = sum(cara[axis] * sombreado[axis] for axis in range(3))
                self.assertGreater(producto, 0.0,
                                   "la normal de sombreado apunta al lado contrario de la cara")

    def test_rechaza_cerrada_dominio_invalido_y_presupuesto(self):
        line = ((0, 0, 0), (100, 0, 0))
        square = ((0, 0, 0), (100, 0, 0), (100, 100, 0), (0, 0, 0))
        self.assertIn("costura UV", ribbon_core.ribbon_buffers(square)["error"])
        for params in ({"width": 0}, {"uv_scale": 0}, {"plane": "xyz"},
                       {"join": "round"}, {"miter_limit": 0.5}):
            with self.subTest(params=params):
                self.assertIn("error", ribbon_core.ribbon_buffers(line, **params))
        huge = tuple((float(index), float(index % 2), 0.0) for index in range(2049))
        self.assertIn("4096", ribbon_core.ribbon_buffers(huge)["error"])


if __name__ == "__main__":
    unittest.main()
