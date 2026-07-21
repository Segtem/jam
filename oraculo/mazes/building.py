"""Transpilador JamSpace -> planta compacta de edificio.

El contrato importante no es copiar la geometria del laberinto fuente sino preservar su grafo:
cada celda abierta fuente se vuelve una region/cuarto, las aristas transitables se vuelven vanos,
portales o conectores, y las paredes sobrantes solo existen para separar regiones sin arista. La
particion absorbe tambien los muros del rectangulo fuente, por eso no queda "espacio muerto" del
maze original: todo pertenece a algun cuarto de la planta.
"""
from __future__ import annotations

from collections import deque
from dataclasses import dataclass, replace
from itertools import combinations

from src.mazes.maze3d import GOAL, OPEN, PLAYER, WALL, Maze3D, solve_3d

Cell = tuple[int, int, int]

_DIRS = ((1, 0), (-1, 0), (0, 1), (0, -1))


@dataclass
class BuildingPlan:
    fine: Maze3D
    scale: int
    rooms: dict[Cell, list[Cell]]
    doorways: dict[tuple[Cell, Cell], list[Cell]]
    merged: dict[Cell, Cell]


def transpile(source: Maze3D, *, scale: int = 4, merge: set[Cell] = frozenset()) -> BuildingPlan:
    """Re-embebe el grafo de `source` en una planta compacta.

    Usamos una pared determinista de una celda fina de espesor: en cada borde entre dos celdas
    gruesas asignadas a regiones distintas, la primera fila/columna fina de la segunda celda queda
    como muro. Los vanos se abren solo sobre aristas del grafo contraido. El borde exterior tambien
    queda cerrado para que el edificio tenga envolvente solida.
    """
    if scale < 3:
        raise ValueError("scale debe ser >= 3 para tener interior, muro y vano distinguibles")

    merged = _merge_map(source, merge)
    nodes, _edges, edge_info = _contracted_graph(source, merged)
    regions = _partition_by_floor(source, merged)
    width, height = source.width, source.height
    fine_w, fine_h = width * scale, height * scale

    floors: list[list[list[str]]] = []
    for z in range(source.n_floors):
        grid = [[OPEN for _ in range(fine_w)] for _ in range(fine_h)]
        for fy in range(fine_h):
            for fx in range(fine_w):
                coarse = (fx // scale, fy // scale, z)
                if coarse not in regions or _is_exterior(fx, fy, fine_w, fine_h) or _is_region_wall(regions, fx, fy, z, scale):
                    grid[fy][fx] = WALL
        floors.append(grid)

    rooms: dict[Cell, set[Cell]] = {rep: set() for rep in nodes}
    doorways: dict[tuple[Cell, Cell], set[Cell]] = {}
    switch_reps = {merged[c] for c in source.switches if c in merged}
    switch_panels = {rep: _center(rep, scale) for rep in switch_reps}

    for z in range(source.n_floors):
        for fy in range(fine_h):
            for fx in range(fine_w):
                if floors[z][fy][fx] == WALL:
                    continue
                rep = regions[(fx // scale, fy // scale, z)]
                if rep in switch_panels and (fx, fy, z) != switch_panels[rep]:
                    floors[z][fy][fx] = WALL
                    continue
                rooms[rep].add((fx, fy, z))

    # Los paneles de switch sobreviven aunque su celda haya caido sobre una pared de particion.
    for rep, panel in switch_panels.items():
        px, py, pz = panel
        floors[pz][py][px] = OPEN
        rooms[rep] = {panel}

    for pair, (a, b) in sorted(edge_info.items()):
        if a[2] != b[2] or abs(a[0] - b[0]) + abs(a[1] - b[1]) != 1:
            continue
        cells = _doorway_cells_for_edge(a, b, merged, switch_panels, scale)
        for fx, fy, fz in cells:
            if 0 <= fz < source.n_floors and 0 <= fy < fine_h and 0 <= fx < fine_w:
                floors[fz][fy][fx] = OPEN
                rooms[pair[0]].discard((fx, fy, fz))
                rooms[pair[1]].discard((fx, fy, fz))
                doorways.setdefault(pair, set()).add((fx, fy, fz))

    room_lists = {rep: sorted(cells) for rep, cells in rooms.items()}
    doorway_lists = {pair: sorted(cells) for pair, cells in doorways.items()}

    out_floors = [["".join(row) for row in grid] for grid in floors]

    doors, keys, hazards, gates = {}, {}, {}, {}
    switches: dict[Cell, str] = {}
    for src, key_id in source.doors.items():
        doors.update({cell: key_id for cell in room_lists.get(merged.get(src, src), [])})
    for src, key_id in source.keys.items():
        keys.update({cell: key_id for cell in room_lists.get(merged.get(src, src), [])})
    for src, flag in source.hazards.items():
        hazards.update({cell: flag for cell in room_lists.get(merged.get(src, src), [])})
    for src, flag in source.gates.items():
        gates.update({cell: flag for cell in room_lists.get(merged.get(src, src), [])})
    for src, flag in source.switches.items():
        rep = merged.get(src, src)
        if room_lists.get(rep):
            switches[room_lists[rep][0]] = flag

    start = source.find(PLAYER)
    goal = source.find(GOAL)
    if start is not None:
        _place_marker(out_floors, room_lists, merged[start], start, scale, PLAYER)
    if goal is not None:
        _place_marker(out_floors, room_lists, merged[goal], goal, scale, GOAL)

    portals = [
        (_representative_cell(room_lists, merged[s], s, scale), _representative_cell(room_lists, merged[d], d, scale))
        for s, d in source.portals
        if s in merged and d in merged and room_lists.get(merged[s]) and room_lists.get(merged[d])
    ]
    connectors = {
        _representative_cell(room_lists, merged[c], c, scale)
        for c in source.connectors
        if c in merged and (c[0], c[1], c[2] + 1) in merged and room_lists.get(merged[c])
    }
    ladders = {
        _representative_cell(room_lists, merged[c], c, scale)
        for c in source.ladders
        if c in merged and (c[0], c[1], c[2] + 1) in merged and room_lists.get(merged[c])
    }

    fine = replace(
        Maze3D.from_layers(out_floors),
        doors=doors,
        keys=keys,
        hazards=hazards,
        gates=gates,
        switches=switches,
        portals=portals,
        connectors=connectors,
        ladders=ladders,
    )
    return BuildingPlan(
        fine=fine,
        scale=scale,
        rooms=room_lists,
        doorways=doorway_lists,
        merged=merged,
    )


def building_graph(plan: BuildingPlan) -> tuple[set[Cell], set[tuple[Cell, Cell]]]:
    """Deriva el grafo desde la geometria fina, no desde las aristas intencionadas.

    Las celdas de cuarto etiquetan los nodos. Las celdas abiertas que no pertenecen a cuarto son
    componentes de vano; si una componente toca dos o mas cuartos, induce esas aristas. Esto sigue
    cazando agujeros accidentales porque cualquier apertura no etiquetada tambien entra en esta
    derivacion geometrica.
    """
    nodes = set(plan.rooms)
    room_by_cell = _room_by_cell(plan)
    edges: set[tuple[Cell, Cell]] = set()
    fine = plan.fine

    for cell, room in room_by_cell.items():
        x, y, z = cell
        for dx, dy in _DIRS:
            other = (x + dx, y + dy, z)
            other_room = room_by_cell.get(other)
            if other_room is not None and other_room != room:
                edges.add(_pair(room, other_room))

    seen: set[Cell] = set()
    for cell in sorted(fine.open_cells() - set(room_by_cell)):
        if cell in seen:
            continue
        comp, adjacent_rooms = _open_component_with_rooms(fine, room_by_cell, cell)
        seen.update(comp)
        for a, b in combinations(sorted(adjacent_rooms), 2):
            edges.add(_pair(a, b))

    for c in fine.connectors | fine.ladders:
        a = room_by_cell.get(c)
        top = (c[0], c[1], c[2] + 1)
        b = room_by_cell.get(top)
        if a is not None and b is not None and a != b:
            edges.add(_pair(a, b))
    for src, dst in fine.portals:
        a = room_by_cell.get(src)
        b = room_by_cell.get(dst)
        if a is not None and b is not None and a != b:
            edges.add(_pair(a, b))

    return nodes, edges


def check_building(source: Maze3D, plan: BuildingPlan, merge: set[Cell] = frozenset()) -> list[str]:
    failures: list[str] = []
    expected_merged = _merge_map(source, merge)
    expected_nodes, expected_edges, _ = _contracted_graph(source, expected_merged)
    got_nodes, got_edges = building_graph(plan)

    if expected_merged != plan.merged:
        failures.append("merged no coincide con la contraccion esperada")
    if got_nodes != expected_nodes:
        failures.append(f"nodos distintos: faltan={sorted(expected_nodes - got_nodes)} sobran={sorted(got_nodes - expected_nodes)}")
    if got_edges != expected_edges:
        failures.append(f"aristas distintas: faltan={sorted(expected_edges - got_edges)} sobran={sorted(got_edges - expected_edges)}")

    failures.extend(_geometry_failures(plan))
    failures.extend(_mechanic_failures(source, plan, expected_merged))

    src_solvable = solve_3d(source)["solvable"]
    fine_solvable = solve_3d(plan.fine)["solvable"]
    if fine_solvable != src_solvable:
        failures.append(f"winnability distinta: source={src_solvable} fine={fine_solvable}")
    return failures


def _pair(a: Cell, b: Cell) -> tuple[Cell, Cell]:
    return (a, b) if a <= b else (b, a)


def _mechanical_cells(source: Maze3D) -> set[Cell]:
    cells = set(source.doors) | set(source.keys) | set(source.gates) | set(source.switches) | set(source.hazards)
    for marker in (source.find(PLAYER), source.find(GOAL)):
        if marker is not None:
            cells.add(marker)
    for src, dst in source.portals:
        cells.add(src)
        cells.add(dst)
    for x, y, z in source.connectors | source.ladders:
        cells.add((x, y, z))
        cells.add((x, y, z + 1))
    return cells


def _merge_map(source: Maze3D, merge: set[Cell]) -> dict[Cell, Cell]:
    open_cells = source.open_cells()
    mergeable = (set(merge) & open_cells) - _mechanical_cells(source)
    out = {cell: cell for cell in open_cells}
    seen: set[Cell] = set()
    for start in sorted(mergeable):
        if start in seen:
            continue
        stack = [start]
        comp: set[Cell] = set()
        seen.add(start)
        while stack:
            cell = stack.pop()
            comp.add(cell)
            x, y, z = cell
            for dx, dy in _DIRS:
                nxt = (x + dx, y + dy, z)
                if nxt in mergeable and nxt not in seen:
                    seen.add(nxt)
                    stack.append(nxt)
        rep = min(comp)
        for cell in comp:
            out[cell] = rep
    return out


def _source_edges(source: Maze3D) -> tuple[set[tuple[Cell, Cell]], dict[tuple[Cell, Cell], tuple[Cell, Cell]]]:
    open_cells = source.open_cells()
    edges: set[tuple[Cell, Cell]] = set()
    info: dict[tuple[Cell, Cell], tuple[Cell, Cell]] = {}
    for x, y, z in sorted(open_cells):
        for dx, dy in ((1, 0), (0, 1)):
            nxt = (x + dx, y + dy, z)
            if nxt in open_cells:
                pair = _pair((x, y, z), nxt)
                edges.add(pair)
                info[pair] = ((x, y, z), nxt)
        for verticals in (source.connectors, source.ladders):
            if (x, y, z) in verticals:
                nxt = (x, y, z + 1)
                if nxt in open_cells:
                    pair = _pair((x, y, z), nxt)
                    edges.add(pair)
                    info.setdefault(pair, ((x, y, z), nxt))
    for src, dst in source.portals:
        if src in open_cells and dst in open_cells:
            pair = _pair(src, dst)
            edges.add(pair)
            info.setdefault(pair, (src, dst))
    return edges, info


def _contracted_graph(
    source: Maze3D, merged: dict[Cell, Cell]
) -> tuple[set[Cell], set[tuple[Cell, Cell]], dict[tuple[Cell, Cell], tuple[Cell, Cell]]]:
    nodes = set(merged.values())
    source_edges, source_info = _source_edges(source)
    edges: set[tuple[Cell, Cell]] = set()
    info: dict[tuple[Cell, Cell], tuple[Cell, Cell]] = {}
    for a, b in sorted(source_edges):
        ra, rb = merged[a], merged[b]
        if ra == rb:
            continue
        pair = _pair(ra, rb)
        edges.add(pair)
        info.setdefault(pair, source_info[_pair(a, b)])
    return nodes, edges, info


def _partition_by_floor(source: Maze3D, merged: dict[Cell, Cell]) -> dict[Cell, Cell]:
    regions: dict[Cell, Cell] = {}
    by_floor: dict[int, list[tuple[int, int, Cell]]] = {}
    for x, y, z in sorted(source.open_cells()):
        by_floor.setdefault(z, []).append((x, y, merged[(x, y, z)]))

    for z in range(source.n_floors):
        seeds = by_floor.get(z, [])
        if not seeds:
            continue
        for y in range(source.height):
            for x in range(source.width):
                _dist, rep = min((abs(x - sx) + abs(y - sy), rep) for sx, sy, rep in seeds)
                regions[(x, y, z)] = rep
    return regions


def _is_exterior(fx: int, fy: int, width: int, height: int) -> bool:
    return fx == 0 or fy == 0 or fx == width - 1 or fy == height - 1


def _is_region_wall(regions: dict[Cell, Cell], fx: int, fy: int, z: int, scale: int) -> bool:
    x, y = fx // scale, fy // scale
    if fx % scale == 0 and x > 0 and regions.get((x - 1, y, z)) != regions.get((x, y, z)):
        return True
    if fy % scale == 0 and y > 0 and regions.get((x, y - 1, z)) != regions.get((x, y, z)):
        return True
    return False


def _center(cell: Cell, scale: int) -> Cell:
    x, y, z = cell
    return (x * scale + scale // 2, y * scale + scale // 2, z)


def _door_offsets(scale: int) -> tuple[int, ...]:
    mid = scale // 2
    return (mid - 1, mid)


def _doorway_cells_for_edge(
    a: Cell,
    b: Cell,
    merged: dict[Cell, Cell],
    switch_panels: dict[Cell, Cell],
    scale: int,
) -> list[Cell]:
    ra, rb = merged[a], merged[b]
    if ra in switch_panels:
        return _switch_access_cells(a, b, switch_panels[ra], rb in switch_panels, scale)
    if rb in switch_panels:
        return _switch_access_cells(b, a, switch_panels[rb], ra in switch_panels, scale)

    ax, ay, az = a
    bx, by, _bz = b
    out: list[Cell] = []
    if bx == ax + 1:
        wall_x = bx * scale
        out.extend((wall_x, ay * scale + off, az) for off in _door_offsets(scale))
    elif bx == ax - 1:
        wall_x = ax * scale
        out.extend((wall_x, ay * scale + off, az) for off in _door_offsets(scale))
    elif by == ay + 1:
        wall_y = by * scale
        out.extend((ax * scale + off, wall_y, az) for off in _door_offsets(scale))
    elif by == ay - 1:
        wall_y = ay * scale
        out.extend((ax * scale + off, wall_y, az) for off in _door_offsets(scale))
    return out


def _switch_access_cells(switch_cell: Cell, other_cell: Cell, panel: Cell, other_is_switch: bool, scale: int) -> list[Cell]:
    sx, sy, sz = switch_cell
    ox, oy, _oz = other_cell
    px, py, pz = panel
    dx, dy = ox - sx, oy - sy
    if dx:
        if dx > 0:
            end = ox * scale + (scale // 2 - 1 if other_is_switch else 0)
            return [(x, py, pz) for x in range(px + 1, end + 1)]
        end = sx * scale if not other_is_switch else ox * scale + scale // 2 + 1
        return [(x, py, pz) for x in range(px - 1, end - 1, -1)]
    if dy > 0:
        end = oy * scale + (scale // 2 - 1 if other_is_switch else 0)
        return [(px, y, pz) for y in range(py + 1, end + 1)]
    end = sy * scale if not other_is_switch else oy * scale + scale // 2 + 1
    return [(px, y, pz) for y in range(py - 1, end - 1, -1)]


def _place_marker(
    floors: list[list[str]], rooms: dict[Cell, list[Cell]], rep: Cell, source_cell: Cell, scale: int, marker: str
) -> None:
    x, y, z = _representative_cell(rooms, rep, source_cell, scale)
    row = list(floors[z][y])
    row[x] = marker
    floors[z][y] = "".join(row)


def _representative_cell(rooms: dict[Cell, list[Cell]], rep: Cell, source_cell: Cell, scale: int) -> Cell:
    preferred = _center(source_cell, scale)
    cells = rooms.get(rep, [])
    if preferred in cells:
        return preferred
    if not cells:
        return preferred
    return cells[len(cells) // 2]


def _room_by_cell(plan: BuildingPlan) -> dict[Cell, Cell]:
    out: dict[Cell, Cell] = {}
    for rep, cells in plan.rooms.items():
        for cell in cells:
            out[cell] = rep
    return out


def _open_component_with_rooms(
    fine: Maze3D, room_by_cell: dict[Cell, Cell], start: Cell
) -> tuple[set[Cell], set[Cell]]:
    comp: set[Cell] = set()
    rooms: set[Cell] = set()
    queue: deque[Cell] = deque([start])
    comp.add(start)
    while queue:
        x, y, z = queue.popleft()
        for dx, dy in _DIRS:
            nxt = (x + dx, y + dy, z)
            room = room_by_cell.get(nxt)
            if room is not None:
                rooms.add(room)
            elif fine.is_open(*nxt) and nxt not in comp:
                comp.add(nxt)
                queue.append(nxt)
    return comp, rooms


def _geometry_failures(plan: BuildingPlan) -> list[str]:
    failures: list[str] = []
    fine = plan.fine
    room_cells = set(_room_by_cell(plan))
    doorway_cells = {cell for cells in plan.doorways.values() for cell in cells}
    open_cells = fine.open_cells()

    orphan = sorted(open_cells - room_cells - doorway_cells)
    if orphan:
        failures.append(f"celdas abiertas huerfanas: {orphan[:8]}")
    closed_rooms = sorted(cell for cell in room_cells if not fine.is_open(*cell))
    if closed_rooms:
        failures.append(f"celdas de cuarto cerradas: {closed_rooms[:8]}")
    closed_doorways = sorted(cell for cell in doorway_cells if not fine.is_open(*cell))
    if closed_doorways:
        failures.append(f"celdas de vano cerradas: {closed_doorways[:8]}")

    for cell in fine.switches:
        rooms = [rep for rep, cells in plan.rooms.items() if cell in cells]
        if not rooms:
            failures.append(f"switch fuera de cuarto: {cell}")
        elif len(plan.rooms[rooms[0]]) != 1:
            failures.append(f"switch room no es 1 celda: {rooms[0]}")
    return failures


def _mechanic_failures(source: Maze3D, plan: BuildingPlan, merged: dict[Cell, Cell]) -> list[str]:
    failures: list[str] = []
    fine = plan.fine

    for name, src_map, fine_map in (
        ("door", source.doors, fine.doors),
        ("key", source.keys, fine.keys),
        ("gate", source.gates, fine.gates),
        ("hazard", source.hazards, fine.hazards),
    ):
        for src, value in src_map.items():
            room = plan.rooms.get(merged.get(src, src), [])
            if not room:
                failures.append(f"{name} sin cuarto: {src}")
            elif any(fine_map.get(cell) != value for cell in room):
                failures.append(f"{name} no cubre el cuarto de {src}")

    for src, flag in source.switches.items():
        room = plan.rooms.get(merged.get(src, src), [])
        mapped = [cell for cell in room if fine.switches.get(cell) == flag]
        if len(room) != 1 or len(mapped) != 1:
            failures.append(f"switch no mapeado como panel 1x1: {src}")

    for marker in (PLAYER, GOAL):
        src = source.find(marker)
        dst = fine.find(marker)
        if src is not None and (dst is None or dst not in plan.rooms.get(merged.get(src, src), [])):
            failures.append(f"{marker} no esta en su cuarto")

    for src, dst in source.portals:
        rs, rd = merged.get(src, src), merged.get(dst, dst)
        if not any(a in plan.rooms.get(rs, []) and b in plan.rooms.get(rd, []) for a, b in fine.portals):
            failures.append(f"portal no preservado: {src}->{dst}")

    for verticals, fine_verticals, label in (
        (source.connectors, fine.connectors, "connector"),
        (source.ladders, fine.ladders, "ladder"),
    ):
        for src in verticals:
            top = (src[0], src[1], src[2] + 1)
            if top not in merged:
                continue
            expected_room = set(plan.rooms.get(merged.get(src, src), []))
            expected_top_room = set(plan.rooms.get(merged[top], []))
            ok = any(c in expected_room and (c[0], c[1], c[2] + 1) in expected_top_room for c in fine_verticals)
            if not ok:
                failures.append(f"{label} no preservado: {src}")
    return failures
