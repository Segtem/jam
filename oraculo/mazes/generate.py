"""Operador de variación procedural para mazes — recursive backtracker + braiding.

Es el operador de VARIACIÓN del loop QD (variación → selección → archivo). Procedural a
propósito: el piloto valida la maquinaria (descriptores + archivo) sobre mazes reales sin
depender del LLM. Es PLUGGABLE — la creación libre del LLM (anti-inyección) lo reemplaza
después, conservando el mismo contrato `(params) → layout`.

Parámetros que barren el espacio de comportamiento:
  - cells_w/cells_h  tamaño en celdas → escala el largo de solución y las celdas abiertas.
  - braid            [0,1] prob. de abrir cada callejón → sube branching/openness, baja dead-ends.
  - goal             'farthest' (camino largo) | 'random'.
"""
from __future__ import annotations

import random
from collections import deque

WALL, OPEN, PLAYER, GOAL = "#", ".", "P", "G"
_DIRS = [(1, 0), (-1, 0), (0, 1), (0, -1)]


def generate_maze(cells_w: int = 6, cells_h: int = 6, braid: float = 0.0,
                  goal: str = "farthest", seed: int | None = None) -> list[str]:
    """Genera un maze como lista de filas de chars. Grid = (2*cells+1) en cada eje."""
    rng = random.Random(seed)
    W, H = 2 * cells_w + 1, 2 * cells_h + 1
    grid = [[WALL] * W for _ in range(H)]

    def cell_to_grid(cx: int, cy: int) -> tuple[int, int]:
        return 2 * cx + 1, 2 * cy + 1

    # ── recursive backtracker (DFS con pila) ──────────────────────────────────
    visited: set[tuple[int, int]] = set()
    stack = [(0, 0)]
    visited.add((0, 0))
    gx, gy = cell_to_grid(0, 0)
    grid[gy][gx] = OPEN
    while stack:
        cx, cy = stack[-1]
        nbrs = [(cx + dx, cy + dy) for dx, dy in _DIRS
                if 0 <= cx + dx < cells_w and 0 <= cy + dy < cells_h
                and (cx + dx, cy + dy) not in visited]
        if not nbrs:
            stack.pop()
            continue
        nx, ny = rng.choice(nbrs)
        # abrir la pared entre (cx,cy) y (nx,ny)
        gx1, gy1 = cell_to_grid(cx, cy)
        gx2, gy2 = cell_to_grid(nx, ny)
        grid[(gy1 + gy2) // 2][(gx1 + gx2) // 2] = OPEN
        grid[gy2][gx2] = OPEN
        visited.add((nx, ny))
        stack.append((nx, ny))

    # ── braiding: abrir callejones para crear bucles ─────────────────────────
    if braid > 0:
        for cy in range(cells_h):
            for cx in range(cells_w):
                gx, gy = cell_to_grid(cx, cy)
                exits = [(dx, dy) for dx, dy in _DIRS if grid[gy + dy][gx + dx] == OPEN]
                if len(exits) <= 1 and rng.random() < braid:
                    # romper una pared cerrada hacia una celda vecina válida
                    walls = [(dx, dy) for dx, dy in _DIRS
                             if grid[gy + dy][gx + dx] == WALL
                             and 0 <= gx + 2 * dx < W and 0 <= gy + 2 * dy < H]
                    if walls:
                        dx, dy = rng.choice(walls)
                        grid[gy + dy][gx + dx] = OPEN

    # ── colocar player y goal ─────────────────────────────────────────────────
    start = cell_to_grid(0, 0)
    target = _farthest_open(grid, start) if goal == "farthest" else _random_open(grid, rng, start)
    sx, sy = start
    tx, ty = target
    grid[sy][sx] = PLAYER
    grid[ty][tx] = GOAL
    return ["".join(row) for row in grid]


def _open_neighbors(grid: list[list[str]], x: int, y: int):
    H, W = len(grid), len(grid[0])
    for dx, dy in _DIRS:
        nx, ny = x + dx, y + dy
        if 0 <= nx < W and 0 <= ny < H and grid[ny][nx] != WALL:
            yield nx, ny


def _farthest_open(grid: list[list[str]], start: tuple[int, int]) -> tuple[int, int]:
    """BFS desde start → la celda transitable más lejana (maximiza el largo de solución)."""
    seen = {start}
    q = deque([start])
    far = start
    while q:
        x, y = q.popleft()
        far = (x, y)
        for nx, ny in _open_neighbors(grid, x, y):
            if (nx, ny) not in seen:
                seen.add((nx, ny))
                q.append((nx, ny))
    return far


def _random_open(grid: list[list[str]], rng: random.Random,
                 start: tuple[int, int]) -> tuple[int, int]:
    cells = [(x, y) for y in range(len(grid)) for x in range(len(grid[0]))
             if grid[y][x] != WALL and (x, y) != start]
    return rng.choice(cells) if cells else start
