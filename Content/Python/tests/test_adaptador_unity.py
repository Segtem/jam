"""Sólo la especialización Python. El motor REAL se prueba con verifica_base_comun_unity.py."""

import unittest
from unittest.mock import patch

from jam import adaptador_godot as ag, adaptador_unity as au


class ClienteFalso:
    def __init__(self, contrato=1):
        self.contrato = contrato
        self.pedidos = []

    def pedir(self, op, **datos):
        self.pedidos.append((op, datos))
        if op == "hola":
            return {"ok": True, "contrato": self.contrato, "version": "6000.falso"}
        if op == "descartar":
            return {"ok": True, "descartados": 0}
        return {"ok": True, "nodo": datos["nombre"],
                "hechos": {"triangulos": len(datos["malla"]["triangulos"]), "posiciones": 8}}


class AdaptadorUnity(unittest.TestCase):
    def test_el_transporte_heredado_usa_el_puerto_de_unity(self):
        with patch.object(ag.Cliente, "__init__", return_value=None) as iniciar:
            au.Cliente()
        iniciar.assert_called_once_with(host="127.0.0.1", puerto=8793, plazo=60.0)

    def test_los_errores_de_transporte_nombraran_unity(self):
        with patch.object(ag.Cliente, "__init__", side_effect=ag.ErrorAdaptador("no hay Godot")):
            with self.assertRaisesRegex(au.ErrorAdaptador, "no hay Unity"):
                au.Cliente()
        with patch.object(ag.Cliente, "__init__", return_value=None):
            cliente = au.Cliente()
        with patch.object(ag.Cliente, "pedir", side_effect=ag.ErrorAdaptador("Godot rechazó")):
            with self.assertRaisesRegex(au.ErrorAdaptador, "Unity rechazó"):
                cliente.pedir("hola")

    def test_mismo_nucleo_y_texto_de_unity_sin_reescribir_el_nombre_del_objeto(self):
        cliente = ClienteFalso()
        adaptador = au.AdaptadorUnity(cliente)
        r = au.correr_texto("caja = mesh_box size_x=200\nver = mesh_preview @caja name=Godot\n",
                            adaptador)
        self.assertTrue(r["ok"], r)
        self.assertEqual(adaptador.version_unity, "6000.falso")
        self.assertIn("en Unity: 12 triángulos", r["nodes"]["ver"]["texto"])
        self.assertIn("«Godot»", r["nodes"]["ver"]["texto"])
        op, datos = cliente.pedidos[-1]
        self.assertEqual(op, "mostrar_malla")
        xs = [v[0] for v in datos["malla"]["vertices"]]
        self.assertEqual((min(xs), max(xs)), (-100, 100))

    def test_compile_juzga_contra_unity(self):
        cliente = ClienteFalso()
        r = au.correr_texto("elegido = pick\n", au.AdaptadorUnity(cliente))
        self.assertFalse(r["ok"])
        self.assertIn("no disponible en este motor (unity)", r["errores"][0]["mensaje"])
        self.assertEqual([op for op, _ in cliente.pedidos], ["hola"])

    def test_contrato_incompatible_nombra_unity(self):
        with self.assertRaisesRegex(au.ErrorAdaptador, "plugin de Unity habla el contrato 2"):
            au.AdaptadorUnity(ClienteFalso(contrato=2))


if __name__ == "__main__":
    unittest.main()
