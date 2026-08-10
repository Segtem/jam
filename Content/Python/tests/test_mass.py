"""Primera vertical MassEntity: contrato F → F y puente C++ runtime."""

from __future__ import annotations

import json
from pathlib import Path
import sys
import types
import unittest
from unittest import mock

unreal = sys.modules.setdefault("unreal", types.ModuleType("unreal"))
if not hasattr(unreal, "TopLevelAssetPath"):
    unreal.TopLevelAssetPath = lambda package, name: (package, name)

from jam import api, curve, mass_core, panel, ribbon, tools, ue  # noqa: E402


ROOT = Path(__file__).resolve().parents[3]


def frame(x=0.0, y=0.0, z=0.0, *, scale=1.0):
    return curve.CurveFrame(
        (x, y, z), (1.0, 0.0, 0.0), (0.0, 0.0, 1.0), 0.0, scale=scale)


def frames(*items):
    return curve.FrameSet(tuple(items), parent_count=1)


class MassCoreTests(unittest.TestCase):
    def test_mc_only_exists_after_a_spatial_massgameplay_template_is_verified(self):
        path = "/Game/Jam/Mass/MC_Ratas.MC_Ratas"
        facts = {"ok": True, "config_path": path, "trait_count": 1,
                 "template_valid": True, "has_transform": True}

        config = mass_core.make_config(path, facts)["config"]
        self.assertEqual(config, mass_core.MassConfig(path))
        for field, bad in (("trait_count", 0), ("template_valid", False),
                           ("has_transform", False)):
            self.assertIn("error", mass_core.make_config(path, {**facts, field: bad}))

    def test_mc_ism_requires_stationary_mesh_fragments_and_monotonic_lod(self):
        path = "/Jam/Mass/MC_JamAmbientISM.MC_JamAmbientISM"
        facts = {
            "ok": True, "config_path": path, "trait_count": 2,
            "template_valid": True, "has_transform": True,
            "has_representation": True, "has_lod": True, "has_viewer": True,
            "has_actor_fragment": True, "stationary": True,
            "mesh_paths": ["/Engine/BasicShapes/Sphere.Sphere"],
            "lod_representation": ["StaticMeshInstance", "StaticMeshInstance",
                                   "StaticMeshInstance", "None"],
            "lod_distances": [0.0, 1500.0, 3500.0, 8000.0],
            "lod_max_counts": [2147483647, 2147483647, 2147483647, 2147483647],
        }

        config = mass_core.make_config(path, facts, require_ism=True)["config"]
        self.assertEqual(config.representation, "ism")
        self.assertEqual(config.mesh_paths, ("/Engine/BasicShapes/Sphere.Sphere",))
        self.assertEqual(config.lod_distances, (0.0, 1500.0, 3500.0, 8000.0))
        spec = mass_core.make_spec(frames(frame()), config=config)["spec"]
        self.assertEqual(spec.representation, "ism")
        for field, bad in (("stationary", False), ("mesh_paths", []),
                           ("has_lod", False),
                           ("lod_distances", [0.0, 3500.0, 1500.0, 8000.0]),
                           ("lod_distances", [0.0, 1500.0, 3500.0, float("inf")])):
            with self.subTest(field=field):
                self.assertIn("error", mass_core.make_config(
                    path, {**facts, field: bad}, require_ism=True))

    def test_mc_can_require_a_measured_per_tier_lod_budget(self):
        path = "/Jam/Mass/MC_JamAmbientBudget.MC_JamAmbientBudget"
        facts = {
            "ok": True, "config_path": path, "trait_count": 2,
            "template_valid": True, "has_transform": True,
            "has_representation": True, "has_lod": True, "has_viewer": True,
            "has_actor_fragment": True, "stationary": True,
            "mesh_paths": ["/Engine/BasicShapes/Sphere.Sphere"],
            "lod_representation": ["StaticMeshInstance", "StaticMeshInstance",
                                   "StaticMeshInstance", "None"],
            "lod_distances": [0.0, 1500.0, 3500.0, 8000.0],
            "lod_max_counts": [1, 1, 1, 2147483647],
        }

        config = mass_core.make_config(
            path, facts, require_lod_budget=True)["config"]
        self.assertEqual(config.lod_max_counts, (1, 1, 1, 2147483647))
        for counts in ([2147483647] * 4, [1, 1, 1, 1], [1, -1, 1, 2147483647],
                       [True, 1, 1, 2147483647], [1, 1, 2147483647]):
            with self.subTest(counts=counts):
                self.assertIn("error", mass_core.make_config(
                    path, {**facts, "lod_max_counts": counts},
                    require_lod_budget=True))

    def test_mc_patrol_requires_dynamic_ism_positive_parameters_and_fragment(self):
        path = "/Jam/Mass/MC_JamAmbientPatrol.MC_JamAmbientPatrol"
        facts = {
            "ok": True, "config_path": path, "trait_count": 3,
            "template_valid": True, "has_transform": True,
            "has_representation": True, "has_lod": True, "has_viewer": True,
            "has_actor_fragment": True, "stationary": False, "moving_ism": True,
            "has_patrol": True, "patrol_speed": 800.0, "patrol_radius": 25.0,
            "mesh_paths": ["/Engine/BasicShapes/Sphere.Sphere"],
            "lod_representation": ["StaticMeshInstance", "StaticMeshInstance",
                                   "StaticMeshInstance", "None"],
            "lod_distances": [0.0, 1500.0, 3500.0, 8000.0],
        }

        config = mass_core.make_config(path, facts, require_patrol=True)["config"]
        self.assertEqual((config.representation, config.behavior),
                         ("ism_dynamic", "patrol"))
        self.assertEqual((config.patrol_speed, config.patrol_radius), (800.0, 25.0))
        for field, bad in (("moving_ism", False), ("has_patrol", False),
                           ("patrol_speed", 0.0), ("patrol_radius", float("inf"))):
            with self.subTest(field=field):
                self.assertIn("error", mass_core.make_config(
                    path, {**facts, field: bad}, require_patrol=True))

    def test_prepare_accepts_finite_frames_and_computes_the_expected_sum(self):
        result = mass_core.prepare(frames(frame(10, 20, 30), frame(-2, 4, 8, scale=2)))
        self.assertNotIn("error", result)
        self.assertEqual(len(result["batch"]), 2)
        self.assertEqual(result["batch"].position_sum, (8.0, 24.0, 38.0))

    def test_prepare_rejects_empty_non_finite_non_positive_and_over_budget_inputs(self):
        failures = (
            mass_core.prepare(object()),
            mass_core.prepare(frames()),
            mass_core.prepare(frames(frame(float("nan"), 0, 0))),
            mass_core.prepare(frames(frame(scale=0))),
            mass_core.prepare(frames(*(frame(i, 0, 0) for i in range(4097)))),
        )
        self.assertTrue(all("error" in result for result in failures))
        self.assertIn("4096", failures[-1]["error"])

    def test_judge_discriminates_count_transform_and_cleanup_mutations(self):
        batch = mass_core.prepare(frames(frame(10, 20, 30), frame(-2, 4, 8)))["batch"]
        facts = {
            "ok": True, "requested": 2, "created": 2, "valid_before": 2,
            "valid_after": 0, "same_archetype": 2, "transform_mismatches": 0,
            "input_sum_x": 8.0, "input_sum_y": 24.0, "input_sum_z": 38.0,
            "observed_sum_x": 8.0, "observed_sum_y": 24.0, "observed_sum_z": 38.0,
        }
        self.assertTrue(mass_core.judge(batch, facts)["ok"])
        for field, bad in (("created", 1), ("valid_after", 1), ("observed_sum_x", 9.0)):
            with self.subTest(field=field):
                mutated = {**facts, field: bad}
                self.assertFalse(mass_core.judge(batch, mutated)["ok"])

    def test_ms_is_a_bounded_durable_recipe_without_unreal_handles(self):
        result = mass_core.make_spec(
            frames(frame(10, 20, 30), frame(-2, 4, 8)),
            config_path="/Game/Mass/Ratas", seed=19, budget=8)

        spec = result["spec"]
        self.assertIsInstance(spec, mass_core.MassSpec)
        self.assertEqual((len(spec), spec.seed, spec.budget), (2, 19, 8))
        self.assertEqual(spec.config_path, "/Game/Mass/Ratas")
        self.assertFalse(any("unreal" in type(value).__module__ for value in spec.frames))

    def test_mass_spec_rejects_a_population_over_its_own_budget(self):
        result = mass_core.make_spec(frames(frame(), frame(1)), budget=1)

        self.assertIn("presupuesto de 1", result["error"])

    def test_mass_spec_accepts_mc_and_rejects_ambiguous_or_invalid_configs(self):
        config = mass_core.MassConfig("/Game/Jam/Mass/MC_Ratas.MC_Ratas")
        spec = mass_core.make_spec(frames(frame()), config=config)["spec"]

        self.assertEqual(spec.config_path, config.config_path)
        self.assertIn("MC válido", mass_core.make_spec(frames(frame()), config=object())["error"])
        self.assertIn("distintas", mass_core.make_spec(
            frames(frame()), config=config,
            config_path="/Game/Jam/Mass/Otra.Otra")["error"])

    def test_spawn_only_publishes_mh_after_identity_world_and_counts_match(self):
        spec = mass_core.make_spec(frames(frame(), frame(1)))["spec"]
        facts = {"ok": True, "population_id": "p1", "world_id": "w1",
                 "requested": 2, "created": 2, "valid": 2}

        handle = mass_core.handle_from_spawn(spec, facts)["handle"]
        self.assertEqual(handle, mass_core.MassHandle("p1", "w1", 2, (1.0, 0.0, 0.0)))
        self.assertIn("created", mass_core.handle_from_spawn(
            spec, {**facts, "created": 1})["error"])

    def test_inspect_and_clear_discriminate_liveness_transform_and_cleanup(self):
        spec = mass_core.make_spec(frames(frame(10, 20, 30), frame(-2, 4, 8)))["spec"]
        handle = mass_core.MassHandle("p1", "w1", 2, spec.position_sum)
        inspect = {"ok": True, "population_id": "p1", "world_id": "w1",
                   "requested": 2, "valid": 2, "transform_mismatches": 0,
                   "observed_sum_x": 8.0, "observed_sum_y": 24.0,
                   "observed_sum_z": 38.0}
        clear = {"ok": True, "population_id": "p1", "world_id": "w1",
                 "valid_before": 2, "valid_after": 0}

        self.assertTrue(mass_core.judge_inspect(handle, inspect)["ok"])
        self.assertTrue(mass_core.judge_clear(handle, clear)["ok"])
        self.assertFalse(mass_core.judge_inspect(
            handle, {**inspect, "valid": 1})["ok"])
        self.assertFalse(mass_core.judge_clear(
            handle, {**clear, "valid_after": 1})["ok"])

    def test_ism_handle_requires_registered_representation_and_lod_fragments(self):
        handle = mass_core.MassHandle("p1", "w1", 2, (1.0, 0.0, 0.0), "ism")
        facts = {"ok": True, "population_id": "p1", "world_id": "w1",
                 "requested": 2, "valid": 2, "transform_mismatches": 0,
                 "observed_sum_x": 1.0, "observed_sum_y": 0.0, "observed_sum_z": 0.0,
                 "representation_fragments": 2, "lod_fragments": 2,
                 "mesh_desc_valid": 2}
        self.assertTrue(mass_core.judge_inspect(handle, facts)["ok"])
        for field in ("representation_fragments", "lod_fragments", "mesh_desc_valid"):
            self.assertFalse(mass_core.judge_inspect(handle, {**facts, field: 1})["ok"])

    def test_patrol_handle_requires_activity_and_respects_its_radius(self):
        handle = mass_core.MassHandle(
            "p1", "w1", 2, (0.0, 0.0, 0.0), "ism_dynamic", "patrol")
        facts = {"ok": True, "population_id": "p1", "world_id": "w1",
                 "requested": 2, "valid": 2, "representation_fragments": 2,
                 "lod_fragments": 2, "mesh_desc_valid": 2,
                 "patrol_fragments": 2, "patrol_initialized": 2,
                 "patrol_moved": 2, "patrol_out_of_bounds": 0}
        self.assertTrue(mass_core.judge_inspect(handle, facts)["ok"])
        for field, bad in (("patrol_moved", 0), ("patrol_out_of_bounds", 1)):
            self.assertFalse(mass_core.judge_inspect(
                handle, {**facts, field: bad})["ok"])


class MassToolTests(unittest.TestCase):
    FACTS = {
        "ok": True, "requested": 2, "created": 2, "valid_before": 2,
        "valid_after": 0, "same_archetype": 2, "transform_mismatches": 0,
        "input_sum_x": 8.0, "input_sum_y": 24.0, "input_sum_z": 38.0,
        "observed_sum_x": 8.0, "observed_sum_y": 24.0, "observed_sum_z": 38.0,
    }

    def test_tool_uses_the_adapter_and_passes_the_same_f(self):
        stream = frames(frame(10, 20, 30), frame(-2, 4, 8))
        try:
            with mock.patch.object(ue, "mass_probe", return_value=self.FACTS) as probe:
                text = tools.t_mass_probe(stream)
            self.assertIn("2 entidades · 1 arquetipo", text)
            self.assertIs(tools.dato_producido_runtime("mass_probe"), stream)
            self.assertEqual(len(probe.call_args.args[0]), 2)
        finally:
            tools.limpiar_asset_producido_runtime("mass_probe")

    def test_tool_fails_closed_when_the_bridge_does_not_clean_up(self):
        stream = frames(frame(10, 20, 30), frame(-2, 4, 8))
        with mock.patch.object(ue, "mass_probe",
                               return_value={**self.FACTS, "valid_after": 1}):
            with self.assertRaisesRegex(RuntimeError, "valid_after"):
                tools.t_mass_probe(stream)

    def test_phase1_tools_create_inspect_and_clear_the_same_population(self):
        stream = frames(frame(10, 20, 30), frame(-2, 4, 8))
        tools.t_mass_spec(stream, seed=19, budget=8)
        spec = tools.dato_producido_runtime("mass_spec")
        spawn = {"ok": True, "population_id": "p1", "world_id": "w1",
                 "requested": 2, "created": 2, "valid": 2}
        inspect = {"ok": True, "population_id": "p1", "world_id": "w1",
                   "requested": 2, "valid": 2, "transform_mismatches": 0,
                   "observed_sum_x": 8.0, "observed_sum_y": 24.0,
                   "observed_sum_z": 38.0}
        clear = {"ok": True, "population_id": "p1", "world_id": "w1",
                 "valid_before": 2, "valid_after": 0}

        with mock.patch.object(ue, "mass_spawn", return_value=spawn), \
             mock.patch.object(ue, "mass_inspect", return_value=inspect), \
             mock.patch.object(ue, "mass_clear", return_value=clear) as clear_call, \
             mock.patch.object(panel, "registrar_efecto_preview") as register:
            tools.t_mass_spawn(spec)
            handle = tools.dato_producido_runtime("mass_spawn")
            inspected = tools.t_mass_inspect(handle)
            cleared = tools.t_mass_clear(handle)
            register.call_args.args[0]()

        self.assertIn("2 entidades vivas", inspected)
        self.assertIn("0 vivas", cleared)
        self.assertEqual(clear_call.call_count, 2)  # Clear explícito + Discard idempotente
        self.assertIs(tools.dato_producido_runtime("mass_inspect"), handle)

    def test_mass_config_uses_adapter_and_feeds_mass_spec_as_mc(self):
        path = "/Game/Jam/Mass/MC_Ratas.MC_Ratas"
        facts = {"ok": True, "config_path": path, "trait_count": 1,
                 "template_valid": True, "has_transform": True}
        with mock.patch.object(ue, "mass_config", return_value=facts) as inspect:
            text = tools.t_mass_config(path=path)
        config = tools.dato_producido_runtime("mass_config")
        tools.t_mass_spec(frames(frame()), config=config)

        self.assertIn("template espacial válido", text)
        self.assertEqual(tools.dato_producido_runtime("mass_spec").config_path, path)
        inspect.assert_called_once_with(path)

    def test_mass_config_can_demand_a_measured_ism_profile(self):
        path = "/Jam/Mass/MC_JamAmbientISM.MC_JamAmbientISM"
        facts = {"ok": True, "config_path": path, "trait_count": 2,
                 "template_valid": True, "has_transform": True,
                 "has_representation": False}
        with mock.patch.object(ue, "mass_config", return_value=facts):
            with self.assertRaisesRegex(RuntimeError, "FMassRepresentationFragment"):
                tools.t_mass_config(path=path, require_ism=True)

    def test_mass_config_can_demand_and_publish_a_measured_lod_budget(self):
        path = "/Jam/Mass/MC_JamAmbientBudget.MC_JamAmbientBudget"
        facts = {
            "ok": True, "config_path": path, "trait_count": 2,
            "template_valid": True, "has_transform": True,
            "has_representation": True, "has_lod": True, "has_viewer": True,
            "has_actor_fragment": True, "stationary": True,
            "mesh_paths": ["/Engine/BasicShapes/Sphere.Sphere"],
            "lod_representation": ["StaticMeshInstance", "StaticMeshInstance",
                                   "StaticMeshInstance", "None"],
            "lod_distances": [0.0, 1500.0, 3500.0, 8000.0],
            "lod_max_counts": [1, 1, 1, 2147483647],
        }
        with mock.patch.object(ue, "mass_config", return_value=facts):
            text = tools.t_mass_config(
                path=path, require_ism=True, require_lod_budget=True)

        self.assertIn("máximos LOD (1, 1, 1, 2147483647)", text)
        self.assertEqual(
            tools.dato_producido_runtime("mass_config").lod_max_counts,
            (1, 1, 1, 2147483647))

    def test_mass_config_can_publish_a_measured_patrol(self):
        path = "/Jam/Mass/MC_JamAmbientPatrol.MC_JamAmbientPatrol"
        facts = {
            "ok": True, "config_path": path, "trait_count": 3,
            "template_valid": True, "has_transform": True,
            "has_representation": True, "has_lod": True, "has_viewer": True,
            "has_actor_fragment": True, "stationary": False, "moving_ism": True,
            "has_patrol": True, "patrol_speed": 800.0, "patrol_radius": 25.0,
            "mesh_paths": ["/Engine/BasicShapes/Sphere.Sphere"],
            "lod_representation": ["StaticMeshInstance", "StaticMeshInstance",
                                   "StaticMeshInstance", "None"],
            "lod_distances": [0.0, 1500.0, 3500.0, 8000.0],
        }
        with mock.patch.object(ue, "mass_config", return_value=facts):
            text = tools.t_mass_config(path=path, require_patrol=True)
        config = tools.dato_producido_runtime("mass_config")
        self.assertIn("patrulla 800 cm/s en radio 25 cm", text)
        self.assertEqual(config.behavior, "patrol")


class MassContractTests(unittest.TestCase):
    def test_graph_publishes_mass_as_a_diagnostic_f_to_f(self):
        spec = {item["verbo"]: item for item in json.loads(api.spec_all())["tools"]}
        node = spec["mass_probe"]
        self.assertEqual((node["in_name"], node["out_name"]), ("F", "F"))
        self.assertEqual((node["cat"], node["seccion"], node["grupo"]),
                         ("Mass", "Distribución", "Diagnóstico"))
        self.assertTrue(tools.REGISTRO["mass_probe"]["read_only"])
        self.assertEqual(ribbon.seccion_de("Mass"), "Distribución")

    def test_runtime_module_uses_real_mass_creation_and_cleanup_apis(self):
        source = (ROOT / "Source/JamMass/Private/JamMassLibrary.cpp").read_text(encoding="utf-8")
        build = (ROOT / "Source/JamMass/JamMass.Build.cs").read_text(encoding="utf-8")
        descriptor = json.loads((ROOT / "Jam.uplugin").read_text(encoding="utf-8"))
        for marker in ("FTransformFragment::StaticStruct()", "BatchCreateEntities",
                       "GetFragmentDataChecked<FTransformFragment>", "BatchDestroyEntities",
                       "IsEntityValid", "Transform.ContainsNaN()", "SpawnPopulation",
                       "InspectPopulation", "ClearPopulation", "Populations.Add"):
            self.assertIn(marker, source)
        module_source = (ROOT / "Source/JamMass/Private/JamMassModule.cpp").read_text(
            encoding="utf-8")
        self.assertIn("FWorldDelegates::OnWorldCleanup", module_source)
        self.assertIn("ClearAllPopulations", module_source)
        self.assertIn('\"MassCore\"', build)
        self.assertIn('\"MassEntity\"', build)
        module = next(item for item in descriptor["Modules"] if item["Name"] == "JamMass")
        self.assertEqual(module["Type"], "Runtime")

    def test_budget_bridge_writes_and_inspects_the_four_lod_limits(self):
        library = (ROOT / "Source/JamMass/Private/JamMassLibrary.cpp").read_text(
            encoding="utf-8")
        trait = (ROOT / "Source/JamMass/Private/JamMassGameplayTypes.cpp").read_text(
            encoding="utf-8")
        for marker in ("PrepareAmbientISMBudgetConfig", 'TEXT("lod_max_counts")',
                       "Visualization->LODParams.LODMaxCount[LOD]"):
            self.assertIn(marker, library)
        for marker in ("ConfigureBudget", "HighMaxCount < 0",
                       "LODParams.LODMaxCount[EMassLOD::High] = HighMaxCount",
                       "LODParams.LODMaxCount[EMassLOD::Medium] = MediumMaxCount",
                       "LODParams.LODMaxCount[EMassLOD::Low] = LowMaxCount",
                       "LODParams.LODMaxCount[EMassLOD::Off] = MAX_int32"):
            self.assertIn(marker, trait)

    def test_pie_budget_probe_has_an_unlimited_control_and_a_bounded_population(self):
        source = (ROOT / "tools/experiments/verifica_mass_lod_budget_58.py").read_text(
            encoding="utf-8")
        for marker in ("MC_JamAmbientISM", "MC_JamAmbientBudget",
                       '"lod_high": 4', '"lod_high": 1',
                       '"lod_medium": 1', '"lod_low": 1', '"lod_off": 1',
                       "JAM_MASS_LOD_BUDGET_58"):
            self.assertIn(marker, source)

    def test_patrol_processor_is_typed_bounded_and_observable(self):
        gameplay = (ROOT / "Source/JamMass/Private/JamMassGameplayTypes.cpp").read_text(
            encoding="utf-8")
        library = (ROOT / "Source/JamMass/Private/JamMassLibrary.cpp").read_text(
            encoding="utf-8")
        for marker in ("UJamMassPatrolProcessor::Execute", "FJamMassPatrolFragment",
                       "FJamMassPatrolParameters", "Patrol.Distance > Parameters.Radius",
                       "++Patrol.Reversals", "ProcessorGroupNames::Movement"):
            self.assertIn(marker, gameplay)
        for marker in ('TEXT("patrol_fragments")', 'TEXT("patrol_reversed")',
                       'TEXT("patrol_out_of_bounds")', "PrepareAmbientPatrolConfig"):
            self.assertIn(marker, library)

    def test_pie_patrol_probe_measures_activity_reversal_bounds_and_dynamic_ism(self):
        source = (ROOT / "tools/experiments/verifica_mass_patrol_58.py").read_text(
            encoding="utf-8")
        for marker in ('"moving_ism": True', '"stationary": False',
                       '"transform_mismatches": 4', '"patrol_moved": 4',
                       '"patrol_reversed": 4', '"patrol_out_of_bounds": 0',
                       '"representation_ism": 4', "JAM_MASS_PATROL_58"):
            self.assertIn(marker, source)

    def test_pie_probe_contrasts_editor_and_pie_world_lifetimes(self):
        source = (ROOT / "tools/experiments/verifica_mass_pie_58.py").read_text(
            encoding="utf-8")
        for marker in ("editor_play_simulate", "get_pie_worlds", "editor_request_end_play",
                       'ESTADO["editor_id"]', 'ESTADO["pie_id"]',
                       "inexistente o ya liberada", "JAM_MASS_PIE_58 TODO VERDE"):
            self.assertIn(marker, source)
        self.assertIn('editor.get("valid") != 3', source)
        self.assertIn('if pie.get("ok")', source)

    def test_graph_publishes_mc_ms_and_mh_with_massgameplay(self):
        spec = {item["verbo"]: item for item in json.loads(api.spec_all())["tools"]}

        self.assertEqual((spec["mass_config"]["in_name"], spec["mass_config"]["out_name"]),
                         ("", "MC"))
        self.assertEqual((spec["mass_spec"]["in_name"], spec["mass_spec"]["out_name"]),
                         ("F", "MS"))
        config_param = next(p for p in spec["mass_spec"]["params"] if p["nombre"] == "config")
        self.assertEqual(config_param["data_type"], "MC")
        self.assertIn("config", tools.REGISTRO["mass_spec"]["optional_data_params"])
        self.assertEqual((spec["mass_spawn"]["in_name"], spec["mass_spawn"]["out_name"]),
                         ("MS", "MH"))
        self.assertEqual((spec["mass_inspect"]["in_name"], spec["mass_inspect"]["out_name"]),
                         ("MH", "MH"))
        self.assertEqual((spec["mass_clear"]["in_name"], spec["mass_clear"]["out_name"]),
                         ("MH", "MH"))
        build = (ROOT / "Source/JamMass/JamMass.Build.cs").read_text(encoding="utf-8")
        descriptor = (ROOT / "Jam.uplugin").read_text(encoding="utf-8")
        self.assertIn('"MassSpawner"', build)
        self.assertIn('"MassGameplay"', descriptor)

    def test_ambient_representation_binds_traits_tags_and_global_processors(self):
        header = (ROOT / "Source/JamMass/Public/JamMassGameplayTypes.h").read_text(
            encoding="utf-8")
        source = (ROOT / "Source/JamMass/Private/JamMassGameplayTypes.cpp").read_text(
            encoding="utf-8")

        for processor in ("UJamMassLODCollectorProcessor",
                          "UJamMassVisualizationLODProcessor",
                          "UJamMassVisualizationProcessor"):
            self.assertIn(processor, header)
        self.assertGreaterEqual(source.count("bAutoRegisterWithProcessingPhases = true"), 3)
        self.assertIn("LODParams.FilterTag = FJamMassAmbientTag::StaticStruct()", source)
        self.assertIn("BuildContext.AddTag<FJamMassAmbientTag>()", source)
        self.assertIn("EntityQuery.AddTagRequirement<FJamMassAmbientTag>", source)
        self.assertIn("FilterTag = FJamMassAmbientTag::StaticStruct()", source)

    def test_build_verifier_checks_each_module_binary(self):
        verifier = (ROOT / "tools/build.py").read_text(encoding="utf-8")
        self.assertIn('(RAIZ / "Source").iterdir()', verifier)
        self.assertIn('f"libUnrealEditor-{modulo.name}.so"', verifier)
        self.assertNotIn('BASE = BINARIOS / "libUnrealEditor-JamEditor.so"', verifier)


if __name__ == "__main__":
    unittest.main()
