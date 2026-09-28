"""La puerta de los agentes (tarea `jam-mcp`): leer y aplicar el grafo abierto como texto, con
conflicto si el humano editó entretanto, la ayuda, y `POST /api/<función>` de `jam.web`."""

from __future__ import annotations

import json
import sys
import threading
import types
import unittest
import urllib.error
import urllib.request
from unittest import mock

_unreal_fake = sys.modules.setdefault("unreal", types.ModuleType("unreal"))
if not hasattr(_unreal_fake, "TopLevelAssetPath"):
    _unreal_fake.TopLevelAssetPath = lambda package, name: (package, name)
for _nombre in ("log", "log_warning", "log_error"):
    if not hasattr(_unreal_fake, _nombre):
        setattr(_unreal_fake, _nombre, lambda *_a, **_k: None)

from jam import api, serve, web  # noqa: E402


def _canvas(nodos: dict, aristas=()) -> str:
    return json.dumps({"nodes": nodos, "edges": [list(a) for a in aristas]})


CAJA = {"caja": {"verb": "mesh_box", "params": {}, "x": 40, "y": 40}}


class _Estado(unittest.TestCase):
    def setUp(self):
        self._c, self._p = dict(api._CANVAS), dict(api._PENDIENTE)
        api._CANVAS["json"] = ""
        api._PENDIENTE.update({"version": 0, "json": "", "visto": 0})

    def tearDown(self):
        api._CANVAS.clear(); api._CANVAS.update(self._c)
        api._PENDIENTE.clear(); api._PENDIENTE.update(self._p)


class LeerYAplicar(_Estado):
    def test_leer_devuelve_el_texto_del_canvas_y_su_version(self):
        api.canvas_publicar(_canvas(CAJA))
        r = json.loads(api.leer_canvas())
        self.assertEqual(r["texto"], "caja = mesh_box\n")
        self.assertTrue(r["canvas_abierto"])
        self.assertEqual(len(r["version"]), 16)

    def test_mover_un_nodo_no_cambia_la_version_editarlo_si(self):
        api.canvas_publicar(_canvas(CAJA))
        v = json.loads(api.leer_canvas())["version"]
        movido = {"caja": dict(CAJA["caja"], x=900)}
        api.canvas_publicar(_canvas(movido))
        self.assertEqual(json.loads(api.leer_canvas())["version"], v)
        editado = {"caja": dict(CAJA["caja"], params={"size_x": "300"})}
        api.canvas_publicar(_canvas(editado))
        self.assertNotEqual(json.loads(api.leer_canvas())["version"], v)

    def test_aplicar_sobre_una_version_vieja_es_conflicto_y_no_pisa(self):
        api.canvas_publicar(_canvas(CAJA))
        v = json.loads(api.leer_canvas())["version"]
        api.canvas_publicar(_canvas({"caja": dict(CAJA["caja"], params={"size_x": "300"})}))
        antes = api._PENDIENTE["version"]
        r = json.loads(api.aplicar_texto("caja = mesh_sphere\n", v))
        self.assertTrue(r["conflicto"])
        self.assertEqual(r["texto"], "caja = mesh_box size_x=300\n")
        self.assertEqual(api._PENDIENTE["version"], antes, "un conflicto no puede llegar al canvas")

    def test_aplicar_sin_correr_lo_manda_al_canvas_y_devuelve_la_version_nueva(self):
        api.canvas_publicar(_canvas(CAJA))
        v = json.loads(api.leer_canvas())["version"]
        r = json.loads(api.aplicar_texto("caja = mesh_box\nn = mesh_normals @caja\n", v))
        self.assertFalse(r["conflicto"])
        self.assertTrue(r["ok"], r["errores"])
        # Lo que el agente lee ahora es lo que mandó, aunque el Graph todavía no lo haya cargado.
        leido = json.loads(api.leer_canvas())
        self.assertEqual(leido["texto"], "caja = mesh_box\nn = mesh_normals @caja\n")
        self.assertEqual(leido["version"], r["version"])

    def test_el_canvas_que_vuelve_a_publicar_lo_mismo_no_genera_conflicto(self):
        api.canvas_publicar(_canvas(CAJA))
        r = json.loads(api.aplicar_texto("caja = mesh_box\nn = mesh_normals @caja\n",
                                         json.loads(api.leer_canvas())["version"]))
        # El Graph levanta el buzón y republica el mismo grafo con sus posiciones.
        grafo = json.loads(api.canvas_pendiente(str(api._PENDIENTE["visto"])))["graph"]
        api.canvas_pendiente(str(api._PENDIENTE["version"]))
        api.canvas_publicar(grafo)
        r2 = json.loads(api.aplicar_texto("caja = mesh_box size_x=10\nn = mesh_normals @caja\n",
                                          r["version"]))
        self.assertFalse(r2["conflicto"], r2)

    def test_aplicar_y_correr_pasa_por_el_run_del_canvas(self):
        with mock.patch.object(api, "run_graph_json",
                               lambda g: json.dumps({"ok": True, "report": "[caja·mesh_box] ✓",
                                                     "nodes": {"caja": {"estado": "ok"}}})):
            r = json.loads(api.aplicar_texto("caja = mesh_box\n", "", "true"))
        self.assertEqual(r["nodes"], {"caja": {"estado": "ok"}})
        self.assertIn("línea 1 [caja·", r["report"])
        self.assertNotIn("graph", r, "el JSON del canvas no viaja al agente: es ruido")

    def test_un_error_se_devuelve_con_su_linea_y_no_llega_al_canvas(self):
        antes = api._PENDIENTE["version"]
        r = json.loads(api.aplicar_texto("caja = mesh_box\nn = mesh_normals @cajaa\n"))
        self.assertFalse(r["ok"])
        self.assertEqual(r["errores"][0]["linea"], 2)
        self.assertEqual(api._PENDIENTE["version"], antes)


class Ayuda(unittest.TestCase):
    def test_sin_filtro_la_sintaxis_y_las_categorias(self):
        t = api.ayuda_texto("")
        self.assertIn("nombre = verbo", t)
        self.assertIn("Mesh (", t)

    def test_un_verbo_da_su_firma(self):
        self.assertTrue(api.ayuda_texto("curve_smooth").startswith("curve_smooth @S → S"))

    def test_una_palabra_busca(self):
        self.assertIn("mesh_weld", api.ayuda_texto("weld"))

    def test_nada_coincide_lo_dice(self):
        self.assertIn("nada coincide", api.ayuda_texto("zzzzqq"))


class PuertaHttp(_Estado):
    """`POST /api/<función>` sobre un servidor HTTP de verdad, en un hilo."""

    def setUp(self):
        super().setUp()
        self.srv = web.http.server.ThreadingHTTPServer(("127.0.0.1", 0), web._Handler)
        threading.Thread(target=self.srv.serve_forever, kwargs={"poll_interval": 0.02},
                         daemon=True).start()
        self.url = f"http://127.0.0.1:{self.srv.server_address[1]}"
        self._directo = mock.patch.object(serve, "en_game_thread", lambda thunk, timeout=0: thunk())
        self._directo.start()

    def tearDown(self):
        self._directo.stop()
        self.srv.shutdown()
        self.srv.server_close()
        super().tearDown()

    def _post(self, ruta, cuerpo):
        req = urllib.request.Request(self.url + ruta, data=json.dumps(cuerpo).encode(), method="POST")
        with urllib.request.urlopen(req, timeout=5) as r:
            return json.loads(r.read())

    def test_una_funcion_publica_responde(self):
        api.canvas_publicar(_canvas(CAJA))
        r = json.loads(self._post("/api/leer_canvas", {"args": []})["resultado"])
        self.assertEqual(r["texto"], "caja = mesh_box\n")

    def test_los_argumentos_llegan_en_orden(self):
        r = json.loads(self._post("/api/aplicar_texto", {"args": ["caja = mesh_box\n", "", "false"]})
                       ["resultado"])
        self.assertTrue(r["ok"], r)

    def test_lo_que_no_esta_en_la_lista_blanca_no_se_llama(self):
        with self.assertRaises(urllib.error.HTTPError) as e:
            self._post("/api/canvas_publicar", {"args": ["{}"]})
        with e.exception as respuesta:
            self.assertEqual(respuesta.code, 404)
            self.assertIn("leer_canvas", json.loads(respuesta.read())["hay"])


if __name__ == "__main__":
    unittest.main()
