"""Necesidad contrafáctica sobre grafos: cada tipo de item con su caso necesario y su caso
decorativo — la MISMA semántica que item_necessity de maze3d."""

from src.mazes.spacegraph import GraphEdge, GraphNode, SpaceGraph
from src.mazes.spacegraph_interest import interest_report, item_necessity_graph


def _chain(n: int) -> SpaceGraph:
    """Cadena a0—a1—…—a(n-1), start en a0, goal al final."""
    g = SpaceGraph()
    for i in range(n):
        g.nodes[f"a{i}"] = GraphNode(f"a{i}", start=(i == 0), goal=(i == n - 1))
    g.edges = [GraphEdge(f"a{i}", f"a{i+1}", kind="open") for i in range(n - 1)]
    return g


def test_door_necesaria_vs_decorativa():
    # necesaria: la llave exige desvío (key colgada de un ramal)
    g = _chain(5)
    g.nodes["llave"] = GraphNode("llave", key="k")
    g.edges.append(GraphEdge("a1", "llave", kind="open"))
    g.edges[3] = GraphEdge("a3", "a4", kind="door", door_id="k")
    nec = item_necessity_graph(g)
    assert nec["decorative_items"] == 0 and nec["n_items"] == 2   # door + key
    # decorativa: la llave está EN el camino (a1) → quitar la puerta no cambia el óptimo
    g2 = _chain(5)
    g2.nodes["a1"] = GraphNode("a1", key="k")
    g2.edges[3] = GraphEdge("a3", "a4", kind="door", door_id="k")
    nec2 = item_necessity_graph(g2)
    assert nec2["decorative_items"] == 2                          # la puerta Y su llave
    assert any("door k" in d for d in nec2["decorative"])


def test_gate_switch_y_hazard():
    # gate necesario: el switch exige desvío; hazard del mismo flag sobre ruta alternativa
    g = _chain(6)
    g.nodes["tablero"] = GraphNode("tablero", switch="f")
    g.edges.append(GraphEdge("a2", "tablero", kind="open"))
    g.edges[4] = GraphEdge("a4", "a5", kind="gate", gate_flag="f")
    nec = item_necessity_graph(g)
    assert nec["decorative_items"] == 0
    # hazard decorativo: en un ramal muerto que nadie necesita cruzar
    g.nodes["pozo"] = GraphNode("pozo", hazard="")
    g.edges.append(GraphEdge("a1", "pozo", kind="open"))
    nec2 = item_necessity_graph(g)
    assert any("hazard (pozo)" in d for d in nec2["decorative"])


def test_shortcut_decorativo_vs_util():
    # shortcut sin gating que NO acorta (paralelo a una arista existente vía nodo extra) = ruido
    g = _chain(4)
    g.nodes["rodeo"] = GraphNode("rodeo")
    g.edges.append(GraphEdge("a0", "rodeo", kind="open"))
    g.edges.append(GraphEdge("rodeo", "a3", kind="shortcut"))    # a0→rodeo→a3 = 2 vs directo 3
    nec = item_necessity_graph(g)
    assert nec["n_items"] == 1 and nec["decorative_items"] == 0  # acorta: 3→2 → NECESARIO
    # y uno que no acorta nada:
    g2 = _chain(4)
    g2.nodes["rodeo"] = GraphNode("rodeo")
    g2.edges.append(GraphEdge("a2", "rodeo", kind="open"))
    g2.edges.append(GraphEdge("rodeo", "a3", kind="shortcut"))   # a2→rodeo→a3 = 2 vs directo 1
    nec2 = item_necessity_graph(g2)
    assert nec2["decorative_items"] == 1


SPEC_HOSPITAL = """@space hospital
node entrada  entrance  start
node pasillo  corridor
node guardia  ward      dims 6x5
node guardia2 ward
node deposito storage   key a
node tablero  nurse_station switch f1
node peligro  exam_room hazard f1
node meta     operating_room goal
edge entrada pasillo
edge pasillo guardia
edge pasillo guardia2
edge guardia2 tablero
edge pasillo deposito
edge guardia meta     door a
edge tablero peligro  gate f1
edge meta    deposito shortcut gate f1
"""


def test_interest_report_gatea():
    corto = _chain(3)                                # ganable pero paseo corto sin items
    r = interest_report(corto)
    assert not r["interesting"]
    assert any("corto" in x or "paseo" in x for x in r["reasons"])
    # y un grafo con mecánicas necesarias y largo decente SÍ pasa
    g = _chain(8)
    g.nodes["llave"] = GraphNode("llave", key="k")
    g.edges.append(GraphEdge("a2", "llave", kind="open"))
    g.edges[5] = GraphEdge("a5", "a6", kind="door", door_id="k")
    r2 = interest_report(g)
    assert r2["interesting"] and r2["quality"] > 2000


def test_el_hospital_de_la_spec_que_dice_el_gate():
    """Medición honesta sobre nuestro propio ejemplo: el gate reporta QUÉ items importan."""
    from src.mazes.spacegraph_dsl import parse_space_graph
    r = interest_report(parse_space_graph(SPEC_HOSPITAL))
    assert r["solvable"] and r["n_items"] >= 5
    # el reporte es accionable: si algo es decorativo, lo nombra
    if not r["interesting"]:
        assert r["reasons"] and all(isinstance(x, str) for x in r["reasons"])