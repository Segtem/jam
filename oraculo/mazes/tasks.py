"""Canal TAREAS-DAG (grounded) — el "qué hacer" del JamMap. Ver [[jampcg-dsl-direction]] / [[votv-idealizable-en-jamdsl]].

En VotV no se gana llegando a un punto: hay TAREAS (descargar la señal, recargar el generador, dormir) con
DEPENDENCIAS (sin energía no hay descarga). Eso es un DAG: tareas como nodos, dependencias como aristas. Este
canal las declara GROUNDED: cada tarea anclada a una CELDA REAL del espacio verificado (no texto suelto) —
`@task id at x,y,z [after dep1,dep2]`. El oráculo verifica lo que importa: ¿existe una caminata real que
complete todas las tareas respetando el DAG y VUELVA a la meta (la cama)? Un prop que tapa la consola, o un
orden imposible, se DESCARTA (la misma red de seguridad BFS de todo JamDSL).

Es la generalización de llave→puerta / switch→gate (dependencias de a pares) a CADENAS de objetivos declarables.
La narrativa (diferida) se colgará de acá: historias sobre tareas que EXISTEN en el juego verificado.
"""
from __future__ import annotations

import re
from collections import deque
from dataclasses import dataclass, field
from typing import Any

from src.mazes.maze3d import GOAL, PLAYER, Maze3D, _deadly, _reconstruct

Cell = tuple[int, int, int]

# @task descargar at 3,1,0            (sin dependencias)
# @task procesar at 5,2,0 after descargar,energia
_TASK_RE = re.compile(r"@task\s+(\w+)\s+at\s+(\d+),(\d+),(\d+)(?:\s+after\s+([\w,]+))?\s*$")


@dataclass(frozen=True)
class Task:
    """Una tarea GROUNDED: id + la celda real donde se hace + sus dependencias (ids que deben estar HECHAS
    antes; pisar la celda con dependencias pendientes NO la completa)."""
    id: str
    cell: Cell
    deps: tuple[str, ...] = ()


@dataclass
class TaskChannel:
    """El canal parseado: la lista de tareas. `require_goal`=True (default) → ganar es completar TODAS las
    tareas Y llegar a `G` (el "volver a la cama" de VotV); False → basta completar todas."""
    tasks: list[Task] = field(default_factory=list)
    require_goal: bool = True

    def by_id(self) -> dict[str, Task]:
        return {t.id: t for t in self.tasks}


def parse_task_channel(text: str) -> TaskChannel | None:
    """Escanea el DSL por directivas `@task` → `TaskChannel`, o None si no hay ninguna."""
    tasks: list[Task] = []
    for raw in text.splitlines():
        if (m := _TASK_RE.match(raw.strip())):
            deps = tuple(d for d in (m[5] or "").split(",") if d)
            tasks.append(Task(id=m[1], cell=(int(m[2]), int(m[3]), int(m[4])), deps=deps))
    return TaskChannel(tasks=tasks) if tasks else None


def dag_check(channel: TaskChannel) -> dict[str, Any]:
    """Sanidad del DAG: dependencias que no existen + ciclos (Kahn). Un ciclo = tareas que jamás podrán
    completarse → el canal es inconsistente ANTES de gastar BFS."""
    ids = {t.id for t in channel.tasks}
    unknown = sorted({d for t in channel.tasks for d in t.deps if d not in ids})
    indeg = {t.id: len([d for d in t.deps if d in ids]) for t in channel.tasks}
    out: dict[str, list[str]] = {i: [] for i in ids}
    for t in channel.tasks:
        for d in t.deps:
            if d in ids:
                out[d].append(t.id)
    q = deque([i for i, n in indeg.items() if n == 0])
    seen = 0
    while q:
        cur = q.popleft()
        seen += 1
        for nxt in out[cur]:
            indeg[nxt] -= 1
            if indeg[nxt] == 0:
                q.append(nxt)
    cycle = seen < len(ids)
    return {"ok": not unknown and not cycle, "unknown_deps": unknown, "cycle": cycle}


def solve_tasks(maze: Maze3D, channel: TaskChannel, max_states: int = 200_000, *,
                flags0: frozenset = frozenset(),
                effective=None) -> dict[str, Any]:
    """BFS de completabilidad del DAG sobre el grafo: MISMO estado que `solve_3d` (celda, llaves, flags)
    extendido con `done` (tareas hechas). Pisar la celda de una tarea con sus deps HECHAS la completa
    (automático). Ganar = todas hechas (+ llegar a `G` si `require_goal`). Compone con TODO el vocabulario
    nav (llaves/puertas/switches/gates/trampas) — una tarea tras un gate exige el switch primero, gratis.

    `effective` (opcional, D2): `frozenset → frozenset` que MAPEA los flags toggleados a los flags EFECTIVOS
    (los toggleados + los power-flags DERIVADOS del canal eléctrico bajo los breakers cerrados) → así una tarea
    detrás de un `@gate` que sólo abre con el breaker cerrado compone con el DAG. None = identidad (nav puro).
    Los power-flags NO entran al estado (son derivados de `flags` → dedup canónico, no explota).

    Devuelve dict tipo `solve_3d` + `completed_order` (orden en que el camino óptimo completa las tareas)."""
    start, goal = maze.find(PLAYER), maze.find(GOAL)
    empty: frozenset = frozenset()
    eff = effective or (lambda f: f)
    sanity = dag_check(channel)
    if start is None or (channel.require_goal and goal is None) or not sanity["ok"] \
            or _deadly(maze, start, eff(flags0)):
        return {"solvable": False, "optimal_steps": None, "path": [], "states_explored": 0,
                "completed_order": [], "dag": sanity}

    task_at: dict[Cell, list[Task]] = {}
    for t in channel.tasks:
        task_at.setdefault(t.cell, []).append(t)
    all_ids = frozenset(t.id for t in channel.tasks)

    def _collect(cell: Cell, held: frozenset) -> frozenset:
        return held | {maze.keys[cell]} if cell in maze.keys else held

    def _toggle(cell: Cell, flags: frozenset) -> frozenset:
        return flags ^ {maze.switches[cell]} if cell in maze.switches else flags

    def _complete(cell: Cell, done: frozenset) -> frozenset:
        # completar en cascada: pisar la celda puede habilitar más de una tarea anclada ahí
        changed = True
        while changed:
            changed = False
            for t in task_at.get(cell, []):
                if t.id not in done and set(t.deps) <= done:
                    done = done | {t.id}
                    changed = True
        return done

    def _won(cell: Cell, done: frozenset) -> bool:
        return done == all_ids and (not channel.require_goal or cell == goal)

    start_state = (start, _collect(start, flags0), flags0, _complete(start, empty))
    prev: dict = {start_state: None}
    queue: deque = deque([start_state])
    explored = 0
    while queue and explored < max_states:
        cur = queue.popleft()
        cell, held, flags, done = cur
        if _won(cell, done):
            chain = _reconstruct(prev, cur)
            path = [s[0] for s in chain]
            order: list[str] = []
            seen: set[str] = set()
            for s in chain:                       # orden real de completado a lo largo del camino óptimo
                for tid in sorted(s[3] - frozenset(seen)):
                    order.append(tid)
                    seen.add(tid)
            return {"solvable": True, "optimal_steps": len(path) - 1, "path": path,
                    "states_explored": explored, "completed_order": order, "dag": sanity}
        explored += 1
        ef = eff(flags)                            # flags EFECTIVOS (toggleados + power-flags derivados del breaker)
        for nxt in maze.neighbors(cell):
            if nxt in maze.doors and maze.doors[nxt] not in held:
                continue
            if nxt in maze.gates and maze.gates[nxt] not in ef:
                continue
            if _deadly(maze, nxt, ef):
                continue
            nf = _toggle(nxt, flags)
            ns = (nxt, _collect(nxt, held), nf, _complete(nxt, done))
            if ns not in prev:
                prev[ns] = cur
                queue.append(ns)

    solvable = False if explored < max_states else None
    return {"solvable": solvable, "optimal_steps": None, "path": [], "states_explored": explored,
            "completed_order": [], "dag": sanity}


def solve_tasks_coupled(maze: Maze3D, channel: TaskChannel, electric, couplings: dict[Cell, str],
                        max_states: int = 200_000, *, flags0: frozenset = frozenset()) -> dict[str, Any]:
    """D2 — TAREAS × BREAKER: el DAG resuelto con la potencia DERIVADA del canal eléctrico. Igual que
    `solve_tasks` pero los `@gate` acoplados a potencia ven los power-flags que resultan de los BREAKERS que el
    jugador cerró (los switches 'gen' toggleados en el estado). Así una tarea encerrada tras una compuerta que
    sólo abre con el generador prendido EXIGE ir a cerrar el breaker primero — el "sistema VotV" (server
    apagado → prenderlo → hacer la tarea → volver) verificado en UN oráculo. Los power-flags se derivan y se
    cachean por subconjunto de flags (mismo truco que `solve_two_way`) → el espacio de estados no crece."""
    from src.mazes.electric import powered_loads
    cache: dict[frozenset, frozenset] = {}

    def effective(flags: frozenset) -> frozenset:
        if flags in cache:
            return cache[flags]
        powered = powered_loads(electric, flags)
        eff = flags | frozenset(f for cell, f in couplings.items() if cell in powered)
        cache[flags] = eff
        return eff

    return solve_tasks(maze, channel, max_states, flags0=flags0, effective=effective)


def tasks_necessity(maze: Maze3D, channel: TaskChannel, max_states: int = 200_000) -> dict[str, Any]:
    """¿El DAG IMPORTA? (necesidad contrafáctica, [[entretenido-necesidad-contrafactual]]): compara el óptimo
    CON tareas contra el reach-G pelado. `detour`>0 = las tareas fuerzan un desvío real (gameplay); 0 = las
    tareas están regaladas sobre el camino (decorativas → señal de curaduría, no error)."""
    from src.mazes.maze3d import solve_3d
    with_tasks = solve_tasks(maze, channel, max_states)
    plain = solve_3d(maze, max_states)
    if not with_tasks["solvable"] or not plain["solvable"]:
        return {"matters": None, "detour": None, "with_tasks": with_tasks["optimal_steps"],
                "plain": plain["optimal_steps"]}
    detour = with_tasks["optimal_steps"] - plain["optimal_steps"]
    return {"matters": detour > 0, "detour": detour,
            "with_tasks": with_tasks["optimal_steps"], "plain": plain["optimal_steps"]}
