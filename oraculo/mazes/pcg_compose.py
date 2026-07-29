"""Composición de programas JamPCG — el GENERADOR de programas default, motor-agnóstico.

`auto_program` propone un programa de vestido para un esqueleto. Es un generador NO-confiable
como cualquier otro: propone; `materialize`/`reverify`/`program_satisfied` disponen. Vivía en el
router FastAPI (`src/api/routers/pcg.py`) — mudado acá para que TODO receptor (la Fundición
incluida) pueda componer el mismo default sin arrastrar el framework web.

TIPADO CON SENTIDO GEOMÉTRICO (mejora de calidad 2026-07-06): antes los `required` iban a las
primeras celdas y TODO el resto era corridor/hallway (una "casa" salía 84% pasillo). Ahora:
- la CIRCULACIÓN es sólo la ESPINA: las celdas del camino BFS P→G (el oráculo como INSUMO del
  generador — la ruta que el jugador VA a caminar es el pasillo del edificio);
- `entrance` va donde está P (se ENTRA por el arranque);
- los `required` y las adyacencias canónicas van COLGADOS de la espina (cuartos con vano al
  pasillo, como un edificio real: double-loaded corridor);
- el resto se llena con VARIEDAD ponderada por tipo (un hospital es mayormente wards y consultas,
  no pasillo) — determinista por seed.
El oráculo sigue disponiendo: si el tipado no satisface el programa del espacio, se descarta."""

from __future__ import annotations

import random
from collections import Counter

from oraculo.mazes.maze3d import GOAL, PLAYER, Maze3D, solve_3d
from oraculo.mazes.pcg_vocab import SPACES

NBRS = [(1, 0, 0), (-1, 0, 0), (0, 1, 0), (0, -1, 0)]

# tipos de CIRCULACIÓN (la espina) — el resto de los tipos son cuartos funcionales
_CIRCULATION = ("corridor", "hallway")

# pesos de VARIEDAD para el relleno (global, filtrado a los room_types de cada espacio): los tipos
# "firma" que se repiten en el edificio real pesan más (un hospital tiene MUCHOS wards; una casa,
# dormitorios), los de servicio aparecen pero no dominan. El gate `program_satisfied` sólo exige
# mínimos — esto es la DISTRIBUCIÓN del generador, no una regla del oráculo.
_VARIETY_WEIGHTS: dict[str, int] = {
    "ward": 4, "exam_room": 2, "waiting_room": 1, "operating_room": 1, "nurse_station": 1,
    "classroom": 4, "laboratory": 1, "library": 1, "cafeteria": 1, "gym": 1,
    "cubicle": 4, "meeting_room": 1, "break_room": 1, "server_room": 1, "reception": 1,
    "bedroom": 3, "living_room": 2, "kitchen": 1, "bathroom": 1, "garage": 1, "closet": 1,
    "office": 1, "storage": 1, "restroom": 1,
}

# TOPES de repetición: los tipos que un edificio real tiene UNA vez (o pocas) no deben salir
# sorteados N veces (una casa con 3 cocinas no se lee casa). Sin entrada = sin tope.
_MAX_REPEAT: dict[str, int] = {
    "kitchen": 1, "living_room": 1, "garage": 1, "entrance": 1, "reception": 1,
    "cafeteria": 1, "gym": 1, "library": 1, "server_room": 1, "break_room": 1,
    "operating_room": 2, "nurse_station": 2, "laboratory": 2, "bathroom": 2, "restroom": 2,
    "meeting_room": 2, "waiting_room": 2, "storage": 2, "closet": 2,
}

# GRADIENTE público→privado (A Pattern Language / informe de legibilidad 2026-07-06): lo público
# recibe cerca de la entrada; lo íntimo/crítico va a la profundidad. El generador lo usa como
# AFINIDAD (no regla dura): rompe el "quirófano pegado al lobby".
_PUBLIC = {"waiting_room", "reception", "cafeteria", "living_room", "kitchen", "break_room",
           "library", "gym", "entrance"}
_PRIVATE = {"ward", "operating_room", "server_room", "bedroom", "storage", "closet",
            "laboratory", "garage"}

# deco legacy si el espacio no declara `SpaceType.deco` (paridad con el comportamiento anterior)
_LEGACY_DECO = ("light_panel", "pipe", "cable_tray", "sign", "duct", "vent", "chair", "plant")


def leaf_cells(maze: Maze3D) -> list[tuple[int, int, int]]:
    """Celdas-HOJA (grado ≤1 en el grafo de nav): los dead-ends donde un prop BLOQUEANTE es seguro
    (no puede tapar una ruta de paso). El resto queda para props decorativos por densidad."""
    opens = set(maze.open_cells())
    leaves = []
    for (x, y, z) in opens:
        deg = sum(1 for dx, dy, dz in NBRS if (x + dx, y + dy, z + dz) in opens)
        if deg <= 1:
            leaves.append((x, y, z))
    return sorted(leaves)


def _depths(maze: Maze3D, start: tuple[int, int, int]) -> dict[tuple[int, int, int], int]:
    """Profundidad BFS de cada celda abierta desde `start` (in-plane + aristas verticales de
    conectores/escaleras + portales) — la métrica del gradiente público→privado."""
    opens = set(maze.open_cells())
    if start not in opens:
        return {}
    vertical = set(maze.connectors) | set(maze.ladders)
    portal = {}
    for a, b in maze.portals:
        portal.setdefault(a, []).append(b)
        portal.setdefault(b, []).append(a)
    depth = {start: 0}
    frontier = [start]
    while frontier:
        nxt = []
        for c in frontier:
            nbrs = [(c[0] + dx, c[1] + dy, c[2]) for dx, dy, _dz in NBRS]
            if c in vertical:
                nbrs.append((c[0], c[1], c[2] + 1))
            if (c[0], c[1], c[2] - 1) in vertical:
                nbrs.append((c[0], c[1], c[2] - 1))
            nbrs += portal.get(c, [])
            for nb in nbrs:
                if nb in opens and nb not in depth:
                    depth[nb] = depth[c] + 1
                    nxt.append(nb)
        frontier = nxt
    return depth


def _spine(maze: Maze3D) -> list[tuple[int, int, int]]:
    """La ESPINA de circulación: el camino BFS P→G del oráculo (respeta llaves/puertas/canales).
    Sin P/G o sin solución → espina vacía (todo el esqueleto son cuartos)."""
    if maze.find(PLAYER) is None or maze.find(GOAL) is None:
        return []
    sol = solve_3d(maze)
    return [tuple(c) for c in sol["path"]] if sol["solvable"] else []


def assign_room_types(maze: Maze3D, space: str, seed: int = 0
                      ) -> tuple[dict[tuple[int, int, int], str], set[tuple[int, int, int]]]:
    """El TIPADO geométrico como función reutilizable: (tipo por celda abierta, espina de
    circulación). La consumen `auto_program` (que lo emite como texto de programa para el
    pipeline de inflado) y el modo EDIFICIO del dress (que tipa por nodo del grafo, sin pasar
    por el texto). Determinista dado `seed`."""
    st = SPACES[space]
    rng = random.Random(f"auto_program:{space}:{seed}")
    opens = sorted(maze.open_cells())
    open_set = set(opens)

    spine = set(_spine(maze)) & open_set
    filler = next((t for t in _CIRCULATION if t in st.room_types), st.room_types[0])
    assign: dict[tuple[int, int, int], str] = {}

    # 1) entrance: donde está P — se entra al edificio por el arranque del jugador
    start = maze.find(PLAYER)
    if "entrance" in st.room_types and start is not None and start in open_set:
        assign[start] = "entrance"

    # celdas de CUARTO (fuera de la espina), ordenadas canónicamente; la espina queda de pasillo
    room_cells = [c for c in opens if c not in spine and c not in assign]

    def next_free(cells) -> tuple[int, int, int] | None:
        return next((c for c in cells if c not in assign), None)

    # 2) adyacencias canónicas: cada par (a,b) ADYACENTE. Si uno del par ya existe (ej. entrance
    #    en P), el otro se CUELGA a su lado (no se duplica un tipo singular); si no, el par va en
    #    dos celdas vecinas, preferentemente fuera de la espina (cuartos que dan al pasillo)
    def hang_next_to(existing_type: str, other: str) -> bool:
        for a in sorted(c for c, t in assign.items() if t == existing_type):
            for dx, dy, _dz in NBRS:
                nb = (a[0] + dx, a[1] + dy, a[2])
                if nb in open_set and nb not in assign:
                    assign[nb] = other
                    return True
        return False

    for ta, tb in st.adjacencies:
        if (ta in assign.values() and hang_next_to(ta, tb)) or \
           (tb in assign.values() and hang_next_to(tb, ta)):
            continue
        placed = False
        for pool in (room_cells, opens):
            for c in pool:
                if c in assign:
                    continue
                for dx, dy, _dz in NBRS:
                    nb = (c[0] + dx, c[1] + dy, c[2])
                    if nb in open_set and nb not in assign:
                        assign[c], assign[nb] = ta, tb
                        placed = True
                        break
                if placed:
                    break
            if placed:
                break

    # 3) los required que falten (descontando lo puesto por entrance/adyacencia): en celdas de
    #    cuarto según el GRADIENTE (lo privado a la profundidad, lo público cerca de la entrada)
    depths = _depths(maze, start) if start is not None else {}
    depth_of = lambda c: depths.get(c, 0)

    def pick_cell(rt: str):
        cells = [c for c in room_cells if c not in assign] or [c for c in opens if c not in assign]
        if not cells:
            return None
        if rt in _PRIVATE:
            return max(cells, key=depth_of)
        if rt in _PUBLIC:
            return min(cells, key=depth_of)
        return cells[0]

    remaining = dict(st.required)
    for t in assign.values():
        if remaining.get(t, 0) > 0:
            remaining[t] -= 1
    for rt in (t for t, n in remaining.items() for _ in range(n)):
        c = pick_cell(rt)
        if c is None:
            break
        assign[c] = rt

    # 4) VARIEDAD: el resto de las celdas de cuarto se llena con tipos funcionales ponderados
    #    (no más "todo pasillo") respetando TOPES de repetición y GRADIENTE (afinidad ×3 cuando
    #    el tipo cae de su lado: privado en la mitad profunda, público en la cercana)
    counts = Counter(assign.values())
    pool = [t for t in st.room_types if t not in _CIRCULATION and t != "entrance"]
    free_cells = [c for c in room_cells if c not in assign]
    cut = sorted(depth_of(c) for c in free_cells)[len(free_cells) // 2] if free_cells else 0
    for c in free_cells:
        deep = depth_of(c) > cut
        avail = [t for t in pool if counts[t] < _MAX_REPEAT.get(t, 99)]
        if not avail:
            avail = pool or [filler]
        weights = [_VARIETY_WEIGHTS.get(t, 1) *
                   (3 if (deep and t in _PRIVATE) or (not deep and t in _PUBLIC) else 1)
                   for t in avail]
        pick = rng.choices(avail, weights=weights, k=1)[0]
        assign[c] = pick
        counts[pick] += 1
    # la espina (y cualquier hueco) queda como circulación
    for c in opens:
        assign.setdefault(c, filler)
    return assign, spine


def auto_program(maze: Maze3D, space: str, room_min: int, room_max: int,
                 avoid: set | None = None, seed: int = 0) -> str:
    """Auto-genera un programa JamPCG para `space` con tipado GEOMÉTRICO (ver docstring del
    módulo). Determinista dado `seed`. El generador PROPONE el tipado; `program_satisfied` lo
    verifica (mínimos + adyacencias + alcanzabilidad) — si no se pudo, el oráculo descarta.
    `avoid` se mantiene por compatibilidad (las recetas ya no ponen bloqueantes en paneles)."""
    st = SPACES[space]
    assign, _ = assign_room_types(maze, space, seed=seed)
    lines = [f"@room size {room_min}..{room_max}", f"@space {space}"]
    for (x, y, z) in sorted(maze.open_cells()):
        lines.append(f"@room_type {x},{y},{z} {assign[(x, y, z)]}")

    # 5) dressing por DENSIDAD: la deco propia del espacio (`SpaceType.deco`; fallback legacy),
    #    todos free (no tocan la nav que verificó el oráculo). El MOBILIARIO por cuarto lo ponen
    #    las recetas de `_furnish_rooms` (V3), gateadas por el oráculo.
    deco_pool = getattr(st, "deco", None) or _LEGACY_DECO
    deco = [p for p in deco_pool if p in st.props]
    for tag in deco[:6]:
        lines.append(f"@prop {tag} density 0.18 free")
    if "pipe_vertical" in st.props:                  # D3: columnas piso→techo, ralas
        lines.append("@prop pipe_vertical density 0.05 free")
    return "\n".join(lines)
