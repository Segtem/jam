"""Ronda 2 · Corte 3 — canal de TAREAS-DAG grafo-nativo (profundidad VotV).

Porta `mazes/tasks.py` (grilla) al grafo: cada nodo puede hospedar una tarea con dependencias; ganar
exige completar TODAS las tareas EN ORDEN válido (deps HECHAS antes) y llegar al goal. Mismo patrón
multi-aspecto que electric/resource (Corte 2). El DAG se sanea (deps existen, sin ciclos)."""

from src.mazes.spacegraph import GraphEdge, GraphNode, SpaceGraph
from src.mazes.spacegraph_channels import dag_check_graph, solve_tasks_graph


def _g(nodes, edges):
    return SpaceGraph(nodes={n.id: n for n in nodes}, edges=list(edges))


def test_tareas_en_orden_valido_ganable():
    # t1 en 'a1', t2 (dep t1) en 'a2'; el camino pasa por a1 antes que a2 → completable
    nodes = [GraphNode("start", "entrance", start=True),
             GraphNode("a1", "storage", task=("t1", ())),
             GraphNode("a2", "ward", task=("t2", ("t1",))),
             GraphNode("meta", "operating_room", goal=True)]
    edges = [GraphEdge("start", "a1", kind="open"),
             GraphEdge("a1", "a2", kind="open"),
             GraphEdge("a2", "meta", kind="open")]
    assert solve_tasks_graph(_g(nodes, edges))["solvable"]


def test_dep_inalcanzable_antes_no_ganable():
    # t2 (dep t1) está ANTES de t1 en el único camino → nunca se completa t2 → no ganable
    nodes = [GraphNode("start", "entrance", start=True),
             GraphNode("a2", "ward", task=("t2", ("t1",))),
             GraphNode("a1", "storage", task=("t1", ())),
             GraphNode("meta", "operating_room", goal=True)]
    edges = [GraphEdge("start", "a2", kind="open"),
             GraphEdge("a2", "a1", kind="open"),
             GraphEdge("a1", "meta", kind="open")]
    # con require_goal=True (default) y todas las tareas obligatorias, no hay orden válido en línea
    assert not solve_tasks_graph(_g(nodes, edges))["solvable"]


def test_dag_check_detecta_ciclo_y_dep_faltante():
    ciclo = [GraphNode("start", "entrance", start=True, task=("t1", ("t2",))),
             GraphNode("meta", "operating_room", goal=True, task=("t2", ("t1",)))]
    fails = dag_check_graph(_g(ciclo, [GraphEdge("start", "meta", kind="open")]))
    assert fails and any("ciclo" in f.lower() for f in fails)

    falta = [GraphNode("start", "entrance", start=True, task=("t1", ("fantasma",))),
             GraphNode("meta", "operating_room", goal=True)]
    fails2 = dag_check_graph(_g(falta, [GraphEdge("start", "meta", kind="open")]))
    assert fails2 and any("fantasma" in f for f in fails2)


def test_sin_tareas_intacto():
    nodes = [GraphNode("a", "entrance", start=True),
             GraphNode("b", "ward", goal=True)]
    g = _g(nodes, [GraphEdge("a", "b", kind="open")])
    # sin tareas declaradas, el canal no exige nada (retro-compatible)
    assert dag_check_graph(g) == []
    assert solve_tasks_graph(g)["solvable"]
