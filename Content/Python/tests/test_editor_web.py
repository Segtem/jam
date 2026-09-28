"""El editor de nodos web (etapa 3 de `fuera-del-motor`): un solo editor, tres motores detrás.

El editor (`web/editor.js`) llama funciones por nombre; tienen que existir con ESE nombre en las dos
puertas —`jam.servidor.Nucleo` (Godot/Unity) y `jam.api` vía `jam.web` (Unreal)— y estar en las dos
listas blancas. Y el núcleo del editor, contra un Godot falso.
"""

from __future__ import annotations

import json
import re
import socketserver
import sys
import threading
import types
import unittest
from pathlib import Path

_unreal_fake = sys.modules.setdefault("unreal", types.ModuleType("unreal"))
if not hasattr(_unreal_fake, "TopLevelAssetPath"):
    _unreal_fake.TopLevelAssetPath = lambda package, name: (package, name)
for _nombre in ("log", "log_warning", "log_error"):
    if not hasattr(_unreal_fake, _nombre):
        setattr(_unreal_fake, _nombre, lambda *_a, **_k: None)

from jam import adaptador_godot, api, servidor, web  # noqa: E402

EDITOR_JS = Path(servidor.WEB) / "editor.js"


class Contrato(unittest.TestCase):
    def test_lo_que_llama_el_editor_existe_en_las_dos_puertas(self):
        llamadas = set(re.findall(r'api\("(\w+)"', EDITOR_JS.read_text(encoding="utf-8")))
        self.assertGreaterEqual(len(llamadas), 6, "el regex dejó de encontrar las llamadas")
        self.assertEqual(sorted(llamadas - servidor.Nucleo.PUBLICAS), [], "falta en jam.servidor")
        self.assertEqual(sorted(llamadas - web.API_PUBLICA), [], "falta en la lista blanca de jam.web")
        self.assertEqual(sorted(n for n in llamadas if not callable(getattr(api, n, None))), [],
                         "falta en jam.api (la puerta de Unreal)")
        self.assertEqual(sorted(n for n in llamadas if not callable(getattr(servidor.Nucleo, n, None))), [])

    def test_la_libreria_del_canvas_esta_en_el_repo_con_su_licencia(self):
        vendor = Path(servidor.WEB) / "vendor"
        self.assertTrue((vendor / "litegraph.js").is_file())
        # El texto de la licencia MIT, no la palabra: un archivo cualquiera no lo trae.
        self.assertIn("Permission is hereby granted, free of charge",
                      (vendor / "LICENSE-litegraph").read_text(encoding="utf-8"))


class _GodotFalso(socketserver.StreamRequestHandler):
    pedidos: list = []

    def handle(self):
        for linea in self.rfile:
            p = json.loads(linea)
            self.pedidos.append(p["op"])
            r = ({"ok": True, "motor": "godot", "contrato": 1, "version": "falso"} if p["op"] == "hola"
                 else {"ok": True, "nodo": p.get("nombre", ""), "hechos": {"triangulos": 12, "posiciones": 8}}
                 if p["op"] == "mostrar_malla" else {"ok": True})
            self.wfile.write((json.dumps(r) + "\n").encode())


class NucleoDelEditor(unittest.TestCase):
    def setUp(self):
        _GodotFalso.pedidos = []
        self.srv = socketserver.ThreadingTCPServer(("127.0.0.1", 0), _GodotFalso)
        self.srv.daemon_threads = True
        threading.Thread(target=self.srv.serve_forever, kwargs={"poll_interval": 0.02}, daemon=True).start()
        puerto = self.srv.server_address[1]
        self.nucleo = servidor.Nucleo("godot")
        cliente = adaptador_godot.Cliente(puerto=puerto, plazo=5)
        self.addCleanup(cliente.cerrar)
        self.nucleo._adaptador = adaptador_godot.AdaptadorGodot(cliente)

    def tearDown(self):
        self.srv.shutdown()
        self.srv.server_close()

    GRAFO = json.dumps({"nodes": {"caja": {"verb": "mesh_box", "params": {}, "x": 0, "y": 0},
                                  "ver": {"verb": "mesh_preview", "params": {"name": "c"}, "x": 300, "y": 0}},
                        "edges": [["caja", "out", "ver", "in"]]})

    def test_el_spec_marca_lo_que_godot_no_tiene(self):
        spec = {t["verbo"]: t for t in self.nucleo.spec_editor()["tools"]}
        self.assertTrue(spec["mesh_box"]["disponible"])
        self.assertFalse(spec["mesh_torus"]["disponible"])
        self.assertTrue(spec["number"]["disponible"], "los nodos de valor son puros")

    def test_compilar_y_correr(self):
        self.assertTrue(self.nucleo.compilar_grafo(self.GRAFO)["ok"])
        r = self.nucleo.correr_grafo(self.GRAFO)
        self.assertTrue(r["ok"], r)
        self.assertIn("mostrar_malla", _GodotFalso.pedidos)
        self.assertIn("en Godot: 12 triángulos", r["nodes"]["ver"]["texto"])

    def test_un_verbo_que_godot_no_tiene_se_marca_en_su_nodo_y_no_corre(self):
        g = json.dumps({"nodes": {"t": {"verb": "mesh_torus", "params": {}}}, "edges": []})
        r = self.nucleo.correr_grafo(g)
        self.assertFalse(r["ok"])
        self.assertEqual(r["nodes"]["t"]["estado"], "error")
        self.assertNotIn("mostrar_malla", _GodotFalso.pedidos)

    def test_texto_ida_y_vuelta(self):
        t = self.nucleo.texto_de_grafo(self.GRAFO)["texto"]
        self.assertEqual(t, "caja = mesh_box\nver = mesh_preview @caja name=c\n")
        r = self.nucleo.grafo_de_texto(t, self.GRAFO)
        self.assertTrue(r["ok"], r)
        self.assertEqual(set(r["graph"]["nodes"]), {"caja", "ver"})


if __name__ == "__main__":
    unittest.main()
