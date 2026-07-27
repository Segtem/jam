from __future__ import annotations

import sys
import types
import unittest
from unittest import mock

# El test del runner necesita importar `tools`, pero no ejecutar Unreal. Mantiene la suite headless e
# independiente del orden en que unittest descubra los módulos.
_unreal_fake = sys.modules.setdefault("unreal", types.ModuleType("unreal"))
if not hasattr(_unreal_fake, "TopLevelAssetPath"):
    _unreal_fake.TopLevelAssetPath = lambda package, name: (package, name)

from jam.graph import GraphPlan, GraphValidationError, JamGraph, compilar, ejecutar_detalle
from jam import session, tools


def _tool(*, source=False, asset_required=True, asset_pin=None, out="A", in_name="A",
          params=None, arity=None, min_inputs=None):
    resolved_arity = (0 if source else 1) if arity is None else arity
    return {
        "source": source,
        "aridad": resolved_arity,
        "min_inputs": (0 if source else 1) if min_inputs is None else min_inputs,
        "in_name": "" if source else in_name,
        "out_name": out,
        "asset_required": asset_required,
        "asset_pin": asset_required if asset_pin is None else asset_pin,
        "params": params or {},
    }


REGISTRY = {
    "asset": _tool(source=True, asset_required=False, params={"name": ""}),
    "pick": _tool(source=True, asset_required=False),
    "place": _tool(params={"x": 0.0, "surface": True, "anchor": "base"}),
    "snap": _tool(params={"grid": 100.0}),
    "nanite": _tool(),
    "create_spline": _tool(source=True, asset_required=False, out="S"),
    "mesh_cylinder": _tool(source=True, asset_required=False, out="M",
                           params={"radius": 50.0}),
    "mesh_normals": _tool(asset_required=False, in_name="M", out="M"),
    "mesh_leaf": _tool(asset_required=False, asset_pin=True, in_name="S", out="M"),
    "mesh_merge": _tool(asset_required=False, in_name="M", out="M", arity=-1, min_inputs=2),
    "mesh_to_static": _tool(asset_required=False, in_name="M", out="A",
                            params={"name": "GeneratedMesh", "folder": "/Game/Jam/Meshes"}),
}

ASSETS = {
    "Rock": "/Game/Props/Rock.Rock",
    "/Game/Props/Rock.Rock": "/Game/Props/Rock.Rock",
    "Tree": "/Game/Props/Tree.Tree",
}


def _resolve_asset(name):
    return ASSETS.get(str(name))


class GraphPreflightTests(unittest.TestCase):
    def compile(self, graph: JamGraph, *, pick=None):
        return compilar(
            graph,
            registro=REGISTRY,
            resolver_asset=_resolve_asset,
            resolver_pick=lambda: pick,
        )

    def test_isolated_place_without_asset_is_rejected(self) -> None:
        graph = JamGraph()
        graph.add("place", {}, nid="place")

        with self.assertRaises(GraphValidationError) as caught:
            self.compile(graph)

        self.assertIn("asset explícito", " ".join(caught.exception.diagnostics["place"]))

    def test_optional_asset_pin_accepts_an_unconnected_leaf(self) -> None:
        graph = JamGraph()
        graph.add("create_spline", {}, nid="curve")
        graph.add("mesh_leaf", {}, nid="leaf")
        graph.connect("curve", "leaf")

        plan = self.compile(graph)

        self.assertIsNone(plan.input_assets["leaf"])

    def test_optional_asset_pin_resolves_a_connected_leaf_mesh(self) -> None:
        graph = JamGraph()
        graph.add("asset", {"name": "Tree"}, nid="asset")
        graph.add("create_spline", {}, nid="curve")
        graph.add("mesh_leaf", {}, nid="leaf")
        graph.connect("curve", "leaf")
        graph.connect("asset", "leaf", "asset")

        plan = self.compile(graph)

        self.assertEqual(plan.input_assets["leaf"], "/Game/Props/Tree.Tree")

    def test_active_session_asset_does_not_rescue_an_empty_graph_pin(self) -> None:
        graph = JamGraph()
        graph.add("place", {}, nid="place")
        resolver_calls = []
        session.set_asset("/Game/Hidden/Fallback.Fallback")
        try:
            with self.assertRaises(GraphValidationError):
                compilar(
                    graph,
                    registro=REGISTRY,
                    resolver_asset=lambda name: resolver_calls.append(name) or str(name),
                )
        finally:
            session.limpiar()

        self.assertEqual(resolver_calls, [])

    def test_isolated_place_with_explicit_asset_is_valid(self) -> None:
        graph = JamGraph()
        graph.add("place", {"asset": "Rock", "x": "25"}, nid="place")

        plan = self.compile(graph)

        self.assertEqual(plan.input_assets["place"], "/Game/Props/Rock.Rock")
        self.assertEqual(plan.params["place"]["x"], 25.0)

    def test_asset_node_can_feed_place(self) -> None:
        graph = JamGraph()
        graph.add("asset", {"name": "Rock"}, nid="asset")
        graph.add("place", {}, nid="place")
        graph.connect("asset", "place")

        plan = self.compile(graph)

        self.assertEqual(plan.output_assets["asset"], "/Game/Props/Rock.Rock")
        self.assertEqual(plan.input_assets["place"], "/Game/Props/Rock.Rock")

    def test_empty_asset_node_is_rejected(self) -> None:
        graph = JamGraph()
        graph.add("asset", {"name": ""}, nid="asset")

        with self.assertRaises(GraphValidationError) as caught:
            self.compile(graph)

        self.assertIn("requiere un nombre", " ".join(caught.exception.diagnostics["asset"]))

    def test_pick_requires_content_browser_selection(self) -> None:
        graph = JamGraph()
        graph.add("pick", {}, nid="pick")
        graph.add("place", {}, nid="place")
        graph.connect("pick", "place")

        with self.assertRaises(GraphValidationError) as caught:
            self.compile(graph, pick=None)

        self.assertIn("seleccionada", " ".join(caught.exception.diagnostics["pick"]))

        plan = self.compile(graph, pick="/Game/Props/Tree.Tree")
        self.assertEqual(plan.input_assets["place"], "/Game/Props/Tree.Tree")

    def test_nonexistent_explicit_asset_is_rejected(self) -> None:
        graph = JamGraph()
        graph.add("place", {"asset": "Missing"}, nid="place")

        with self.assertRaises(GraphValidationError) as caught:
            self.compile(graph)

        self.assertIn("no encontrado", " ".join(caught.exception.diagnostics["place"]))

    def test_text_cannot_connect_directly_to_asset_pin(self) -> None:
        graph = JamGraph()
        graph.add("text", {"name": "path", "value": "Rock"}, nid="text")
        graph.add("place", {}, nid="place")
        graph.connect("text", "place", "asset")

        with self.assertRaises(GraphValidationError) as caught:
            self.compile(graph)

        self.assertIn("esperaba A, recibió T", " ".join(caught.exception.diagnostics["place"]))

    def test_text_can_drive_asset_name_then_asset_can_feed_place(self) -> None:
        graph = JamGraph()
        graph.add("text", {"name": "path", "value": "Rock"}, nid="text")
        graph.add("asset", {"name": ""}, nid="asset")
        graph.add("place", {}, nid="place")
        graph.connect("text", "asset", "name")
        graph.connect("asset", "place")

        plan = self.compile(graph)

        self.assertEqual(plan.output_assets["asset"], "/Game/Props/Rock.Rock")
        self.assertEqual(plan.input_assets["place"], "/Game/Props/Rock.Rock")

    def test_number_can_drive_tool_parameter(self) -> None:
        graph = JamGraph()
        graph.add("number", {"name": "offset", "value": 42}, nid="number")
        graph.add("place", {"asset": "Rock"}, nid="place")
        graph.connect("number", "place", "x")

        plan = self.compile(graph)

        self.assertEqual(plan.params["place"]["x"], 42.0)

    def test_multiple_main_inputs_are_rejected(self) -> None:
        graph = JamGraph()
        graph.add("asset", {"name": "Rock"}, nid="rock")
        graph.add("asset", {"name": "Tree"}, nid="tree")
        graph.add("place", {}, nid="place")
        graph.connect("rock", "place")
        graph.connect("tree", "place")

        with self.assertRaises(GraphValidationError) as caught:
            self.compile(graph)

        self.assertIn("admite un solo cable", " ".join(caught.exception.diagnostics["place"]))

    def test_unknown_tool_and_cycle_are_compile_errors(self) -> None:
        unknown = JamGraph()
        unknown.add("removed_tool", {}, nid="old")
        with self.assertRaises(GraphValidationError) as caught_unknown:
            self.compile(unknown)
        self.assertIn("verbo desconocido", " ".join(caught_unknown.exception.diagnostics["old"]))

        cycle = JamGraph()
        cycle.add("place", {"asset": "Rock"}, nid="a")
        cycle.add("snap", {"asset": "Rock"}, nid="b")
        cycle.connect("a", "b")
        cycle.connect("b", "a")
        with self.assertRaises(GraphValidationError) as caught_cycle:
            self.compile(cycle)
        self.assertIn("ciclo", " ".join(caught_cycle.exception.diagnostics["_graph"]))

    def test_runtime_transform_output_replaces_predicted_path_for_downstream_node(self) -> None:
        graph = JamGraph()
        graph.add("fracture", {}, nid="fracture")
        graph.add("place", {}, nid="place")
        graph.connect("fracture", "place")
        source = "/Game/Props/Crate.Crate"
        predicted = "/Game/JamDF/Fractures/GC_Crate"
        staged = "/Game/JamPreview/graph/PV_run_GC_Crate"
        received = []

        def fracture_fn(asset):
            self.assertEqual(asset, source)
            tools._RUNTIME_ASSET_OUTPUTS["fracture"] = staged
            return "fracture ✓"

        def place_fn(asset):
            received.append(asset)
            return "place ✓"

        registry = {
            "fracture": {"fn": fracture_fn, "params": {}},
            "place": {"fn": place_fn, "params": {}},
        }
        plan = GraphPlan(
            order=["fracture", "place"],
            params={"fracture": {}, "place": {}},
            input_assets={"fracture": source, "place": predicted},
            output_assets={"fracture": predicted, "place": predicted},
            values={},
            values_by_node={},
        )

        try:
            with mock.patch.object(tools, "REGISTRO", registry):
                _report, states = ejecutar_detalle(graph, plan)
        finally:
            tools._RUNTIME_ASSET_OUTPUTS.clear()

        self.assertEqual(received, [staged])
        self.assertEqual(states["place"]["estado"], "ok")

    def test_nanite_is_an_asset_to_asset_transform_in_the_plan(self) -> None:
        graph = JamGraph()
        graph.add("asset", {"name": "Rock"}, nid="asset")
        graph.add("nanite", {}, nid="nanite")
        graph.add("place", {}, nid="place")
        graph.connect("asset", "nanite")
        graph.connect("nanite", "place")
        predicted = "/Game/Jam/Nanite/Rock_Nanite"

        plan = compilar(
            graph,
            registro=REGISTRY,
            resolver_asset=_resolve_asset,
            transformar_asset=lambda verb, asset, _params: predicted if verb == "nanite" else None,
        )

        self.assertEqual(plan.input_assets["nanite"], "/Game/Props/Rock.Rock")
        self.assertEqual(plan.output_assets["nanite"], predicted)
        self.assertEqual(plan.input_assets["place"], predicted)

    def test_dynamic_mesh_chain_is_typed_and_predicts_static_asset(self) -> None:
        graph = JamGraph()
        graph.add("mesh_cylinder", {"radius": 80}, nid="cylinder")
        graph.add("mesh_normals", {}, nid="normals")
        graph.add("mesh_to_static", {"name": "Column"}, nid="static")
        graph.add("nanite", {}, nid="nanite")
        graph.add("place", {}, nid="place")
        graph.connect("cylinder", "normals")
        graph.connect("normals", "static")
        graph.connect("static", "nanite")
        graph.connect("nanite", "place")

        def predict(verb, asset, params):
            if verb == "mesh_to_static":
                return f"/Game/Jam/Meshes/SM_{params['name']}"
            if verb == "nanite":
                return "/Game/Jam/Nanite/SM_Column_Nanite"
            return None

        plan = compilar(graph, registro=REGISTRY, transformar_asset=predict)

        self.assertEqual(plan.params["cylinder"]["radius"], 80.0)
        self.assertEqual(plan.output_assets["static"], "/Game/Jam/Meshes/SM_Column")
        self.assertEqual(plan.input_assets["nanite"], "/Game/Jam/Meshes/SM_Column")
        self.assertEqual(plan.input_assets["place"], "/Game/Jam/Nanite/SM_Column_Nanite")

    def test_dynamic_mesh_input_rejects_assets_and_requires_a_wire(self) -> None:
        incompatible = JamGraph()
        incompatible.add("asset", {"name": "Rock"}, nid="asset")
        incompatible.add("mesh_normals", {}, nid="normals")
        incompatible.connect("asset", "normals")
        with self.assertRaises(GraphValidationError) as caught_type:
            self.compile(incompatible)
        self.assertIn("esperaba M", " ".join(caught_type.exception.diagnostics["normals"]))

        disconnected = JamGraph()
        disconnected.add("mesh_normals", {}, nid="normals")
        with self.assertRaises(GraphValidationError) as caught_wire:
            self.compile(disconnected)
        self.assertIn("conexión(es) M", " ".join(caught_wire.exception.diagnostics["normals"]))

    def test_runner_carries_dynamic_mesh_objects_and_variadic_lists(self) -> None:
        graph = JamGraph()
        graph.add("mesh_cylinder", {}, nid="a")
        graph.add("mesh_cylinder", {}, nid="b")
        graph.add("mesh_merge", {}, nid="merge")
        graph.add("mesh_to_static", {}, nid="static")
        graph.connect("a", "merge")
        graph.connect("b", "merge")
        graph.connect("merge", "static")
        first, second, merged = object(), object(), object()
        received = []

        produced = iter((first, second))

        def source_fn(_input):
            value = next(produced)
            tools._RUNTIME_DATA_OUTPUTS["mesh_cylinder"] = value
            return "mesh source ✓"

        def merge_fn(inputs):
            received.append(list(inputs))
            tools._RUNTIME_DATA_OUTPUTS["mesh_merge"] = merged
            return "mesh merge ✓"

        def static_fn(input_mesh):
            received.append(input_mesh)
            tools._RUNTIME_ASSET_OUTPUTS["mesh_to_static"] = "/Game/JamPreview/graph/SM_Test"
            return "static mesh ✓"

        registry = {
            "mesh_cylinder": {"fn": source_fn, "params": {}, "aridad": 0},
            "mesh_merge": {"fn": merge_fn, "params": {}, "aridad": -1},
            "mesh_to_static": {"fn": static_fn, "params": {}, "aridad": 1},
        }
        plan = GraphPlan(
            order=["a", "b", "merge", "static"],
            params={nid: {} for nid in ("a", "b", "merge", "static")},
            input_assets={nid: None for nid in ("a", "b", "merge", "static")},
            output_assets={"a": None, "b": None, "merge": None,
                           "static": "/Game/Jam/Meshes/SM_Test"},
            values={}, values_by_node={},
        )

        try:
            with mock.patch.object(tools, "REGISTRO", registry):
                _report, states = ejecutar_detalle(graph, plan)
        finally:
            tools._RUNTIME_ASSET_OUTPUTS.clear()
            tools._RUNTIME_DATA_OUTPUTS.clear()

        self.assertEqual(received[0], [first, second])
        self.assertIs(received[1], merged)
        self.assertEqual(states["static"]["estado"], "ok")

    def test_runner_keeps_rich_main_input_and_injects_side_asset(self) -> None:
        graph = JamGraph()
        graph.add("asset", {}, nid="leaf")
        graph.add("curve", {}, nid="branch")
        graph.add("mesh_along_curve", {}, nid="leaves")
        graph.connect("branch", "leaves")
        graph.connect("leaf", "leaves", "asset")
        curve_value = object()
        received = []

        def asset_fn(_input):
            return "asset ✓"

        def curve_fn(_input):
            tools._RUNTIME_DATA_OUTPUTS["curve"] = curve_value
            return "curve ✓"

        def along_fn(curve_input, *, asset=None):
            received.append((curve_input, asset))
            tools._RUNTIME_DATA_OUTPUTS["mesh_along_curve"] = object()
            return "along curve ✓"

        asset_path = "/Game/Leaves/SM_Leaf.SM_Leaf"
        registry = {
            "asset": {"fn": asset_fn, "params": {}, "aridad": 0},
            "curve": {"fn": curve_fn, "params": {}, "aridad": 0},
            "mesh_along_curve": {
                "fn": along_fn, "params": {}, "aridad": 1, "asset_argument": True,
            },
        }
        plan = GraphPlan(
            order=["leaf", "branch", "leaves"],
            params={nid: {} for nid in ("leaf", "branch", "leaves")},
            input_assets={"leaf": asset_path, "branch": None, "leaves": asset_path},
            output_assets={"leaf": asset_path, "branch": None, "leaves": asset_path},
            values={}, values_by_node={},
        )

        try:
            with mock.patch.object(tools, "REGISTRO", registry):
                _report, states = ejecutar_detalle(graph, plan)
        finally:
            tools._RUNTIME_ASSET_OUTPUTS.clear()
            tools._RUNTIME_DATA_OUTPUTS.clear()

        self.assertEqual(received, [(curve_value, asset_path)])
        self.assertEqual(states["leaves"]["estado"], "ok")


if __name__ == "__main__":
    unittest.main()
