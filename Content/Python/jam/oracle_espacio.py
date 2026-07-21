"""Oráculo de ESPACIO para BotOO — winnability de un mapa de extracción.

Modela el loop de Hunt: Showdown con las primitivas del grafo (`oraculo.mazes.spacegraph`):

    entrada --- pista(da el "sello") --- ... --- cripta(jefe) --( puerta: exige sello )-- extracción

- `key` en un nodo  = pickup al ENTRAR (la pista te entrega el sello para desterrar al Antiguo).
- `door_id` en una arista = exige tener esa llave (no extraés sin haber banisheado al jefe).
- `start`/`goal` = entrada / punto de extracción.

El oráculo (`solve_graph`, BFS sobre (nodo, llaves, flags)) dictamina si el mapa se puede
TERMINAR. Un mapa donde el sello es inalcanzable → `solvable=False`: eso es lo que Dash no puede
decirte. Acá los grafos son demos en código; la próxima rebanada los lee del nivel real.
"""

from __future__ import annotations

from . import bridge

bridge.ensure_oraculo_on_path()

from oraculo.mazes.spacegraph import SpaceGraph, GraphNode, GraphEdge, solve_graph  # noqa: E402


def _n(id: str, **kw) -> GraphNode:
    return GraphNode(id=id, type=kw.pop("type", "room"), **kw)


def mapa_botoo_ganable() -> SpaceGraph:
    """Un contrato de extracción SANO: la pista entrega el sello, con él se extrae."""
    nodes = {
        "entrada": _n("entrada", type="spawn", start=True),
        "pista": _n("pista", type="clue", key="sello_antiguo"),
        "galeria": _n("galeria"),
        "cripta": _n("cripta", type="boss"),
        "extraccion": _n("extraccion", type="extract", goal=True),
    }
    edges = [
        GraphEdge(a="entrada", b="pista", kind="door"),
        GraphEdge(a="entrada", b="galeria", kind="door"),
        GraphEdge(a="galeria", b="cripta", kind="door"),
        # sólo se extrae con el sello (desterraste al Antiguo):
        GraphEdge(a="cripta", b="extraccion", kind="door", door_id="sello_antiguo"),
    ]
    return SpaceGraph(nodes=nodes, edges=edges, space="extraction")


def mapa_botoo_roto() -> SpaceGraph:
    """El MISMO mapa pero con la pista amurallada: el sello es inalcanzable → NO ganable.

    Es el caso que prueba que el oráculo no es un sello de goma: un diseñador que olvida
    conectar la pista produce un mapa de extracción imposible, y el oráculo lo caza."""
    g = mapa_botoo_ganable()
    # cortamos la única arista que llega a la pista:
    g.edges = [e for e in g.edges if not (e.a == "entrada" and e.b == "pista")]
    return g


def veredicto(graph: SpaceGraph) -> dict:
    """Corre el oráculo y devuelve el dict crudo de `solve_graph`."""
    return solve_graph(graph)


def veredicto_texto(nombre: str, graph: SpaceGraph) -> str:
    """Veredicto legible para mostrar en el editor / log."""
    r = veredicto(graph)
    if r["solvable"]:
        camino = " → ".join(r["path"])
        return (f"[{nombre}] GANABLE ✓  ({r['optimal_steps']} tramos, "
                f"{r['states_explored']} estados)\n   ruta óptima: {camino}")
    razon = r.get("reason", "sin ruta que complete la extracción")
    return f"[{nombre}] NO GANABLE ✗  — {razon}  ({r['states_explored']} estados explorados)"
