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


class PreviewTransactionTests(unittest.TestCase):
    def setUp(self):
        self.subsystem = _ActorSubsystem()
        self.assets: set[str] = set()
        panel._PREVIEW_CONTEXT = None
        panel._PREVIEW_ASSETS_BY_OWNER.clear()

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
        for patcher in reversed(self.patchers):
            patcher.stop()

    @staticmethod
    def _preview_actor(path: str, owner: str):
        actor = _Actor(path)
        original = actor.get_actor_label()
        actor.tags = [panel._TAG_PREVIEW, panel._owner_tag(owner), panel._encode_label(original)]
        actor.set_actor_label(panel._PREFIX_PREVIEW + original)
        return actor

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


if __name__ == "__main__":
    unittest.main()
