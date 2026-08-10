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

    def test_pie_probe_contrasts_editor_and_pie_world_lifetimes(self):
        source = (ROOT / "tools/experiments/verifica_mass_pie_58.py").read_text(
            encoding="utf-8")
        for marker in ("editor_play_simulate", "get_pie_worlds", "editor_request_end_play",
                       'ESTADO["editor_id"]', 'ESTADO["pie_id"]',
                       "inexistente o ya liberada", "JAM_MASS_PIE_58 TODO VERDE"):
            self.assertIn(marker, source)
        self.assertIn('editor.get("valid") != 3', source)
        self.assertIn('if pie.get("ok")', source)

    def test_graph_publishes_ms_and_mh_without_massgameplay(self):
        spec = {item["verbo"]: item for item in json.loads(api.spec_all())["tools"]}

        self.assertEqual((spec["mass_spec"]["in_name"], spec["mass_spec"]["out_name"]),
                         ("F", "MS"))
        self.assertEqual((spec["mass_spawn"]["in_name"], spec["mass_spawn"]["out_name"]),
                         ("MS", "MH"))
        self.assertEqual((spec["mass_inspect"]["in_name"], spec["mass_inspect"]["out_name"]),
                         ("MH", "MH"))
        self.assertEqual((spec["mass_clear"]["in_name"], spec["mass_clear"]["out_name"]),
                         ("MH", "MH"))
        build = (ROOT / "Source/JamMass/JamMass.Build.cs").read_text(encoding="utf-8")
        descriptor = (ROOT / "Jam.uplugin").read_text(encoding="utf-8")
        self.assertNotIn("MassGameplay", build)
        self.assertNotIn("MassGameplay", descriptor)

    def test_build_verifier_checks_each_module_binary(self):
        verifier = (ROOT / "tools/build.py").read_text(encoding="utf-8")
        self.assertIn('(RAIZ / "Source").iterdir()', verifier)
        self.assertIn('f"libUnrealEditor-{modulo.name}.so"', verifier)
        self.assertNotIn('BASE = BINARIOS / "libUnrealEditor-JamEditor.so"', verifier)


if __name__ == "__main__":
    unittest.main()
