from __future__ import annotations

import sys
import types
import unittest
from unittest import mock

# `panel` sólo usa Unreal al ejecutar sus adaptadores. Para probar la máquina de estados de Preview
# inyectamos un módulo mínimo y actores falsos; la suite sigue siendo headless.
_unreal_fake = sys.modules.setdefault("unreal", types.ModuleType("unreal"))
if not hasattr(_unreal_fake, "TopLevelAssetPath"):
    _unreal_fake.TopLevelAssetPath = lambda package, name: (package, name)
if not hasattr(_unreal_fake, "PCGComponent"):
    _unreal_fake.PCGComponent = type("PCGComponent", (), {})

from jam import panel  # noqa: E402


class _Location:
    x = 1.0
    y = 2.0
    z = 3.0


class _Asset:
    def __init__(self, path: str):
        self.path = path

    def get_path_name(self):
        return self.path + "." + self.path.rsplit("/", 1)[-1]


class _PCGComponent:
    def __init__(self, graph=None):
        self.graph = graph
        self.generated = 0

    def get_graph(self):
        return self.graph

    def set_graph(self, graph):
        self.graph = graph

    def modify(self):
        return True

    def generate(self, force):
        self.generated += int(bool(force))


class _Actor:
    def __init__(self, path: str, tags=(), component=None):
        self.path = path
        self.tags = list(tags)
        self.label = path.rsplit("/", 1)[-1]
        self.component = component

    def get_path_name(self):
        return self.path

    def get_actor_label(self):
        return self.label

    def set_actor_label(self, label):
        self.label = str(label)

    def get_component_by_class(self, component_class):
        return self.component

    def modify(self):
        return True

    def get_actor_location(self):
        return _Location()


class _ActorSubsystem:
    def __init__(self, actors=()):
        self.actors = list(actors)

    def get_all_level_actors(self):
        return list(self.actors)

    def destroy_actor(self, actor):
        self.actors.remove(actor)


class _ArnesPreview:
    """El arnés falso compartido. Va aparte de los TestCase para que heredarlo no reejecute la
    suite del vecino: una clase de tests que hereda de otra corre también todos sus casos."""

    def setUp(self):
        self.subsystem = _ActorSubsystem()
        self.assets: set[str] = set()
        panel._PREVIEW_CONTEXT = None
        panel._PREVIEW_ASSETS_BY_OWNER.clear()
        panel._PREVIEW_EFFECTS_BY_OWNER.clear()

        def delete_asset(path):
            self.assets.discard(path)
            return True

        def rename_asset(source, destination):
            if source not in self.assets or destination in self.assets:
                return False
            self.assets.remove(source)
            self.assets.add(destination)
            return True

        self.patchers = [
            mock.patch.object(panel, "_actor_sub", return_value=self.subsystem),
            mock.patch.object(panel, "_tags_de", side_effect=lambda actor: list(actor.tags)),
            mock.patch.object(panel, "_set_tags",
                              side_effect=lambda actor, tags: setattr(actor, "tags", list(tags))),
            mock.patch.object(panel, "_seleccionar"),
            mock.patch.object(panel, "_asset_exists", side_effect=lambda path: path in self.assets),
            mock.patch.object(panel, "_asset_delete", side_effect=delete_asset),
            mock.patch.object(panel, "_asset_rename", side_effect=rename_asset),
            mock.patch.object(panel, "_asset_load",
                              side_effect=lambda path: _Asset(path) if path in self.assets else None),
        ]
        for patcher in self.patchers:
            patcher.start()

    def tearDown(self):
        panel._PREVIEW_CONTEXT = None
        panel._PREVIEW_ASSETS_BY_OWNER.clear()
        panel._PREVIEW_EFFECTS_BY_OWNER.clear()
        for patcher in reversed(self.patchers):
            patcher.stop()

    @staticmethod
    def _preview_actor(path: str, owner: str):
        actor = _Actor(path)
        original = actor.get_actor_label()
        actor.tags = [panel._TAG_PREVIEW, panel._owner_tag(owner), panel._encode_label(original)]
        actor.set_actor_label(panel._PREFIX_PREVIEW + original)
        return actor


class PreviewTransactionTests(_ArnesPreview, unittest.TestCase):
    def test_success_replaces_only_the_same_owner_preview(self):
        old_dash = self._preview_actor("/Level/OldDash", "dash")
        graph = self._preview_actor("/Level/Graph", "graph")
        self.subsystem.actors.extend([old_dash, graph])

        def run(_widget):
            self.subsystem.actors.append(_Actor("/Level/NewDash"))
            return "tool ok"

        report = panel._preview(run, owner="dash")
        new_dash = next(a for a in self.subsystem.actors if a.path == "/Level/NewDash")

        self.assertNotIn(old_dash, self.subsystem.actors)
        self.assertIn(graph, self.subsystem.actors)
        self.assertIn(panel._TAG_PREVIEW, new_dash.tags)
        self.assertEqual(panel._owner_de(new_dash), "dash")
        self.assertEqual(new_dash.get_actor_label(), "prev_NewDash")
        self.assertIn("reemplazó 1", report)

    def test_runtime_effect_is_replaced_and_discarded_with_its_owner(self):
        calls = []

        def first(_widget):
            panel.registrar_efecto_preview(
                lambda: calls.append("discard first"), descripcion="primero")
            return "first"

        def second(_widget):
            panel.registrar_efecto_preview(
                lambda: calls.append("discard second"), descripcion="segundo")
            return "second"

        panel._preview(first, owner="graph")
        self.assertTrue(panel.hay_preview("graph"))
        panel._preview(second, owner="graph")
        self.assertEqual(calls, ["discard first"])

        report = panel._h_descartar(owner="graph")

        self.assertEqual(calls, ["discard first", "discard second"])
        self.assertIn("1 efecto(s) runtime liberado(s)", report)
        self.assertFalse(panel.hay_preview("graph"))

    def test_failed_preview_rolls_back_new_runtime_effect_and_preserves_previous(self):
        calls = []

        panel._preview(lambda _w: (
            panel.registrar_efecto_preview(
                lambda: calls.append("old"), descripcion="anterior") or "ok"),
            owner="graph")

        def fail(_widget):
            panel.registrar_efecto_preview(
                lambda: calls.append("new"), descripcion="nuevo")
            raise RuntimeError("fallo deliberado")

        report = panel._preview(fail, owner="graph")

        self.assertIn("PREVIEW revertida", report)
        self.assertEqual(calls, ["new"])
        self.assertTrue(panel.hay_preview("graph"))
        panel._h_descartar(owner="graph")
        self.assertEqual(calls, ["new", "old"])

    def test_exception_rolls_back_new_actors_and_preserves_previous_preview(self):
        previous = self._preview_actor("/Level/Previous", "graph")
        self.subsystem.actors.append(previous)
        staged = []

        def fail(_widget):
            temp = panel.preview_asset_path("/Game/JamPCG/Partial")
            staged.append(temp)
            self.assets.add(temp)
            self.subsystem.actors.append(_Actor("/Level/Partial"))
            raise RuntimeError("boom")

        report = panel._preview(fail, owner="graph")

        self.assertEqual(self.subsystem.actors, [previous])
        self.assertNotIn(staged[0], self.assets)
        self.assertIn("PREVIEW revertida", report)
        self.assertIn("ROLLBACK ✓", report)

    def test_confirm_recovers_preview_from_persistent_tags(self):
        actor = self._preview_actor("/Level/Recovered", "graph")
        self.subsystem.actors.append(actor)

        report = panel._h_confirmar(owner="graph")

        self.assertIn(actor, self.subsystem.actors)
        self.assertNotIn(panel._TAG_PREVIEW, actor.tags)
        self.assertIsNone(panel._owner_de(actor))
        self.assertEqual(actor.get_actor_label(), "bake_Recovered")
        self.assertIn("BAKE/CONFIRMADO [graph] ✓", report)
        self.assertIn("no hay preview", panel._h_descartar(owner="graph"))
        self.assertIn(actor, self.subsystem.actors)

    def test_discard_is_scoped_and_tolerates_missing_actors(self):
        dash = self._preview_actor("/Level/Dash", "dash")
        graph = self._preview_actor("/Level/Graph", "graph")
        self.subsystem.actors.extend([dash, graph])

        report = panel._h_descartar(owner="graph")

        self.assertEqual(self.subsystem.actors, [dash])
        self.assertIn("1 piezas borradas", report)
        # Si el actor restante se borró a mano, consultar/confirmar no explota con una referencia vieja.
        self.subsystem.actors.clear()
        self.assertFalse(panel.hay_preview("dash"))
        self.assertIn("no hay preview", panel._h_confirmar(owner="dash"))

    def test_discard_removes_the_staged_asset_recorded_on_the_actor(self):
        staged = []

        def run(_widget):
            temp = panel.preview_asset_path("/Game/JamPCG/Forest")
            staged.append(temp)
            self.assets.add(temp)
            self.subsystem.actors.append(_Actor("/Level/PCGVolume"))
            return "pcg ok"

        panel._preview(run, owner="graph")
        actor = self.subsystem.actors[0]

        self.assertIn(staged[0], self.assets)
        self.assertEqual(panel._asset_records([actor]), [
            {"temp": staged[0], "final": "/Game/JamPCG/Forest"},
        ])

        report = panel._h_descartar(owner="graph")

        self.assertEqual(self.subsystem.actors, [])
        self.assertNotIn(staged[0], self.assets)
        self.assertIn("1 piezas borradas", report)

    def test_asset_only_preview_can_bake_without_a_marker_actor(self):
        final = "/Game/Jam/Nanite/SM_Rock_Nanite"
        staged = []

        def run(_widget):
            temp = panel.preview_asset_path(final)
            staged.append(temp)
            self.assets.add(temp)
            return "nanite ok"

        preview_report = panel._preview(run, owner="graph")

        self.assertEqual(self.subsystem.actors, [])
        self.assertTrue(panel.hay_preview("graph"))
        self.assertIn("1 asset(s) temporal(es)", preview_report)

        bake_report = panel._h_confirmar(owner="graph")

        self.assertNotIn(staged[0], self.assets)
        self.assertIn(final, self.assets)
        self.assertFalse(panel.hay_preview("graph"))
        self.assertIn("únicamente Content", bake_report)

    def test_asset_only_preview_can_be_discarded(self):
        final = "/Game/Jam/Nanite/SM_Rock_Nanite"
        staged = []

        def run(_widget):
            temp = panel.preview_asset_path(final)
            staged.append(temp)
            self.assets.add(temp)
            return "nanite ok"

        panel._preview(run, owner="graph")
        report = panel._h_descartar(owner="graph")

        self.assertNotIn(staged[0], self.assets)
        self.assertFalse(panel.hay_preview("graph"))
        self.assertIn("1 asset(s) temporal(es) borrado(s)", report)

    def test_bake_promotes_to_a_unique_path_without_overwriting_content(self):
        final = "/Game/JamPCG/Forest"
        self.assets.add(final)
        staged = []

        def run(_widget):
            temp = panel.preview_asset_path(final)
            staged.append(temp)
            self.assets.add(temp)
            self.subsystem.actors.append(_Actor("/Level/PCGVolume"))
            return "pcg ok"

        panel._preview(run, owner="graph")
        actor = self.subsystem.actors[0]
        report = panel._h_confirmar(owner="graph")

        self.assertNotIn(staged[0], self.assets)
        self.assertIn(final, self.assets)
        self.assertIn(final + "_2", self.assets)
        self.assertNotIn(panel._TAG_PREVIEW, actor.tags)
        self.assertEqual(panel._asset_records([actor]), [])
        self.assertEqual(actor.get_actor_label(), "bake_PCGVolume")
        self.assertIn(final + "_2", report)

    def test_failed_asset_promotion_keeps_preview_available(self):
        staged = []

        def run(_widget):
            temp = panel.preview_asset_path("/Game/JamPCG/Forest")
            staged.append(temp)
            self.assets.add(temp)
            self.subsystem.actors.append(_Actor("/Level/PCGVolume"))
            return "pcg ok"

        panel._preview(run, owner="graph")
        actor = self.subsystem.actors[0]
        with mock.patch.object(panel, "_asset_rename", return_value=False):
            report = panel._h_confirmar(owner="graph")

        self.assertIn("BAKE cancelado", report)
        self.assertIn(staged[0], self.assets)
        self.assertIn(panel._TAG_PREVIEW, actor.tags)
        self.assertEqual(actor.get_actor_label(), "prev_PCGVolume")
        self.assertTrue(panel.hay_preview("graph"))

    def test_failed_asset_deletion_keeps_actor_and_recovery_record(self):
        staged = []

        def run(_widget):
            temp = panel.preview_asset_path("/Game/JamPCG/Forest")
            staged.append(temp)
            self.assets.add(temp)
            self.subsystem.actors.append(_Actor("/Level/PCGVolume"))
            return "pcg ok"

        panel._preview(run, owner="graph")
        actor = self.subsystem.actors[0]
        with mock.patch.object(panel, "_asset_delete", return_value=False):
            report = panel._h_descartar(owner="graph")

        self.assertIn("DESCARTE incompleto", report)
        self.assertIn(actor, self.subsystem.actors)
        self.assertIn(staged[0], self.assets)
        self.assertEqual(actor.get_actor_label(), "prev_PCGVolume")
        self.assertEqual(panel._asset_records([actor]), [
            {"temp": staged[0], "final": "/Game/JamPCG/Forest"},
        ])

    def test_baked_pcg_keeps_final_graph_after_a_later_run_and_discard(self):
        final = "/Game/JamPCG/Forest"
        first_temp = []

        def first_run(_widget):
            temp = panel.preview_asset_path(final)
            first_temp.append(temp)
            self.assets.add(temp)
            component = _PCGComponent(_Asset(temp))
            self.subsystem.actors.append(_Actor("/Level/FirstPCG", component=component))
            return "pcg one"

        panel._preview(first_run, owner="graph")
        baked = self.subsystem.actors[0]
        baked_component = baked.component
        panel._h_confirmar(owner="graph")

        self.assertEqual(baked.get_actor_label(), "bake_FirstPCG")
        self.assertEqual(panel._asset_path(baked_component.get_graph()), final)
        self.assertNotIn(first_temp[0], self.assets)

        second_temp = []

        def second_run(_widget):
            temp = panel.preview_asset_path(final)
            second_temp.append(temp)
            self.assets.add(temp)
            component = _PCGComponent(_Asset(temp))
            self.subsystem.actors.append(_Actor("/Level/SecondPCG", component=component))
            return "pcg two"

        panel._preview(second_run, owner="graph")

        self.assertIn(baked, self.subsystem.actors)
        self.assertEqual(panel._asset_path(baked_component.get_graph()), final)
        self.assertTrue(panel.hay_preview("graph"))

        panel._h_descartar(owner="graph")

        self.assertEqual(self.subsystem.actors, [baked])
        self.assertEqual(panel._asset_path(baked_component.get_graph()), final)
        self.assertIn(final, self.assets)
        self.assertNotIn(second_temp[0], self.assets)

    def test_fracture_runs_stage_new_df_and_gc_without_touching_baked_versions(self):
        finals = [
            "/Game/JamDF/Fractures/DF_Crate",
            "/Game/JamDF/Fractures/GC_Crate",
        ]

        def fracture_run(actor_path, staged):
            def run(_widget):
                for final in finals:
                    temp = panel.preview_asset_path(final)
                    staged.append(temp)
                    self.assets.add(temp)
                self.subsystem.actors.append(_Actor(actor_path))
                return "fracture + place ok"
            return run

        first_staged = []
        panel._preview(fracture_run("/Level/FirstGC", first_staged), owner="graph")
        baked = self.subsystem.actors[0]
        panel._h_confirmar(owner="graph")

        self.assertEqual(baked.get_actor_label(), "bake_FirstGC")
        self.assertTrue(all(final in self.assets for final in finals))
        self.assertTrue(all(temp not in self.assets for temp in first_staged))

        second_staged = []
        panel._preview(fracture_run("/Level/SecondGC", second_staged), owner="graph")

        self.assertIn(baked, self.subsystem.actors)
        self.assertTrue(all(final in self.assets for final in finals))
        self.assertTrue(all(temp in self.assets for temp in second_staged))

        panel._h_descartar(owner="graph")

        self.assertEqual(self.subsystem.actors, [baked])
        self.assertTrue(all(final in self.assets for final in finals))
        self.assertTrue(all(temp not in self.assets for temp in second_staged))


class PingPongDeRanurasTests(_ArnesPreview, unittest.TestCase):
    """El staging alterna entre DOS ranuras por destino en vez de estrenar ruta cada corrida.

    El motivo es medido y está en `preview_asset_path`: borrar el temporal de la vuelta anterior
    costaba 142 ms —cuatro veces escribirlo, y ninguna primitiva del binding lo evita—, así que la
    corrida interactiva dejó de borrar. Lo que estos tests cuidan es que ese ahorro no se haya
    llevado puesta ninguna de las propiedades que el Preview ya garantizaba.
    """

    FINAL = "/Game/Jam/Meshes/SM_Cinta"

    def _correr(self, final=None, fallar=False, actor=None):
        """Una corrida como la de un verbo que hornea: pide ruta staged y escribe ahí."""
        destino = final or self.FINAL
        caja = {}

        def run(_widget):
            caja["temp"] = panel.preview_asset_path(destino)
            self.assets.add(caja["temp"])
            if actor:
                self.subsystem.actors.append(_Actor(actor))
            if fallar:
                raise RuntimeError("el grafo falló después de escribir el asset")
            return "ok"

        caja["reporte"] = panel._preview(run, owner="graph")
        return caja

    def test_dos_corridas_seguidas_usan_ranuras_distintas(self):
        primera = self._correr()
        segunda = self._correr()
        self.assertNotEqual(primera["temp"], segunda["temp"])

    def test_la_tercera_corrida_vuelve_a_pisar_la_primera_ranura(self):
        """Dos ranuras alcanzan: si la tercera estrenara ruta, la basura crecería sin techo."""
        rutas = [self._correr()["temp"] for _ in range(3)]
        self.assertEqual(rutas[0], rutas[2])
        self.assertNotEqual(rutas[0], rutas[1])

    def test_la_corrida_exitosa_NO_borra_el_staged_anterior(self):
        """Es el ahorro entero: lo que la vuelta que viene va a pisar no se borra ahora."""
        primera = self._correr()
        self._correr()
        self.assertIn(primera["temp"], self.assets)

    def test_un_destino_que_el_grafo_dejo_de_producir_SI_se_borra(self):
        """A ese no va a pisarlo nadie: sin esto el ping-pong sería una excusa para dejar basura."""
        viejo = self._correr(final="/Game/Jam/Meshes/SM_Viejo")
        self._correr(final="/Game/Jam/Meshes/SM_Nuevo")
        self.assertNotIn(viejo["temp"], self.assets)

    def test_una_corrida_que_FALLA_deja_intacto_el_Preview_anterior(self):
        """La garantía que el ping-pong existía para no romper.

        Sobrescribir la misma ruta habría sido más simple y también más rápido, pero una corrida
        fallida se habría llevado puesto el Preview bueno de la corrida anterior. Con dos ranuras el
        anterior nunca se toca: lo que se pisa es basura de dos vueltas atrás.
        """
        bueno = self._correr()
        malo = self._correr(fallar=True)

        self.assertIn(bueno["temp"], self.assets, "el Preview anterior tiene que seguir en su ruta")
        self.assertNotEqual(bueno["temp"], malo["temp"])
        self.assertNotIn(malo["temp"], self.assets, "lo nuevo de una corrida fallida se descarta")
        self.assertIn("ROLLBACK", malo["reporte"])

    def test_descartar_barre_la_ranura_vieja_que_el_Run_dejo_en_pie(self):
        """Lo que el Run no borró tiene que llevárselo alguien, o Content acumula para siempre."""
        barridas = []
        with mock.patch.object(panel, "_barrer_ranuras_sobrantes",
                               side_effect=lambda owner: barridas.append(owner)):
            self._correr(actor="/Level/Cinta")
            self._correr(actor="/Level/Cinta2")
            panel._h_descartar(owner="graph")
        self.assertEqual(barridas, ["graph"])

    def test_bake_tambien_barre_la_ranura_vieja(self):
        barridas = []
        with mock.patch.object(panel, "_barrer_ranuras_sobrantes",
                               side_effect=lambda owner: barridas.append(owner)):
            self._correr(actor="/Level/Cinta")
            self._correr(actor="/Level/Cinta2")
            panel._h_confirmar(owner="graph")
        self.assertEqual(barridas, ["graph"])


class RecuperacionDeRanurasTests(unittest.TestCase):
    """Tras recargar Python la memoria no existe y hay DOS temporales por destino en disco.

    Sin un criterio de recencia, Bake promovería los dos y de un Preview saldrían dos assets
    finales. El sello `_ASSET_META_SERIE` es ese criterio.
    """

    def setUp(self):
        self.serie = {}
        self.finales = {}
        self.rutas = []

        def get_metadata_tag(obj, tag):
            ruta = obj.path
            if tag == panel._ASSET_META_OWNER:
                return "graph"
            if tag == panel._ASSET_META_FINAL:
                return self.finales.get(ruta, "")
            if tag == panel._ASSET_META_SERIE:
                return self.serie.get(ruta, "")
            return ""

        biblioteca = types.SimpleNamespace(
            list_assets=lambda base, recursive, include_folder: list(self.rutas),
            get_metadata_tag=get_metadata_tag)
        self.patchers = [
            mock.patch.object(panel.unreal, "EditorAssetLibrary", biblioteca, create=True),
            mock.patch.object(panel, "_asset_load", side_effect=lambda p: _Asset(p)),
        ]
        for p in self.patchers:
            p.start()

    def tearDown(self):
        for p in reversed(self.patchers):
            p.stop()

    def _slot(self, ruta, final, serie):
        self.rutas.append(ruta)
        self.finales[ruta] = final
        self.serie[ruta] = serie

    def test_de_dos_ranuras_del_mismo_destino_gana_la_del_sello_mas_alto(self):
        final = "/Game/Jam/Meshes/SM_Cinta"
        self._slot("/Game/JamPreview/graph/PVA_SM_Cinta", final, "1000.0")
        self._slot("/Game/JamPreview/graph/PVB_SM_Cinta", final, "2000.0")
        recuperados = panel._recover_asset_records("graph")
        self.assertEqual([r["temp"] for r in recuperados],
                         ["/Game/JamPreview/graph/PVB_SM_Cinta"])

    def test_destinos_distintos_se_recuperan_los_dos(self):
        """Colapsar por destino no puede comerse previews que no compiten entre sí."""
        self._slot("/Game/JamPreview/graph/PVA_SM_Uno", "/Game/Jam/SM_Uno", "1000.0")
        self._slot("/Game/JamPreview/graph/PVA_SM_Dos", "/Game/Jam/SM_Dos", "1000.0")
        self.assertEqual(len(panel._recover_asset_records("graph")), 2)

    def test_un_asset_sin_sello_pierde_contra_uno_sellado(self):
        """Un temporal escrito por la versión anterior de Jam: no tiene sello y es el viejo."""
        final = "/Game/Jam/Meshes/SM_Cinta"
        self._slot("/Game/JamPreview/graph/PV_abc123_SM_Cinta", final, "")
        self._slot("/Game/JamPreview/graph/PVA_SM_Cinta", final, "1000.0")
        self.assertEqual([r["temp"] for r in panel._recover_asset_records("graph")],
                         ["/Game/JamPreview/graph/PVA_SM_Cinta"])


if __name__ == "__main__":
    unittest.main()
