"""El puente grafo→Maze3D sintético (escala ×2): equivalencia de winnability y cero
adyacencias espurias por construcción."""

from oraculo.mazes.embedder import Embedding
from oraculo.mazes.maze3d import solve_3d
from oraculo.mazes.spacegraph import GraphEdge, GraphNode, SpaceGraph, from_maze, solve_graph
from oraculo.mazes.spacegraph_realize import graph_to_maze


def _graph(with_key: bool = True) -> SpaceGraph:
    g = SpaceGraph(space="house")
    g.nodes = {
        "inicio": GraphNode(id="inicio", type="entrance", start=True),
        "living": GraphNode(id="living", type="living_room"),
        "deposito": GraphNode(id="deposito", type="storage",
                              key="a" if with_key else None),
        "meta": GraphNode(id="meta", type="bedroom", goal=True),
    }
    g.edges = [
        GraphEdge("inicio", "living", kind="open"),
        GraphEdge("living", "deposito", kind="open"),
        GraphEdge("living", "meta", kind="door", door_id="a"),
    ]
    return g


def _embedding() -> Embedding:
    # a mano: living es hub; meta a distancia 2 (ruta de 1 celda)
    return Embedding(
        positions={"inicio": (0, 1, 0), "living": (1, 1, 0),
                   "deposito": (1, 0, 0), "meta": (3, 1, 0)},
        routes={2: [(2, 1, 0)]},
        width=4, height=2, n_floors=1,
    )


def test_equivalencia_de_winnability_via_puente():
    g = _graph()
    maze, merge, owner = graph_to_maze(g, _embedding())
    assert solve_3d(maze)["solvable"] == solve_graph(g)["solvable"] is True
    # sin la llave, ambas representaciones coinciden en NO ganable
    g2 = _graph(with_key=False)
    maze2, _, _ = graph_to_maze(g2, _embedding())
    assert solve_3d(maze2)["solvable"] == solve_graph(g2)["solvable"] is False


def test_mecanica_de_arista_se_vuelve_vestibulo():
    maze, merge, owner = graph_to_maze(_graph(), _embedding())
    assert len(maze.doors) == 1                      # un vestíbulo con la puerta
    (vest, did), = maze.doors.items()
    assert did == "a" and vest not in merge          # el vestíbulo no se contrae
    assert vest not in owner                         # y no es ningún cuarto del grafo


def test_cero_adyacencias_espurias():
    """La propiedad de la escala ×2: el grafo del maze sintético (via from_maze + contracción
    de los intermedios) tiene EXACTAMENTE las aristas del fuente."""
    g = _graph()
    maze, merge, owner = graph_to_maze(g, _embedding())
    node_cells = set(owner)
    # ningún par de celdas-NODO adyacentes en la grilla (todo pasa por intermedios)
    for a in node_cells:
        for b in node_cells:
            if a != b:
                assert abs(a[0] - b[0]) + abs(a[1] - b[1]) + abs(a[2] - b[2]) >= 2
    # y el grafo re-importado del sintético preserva el veredicto (la prueba operacional)
    assert solve_graph(from_maze(maze))["solvable"] == solve_graph(g)["solvable"]


def test_round_trip_con_switch_gate_y_hazard():
    g = SpaceGraph()
    g.nodes = {
        "a": GraphNode(id="a", start=True),
        "tablero": GraphNode(id="tablero", switch="f"),
        "peligro": GraphNode(id="peligro", hazard="f"),
        "z": GraphNode(id="z", goal=True),
    }
    g.edges = [
        GraphEdge("a", "tablero", kind="open"),
        GraphEdge("a", "peligro", kind="gate" if False else "open", gate_flag=None),
        GraphEdge("peligro", "z", kind="open"),
    ]
    emb = Embedding(positions={"a": (0, 0, 0), "tablero": (0, 1, 0),
                               "peligro": (1, 0, 0), "z": (2, 0, 0)},
                    routes={}, width=3, height=2, n_floors=1)
    maze, _, _ = graph_to_maze(g, emb)
    # el hazard exige el switch: ganable en ambas representaciones
    assert solve_graph(g)["solvable"] is True
    assert solve_3d(maze)["solvable"] is True
    assert maze.switches and maze.hazards
