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

from jam.graph import (GraphPlan, GraphValidationError, JamGraph, compilar, ejecutar_detalle,
                       puede_bypass)
from jam import session, tools


def _tool(*, source=False, asset_required=True, asset_pin=None, out="A", in_name="A",
          params=None, arity=None, min_inputs=None):
    resolved_arity = (0 if source else 1) if arity is None else arity
    entrada = "" if source else in_name
    # Misma regla que `tools.py`: un verbo cuya entrada PRINCIPAL ya es un asset no tiene además una
    # fila `asset` — serían dos pines para lo mismo. Se deriva acá igual que allá para que este
    # registro de mentira no pueda quedar describiendo un canvas que ya no existe.
    pin = asset_required if asset_pin is None else asset_pin
    return {
        "source": source,
        "aridad": resolved_arity,
        "min_inputs": (0 if source else 1) if min_inputs is None else min_inputs,
        "in_name": entrada,
        "out_name": out,
        "asset_required": asset_required,
        "asset_pin": bool(pin),
        # «tiene su propio pin en el canvas», que no es lo mismo que «consume un asset»
        "asset_row": bool(pin) and entrada != "A",
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
        # Se usa `mesh_leaf` y no `place`: `place` recibe el asset por su pin PRINCIPAL, así que ya
        # no tiene una fila `asset` aparte —eran dos pines para lo mismo—. `mesh_leaf` sí la tiene,
        # porque por el header recibe una curva: ahí son dos entradas distintas de verdad.
        graph = JamGraph()
        graph.add("text", {"name": "path", "value": "Rock"}, nid="text")
        graph.add("curve_bezier", {}, nid="curva")
        graph.add("mesh_leaf", {}, nid="hoja")
        graph.connect("curva", "hoja")
        graph.connect("text", "hoja", "asset")

        with self.assertRaises(GraphValidationError) as caught:
            self.compile(graph)

        self.assertIn("esperaba A, recibió T", " ".join(caught.exception.diagnostics["hoja"]))

    def test_a_verb_whose_main_input_is_an_asset_has_no_separate_asset_pin(self) -> None:
        """El duplicado que se sacó: `place` ofrecía el asset por el pin del header Y por una fila
        propia. Dos lugares donde enchufar lo mismo, sin ninguna pista de cuál."""
        graph = JamGraph()
        graph.add("asset", {"name": "Rock"}, nid="a")
        graph.add("place", {}, nid="place")
        graph.connect("a", "place", "asset")

        with self.assertRaises(GraphValidationError) as caught:
            self.compile(graph)

        self.assertIn("pin de entrada desconocido",
                      " ".join(caught.exception.diagnostics["place"]))

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


class BypassTests(unittest.TestCase):
    """Apagar un nodo sin borrarlo: el stream lo atraviesa (el bypass flag de Houdini)."""

    def test_a_verb_that_takes_and_makes_the_same_type_can_be_bypassed(self):
        self.assertTrue(puede_bypass("nanite", REGISTRY))   # A → A
        self.assertTrue(puede_bypass("mesh_normals", REGISTRY))   # M → M

    def test_a_verb_that_changes_the_type_cannot(self):
        """`mesh_to_static` es M → A. Apagarlo dejaría salir una M por un pin que promete A, y el
        nodo de abajo esperaría un asset que nunca llega. Se prohíbe en vez de re-propagar tipos."""
        self.assertFalse(puede_bypass("mesh_to_static", REGISTRY))
        self.assertFalse(puede_bypass("mesh_leaf", REGISTRY))     # S → M

    def test_a_source_cannot_be_bypassed(self):
        """No tiene entrada que dejar pasar: apagarla sería producir nada, que no es ser
        transparente. Para eso está borrarla."""
        self.assertFalse(puede_bypass("asset", REGISTRY))
        self.assertFalse(puede_bypass("create_spline", REGISTRY))

    def test_an_unknown_verb_is_not_bypassable(self):
        self.assertFalse(puede_bypass("no_existe", REGISTRY))

    def test_compile_rejects_a_bypass_the_ui_would_never_offer(self):
        """El flag lo pone la UI, que sólo lo ofrece donde corresponde — pero un `.jamgraph` editado
        a mano puede traerlo en cualquier nodo, y ahí el tipado se rompería sin que nada avise."""
        graph = JamGraph()
        graph.add("mesh_cylinder", {}, nid="cil")
        graph.add("mesh_to_static", {}, nid="conv")
        graph.connect("cil", "conv")
        graph.nodes["conv"]["bypass"] = True

        with self.assertRaises(GraphValidationError) as ctx:
            compilar(graph, registro=REGISTRY, resolver_asset=ASSETS.get)
        self.assertIn("no se puede bypassear", " ".join(ctx.exception.diagnostics["conv"]))

    def test_compile_ignores_the_params_of_a_bypassed_node(self):
        """Un nodo apagado no corre, así que sus params son irrelevantes. Si siguieran validándose,
        apagar un nodo para esquivar su problema seguiría bloqueando el Run por ese mismo problema
        — que es justo lo contrario de para qué sirve el bypass."""
        graph = JamGraph()
        graph.add("asset", {"name": "Rock"}, nid="a")
        graph.add("snap", {"parametro_inventado": "7"}, nid="s")
        graph.connect("a", "s")

        with self.assertRaises(GraphValidationError):
            compilar(graph, registro=REGISTRY, resolver_asset=ASSETS.get)

        graph.nodes["s"]["bypass"] = True
        plan = compilar(graph, registro=REGISTRY, resolver_asset=ASSETS.get)
        self.assertIn("s", plan.order)

    def test_a_bypassed_node_does_not_run_and_passes_its_input_through(self):
        corridos = []

        def snap_fn(asset, **_kw):
            corridos.append(asset)
            return "snap ✓"

        def place_fn(asset, **_kw):
            corridos.append(asset)
            return "place ✓"

        graph = JamGraph()
        graph.add("asset", {"name": "Rock"}, nid="a")
        graph.add("snap", {}, nid="s")
        graph.add("place", {}, nid="p")
        graph.connect("a", "s")
        graph.connect("s", "p")
        graph.nodes["s"]["bypass"] = True

        registry = {
            "snap": {"fn": snap_fn, "params": {}},
            "place": {"fn": place_fn, "params": {}},
        }
        plan = GraphPlan(
            order=["s", "p"],
            params={"s": {}, "p": {}},
            input_assets={"s": "/Game/Props/Rock.Rock", "p": "/Game/Props/Rock.Rock"},
            output_assets={},
            values={},
            values_by_node={},
        )
        with mock.patch.object(tools, "REGISTRO", registry):
            _report, states = ejecutar_detalle(graph, plan)

        # `snap` no corrió; `place` sí, y recibió lo que `snap` dejó pasar sin tocar.
        self.assertEqual(corridos, ["/Game/Props/Rock.Rock"])
        self.assertEqual(states["s"]["estado"], "bypass")
        self.assertEqual(states["p"]["estado"], "ok")


class BypassSoloConMismoTipoTests(unittest.TestCase):
    """La regla vive DOS veces: `puede_bypass` acá y `JamPuedeBypass` en el `.cpp`.

    Se duplica a propósito —el C++ la necesita por nodo y por frame para decidir si dibuja el botón,
    y no puede cruzar a Python para eso— así que se ata igual que la regla del marquee: el test LEE
    el `.cpp` y exige que siga diciendo lo mismo. Si alguien relaja una de las dos, el canvas
    ofrecería apagar un nodo que Compile va a rechazar, o al revés.
    """

    def condicion(self) -> str:
        import re
        from pathlib import Path

        raiz = Path(__file__).resolve().parents[3]
        cpp = (raiz / "Source" / "JamEditor" / "Private" / "SJamGraphEditor.cpp").read_text(
            encoding="utf-8")
        m = re.search(r"static bool JamPuedeBypass\(const FJamTool& T\)\s*\{(.+?)\}", cpp, re.S)
        self.assertIsNotNone(m, "no encontré JamPuedeBypass en el C++")
        return re.sub(r"\s+", " ", m.group(1))

    def test_the_cpp_demands_the_same_type_in_and_out(self):
        """Es LA condición que hace que apagar un nodo no pueda romperle el tipo a nadie."""
        self.assertIn("T.InName == T.OutName", self.condicion())

    def test_the_cpp_refuses_sources_like_python_does(self):
        """Una fuente no tiene entrada que dejar pasar; `puede_bypass` la rechaza por `source` y por
        `aridad == 0`, y el C++ tiene que rechazarla por las dos mismas razones."""
        c = self.condicion()
        self.assertIn("!T.bSource", c)
        self.assertIn("T.Arity != 0", c)

    def test_both_sides_agree_on_every_verb_of_the_real_catalogue(self):
        """La prueba que de verdad importa: sobre los 140 verbos reales, ninguna discrepancia.

        Se reimplementa la condición del `.cpp` leyendo sus mismos campos y se compara verbo por
        verbo contra `puede_bypass`. Un desacuerdo acá significa que el canvas y Compile no
        coinciden en qué se puede apagar.
        """
        c = self.condicion()
        # El test anterior ya fijó la FORMA; acá se comprueba el ACUERDO sobre el catálogo real.
        self.assertIn("!T.InName.IsEmpty()", c)
        for verbo, info in tools.REGISTRO.items():
            segun_cpp = (not info.get("source") and info.get("aridad", 1) != 0
                         and bool(info.get("in_name"))
                         and info.get("in_name") == info.get("out_name"))
            self.assertEqual(puede_bypass(verbo, tools.REGISTRO), segun_cpp,
                             f"C++ y Python no coinciden sobre «{verbo}»")


class SelectTests(unittest.TestCase):
    """El condicional en dataflow: las dos ramas se calculan igual, el select elige cuál sigue.

    Es el Dispatch de Grasshopper y no el Branch de Blueprint — Jam no tiene pines de ejecución, así
    que poner un `select` NO ahorra el trabajo de la rama descartada.
    """

    def test_the_two_branches_and_the_output_are_the_same_type(self):
        """La regla que hace que el select no pueda romper el tipado: un verbo por familia, así se
        cumple por construcción y el error lo da el chequeo de cables de siempre."""
        for verbo, tipo in (("select_mesh", "M"), ("select_asset", "A")):
            info = tools.REGISTRO[verbo]
            self.assertEqual(info["out_name"], tipo, verbo)
            self.assertEqual(info["data_params"]["si"], tipo, verbo)
            self.assertEqual(info["data_params"]["no"], tipo, verbo)
            self.assertEqual(info["data_params"]["cond"], "B", verbo)

    def test_it_has_no_main_input_because_si_and_no_have_meaning(self):
        """Con entrada variádica las ramas entrarían por el mismo pin y se distinguirían por ORDEN
        de cable — invisible y frágil justo donde el orden significa algo."""
        for verbo in ("select_mesh", "select_asset"):
            self.assertTrue(tools.REGISTRO[verbo]["source"], verbo)
            self.assertEqual(tools.REGISTRO[verbo]["in_name"], "", verbo)

    def test_it_follows_the_true_branch(self):
        elegidos = []

        def select_fn(_entrada, *, cond=None, si=None, no=None):
            elegidos.append(si if cond else no)
            tools._RUNTIME_DATA_OUTPUTS["select_mesh"] = si if cond else no
            return "SELECT M ✓"

        graph = JamGraph()
        graph.add("select_mesh", {}, nid="sel")
        plan = GraphPlan(order=["sel"], params={"sel": {}}, input_assets={},
                         output_assets={}, values={}, values_by_node={})
        registry = {"select_mesh": {"fn": select_fn, "params": {},
                                    "data_params": {"cond": "B", "si": "M", "no": "M"}}}
        try:
            with mock.patch.object(tools, "REGISTRO", registry):
                _r, estados = ejecutar_detalle(graph, plan)
        finally:
            tools._RUNTIME_DATA_OUTPUTS.clear()
        self.assertEqual(estados["sel"]["estado"], "ok")

    def test_a_condition_without_a_cable_is_an_error_and_not_silently_false(self):
        """Sin cable, `cond` llega como None. Tratarlo como «falso» haría que el grafo eligiera
        siempre la rama «no» sin que nada avise — el peor modo de fallar de un condicional."""
        from jam.tools import t_select_mesh
        with self.assertRaises(RuntimeError) as ctx:
            t_select_mesh(None, cond=None, si="a", no="b")
        self.assertIn("cond", str(ctx.exception))

    def test_the_chosen_branch_must_actually_be_connected(self):
        from jam.tools import t_select_mesh
        with self.assertRaises(RuntimeError) as ctx:
            t_select_mesh(None, cond=True, si=None, no="b")
        self.assertIn("sí", str(ctx.exception))

    def test_a_comparison_can_drive_it(self):
        """La razón de ser de las comparaciones: son las únicas que producen el B que pide `cond`."""
        from jam import math_core
        self.assertEqual(math_core.tipo_salida("compare_greater"),
                         tools.REGISTRO["select_mesh"]["data_params"]["cond"])


class RerouteTests(unittest.TestCase):
    """Punto de paso con forma de NODO, estilo Blueprint.

    Convive con las vías sobre el cable: la vía es más liviana, el nodo se selecciona, se mueve con
    el grupo y sobrevive a copiar/pegar.
    """

    TIPOS = {"reroute_mesh": "M", "reroute_asset": "A", "reroute_points": "P",
             "reroute_curve": "S", "reroute_frames": "F"}

    def test_it_takes_and_returns_the_same_type(self):
        """Es la regla que hace que un reroute no pueda romper el tipado: si entrara M y saliera A,
        insertarlo en un cable cambiaría lo que llega abajo."""
        for verbo, tipo in self.TIPOS.items():
            info = tools.REGISTRO[verbo]
            self.assertEqual(info["in_name"], tipo, verbo)
            self.assertEqual(info["out_name"], tipo, verbo)

    def test_it_is_not_a_source_because_it_has_something_to_pass_through(self):
        for verbo in self.TIPOS:
            self.assertFalse(tools.REGISTRO[verbo]["source"], verbo)
            self.assertEqual(tools.REGISTRO[verbo]["aridad"], 1, verbo)

    def test_it_has_no_parameters_to_get_wrong(self):
        """Un punto de paso que se pudiera configurar dejaría de ser transparente."""
        for verbo in self.TIPOS:
            self.assertEqual(tools.REGISTRO[verbo]["params"], {}, verbo)

    def test_it_passes_the_data_through_untouched(self):
        """La propiedad entera del feature. Se apoya en que el runner cae a `entrada` cuando el
        verbo no produce salida propia — el mismo mecanismo del bypass."""
        recibido = []

        def consumidor(entrada, **_kw):
            recibido.append(entrada)
            return "consumidor ✓"

        graph = JamGraph()
        graph.add("reroute_mesh", {}, nid="rr")
        graph.add("place", {}, nid="fin")
        graph.connect("rr", "fin")
        plan = GraphPlan(order=["rr", "fin"], params={"rr": {}, "fin": {}},
                         input_assets={"rr": "/Game/X.X"}, output_assets={},
                         values={}, values_by_node={})
        registry = {"reroute_mesh": {"fn": tools.t_reroute, "params": {}},
                    "place": {"fn": consumidor, "params": {}}}
        with mock.patch.object(tools, "REGISTRO", registry):
            _r, estados = ejecutar_detalle(graph, plan)

        self.assertEqual(estados["rr"]["estado"], "ok")
        self.assertEqual(recibido, ["/Game/X.X"],
                         "el reroute tenía que dejar pasar exactamente lo que entró")

    def test_every_type_that_can_be_rerouted_can_also_be_bypassed(self):
        """Las dos reglas son la misma —recibir y producir el mismo tipo— así que un reroute que no
        admitiera bypass significaría que una de las dos se rompió."""
        for verbo in self.TIPOS:
            self.assertTrue(puede_bypass(verbo, tools.REGISTRO), verbo)


if __name__ == "__main__":
    unittest.main()


class PinQueAceptaVariosTiposTests(unittest.TestCase):
    """`place` toma un asset A y también la COLECCIÓN A[] de variantes.

    No es un comodín: la lista de tipos extra es cerrada y la escribe el registro. Y A[] arrastra
    un requisito —`points` cableado—, porque sin puntos habría que elegir una variante para colocar
    UNA, y eso no lo dijo nadie. El requisito viaja junto al tipo, no como regla suelta.
    """

    @staticmethod
    def _cadena(*, con_points: bool) -> JamGraph:
        g = JamGraph()
        g.add("brush", {}, nid="pincel")
        g.add("scatter", {"count": "12"}, nid="disp")
        g.add("asset", {"name": "/A.A"}, nid="a1")
        g.add("asset", {"name": "/B.B"}, nid="a2")
        g.add("asset_set", {}, nid="vars")
        g.add("place", {"physics": "True"}, nid="poner")
        g.connect("pincel", "disp")
        g.connect("a1", "vars")
        g.connect("a2", "vars")
        g.connect("vars", "poner")
        if con_points:
            g.connect("disp", "poner", "points")
        return g

    @staticmethod
    def _cableado(diagnosticos: dict) -> dict:
        """Sin motor los nodos `asset` no resuelven rutas. Eso no es lo que se está probando."""
        ruido = ("resolver asset", "no encontrado", "ObjectPath")
        limpio = {nid: [m for m in msgs if not any(r in m for r in ruido)]
                  for nid, msgs in diagnosticos.items()}
        return {nid: msgs for nid, msgs in limpio.items() if msgs}

    def test_a_collection_of_variants_can_feed_place(self):
        from jam.graph import validar
        self.assertEqual(self._cableado(validar(self._cadena(con_points=True))), {},
                         "A[] → place tendría que ser un cable legal")

    def test_a_collection_without_points_is_refused_with_a_reason(self):
        from jam.graph import validar
        diag = self._cableado(validar(self._cadena(con_points=False)))
        self.assertIn("poner", diag)
        self.assertTrue(any("points" in m for m in diag["poner"]),
                        f"tendría que nombrar el pin que falta: {diag}")

    def test_the_extra_types_are_a_closed_list_and_not_a_wildcard(self):
        """Un comodín aceptaría una malla o una curva. Sólo entra lo declarado."""
        from jam.graph import validar
        g = JamGraph()
        g.add("mesh_box", {}, nid="caja")
        g.add("scatter", {"count": "4"}, nid="disp")
        g.add("place", {}, nid="poner")
        g.connect("caja", "poner")
        g.connect("disp", "poner", "points")
        self.assertTrue(any("incompatible" in m for m in validar(g).get("caja", [])),
                        "una malla no puede entrar por el pin que acepta A y A[]")

    def test_the_spec_carries_the_extra_types_to_the_ui(self):
        """Si no viajan en el spec, el C++ tendría que conocer verbos por nombre."""
        import json
        spec = json.loads(tools.spec_json(include_graph_only=True))
        ficha = next(t for t in spec["tools"] if t["verbo"] == "place")
        self.assertEqual(ficha["in_accepts"], ["A[]"])

    def test_the_cpp_consults_the_extra_types_instead_of_hardcoding_place(self):
        """La regla de compatibilidad está forzosamente duplicada en Slate: si el C++ no mirara
        `InAccepts`, la UI rechazaría el cable que el Compile acepta — y no habría forma de tenderlo.
        """
        from pathlib import Path
        cpp = (Path(__file__).resolve().parents[3] / "Source" / "JamEditor" / "Private"
               / "SJamGraphEditor.cpp").read_text(encoding="utf-8")
        regla = cpp[cpp.index("static bool JamTiposCompatibles"):]
        regla = regla[:regla.index("\n}\n")]
        self.assertIn("Extras->Contains(OutType)", regla)
        codigo = "\n".join(l for l in regla.splitlines() if not l.strip().startswith("//"))
        self.assertNotIn("place", codigo,
                         "el C++ no puede conocer el verbo por nombre; lo declara el registro")
        self.assertEqual(cpp.count("JamTiposCompatibles(OutType, InType, Extras)"), 2,
                         "los DOS caminos —tender un cable y abrir un archivo— tienen que pasar "
                         "los tipos extra, o uno rechaza lo que el otro acepta")
