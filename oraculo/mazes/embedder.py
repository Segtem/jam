"""G3a — el EMBEDDER: de un grafo LIBRE (sin coordenadas) a posiciones de grilla + ruteo.

El realizador métrico (`floorplan.py`) necesita nodos con coordenadas de grilla donde las
aristas in-plane conecten celdas GRID-ADYACENTES (ahí carva vanos). Un grafo libre no trae
coordenadas, y sus aristas pueden exigir más que la adyacencia (hub de grado 6). Este módulo
resuelve ambas cosas (algoritmo del informe de embedding 2026-07-07):

1. **Posiciones**: init por anillos BFS desde el start + SIMULATED ANNEALING sobre la grilla
   entera (mover un nodo a celda vecina libre; costo = suma de largos Manhattan de aristas +
   área del bounding box; determinista por seed).
2. **Ruteo**: cada arista in-plane que no quedó entre celdas adyacentes se realiza como CAMINO
   ortogonal de celdas-PASILLO sintéticas (BFS por celdas libres, una celda no puede ser usada
   por dos rutas ni pisar un nodo). Las celdas de ruta se devuelven POR ARISTA: el realizador
   las convierte en nodos-hall que se CONTRAEN con el mecanismo de merge existente → el grafo
   contraído sigue siendo ISOMORFO al original (subdividir una arista con nodos libres preserva
   la misión; la mecánica door/gate de la arista viaja al ÚLTIMO tramo — un solo vano gateado).
3. **Pisos**: nodos con `floor` distinto se embeben por piso; una arista `stair` exige la MISMA
   (x, y) en ambos pisos (costo duro en el SA). Las `portal` no restringen nada (no-euclidianas).

El embedder es un GENERADOR: si tras `tries` reinicios no logra rutear todo, devuelve None
(honesto) — y aguas arriba el realizador + su iso-check siguen siendo el juez final.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
import math
import random

from oraculo.mazes.spacegraph import SpaceGraph

Cell = tuple[int, int, int]
Coord = tuple[int, int]


@dataclass
class Embedding:
    """El resultado: `positions` (nodo → celda, únicas), `routes` (índice de arista en
    `graph.edges` → celdas intermedias del camino, VACÍO si los extremos quedaron adyacentes;
    las celdas de ruta no se solapan entre sí ni con nodos), y el tamaño de la grilla usada."""
    positions: dict[str, Cell] = field(default_factory=dict)
    routes: dict[int, list[Cell]] = field(default_factory=dict)
    width: int = 0
    height: int = 0
    n_floors: int = 1


def embed(graph: SpaceGraph, *, seed: int = 0, tries: int = 8,
          sa_iterations: int = 4000) -> Embedding | None:
    """Grafo → embedding de grilla, o None si no se pudo rutear (el caller decide: otro seed,
    o descartar el candidato). Determinista dado `seed`. Garantías al devolver no-None:
    - posiciones únicas por piso; toda arista in-plane realizada por una CADENA de celdas
      grid-adyacentes (extremos + routes[i]); celdas de ruta de uso exclusivo;
    - aristas `stair`: misma (x,y) en pisos z y z' de sus extremos;
    - grilla compacta (recortada al bounding box + margen 1)."""
    if not graph.nodes:
        return Embedding(width=0, height=0, n_floors=0)
    if tries <= 0 or any(node.floor < 0 for node in graph.nodes.values()):
        return None

    master_rng = random.Random(seed)
    for _attempt in range(tries):
        sub_seed = master_rng.randrange(2**63)
        emb = _embed_once(graph, seed=sub_seed, sa_iterations=sa_iterations)
        if emb is not None and not check_embedding(graph, emb):
            return emb
    return None


def check_embedding(graph: SpaceGraph, emb: Embedding) -> list[str]:
    """El verificador MECÁNICO del embedding (lista de fallas, vacía = OK): unicidad de celdas,
    cadenas adyacentes por arista, exclusividad de rutas, stairs alineadas, bounds. Es la
    red de seguridad del SA (heurístico ⇒ no confiable ⇒ se verifica, como todo en Jam)."""
    failures: list[str] = []

    graph_ids = set(graph.nodes)
    pos_ids = set(emb.positions)
    for node_id in sorted(graph_ids - pos_ids):
        failures.append(f"falta posicion para nodo: {node_id}")
    for node_id in sorted(pos_ids - graph_ids):
        failures.append(f"posicion para nodo inexistente: {node_id}")

    if graph.nodes and (emb.width <= 0 or emb.height <= 0 or emb.n_floors <= 0):
        failures.append("bounds invalidos para embedding no vacio")

    seen_nodes: dict[Cell, str] = {}
    node_cells: set[Cell] = set()
    for node_id, cell in emb.positions.items():
        if node_id not in graph.nodes:
            continue
        if not _cell_in_bounds(cell, emb):
            failures.append(f"nodo fuera de bounds: {node_id} en {cell}")
        expected_floor = graph.nodes[node_id].floor
        if cell[2] != expected_floor:
            failures.append(f"piso incorrecto para {node_id}: {cell[2]} != {expected_floor}")
        other = seen_nodes.get(cell)
        if other is not None:
            failures.append(f"dos nodos misma celda: {other},{node_id} en {cell}")
        seen_nodes[cell] = node_id
        node_cells.add(cell)

    valid_route_indices = set(range(len(graph.edges)))
    for edge_idx in sorted(set(emb.routes) - valid_route_indices):
        failures.append(f"ruta para arista inexistente: {edge_idx}")

    used_route_cells: dict[Cell, int] = {}
    for edge_idx, route in sorted(emb.routes.items()):
        if edge_idx not in valid_route_indices:
            continue
        local_seen: set[Cell] = set()
        for cell in route:
            if not _cell_in_bounds(cell, emb):
                failures.append(f"ruta fuera de bounds: arista {edge_idx} celda {cell}")
            if cell in node_cells:
                failures.append(f"ruta pisa nodo: arista {edge_idx} celda {cell}")
            if cell in local_seen:
                failures.append(f"ruta repite celda: arista {edge_idx} celda {cell}")
            local_seen.add(cell)
            previous = used_route_cells.get(cell)
            if previous is not None:
                failures.append(
                    f"rutas solapadas: aristas {previous} y {edge_idx} celda {cell}"
                )
            used_route_cells[cell] = edge_idx

    for edge_idx, edge in enumerate(graph.edges):
        route = emb.routes.get(edge_idx, [])
        if edge.a not in emb.positions or edge.b not in emb.positions:
            failures.append(f"arista sin extremos posicionados: {edge_idx} {edge.a}-{edge.b}")
            continue
        if edge.kind == "cable":
            if route:
                failures.append(f"cable con ruta geometrica: arista {edge_idx}")
            continue
        a = emb.positions[edge.a]
        b = emb.positions[edge.b]

        if edge.kind == "portal":
            if route:
                failures.append(f"portal con ruta geometrica: arista {edge_idx}")
            continue

        if edge.kind == "stair":
            if route:
                failures.append(f"stair con ruta geometrica: arista {edge_idx}")
            if a[:2] != b[:2]:
                failures.append(f"stair desalineada: arista {edge_idx} {a} != {b}")
            continue

        if a[2] != b[2]:
            failures.append(f"arista in-plane cruza pisos: arista {edge_idx} {a} -> {b}")
            continue
        if any(cell[2] != a[2] for cell in route):
            failures.append(f"ruta cambia de piso: arista {edge_idx}")

        if not route:
            if _manhattan3(a, b) != 1:
                failures.append(f"arista sin ruta no adyacente: arista {edge_idx} {a} -> {b}")
            continue

        # El nodo representa una sala: las rutas entran por un puerto en su halo de 8 celdas.
        # El pasillo entre puertos conserva pasos ortogonales y celdas exclusivas.
        if not _port_adjacent(a, route[0]):
            failures.append(f"ruta no toca puerto inicial: arista {edge_idx} {a} -> {route[0]}")
        if not _port_adjacent(b, route[-1]):
            failures.append(f"ruta no toca puerto final: arista {edge_idx} {route[-1]} -> {b}")
        for left, right in zip(route, route[1:]):
            if _manhattan3(left, right) != 1:
                failures.append(
                    f"cadena no adyacente: arista {edge_idx} tramo {left} -> {right}"
                )
                break

    return failures


def _embed_once(graph: SpaceGraph, *, seed: int, sa_iterations: int) -> Embedding | None:
    rng = random.Random(seed)
    units = _stair_units(graph)
    if units is None:
        return None
    unit_for_node, unit_nodes = units

    side = max(3, 3 * math.ceil(math.sqrt(len(graph.nodes))))
    positions = _initial_positions(graph, unit_for_node, unit_nodes, side)
    if positions is None:
        return None

    _anneal(graph, positions, unit_nodes, side, rng, sa_iterations)
    # SEPARACION POR PARIDAD: el SA empaqueta (costo = largo+bbox) y puede dejar nodos sin
    # puertos ortogonales libres (visto en vivo: 'cocina' con 4 vecinos-nodo → irrutable).
    # Escalar x2 tras el SA pone todo nodo en coordenadas pares → sus 4 puertos (impares)
    # nunca son nodos, y toda arista de vecinos (dist 2) rutea por su punto medio libre.
    positions = {nid: (c[0] * 2, c[1] * 2, c[2]) for nid, c in positions.items()}
    routes = _route_edges(graph, positions, side * 2, side * 2)
    if routes is None:
        return None
    return _compact_embedding(graph, positions, routes)


def _stair_units(graph: SpaceGraph) -> tuple[dict[str, str], dict[str, tuple[str, ...]]] | None:
    parent = {node_id: node_id for node_id in graph.nodes}

    def find(node_id: str) -> str:
        while parent[node_id] != node_id:
            parent[node_id] = parent[parent[node_id]]
            node_id = parent[node_id]
        return node_id

    def union(a: str, b: str) -> None:
        ra = find(a)
        rb = find(b)
        if ra == rb:
            return
        if rb < ra:
            ra, rb = rb, ra
        parent[rb] = ra

    for edge in graph.edges:
        if edge.kind != "stair":
            continue
        if edge.a not in graph.nodes or edge.b not in graph.nodes:
            return None
        union(edge.a, edge.b)

    groups: dict[str, list[str]] = {}
    for node_id in sorted(graph.nodes):
        groups.setdefault(find(node_id), []).append(node_id)

    unit_for_node: dict[str, str] = {}
    unit_nodes: dict[str, tuple[str, ...]] = {}
    for root, nodes in groups.items():
        floors: set[int] = set()
        for node_id in nodes:
            floor = graph.nodes[node_id].floor
            if floor in floors:
                return None
            floors.add(floor)
            unit_for_node[node_id] = root
        unit_nodes[root] = tuple(nodes)

    return unit_for_node, unit_nodes


def _initial_positions(
    graph: SpaceGraph,
    unit_for_node: dict[str, str],
    unit_nodes: dict[str, tuple[str, ...]],
    side: int,
) -> dict[str, Cell] | None:
    center = (side // 2, side // 2)
    unit_order = _bfs_unit_order(graph, unit_for_node, unit_nodes)
    occupied: set[Cell] = set()
    unit_xy: dict[str, Coord] = {}

    for unit_id, depth in unit_order:
        xy = _nearest_free_coord(center, depth, side, unit_nodes[unit_id], graph, occupied)
        if xy is None:
            return None
        unit_xy[unit_id] = xy
        for node_id in unit_nodes[unit_id]:
            occupied.add((xy[0], xy[1], graph.nodes[node_id].floor))

    positions: dict[str, Cell] = {}
    for node_id in sorted(graph.nodes):
        xy = unit_xy[unit_for_node[node_id]]
        positions[node_id] = (xy[0], xy[1], graph.nodes[node_id].floor)
    return positions


def _bfs_unit_order(
    graph: SpaceGraph,
    unit_for_node: dict[str, str],
    unit_nodes: dict[str, tuple[str, ...]],
) -> list[tuple[str, int]]:
    unit_adj: dict[str, set[str]] = {unit_id: set() for unit_id in unit_nodes}
    degree: dict[str, int] = {node_id: 0 for node_id in graph.nodes}
    for edge in graph.edges:
        if edge.a not in graph.nodes or edge.b not in graph.nodes:
            continue
        if edge.kind == "cable":
            continue
        degree[edge.a] += 1
        degree[edge.b] += 1
        if edge.kind == "portal":
            continue
        ua = unit_for_node[edge.a]
        ub = unit_for_node[edge.b]
        if ua != ub:
            unit_adj[ua].add(ub)
            unit_adj[ub].add(ua)

    start = graph.start()
    if start is None:
        start = min(graph.nodes, key=lambda node_id: (-degree[node_id], node_id))
    start_unit = unit_for_node[start]

    order: list[tuple[str, int]] = []
    seen: set[str] = set()
    roots = [start_unit] + sorted(set(unit_nodes) - {start_unit})
    for root in roots:
        if root in seen:
            continue
        queue: deque[tuple[str, int]] = deque([(root, 0)])
        seen.add(root)
        while queue:
            unit_id, depth = queue.popleft()
            order.append((unit_id, depth))
            for next_unit in sorted(unit_adj[unit_id]):
                if next_unit in seen:
                    continue
                seen.add(next_unit)
                queue.append((next_unit, depth + 1))
    return order


def _nearest_free_coord(
    center: Coord,
    target_depth: int,
    side: int,
    nodes: tuple[str, ...],
    graph: SpaceGraph,
    occupied: set[Cell],
) -> Coord | None:
    coords = [(x, y) for y in range(side) for x in range(side)]
    coords.sort(key=lambda xy: (
        abs(_manhattan2(xy, center) - target_depth),
        _manhattan2(xy, center),
        xy[1],
        xy[0],
    ))
    for x, y in coords:
        cells = {(x, y, graph.nodes[node_id].floor) for node_id in nodes}
        if not cells & occupied:
            return (x, y)
    return None


def _anneal(
    graph: SpaceGraph,
    positions: dict[str, Cell],
    unit_nodes: dict[str, tuple[str, ...]],
    side: int,
    rng: random.Random,
    sa_iterations: int,
) -> None:
    if sa_iterations <= 0 or not unit_nodes:
        return

    units = sorted(unit_nodes)
    current_cost = _layout_cost(graph, positions)
    start_temp = max(1.0, len(graph.edges) * 0.75)
    end_temp = 0.02
    occupied = set(positions.values())

    for i in range(sa_iterations):
        unit_id = rng.choice(units)
        dx, dy = rng.choice(((1, 0), (-1, 0), (0, 1), (0, -1)))
        moving_nodes = unit_nodes[unit_id]
        old_cells = {positions[node_id] for node_id in moving_nodes}
        free_occupied = occupied - old_cells

        proposed: dict[str, Cell] = {}
        valid = True
        for node_id in moving_nodes:
            x, y, z = positions[node_id]
            nx = x + dx
            ny = y + dy
            cell = (nx, ny, z)
            if nx < 0 or ny < 0 or nx >= side or ny >= side or cell in free_occupied:
                valid = False
                break
            proposed[node_id] = cell
        if not valid:
            continue

        old = {node_id: positions[node_id] for node_id in moving_nodes}
        positions.update(proposed)
        next_cost = _layout_cost(graph, positions)
        temp = start_temp * ((end_temp / start_temp) ** (i / max(1, sa_iterations - 1)))
        delta = next_cost - current_cost
        if delta <= 0 or rng.random() < math.exp(-delta / temp):
            occupied = free_occupied | set(proposed.values())
            current_cost = next_cost
        else:
            positions.update(old)


def _layout_cost(graph: SpaceGraph, positions: dict[str, Cell]) -> float:
    total = 0.0
    for edge in graph.edges:
        if edge.kind in {"portal", "stair", "cable"}:
            continue
        if edge.a not in positions or edge.b not in positions:
            total += 10_000.0
            continue
        a = positions[edge.a]
        b = positions[edge.b]
        if a[2] != b[2]:
            total += 10_000.0
            continue
        total += _manhattan2(a[:2], b[:2])

    by_cluster_floor: dict[tuple[str, int], list[Coord]] = {}
    for nid, cell in positions.items():
        cluster_id = nid.split("__")[0] if "__" in nid else "__root__"
        by_cluster_floor.setdefault((cluster_id, cell[2]), []).append((cell[0], cell[1]))

    area = 0.0
    boxes_by_floor: dict[int, dict[str, tuple[int, int, int, int]]] = {}

    for (cluster_id, z), coords in by_cluster_floor.items():
        xs = [xy[0] for xy in coords]
        ys = [xy[1] for xy in coords]
        min_x, max_x = min(xs), max(xs)
        min_y, max_y = min(ys), max(ys)
        area += (max_x - min_x + 1) * (max_y - min_y + 1)
        boxes_by_floor.setdefault(z, {})[cluster_id] = (min_x, min_y, max_x, max_y)

    overlap_penalty = 0.0
    for z, boxes in boxes_by_floor.items():
        cids = list(boxes.keys())
        for i in range(len(cids)):
            for j in range(i + 1, len(cids)):
                b1 = boxes[cids[i]]
                b2 = boxes[cids[j]]
                ox = max(0, min(b1[2], b2[2]) - max(b1[0], b2[0]))
                oy = max(0, min(b1[3], b2[3]) - max(b1[1], b2[1]))
                overlap_penalty += ox * oy

    # CRUCES: el ruteo cell-disjoint exige un arreglo cuasi-planar — sin esta penalidad el SA
    # empaqueta arreglos no-planares irruteables (informe de embedding: "penalizar fuertemente
    # cruces"; visto en vivo con la casa del LLM: 0/10 ruteos sin esto)
    return total + 0.15 * area + 50.0 * overlap_penalty + 200.0 * _crossings(graph, positions)


def _crossings(graph: SpaceGraph, positions: dict[str, Cell]) -> int:
    """Cruces entre los SEGMENTOS RECTOS de las aristas in-plane (proxy barato de planaridad
    del arreglo — el ruteo real es ortogonal, pero un arreglo con muchos cruces rectos es
    irruteable de forma disjunta)."""
    segs = []
    for e in graph.edges:
        if e.kind in {"portal", "stair", "cable"}:
            continue
        a = positions.get(e.a)
        b = positions.get(e.b)
        if a is None or b is None or a[2] != b[2]:
            continue
        segs.append((a[:2], b[:2], e.a, e.b))
    n = 0
    for i in range(len(segs)):
        for j in range(i + 1, len(segs)):
            (a1, b1, u1, v1), (a2, b2, u2, v2) = segs[i], segs[j]
            if {u1, v1} & {u2, v2}:
                continue                              # comparten nodo: no es cruce
            if _segments_cross(a1, b1, a2, b2):
                n += 1
    return n


def _segments_cross(p1: Coord, p2: Coord, p3: Coord, p4: Coord) -> bool:
    def orient(a: Coord, b: Coord, c: Coord) -> int:
        v = (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])
        return (v > 0) - (v < 0)

    o1, o2 = orient(p1, p2, p3), orient(p1, p2, p4)
    o3, o4 = orient(p3, p4, p1), orient(p3, p4, p2)
    if o1 != o2 and o3 != o4:
        return True
    def on(a: Coord, b: Coord, c: Coord) -> bool:
        return (orient(a, b, c) == 0 and min(a[0], b[0]) <= c[0] <= max(a[0], b[0])
                and min(a[1], b[1]) <= c[1] <= max(a[1], b[1]))
    return on(p1, p2, p3) or on(p1, p2, p4) or on(p3, p4, p1) or on(p3, p4, p2)


def _route_edges(
    graph: SpaceGraph,
    positions: dict[str, Cell],
    width: int,
    height: int,
) -> dict[int, list[Cell]] | None:
    routes: dict[int, list[Cell]] = {idx: [] for idx in range(len(graph.edges))}
    reserved = set(positions.values())
    order: list[tuple[int, int]] = []

    for edge_idx, edge in enumerate(graph.edges):
        if edge.kind in {"portal", "stair", "cable"}:
            continue
        if edge.a not in positions or edge.b not in positions:
            return None
        a = positions[edge.a]
        b = positions[edge.b]
        if a[2] != b[2]:
            return None
        order.append((_manhattan2(a[:2], b[:2]), edge_idx))

    for _length, edge_idx in sorted(order):
        edge = graph.edges[edge_idx]
        a = positions[edge.a]
        b = positions[edge.b]
        if _manhattan2(a[:2], b[:2]) == 1:
            continue
        route = _bfs_route(a, b, reserved, width, height)
        if route is None:
            return None
        routes[edge_idx] = route
        reserved.update(route)

    return routes


def _bfs_route(
    start: Cell,
    goal: Cell,
    blocked: set[Cell],
    width: int,
    height: int,
) -> list[Cell] | None:
    z = start[2]
    queue: deque[Cell] = deque()
    prev: dict[Cell, Cell | None] = {}
    for cell in _port_cells(start, width, height):
        if cell[2] != z or cell in blocked:
            continue
        queue.append(cell)
        prev[cell] = None

    while queue:
        cell = queue.popleft()
        if _port_adjacent(goal, cell):
            return _reconstruct_route(cell, prev)
        for nxt in _neighbors(cell, width, height):
            if nxt[2] != z or nxt in blocked or nxt in prev:
                continue
            prev[nxt] = cell
            queue.append(nxt)
    return None


def _reconstruct_route(last: Cell, prev: dict[Cell, Cell | None]) -> list[Cell]:
    out = []
    cell: Cell | None = last
    while cell is not None:
        out.append(cell)
        cell = prev[cell]
    out.reverse()
    return out


def _compact_embedding(
    graph: SpaceGraph,
    positions: dict[str, Cell],
    routes: dict[int, list[Cell]],
) -> Embedding:
    used = list(positions.values())
    for route in routes.values():
        used.extend(route)

    min_x = min(cell[0] for cell in used)
    max_x = max(cell[0] for cell in used)
    min_y = min(cell[1] for cell in used)
    max_y = max(cell[1] for cell in used)
    shift_x = 1 - min_x
    shift_y = 1 - min_y

    def shift(cell: Cell) -> Cell:
        return (cell[0] + shift_x, cell[1] + shift_y, cell[2])

    shifted_positions = {node_id: shift(cell) for node_id, cell in positions.items()}
    shifted_routes = {
        edge_idx: [shift(cell) for cell in route]
        for edge_idx, route in routes.items()
    }
    max_floor = max((node.floor for node in graph.nodes.values()), default=-1)
    return Embedding(
        positions=shifted_positions,
        routes=shifted_routes,
        width=max_x - min_x + 3,
        height=max_y - min_y + 3,
        n_floors=max_floor + 1,
    )


def _neighbors(cell: Cell, width: int, height: int) -> list[Cell]:
    x, y, z = cell
    out: list[Cell] = []
    for dx, dy in ((1, 0), (0, 1), (-1, 0), (0, -1)):
        nx = x + dx
        ny = y + dy
        if 0 <= nx < width and 0 <= ny < height:
            out.append((nx, ny, z))
    return out


def _port_cells(cell: Cell, width: int, height: int) -> list[Cell]:
    # V1: puertos ORTOGONALES (coherente con _port_adjacent) — el puente x2 exige cadenas
    # 4-conectadas de punta a punta.
    x, y, z = cell
    out: list[Cell] = []
    for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
        nx, ny = x + dx, y + dy
        if 0 <= nx < width and 0 <= ny < height:
            out.append((nx, ny, z))
    return out


def _port_adjacent(node: Cell, cell: Cell) -> bool:
    # V1: puertos ESTRICTAMENTE ortogonales (4-conn). El puente grafo→maze (spacegraph_realize,
    # escala x2) exige cadenas 4-conectadas para su prueba de no-adyacencias-espurias; un puerto
    # diagonal la romperia. Consecuencia: grado in-plane <= 4 por nodo (gateado en
    # realizable_static); los hubs multi-celda llegan en V2.
    return (
        node[2] == cell[2]
        and abs(node[0] - cell[0]) + abs(node[1] - cell[1]) == 1
    )


def _cell_in_bounds(cell: Cell, emb: Embedding) -> bool:
    x, y, z = cell
    return 0 <= x < emb.width and 0 <= y < emb.height and 0 <= z < emb.n_floors


def _manhattan2(a: Coord, b: Coord) -> int:
    return abs(a[0] - b[0]) + abs(a[1] - b[1])


def _manhattan3(a: Cell, b: Cell) -> int:
    return abs(a[0] - b[0]) + abs(a[1] - b[1]) + abs(a[2] - b[2])
