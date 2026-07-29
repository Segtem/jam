"""El rayo que busca el suelo no puede apoyarse en lo que Jam todavía no fijó.

EL BUG: colocar «sobre la superficie» y darle Run varias veces hacía SUBIR el modelo, un cuerpo por
corrida. La causa no está en `place` sino en la combinación de dos cosas correctas por separado:

* el Preview es transaccional a propósito — el anterior sigue vivo hasta que el nuevo termina bien,
  para poder revertir sin perder nada;
* `place(surface=True)` raycastea para encontrar el piso.

Así que en el momento del raycast la copia anterior está ahí, y el rayo la encuentra a ella. Cada
Run apoyaba el modelo encima del Run anterior.

Al confirmar, los tags se sacan y el actor pasa a ser escena normal: desde ahí SÍ es suelo válido,
que es lo correcto — apoyarse sobre algo que uno ya fijó es lo que uno quiere.
"""

from __future__ import annotations

import sys
import types
import unittest

_unreal = sys.modules.setdefault("unreal", types.ModuleType("unreal"))
if not hasattr(_unreal, "TopLevelAssetPath"):
    _unreal.TopLevelAssetPath = lambda package, name: (package, name)

from jam import ue  # noqa: E402


class ActorFalso:
    def __init__(self, nombre, tags):
        self.nombre = nombre
        self._tags = tags

    def get_editor_property(self, clave):
        if clave == "tags":
            return self._tags
        raise KeyError(clave)


class ActoresDeJamTests(unittest.TestCase):
    def setUp(self):
        self._original = ue.actores_nivel

    def tearDown(self):
        ue.actores_nivel = self._original

    def poblar(self, actores):
        ue.actores_nivel = lambda: actores

    def test_a_preview_actor_is_skipped(self):
        """Es EL caso del bug: la copia del Run anterior todavía está en el nivel."""
        preview = ActorFalso("preview", ["jam:preview", "jam:preview-owner=graph"])
        suelo = ActorFalso("suelo", [])
        self.poblar([preview, suelo])
        self.assertEqual([a.nombre for a in ue.actores_de_jam()], ["preview"])

    def test_ghosts_and_gizmos_are_skipped_too(self):
        """Un fantasma es una AYUDA VISUAL. Apoyarse en él sería apoyarse en algo que ni siquiera
        va a existir."""
        self.poblar([ActorFalso("fantasma", ["jam:ghost"]),
                     ActorFalso("gizmo", ["jam:gizmo"]),
                     ActorFalso("piso", [])])
        self.assertEqual(sorted(a.nombre for a in ue.actores_de_jam()), ["fantasma", "gizmo"])

    def test_a_confirmed_actor_is_valid_ground_again(self):
        """Confirmar saca los tags. Desde ahí es escena normal, y apoyarse encima es correcto: es
        justamente lo que uno quiere al apilar algo sobre lo que ya puso."""
        self.poblar([ActorFalso("ya_confirmado", ["Jam", "otra-cosa"]), ActorFalso("piso", [])])
        self.assertEqual(ue.actores_de_jam(), [])

    def test_an_empty_level_is_not_an_error(self):
        self.poblar([])
        self.assertEqual(ue.actores_de_jam(), [])

    def test_an_actor_without_readable_tags_is_treated_as_scene(self):
        """Fallar CERRADO: si no se pueden leer los tags, el actor cuenta como escena y el rayo se
        apoya en él. Al revés —tratarlo como de Jam— haría desaparecer suelo real."""
        class SinTags:
            nombre = "raro"

            def get_editor_property(self, clave):
                raise RuntimeError("sin tags")

        self.poblar([SinTags()])
        self.assertEqual(ue.actores_de_jam(), [])


class ContratoDelRayoTests(unittest.TestCase):
    def test_the_ray_actually_hands_the_jam_actors_to_the_engine(self):
        """La prueba que faltaba: que el rayo USE la lista, no sólo que la sepa calcular.

        Se intercepta la llamada al motor y se mira QUÉ se le pasa. No es mockear nuestra propia
        lógica —eso no verificaría nada—: es verificar el argumento exacto que cruza la frontera,
        que es lo único que decide si el rayo pega en el preview anterior o en el piso.
        """
        preview = ActorFalso("preview", ["jam:preview"])
        piso = ActorFalso("piso", [])
        original_actores, original_mundo = ue.actores_nivel, ue._mundo
        original_sl = getattr(_unreal, "SystemLibrary", None)
        visto = {}

        class SystemLibraryFalsa:
            @staticmethod
            def line_trace_single(mundo, a, b, canal, complejo, ignorar, dibujo, trazar):
                visto["ignorar"] = list(ignorar)
                return None      # «sin impacto»: alcanza, lo que se mide es el argumento

        try:
            ue.actores_nivel = lambda: [preview, piso]
            ue._mundo = lambda: None
            _unreal.SystemLibrary = SystemLibraryFalsa
            _unreal.Vector = lambda x, y, z: (x, y, z)
            _unreal.TraceTypeQuery = types.SimpleNamespace(TRACE_TYPE_QUERY1=0)
            _unreal.DrawDebugTrace = types.SimpleNamespace(NONE=0)
            ue.raycast(0.0, 0.0)
            self.assertIn(preview, visto["ignorar"],
                          "el rayo se va a apoyar en el preview anterior: el modelo SUBE por Run")
            self.assertNotIn(piso, visto["ignorar"], "el piso real tiene que seguir siendo suelo")
        finally:
            ue.actores_nivel, ue._mundo = original_actores, original_mundo
            if original_sl is not None:
                _unreal.SystemLibrary = original_sl

    def test_the_ray_ignores_jam_actors_by_default(self):
        """Por DEFECTO, porque quien pide «apoyalo en la superficie» quiere el suelo. Que haya que
        acordarse de pasar un flag es cómo el bug duró tanto."""
        import inspect

        firma = inspect.signature(ue.raycast)
        self.assertIs(firma.parameters["ignorar_jam"].default, True)
        self.assertIs(inspect.signature(ue.raycast_entre).parameters["ignorar_jam"].default, True)

    def test_the_caller_can_still_ask_for_everything(self):
        """Queda la puerta para el caso contrario —medir contra lo que hay, previews incluidos—,
        pero explícita."""
        import inspect

        self.assertIn("ignorar_jam", inspect.signature(ue.raycast).parameters)


if __name__ == "__main__":
    unittest.main()
