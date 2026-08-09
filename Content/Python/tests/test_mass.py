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

from jam import api, curve, mass_core, ribbon, tools, ue  # noqa: E402


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
                       "IsEntityValid", "Transform.ContainsNaN()"):
            self.assertIn(marker, source)
        self.assertIn('\"MassCore\"', build)
        self.assertIn('\"MassEntity\"', build)
        module = next(item for item in descriptor["Modules"] if item["Name"] == "JamMass")
        self.assertEqual(module["Type"], "Runtime")

    def test_build_verifier_checks_each_module_binary(self):
        verifier = (ROOT / "tools/build.py").read_text(encoding="utf-8")
        self.assertIn('(RAIZ / "Source").iterdir()', verifier)
        self.assertIn('f"libUnrealEditor-{modulo.name}.so"', verifier)
        self.assertNotIn('BASE = BINARIOS / "libUnrealEditor-JamEditor.so"', verifier)


if __name__ == "__main__":
    unittest.main()
