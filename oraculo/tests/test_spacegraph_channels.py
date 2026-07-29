"""Corte 2 — canales NO-nav sobre el grafo de misión (G1.5).

Verifica los oráculos grafo-nativos portados de la grilla (electric/resource/couple) y su composición
en el `GraphOracle` de la fachada. Retro-compatibilidad DURA: un grafo sin canales se comporta idéntico."""

from dataclasses import replace

from oraculo.mazes.spacegraph import GraphEdge, GraphNode, SpaceGraph, solve_graph
from oraculo.mazes.spacegraph_channels import (all_powered_graph,
                                           solve_survival_graph)


def _g(nodes, edges, **kw):
    return SpaceGraph(nodes={n.id: n for n in nodes}, edges=list(edges), **kw)


# ── Canal ELÉCTRICO: BFS sobre aristas cable desde una fuente ───────────────────────────────────────

def test_electrico_load_energizada_por_cable():
    nodes = [GraphNode("gen", "server_room", power="source", start=True),
             GraphNode("sala", "ward", power="load", goal=True)]
    edges = [GraphEdge("gen", "sala", kind="cable")]
    fails = all_powered_graph(_g(nodes, edges))
    assert fails == []


def test_electrico_load_sin_cable_falla_con_razon():
    nodes = [GraphNode("gen", "server_room", power="source", start=True),
             GraphNode("sala", "ward", power="load", goal=True)]
    edges = [GraphEdge("gen", "sala", kind="open")]           # vano, no cable → no conduce energía
    fails = all_powered_graph(_g(nodes, edges))
    assert fails and any("sala" in f for f in fails)


# ── Canal RECURSO: BFS presupuestado start→goal con drain/refill por nodo ────────────────────────────

def test_recurso_presupuesto_alcanza():
    nodes = [GraphNode("a", "entrance", start=True),
             GraphNode("b", "corridor", drain=("fuel", 3)),
             GraphNode("c", "ward", drain=("fuel", 3), goal=True)]
    edges = [GraphEdge("a", "b", kind="open"), GraphEdge("b", "c", kind="open")]
    g = _g(nodes, edges, resources={"fuel": (10, 0, 10)})
    assert solve_survival_graph(g, "fuel")["solvable"]


def test_recurso_presupuesto_insuficiente_no_llega_vivo():
    nodes = [GraphNode("a", "entrance", start=True),
             GraphNode("b", "corridor", drain=("fuel", 8)),
             GraphNode("c", "ward", drain=("fuel", 8), goal=True)]
    edges = [GraphEdge("a", "b", kind="open"), GraphEdge("b", "c", kind="open")]
    g = _g(nodes, edges, resources={"fuel": (10, 0, 10)})
    assert not solve_survival_graph(g, "fuel")["solvable"]


def test_recurso_refill_repone():
    nodes = [GraphNode("a", "entrance", start=True),
             GraphNode("depot", "storage", refill=("fuel", 6)),
             GraphNode("b", "corridor", drain=("fuel", 8)),
             GraphNode("c", "ward", drain=("fuel", 8), goal=True)]
    edges = [GraphEdge("a", "depot", kind="open"), GraphEdge("depot", "b", kind="open"),
             GraphEdge("b", "c", kind="open")]
    g = _g(nodes, edges, resources={"fuel": (10, 0, 10)})
    assert solve_survival_graph(g, "fuel")["solvable"]


# ── Retro-compatibilidad: sin canales, el veredicto de nav es idéntico ───────────────────────────────

def test_sin_canales_nav_pura_intacta():
    nodes = [GraphNode("a", "entrance", start=True),
             GraphNode("b", "corridor"),
             GraphNode("c", "ward", goal=True)]
    edges = [GraphEdge("a", "b"), GraphEdge("b", "c")]
    g = _g(nodes, edges)
    sol = solve_graph(g)
    assert sol["solvable"] and sol["optimal_steps"] == 2
    # sin power declarado, el canal eléctrico no aplica (no hay loads → nada que energizar)
    assert all_powered_graph(g) == []
