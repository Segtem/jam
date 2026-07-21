"""Placer PROGRAM-AWARE: tipa un laberinto para satisfacer el programa de un espacio (las abstracciones
de sentido: circulation/adjacent/forbidden/access_depth/ratio/zones), en vez de tirar tipos al azar.

Sigue siendo generador-no-confiable + oráculo-exacto ([[esencia-norte-verificador]]): el placer PROPONE
(es falible, usa semillas), y `program_satisfied` DISPONE. La diferencia con el tipado aleatorio es que
el placer ENTIENDE la estructura — arma una espina de circulación que domina todas las celdas, mide la
profundidad desde la entrada, y coloca cada sala donde el programa la quiere (lo profundo profundo, la
enfermería pegada a una sala, los baños proporcionales). Así el oráculo acepta seguido, no 1 en 1000.

`place` devuelve el tipado de UN seed; `generate` prueba N seeds y se queda con los que el oráculo valida.
V1: un solo piso (z de la entrada).
"""

from __future__ import annotations

import math
import random
from collections import Counter, deque
from typing import Any

from src.mazes.maze3d import PLAYER, Maze3D

Cell = tuple[int, int, int]
_DIRS = ((1, 0, 0), (-1, 0, 0), (0, 1, 0), (0, -1, 0))


def _neighbors(c: Cell) -> list[Cell]:
    """Vecinos HORIZONTALES (mismo piso). El oráculo mide adyacencia/zonas por-piso (`_source_adjacent`,
    mismo z), así que la preferencia de pegado y la fuga de zona usan estos."""
    return [(c[0] + dx, c[1] + dy, c[2] + dz) for dx, dy, dz in _DIRS]


def _graph_neighbors(maze: Maze3D, c: Cell, cells: set[Cell]) -> list[Cell]:
    """Vecinos en el GRAFO real del laberinto: horizontal + verticales por escaleras/conectores. Con esto
    la profundidad y la conectividad de circulación SUBEN de piso (multi-piso)."""
    return [nb for nb in maze.neighbors(c) if nb in cells]


def _stair_cells(maze: Maze3D) -> set[Cell]:
    """Celdas OCUPADAS por circulación vertical (conectores, shafts de escalera, escaleras trepables). La
    escalera es un ANULADOR de espacio: donde hay escalera SOLO puede haber escalera — nunca una sala.
    Estas celdas quedan reservadas a circulación (vertical) y ni el placer ni el repair las pisan."""
    s: set[Cell] = set(getattr(maze, "connectors", set())) | set(getattr(maze, "ladders", set()))
    s |= set(getattr(maze, "stairs", {}))
    shafts = getattr(maze, "stair_shafts", None)
    if callable(shafts):
        s |= set(shafts())
    return s


def _depths(maze: Maze3D, cells: set[Cell], start: Cell) -> dict[Cell, int]:
    """Profundidad en SALTOS de celda desde `start` sobre el grafo real (cruza pisos por escaleras)."""
    depth = {start: 0}
    dq = deque([start])
    while dq:
        c = dq.popleft()
        for nb in _graph_neighbors(maze, c, cells):
            if nb not in depth:
                depth[nb] = depth[c] + 1
                dq.append(nb)
    return depth


def _connected_dominating_corridors(maze: Maze3D, cells: set[Cell], entrance: Cell,
                                    rng: random.Random) -> set[Cell]:
    """Espina de circulación: conjunto CONEXO (por el grafo real, sube de piso) que DOMINA todas las celdas
    (cada celda es corridor o toca uno HORIZONTALMENTE — como lo mide el oráculo). Greedy desde la entrada:
    agrega la celda-frontera que cubre más celdas sin cubrir."""
    def covers(c: Cell) -> set[Cell]:                   # dominación = toque HORIZONTAL (mismo piso)
        return {c} | {nb for nb in _neighbors(c) if nb in cells}
    corridor = {entrance}
    covered = covers(entrance)
    while covered != cells:
        # la circulación crece por el grafo REAL (puede trepar una escalera para dominar el piso de arriba)
        frontier = {nb for c in corridor for nb in _graph_neighbors(maze, c, cells) if nb not in corridor}
        if not frontier:
            break
        best = max(sorted(frontier, key=lambda c: rng.random()), key=lambda c: len(covers(c) - covered))
        corridor.add(best)
        covered |= covers(best)
    corridor.discard(entrance)                          # la entrada tiene su propio tipo
    return corridor


def _demand(program: Any) -> Counter:
    """Cuántas salas de cada tipo hay que colocar: lo requerido, subido por los ratios."""
    dem = Counter(program.required)
    for served, per, n in getattr(program, "ratio", ()):
        need = math.ceil(dem.get(per, 0) / n) if n > 0 else 0
        if dem.get(served, 0) < need:
            dem[served] = need
    return dem


def place(maze: Maze3D, program: Any, seed: int) -> dict[Cell, str] | None:
    """Tipa el laberinto para satisfacer `program`. Devuelve celda→tipo, o None si no entra la demanda."""
    rng = random.Random(seed)
    entrance = maze.find(PLAYER)
    if entrance is None:
        return None
    cells = set(maze.open_cells())                       # TODOS los pisos (multi-piso)
    cells.add(entrance)
    depth = _depths(maze, cells, entrance)

    stairs = _stair_cells(maze) & cells                  # anuladores de espacio: solo circulación vertical
    corridors = _connected_dominating_corridors(maze, cells, entrance, rng)
    rooms = [c for c in cells if c not in corridors and c != entrance and c not in stairs]
    rng.shuffle(rooms)
    rooms.sort(key=lambda c: depth.get(c, 0), reverse=True)   # profundos primero

    types: dict[Cell, str] = {entrance: "entrance"}
    for c in corridors:
        types[c] = "corridor"
    for c in stairs:                                     # la escalera reclama su celda: nunca una sala
        types[c] = "corridor"

    dem = _demand(program)
    dem.pop("entrance", None)                            # la entrada ya está
    access = dict(getattr(program, "access_depth", {}))
    # de qué tipos debe estar pegada cada sala (adyacencia simétrica: cualquiera puede ser el ancla)
    partners: dict[str, set[str]] = {}
    for a, b in getattr(program, "adjacent", ()):
        partners.setdefault(a, set()).add(b)
        partners.setdefault(b, set()).add(a)
    type_zone = {tt: z for z, tps in getattr(program, "zones", {}).items() for tt in tps}

    # colocar por profundidad: los tipos que EXIGEN estar profundos, en las celdas más profundas primero
    by_depth_need = sorted(dem, key=lambda t: access.get(t, 0), reverse=True)
    for t in by_depth_need:
        need = dem[t]
        min_d = access.get(t, 0)
        want = partners.get(t, set())
        anchors = [c for c, tt in types.items() if tt in want]   # partners YA colocados
        my_zone = type_zone.get(t)
        candidates = [c for c in rooms if c not in types and depth.get(c, 0) >= min_d]

        def _leaks(c: Cell) -> int:                      # ¿pegar acá crea fuga de zona?
            if my_zone is None:
                return 0
            return 1 if any(type_zone.get(types.get(nb)) not in (None, my_zone)
                            for nb in _neighbors(c)) else 0

        # preferir: pegado a un compañero de adyacencia, y SIN crear fuga de zona
        candidates.sort(key=lambda c: (0 if any(nb in anchors for nb in _neighbors(c)) else 1,
                                       _leaks(c), rng.random()))
        placed = 0
        for c in candidates:
            if placed >= need:
                break
            types[c] = t
            placed += 1
        if placed < need:
            return None                                  # el laberinto no aloja esta demanda

    # relleno: las salas sin tipo pasan a corridor (extiende la circulación, siempre válido)
    for c in rooms:
        types.setdefault(c, "corridor")
    return _repair(maze, program, types, rng, program.space)


_VIOLATION_KEYS = ("adjacency_missing", "isolated", "forbidden_present",
                   "too_shallow", "ratio_unmet", "zone_leak", "missing", "unreachable")


def _violations(res: dict) -> int:
    return sum(len(res[k]) for k in _VIOLATION_KEYS if res.get(k))


def _repair(maze: Maze3D, program: Any, types: dict[Cell, str], rng: random.Random,
            space: str, iters: int | None = None) -> dict[Cell, str]:
    """Búsqueda local por SWAPS: intercambia el tipo de dos celdas (preserva los conteos → required/ratio
    quedan intactos) para bajar las violaciones que reporta el oráculo. El greedy acierta los conteos; esto
    reacomoda el DÓNDE (pega los pares de adyacencia, separa las zonas). Hill-climb con mesetas planas.
    El presupuesto ESCALA con el problema (más celdas / más pares = espacio de búsqueda mayor)."""
    from src.mazes.pcg import expand, parse_pcg, program_satisfied

    entrance = maze.find(PLAYER)
    locked = _stair_cells(maze) | {entrance}             # escaleras y entrada no se intercambian
    movable = [c for c in types if c not in locked]

    def score(t: dict[Cell, str]) -> int:
        res = program_satisfied(expand(maze, parse_pcg(_to_pcg_text(t, space))), program)
        return 0 if res["ok"] else _violations(res)

    if iters is None:                                    # presupuesto proporcional al tamaño del problema
        iters = max(400, 60 * len(movable))

    cur = dict(types)
    cur_s = score(cur)
    best, best_s = dict(cur), cur_s
    if best_s == 0 or len(movable) < 2:
        return best
    for _ in range(iters):
        a, b = rng.sample(movable, 2)
        if cur[a] == cur[b]:
            continue
        cur[a], cur[b] = cur[b], cur[a]
        s = score(cur)
        if s <= cur_s:                                   # acepta iguales (escapa mesetas) y mejoras
            cur_s = s
            if s < best_s:
                best, best_s = dict(cur), s
                if best_s == 0:
                    return best
        else:
            cur[a], cur[b] = cur[b], cur[a]              # revierte el empeoramiento
    return best


def _to_pcg_text(types: dict[Cell, str], space: str) -> str:
    lines = ["@room size 2..2", f"@space {space}"]
    for (x, y, z), t in sorted(types.items()):
        lines.append(f"@room_type {x},{y},{z} {t}")
    return "\n".join(lines) + "\n"


def generate(maze: Maze3D, program: Any, seeds, *, space: str | None = None) -> dict[str, Any]:
    """Placer + oráculo: prueba N seeds, se queda con los tipados que `program_satisfied` VALIDA."""
    from src.mazes.pcg import expand, parse_pcg, program_satisfied
    kept: list[dict[Cell, str]] = []
    tried = 0
    sp = space or program.space
    for seed in seeds:
        tried += 1
        types = place(maze, program, seed)
        if types is None:
            continue
        content = expand(maze, parse_pcg(_to_pcg_text(types, sp)))
        if program_satisfied(content, program)["ok"]:
            kept.append(types)
    return {"kept": kept, "tried": tried, "n_kept": len(kept)}
