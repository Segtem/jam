"""Keystone del dashboard reframeado (jam api): el loop PROGRAMA → GENERADOR → VEREDICTO, en un solo
llamado. Dado un programa de espacio (las abstracciones de sentido), un esqueleto de laberinto, y un
generador (el placer procedural o, más adelante, un LLM), corre y devuelve por cada semilla: el veredicto
DESGLOSADO POR ABSTRACCIÓN (no un ok/no binario) y la planta tipada para previsualizar.

La UI se organiza alrededor de esta estructura: columna PROGRAMA (edita las abstracciones), columna
GENERADOR (elige y corre), columna VEREDICTO (por qué pasa o falla, regla por regla), y el PREVIEW abajo.
"""

from __future__ import annotations

from typing import Any

from oraculo.mazes.maze3d import Maze3D
from oraculo.mazes.pcg import SpaceProgram, expand, parse_pcg, program_satisfied
from oraculo.mazes.pcg_vocab import space_program_for
from oraculo.mazes.space_placer import _depths, _stair_cells, _to_pcg_text, place

# Cada abstracción: (campo en SpaceProgram, clave de violación en el reporte, etiqueta, glosa).
# El orden es el del panel VEREDICTO.
_ABSTRACTIONS = [
    ("required", "missing", "Cantidades", "cada tipo de sala aparece las veces mínimas"),
    ("adjacent", "adjacency_missing", "Adyacencia", "los pares que deben tocarse, se tocan"),
    ("circulation", "isolated", "Circulación", "toda sala toca un pasillo (nada sellado)"),
    ("forbidden", "forbidden_present", "Prohibiciones", "los pares vetados no se pegan"),
    ("access_depth", "too_shallow", "Profundidad", "lo privado, lejos de la entrada"),
    ("ratio", "ratio_unmet", "Proporción", "los conteos guardan la relación pedida"),
    ("zones", "zone_leak", "Zonas", "las alas distintas no se mezclan directo"),
]

_DEFAULT_SKELETON = ["########", "#P.....#", "#......#", "#.....G#", "########"]


def _rect_floor(w: int, h: int, *, player=False, goal=False, stair=None) -> str:
    rows = []
    for y in range(h):
        rows.append("".join("#" if (x == 0 or y == 0 or x == w - 1 or y == h - 1) else "." for x in range(w)))
    grid = [list(r) for r in rows]
    if player:
        grid[1][1] = "P"
    if goal:
        grid[h - 2][w - 2] = "G"
    if stair:
        grid[stair[1]][stair[0]] = "H"
    return ["".join(r) for r in grid]


# PRESETS: (esqueleto, programa) nombrados. El "hospital de verdad" — 2 pisos, 13 tipos, las 7 abstracciones
# incluida la profundidad vertical (el quirófano profundo cruzando la escalera). El generador lo fabrica y el
# oráculo lo verifica igual que a la cajita chica; es el mismo loop, a escala real.
def _hospital_grande():
    w, h = 11, 7
    skel = [_rect_floor(w, h, player=True, stair=(w - 2, h - 2)),
            _rect_floor(w, h, goal=True, stair=(w - 2, h - 2))]
    program = {
        "space": "hospital",
        "required": {"entrance": 1, "reception": 1, "waiting_room": 2, "triage": 1, "nurse_station": 2,
                     "ward": 15, "exam_room": 6, "operating_room": 1, "pharmacy": 1, "lab": 1,
                     "restroom": 5, "office": 3, "storage": 2},
        "adjacent": [["nurse_station", "ward"], ["waiting_room", "reception"], ["reception", "entrance"],
                     ["triage", "waiting_room"], ["operating_room", "nurse_station"]],
        "circulation": ["corridor"],
        "forbidden": [["ward", "entrance"], ["operating_room", "entrance"]],
        "access_depth": {"ward": 3, "operating_room": 5},
        "ratio": [["restroom", "ward", 4]],
        "zones": {"clinica": ["ward", "nurse_station", "exam_room", "operating_room"],
                  "publica": ["waiting_room", "reception", "triage"],
                  "servicio": ["pharmacy", "lab", "storage"]},
    }
    return skel, program


PRESETS = {"hospital_grande": _hospital_grande}


def _resolve_program(space: str | None, program: dict | None) -> SpaceProgram:
    """El programa viene por NOMBRE canónico (pcg_vocab) o INLINE (dict con las abstracciones)."""
    if program:
        def tup(rows):
            return tuple(tuple(r) for r in rows) if rows else ()
        return SpaceProgram(
            space=program.get("space", space or "espacio"),
            required=dict(program.get("required", {})),
            adjacent=tup(program.get("adjacent")),
            circulation=tuple(program.get("circulation", ())),
            forbidden=tup(program.get("forbidden")),
            access_depth=dict(program.get("access_depth", {})),
            ratio=tup(program.get("ratio")),
            zones={k: tuple(v) for k, v in program.get("zones", {}).items()},
        )
    if space:
        return space_program_for(space)
    raise ValueError("hace falta 'space' (nombre canónico) o 'program' (inline)")


def _resolve_skeleton(skeleton: list[list[str]] | None) -> Maze3D:
    if not skeleton:
        return Maze3D.from_layers([_DEFAULT_SKELETON])
    return Maze3D.from_layers(skeleton)


def _declared(program: SpaceProgram, field: str) -> bool:
    """¿El programa DECLARA esta abstracción? (si no, no la mostramos en el veredicto)."""
    return bool(getattr(program, field, None))


def _verdict_rows(report: dict, program: SpaceProgram) -> list[dict[str, Any]]:
    """El reporte del oráculo → filas por abstracción DECLARADA: {key, label, ok, detail}."""
    rows = []
    for field, vkey, label, gloss in _ABSTRACTIONS:
        if field == "required" or _declared(program, field):
            viol = report.get(vkey)
            rows.append({"key": field, "label": label, "gloss": gloss,
                         "ok": not viol, "detail": viol or None})
    return rows


def _plan_view(maze: Maze3D, types: dict, program: SpaceProgram) -> dict[str, Any]:
    entrance = maze.find("P")
    depth = _depths(maze, set(maze.open_cells()) | {entrance}, entrance)
    stairs = _stair_cells(maze)
    cells = [{"x": x, "y": y, "z": z, "type": t, "depth": depth.get((x, y, z)),
              "stair": (x, y, z) in stairs}
             for (x, y, z), t in sorted(types.items())]
    floors = [["".join(row) for row in maze.floors[z]] for z in range(maze.n_floors)]
    return {"floors": floors, "n_floors": maze.n_floors, "cells": cells,
            "entrance": list(entrance)}


def _program_view(program: SpaceProgram) -> dict[str, Any]:
    return {"space": program.space, "required": dict(program.required),
            "adjacent": [list(p) for p in program.adjacent],
            "circulation": list(program.circulation),
            "forbidden": [list(p) for p in program.forbidden],
            "access_depth": dict(program.access_depth),
            "ratio": [list(r) for r in program.ratio],
            "zones": {k: list(v) for k, v in program.zones.items()}}


def studio_run(space: str | None = None, program: dict | None = None,
               skeleton: list[list[str]] | None = None,
               generator: str = "placer", seeds: int = 8,
               preset: str | None = None) -> dict[str, Any]:
    """Corre el loop y devuelve todo lo que la UI necesita: el programa resuelto, y por cada semilla el
    veredicto por abstracción + la planta. `generator` hoy = 'placer' (el LLM entra por el harness aparte).
    `preset` (ej. 'hospital_grande') trae un esqueleto + programa a escala real de una sola pieza."""
    if preset:
        if preset not in PRESETS:
            raise ValueError(f"preset desconocido: {preset!r} (hay: {sorted(PRESETS)})")
        skel, program = PRESETS[preset]()
        skeleton = skeleton or skel
    prog = _resolve_program(space, program)
    maze = _resolve_skeleton(skeleton)
    results = []
    for seed in range(max(1, seeds)):
        types = place(maze, prog, seed)
        if types is None:
            results.append({"seed": seed, "ok": False,
                            "reason": "el esqueleto no aloja la demanda de salas"})
            continue
        report = program_satisfied(
            expand(maze, parse_pcg(_to_pcg_text(types, prog.space))), prog)
        results.append({"seed": seed, "ok": report["ok"],
                        "verdict": _verdict_rows(report, prog),
                        "plan": _plan_view(maze, types, prog)})
    return {"space": prog.space, "program": _program_view(prog),
            "generator": generator, "seeds": max(1, seeds),
            "skeleton": [list(maze.floors[z]) for z in range(maze.n_floors)],  # para regenerar sin perderlo
            "n_valid": sum(1 for r in results if r.get("ok")),
            "results": results}
