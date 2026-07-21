"""Descriptores LIMINALES — la dimensión "Backrooms-ness" medida desde AFUERA sobre la estructura.

Principio anti-inyección (ver descriptors.py): no inyectamos estética liminal; MEDIMOS qué tan liminal
ES un espacio ya verificado por Capa 0. Cada descriptor es una DIMENSIÓN de comportamiento (no una
métrica a maximizar) que la emergencia puede llenar, agnóstica de contenido:

  - room_ness   fracción de celdas transitables "abiertas" (grado ≥3) = salas vs pasillos.
  - sightline   línea de visión recta más larga (corrida de celdas transitables en fila o columna).
  - sameness    repetitividad del tejido = 1 - (patrones-3x3-distintos / celdas) → falta de hitos.

room_ness × sightline × sameness describen el "liminal-ness": un Backrooms canónico es ABIERTO (salas,
no pasillos), con SIGHTLINES largas, y MUY REPETITIVO (sin hitos para orientarse → perderse). Son
ortogonales a los descriptores de craft de `descriptors.py` (que miden el laberinto qua laberinto).
"""
from __future__ import annotations

from typing import Any

from src.jamscript.env import JamEnv
from src.jamscript.parser import JamSpec

_DIRS = [(1, 0), (-1, 0), (0, 1), (0, -1)]


def _open_cells(env: JamEnv) -> set[tuple[int, int]]:
    """Celdas transitables (todo lo que no es pared; las entidades NO bloquean → cuentan)."""
    return {(x, y)
            for y in range(env.height)
            for x in range(env.width)
            if (x, y) not in env._walls}


def _degree(open_cells: set[tuple[int, int]]) -> dict[tuple[int, int], int]:
    """Celda transitable → cantidad de vecinos ortogonales transitables (0–4)."""
    return {(x, y): sum(((x + dx, y + dy) in open_cells) for dx, dy in _DIRS)
            for (x, y) in open_cells}


def _longest_sightline(env: JamEnv, open_cells: set[tuple[int, int]]) -> int:
    """Corrida máxima de celdas transitables consecutivas en alguna fila o columna.

    Es la línea de visión recta más larga: los espacios liminales tienen sightlines largas
    (pasillos/salas que se pierden en la distancia). Mide en celdas."""
    best = 0
    for y in range(env.height):              # filas
        run = 0
        for x in range(env.width):
            run = run + 1 if (x, y) in open_cells else 0
            best = max(best, run)
    for x in range(env.width):               # columnas
        run = 0
        for y in range(env.height):
            run = run + 1 if (x, y) in open_cells else 0
            best = max(best, run)
    return best


def _sameness(open_cells: set[tuple[int, int]]) -> float:
    """Repetitividad del tejido: 1 - (vecindarios 3×3 distintos / celdas transitables).

    Para cada celda transitable se toma su parche 3×3 (transitable=0 / pared o fuera-de-grilla=1).
    Pocos parches distintos = tejido muy uniforme = sin hitos para orientarse → alta "lostness".
    1.0 = todas las celdas idénticas; ~0 = cada celda con un contexto único."""
    patterns = [
        tuple(0 if (x + dx, y + dy) in open_cells else 1
              for dy in (-1, 0, 1) for dx in (-1, 0, 1))
        for (x, y) in open_cells
    ]
    if not patterns:
        return 0.0
    return round(1.0 - len(set(patterns)) / len(patterns), 4)


def liminal_descriptors(spec: JamSpec) -> dict[str, Any]:
    """Calcula los descriptores liminales de un maze-spec. No muta nada (el env es efímero)."""
    env = JamEnv(spec)
    open_cells = _open_cells(env)
    n_open = max(1, len(open_cells))
    degree = _degree(open_cells)
    room_cells = sum(1 for d in degree.values() if d >= 3)
    return {
        "room_ness":  round(room_cells / n_open, 4),
        "sightline":  _longest_sightline(env, open_cells),
        "sameness":   _sameness(open_cells),
        "open_cells": len(open_cells),
        "dims":       [env.width, env.height],
    }
