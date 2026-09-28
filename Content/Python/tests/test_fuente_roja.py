"""Un nodo rojo corta lo que cuelga de él (tarea `fuente-roja`).

El ejecutor seguía el orden topológico sin mirar atrás: el hijo de un nodo que reventó recibía
`None`, corría igual y fallaba con un `NoneType` que escondía la causa —o, si su verbo tolera una
entrada vacía, hacía su efecto con nada—. Para un LLM que lee el reporte, eso es N errores falsos
tapando el único verdadero.
"""

from __future__ import annotations

import json
import sys
import types
import unittest
from pathlib import Path
from unittest import mock

_unreal_fake = sys.modules.setdefault("unreal", types.ModuleType("unreal"))
if not hasattr(_unreal_fake, "TopLevelAssetPath"):
    _unreal_fake.TopLevelAssetPath = lambda package, name: (package, name)

from jam import graph, tools  # noqa: E402

RAIZ = Path(__file__).resolve().parents[3]


def _revienta(*_a, **_k):
    raise RuntimeError("fuente inválida")


class FuenteRoja(unittest.TestCase):
    def _correr(self):
        """src → mv → mv2, y una rama independiente ok → ok2 que no toca la fuente rota."""
        llamados = []

        def registrar(entrada, **_kw):
            llamados.append(entrada)
            return "MOVE P ✓"

        doc = {"nodes": {
            "src": {"verb": "pts_line", "params": {"count": "4"}},
            "mv": {"verb": "move", "params": {"dx": "50"}},
            "mv2": {"verb": "move", "params": {"dx": "5"}},
            "ok": {"verb": "pts_circle", "params": {}},
            "ok2": {"verb": "jitter", "params": {}},
        }, "edges": [["src", "out", "mv", "in"], ["mv", "out", "mv2", "in"],
                     ["ok", "out", "ok2", "in"]]}
        with mock.patch.dict(tools.REGISTRO["pts_line"], fn=_revienta), \
                mock.patch.dict(tools.REGISTRO["move"], fn=registrar):
            reporte, por_nodo = graph.ejecutar_detalle(graph.JamGraph.from_json(json.dumps(doc)))
        return reporte, por_nodo, llamados

    def test_la_fuente_queda_roja(self):
        _r, por_nodo, _l = self._correr()
        self.assertEqual(por_nodo["src"]["estado"], "error")

    def test_los_dependientes_no_corren(self):
        _r, por_nodo, llamados = self._correr()
        self.assertEqual(llamados, [], "un dependiente corrió con la entrada de un nodo roto")
        self.assertEqual(por_nodo["mv"]["estado"], "cancelado")
        self.assertEqual(por_nodo["mv2"]["estado"], "cancelado")

    def test_el_nieto_nombra_la_fuente_original(self):
        _r, por_nodo, _l = self._correr()
        self.assertIn("«src»", por_nodo["mv2"]["texto"])

    def test_un_solo_error_en_el_reporte(self):
        reporte, por_nodo, _l = self._correr()
        self.assertEqual([n for n, v in por_nodo.items() if v["estado"] == "error"], ["src"])
        self.assertEqual(reporte.count("[error]"), 1, reporte)

    def test_una_rama_independiente_corre_igual(self):
        _r, por_nodo, _l = self._correr()
        self.assertNotIn(por_nodo["ok2"]["estado"], ("cancelado", "error"), por_nodo["ok2"])

    def test_slate_pinta_el_estado_que_emite_el_cerebro(self):
        """Sin esto el nodo cancelado se pinta como «todavía no corrió»: un silencio más."""
        cpp = (RAIZ / "Source/JamEditor/Private/SJamGraphNode.cpp").read_text(encoding="utf-8")
        for funcion in ("FString SJamGraphNode::StateGlyph", "FLinearColor SJamGraphNode::StateColor"):
            cuerpo = cpp.split(funcion)[1].split("\n}")[0]
            self.assertIn('ResultState == TEXT("cancelado")', cuerpo, funcion)
        self.assertIn('LOCTEXT("VeredictoCancelado"', cpp)


if __name__ == "__main__":
    unittest.main()
