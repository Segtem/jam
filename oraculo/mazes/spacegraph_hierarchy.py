"""Jerarquia de SpaceGraph: aplanado de sub-grafos con puertos.

V1 no introduce un embedder nuevo: un grafo jerarquico se convierte a un grafo plano y el resto
del pipeline (`realizable_static`, `solve_graph`, `embed`) opera exactamente como antes.
"""

from __future__ import annotations

from dataclasses import replace

from src.mazes.spacegraph import GraphEdge, SpaceGraph, Subgraph


def flatten_hierarchy(graph: SpaceGraph) -> SpaceGraph:
    """Inlinea los nodos `@expand` y reconecta sus aristas a los puertos del sub-grafo.

    Sin nodos expandidos devuelve el mismo `graph` (identidad retro-compatible). Si un nodo tiene
    mas/menos aristas externas que puertos, la asignacion es round-robin: la arista i cuelga de
    `ports[i % len(ports)]`, preservando `kind`, `door_id` y `gate_flag`.
    """
    expanded = {node_id: node.expand for node_id, node in graph.nodes.items() if node.expand}
    if not expanded:
        return graph

    flat_nodes = {
        node_id: node
        for node_id, node in graph.nodes.items()
        if node_id not in expanded
    }
    flat_edges: list[GraphEdge] = []
    occupied = set(flat_nodes)
    instance_ports: dict[str, list[str]] = {}

    for parent_id, subgraph_id in expanded.items():
        if subgraph_id is None:
            continue
        subgraph = graph.subgraphs.get(subgraph_id)
        if subgraph is None:
            raise ValueError(f"@expand refiere subgraph no declarado: {subgraph_id!r}")

        _validate_subgraph_ports(subgraph)
        prefix = _choose_prefix(subgraph_id, parent_id, subgraph, occupied)
        mapping = {node_id: f"{prefix}__{node_id}" for node_id in subgraph.nodes}
        occupied.update(mapping.values())
        ports = [mapping[port_id] for port_id in subgraph.ports]
        instance_ports[parent_id] = ports

        parent = graph.nodes[parent_id]
        anchor_id = subgraph.ports[0] if subgraph.ports else next(iter(subgraph.nodes), None)
        for node_id, node in subgraph.nodes.items():
            new_node = replace(
                node,
                id=mapping[node_id],
                start=parent.start if node_id == anchor_id else False,
                goal=parent.goal if node_id == anchor_id else False,
                expand=None,
            )
            flat_nodes[new_node.id] = new_node

        for edge in subgraph.edges:
            flat_edges.append(replace(edge, a=mapping[edge.a], b=mapping[edge.b]))

    incident_order: dict[str, list[int]] = {node_id: [] for node_id in expanded}
    for edge_index, edge in enumerate(graph.edges):
        if edge.a in incident_order:
            incident_order[edge.a].append(edge_index)
        if edge.b in incident_order:
            incident_order[edge.b].append(edge_index)
    incident_pos = {
        (node_id, edge_index): pos
        for node_id, edge_indices in incident_order.items()
        for pos, edge_index in enumerate(edge_indices)
    }

    for edge_index, edge in enumerate(graph.edges):
        a = _mapped_endpoint(edge.a, edge_index, instance_ports, incident_pos)
        b = _mapped_endpoint(edge.b, edge_index, instance_ports, incident_pos)
        flat_edges.append(replace(edge, a=a, b=b))

    return SpaceGraph(
        nodes=flat_nodes,
        edges=flat_edges,
        space=graph.space,
        seed=graph.seed,
        resources=dict(graph.resources),
        subgraphs={},
    )


def _validate_subgraph_ports(subgraph: Subgraph) -> None:
    for port_id in subgraph.ports:
        if port_id not in subgraph.nodes:
            raise ValueError(f"subgraph {subgraph.id!r} declara port inexistente: {port_id!r}")
    for edge in subgraph.edges:
        if edge.a not in subgraph.nodes or edge.b not in subgraph.nodes:
            raise ValueError(f"subgraph {subgraph.id!r} tiene arista con referencia rota")


def _choose_prefix(subgraph_id: str, parent_id: str, subgraph: Subgraph,
                   occupied: set[str]) -> str:
    for prefix in (subgraph_id, f"{parent_id}__{subgraph_id}"):
        if _prefix_is_free(prefix, subgraph, occupied):
            return prefix
    i = 2
    while True:
        prefix = f"{parent_id}__{subgraph_id}_{i}"
        if _prefix_is_free(prefix, subgraph, occupied):
            return prefix
        i += 1


def _prefix_is_free(prefix: str, subgraph: Subgraph, occupied: set[str]) -> bool:
    return all(f"{prefix}__{node_id}" not in occupied for node_id in subgraph.nodes)


def _mapped_endpoint(node_id: str, edge_index: int, instance_ports: dict[str, list[str]],
                     incident_pos: dict[tuple[str, int], int]) -> str:
    ports = instance_ports.get(node_id)
    if ports is None:
        return node_id
    if not ports:
        raise ValueError(f"nodo expandido {node_id!r} tiene aristas externas pero su subgraph no tiene ports")
    pos = incident_pos[(node_id, edge_index)]
    return ports[pos % len(ports)]
