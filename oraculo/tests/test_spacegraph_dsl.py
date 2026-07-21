"""Tests del DSL textual de SpaceGraph (G2)."""

from __future__ import annotations

import pytest

from src.mazes.spacegraph import realizable_static, solve_graph
from src.mazes.spacegraph_dsl import SPACEGRAPH_GBNF, build_gbnf, conforms, parse_space_graph


SPEC_EXAMPLE = """
# comentarios con '#'
@space hospital
@seed 7

node entrada  entrance  start
node pasillo  corridor  tags hub
node guardia  ward      dims 6x5
node deposito storage   key a
node tablero  nurse_station switch f1
node peligro  exam_room hazard f1
node meta     operating_room goal

edge entrada pasillo
edge pasillo guardia
edge pasillo deposito
edge guardia meta     door a
edge pasillo tablero
edge tablero peligro  gate f1
edge meta    deposito shortcut gate f1
"""


def test_parsea_ejemplo_completo_de_la_spec_y_es_ganable() -> None:
    graph = parse_space_graph(SPEC_EXAMPLE)

    assert graph.space == "hospital"
    assert graph.seed == 7
    assert graph.start() == "entrada"
    assert graph.goal() == "meta"
    assert graph.nodes["guardia"].dims == (6.0, 5.0)
    assert graph.nodes["pasillo"].tags == ("hub",)
    assert graph.nodes["deposito"].key == "a"
    assert graph.nodes["tablero"].switch == "f1"
    assert graph.nodes["peligro"].hazard == "f1"

    locked = next(edge for edge in graph.edges if {edge.a, edge.b} == {"guardia", "meta"})
    assert locked.kind == "open"
    assert locked.door_id == "a"

    assert realizable_static(graph) == []
    assert solve_graph(graph)["solvable"] is True


@pytest.mark.parametrize(
    "text, expected",
    [
        ("node a start\nnode a goal\n", "línea 2"),
        ("node a start\nedge a b\nnode b goal\n", "línea 2"),
        ("node a start\nnode b goal\nedge a a\n", "línea 3"),
        ("node a start\nnode b goal\nedge a b\nedge b a\n", "línea 4"),
        ("node a start\nnode b goal dims 2por3\n", "línea 2"),
        ("node a start\nnode b start goal\n", "línea 2"),
        ("node a start start\n", "línea 1"),
    ],
)
def test_errores_semanticos_reportan_linea_correcta(text: str, expected: str) -> None:
    with pytest.raises(ValueError, match=expected):
        parse_space_graph(text)


def test_kinds_y_modificadores_de_edge() -> None:
    graph = parse_space_graph(
        """
node a room start
node b room goal
node c room
node d room
edge a b shortcut gate f1
edge b c
edge c d stair
edge a d portal
"""
    )

    shortcut, default, stair, portal = graph.edges
    assert shortcut.kind == "shortcut"
    assert shortcut.gate_flag == "f1"
    assert shortcut.door_id is None
    assert default.kind == "open"
    assert stair.kind == "stair"
    assert portal.kind == "portal"


def test_hazard_bare_hazard_flag_tags_comas_y_dims_float() -> None:
    graph = parse_space_graph(
        """
node a room start hazard dims 6.5x.25 tags hub,leaf
node b room goal hazard f1 floor 2
edge a b
"""
    )

    assert graph.nodes["a"].hazard == ""
    assert graph.nodes["a"].dims == (6.5, 0.25)
    assert graph.nodes["a"].tags == ("hub", "leaf")
    assert graph.nodes["b"].hazard == "f1"
    assert graph.nodes["b"].floor == 2


def test_conforms_reusa_el_parser() -> None:
    valid = "node a start\nnode b goal\nedge a b\n"
    invalid = "node a start\nedge a b\n"

    assert conforms(valid) is True
    parse_space_graph(valid)

    assert conforms(invalid) is False
    with pytest.raises(ValueError, match="línea 2"):
        parse_space_graph(invalid)


def test_spacegraph_gbnf_expone_producciones_clave() -> None:
    assert SPACEGRAPH_GBNF == build_gbnf()
    for production in ("node_line", "edge_line", "space_decl"):
        assert production in SPACEGRAPH_GBNF
    for token in ('"node"', '"edge"', '"@space"', '"@seed"', '"shortcut"', '"stair"', '"portal"'):
        assert token in SPACEGRAPH_GBNF
