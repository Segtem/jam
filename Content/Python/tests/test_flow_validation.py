from __future__ import annotations

import unittest

from jam.flow import Flow, FlowValidationError


class FlowValidationTests(unittest.TestCase):
    def test_unary_node_requires_input(self) -> None:
        flow = Flow()
        flow.add("move", {}, "move")

        with self.assertRaises(FlowValidationError) as caught:
            flow.evaluar()

        self.assertIn("move", caught.exception.diagnostics)
        self.assertIn("recibió 0", " ".join(caught.exception.diagnostics["move"]))

    def test_unary_node_rejects_multiple_streams(self) -> None:
        flow = Flow()
        flow.add("pts_line", {"count": 2}, "line")
        flow.add("pts_circle", {"count": 5}, "circle")
        flow.add("move", {}, "move")
        flow.connect("line", "move")
        flow.connect("circle", "move")

        with self.assertRaises(FlowValidationError) as caught:
            flow.evaluar()

        self.assertIn("recibió 2", " ".join(caught.exception.diagnostics["move"]))

    def test_parameter_wire_must_match_type(self) -> None:
        flow = Flow()
        flow.add("pts_line", {"count": 2}, "line")
        flow.add("pts_circle", {"count": 5}, "points")
        flow.add("move", {"dx": 25.0}, "move")
        flow.connect("line", "move")
        flow.connect("points", "move", "dx")

        with self.assertRaises(FlowValidationError) as caught:
            flow.evaluar()

        self.assertIn("esperaba N, recibió P", " ".join(caught.exception.diagnostics["move"]))

    def test_number_can_drive_numeric_parameter(self) -> None:
        flow = Flow()
        flow.add("pts_line", {"count": 2}, "line")
        flow.add("number", {"name": "offset", "value": 25.0}, "number")
        flow.add("move", {"dx": 0.0}, "move")
        flow.connect("line", "move")
        flow.connect("number", "move", "dx")

        output = flow.evaluar()

        self.assertEqual(len(output["move"]), 2)
        self.assertEqual(output["move"][0].pos.x, 25.0)

    def test_variadic_node_consumes_all_streams(self) -> None:
        flow = Flow()
        flow.add("pts_line", {"count": 2}, "line")
        flow.add("pts_circle", {"count": 5}, "circle")
        flow.add("merge", {}, "merge")
        flow.connect("line", "merge")
        flow.connect("circle", "merge")

        output = flow.evaluar()

        self.assertEqual(len(output["merge"]), 7)

    def test_unknown_operation_is_an_error(self) -> None:
        flow = Flow()
        flow.add("renamed_or_removed", {}, "old")

        with self.assertRaises(FlowValidationError) as caught:
            flow.evaluar()

        self.assertIn("operación desconocida", " ".join(caught.exception.diagnostics["old"]))

    def test_info_metadata_is_available_without_polluting_params(self) -> None:
        flow = Flow()
        flow.add("pts_line", {"count": 3}, "line")
        flow.add("info", {}, "info")
        flow.connect("line", "info")

        output = flow.evaluar()

        self.assertEqual(len(output["info"]), 3)
        self.assertEqual(flow.resultados["info"]["stats"]["n"], 3)
        self.assertNotIn("_stats", flow.nodos["info"]["params"])

    def test_duplicate_variable_names_are_rejected(self) -> None:
        flow = Flow()
        flow.add("number", {"name": "n", "value": 1}, "one")
        flow.add("number", {"name": "n", "value": 2}, "two")

        with self.assertRaises(FlowValidationError) as caught:
            flow.evaluar()

        self.assertIn("duplicado", " ".join(caught.exception.diagnostics["one"]))
        self.assertIn("duplicado", " ".join(caught.exception.diagnostics["two"]))


if __name__ == "__main__":
    unittest.main()
