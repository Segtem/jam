"""El visor 2D: que la imagen diga la verdad sobre el dato.

Un preview es una herramienta de CONFIANZA — se mira para decidir. Si dibuja algo distinto de lo
que calculó el grafo, es peor que no tenerlo: hace tomar decisiones sobre una mentira. Por eso lo
que se fija acá no es que «salga un PNG» sino que el PNG sea el dato.

Todo esto es puro y corre sin editor. Lo único que necesita Unreal es leer los triángulos de una
malla, y eso se verifica en `tools/experiments/verifica_preview2d.py`.
"""

from __future__ import annotations

import struct
import sys
import types
import unittest
import zlib

sys.modules.setdefault("unreal", types.ModuleType("unreal"))

from jam import preview2d  # noqa: E402


def leer_png(datos: bytes):
    """Decodifica el PNG que escribimos, para comprobar los píxeles de vuelta.

    Se decodifica de verdad en vez de confiar en el encoder: un test que sólo mira la firma del
    archivo aprueba igual un PNG con las filas corridas o los canales al revés.
    """
    assert datos[:8] == b"\x89PNG\r\n\x1a\n", "no es un PNG"
    pos, ancho, alto, crudo = 8, 0, 0, b""
    while pos < len(datos):
        largo = struct.unpack(">I", datos[pos:pos + 4])[0]
        tipo = datos[pos + 4:pos + 8]
        cuerpo = datos[pos + 8:pos + 8 + largo]
        esperado = struct.unpack(">I", datos[pos + 8 + largo:pos + 12 + largo])[0]
        assert zlib.crc32(tipo + cuerpo) & 0xFFFFFFFF == esperado, f"CRC roto en {tipo}"
        if tipo == b"IHDR":
            ancho, alto, prof, color = struct.unpack(">IIBB", cuerpo[:10])
            assert (prof, color) == (8, 2), "se esperaba RGB de 8 bits"
        elif tipo == b"IDAT":
            crudo += cuerpo
        pos += 12 + largo

    plano = zlib.decompress(crudo)
    filas, paso = [], ancho * 3 + 1
    for j in range(alto):
        inicio = j * paso
        assert plano[inicio] == 0, "este decodificador sólo entiende el filtro None"
        fila = plano[inicio + 1:inicio + paso]
        filas.append([tuple(fila[i * 3:i * 3 + 3]) for i in range(ancho)])
    return ancho, alto, filas


class PngTests(unittest.TestCase):
    def test_the_png_decodes_back_to_the_pixels_we_wrote(self):
        pixeles = [[(255, 0, 0), (0, 255, 0)], [(0, 0, 255), (16, 32, 48)]]
        ancho, alto, leidas = leer_png(preview2d.png(2, 2, pixeles))
        self.assertEqual((ancho, alto), (2, 2))
        self.assertEqual(leidas, pixeles)

    def test_a_row_of_the_wrong_length_is_refused(self):
        """Sin esta guarda el PNG sale corrido: cada fila empieza donde terminó la anterior, así que
        un píxel de más desplaza toda la imagen en diagonal y parece un efecto, no un error."""
        with self.assertRaises(ValueError):
            preview2d.png(3, 1, [[(0, 0, 0), (0, 0, 0)]])

    def test_the_wrong_number_of_rows_is_refused(self):
        with self.assertRaises(ValueError):
            preview2d.png(1, 3, [[(0, 0, 0)]])


class RampaTests(unittest.TestCase):
    def test_zero_and_one_are_the_extremes(self):
        self.assertEqual(preview2d.color_de(0.0), preview2d.RAMPA[0][1])
        self.assertEqual(preview2d.color_de(1.0), preview2d.RAMPA[-1][1])

    def test_it_is_monotonic_in_brightness(self):
        """La rampa puede tener color, pero el BRILLO tiene que crecer con el valor: si no, un 0.3 y
        un 0.7 se ven igual de claros y la imagen deja de leerse como una máscara."""
        brillos = [sum(preview2d.color_de(v / 20.0)) for v in range(21)]
        self.assertEqual(brillos, sorted(brillos))

    def test_values_outside_the_range_saturate_instead_of_wrapping(self):
        """Una máscara que se pasa de 1 tiene que verse saturada, no volver al negro: el error se
        nota justamente porque queda una mancha plana."""
        self.assertEqual(preview2d.color_de(4.0), preview2d.color_de(1.0))
        self.assertEqual(preview2d.color_de(-3.0), preview2d.color_de(0.0))


class CampoTests(unittest.TestCase):
    def test_the_image_is_not_mirrored_vertically(self):
        """La fila 0 de un PNG es la de ARRIBA y en un mapa la Y crece hacia arriba. Sin invertir al
        recorrer, la imagen sale espejada y todo se interpreta al revés sin que nada falle."""
        pixeles = preview2d.campo(lambda x, y: y, 4, 4, desde=(0.0, 0.0), hasta=(1.0, 1.0))
        arriba = sum(pixeles[0][0])
        abajo = sum(pixeles[-1][0])
        self.assertGreater(arriba, abajo, "la Y alta tiene que quedar arriba")

    def test_it_samples_the_range_it_was_given(self):
        vistos = []
        preview2d.campo(lambda x, y: vistos.append((x, y)) or 0.0, 2, 2,
                        desde=(-100.0, -50.0), hasta=(100.0, 50.0))
        xs = sorted({round(x, 4) for x, _ in vistos})
        ys = sorted({round(y, 4) for _, y in vistos})
        self.assertEqual(xs, [-100.0, 100.0])
        self.assertEqual(ys, [-50.0, 50.0])

    def test_a_constant_field_is_a_flat_image(self):
        pixeles = preview2d.campo(lambda x, y: 0.5, 8, 8)
        self.assertEqual({p for fila in pixeles for p in fila}, {preview2d.color_de(0.5)})


class IslasTests(unittest.TestCase):
    def test_a_triangle_inside_the_square_is_drawn_in_the_normal_colour(self):
        pixeles = preview2d.islas_uv([[(0.2, 0.2), (0.8, 0.2), (0.5, 0.8)]], 64, 64)
        colores = {p for fila in pixeles for p in fila}
        self.assertIn((80, 200, 206), colores)
        self.assertNotIn((216, 92, 92), colores, "nada debería estar marcado como fuera de rango")

    def test_a_triangle_outside_the_square_is_marked(self):
        """Fuera del 0..1 la textura se repite: sirve para tileado y no sirve para atlas ni para
        hornear. Tiene que verse distinto SIN leer un número."""
        pixeles = preview2d.islas_uv([[(0.2, 0.2), (1.6, 0.2), (0.5, 0.8)]], 64, 64)
        colores = {p for fila in pixeles for p in fila}
        self.assertIn((216, 92, 92), colores)

    def test_the_grid_is_drawn_even_with_no_triangles(self):
        """Un desplegado vacío tiene que verse como un cuadrado vacío, no como un panel roto."""
        pixeles = preview2d.islas_uv([], 64, 64)
        self.assertIn((38, 42, 48), {p for fila in pixeles for p in fila})

    def test_uv_zero_zero_lands_at_the_bottom_left(self):
        """La convención de UV: el origen abajo a la izquierda. Dibujarlo arriba da una imagen que
        no se corresponde con lo que muestra el editor de UVs de UE."""
        pixeles = preview2d.islas_uv([[(0.0, 0.0), (0.02, 0.0), (0.0, 0.02)]], 64, 64)
        abajo_izq = any(pixeles[j][i] == (80, 200, 206)
                        for j in range(60, 64) for i in range(0, 4))
        arriba_izq = any(pixeles[j][i] == (80, 200, 206)
                         for j in range(0, 4) for i in range(0, 4))
        self.assertTrue(abajo_izq)
        self.assertFalse(arriba_izq)


class AyudaTests(unittest.TestCase):
    def test_a_type_that_is_drawn_explains_what_you_are_looking_at(self):
        self.assertIn("UVs", preview2d.texto_de_ayuda("M"))
        self.assertIn("máscara", preview2d.texto_de_ayuda("MT"))

    def test_a_type_that_is_not_drawn_says_WHY(self):
        """Un panel en blanco parece un bug. «Esto ya lo ves en el viewport» es información."""
        texto = preview2d.texto_de_ayuda("P")
        self.assertIn("viewport", texto)
        self.assertIn("P", texto)


if __name__ == "__main__":
    unittest.main()
