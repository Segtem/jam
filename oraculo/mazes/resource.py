"""Canal RECURSO — el oráculo de SUPERVIVENCIA del JamMap (aspecto, no escala).

Disciplina canal-por-aspecto del ADR [[2026-06-25-ADR-Vocabulario-JamMap-Canales-y-Directivas]]: un canal es
otro JamMap sobre las MISMAS coordenadas, con su alfabeto chico y SU PROPIO ORÁCULO. El canal navegación
responde winnability binaria ("¿`P` llega a `G`?"); el loop de un juego tipo VotV/Penumbra **no es llegar, es
SOSTENER un presupuesto en el tiempo** (no morir de hambre / sin energía / sin cordura mientras avanzás).

Esto es la winnability extendida de *alcanzar una meta* → *existe una política que mantiene un vector de
recursos dentro de cota durante N pasos* (bounded model checking / planning, sigue siendo decidible y
determinista). Ver el análisis [[2026-06-30-ANALISIS-Idealizar-VotV-en-JamDSL-Factibilidad]] (canal RECURSO =
la pieza de más leverage para subir de "Backrooms vestido" a "Penumbra/VotV verificable").

Modelo (mínimo, honesto):
  - Cada RECURSO es un escalar ENTERO acotado a `[lo, hi]`. Se DRENA `drain` por cada PASO (move). Caer por
    debajo de `lo` = MUERTE (se poda el estado). `hi` = tope de almacenamiento (clamp al recargar).
  - Una FUENTE es una celda que, al pisarla, suma `delta` a uno o más recursos (comida, cama, generador),
    clampeado a `[lo, hi]`.
  - El estado se discretiza por construcción (recursos enteros en `[lo, hi]`) → el espacio aumentado es
    FINITO. Ese es el caveat de tractabilidad del análisis: rangos chicos = búsqueda barata.

Dos modos de victoria:
  A) `solve_survival` — REACH-ALIVE: llegar a `G` con todos los recursos ≥ `lo` en TODO el camino (Penumbra:
     llegá a la salida antes de que se te acabe la cordura). Drop-in paralelo de `solve_3d`.
  B) `survival_horizon` — SURVIVE-T: ¿cuántos pasos podés mantenerte vivo? `inf` si hay un CICLO sostenible
     (un loop que no agota = sobrevivís para siempre). El oráculo "sobrevivir N días" de VotV.

Surface en el DSL de texto (`[Recurso N]` + `@budget/@drain/@source`) = próximo paso; acá el spec es
programático (igual que el oráculo de nav existió antes que toda la gramática).
"""
from __future__ import annotations

import re
from collections import deque
from dataclasses import dataclass, field
from typing import Any

from src.mazes.maze3d import GOAL, PLAYER, Maze3D, _deadly

Cell = tuple[int, int, int]


@dataclass(frozen=True)
class Resource:
    """Un recurso escalar acotado. `start`=nivel inicial · `hi`=tope (clamp) · `lo`=piso (caer debajo=muerte)
    · `drain`=cuánto se pierde por paso."""
    name: str
    start: int
    hi: int
    lo: int = 0
    drain: int = 1


@dataclass
class ResourceSpec:
    """Canal recurso sobre un Maze3D: los recursos y las celdas-FUENTE (`celda → {recurso: delta}`)."""
    resources: list[Resource]
    sources: dict[Cell, dict[str, int]] = field(default_factory=dict)

    def _order(self) -> list[str]:
        return [r.name for r in self.resources]

    def start_levels(self) -> tuple[int, ...]:
        return tuple(r.start for r in self.resources)

    def apply(self, levels: tuple[int, ...], cell: Cell, *, drain: bool,
              extra: dict[str, int] | None = None) -> tuple[int, ...] | None:
        """Nuevo vector de niveles tras (opcionalmente) drenar un paso y aplicar la fuente de `cell`.
        `extra` = delta por recurso de OTRO canal (el ACOPLE recurso↔eléctrico: una carga alimentada que
        consume/genera un recurso por paso). Devuelve None si algún recurso cae por debajo de su `lo` (MUERTE)."""
        src = self.sources.get(cell, {})
        out = []
        for i, r in enumerate(self.resources):
            v = levels[i] - (r.drain if drain else 0)
            if r.name in src:
                v += src[r.name]
            if extra and r.name in extra:   # acople cross-aspecto (ej. el server alimentado quema fuel/genera calor)
                v += extra[r.name]
            v = min(v, r.hi)                 # clamp al tope de almacenamiento
            if v < r.lo:                     # se agotó → muerte
                return None
            out.append(v)
        return tuple(out)


def _collect(maze: Maze3D, cell: Cell, held: frozenset) -> frozenset:
    return held | {maze.keys[cell]} if cell in maze.keys else held


def _toggle(maze: Maze3D, cell: Cell, flags: frozenset) -> frozenset:
    return flags ^ {maze.switches[cell]} if cell in maze.switches else flags


def _passable(maze: Maze3D, nxt: Cell, held: frozenset, flags: frozenset) -> bool:
    """Mismas reglas de poda que `solve_3d`: puerta cerrada, compuerta OFF o trampa mortal armada."""
    if nxt in maze.doors and maze.doors[nxt] not in held:
        return False
    if nxt in maze.gates and maze.gates[nxt] not in flags:
        return False
    return not _deadly(maze, nxt, flags)


def _reconstruct(prev: dict, node):
    path = [node]
    while prev[node] is not None:
        node = prev[node]
        path.append(node)
    path.reverse()
    return path


def solve_survival(maze: Maze3D, spec: ResourceSpec, max_states: int = 200_000) -> dict[str, Any]:
    """Modo A (REACH-ALIVE): BFS de winnability aumentada por recursos, de `P` a `G`. Mismo contrato que
    `solve_3d` + `levels_at_goal`. `solvable`: True (camino vivo) | False (agotado) | None (presupuesto)."""
    start = maze.find(PLAYER)
    goal = maze.find(GOAL)
    empty: frozenset = frozenset()
    lv0 = spec.apply(spec.start_levels(), start, drain=False) if start is not None else None
    if start is None or goal is None or lv0 is None or _deadly(maze, start, empty):
        return {"solvable": False, "optimal_steps": None, "path": [], "states_explored": 0,
                "levels_at_goal": None}

    start_state = (start, _collect(maze, start, empty), empty, lv0)
    prev: dict = {start_state: None}
    queue: deque = deque([start_state])
    explored = 0
    while queue and explored < max_states:
        cur = queue.popleft()
        cell, held, flags, levels = cur
        if cell == goal:
            path = [s[0] for s in _reconstruct(prev, cur)]
            return {"solvable": True, "optimal_steps": len(path) - 1, "path": path,
                    "states_explored": explored, "levels_at_goal": dict(zip(spec._order(), levels))}
        explored += 1
        for nxt in maze.neighbors(cell):
            if not _passable(maze, nxt, held, flags):
                continue
            nlv = spec.apply(levels, nxt, drain=True)
            if nlv is None:                       # te morís de hambre/energía al dar el paso → poda
                continue
            ns = (nxt, _collect(maze, nxt, held), _toggle(maze, nxt, flags), nlv)
            if ns not in prev:
                prev[ns] = cur
                queue.append(ns)
    return {"solvable": False if explored < max_states else None, "optimal_steps": None, "path": [],
            "states_explored": explored, "levels_at_goal": None}


def survival_horizon(maze: Maze3D, spec: ResourceSpec, max_states: int = 200_000) -> dict[str, Any]:
    """Modo B (SURVIVE-T): ¿cuántos PASOS podés mantenerte vivo desde `P`? `horizon`=int finito, o
    `float('inf')` si hay un CICLO sostenible alcanzable vivo (loop que no agota → sobrevivís para siempre).
    El oráculo "sobrevivir N días" de VotV. `survives(days)` = `horizon >= days`."""
    start = maze.find(PLAYER)
    empty: frozenset = frozenset()
    lv0 = spec.apply(spec.start_levels(), start, drain=False) if start is not None else None
    if start is None or lv0 is None or _deadly(maze, start, empty):
        return {"horizon": 0, "states_explored": 0}

    s0 = (start, _collect(maze, start, empty), empty, lv0)
    # sucesores vivos de un estado (deterministas por vecino elegido)
    def succ(state) -> list:
        cell, held, flags, levels = state
        out = []
        for nxt in maze.neighbors(cell):
            if not _passable(maze, nxt, held, flags):
                continue
            nlv = spec.apply(levels, nxt, drain=True)
            if nlv is None:
                continue
            out.append((nxt, _collect(maze, nxt, held), _toggle(maze, nxt, flags), nlv))
        return out

    # DFS iterativo de 3 colores: detecta back-edge (ciclo vivo → inf) y memoiza el camino vivo más largo.
    WHITE, GRAY, BLACK = 0, 1, 2
    color: dict = {}
    longest: dict = {}            # máximos PASOS que se pueden dar desde el estado, manteniéndose vivo
    explored = 0
    stack = [(s0, False)]
    while stack:
        state, processed = stack.pop()
        if processed:
            best = 0
            for nx in succ(state):
                best = max(best, 1 + longest.get(nx, 0))
            longest[state] = best
            color[state] = BLACK
            continue
        if color.get(state, WHITE) != WHITE:
            continue
        color[state] = GRAY
        explored += 1
        if explored >= max_states:
            return {"horizon": float("inf"), "states_explored": explored, "truncated": True}
        stack.append((state, True))
        for nx in succ(state):
            c = color.get(nx, WHITE)
            if c == GRAY:                          # back-edge → ciclo vivo alcanzable → supervivencia infinita
                return {"horizon": float("inf"), "states_explored": explored}
            if c == WHITE:
                stack.append((nx, False))
    return {"horizon": longest.get(s0, 0), "states_explored": explored}


def survives(maze: Maze3D, spec: ResourceSpec, days: int, max_states: int = 200_000) -> bool:
    """¿Se puede sobrevivir al menos `days` pasos desde `P`? (conveniencia sobre `survival_horizon`). Si la
    búsqueda se TRUNCÓ (`max_states`), el horizonte no está certificado → conservador: NO cuenta (el oráculo de
    aceptación no da OK sin verificar)."""
    h = survival_horizon(maze, spec, max_states)
    return h["horizon"] >= days and not h.get("truncated")


# ── SURFACE EN EL DSL DE TEXTO ────────────────────────────────────────────────────────────────────
# El canal recurso es DUEÑO de su propia sintaxis (igual que nav vive en ascii_map). Va como un bloque
# `[Recurso 0]` con DIRECTIVAS (no grilla — las fuentes se ubican por coordenada):
#   @drain  <name> <n>                    cuánto se gasta por paso
#   @cap    <name> <n>                    tope de almacenamiento (hi)
#   @start  <name> <n>                    nivel inicial
#   @budget <name> >= <lo> over days=<N>  CONDICIÓN DE VICTORIA: sobrevivir N pasos manteniendo name >= lo
#   @source <x>,<y>,<z> <name> <±delta>   celda-fuente (comida/generador) que recarga al pisarla
# El parser de nav (ascii_map) ignora estas líneas (tienen dígitos/comas → no son filas de grilla).
_RES_HDR = re.compile(r"^\[Recurso\b")
_RES_DRAIN = re.compile(r"@drain\s+(\w+)\s+(\d+)")
_RES_CAP = re.compile(r"@cap\s+(\w+)\s+(\d+)")
_RES_START = re.compile(r"@start\s+(\w+)\s+(\d+)")
_RES_BUDGET = re.compile(r"@budget\s+(\w+)\s*>=\s*(\d+)\s+over\s+days\s*=\s*(\d+)")
_RES_SOURCE = re.compile(r"@source\s+(\d+),(\d+),(\d+)\s+(\w+)\s*([+-]?\d+)")


@dataclass
class ResourceChannel:
    """El canal recurso parseado del DSL: el `spec` + la condición de victoria. `days`=None → modo REACH-ALIVE
    (llegar a G vivo); `days`=int → modo SURVIVE-T (sobrevivir N pasos, sin necesidad de G)."""
    spec: ResourceSpec
    days: int | None = None


def parse_resource_channel(text: str) -> ResourceChannel | None:
    """Escanea el DSL JamMap por directivas de recurso → `ResourceChannel`, o None si no hay ninguna.
    Tolerante a faltantes (defaults: drain 1 · cap=start o 10 · start=cap · lo del @budget o 0)."""
    drain: dict[str, int] = {}
    cap: dict[str, int] = {}
    start: dict[str, int] = {}
    lo: dict[str, int] = {}
    sources: dict[Cell, dict[str, int]] = {}
    days: int | None = None
    seen = False
    for raw in text.splitlines():
        s = raw.strip()
        if _RES_HDR.match(s):
            seen = True
            continue
        if (m := _RES_DRAIN.match(s)):
            drain[m[1]] = int(m[2]); seen = True
        elif (m := _RES_CAP.match(s)):
            cap[m[1]] = int(m[2]); seen = True
        elif (m := _RES_START.match(s)):
            start[m[1]] = int(m[2]); seen = True
        elif (m := _RES_BUDGET.match(s)):
            lo[m[1]] = int(m[2]); days = max(days or 0, int(m[3])); seen = True
        elif (m := _RES_SOURCE.match(s)):
            cell = (int(m[1]), int(m[2]), int(m[3]))
            sources.setdefault(cell, {})[m[4]] = int(m[5]); seen = True
    if not seen:
        return None
    names = set(drain) | set(cap) | set(start) | set(lo) | {n for d in sources.values() for n in d}
    resources = []
    for name in sorted(names):
        st = start.get(name, cap.get(name, 10))
        hi = cap.get(name, st)
        resources.append(Resource(name=name, start=st, hi=hi, lo=lo.get(name, 0),
                                   drain=drain.get(name, 1)))
    return ResourceChannel(ResourceSpec(resources, sources), days=days)


def render_resource_channel(channel: ResourceChannel) -> list[str]:
    """`ResourceChannel` → líneas del DSL (inversa de `parse_resource_channel`). Round-trip estable."""
    out = ["[Recurso 0]"]
    for r in channel.spec.resources:
        out.append(f"@drain {r.name} {r.drain}")
        out.append(f"@cap {r.name} {r.hi}")
        out.append(f"@start {r.name} {r.start}")
        if channel.days is not None:
            out.append(f"@budget {r.name} >= {r.lo} over days={channel.days}")
    for cell, deltas in sorted(channel.spec.sources.items()):
        for name, d in sorted(deltas.items()):
            out.append(f"@source {cell[0]},{cell[1]},{cell[2]} {name} {d:+d}")
    return out


def evaluate_channel(maze: Maze3D, channel: ResourceChannel, max_states: int = 200_000) -> dict[str, Any]:
    """Oráculo unificado para GATEAR un elite: corre el modo correcto del canal y devuelve un veredicto
    común `{ok, mode, ...}`. `days` set → SURVIVE-T (sobrevivir N pasos); si no → REACH-ALIVE (llegar a G)."""
    if channel.days is not None:
        h = survival_horizon(maze, channel.spec, max_states)
        truncated = bool(h.get("truncated"))              # búsqueda truncada → horizonte NO certificado
        inf = h["horizon"] == float("inf") and not truncated
        # JSON-safe: `inf` no es JSON válido → lo expresamos como sustainable=True + horizon=None. Conservador:
        # truncado NO cuenta como ok (no damos OK de supervivencia sin verificar).
        return {"ok": (not truncated) and h["horizon"] >= channel.days, "mode": "survive", "days": channel.days,
                "sustainable": inf, "horizon": None if h["horizon"] == float("inf") else int(h["horizon"]),
                "truncated": truncated}
    sur = solve_survival(maze, channel.spec, max_states)
    return {"ok": bool(sur["solvable"]), "mode": "reach", "optimal_steps": sur["optimal_steps"],
            "levels_at_goal": sur["levels_at_goal"]}


def resource_necessity(maze: Maze3D, spec: ResourceSpec, max_states: int = 200_000) -> dict[str, Any]:
    """Necesidad CONTRAFÁCTICA del canal recurso ([[entretenido-necesidad-contrafactual]]): el recurso
    *importa* sólo si la restricción CAMBIA el veredicto vs la navegación pura. Compara `solve_3d`
    (ignora recursos) con `solve_survival`:
      - `binding`     = el nivel es ganable SIN recursos pero NO sobrevivible CON ellos (la cota muerde).
      - `detour`      = sobrevivible, pero el óptimo se alarga (obliga un rodeo por una fuente).
    Si `binding` y `detour` son ambos False, el canal recurso es decorativo en este mapa (no cuenta)."""
    from src.mazes.maze3d import solve_3d
    nav = solve_3d(maze, max_states)
    sur = solve_survival(maze, spec, max_states)
    nav_ok = bool(nav["solvable"])
    sur_ok = bool(sur["solvable"])
    binding = nav_ok and not sur_ok
    detour = bool(nav_ok and sur_ok and nav["optimal_steps"] is not None
                  and sur["optimal_steps"] is not None and sur["optimal_steps"] > nav["optimal_steps"])
    return {"binding": binding, "detour": detour, "matters": binding or detour,
            "nav_steps": nav["optimal_steps"], "survival_steps": sur["optimal_steps"]}
