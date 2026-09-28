"""`jam.colocacion`: dónde va cada instancia de `place`, sin motor. Las cajas esperadas son las que
MIDIÓ Unreal con `verifica_colocar_58.py` (2026-09-28) sobre los mismos casos."""

import sys
import unittest

sys.modules.setdefault("unreal", None)

from jam import colocacion, comun, flow, malla_core  # noqa: E402


def _caja_de_prueba():
    m, _ = comun.IMPLEMENTA["mesh_box"](None, size_x=100, size_y=50, size_z=30)
    m, _ = comun.IMPLEMENTA["mesh_transform"](m, x=40, y=10)
    h = malla_core.hechos(m)
    return colocacion.caja_de(h["min"], h["max"])


def _mundo(caja, inst):
    c = colocacion.caja_de_mundo(caja, inst["pos"], inst["yaw"], inst["escala"])
    o, e = c.origin, c.extent
    return ([round(o.x - e.x, 3), round(o.y - e.y, 3), round(o.z - e.z, 3)],
            [round(o.x + e.x, 3), round(o.y + e.y, 3), round(o.z + e.z, 3)])


class ComoUnreal(unittest.TestCase):
    def test_girada_escalada_y_por_el_centro(self):
        caja = _caja_de_prueba()
        inst, _ = colocacion.planear([caja], x=300, y=-200, z=50, yaw=30, scale=2,
                                     surface=False, anchor="center")
        self.assertEqual(_mundo(caja, inst[0]),
                         ([188.397, -293.301, 20.0], [411.603, -106.699, 80.0]))

    def test_sobre_un_piso_por_raycast(self):
        caja = _caja_de_prueba()
        rayos = []

        def raycast(desde, hacia):
            rayos.append((desde, hacia))
            return {"golpe": True, "punto": [100.0, 150.0, -5.0], "normal": [0, 0, 1]}
        inst, _ = colocacion.planear([caja], x=100, y=150, z=500, yaw=-45, raycast=raycast)
        self.assertEqual(rayos, [((100, 150, 1.0e6), (100, 150, -1.0e6))], "vertical, hacia abajo")
        self.assertEqual(_mundo(caja, inst[0]),
                         ([46.967, 96.967, -5.0], [153.033, 203.033, 25.0]))

    def test_sin_golpe_queda_donde_se_pidio(self):
        caja = _caja_de_prueba()
        inst, _ = colocacion.planear([caja], x=100, y=150, z=500,
                                     raycast=lambda _d, _h: {"golpe": False})
        self.assertEqual(_mundo(caja, inst[0])[0][2], 500.0)

    def test_en_puntos_reparte_por_huella(self):
        caja = _caja_de_prueba()
        f, _ = flow.OPS["pts_line"]
        puntos = f([], {"ax": -400, "bx": 400, "count": 6, "seed": 3})
        inst, pisados = colocacion.planear([caja], puntos=puntos, scale_min=0.5, scale_max=1.5)
        self.assertEqual((len(inst), pisados), (3, 3))
        self.assertEqual(sorted(_mundo(caja, i) for i in inst)[0],
                         ([-449.674, -38.98, 0.0], [-350.326, 38.98, 26.666]))


class LoQueNoHace(unittest.TestCase):
    def test_align_y_view_se_rechazan_con_su_porque(self):
        caja = _caja_de_prueba()
        with self.assertRaisesRegex(colocacion.ErrorColocacion, "align"):
            colocacion.planear([caja], align=True, surface=False)
        with self.assertRaisesRegex(colocacion.ErrorColocacion, "viewport"):
            colocacion.planear([caja], view=True)

    def test_sin_asset_no_coloca(self):
        with self.assertRaisesRegex(colocacion.ErrorColocacion, "QUÉ colocar"):
            colocacion.planear([], surface=False)


if __name__ == "__main__":
    unittest.main()
