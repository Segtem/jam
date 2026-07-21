"""Descriptores de craft de laberintos — medidos desde AFUERA sobre el JamEnv.

Cada descriptor es una DIMENSIÓN del espacio de comportamiento que la emergencia llena
(no una métrica a maximizar). El KB de craft de mazes ("un buen laberinto tiene decisiones,
callejones, un camino largo no trivial") se vuelve aquí MEDIBLE y agnóstico de contenido:

  - solution_length  largo del camino óptimo a la meta (BFS sobre el forward model).
  - branching        densidad de cruces (celdas con ≥3 salidas) = densidad de DECISIONES.
  - dead_end_density densidad de callejones (celdas con 1 sola salida) = trampas/exploración.
  - openness         proporción de celdas transitables = pasillo cerrado vs sala abierta.
  - solvable         GATE de winnability: el oráculo formal de Capa 0 (None = presupuesto excedido).

solution_length × branching × dead_end_density definen los NICHOS del archivo MAP-Elites.
"""
from __future__ import annotations

from typing import Any

from src.gameenv.metrics import reachability
from src.jamscript.env import JamEnv
from src.jamscript.parser import JamSpec

_DIRS = [(1, 0), (-1, 0), (0, 1), (0, -1)]


def _open_cells_and_degree(env: JamEnv) -> dict[tuple[int, int], int]:
    """Mapa celda-transitable → grado (cantidad de vecinos ortogonales transitables)."""
    open_cells = {
        (x, y)
        for y in range(env.height)
        for x in range(env.width)
        if (x, y) not in env._walls
    }
    return {
        (x, y): sum(((x + dx, y + dy) in open_cells) for dx, dy in _DIRS)
        for (x, y) in open_cells
    }


def maze_descriptors(spec: JamSpec, max_states: int = 50_000) -> dict[str, Any]:
    """Calcula los descriptores de un maze-spec. No muta nada (el env es efímero)."""
    env = JamEnv(spec)
    degree = _open_cells_and_degree(env)
    n_open = max(1, len(degree))

    # Excluir start/goal del conteo de callejones (no son trampas de diseño).
    endpoints = {(e["x"], e["y"]) for e in env._initial_entities
                 if e["role"] in ("player", "goal")}

    dead_ends = sum(1 for c, d in degree.items() if d == 1 and c not in endpoints)
    junctions = sum(1 for d in degree.values() if d >= 3)

    reach = reachability(env, max_states=max_states)

    return {
        "solution_length":  reach["optimal_steps"],          # None si no solvable
        "solvable":         reach["solvable"],                # True/False/None
        "branching":        round(junctions / n_open, 4),
        "dead_end_density": round(dead_ends / n_open, 4),
        "openness":         round(len(degree) / (env.width * env.height), 4),
        "open_cells":       len(degree),
        "junctions":        junctions,
        "dead_ends":        dead_ends,
        "states_explored":  reach["states_explored"],
        "dims":             [env.width, env.height],
    }
