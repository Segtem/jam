"""Un parámetro mal escrito o una opción fuera de la lista es un ERROR, no un default en silencio.

Tarea `dsl-parametros`: `scatter SM_Rock cownt=10` corría en verde con `count=24`, y `pattern=poison`
pasaba hasta adentro del verbo. Se prueba por las tres rutas que leen params escritos: la consola
(`panel.ejecutar_dsl`, que es lo que llaman `api.run` y la Dash Bar), el Compile del Graph y el
preflight de Flow. En las tres el mensaje nombra lo que quiso decir.
"""

from __future__ import annotations

import sys
import types
import unittest
from unittest import mock

_unreal_fake = sys.modules.setdefault("unreal", types.ModuleType("unreal"))
if not hasattr(_unreal_fake, "TopLevelAssetPath"):
    _unreal_fake.TopLevelAssetPath = lambda package, name: (package, name)

from jam import flow, graph, panel, tools  # noqa: E402


class Consola(unittest.TestCase):
    def _correr(self, linea):
        corridas = []
        # `menu` sólo lo usa `verify` y arrastra módulos que necesitan el motor de verdad.
        with mock.patch.dict(sys.modules, {"jam.menu": types.ModuleType("jam.menu")}), \
                mock.patch.object(panel, "_resolver_asset", lambda n: n or "SM_Rock"), \
                mock.patch.object(panel, "_preview", lambda fn, *a, **k: corridas.append(fn) or "✓"):
            return panel.ejecutar_dsl(linea), corridas

    def test_un_parametro_mal_escrito_no_corre_y_sugiere(self):
        texto, corridas = self._correr("scatter SM_Rock cownt=10")
        self.assertEqual(corridas, [], "corrió con el default: el silencio que la tarea cierra")
        self.assertIn("[error]", texto)
        self.assertIn("«cownt»", texto)
        self.assertIn("¿quisiste decir «count»?", texto)

    def test_una_opcion_invalida_no_corre_y_sugiere(self):
        texto, corridas = self._correr("scatter SM_Rock pattern=poison")
        self.assertEqual(corridas, [])
        self.assertIn("¿quisiste decir «poisson»?", texto)
        self.assertIn("hexagonal", texto)  # lista las opciones

    def test_un_numero_que_no_es_numero_no_corre(self):
        texto, corridas = self._correr("scatter SM_Rock count=muchas")
        self.assertEqual(corridas, [])
        self.assertIn("count", texto)

    def test_los_verbos_sin_spawn_tambien_rechazan(self):
        # `pivot` no pasa por preview: su rama descartaba los errores en otra variable.
        with mock.patch.dict(tools.REGISTRO["pivot"], fn=lambda *a, **k: "corrió"):
            texto, _ = self._correr("pivot SM_Rock anchr=base")
        self.assertNotEqual(texto, "corrió")
        self.assertIn("¿quisiste decir «anchor»?", texto)

    def test_el_error_de_params_no_lo_tapa_una_biblioteca_vacia(self):
        with mock.patch.dict(sys.modules, {"jam.menu": types.ModuleType("jam.menu")}), \
                mock.patch.object(panel, "_resolver_asset", lambda n: None):
            texto = panel.ejecutar_dsl("scatter cownt=10")
        self.assertIn("¿quisiste decir «count»?", texto)

    def test_una_linea_bien_escrita_sigue_corriendo(self):
        texto, corridas = self._correr("scatter SM_Rock count=10 pattern=grid n=3")
        self.assertEqual(len(corridas), 1, texto)


class CompileDelGraph(unittest.TestCase):
    def _errores(self, params):
        g = graph.JamGraph.from_json(
            '{"nodes": {"s": {"verb": "scatter", "params": %s}}, "edges": []}'
            % __import__("json").dumps(params))
        with self.assertRaises(graph.GraphValidationError) as ctx:
            graph.compilar(g, registro=tools.REGISTRO)
        return str(ctx.exception)

    def test_parametro_desconocido_sugiere(self):
        self.assertIn("¿quisiste decir «count»?", self._errores({"cownt": "10"}))

    def test_opcion_invalida_es_error_de_compile(self):
        self.assertIn("«poison» no es una opción", self._errores({"pattern": "poison"}))


class PreflightDeFlow(unittest.TestCase):
    def _diag(self, params):
        f = flow.Flow.from_json(
            '{"nodes": {"s": {"kind": "source_surface", "params": %s}}, "edges": []}'
            % __import__("json").dumps(params))
        return " ".join(f.validar().get("s", []))

    def test_parametro_desconocido_sugiere(self):
        self.assertIn("¿quisiste decir «count»?", self._diag({"cownt": "10"}))

    def test_opcion_invalida(self):
        self.assertIn("«poison» no es una opción", self._diag({"pattern": "poison"}))

    def test_una_expresion_no_se_juzga_como_opcion(self):
        self.assertNotIn("no es una opción", self._diag({"pattern": "=modo"}))


if __name__ == "__main__":
    unittest.main()
