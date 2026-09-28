"""El adaptador de Godot del lado del núcleo (tarea `base-comun`, paso 2), contra un Godot FALSO: un
servidor TCP que habla el contrato. La prueba con Godot de verdad es
`tools/experiments/verifica_base_comun_godot.py`."""

from __future__ import annotations

import json
import socketserver
import subprocess
import sys
import threading
import unittest
from pathlib import Path

from jam import adaptador_godot as ag

RAIZ_PY = Path(__file__).resolve().parents[1]


class _GodotFalso(socketserver.StreamRequestHandler):
    pedidos: list = []
    contrato = 1

    def handle(self):
        for linea in self.rfile:
            p = json.loads(linea)
            self.pedidos.append(p)
            if p["op"] == "hola":
                r = {"ok": True, "motor": "godot", "contrato": self.contrato, "version": "falso"}
            elif p["op"] == "descartar":
                r = {"ok": True, "descartados": 0}
            elif p["op"] == "mostrar_malla":
                r = {"ok": True, "nodo": p["nombre"],
                     "hechos": {"triangulos": len(p["malla"]["triangulos"]), "posiciones": 8}}
            else:
                r = {"ok": False, "error": "op desconocida"}
            self.wfile.write((json.dumps(r) + "\n").encode())


class _Base(unittest.TestCase):
    def setUp(self):
        _GodotFalso.pedidos = []
        _GodotFalso.contrato = 1
        self.srv = socketserver.ThreadingTCPServer(("127.0.0.1", 0), _GodotFalso)
        self.srv.daemon_threads = True
        threading.Thread(target=self.srv.serve_forever, kwargs={"poll_interval": 0.02}, daemon=True).start()
        self.puerto = self.srv.server_address[1]

    def tearDown(self):
        self.srv.shutdown()
        self.srv.server_close()


class Adaptador(_Base):
    def _adaptador(self):
        self.cliente = ag.Cliente(puerto=self.puerto, plazo=5)
        self.addCleanup(self.cliente.cerrar)
        return ag.AdaptadorGodot(self.cliente)

    def test_la_caja_se_calcula_en_el_nucleo_y_a_godot_le_llega_la_malla(self):
        r = ag.correr_texto("caja = mesh_box size_x=200\nver = mesh_preview @caja name=c\n",
                            self._adaptador())
        self.assertTrue(r["ok"], r)
        mostrar = [p for p in _GodotFalso.pedidos if p["op"] == "mostrar_malla"]
        self.assertEqual(len(mostrar), 1)
        xs = [v[0] for v in mostrar[0]["malla"]["vertices"]]
        self.assertEqual((min(xs), max(xs)), (-100, 100), "viaja en el marco del núcleo (cm)")
        self.assertIn("en Godot: 12 triángulos", r["nodes"]["ver"]["texto"])

    def test_un_verbo_que_godot_no_tiene_no_corre_y_dice_por_que(self):
        r = ag.correr_texto("c = curve_line\ntorno = mesh_revolve @c\nver = mesh_preview @torno\n",
                            self._adaptador())
        self.assertFalse(r["ok"])
        self.assertEqual(r["errores"][0]["linea"], 2)
        self.assertIn("no disponible en este motor (godot)", r["errores"][0]["mensaje"])
        self.assertFalse([p for p in _GodotFalso.pedidos if p["op"] == "mostrar_malla"])

    def test_un_plugin_sin_las_ops_de_colocar_deja_place_deshabilitado(self):
        # El falso anuncia sólo el contrato 1 original: asset/place/mesh_to_static no corren.
        r = ag.correr_texto("caja = mesh_box\na = mesh_to_static @caja\nc = place @a surface=false\n",
                            self._adaptador())
        self.assertFalse(r["ok"])
        self.assertIn("no disponible en este motor (godot)", r["errores"][0]["mensaje"])
        self.assertEqual({e["nodo"] for e in r["errores"]} & {"a", "c"}, {"a", "c"})

    def test_las_ops_de_flow_corren_en_el_nucleo(self):
        r = ag.correr_texto("linea = pts_line count=5\nruido = jitter @linea\n", self._adaptador())
        self.assertTrue(r["ok"], r)
        self.assertIn("JITTER P ✓ — 5 puntos", r["nodes"]["ruido"]["texto"])
        self.assertEqual([p["op"] for p in _GodotFalso.pedidos], ["hola"], "no molesta a Godot")

    def test_otro_contrato_se_rechaza_al_conectar(self):
        _GodotFalso.contrato = 2
        with self.assertRaises(ag.ErrorAdaptador) as e:
            self._adaptador()
        self.assertIn("contrato 2", str(e.exception))

    def test_sin_godot_el_error_dice_que_abrir(self):
        with self.assertRaises(ag.ErrorAdaptador) as e:
            ag.Cliente(puerto=9, plazo=1)
        self.assertIn("plugin Jam", str(e.exception))


class SinUnreal(_Base):
    def test_el_grafo_corre_con_unreal_bloqueado(self):
        """El núcleo corre FUERA del motor: en un proceso donde importar `unreal` es un error."""
        script = f"""
import sys
sys.modules["unreal"] = None
from jam import adaptador_godot as ag
c = ag.Cliente(puerto={self.puerto}, plazo=5)
r = ag.correr_texto("caja = mesh_box\\nver = mesh_preview @caja\\n", ag.AdaptadorGodot(c))
print("OK" if r["ok"] else r)
"""
        salida = subprocess.run([sys.executable, "-B", "-c", script], cwd=RAIZ_PY,
                                capture_output=True, text=True, timeout=30)
        self.assertEqual(salida.stdout.strip(), "OK", salida.stderr[-800:])


if __name__ == "__main__":
    unittest.main()
