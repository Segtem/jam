"""ACOPLE cross-aspecto ELÉCTRICO → NAVEGACIÓN — el "riesgo #2" del JamMap, en su versión TRATABLE.

El problema abierto (declarado en [[jammap-anidado-multiaspecto]] / `nested.py`): verificar varios canales
ACOPLADOS sin que la explosión de estados mate la "verificación barata". La clave de este primer corte es que
el acople es de **UNA VÍA**: el cableado eléctrico NO depende de dónde está el jugador (no hay, todavía, un
switch que el jugador prenda para re-energizar). Entonces se descompone:

  1. Resolver el canal ELÉCTRICO una vez (BFS barato sobre cables) → qué cargas `L` están alimentadas.
  2. CONGELAR ese resultado como un set de flags ON (uno por carga acoplada a una compuerta de nav).
  3. Resolver NAVEGACIÓN con esos flags ya prendidos (`solve_3d(flags0=...)`).

Es **"BFS y después BFS", no "BFS sobre BFS"** → no explota. Mismo principio que el anidado (verificar la hoja,
congelar el contrato, el padre compone sólo por el contrato). El caso de DOS vías (el jugador prende un breaker
que cambia la potencia a mitad de la navegación) = la generalidad completa del riesgo #2, próximo escalón: ahí
el estado eléctrico relevante entra al estado del BFS de nav (cacheado por subconjunto de flags).

Surface en el DSL: `@power x,y,z <flag>` = "la carga en (x,y,z), si está alimentada por el canal eléctrico,
prende el flag <flag>". Una compuerta de nav `@gate cx,cy,cz <flag>` abre sólo con ese flag → la winnability de
nav queda ACOPLADA al cableado eléctrico (ej. la puerta del server abre sólo si el generador lo alimenta).
"""
from __future__ import annotations

import re
from collections import deque
from typing import Any

from src.mazes.electric import ElectricChannel, parse_electric_channel, powered_loads
from src.mazes.maze3d import GOAL, PLAYER, Maze3D, _deadly, _reconstruct, solve_3d

Cell = tuple[int, int, int]

_POWER_RE = re.compile(r"@power\s+(\d+),(\d+),(\d+)\s+(\w+)\s*$")
_CONSUME_RE = re.compile(r"@consume\s+(\d+),(\d+),(\d+)\s+(\w+)\s+([+-]?\d+)\s*$")  # [+-] como @source: '+3' vale


def parse_power_couplings(text: str) -> dict[Cell, str]:
    """Directivas `@power x,y,z flag` → {celda_de_carga: flag}. La carga en esa celda, si el canal eléctrico
    la alimenta, prende `flag` (que una `@gate` de nav puede requerir). Vacío si no hay ninguna."""
    out: dict[Cell, str] = {}
    for raw in text.splitlines():
        m = _POWER_RE.match(raw.strip())
        if m:
            out[(int(m[1]), int(m[2]), int(m[3]))] = m[4]
    return out


def coupled_flags(electric: ElectricChannel, couplings: dict[Cell, str]) -> frozenset:
    """Flags que el canal eléctrico deja ON: el de cada carga acoplada que SÍ está alimentada."""
    powered = powered_loads(electric)
    return frozenset(flag for cell, flag in couplings.items() if cell in powered)


def solve_coupled(maze: Maze3D, electric: ElectricChannel, couplings: dict[Cell, str],
                  max_states: int = 200_000) -> dict[str, Any]:
    """Winnability de NAV acoplada al canal ELÉCTRICO. Si el eléctrico tiene BREAKERS (el jugador puede
    re-energizar a mitad de nav) → acople de DOS VÍAS (`solve_two_way`). Si no, atajo ESTÁTICO de una vía:
    congela qué cargas están alimentadas y resuelve nav con esos power-flags ON desde el arranque."""
    if electric.breakers:
        return solve_two_way(maze, electric, couplings, max_states)
    flags0 = coupled_flags(electric, couplings)
    res = solve_3d(maze, max_states, flags0=flags0)
    res["power_flags"] = sorted(flags0)
    return res


def solve_two_way(maze: Maze3D, electric: ElectricChannel, couplings: dict[Cell, str],
                  max_states: int = 200_000) -> dict[str, Any]:
    """ACOPLE DE DOS VÍAS (la generalidad del riesgo #2): el jugador prende BREAKERS (switches de nav) que
    re-energizan cables → cambian qué cargas están alimentadas → cambian qué `@gate` abren, A MITAD de la
    navegación. El estado eléctrico relevante ya vive en los flags toggleados por switches (el estado del BFS de
    nav); los power-flags se DERIVAN (no se guardan) y se cachean por subconjunto de flags → el espacio de
    estados es el MISMO que nav-con-switches, NO explota. (Un breaker detrás de la compuerta que él mismo
    alimenta = deadlock → el oráculo lo caza como inganable.)"""
    start = maze.find(PLAYER)
    goal = maze.find(GOAL)
    empty: frozenset = frozenset()
    cache: dict[frozenset, frozenset] = {}

    def effective(flags: frozenset) -> frozenset:
        """flags toggleados + power-flags DERIVADOS (cargas alimentadas bajo los breakers cerrados de `flags`)."""
        if flags in cache:
            return cache[flags]
        powered = powered_loads(electric, flags)
        eff = flags | frozenset(f for cell, f in couplings.items() if cell in powered)
        cache[flags] = eff
        return eff

    if start is None or goal is None or _deadly(maze, start, effective(empty)):
        return {"solvable": False, "optimal_steps": None, "path": [], "states_explored": 0, "power_flags": []}

    def collect(cell: Cell, held: frozenset) -> frozenset:
        return held | {maze.keys[cell]} if cell in maze.keys else held

    def toggle(cell: Cell, flags: frozenset) -> frozenset:
        return flags ^ {maze.switches[cell]} if cell in maze.switches else flags

    # ESTADO = (celda, llaves, flags TOGGLEADOS). Los power-flags NO se guardan (son derivados) → dedup canónico.
    start_state = (start, collect(start, empty), empty)
    prev: dict = {start_state: None}
    queue: deque = deque([start_state])
    explored = 0
    while queue and explored < max_states:
        cur = queue.popleft()
        cell, held, flags = cur
        if cell == goal:
            path = [s[0] for s in _reconstruct(prev, cur)]
            return {"solvable": True, "optimal_steps": len(path) - 1, "path": path,
                    "states_explored": explored, "power_flags": sorted(effective(flags) - flags)}
        explored += 1
        eff = effective(flags)                         # gates/hazards ven los power-flags derivados
        for nxt in maze.neighbors(cell):
            if nxt in maze.doors and maze.doors[nxt] not in held:
                continue
            if nxt in maze.gates and maze.gates[nxt] not in eff:
                continue                               # compuerta cerrada (o su carga sin alimentar)
            if _deadly(maze, nxt, eff):
                continue
            ns = (nxt, collect(nxt, held), toggle(nxt, flags))
            if ns not in prev:
                prev[ns] = cur
                queue.append(ns)
    return {"solvable": False if explored < max_states else None, "optimal_steps": None, "path": [],
            "states_explored": explored, "power_flags": []}


def coupling_necessity(maze: Maze3D, electric: ElectricChannel, couplings: dict[Cell, str],
                       max_states: int = 200_000) -> dict[str, Any]:
    """Necesidad CONTRAFÁCTICA del acople ([[entretenido-necesidad-contrafactual]]): ¿el canal eléctrico
    MUERDE sobre la navegación? Compara tres cableados:
      - real      = el cableado declarado (`solve_coupled`).
      - sin poder = ninguna compuerta acoplada abre (flags0 vacío).
      - todo poder = todas las cargas alimentadas (cableado ideal).
    Verdicts:
      - `binding`  = INGANABLE sin poder pero GANABLE con el cableado real → el eléctrico es lo que habilita nav
                     (dependencia real y satisfecha). El caso interesante.
      - `broken`   = GANABLE con todo-poder pero NO con el real → el cableado es INSUFICIENTE (una carga que nav
                     necesita NO está alimentada) → mapa inganable por mal cableado. El fallo que el oráculo caza.
      - `trivial`  = GANABLE aun sin poder → el canal eléctrico no afecta nav (decorativo en este mapa).
    `ok` = el mapa, tal como está cableado, es ganable.

    NOTA (capacidad/sobrecarga): `full_power` fuerza `flags0=all_flags` directo a `solve_3d`, SIN pasar por el
    oráculo eléctrico → es la IDEALIZACIÓN "todas las cargas mágicamente prendidas", no "todos los breakers
    cerrados". Es a propósito: `broken` = ganable-si-todo-prendiera pero no con el cableado real; la sobrecarga
    es justo lo que separa `real` de `full`. Si algún día se deriva `full_power` del oráculo, cuidado: por la
    no-monotonicidad (cerrar un breaker mergea circuitos y puede sobrecargar), todo-ON puede prender MENOS que
    el cableado real → dejaría de ser cota superior."""
    all_flags = frozenset(couplings.values())
    real = solve_coupled(maze, electric, couplings, max_states)
    no_power = solve_3d(maze, max_states, flags0=frozenset())
    full_power = solve_3d(maze, max_states, flags0=all_flags)
    real_ok = bool(real["solvable"])
    no_ok = bool(no_power["solvable"])
    full_ok = bool(full_power["solvable"])
    return {
        "ok": real_ok,
        "binding": (not no_ok) and real_ok,
        "broken": full_ok and not real_ok,
        "trivial": no_ok,
        "matters": (not no_ok) and real_ok,
        "power_flags": real["power_flags"],
        "real_steps": real["optimal_steps"],
    }


def evaluate_coupling(text: str, maze: Maze3D, max_states: int = 200_000) -> dict[str, Any] | None:
    """Conveniencia para GATEAR un elite desde el DSL: parsea el canal eléctrico + los `@power` y devuelve el
    veredicto de `coupling_necessity`, o None si el DSL no acopla nada (ni `[Electrico]` ni `@power`)."""
    electric = parse_electric_channel(text)
    couplings = parse_power_couplings(text)
    if electric is None or not couplings:
        return None
    return coupling_necessity(maze, electric, couplings, max_states)


# ── ACOPLE RECURSO ↔ ELÉCTRICO (el server consume energía Y genera calor) ────────────────────────
def parse_consumes(text: str) -> dict[Cell, dict[str, str]]:
    """Directivas `@consume x,y,z <rec> <delta>` → {celda_de_carga: {rec: delta}}: la carga, MIENTRAS está
    alimentada, suma `delta` al recurso por paso (delta<0 = consume/quema fuel; >0 = genera). El acople
    RECURSO↔ELÉCTRICO. Vacío si no hay ninguna."""
    out: dict[Cell, dict[str, int]] = {}
    for raw in text.splitlines():
        m = _CONSUME_RE.match(raw.strip())
        if m:
            out.setdefault((int(m[1]), int(m[2]), int(m[3])), {})[m[4]] = int(m[5])
    return out


def solve_powered_survival(maze: Maze3D, resource_channel, electric: ElectricChannel,
                           couplings: dict[Cell, str], consumes: dict[Cell, dict[str, int]],
                           max_states: int = 200_000) -> dict[str, Any]:
    """ACOPLE RECURSO↔ELÉCTRICO↔NAV (el sistema tipo-VotV completo): reach-`G` vivo, donde una carga ALIMENTADA
    DRENA un recurso por paso (`@consume`: el server quema fuel / gasta refrigerante mientras está encendido) y
    además puede abrir una `@gate` (`@power`). El jugador prende el breaker para pasar la compuerta, pero eso le
    cuesta recursos → gestión (prender lo justo). TRACTABLE: el estado `(celda, llaves, flags, niveles)` es el
    mismo de `solve_survival`; lo eléctrico (qué cargas alimentadas) se DERIVA de los flags, cacheado por
    subconjunto → no se multiplica por el eléctrico. Devuelve dict tipo `solve_3d` + `levels_at_goal`/`power_flags`."""
    spec = resource_channel.spec
    start = maze.find(PLAYER)
    goal = maze.find(GOAL)
    empty: frozenset = frozenset()
    pow_cache: dict[frozenset, set] = {}
    eff_cache: dict[frozenset, frozenset] = {}

    def powered(flags: frozenset) -> set:
        if flags not in pow_cache:
            pow_cache[flags] = powered_loads(electric, flags)
        return pow_cache[flags]

    def effective(flags: frozenset) -> frozenset:
        if flags not in eff_cache:
            eff_cache[flags] = flags | frozenset(f for c, f in couplings.items() if c in powered(flags))
        return eff_cache[flags]

    def extra_of(flags: frozenset) -> dict[str, int]:
        ex: dict[str, int] = {}
        for c in powered(flags):                       # cada carga alimentada suma su consumo/generación
            for r, d in consumes.get(c, {}).items():
                ex[r] = ex.get(r, 0) + d
        return ex

    lv0 = spec.apply(spec.start_levels(), start, drain=False) if start is not None else None
    if start is None or goal is None or lv0 is None or _deadly(maze, start, effective(empty)):
        return {"solvable": False, "optimal_steps": None, "path": [], "states_explored": 0,
                "levels_at_goal": None, "power_flags": []}

    def collect(cell: Cell, held: frozenset) -> frozenset:
        return held | {maze.keys[cell]} if cell in maze.keys else held

    def toggle(cell: Cell, flags: frozenset) -> frozenset:
        return flags ^ {maze.switches[cell]} if cell in maze.switches else flags

    start_state = (start, collect(start, empty), empty, lv0)
    prev: dict = {start_state: None}
    queue: deque = deque([start_state])
    explored = 0
    while queue and explored < max_states:
        cur = queue.popleft()
        cell, held, flags, levels = cur
        if cell == goal:
            path = [s[0] for s in _reconstruct(prev, cur)]
            return {"solvable": True, "optimal_steps": len(path) - 1, "path": path,
                    "states_explored": explored, "levels_at_goal": dict(zip(spec._order(), levels)),
                    "power_flags": sorted(effective(flags) - flags)}
        explored += 1
        eff = effective(flags)
        ex = extra_of(flags)                           # consumo bajo el estado eléctrico ACTUAL (server on/off)
        for nxt in maze.neighbors(cell):
            if nxt in maze.doors and maze.doors[nxt] not in held:
                continue
            if nxt in maze.gates and maze.gates[nxt] not in eff:
                continue
            if _deadly(maze, nxt, eff):
                continue
            nlv = spec.apply(levels, nxt, drain=True, extra=ex)
            if nlv is None:                            # se agotó el recurso (el server lo quemó) → poda
                continue
            ns = (nxt, collect(nxt, held), toggle(nxt, flags), nlv)
            if ns not in prev:
                prev[ns] = cur
                queue.append(ns)
    return {"solvable": False if explored < max_states else None, "optimal_steps": None, "path": [],
            "states_explored": explored, "levels_at_goal": None, "power_flags": []}


def powered_survival_horizon(maze: Maze3D, resource_channel, electric: ElectricChannel,
                             couplings: dict[Cell, str], consumes: dict[Cell, dict[str, int]],
                             max_states: int = 200_000) -> dict[str, Any]:
    """SURVIVE-N acoplado (el modo VotV completo, análogo de `survival_horizon` pero con el acople
    recurso↔eléctrico↔nav): ¿cuántos PASOS sobrevive el jugador GESTIONANDO el server? Prender el breaker abre
    una `@gate` (llega a más fuentes) PERO la carga alimentada quema fuel/refrigerante (`@consume`) cada paso →
    hay que prenderlo lo justo. `horizon`=int finito, o `float('inf')` si hay un CICLO sostenible alcanzable
    (un loop de recarga que no agota → sobrevive para siempre — ej. una ronda server-off para recargar,
    server-on para el evento). `survives_days = horizon >= days`. NO necesita `G`.

    TRACTABLE igual que `solve_powered_survival`: el estado `(celda, llaves, flags, niveles)` es el de
    `survival_horizon`; lo eléctrico (cargas alimentadas → power-flags derivados + consumo) se DERIVA de los
    flags, cacheado por subconjunto → no multiplica el espacio por el eléctrico. Detección de ciclo vivo = el
    mismo DFS de 3 colores del canal recurso."""
    spec = resource_channel.spec
    start = maze.find(PLAYER)
    empty: frozenset = frozenset()
    pow_cache: dict[frozenset, set] = {}
    eff_cache: dict[frozenset, frozenset] = {}
    extra_cache: dict[frozenset, dict[str, int]] = {}

    def powered(flags: frozenset) -> set:
        if flags not in pow_cache:
            pow_cache[flags] = powered_loads(electric, flags)
        return pow_cache[flags]

    def effective(flags: frozenset) -> frozenset:
        if flags not in eff_cache:
            eff_cache[flags] = flags | frozenset(f for c, f in couplings.items() if c in powered(flags))
        return eff_cache[flags]

    def extra_of(flags: frozenset) -> dict[str, int]:
        if flags not in extra_cache:
            ex: dict[str, int] = {}
            for c in powered(flags):
                for r, d in consumes.get(c, {}).items():
                    ex[r] = ex.get(r, 0) + d
            extra_cache[flags] = ex
        return extra_cache[flags]

    lv0 = spec.apply(spec.start_levels(), start, drain=False) if start is not None else None
    if start is None or lv0 is None or _deadly(maze, start, effective(empty)):
        return {"horizon": 0, "states_explored": 0}

    def collect(cell: Cell, held: frozenset) -> frozenset:
        return held | {maze.keys[cell]} if cell in maze.keys else held

    def toggle(cell: Cell, flags: frozenset) -> frozenset:
        return flags ^ {maze.switches[cell]} if cell in maze.switches else flags

    def succ(state) -> list:
        cell, held, flags, levels = state
        eff = effective(flags)
        ex = extra_of(flags)                           # consumo bajo el estado eléctrico ACTUAL (server on/off)
        out = []
        for nxt in maze.neighbors(cell):
            if nxt in maze.doors and maze.doors[nxt] not in held:
                continue
            if nxt in maze.gates and maze.gates[nxt] not in eff:
                continue
            if _deadly(maze, nxt, eff):
                continue
            nlv = spec.apply(levels, nxt, drain=True, extra=ex)
            if nlv is None:                            # el server quemó el recurso → paso mortal, poda
                continue
            out.append((nxt, collect(nxt, held), toggle(nxt, flags), nlv))
        return out

    # DFS iterativo de 3 colores (idéntico a survival_horizon): back-edge = ciclo vivo → inf; memoiza el
    # camino vivo más largo. El acople entra sólo por `succ` (eff para gates/hazards, ex para el drenaje).
    s0 = (start, collect(start, empty), empty, lv0)
    WHITE, GRAY, BLACK = 0, 1, 2
    color: dict = {}
    longest: dict = {}
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
            if c == GRAY:                              # ciclo vivo alcanzable → supervivencia infinita
                return {"horizon": float("inf"), "states_explored": explored}
            if c == WHITE:
                stack.append((nx, False))
    return {"horizon": longest.get(s0, 0), "states_explored": explored}


def powered_survives(maze: Maze3D, resource_channel, electric: ElectricChannel,
                     couplings: dict[Cell, str], consumes: dict[Cell, dict[str, int]],
                     days: int, max_states: int = 200_000) -> bool:
    """¿Se puede sobrevivir al menos `days` pasos gestionando el server? (conveniencia sobre
    `powered_survival_horizon`). Si la búsqueda se TRUNCÓ (`max_states`), el horizonte no está certificado →
    conservador: NO cuenta como sobrevivible (un oráculo de aceptación no debe dar OK sin verificar)."""
    h = powered_survival_horizon(maze, resource_channel, electric, couplings, consumes, max_states)
    return h["horizon"] >= days and not h.get("truncated")


def powered_horizon_necessity(maze: Maze3D, resource_channel, electric: ElectricChannel,
                              couplings: dict[Cell, str], consumes: dict[Cell, dict[str, int]],
                              days: int, max_states: int = 200_000) -> dict[str, Any]:
    """Necesidad CONTRAFÁCTICA del acople en modo SURVIVE-N: ¿el CONSUMO eléctrico muerde el horizonte de
    supervivencia? Compara el horizonte real (con `@consume`) contra el mismo mapa SIN consumo (server gratis):
      - `ok`          = se sobrevive `days` como está (horizon real ≥ days).
      - `binding_fail`= se sobrevive `days` SIN el consumo pero NO con él → el costo eléctrico rompe el horizonte.
      - `matters`     = el consumo cambia si se llega a `days` O acorta el horizonte finito (si no, decorativo).
    TRUNCACIÓN: `real` y `free` pueden truncar por separado (`free`, con menos poda, es MÁS propenso) → un
    horizonte no certificado. Conservador: un lado truncado NO cuenta como sobrevivible, y si CUALQUIERA truncó
    no afirmamos `matters` (evita `binding_fail`/`matters` falsos por un `inf` espurio). `truncated` se propaga."""
    real = powered_survival_horizon(maze, resource_channel, electric, couplings, consumes, max_states)
    free = powered_survival_horizon(maze, resource_channel, electric, couplings, {}, max_states)
    rt, ft = bool(real.get("truncated")), bool(free.get("truncated"))
    truncated = rt or ft
    real_h, free_h = real["horizon"], free["horizon"]
    real_ok = real_h >= days and not rt
    free_ok = free_h >= days and not ft
    matters = (not truncated) and ((real_ok != free_ok) or (real_h != free_h))
    return {"ok": real_ok, "binding_fail": (not truncated) and free_ok and not real_ok, "matters": matters,
            "real_horizon": None if real_h == float("inf") else int(real_h),
            "free_horizon": None if free_h == float("inf") else int(free_h),
            "sustainable": real_h == float("inf") and not rt, "truncated": truncated}


def powered_survival_necessity(maze: Maze3D, resource_channel, electric: ElectricChannel,
                               couplings: dict[Cell, str], consumes: dict[Cell, dict[str, int]],
                               max_states: int = 200_000) -> dict[str, Any]:
    """Necesidad CONTRAFÁCTICA del acople recurso↔eléctrico: ¿el CONSUMO eléctrico muerde la supervivencia?
    Compara el cableado real (con `@consume`) contra el mismo mapa SIN consumo (el server gratis):
      - `ok`          = ganable como está (real solvable).
      - `binding_fail`= ganable SIN el consumo pero NO con él → el costo eléctrico rompe la supervivencia.
      - `matters`     = el consumo cambia el veredicto O el óptimo (si no, es decorativo)."""
    real = solve_powered_survival(maze, resource_channel, electric, couplings, consumes, max_states)
    free = solve_powered_survival(maze, resource_channel, electric, couplings, {}, max_states)
    real_ok, free_ok = bool(real["solvable"]), bool(free["solvable"])
    matters = (real_ok != free_ok) or (real_ok and free_ok
                                       and real["optimal_steps"] != free["optimal_steps"])
    return {"ok": real_ok, "binding_fail": free_ok and not real_ok, "matters": matters,
            "real_steps": real["optimal_steps"], "free_steps": free["optimal_steps"]}


def evaluate_powered(text: str, maze: Maze3D, max_states: int = 200_000) -> dict[str, Any] | None:
    """Conveniencia para GATEAR un elite con acople recurso↔eléctrico desde el DSL. None si el DSL no tiene
    los tres ingredientes (canal recurso + canal eléctrico + al menos un `@consume`)."""
    from src.mazes.resource import parse_resource_channel
    rc = parse_resource_channel(text)
    electric = parse_electric_channel(text)
    consumes = parse_consumes(text)
    if rc is None or electric is None or not consumes:
        return None
    return powered_survival_necessity(maze, rc, electric, parse_power_couplings(text), consumes, max_states)
