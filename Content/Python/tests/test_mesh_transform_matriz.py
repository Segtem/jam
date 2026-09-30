"""`mesh_transform` con una matriz cableada: el primer consumidor de escena de las matrices (tarea
`matrices-ue`). En el núcleo se aplica `M · v`; Unreal la recibe como `FTransform` (`ue.py`)."""

import math
import sys
import unittest

sys.modules.setdefault("unreal", None)

from jam import comun, malla_core, malla_ops  # noqa: E402
from jam import math_core as mc  # noqa: E402

IDENTIDAD = mc._mx_escala((1.0, 1.0, 1.0))


def _caja():
    m, _ = comun.IMPLEMENTA["mesh_box"](None, size_x=100, size_y=50, size_z=30)
    return m


def _volumen(m):
    return sum(sum(a[i] * c[i] for i in range(3)) for a, c in
               ((m.vertices[t[0]], malla_core.cara_frontal(m.vertices, t)) for t in m.triangulos)) / 6.0


class ConMatriz(unittest.TestCase):
    def test_traslacion_y_rotacion_dan_lo_mismo_que_una_cadena_de_matrices(self):
        rot = mc._mx_rotacion((0.0, 0.0, 1.0), 90.0)
        tras = mc._mx_traslacion((10.0, 20.0, 30.0))
        m = malla_ops.transformar(_caja(), matriz=mc._mx_por_mx(tras, rot))
        h = malla_core.hechos(m)
        # La caja 100×50×30 girada 90° en Z queda 50×100, y después se traslada.
        self.assertEqual((h["min"], h["max"]), ([-15.0, -30.0, 30.0], [35.0, 70.0, 60.0]))

    def test_despues_de_los_campos(self):
        tras = mc._mx_traslacion((0.0, 0.0, 100.0))
        m = malla_ops.transformar(_caja(), scale_z=2.0, matriz=tras)
        self.assertEqual(malla_core.hechos(m)["max"][2], 160.0, "escala 2 en Z y recién ahí +100")

    def test_un_espejo_da_vuelta_las_caras(self):
        espejo = mc._mx_escala((-1.0, 1.0, 1.0))
        m = malla_ops.transformar(_caja(), matriz=espejo)
        self.assertGreater(_volumen(m), 0.0, "las caras siguen mirando afuera")
        self.assertTrue(all(math.isclose(math.sqrt(sum(c * c for c in n)), 1.0) for n in m.normales))

    def test_sin_matriz_nada_cambia(self):
        self.assertEqual(malla_ops.transformar(_caja(), x=5), malla_ops.transformar(_caja(), x=5, matriz=None))


class LoQueNoSeAplica(unittest.TestCase):
    def test_cizalla_proyeccion_y_eje_aplastado_se_rechazan_con_el_motivo(self):
        ident = list(IDENTIDAD)
        cizalla = ident[:]; cizalla[1] = 0.5
        proyeccion = ident[:]; proyeccion[12] = 0.1
        for matriz, motivo in ((cizalla, "cizalla"), (proyeccion, "proyección"),
                               (mc._mx_escala((0.0, 1.0, 1.0)), "aplasta")):
            with self.subTest(motivo=motivo), self.assertRaisesRegex(malla_core.MallaError, motivo):
                malla_ops.transformar(_caja(), matriz=tuple(matriz))


if __name__ == "__main__":
    unittest.main()
