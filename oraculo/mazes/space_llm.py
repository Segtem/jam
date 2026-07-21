"""Camino 2 — el LLM escribe el DSL, el oráculo lo juzga.

La tesis del norte ([[esencia-norte-verificador]], [[no-injection-free-creation]]): el generador NO se
confía; se lo deja CREAR LIBRE y se lo mide DESDE AFUERA con un oráculo exacto. El placer procedural
(`space_placer`) es UN generador; acá el generador es un LLM que escribe el DSL de tipado a mano. El mismo
`program_satisfied` es el juez para los dos — así podemos COMPETIR generadores sin cambiar el verificador
(anti-Goodhart: nadie optimiza el juez, el juez está congelado).

Este módulo es el HARNESS, no un LLM: arma el prompt (laberinto + programa en palabras), parsea el DSL que
vuelve, y lo somete al oráculo. `propose_fn` es cualquier cosa que dado un prompt devuelva texto — un LLM
externo (ask-codex/ask-agy), este mismo Claude, o un stub de test. El loop es idéntico al del placer:
proponé N veces, quedate con lo que el oráculo VALIDA.
"""

from __future__ import annotations

import re
from typing import Any, Callable

from src.mazes.maze3d import PLAYER, Maze3D
from src.mazes.pcg import SpaceProgram, expand, parse_pcg, program_satisfied

Propose = Callable[[str], str]


def _ascii_floors(maze: Maze3D) -> str:
    out = []
    for z in range(maze.n_floors):
        out.append(f"piso z={z}:")
        for y, row in enumerate(maze.floors[z]):
            out.append("  " + "".join(row))
    return "\n".join(out)


def _rules_in_words(program: SpaceProgram) -> str:
    """El programa (las abstracciones) en lenguaje llano — lo que hace COHERENTE al edificio."""
    L: list[str] = []
    req = ", ".join(f"{n}× {t}" for t, n in program.required.items())
    L.append(f"- CANTIDADES mínimas: {req}.")
    if program.adjacent:
        L.append("- ADYACENCIA (deben tocarse, mismo piso): " +
                  "; ".join(f"{a}↔{b}" for a, b in program.adjacent) + ".")
    if program.circulation:
        L.append(f"- CIRCULACIÓN: los tipos {list(program.circulation)} son pasillo; TODA otra sala debe "
                 "tocar un pasillo (mismo piso). Armá una espina de pasillos que llegue a todo.")
    if program.forbidden:
        L.append("- PROHIBIDO pegar: " + "; ".join(f"{a}↔{b}" for a, b in program.forbidden) + ".")
    if program.access_depth:
        L.append("- PROFUNDIDAD mínima (saltos de sala desde la entrada, mismo piso): " +
                 "; ".join(f"{t}≥{d}" for t, d in program.access_depth.items()) +
                 " (lo privado, lejos de la puerta).")
    if program.ratio:
        L.append("- PROPORCIÓN: " + "; ".join(f"≥1 {s} cada {n} {p}" for s, p, n in program.ratio) + ".")
    if program.zones:
        z = "; ".join(f"{name}={list(ts)}" for name, ts in program.zones.items())
        L.append(f"- ZONAS (alas): {z}. Dos salas de zonas DISTINTAS no se pegan directo (media un pasillo).")
    return "\n".join(L)


def describe_task(maze: Maze3D, program: SpaceProgram) -> str:
    """Prompt para el generador: el laberinto, sus celdas abiertas, y el programa a satisfacer."""
    entrance = maze.find(PLAYER)
    cells = sorted(set(maze.open_cells()) | {entrance})
    to_type = [c for c in cells if c != entrance]
    cell_list = " ".join(f"{x},{y},{z}" for x, y, z in to_type)
    return f"""Sos un arquitecto. Tenés que TIPAR cada celda de un laberinto para construir un "{program.space}"
que tenga SENTIDO. No inventás el layout del laberinto (ya está); asignás qué es cada celda.

El laberinto (# muro, P entrada del jugador, G salida, . transitable, H escalera al piso de arriba):
{_ascii_floors(maze)}

La celda de la entrada {entrance} YA es de tipo "entrance" (no la tipes vos).
Tenés que asignar un tipo a CADA UNA de estas celdas abiertas (y solo a estas):
{cell_list}

El edificio tiene SENTIDO si cumple TODAS estas reglas:
{_rules_in_words(program)}

Los tipos de sala válidos son los que aparecen arriba, más "corridor" (pasillo) para lo que sea circulación
o sobrante. Coordenadas en x,y,z (z = piso). Celdas con manhattan==1 en el mismo piso están pegadas.

Respondé SOLO con el DSL, un `@room_type` por celda, en un bloque:
@room size 2..2
@space {program.space}
@room_type x,y,z tipo
... (una línea por cada celda listada)
"""


_RT = re.compile(r"@room_type\s+(-?\d+)\s*,\s*(-?\d+)\s*,\s*(-?\d+)\s+(\w+)")


def extract_dsl(text: str, space: str) -> str:
    """Rescata el DSL del texto del LLM (que puede venir con prosa/```). Reconstruye un bloque canónico."""
    lines = ["@room size 2..2", f"@space {space}"]
    for m in _RT.finditer(text):
        x, y, z, t = m.groups()
        lines.append(f"@room_type {x},{y},{z} {t}")
    return "\n".join(lines) + "\n"


def judge(maze: Maze3D, program: SpaceProgram, dsl_text: str) -> dict[str, Any]:
    """El juez: parsea el DSL propuesto y corre el oráculo exacto. Devuelve el reporte de violaciones.
    La entrada (celda del PLAYER) se FUERZA a "entrance" — el prompt le pide al LLM que no la tipe, así que
    el harness la re-inyecta (y si el LLM igual la tipó de otra cosa, mandan las reglas: la entrada es la
    entrada)."""
    from src.mazes.space_placer import _stair_cells

    dsl = extract_dsl(dsl_text, program.space)
    # invariantes que el harness FUERZA (no se los deja al generador): la entrada es la entrada, y la
    # escalera ANULA el espacio (donde hay escalera solo hay escalera — nunca una sala).
    forced: dict[tuple[int, int, int], str] = {}
    entrance = maze.find(PLAYER)
    if entrance is not None:
        forced[entrance] = "entrance"
    for c in _stair_cells(maze) & set(maze.open_cells()):
        forced[c] = "corridor"
    for (x, y, z), t in forced.items():
        dsl = re.sub(rf"(?m)^@room_type\s+{x}\s*,\s*{y}\s*,\s*{z}\s+\w+\s*$", "", dsl)
        dsl += f"@room_type {x},{y},{z} {t}\n"
    content = expand(maze, parse_pcg(dsl))
    return program_satisfied(content, program)


def llm_generate(maze: Maze3D, program: SpaceProgram, propose: Propose, n: int) -> dict[str, Any]:
    """Loop del norte con un LLM de generador: proponé N veces, quedate con lo que el oráculo VALIDA.
    Devuelve las propuestas válidas, todos los reportes (para auditar en qué falla el LLM), y la tasa."""
    prompt = describe_task(maze, program)
    kept: list[str] = []
    reports: list[dict[str, Any]] = []
    for _ in range(n):
        proposal = propose(prompt)
        report = judge(maze, program, proposal)
        reports.append(report)
        if report["ok"]:
            kept.append(proposal)
    return {"kept": kept, "reports": reports, "tried": n, "n_kept": len(kept), "prompt": prompt}
