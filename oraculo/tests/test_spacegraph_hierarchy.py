"""Corte 3 — jerarquía @expand con puertos (G4): el sitio compuesto de sub-grafos.

Un nodo se EXPANDE a un sub-grafo; el sub-grafo declara `port` que ligan a las aristas del padre.
El oráculo APLANA (sustitución en los puertos) y corre solve_graph sobre el grafo plano —
jerárquico ≡ plano. La realización embebe el grafo aplanado con el embedder existente (V1)."""

from oraculo.mazes.spacegraph import solve_graph
from oraculo.mazes.spacegraph_dsl import parse_space_graph
from oraculo.mazes.spacegraph_hierarchy import flatten_hierarchy

SITIO = """@space hospital
subgraph ala {
  node p1 corridor port
  node cama ward
  node p2 corridor port
  edge p1 cama
  edge cama p2
}
node entrada entrance start
node hub corridor @expand ala
node meta operating_room goal
edge entrada hub
edge hub meta
"""


def test_parse_declara_subgrafo_y_expand():
    g = parse_space_graph(SITIO)
    assert "ala" in g.subgraphs
    sub = g.subgraphs["ala"]
    assert len(sub.nodes) == 3 and len(sub.edges) == 2
    assert sub.ports == ["p1", "p2"]           # en orden de declaración
    assert g.nodes["hub"].expand == "ala"


def test_flatten_inlina_en_los_puertos():
    g = parse_space_graph(SITIO)
    flat = flatten_hierarchy(g)
    # hub desaparece; entran los nodos del sub-grafo (id-prefijados, sin colisión)
    assert "hub" not in flat.nodes
    assert not any(n.expand for n in flat.nodes.values())
    # entrada, meta + los 3 del ala (ala__p1, ala__cama, ala__p2) = 5
    assert len(flat.nodes) == 5
    # las aristas del padre se re-conectan a los puertos en orden
    ids = set(flat.nodes)
    assert {"entrada", "meta"} <= ids
    assert any(nid.endswith("p1") for nid in ids) and any(nid.endswith("cama") for nid in ids)


def test_ganabilidad_del_plano():
    g = parse_space_graph(SITIO)
    flat = flatten_hierarchy(g)
    sol = solve_graph(flat)
    # entrada → ala__p1 → ala__cama → ala__p2 → meta = 4 aristas
    assert sol["solvable"] and sol["optimal_steps"] == 4


def test_grafo_sin_jerarquia_intacto():
    plano = """@space hospital
node a entrance start
node b corridor
node c ward goal
edge a b
edge b c
"""
    g = parse_space_graph(plano)
    assert g.subgraphs == {}
    flat = flatten_hierarchy(g)
    # sin @expand, aplanar es identidad (mismos nodos/aristas)
    assert set(flat.nodes) == set(g.nodes) and len(flat.edges) == len(g.edges)
    assert solve_graph(flat)["optimal_steps"] == 2
