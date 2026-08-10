"""Sensor puro del subconjunto de JamSpace que hoy produce el nivel de Unreal.

La recursión para alcanzar la extracción vive acá, del lado sensor: el catálogo declarativo sólo
juzga los hechos resultantes. Este módulo no importa Unreal, Oracle ni el solver de referencia.
"""

from __future__ import annotations

from collections import deque


_CAMPOS_DE_NODO_NO_SOPORTADOS = (
    "switch", "hazard", "power", "drain", "refill", "expand", "task",
)
_ARISTAS_NAVEGABLES = {"door", "open", "stair", "portal", "shortcut"}


def configuracion_no_soportada(graph) -> tuple[str, ...]:
    """Enumera capacidades históricas que el contrato declarativo vivo aún no representa."""
    problemas = []
    for nodo in graph.nodes.values():
        for campo in _CAMPOS_DE_NODO_NO_SOPORTADOS:
            if getattr(nodo, campo, None) is not None:
                problemas.append(f"nodo {nodo.id}: {campo}")
    for arista in graph.edges:
        if getattr(arista, "kind", "door") not in _ARISTAS_NAVEGABLES:
            problemas.append(f"arista {arista.a}-{arista.b}: kind={arista.kind}")
        if getattr(arista, "gate_flag", None) is not None:
            problemas.append(f"arista {arista.a}-{arista.b}: gate_flag")
    if getattr(graph, "resources", None):
        problemas.append("canal resources")
    if getattr(graph, "subgraphs", None):
        problemas.append("subgraphs sin aplanar")
    return tuple(problemas)


def _alcance(graph) -> tuple[bool, int]:
    """BFS de (nodo, llaves), independiente del solver histórico."""
    inicio = next((n.id for n in graph.nodes.values() if n.start), None)
    meta = next((n.id for n in graph.nodes.values() if n.goal), None)
    if inicio is None or meta is None or inicio not in graph.nodes or meta not in graph.nodes:
        return False, 0

    llave_inicial = graph.nodes[inicio].key
    estado = (inicio, frozenset({llave_inicial}) if llave_inicial is not None else frozenset())
    cola = deque([estado])
    vistos = {estado}
    explorados = 0
    while cola:
        nodo_id, llaves = cola.popleft()
        if nodo_id == meta:
            return True, explorados
        explorados += 1
        for arista in graph.edges:
            if arista.a == nodo_id:
                vecino = arista.b
            elif arista.b == nodo_id:
                vecino = arista.a
            else:
                continue
            if vecino not in graph.nodes:
                continue
            if arista.door_id is not None and arista.door_id not in llaves:
                continue
            llave = graph.nodes[vecino].key
            nuevas = llaves | {llave} if llave is not None else llaves
            siguiente = (vecino, frozenset(nuevas))
            if siguiente not in vistos:
                vistos.add(siguiente)
                cola.append(siguiente)
    return False, explorados


def hechos(graph) -> dict:
    """Publica estructura y alcance; no decide qué resultado es aceptable."""
    alcanzable, explorados = _alcance(graph)
    return {"espacio": [{
        "inicios": sum(bool(n.start) for n in graph.nodes.values()),
        "metas": sum(bool(n.goal) for n in graph.nodes.values()),
        "alcanzable": alcanzable,
        "estados_explorados": explorados,
    }]}
