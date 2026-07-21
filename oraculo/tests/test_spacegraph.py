from __future__ import annotations

from dataclasses import replace
from itertools import combinations

from src.mazes.maze3d import (
    Maze3D,
    add_door,
    add_gate,
    add_hazard,
    add_key,
    add_portal,
    add_switch,
    solve_3d,
)
from src.mazes.spacegraph import GraphEdge, GraphNode, SpaceGraph, from_maze, realizable_static, solve_graph


def _graph(nodes: list[GraphNode], edges: list[GraphEdge]) -> SpaceGraph:
    return SpaceGraph(nodes={node.id: node for node in nodes}, edges=edges)


def test_solve_graph_cadena_simple() -> None:
    graph = _graph(
        [GraphNode("s", start=True), GraphNode("a"), GraphNode("g", goal=True)],
        [GraphEdge("s", "a", kind="open"), GraphEdge("a", "g", kind="open")],
    )

    res = solve_graph(graph)

    assert res["solvable"] is True
    assert res["optimal_steps"] == 2
    assert res["path"] == ["s", "a", "g"]


def test_solve_graph_door_key_obliga_desvio() -> None:
    graph = _graph(
        [
            GraphNode("s", start=True),
            GraphNode("a"),
            GraphNode("key_room", key="k"),
            GraphNode("door_room"),
            GraphNode("g", goal=True),
        ],
        [
            GraphEdge("s", "a", kind="open"),
            GraphEdge("a", "door_room", kind="door", door_id="k"),
            GraphEdge("door_room", "g", kind="open"),
            GraphEdge("a", "key_room", kind="open"),
        ],
    )

    res = solve_graph(graph)

    assert res["solvable"] is True
    assert res["optimal_steps"] == 5
    assert res["path"] == ["s", "a", "key_room", "a", "door_room", "g"]

    no_key = replace(graph.nodes["key_room"], key=None)
    blocked = SpaceGraph(nodes={**graph.nodes, "key_room": no_key}, edges=graph.edges)
    assert solve_graph(blocked)["solvable"] is False


def test_solve_graph_gate_exige_toggle() -> None:
    graph = _graph(
        [
            GraphNode("s", start=True),
            GraphNode("switch", switch="f"),
            GraphNode("gate_room"),
            GraphNode("g", goal=True),
        ],
        [
            GraphEdge("s", "switch", kind="open"),
            GraphEdge("switch", "gate_room", kind="open", gate_flag="f"),
            GraphEdge("gate_room", "g", kind="open"),
        ],
    )

    res = solve_graph(graph)

    assert res["solvable"] is True
    assert res["optimal_steps"] == 3
    assert res["path"] == ["s", "switch", "gate_room", "g"]


def test_solve_graph_switch_permite_no_togglear_en_revisita() -> None:
    graph = _graph(
        [
            GraphNode("s", start=True),
            GraphNode("switch", switch="f"),
            GraphNode("first_gate"),
            GraphNode("key_room", key="k"),
            GraphNode("g", goal=True),
        ],
        [
            GraphEdge("s", "switch", kind="open"),
            GraphEdge("switch", "first_gate", kind="open", gate_flag="f"),
            GraphEdge("first_gate", "key_room", kind="open"),
            GraphEdge("switch", "g", kind="open", door_id="k", gate_flag="f"),
        ],
    )

    res = solve_graph(graph)

    assert res["solvable"] is True
    assert res["optimal_steps"] == 6
    assert res["path"] == ["s", "switch", "first_gate", "key_room", "first_gate", "switch", "g"]
    assert res["path"].count("switch") == 2


def test_solve_graph_hazard_bloquea_y_switch_desarma() -> None:
    blocked = _graph(
        [GraphNode("s", start=True), GraphNode("hazard", hazard=""), GraphNode("g", goal=True)],
        [GraphEdge("s", "hazard", kind="open"), GraphEdge("hazard", "g", kind="open")],
    )
    assert solve_graph(blocked)["solvable"] is False

    disarmed = _graph(
        [
            GraphNode("s", start=True),
            GraphNode("switch", switch="safe"),
            GraphNode("hazard", hazard="safe"),
            GraphNode("g", goal=True),
        ],
        [
            GraphEdge("s", "switch", kind="open"),
            GraphEdge("switch", "hazard", kind="open"),
            GraphEdge("hazard", "g", kind="open"),
        ],
    )
    res = solve_graph(disarmed)
    assert res["solvable"] is True
    assert res["path"] == ["s", "switch", "hazard", "g"]


def test_solve_graph_shortcut_gateado_cambia_optimo() -> None:
    def build(with_switch: bool) -> SpaceGraph:
        return _graph(
            [
                GraphNode("s", start=True),
                GraphNode("a"),
                GraphNode("b"),
                GraphNode("c"),
                GraphNode("switch", switch="f" if with_switch else None),
                GraphNode("g", goal=True),
            ],
            [
                GraphEdge("s", "a", kind="open"),
                GraphEdge("a", "b", kind="open"),
                GraphEdge("b", "c", kind="open"),
                GraphEdge("c", "g", kind="open"),
                GraphEdge("s", "switch", kind="open"),
                GraphEdge("switch", "g", kind="shortcut", gate_flag="f"),
            ],
        )

    without_flag = solve_graph(build(with_switch=False))
    with_flag = solve_graph(build(with_switch=True))

    assert without_flag["solvable"] is True
    assert without_flag["optimal_steps"] == 4
    assert with_flag["solvable"] is True
    assert with_flag["optimal_steps"] == 2
    assert with_flag["path"] == ["s", "switch", "g"]


def test_solve_graph_truncated_es_conservador() -> None:
    graph = _graph(
        [GraphNode("s", start=True), GraphNode("a"), GraphNode("g", goal=True)],
        [GraphEdge("s", "a", kind="open"), GraphEdge("a", "g", kind="open")],
    )

    res = solve_graph(graph, max_states=1)

    assert res["solvable"] is False
    assert res["truncated"] is True
    assert res["optimal_steps"] is None


def test_realizable_static_ok_y_fallas_basicas() -> None:
    ok = _graph(
        [GraphNode("s", start=True), GraphNode("g", goal=True)],
        [GraphEdge("s", "g", kind="open")],
    )
    assert realizable_static(ok) == []

    broken_ref = _graph(
        [GraphNode("s", start=True), GraphNode("g", goal=True)],
        [GraphEdge("s", "missing", kind="open")],
    )
    assert any("referencia rota" in failure for failure in realizable_static(broken_ref))

    two_starts = _graph(
        [GraphNode("s", start=True), GraphNode("s2", start=True), GraphNode("g", goal=True)],
        [GraphEdge("s", "g", kind="open"), GraphEdge("s2", "g", kind="open")],
    )
    assert any("exactamente 1 start" in failure for failure in realizable_static(two_starts))

    disconnected = _graph(
        [GraphNode("s", start=True), GraphNode("g", goal=True), GraphNode("island")],
        [GraphEdge("s", "g", kind="open")],
    )
    assert any("no conectado" in failure for failure in realizable_static(disconnected))

    nodes = [GraphNode(f"n{i}", start=i == 0, goal=i == 1) for i in range(5)]
    k5 = _graph(nodes, [GraphEdge(a.id, b.id, kind="open") for a, b in combinations(nodes, 2)])
    k5_failures = realizable_static(k5)
    assert any("no planar barato" in failure for failure in k5_failures)
    assert any("K5" in failure for failure in k5_failures)

    star_nodes = [GraphNode("hub", start=True)] + [
        GraphNode(f"leaf{i}", goal=i == 0) for i in range(9)
    ]
    high_degree = _graph(star_nodes, [GraphEdge("hub", f"leaf{i}", kind="open") for i in range(9)])
    assert any("grado > 8" in failure for failure in realizable_static(high_degree))


def test_from_maze_equivale_a_solve_3d_en_bateria_legacy() -> None:
    simple = Maze3D.from_layers([["#####", "#P.G#", "#####"]])

    locked = Maze3D.from_layers([["#######", "#P...G#", "#######"]])
    add_key(locked, (2, 1, 0), "a")
    add_door(locked, (3, 1, 0), "a")

    switched = Maze3D.from_layers([["#######", "#P...G#", "#######"]])
    add_switch(switched, (2, 1, 0), "f")
    add_gate(switched, (4, 1, 0), "f")

    hazard = Maze3D.from_layers([["#######", "#P.X.G#", "#######"]])
    add_hazard(hazard, (3, 1, 0))

    vertical = Maze3D.from_layers(
        [["###", "#P#", "###"], ["###", "#G#", "###"]],
        extra_connectors={(1, 1, 0)},
    )

    portal = Maze3D.from_layers([["#######", "#P#..G#", "#######"]])
    add_portal(portal, (1, 1, 0), (3, 1, 0))

    for maze in [simple, locked, switched, hazard, vertical, portal]:
        assert solve_graph(from_maze(maze))["solvable"] == solve_3d(maze)["solvable"]


def test_normalize_hubs_parte_el_distribuidor_y_preserva_la_mision():
    """Un pasillo de grado 8 (sin mecánica) se parte en cadena de segmentos grado ≤4; la
    winnability y el veredicto estático quedan bien, y los hubs CON mecánica no se tocan."""
    from src.mazes.spacegraph import (GraphEdge, GraphNode, SpaceGraph, normalize_hubs,
                                      realizable_static, solve_graph)
    g = SpaceGraph(space="house")
    g.nodes["pasillo"] = GraphNode("pasillo", type="hallway")
    g.nodes["inicio"] = GraphNode("inicio", type="entrance", start=True)
    g.edges.append(GraphEdge("inicio", "pasillo", kind="open"))
    for i in range(7):
        nid = f"cuarto_{i}"
        g.nodes[nid] = GraphNode(nid, type="bedroom", goal=(i == 6))
        g.edges.append(GraphEdge("pasillo", nid, kind="open"))
    assert any("grado in-plane" in f for f in realizable_static(g))
    n = normalize_hubs(g)
    assert not any("grado in-plane" in f for f in realizable_static(n))
    assert solve_graph(n)["solvable"]
    segs = [nid for nid in n.nodes if nid.startswith("pasillo")]
    assert len(segs) >= 3 and all(n.nodes[s].type == "hallway" for s in segs)
    # un hub CON mecánica: se extrae un LOBBY (la mecánica queda en el nodo original,
    # con grado bajo; el lobby absorbe el exceso) y el grafo sigue ganable
    g.nodes["pasillo"] = GraphNode("pasillo", type="hallway", key="a")
    n2 = normalize_hubs(g)
    assert "pasillo__lobby" in n2.nodes
    assert n2.nodes["pasillo"].key == "a" and n2.nodes["pasillo__lobby"].key is None
    assert not any("grado in-plane" in f for f in realizable_static(n2))
    assert solve_graph(n2)["solvable"]
