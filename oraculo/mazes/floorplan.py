"""Transpilador V2 — plano MÉTRICO rectangular: el edificio con tamaños REALES.

La V1 (`building.py`) probó el concepto en la grilla del visor (celdas de 2 m → muros de 2 m de
espesor, cuartos-blob). La V2 cambia la representación: el edificio es un PLANO VECTORIAL en
metros — cuartos RECTANGULARES sobre una malla de columnas/filas de ancho variable (el mismo
esqueleto de la grilla fuente, con cada columna/fila dimensionada por los TIPOS de cuarto que
contiene), muros de 0.20 m, puertas de 1.00 m. El mismo NORTE de la V1: sólo el GRAFO es sagrado
(nodos + aristas + mecánicas); `check_floorplan` deriva el grafo DE LA GEOMETRÍA (las puertas
reales sobre fronteras reales) y exige isomorfismo exacto con el fuente contraído. La winnability
se HEREDA por el isomorfismo (las mecánicas son propiedades de nodo, preservadas 1:1 — el BFS
del fuente es la prueba); la transitabilidad INTERNA de cada cuarto (que los props no tapien una
puerta) se verifica aparte con `room_passable` (raster fino por cuarto).

Reusa de `building.py`: `_mechanical_cells`, `_merge_map`, `_contracted_graph` (la contracción
de pasillos es la misma). La corrida de pasillo contraída cae naturalmente en un RECT largo
(double-loaded corridor)."""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from math import ceil

from oraculo.mazes.building import _contracted_graph, _mechanical_cells, _merge_map
from oraculo.mazes.maze3d import GOAL, PLAYER, Maze3D

Cell = tuple[int, int, int]
Rect = tuple[float, float, float, float]      # (x0, y0, x1, y1) en METROS, y crece hacia el sur

WALL_T = 0.20          # espesor de muro interior (m)
DOOR_W = 1.00          # ancho de vano/puerta (m)
MIN_SIDE = 2.0         # ningún cuarto no-circulación más angosto que esto (m)
MAX_SIDE = 7.0         # tope por columna/fila (m) — un ward no infla un baño vecino al absurdo
EPS = 1e-6
CHECK_EPS = 0.01
POCHÉ_MIN_SIDE = 0.35  # si el excedente por lado es menor, no vale la pena generar poché
DOUBLE_LOADED_MAX_GRID_DIST = 2  # alcance discreto para absorber poché pegado a circulación

# ── Dimensiones OBJETIVO por tipo de cuarto (ancho, profundidad) en metros ─────────────────────
# El catálogo es la SEMÁNTICA métrica del tipo (informe de legibilidad: "el baño de 8×8 destruye
# la inmersión"). La malla resuelve por columna/fila = max de los objetivos clampeado, así que
# son deseos, no garantías — la forma final la decide el layout y la audita el check.
ROOM_DIMS_M: dict[str, tuple[float, float]] = {
    "corridor": (2.2, 2.2), "hallway": (1.6, 1.6),
    "entrance": (3.0, 3.0), "reception": (3.5, 3.0),
    "ward": (6.0, 5.0), "operating_room": (5.0, 5.0), "exam_room": (3.2, 3.5),
    "nurse_station": (3.0, 3.0), "waiting_room": (4.0, 4.0),
    "classroom": (6.5, 5.5), "laboratory": (5.0, 4.5), "library": (5.5, 5.0),
    "gym": (7.0, 7.0), "cafeteria": (6.0, 5.5),
    "office": (3.2, 3.5), "cubicle": (2.5, 2.5), "meeting_room": (4.0, 3.5),
    "break_room": (3.5, 3.0), "server_room": (3.0, 4.0),
    "bedroom": (3.6, 3.6), "kitchen": (3.2, 3.5), "living_room": (5.0, 4.5),
    "bathroom": (2.2, 2.4), "restroom": (2.4, 2.4), "closet": (1.8, 1.8),
    "storage": (3.0, 3.0), "garage": (4.0, 5.5),
}
DEFAULT_DIMS_M = (3.0, 3.0)


@dataclass(frozen=True)
class DoorSpec:
    """Un VANO físico que realiza una arista del grafo contraído. `axis` = eje a lo largo del
    cual corre la ABERTURA ("x" = puerta en muro horizontal, se cruza de norte a sur). La
    mecánica viaja acá: `door_id` (llave que la abre — la puerta arranca CERRADA/sólida) y/o
    `gate_flag` (se abre con el flag ON). None/None = vano abierto."""
    edge: tuple[Cell, Cell]
    x: float
    y: float
    z: int
    axis: str
    width: float = DOOR_W
    door_id: str | None = None
    gate_flag: str | None = None


@dataclass(frozen=True)
class WallSeg:
    """Masa maciza axis-aligned: muro fino o poché grueso; el rect está en metros."""
    x0: float
    y0: float
    x1: float
    y1: float
    z: int


@dataclass
class RoomSpec:
    """Un cuarto del plano: la unión de rects (en la malla) de su región contraída; para nodos
    sin contraer es UN rect. `rep` = el nodo representante del grafo."""
    rep: Cell
    z: int
    rects: list[Rect] = field(default_factory=list)

    def bounds(self) -> Rect:
        xs0, ys0, xs1, ys1 = zip(*self.rects)
        return (min(xs0), min(ys0), max(xs1), max(ys1))


@dataclass
class FloorPlan:
    """El plano métrico completo. Mecánicas en COORDENADAS DE METROS (posiciones de items) o
    por cuarto (zonas): `keys` (pos + id), `switches` (pos del panel CONTRA un muro + flag),
    `hazard_rooms` (rep + flag — la zona es el cuarto), `start`/`goal` (pos), `stairs` (pares
    de pos vertical entre pisos), `portals` (pares de pos). Las puertas con mecánica van en
    `doors` (door_id/gate_flag)."""
    size_m: tuple[float, float]
    n_floors: int
    rooms: dict[Cell, RoomSpec]
    walls: list[WallSeg]
    doors: list[DoorSpec]
    merged: dict[Cell, Cell]
    start: tuple[float, float, int] | None = None
    goal: tuple[float, float, int] | None = None
    keys: list[dict] = field(default_factory=list)         # {"pos": (x,y,z), "id": str}
    switches: list[dict] = field(default_factory=list)     # {"pos": (x,y,z), "flag": str}
    hazard_rooms: list[dict] = field(default_factory=list)  # {"rep": Cell, "flag": str}
    stairs: list[tuple[tuple[float, float, int], tuple[float, float, int]]] = field(default_factory=list)
    portals: list[tuple[tuple[float, float, int], tuple[float, float, int]]] = field(default_factory=list)


def layout_building(source: Maze3D, *, dims: dict[Cell, tuple[float, float]],
                    merge: set[Cell] = frozenset()) -> FloorPlan:
    """Grilla fuente + dimensiones deseadas por celda (metros, del catálogo por tipo) → plano
    métrico. La malla: ancho de columna x = clamp(max de dims[c][0] de las celdas abiertas de la
    columna, MIN_SIDE, MAX_SIDE) (+ WALL_T entre columnas); filas igual. Multi-piso comparte la
    malla (max entre pisos) → las escaleras alinean. Cada cuarto se encoge dentro de su celda
    objetivo; el excedente se emite como poché macizo. Muros = todo el envelope menos cuartos,
    nichos y vanos; puertas = un DoorSpec por arista del grafo contraído, anclado al borde de las
    celdas fuente que materializan la arista, con la mecánica del nodo destino/origen
    (door_id del cuarto puerta, gate_flag del cuarto gate — TODAS las puertas de un cuarto
    gateado llevan su mecánica: no se puede entrar sin la llave/flag, fiel al esqueleto)."""
    _mechanical_cells(source)  # fuerza el mismo criterio que usa `_merge_map` para proteger mecánicas.
    merged = _merge_map(source, merge)
    nodes, _edges, edge_info = _contracted_graph(source, merged)
    active_cols, active_rows = _active_axes(source)
    if not active_cols or not active_rows:
        return FloorPlan(
            size_m=(WALL_T * 2, WALL_T * 2),
            n_floors=source.n_floors,
            rooms={},
            walls=[],
            doors=[],
            merged=merged,
        )

    col_widths, row_heights = _axis_sizes(source, dims, active_cols, active_rows)
    x_spans, total_w = _axis_spans(active_cols, col_widths)
    y_spans, total_h = _axis_spans(active_rows, row_heights)
    assigned = _partition_active(source, merged, active_cols, active_rows)

    cell_rects, room_rects = _room_rects(source, merged, dims, x_spans, y_spans)
    rooms = {
        rep: RoomSpec(rep=rep, z=rep[2], rects=sorted(room_rects.get(rep, [])))
        for rep in sorted(nodes)
    }

    door_id_by_rep = _values_by_rep(source.doors, merged)
    gate_flag_by_rep = _values_by_rep(source.gates, merged)
    doors: list[DoorSpec] = []
    door_sources: list[tuple[DoorSpec, Cell, Cell]] = []
    for pair, (a, b) in sorted(edge_info.items()):
        if a[2] != b[2] or abs(a[0] - b[0]) + abs(a[1] - b[1]) != 1:
            continue
        ra, rb = merged[a], merged[b]
        axis, line, lo, hi = _source_edge_boundary(a, b, x_spans, y_spans)
        x, y = _door_position(axis, line, lo, hi, rooms[ra].rects, rooms[rb].rects)
        door = DoorSpec(
            edge=pair,
            x=_clean(x),
            y=_clean(y),
            z=a[2],
            axis=axis,
            width=DOOR_W,
            door_id=_edge_value((ra, rb), door_id_by_rep),
            gate_flag=_edge_value((ra, rb), gate_flag_by_rep),
        )
        doors.append(door)
        door_sources.append((door, a, b))

    _add_door_niches(rooms, cell_rects, door_sources, merged)
    _add_double_loaded_annexes(
        source, merged, assigned, rooms, dims, active_cols, active_rows, x_spans, y_spans
    )
    solid_atoms = _solid_atoms(assigned, active_cols, active_rows, x_spans, y_spans, source.n_floors)
    cuts = [(rect, room.z) for room in rooms.values() for rect in room.rects]
    cuts.extend((_door_rect(door), door.z) for door in doors)
    walls = _merge_walls(_subtract_cuts(solid_atoms, cuts))

    start = _marker_pos(source.find(PLAYER), merged, rooms, x_spans, y_spans)
    goal = _marker_pos(source.find(GOAL), merged, rooms, x_spans, y_spans)
    keys = [
        {"pos": _pos_tuple(_cell_center(cell, x_spans, y_spans), cell[2]), "id": key_id}
        for cell, key_id in sorted(source.keys.items())
        if cell in merged
    ]
    switches = [
        {"pos": _pos_tuple(_switch_position(rooms[merged[cell]], [d for d in doors if merged[cell] in d.edge]), cell[2]), "flag": flag}
        for cell, flag in sorted(source.switches.items())
        if cell in merged and merged[cell] in rooms
    ]
    hazard_rooms = sorted(
        ({"rep": rep, "flag": flag} for rep, flag in _values_by_rep(source.hazards, merged).items()),
        key=lambda item: (item["rep"], item["flag"]),
    )
    stairs = _stairs(source, merged, rooms, x_spans, y_spans)
    portals = _portals(source, merged, rooms, x_spans, y_spans)

    return FloorPlan(
        size_m=(_clean(total_w), _clean(total_h)),
        n_floors=source.n_floors,
        rooms=rooms,
        walls=walls,
        doors=doors,
        merged=merged,
        start=start,
        goal=goal,
        keys=keys,
        switches=switches,
        hazard_rooms=hazard_rooms,
        stairs=stairs,
        portals=portals,
    )


def check_floorplan(source: Maze3D, plan: FloorPlan, merge: set[Cell] = frozenset()) -> list[str]:
    """El oráculo del plano (lista de fallas; vacía = OK):
    - ISOMORFISMO derivado de la GEOMETRÍA: aristas = pares de cuartos que comparten un DoorSpec
      cuya abertura cae sobre frontera REAL de ambos (verificado contra los rects) == grafo
      fuente contraído, exacto. Aristas verticales por `stairs` alineadas en XY; portales aparte.
    - COBERTURA: los rects de cuartos no se solapan; cuartos + muros cubren el envelope (nada de
      espacio abierto huérfano); toda frontera entre cuartos distintos está cubierta por muro
      salvo las aberturas de sus DoorSpec (ε=1 cm).
    - Puertas con width ≥ 0.9 m; los cuartos no se solapan con otros cuartos ni con poché.
    - Mecánicas: cada door/key/gate/switch/hazard/portal/conector del fuente presente (ids y
      flags exactos); las puertas de un cuarto-door llevan su door_id; P/G presentes.
    La winnability se hereda del isomorfismo (mecánicas de nodo preservadas) — el BFS del FUENTE
    es la prueba; no hay grilla fina que resolver."""
    failures: list[str] = []
    expected_merged = _merge_map(source, merge)
    expected_nodes, expected_edges, _ = _contracted_graph(source, expected_merged)
    got_edges, graph_failures = _floorplan_edges(plan)

    if plan.merged != expected_merged:
        failures.append("merged no coincide con la contraccion esperada")
    got_nodes = set(plan.rooms)
    if got_nodes != expected_nodes:
        failures.append(f"nodos distintos: faltan={sorted(expected_nodes - got_nodes)} sobran={sorted(got_nodes - expected_nodes)}")
    if got_edges != expected_edges:
        failures.append(f"aristas distintas: faltan={sorted(expected_edges - got_edges)} sobran={sorted(got_edges - expected_edges)}")

    failures.extend(graph_failures)
    failures.extend(_geometry_failures(plan))
    failures.extend(_mechanic_failures(source, plan, expected_merged))
    return failures


def room_passable(room: RoomSpec, doors: list[DoorSpec], prop_boxes: list[Rect],
                  clearance: float = 0.6) -> bool:
    """¿El cuarto sigue siendo transitable con estos props adentro? Raster fino (0.2 m) del
    interior del cuarto menos los AABBs de props bloqueantes → BFS: TODAS sus puertas deben
    quedar mutuamente alcanzables con un pasillo interno de al menos `clearance`. Lo llama el
    amoblado del dress (la receta propone, esto dispone)."""
    step = 0.2
    x0, y0, x1, y1 = room.bounds()
    nx = max(1, ceil((x1 - x0) / step))
    ny = max(1, ceil((y1 - y0) / step))
    radius = max(0, ceil((clearance / 2.0) / step))

    def center(ix: int, iy: int) -> tuple[float, float]:
        return (x0 + (ix + 0.5) * step, y0 + (iy + 0.5) * step)

    raw: set[tuple[int, int]] = set()
    for iy in range(ny):
        for ix in range(nx):
            px, py = center(ix, iy)
            if _point_in_rects(px, py, room.rects) and not any(_point_in_rect(px, py, box) for box in prop_boxes):
                raw.add((ix, iy))

    free: set[tuple[int, int]] = set()
    for ix, iy in raw:
        ok = True
        for dy in range(-radius, radius + 1):
            for dx in range(-radius, radius + 1):
                if dx * dx + dy * dy > radius * radius:
                    continue
                if (ix + dx, iy + dy) not in raw:
                    ok = False
                    break
            if not ok:
                break
        if ok:
            free.add((ix, iy))

    touching = [door for door in doors if _door_touches_room(room, door)]
    if len(touching) <= 1:
        return all(_door_seed(room, door, free, center, clearance) is not None for door in touching)

    seeds = [_door_seed(room, door, free, center, clearance) for door in touching]
    if any(seed is None for seed in seeds):
        return False
    targets = set(seeds)
    seen = {seeds[0]}
    queue: deque[tuple[int, int]] = deque([seeds[0]])
    while queue:
        ix, iy = queue.popleft()
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            nxt = (ix + dx, iy + dy)
            if nxt in free and nxt not in seen:
                seen.add(nxt)
                queue.append(nxt)
    return targets <= seen


def _pair(a: Cell, b: Cell) -> tuple[Cell, Cell]:
    return (a, b) if a <= b else (b, a)


def _clean(value: float) -> float:
    return round(value, 6)


def _clean_rect(rect: Rect) -> Rect:
    return tuple(_clean(v) for v in rect)  # type: ignore[return-value]


def _active_axes(source: Maze3D) -> tuple[list[int], list[int]]:
    open_cells = source.open_cells()
    return sorted({x for x, _y, _z in open_cells}), sorted({y for _x, y, _z in open_cells})


def _clamp_side(value: float) -> float:
    return min(MAX_SIDE, max(MIN_SIDE, value))


def _axis_sizes(
    source: Maze3D,
    dims: dict[Cell, tuple[float, float]],
    cols: list[int],
    rows: list[int],
) -> tuple[dict[int, float], dict[int, float]]:
    open_cells = source.open_cells()
    col_widths: dict[int, float] = {}
    row_heights: dict[int, float] = {}
    for x in cols:
        wanted = [dims.get(cell, DEFAULT_DIMS_M)[0] for cell in open_cells if cell[0] == x]
        col_widths[x] = _clamp_side(max(wanted, default=DEFAULT_DIMS_M[0]))
    for y in rows:
        wanted = [dims.get(cell, DEFAULT_DIMS_M)[1] for cell in open_cells if cell[1] == y]
        row_heights[y] = _clamp_side(max(wanted, default=DEFAULT_DIMS_M[1]))
    return col_widths, row_heights


def _axis_spans(indices: list[int], sizes: dict[int, float]) -> tuple[dict[int, tuple[float, float]], float]:
    pos = WALL_T
    spans: dict[int, tuple[float, float]] = {}
    for idx in indices:
        spans[idx] = (_clean(pos), _clean(pos + sizes[idx]))
        pos += sizes[idx] + WALL_T
    return spans, pos


def _partition_active(
    source: Maze3D,
    merged: dict[Cell, Cell],
    cols: list[int],
    rows: list[int],
) -> dict[Cell, Cell]:
    assigned: dict[Cell, Cell] = {}
    by_floor: dict[int, list[tuple[int, int, Cell]]] = {}
    for x, y, z in sorted(source.open_cells()):
        by_floor.setdefault(z, []).append((x, y, merged[(x, y, z)]))

    for z in range(source.n_floors):
        seeds = by_floor.get(z, [])
        if not seeds:
            continue
        for y in rows:
            for x in cols:
                cell = (x, y, z)
                if cell in merged:
                    assigned[cell] = merged[cell]
                else:
                    # Los muros internos del ASCII no son sagrados: se absorben por Voronoi Manhattan.
                    _dist, rep = min((abs(x - sx) + abs(y - sy), rep) for sx, sy, rep in seeds)
                    assigned[cell] = rep
    return assigned


def _tracks(indices: list[int], spans: dict[int, tuple[float, float]]) -> list[tuple[float, float]]:
    out: list[tuple[float, float]] = [(0.0, WALL_T)]
    for i, idx in enumerate(indices):
        x0, x1 = spans[idx]
        out.append((x0, x1))
        if i == len(indices) - 1:
            out.append((x1, _clean(x1 + WALL_T)))
        else:
            out.append((x1, spans[indices[i + 1]][0]))
    return out


def _plan_atoms(
    assigned: dict[Cell, Cell],
    cols: list[int],
    rows: list[int],
    x_spans: dict[int, tuple[float, float]],
    y_spans: dict[int, tuple[float, float]],
    n_floors: int,
) -> tuple[dict[Cell, list[Rect]], list[tuple[Rect, int]]]:
    xs = _tracks(cols, x_spans)
    ys = _tracks(rows, y_spans)
    rooms: dict[Cell, list[Rect]] = {}
    walls: list[tuple[Rect, int]] = []
    for z in range(n_floors):
        if not any(cell[2] == z for cell in assigned):
            continue
        for yi, (y0, y1) in enumerate(ys):
            for xi, (x0, x1) in enumerate(xs):
                rect = _clean_rect((x0, y0, x1, y1))
                owner = _atom_owner(assigned, cols, rows, xi, yi, z)
                if owner is None:
                    walls.append((rect, z))
                else:
                    rooms.setdefault(owner, []).append(rect)
    return rooms, walls


def _solid_atoms(
    assigned: dict[Cell, Cell],
    cols: list[int],
    rows: list[int],
    x_spans: dict[int, tuple[float, float]],
    y_spans: dict[int, tuple[float, float]],
    n_floors: int,
) -> list[tuple[Rect, int]]:
    xs = _tracks(cols, x_spans)
    ys = _tracks(rows, y_spans)
    out: list[tuple[Rect, int]] = []
    for z in range(n_floors):
        if not any(cell[2] == z for cell in assigned):
            continue
        for y0, y1 in ys:
            for x0, x1 in xs:
                out.append((_clean_rect((x0, y0, x1, y1)), z))
    return out


def _room_rects(
    source: Maze3D,
    merged: dict[Cell, Cell],
    dims: dict[Cell, tuple[float, float]],
    x_spans: dict[int, tuple[float, float]],
    y_spans: dict[int, tuple[float, float]],
) -> tuple[dict[Cell, list[Rect]], dict[Cell, list[Rect]]]:
    cells_by_rep: dict[Cell, list[Cell]] = {}
    for cell in sorted(source.open_cells()):
        if cell in merged:
            cells_by_rep.setdefault(merged[cell], []).append(cell)

    cell_rects: dict[Cell, list[Rect]] = {}
    room_rects: dict[Cell, list[Rect]] = {}
    for rep, cells in sorted(cells_by_rep.items()):
        circulation = _is_circulation_rep(cells, dims)
        corridor_w = _circulation_width(cells, dims)
        for cell in cells:
            atom = _cell_rect(cell, x_spans, y_spans)
            if circulation:
                rects = _circulation_rects(source, merged, cell, atom, corridor_w, x_spans, y_spans)
            else:
                rects = [_shrunken_rect(atom, dims.get(cell, DEFAULT_DIMS_M))]
            rects = _dedupe_rects(rects)
            cell_rects[cell] = rects
            room_rects.setdefault(rep, []).extend(rects)

    return cell_rects, {rep: _dedupe_rects(rects) for rep, rects in room_rects.items()}


def _add_double_loaded_annexes(
    source: Maze3D,
    merged: dict[Cell, Cell],
    assigned: dict[Cell, Cell],
    rooms: dict[Cell, RoomSpec],
    dims: dict[Cell, tuple[float, float]],
    cols: list[int],
    rows: list[int],
    x_spans: dict[int, tuple[float, float]],
    y_spans: dict[int, tuple[float, float]],
) -> None:
    """Convierte poché interno pegado a pasillos en anexos de cuartos cercanos.

    El grafo no cambia: sólo se cortan más rects de cuarto dentro de celdas cerradas del
    bounding box, manteniendo los muros/puertas existentes entre regiones distintas. Esto
    permite pasillos double-loaded sin declarar aristas nuevas ni mover vanos.
    """
    open_cells = source.open_cells()
    non_circulation_reps = {
        rep for rep in rooms
        if not _is_circulation_dim(dims.get(rep, DEFAULT_DIMS_M))
    }
    if len(non_circulation_reps) < 4:
        return

    circulation_cells = {
        cell for cell in open_cells
        if merged.get(cell) not in non_circulation_reps
        and _is_circulation_dim(dims.get(merged.get(cell, cell), dims.get(cell, DEFAULT_DIMS_M)))
    }
    if not circulation_cells:
        return

    seeds = [
        (cell, merged[cell])
        for cell in sorted(open_cells)
        if merged.get(cell) in non_circulation_reps
    ]
    if not seeds:
        return

    for z in range(source.n_floors):
        for y in rows:
            for x in cols:
                cell = (x, y, z)
                if cell in open_cells or cell not in assigned:
                    continue
                if not any((x + dx, y + dy, z) in circulation_cells
                           for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1))):
                    continue
                dist, rep = min(
                    (abs(x - seed[0]) + abs(y - seed[1]) + 10 * abs(z - seed[2]), rep)
                    for seed, rep in seeds
                )
                if dist > DOUBLE_LOADED_MAX_GRID_DIST or rep not in rooms:
                    continue
                rooms[rep].rects.append(_clean_rect(_cell_rect(cell, x_spans, y_spans)))

    for room in rooms.values():
        room.rects = _dedupe_rects(room.rects)


def _is_circulation_rep(cells: list[Cell], dims: dict[Cell, tuple[float, float]]) -> bool:
    return len(cells) > 1 or any(_is_circulation_dim(dims.get(cell, DEFAULT_DIMS_M)) for cell in cells)


def _is_circulation_dim(dim: tuple[float, float]) -> bool:
    return _dim_matches(dim, ROOM_DIMS_M["corridor"]) or _dim_matches(dim, ROOM_DIMS_M["hallway"])


def _dim_matches(a: tuple[float, float], b: tuple[float, float]) -> bool:
    return _same(a[0], b[0]) and _same(a[1], b[1])


def _circulation_width(cells: list[Cell], dims: dict[Cell, tuple[float, float]]) -> float:
    if any(_dim_matches(dims.get(cell, DEFAULT_DIMS_M), ROOM_DIMS_M["hallway"]) for cell in cells):
        return ROOM_DIMS_M["hallway"][0]
    if any(_dim_matches(dims.get(cell, DEFAULT_DIMS_M), ROOM_DIMS_M["corridor"]) for cell in cells):
        return ROOM_DIMS_M["corridor"][0]
    wanted = min(min(dims.get(cell, DEFAULT_DIMS_M)) for cell in cells)
    return max(DOOR_W, min(wanted, ROOM_DIMS_M["corridor"][0]))


def _shrunken_rect(atom: Rect, target: tuple[float, float]) -> Rect:
    x0, y0, x1, y1 = atom
    width = _room_target_length(x1 - x0, max(MIN_SIDE, target[0]))
    height = _room_target_length(y1 - y0, max(MIN_SIDE, target[1]))
    cx, cy = (x0 + x1) / 2.0, (y0 + y1) / 2.0
    return _clean_rect((cx - width / 2.0, cy - height / 2.0, cx + width / 2.0, cy + height / 2.0))


def _room_target_length(atom_len: float, target: float) -> float:
    wanted = min(atom_len, target)
    if atom_len <= wanted + POCHÉ_MIN_SIDE * 2.0 + EPS:
        return atom_len
    return wanted


def _circulation_rects(
    source: Maze3D,
    merged: dict[Cell, Cell],
    cell: Cell,
    atom: Rect,
    width: float,
    x_spans: dict[int, tuple[float, float]],
    y_spans: dict[int, tuple[float, float]],
) -> list[Rect]:
    x0, y0, x1, y1 = atom
    cx, cy = (x0 + x1) / 2.0, (y0 + y1) / 2.0
    ix0, ix1 = _centered_interval_exact(x0, x1, width)
    iy0, iy1 = _centered_interval_exact(y0, y1, width)
    rects = [_clean_rect((ix0, iy0, ix1, iy1))]
    for neighbor in source.neighbors(cell):
        dx, dy = neighbor[0] - cell[0], neighbor[1] - cell[1]
        if neighbor[2] != cell[2] or abs(dx) + abs(dy) != 1 or neighbor not in merged:
            continue
        same_room = merged[neighbor] == merged[cell]
        if dx:
            end = _grid_line_between(cell, neighbor, x_spans, y_spans) if same_room else (x1 if dx > 0 else x0)
            rects.append(_clean_rect((min(cx, end), iy0, max(cx, end), iy1)))
        else:
            end = _grid_line_between(cell, neighbor, x_spans, y_spans) if same_room else (y1 if dy > 0 else y0)
            rects.append(_clean_rect((ix0, min(cy, end), ix1, max(cy, end))))
    return [rect for rect in rects if rect[2] - rect[0] > EPS and rect[3] - rect[1] > EPS]


def _centered_interval_exact(lo: float, hi: float, width: float) -> tuple[float, float]:
    span = hi - lo
    if span <= width + EPS:
        return lo, hi
    center = (lo + hi) / 2.0
    half = width / 2.0
    return center - half, center + half


def _grid_line_between(
    cell: Cell,
    neighbor: Cell,
    x_spans: dict[int, tuple[float, float]],
    y_spans: dict[int, tuple[float, float]],
) -> float:
    if cell[0] != neighbor[0]:
        left, right = sorted((cell[0], neighbor[0]))
        return _clean((x_spans[left][1] + x_spans[right][0]) / 2.0)
    top, bottom = sorted((cell[1], neighbor[1]))
    return _clean((y_spans[top][1] + y_spans[bottom][0]) / 2.0)


def _dedupe_rects(rects: list[Rect]) -> list[Rect]:
    seen: set[Rect] = set()
    out: list[Rect] = []
    for rect in rects:
        clean = _clean_rect(rect)
        if clean in seen or clean[2] - clean[0] <= EPS or clean[3] - clean[1] <= EPS:
            continue
        seen.add(clean)
        out.append(clean)
    return sorted(out)


def _atom_owner(
    assigned: dict[Cell, Cell],
    cols: list[int],
    rows: list[int],
    xi: int,
    yi: int,
    z: int,
) -> Cell | None:
    x_cell = xi % 2 == 1
    y_cell = yi % 2 == 1
    if x_cell and y_cell:
        return assigned.get((cols[xi // 2], rows[yi // 2], z))
    if xi == 0 or yi == 0 or xi == len(cols) * 2 or yi == len(rows) * 2:
        return None
    if not x_cell and y_cell:
        row = rows[yi // 2]
        left = assigned.get((cols[xi // 2 - 1], row, z))
        right = assigned.get((cols[xi // 2], row, z))
        return left if left is not None and left == right else None
    if x_cell and not y_cell:
        col = cols[xi // 2]
        top = assigned.get((col, rows[yi // 2 - 1], z))
        bottom = assigned.get((col, rows[yi // 2], z))
        return top if top is not None and top == bottom else None
    reps = {
        assigned.get((cols[xi // 2 - 1], rows[yi // 2 - 1], z)),
        assigned.get((cols[xi // 2], rows[yi // 2 - 1], z)),
        assigned.get((cols[xi // 2 - 1], rows[yi // 2], z)),
        assigned.get((cols[xi // 2], rows[yi // 2], z)),
    }
    return reps.pop() if len(reps) == 1 and None not in reps else None


def _values_by_rep(values: dict[Cell, str], merged: dict[Cell, Cell]) -> dict[Cell, str]:
    out: dict[Cell, str] = {}
    for cell, value in values.items():
        if cell in merged:
            out[merged[cell]] = value
    return out


def _edge_value(edge: tuple[Cell, Cell], values: dict[Cell, str]) -> str | None:
    vals = [values[rep] for rep in edge if rep in values]
    return vals[0] if vals else None


def _cell_rect(cell: Cell, x_spans: dict[int, tuple[float, float]], y_spans: dict[int, tuple[float, float]]) -> Rect:
    x, y, _z = cell
    x0, x1 = x_spans[x]
    y0, y1 = y_spans[y]
    return (x0, y0, x1, y1)


def _source_edge_boundary(
    a: Cell,
    b: Cell,
    x_spans: dict[int, tuple[float, float]],
    y_spans: dict[int, tuple[float, float]],
) -> tuple[str, float, float, float]:
    ax0, ay0, ax1, ay1 = _cell_rect(a, x_spans, y_spans)
    bx0, by0, bx1, by1 = _cell_rect(b, x_spans, y_spans)
    if a[0] != b[0]:
        left, right = (a, b) if a[0] < b[0] else (b, a)
        line = _clean((x_spans[left[0]][1] + x_spans[right[0]][0]) / 2.0)
        return "y", line, max(ay0, by0), min(ay1, by1)
    top, bottom = (a, b) if a[1] < b[1] else (b, a)
    line = _clean((y_spans[top[1]][1] + y_spans[bottom[1]][0]) / 2.0)
    return "x", line, max(ax0, bx0), min(ax1, bx1)


def _cell_center(cell: Cell, x_spans: dict[int, tuple[float, float]], y_spans: dict[int, tuple[float, float]]) -> tuple[float, float]:
    x0, y0, x1, y1 = _cell_rect(cell, x_spans, y_spans)
    return (_clean((x0 + x1) / 2.0), _clean((y0 + y1) / 2.0))


def _pos_tuple(pos: tuple[float, float], z: int) -> tuple[float, float, int]:
    return (_clean(pos[0]), _clean(pos[1]), z)


def _marker_pos(
    cell: Cell | None,
    merged: dict[Cell, Cell],
    rooms: dict[Cell, RoomSpec],
    x_spans: dict[int, tuple[float, float]],
    y_spans: dict[int, tuple[float, float]],
) -> tuple[float, float, int] | None:
    if cell is None or cell not in merged or merged[cell] not in rooms:
        return None
    return _pos_tuple(_cell_center(cell, x_spans, y_spans), cell[2])


def _shared_boundary_segments(
    pair: tuple[Cell, Cell],
    assigned: dict[Cell, Cell],
    cols: list[int],
    rows: list[int],
    x_spans: dict[int, tuple[float, float]],
    y_spans: dict[int, tuple[float, float]],
    z: int,
) -> list[tuple[str, float, float, float]]:
    out: list[tuple[str, float, float, float]] = []
    for i in range(len(cols) - 1):
        left_x, right_x = cols[i], cols[i + 1]
        line = _clean((x_spans[left_x][1] + x_spans[right_x][0]) / 2.0)
        for y in rows:
            left = assigned.get((left_x, y, z))
            right = assigned.get((right_x, y, z))
            if left is not None and right is not None and left != right and _pair(left, right) == pair:
                out.append(("y", line, y_spans[y][0], y_spans[y][1]))
    for i in range(len(rows) - 1):
        top_y, bottom_y = rows[i], rows[i + 1]
        line = _clean((y_spans[top_y][1] + y_spans[bottom_y][0]) / 2.0)
        for x in cols:
            top = assigned.get((x, top_y, z))
            bottom = assigned.get((x, bottom_y, z))
            if top is not None and bottom is not None and top != bottom and _pair(top, bottom) == pair:
                out.append(("x", line, x_spans[x][0], x_spans[x][1]))
    return out


def _door_position(axis: str, line: float, lo: float, hi: float, a_rects: list[Rect], b_rects: list[Rect]) -> tuple[float, float]:
    a_intervals = _projection_intervals(a_rects, axis, lo, hi)
    b_intervals = _projection_intervals(b_rects, axis, lo, hi)
    along = _door_along_position(a_intervals, b_intervals, lo, hi)
    return (_clean(along), _clean(line)) if axis == "x" else (_clean(line), _clean(along))


def _projection_intervals(rects: list[Rect], axis: str, lo: float, hi: float) -> list[tuple[float, float]]:
    intervals: list[tuple[float, float]] = []
    for rect in rects:
        rlo, rhi = (rect[0], rect[2]) if axis == "x" else (rect[1], rect[3])
        p0, p1 = max(lo, rlo), min(hi, rhi)
        if p1 - p0 > EPS:
            intervals.append((_clean(p0), _clean(p1)))
    return sorted(intervals)


def _door_along_position(
    a_intervals: list[tuple[float, float]],
    b_intervals: list[tuple[float, float]],
    lo: float,
    hi: float,
) -> float:
    best_overlap: tuple[float, float] | None = None
    for a0, a1 in a_intervals:
        for b0, b1 in b_intervals:
            o0, o1 = max(a0, b0), min(a1, b1)
            if o1 - o0 >= DOOR_W - CHECK_EPS and (
                best_overlap is None or o1 - o0 > best_overlap[1] - best_overlap[0]
            ):
                best_overlap = (o0, o1)
    if best_overlap is not None:
        return _clamp_door_center((best_overlap[0] + best_overlap[1]) / 2.0, lo, hi)

    a_mid = _longest_interval_midpoint(a_intervals, lo, hi)
    b_mid = _longest_interval_midpoint(b_intervals, lo, hi)
    return _clamp_door_center((a_mid + b_mid) / 2.0, lo, hi)


def _longest_interval_midpoint(intervals: list[tuple[float, float]], lo: float, hi: float) -> float:
    if not intervals:
        return (lo + hi) / 2.0
    a0, a1 = max(intervals, key=lambda it: (it[1] - it[0], -it[0]))
    return (a0 + a1) / 2.0


def _clamp_door_center(value: float, lo: float, hi: float) -> float:
    min_center, max_center = lo + DOOR_W / 2.0, hi - DOOR_W / 2.0
    if max_center < min_center:
        return (lo + hi) / 2.0
    return min(max(value, min_center), max_center)


def _add_door_niches(
    rooms: dict[Cell, RoomSpec],
    cell_rects: dict[Cell, list[Rect]],
    door_sources: list[tuple[DoorSpec, Cell, Cell]],
    merged: dict[Cell, Cell],
) -> None:
    for door, a, b in door_sources:
        for cell, other in ((a, b), (b, a)):
            rep = merged[cell]
            niche = _door_niche(cell, other, cell_rects.get(cell, []), door)
            if niche is not None:
                rooms[rep].rects.append(niche)
    for room in rooms.values():
        room.rects = _dedupe_rects(room.rects)


def _door_niche(cell: Cell, other: Cell, rects: list[Rect], door: DoorSpec) -> Rect | None:
    if not rects:
        return None
    half = door.width / 2.0
    if door.axis == "y" and cell[0] != other[0]:
        y0, y1 = door.y - half, door.y + half
        candidates = _rects_crossing_interval(rects, "y", y0, y1)
        if cell[0] < other[0]:
            edge = max(rect[2] for rect in candidates)
            return None if edge >= door.x - EPS else _clean_rect((edge, y0, door.x, y1))
        edge = min(rect[0] for rect in candidates)
        return None if edge <= door.x + EPS else _clean_rect((door.x, y0, edge, y1))
    if door.axis == "x" and cell[1] != other[1]:
        x0, x1 = door.x - half, door.x + half
        candidates = _rects_crossing_interval(rects, "x", x0, x1)
        if cell[1] < other[1]:
            edge = max(rect[3] for rect in candidates)
            return None if edge >= door.y - EPS else _clean_rect((x0, edge, x1, door.y))
        edge = min(rect[1] for rect in candidates)
        return None if edge <= door.y + EPS else _clean_rect((x0, door.y, x1, edge))
    return None


def _rects_crossing_interval(rects: list[Rect], axis: str, lo: float, hi: float) -> list[Rect]:
    idx0, idx1 = (0, 2) if axis == "x" else (1, 3)
    crossing = [rect for rect in rects if min(rect[idx1], hi) - max(rect[idx0], lo) > EPS]
    return crossing or rects


def _door_rect(door: DoorSpec) -> Rect:
    half = door.width / 2.0
    if door.axis == "x":
        return _clean_rect((door.x - half, door.y - WALL_T / 2.0, door.x + half, door.y + WALL_T / 2.0))
    return _clean_rect((door.x - WALL_T / 2.0, door.y - half, door.x + WALL_T / 2.0, door.y + half))


def _subtract_cuts(solids: list[tuple[Rect, int]], cuts: list[tuple[Rect, int]]) -> list[WallSeg]:
    out: list[WallSeg] = []
    for rect, z in solids:
        pieces = [rect]
        for cut, cut_z in cuts:
            if cut_z != z:
                continue
            next_pieces: list[Rect] = []
            for piece in pieces:
                next_pieces.extend(_subtract_rect(piece, cut))
            pieces = next_pieces
        for x0, y0, x1, y1 in pieces:
            if x1 - x0 > EPS and y1 - y0 > EPS:
                out.append(WallSeg(_clean(x0), _clean(y0), _clean(x1), _clean(y1), z))
    return out


def _subtract_rect(rect: Rect, cut: Rect) -> list[Rect]:
    x0, y0, x1, y1 = rect
    cx0, cy0, cx1, cy1 = cut
    ox0, oy0, ox1, oy1 = max(x0, cx0), max(y0, cy0), min(x1, cx1), min(y1, cy1)
    if ox1 <= ox0 + EPS or oy1 <= oy0 + EPS:
        return [rect]
    pieces = [
        (x0, y0, ox0, y1),
        (ox1, y0, x1, y1),
        (ox0, y0, ox1, oy0),
        (ox0, oy1, ox1, y1),
    ]
    return [_clean_rect(piece) for piece in pieces if piece[2] - piece[0] > EPS and piece[3] - piece[1] > EPS]


def _merge_walls(walls: list[WallSeg]) -> list[WallSeg]:
    changed = True
    merged = walls[:]
    while changed:
        changed = False
        out: list[WallSeg] = []
        used = [False] * len(merged)
        for i, wall in enumerate(merged):
            if used[i]:
                continue
            cur = wall
            for j in range(i + 1, len(merged)):
                other = merged[j]
                if used[j] or other.z != cur.z:
                    continue
                if _same(cur.x0, other.x0) and _same(cur.x1, other.x1) and (_same(cur.y1, other.y0) or _same(other.y1, cur.y0)):
                    cur = WallSeg(cur.x0, min(cur.y0, other.y0), cur.x1, max(cur.y1, other.y1), cur.z)
                    used[j] = True
                    changed = True
                elif _same(cur.y0, other.y0) and _same(cur.y1, other.y1) and (_same(cur.x1, other.x0) or _same(other.x1, cur.x0)):
                    cur = WallSeg(min(cur.x0, other.x0), cur.y0, max(cur.x1, other.x1), cur.y1, cur.z)
                    used[j] = True
                    changed = True
            used[i] = True
            out.append(cur)
        merged = out
    return sorted(merged, key=lambda w: (w.z, w.y0, w.x0, w.y1, w.x1))


def _same(a: float, b: float, eps: float = CHECK_EPS) -> bool:
    return abs(a - b) <= eps


def _switch_position(room: RoomSpec, doors: list[DoorSpec]) -> tuple[float, float]:
    bx0, by0, bx1, by1 = max(room.rects, key=lambda r: (r[2] - r[0]) * (r[3] - r[1]))
    candidates = [
        (bx0 + 0.25, (by0 + by1) / 2.0),
        (bx1 - 0.25, (by0 + by1) / 2.0),
        ((bx0 + bx1) / 2.0, by0 + 0.25),
        ((bx0 + bx1) / 2.0, by1 - 0.25),
    ]
    inside = [p for p in candidates if _point_in_rect(p[0], p[1], (bx0, by0, bx1, by1))]
    if not inside:
        return _room_center(room)
    return max(inside, key=lambda p: min((_dist2(p, (d.x, d.y)) for d in doors), default=9999.0))


def _room_center(room: RoomSpec) -> tuple[float, float]:
    x0, y0, x1, y1 = room.bounds()
    return (_clean((x0 + x1) / 2.0), _clean((y0 + y1) / 2.0))


def _dist2(a: tuple[float, float], b: tuple[float, float]) -> float:
    return (a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2


def _stairs(
    source: Maze3D,
    merged: dict[Cell, Cell],
    rooms: dict[Cell, RoomSpec],
    x_spans: dict[int, tuple[float, float]],
    y_spans: dict[int, tuple[float, float]],
) -> list[tuple[tuple[float, float, int], tuple[float, float, int]]]:
    out: list[tuple[tuple[float, float, int], tuple[float, float, int]]] = []
    for cell in sorted(source.connectors | source.ladders):
        top = (cell[0], cell[1], cell[2] + 1)
        if cell not in merged or top not in merged or merged[cell] not in rooms or merged[top] not in rooms:
            continue
        xy = _cell_center(cell, x_spans, y_spans)
        out.append((_pos_tuple(xy, cell[2]), _pos_tuple(xy, cell[2] + 1)))
    return out


def _portals(
    source: Maze3D,
    merged: dict[Cell, Cell],
    rooms: dict[Cell, RoomSpec],
    x_spans: dict[int, tuple[float, float]],
    y_spans: dict[int, tuple[float, float]],
) -> list[tuple[tuple[float, float, int], tuple[float, float, int]]]:
    out: list[tuple[tuple[float, float, int], tuple[float, float, int]]] = []
    for src, dst in source.portals:
        if src not in merged or dst not in merged or merged[src] not in rooms or merged[dst] not in rooms:
            continue
        out.append((_pos_tuple(_cell_center(src, x_spans, y_spans), src[2]),
                    _pos_tuple(_cell_center(dst, x_spans, y_spans), dst[2])))
    return out


def _floorplan_edges(plan: FloorPlan) -> tuple[set[tuple[Cell, Cell]], list[str]]:
    edges: set[tuple[Cell, Cell]] = set()
    failures: list[str] = []
    for door in plan.doors:
        touching = _door_touching_rooms(plan, door)
        if door.width < 0.9:
            failures.append(f"puerta demasiado angosta: {door.edge} width={door.width}")
        if len(touching) != 2:
            failures.append(f"puerta fuera de frontera real: {door.edge}")
            continue
        pair = _pair(touching[0], touching[1])
        edges.add(pair)
        if pair != _pair(*door.edge):
            failures.append(f"puerta declara {door.edge} pero cae en {pair}")
    for a, b in plan.stairs:
        if not (_same(a[0], b[0]) and _same(a[1], b[1]) and abs(a[2] - b[2]) == 1):
            failures.append(f"stair desalineada: {a}->{b}")
            continue
        ra = _room_at_pos(plan, a)
        rb = _room_at_pos(plan, b)
        if ra is None or rb is None:
            failures.append(f"stair fuera de cuarto: {a}->{b}")
        elif ra != rb:
            edges.add(_pair(ra, rb))
    for a, b in plan.portals:
        ra = _room_at_pos(plan, a)
        rb = _room_at_pos(plan, b)
        if ra is None or rb is None:
            failures.append(f"portal fuera de cuarto: {a}->{b}")
        elif ra != rb:
            edges.add(_pair(ra, rb))
    failures.extend(_room_contact_failures(plan))
    return edges, failures


def _room_contact_failures(plan: FloorPlan) -> list[str]:
    failures: list[str] = []
    doors_by_pair: dict[tuple[Cell, Cell], list[DoorSpec]] = {}
    for door in plan.doors:
        doors_by_pair.setdefault(_pair(*door.edge), []).append(door)

    rooms = list(plan.rooms.items())
    for i, (ra, a) in enumerate(rooms):
        for rb, b in rooms[i + 1:]:
            if a.z != b.z:
                continue
            pair = _pair(ra, rb)
            bad_contact = False
            for axis, line, lo, hi in _room_contacts(a.rects, b.rects):
                if not _contact_covered_by_doors(axis, line, lo, hi, a.z, doors_by_pair.get(pair, [])):
                    failures.append(f"contacto abierto extra: {pair}")
                    bad_contact = True
                    break
            if bad_contact:
                continue
    return failures


def _room_contacts(a_rects: list[Rect], b_rects: list[Rect]) -> list[tuple[str, float, float, float]]:
    out: list[tuple[str, float, float, float]] = []
    for a in a_rects:
        for b in b_rects:
            y0, y1 = max(a[1], b[1]), min(a[3], b[3])
            if y1 - y0 > CHECK_EPS and _same(a[2], b[0]):
                out.append(("y", a[2], y0, y1))
            if y1 - y0 > CHECK_EPS and _same(b[2], a[0]):
                out.append(("y", b[2], y0, y1))
            x0, x1 = max(a[0], b[0]), min(a[2], b[2])
            if x1 - x0 > CHECK_EPS and _same(a[3], b[1]):
                out.append(("x", a[3], x0, x1))
            if x1 - x0 > CHECK_EPS and _same(b[3], a[1]):
                out.append(("x", b[3], x0, x1))
    return out


def _contact_covered_by_doors(axis: str, line: float, lo: float, hi: float, z: int, doors: list[DoorSpec]) -> bool:
    openings: list[tuple[float, float]] = []
    for door in doors:
        if door.z != z or door.axis != axis:
            continue
        half = door.width / 2.0
        if axis == "x" and _same(door.y, line):
            openings.append((door.x - half, door.x + half))
        elif axis == "y" and _same(door.x, line):
            openings.append((door.y - half, door.y + half))
    cursor = lo
    for o0, o1 in sorted(openings):
        if o1 <= cursor + CHECK_EPS:
            continue
        if o0 > cursor + CHECK_EPS:
            return False
        cursor = max(cursor, o1)
        if cursor >= hi - CHECK_EPS:
            return True
    return cursor >= hi - CHECK_EPS


def _door_touching_rooms(plan: FloorPlan, door: DoorSpec) -> list[Cell]:
    out: list[Cell] = []
    for rep, room in plan.rooms.items():
        if _door_touches_room(room, door):
            out.append(rep)
    return sorted(out)


def _door_touches_room(room: RoomSpec, door: DoorSpec) -> bool:
    if room.z != door.z:
        return False
    half = door.width / 2.0
    if door.axis == "x":
        lo, hi = door.x - half, door.x + half
        return any(
            (_same(rect[3], door.y) or _same(rect[1], door.y))
            and rect[0] <= lo + CHECK_EPS and rect[2] >= hi - CHECK_EPS
            for rect in room.rects
        )
    if door.axis == "y":
        lo, hi = door.y - half, door.y + half
        return any(
            (_same(rect[2], door.x) or _same(rect[0], door.x))
            and rect[1] <= lo + CHECK_EPS and rect[3] >= hi - CHECK_EPS
            for rect in room.rects
        )
    return False


def _room_at_pos(plan: FloorPlan, pos: tuple[float, float, int] | None) -> Cell | None:
    if pos is None:
        return None
    x, y, z = pos
    for rep, room in plan.rooms.items():
        if room.z == z and _point_in_rects(x, y, room.rects):
            return rep
    return None


def _point_in_rects(x: float, y: float, rects: list[Rect]) -> bool:
    return any(_point_in_rect(x, y, rect) for rect in rects)


def _point_in_rect(x: float, y: float, rect: Rect) -> bool:
    x0, y0, x1, y1 = rect
    return x0 - CHECK_EPS <= x <= x1 + CHECK_EPS and y0 - CHECK_EPS <= y <= y1 + CHECK_EPS


def _rect_overlap(a: Rect, b: Rect, eps: float = CHECK_EPS) -> bool:
    return min(a[2], b[2]) - max(a[0], b[0]) > eps and min(a[3], b[3]) - max(a[1], b[1]) > eps


def _geometry_failures(plan: FloorPlan) -> list[str]:
    failures: list[str] = []
    w, h = plan.size_m
    by_floor: dict[int, list[tuple[Cell, Rect]]] = {}
    for rep, room in plan.rooms.items():
        if not room.rects:
            failures.append(f"cuarto sin rects: {rep}")
            continue
        for rect in room.rects:
            if rect[0] < -CHECK_EPS or rect[1] < -CHECK_EPS or rect[2] > w + CHECK_EPS or rect[3] > h + CHECK_EPS:
                failures.append(f"rect fuera del envelope: {rep} {rect}")
            if rect[2] - rect[0] <= EPS or rect[3] - rect[1] <= EPS:
                failures.append(f"rect degenerado: {rep} {rect}")
            by_floor.setdefault(room.z, []).append((rep, rect))

    for z, items in by_floor.items():
        for i, (ra, a) in enumerate(items):
            for rb, b in items[i + 1:]:
                if ra != rb and _rect_overlap(a, b):
                    failures.append(f"rects de cuartos se solapan en z={z}: {ra} {rb}")
                    break

    for wall in plan.walls:
        ww, hh = wall.x1 - wall.x0, wall.y1 - wall.y0
        if wall.x0 < -CHECK_EPS or wall.y0 < -CHECK_EPS or wall.x1 > w + CHECK_EPS or wall.y1 > h + CHECK_EPS:
            failures.append(f"muro fuera del envelope: {wall}")
        if ww <= EPS or hh <= EPS:
            failures.append(f"muro degenerado: {wall}")

    for z, room_items in by_floor.items():
        wall_rects = [(wall.x0, wall.y0, wall.x1, wall.y1) for wall in plan.walls if wall.z == z]
        for rep, rect in room_items:
            for wall_rect in wall_rects:
                if _rect_overlap(rect, wall_rect):
                    failures.append(f"cuarto y muro se solapan en z={z}: {rep} {wall_rect}")
                    break

    failures.extend(_coverage_failures(plan))
    return failures


def _coverage_failures(plan: FloorPlan) -> list[str]:
    failures: list[str] = []
    room_rects_by_z: dict[int, list[Rect]] = {}
    for room in plan.rooms.values():
        room_rects_by_z.setdefault(room.z, []).extend(room.rects)
    wall_rects_by_z: dict[int, list[Rect]] = {}
    for wall in plan.walls:
        wall_rects_by_z.setdefault(wall.z, []).append((wall.x0, wall.y0, wall.x1, wall.y1))
    door_rects_by_z: dict[int, list[Rect]] = {}
    for door in plan.doors:
        door_rects_by_z.setdefault(door.z, []).append(_door_rect(door))

    for z in sorted(set(room_rects_by_z) | set(wall_rects_by_z) | set(door_rects_by_z)):
        rects = room_rects_by_z.get(z, []) + wall_rects_by_z.get(z, []) + door_rects_by_z.get(z, [])
        if not rects:
            continue
        xs = sorted({0.0, plan.size_m[0]} | {v for rect in rects for v in (rect[0], rect[2])})
        ys = sorted({0.0, plan.size_m[1]} | {v for rect in rects for v in (rect[1], rect[3])})
        for x0, x1 in zip(xs, xs[1:]):
            if x1 - x0 <= CHECK_EPS:
                continue
            mx = (x0 + x1) / 2.0
            for y0, y1 in zip(ys, ys[1:]):
                if y1 - y0 <= CHECK_EPS:
                    continue
                my = (y0 + y1) / 2.0
                if not any(_point_in_rect(mx, my, rect) for rect in rects):
                    failures.append(f"coverage incompleta z={z} en ({_clean(mx)}, {_clean(my)})")
                    return failures
    return failures


def _mechanic_failures(source: Maze3D, plan: FloorPlan, merged: dict[Cell, Cell]) -> list[str]:
    failures: list[str] = []
    door_by_rep = _values_by_rep(source.doors, merged)
    gate_by_rep = _values_by_rep(source.gates, merged)

    for rep, key_id in door_by_rep.items():
        incident = [door for door in plan.doors if rep in door.edge]
        if not incident:
            failures.append(f"door sin puertas incidentes: {rep}")
        elif any(door.door_id != key_id for door in incident):
            failures.append(f"door_id no cubre todas las puertas de {rep}")
    for rep, flag in gate_by_rep.items():
        incident = [door for door in plan.doors if rep in door.edge]
        if not incident:
            failures.append(f"gate sin puertas incidentes: {rep}")
        elif any(door.gate_flag != flag for door in incident):
            failures.append(f"gate_flag no cubre todas las puertas de {rep}")

    for cell, key_id in source.keys.items():
        rep = merged.get(cell)
        if rep is None or not _mechanic_item_present(plan.keys, rep, key_id, plan):
            failures.append(f"key no preservada: {cell} id={key_id}")
    for cell, flag in source.switches.items():
        rep = merged.get(cell)
        matches = [sw for sw in plan.switches if sw.get("flag") == flag and _room_at_pos(plan, sw.get("pos")) == rep]
        if not matches:
            failures.append(f"switch no preservado: {cell} flag={flag}")
        elif rep in plan.rooms and not any(_near_room_wall(plan.rooms[rep], sw["pos"]) for sw in matches):
            failures.append(f"switch no esta pegado a muro: {cell}")

    expected_hazards = {(merged[cell], flag) for cell, flag in source.hazards.items() if cell in merged}
    got_hazards = {(item.get("rep"), item.get("flag")) for item in plan.hazard_rooms}
    if got_hazards != expected_hazards:
        failures.append(f"hazards distintos: faltan={sorted(expected_hazards - got_hazards)} sobran={sorted(got_hazards - expected_hazards)}")

    for marker, pos in ((PLAYER, plan.start), (GOAL, plan.goal)):
        cell = source.find(marker)
        if cell is None:
            continue
        rep = merged.get(cell)
        if pos is None or _room_at_pos(plan, pos) != rep:
            failures.append(f"{marker} no esta en su cuarto")

    failures.extend(_stair_failures(source, plan, merged))
    failures.extend(_portal_failures(source, plan, merged))
    return failures


def _mechanic_item_present(items: list[dict], rep: Cell, value: str, plan: FloorPlan) -> bool:
    return any(item.get("id") == value and _room_at_pos(plan, item.get("pos")) == rep for item in items)


def _near_room_wall(room: RoomSpec, pos: tuple[float, float, int]) -> bool:
    x, y, _z = pos
    return any(
        _point_in_rect(x, y, rect)
        and min(abs(x - rect[0]), abs(x - rect[2]), abs(y - rect[1]), abs(y - rect[3])) <= 0.26
        for rect in room.rects
    )


def _stair_failures(source: Maze3D, plan: FloorPlan, merged: dict[Cell, Cell]) -> list[str]:
    failures: list[str] = []
    expected: list[tuple[Cell, Cell]] = []
    for cell in sorted(source.connectors | source.ladders):
        top = (cell[0], cell[1], cell[2] + 1)
        if cell in merged and top in merged and merged[cell] != merged[top]:
            expected.append((merged[cell], merged[top]))
    got: list[tuple[Cell, Cell]] = []
    for a, b in plan.stairs:
        ra = _room_at_pos(plan, a)
        rb = _room_at_pos(plan, b)
        if ra is not None and rb is not None and ra != rb:
            got.append((ra, rb))
    for edge in expected:
        if edge not in got and (edge[1], edge[0]) not in got:
            failures.append(f"connector/stair no preservado: {edge}")
    return failures


def _portal_failures(source: Maze3D, plan: FloorPlan, merged: dict[Cell, Cell]) -> list[str]:
    expected = [(merged[src], merged[dst]) for src, dst in source.portals if src in merged and dst in merged and merged[src] != merged[dst]]
    got = []
    for a, b in plan.portals:
        ra = _room_at_pos(plan, a)
        rb = _room_at_pos(plan, b)
        if ra is not None and rb is not None and ra != rb:
            got.append((ra, rb))
    failures = []
    for edge in expected:
        if edge not in got:
            failures.append(f"portal no preservado: {edge}")
    extra = [edge for edge in got if edge not in expected]
    if extra:
        failures.append(f"portales extra: {extra}")
    return failures


def _door_seed(
    room: RoomSpec,
    door: DoorSpec,
    free: set[tuple[int, int]],
    center,
    clearance: float,
) -> tuple[int, int] | None:
    if not free:
        return None
    candidates: list[tuple[float, tuple[int, int]]] = []
    half = door.width / 2.0
    front = WALL_T + clearance
    for ix, iy in free:
        px, py = center(ix, iy)
        if (door.axis == "x" and door.x - half - CHECK_EPS <= px <= door.x + half + CHECK_EPS
                and abs(py - door.y) <= front):
            candidates.append((_dist2((px, py), (door.x, door.y)), (ix, iy)))
        elif (door.axis == "y" and door.y - half - CHECK_EPS <= py <= door.y + half + CHECK_EPS
                and abs(px - door.x) <= front):
            candidates.append((_dist2((px, py), (door.x, door.y)), (ix, iy)))
    return min(candidates)[1] if candidates else None
