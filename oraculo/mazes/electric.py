"""Canal ELÉCTRICO — el oráculo de POTENCIA del JamMap (segundo aspecto, después de [[canal-recurso]]).

Disciplina canal-por-aspecto del ADR [[2026-06-25-ADR-Vocabulario-JamMap-Canales-y-Directivas]]: otra grilla
sobre las MISMAS coordenadas que la navegación, **alfabeto chico propio** y **su propio oráculo**. Mientras el
canal nav responde "¿`P` llega a `G`?", el eléctrico responde **"¿toda carga `L` está alimentada por una
fuente `S`?"** — BFS sobre el GRAFO DE CABLES (no sobre celdas transitables).

A diferencia del recurso (directivas), el eléctrico es **grid-based** (glifos sobre celdas), igual que nav:

    [Electrico 0]        # mismo piso, OTRO canal, mismas coordenadas
    #######
    #S---L#              # S=fuente  -=cable  L=carga (lámpara/equipo)  +=empalme/breaker
    #...|.#              # (| y - son ambos cable; el | sólo es legibilidad vertical)
    #..L--#
    #######

Alfabeto: `S`=fuente de energía · `L`=carga (lámpara/equipo) · `-` `|` `+`=cable (empalmes) · `.`/`#`/` `=sin
cable. **Oráculo `all_powered`:** una carga está alimentada sólo si hay un camino de celdas-cable que la conecta
a alguna `S` (adyacencia 4-dir en el mismo piso). Verificación barata = BFS, igual que nav. El ACOPLE
cross-aspecto (`@power S->L` que abre una puerta de nav, calor que depende de la carga…) = el "riesgo #2", se
monta encima de este oráculo (próximo paso). Vertical (cable entre pisos) = diferido a un glifo tipo conector.
"""
from __future__ import annotations

import re
from collections import deque
from dataclasses import dataclass, field
from typing import Any

Cell = tuple[int, int, int]

_ELEC_HDR = re.compile(r"^\[Electrico\s+(\d+)\]\s*$")
_BREAKER_RE = re.compile(r"@breaker\s+(\d+),(\d+),(\d+)\s+(\w+)\s*$")
_CAPACITY_RE = re.compile(r"@capacity\s+(\d+),(\d+),(\d+)\s+(\d+)\s*$")   # una fuente S abastece capacidad n
_DEMAND_RE = re.compile(r"@demand\s+(\d+),(\d+),(\d+)\s+(\d+)\s*$")       # una carga L consume n (default 1)
_PRIORITY_RE = re.compile(r"@priority\s+(\d+),(\d+),(\d+)\s+(\d+)\s*$")   # prioridad de una carga (mayor = antes)
_SOURCE_CH = "S"
_LOAD_CH = "L"
_WIRE_CH = set("-|+")                       # cables/empalmes (puro ruteo, sin semántica extra)
_ELEC_CHARS = set("#. ") | {_SOURCE_CH, _LOAD_CH} | _WIRE_CH
_CONDUCT = {_SOURCE_CH, _LOAD_CH} | _WIRE_CH  # celdas que CONDUCEN (la fuente y la carga también son nodos del grafo)
_DIRS = [(1, 0), (-1, 0), (0, 1), (0, -1)]


@dataclass
class ElectricChannel:
    """El canal eléctrico parseado: la grilla por piso (`z → filas`) + los cells clasificados (coords (x,y,z))."""
    grid: dict[int, list[str]] = field(default_factory=dict)
    sources: set[Cell] = field(default_factory=set)
    loads: set[Cell] = field(default_factory=set)
    wires: set[Cell] = field(default_factory=set)     # TODAS las celdas que conducen (incluye S y L)
    breakers: dict[Cell, str] = field(default_factory=dict)  # celda-cable → flag que la habilita (el acople 2-vías:
    #   un BREAKER conduce sólo si su flag está ON; el jugador lo prende con un @switch de nav)
    caps: dict[Cell, int] = field(default_factory=dict)      # fuente S → capacidad que abastece (@capacity)
    demands: dict[Cell, int] = field(default_factory=dict)   # carga L → consumo (@demand; default 1). El modelo de
    #   SOBRECARGA es POR-COMPONENTE (opt-in local): un circuito cuya fuente tiene @capacity y que pide más de lo
    #   que da queda DESENERGIZADO entero (la protección lo corta, all-or-nothing determinista). No confundir con
    #   @breaker (ese es el switch que abre/cierra el jugador; acá es la protección por sobrecarga del oráculo)
    priorities: dict[Cell, int] = field(default_factory=dict)  # carga L → prioridad (@priority, default 0). Si un
    #   circuito sobrecargado tiene ALGUNA carga con @priority → LOAD-SHEDDING graceful (panel inteligente): se
    #   mantienen las cargas de mayor prioridad que ENTRAN en la capacidad y se tiran las demás (greedy, mayor
    #   prioridad primero, desempate por coord — determinista, sin subset-sum). Sin @priority → all-or-nothing.


def parse_electric_channel(text: str) -> ElectricChannel | None:
    """Escanea el DSL por bloques `[Electrico N]` → `ElectricChannel`, o None si no hay ninguno. Cada `N` = el
    piso `z` (mismas coords que `[Piso N]`). Corta el bloque en la próxima cabecera `[...]` o línea no-grilla."""
    grid: dict[int, list[str]] = {}
    breakers: dict[Cell, str] = {}
    caps: dict[Cell, int] = {}
    demands: dict[Cell, int] = {}
    priorities: dict[Cell, int] = {}
    cur: int | None = None
    for raw in text.splitlines():
        line = raw.rstrip()
        s = line.strip()
        me = _ELEC_HDR.match(s)
        if me:
            cur = int(me[1]); grid.setdefault(cur, [])
            continue
        if (mb := _BREAKER_RE.match(s)):       # @breaker x,y,z flag (acople 2-vías) — fuera o dentro del bloque
            breakers[(int(mb[1]), int(mb[2]), int(mb[3]))] = mb[4]
            cur = None
            continue
        if (mc := _CAPACITY_RE.match(s)):      # @capacity x,y,z n (capacidad de una fuente)
            caps[(int(mc[1]), int(mc[2]), int(mc[3]))] = int(mc[4])
            cur = None
            continue
        if (md := _DEMAND_RE.match(s)):        # @demand x,y,z n (consumo de una carga)
            demands[(int(md[1]), int(md[2]), int(md[3]))] = int(md[4])
            cur = None
            continue
        if (mp := _PRIORITY_RE.match(s)):      # @priority x,y,z n (prioridad de una carga para el shedding)
            priorities[(int(mp[1]), int(mp[2]), int(mp[3]))] = int(mp[4])
            cur = None
            continue
        if s.startswith("["):                  # otra cabecera de canal → termina el bloque eléctrico
            cur = None
            continue
        if cur is None or not s:
            continue
        if line.lstrip().startswith("# "):     # comentario/leyenda
            continue
        if all(c in _ELEC_CHARS for c in line):
            grid[cur].append(line)
        else:                                  # línea ajena → cierra el bloque (defensivo)
            cur = None
    if not grid or all(not rows for rows in grid.values()):
        return None

    ch = ElectricChannel(grid=grid, breakers=breakers, caps=caps, demands=demands, priorities=priorities)
    for z, rows in grid.items():
        for y, row in enumerate(rows):
            for x, c in enumerate(row):
                if c in _CONDUCT:
                    cell = (x, y, z)
                    ch.wires.add(cell)
                    if c == _SOURCE_CH:
                        ch.sources.add(cell)
                    elif c == _LOAD_CH:
                        ch.loads.add(cell)
    return ch


def _powered_cells(channel: ElectricChannel, active_flags: frozenset = frozenset()) -> set[Cell]:
    """Conjunto de celdas ENERGIZADAS. Recorre los COMPONENTES CONEXOS del grafo de cables (adyacencia 4-dir,
    mismo piso) sobre las celdas que CONDUCEN ahora: un BREAKER (celda con flag en `channel.breakers`) conduce
    sólo si su flag está en `active_flags` (acople 2-vías). Un componente se energiza sólo si contiene ≥1 fuente
    `S`. Determinista y función PURA de `active_flags` (por eso couple.py puede cachear por subconjunto de flags).

    MODELO DE SOBRECARGA (por-componente, opt-in local): un componente se chequea por capacidad sólo si ALGUNA
    de sus fuentes tiene `@capacity` (si ninguna la tiene → capacidad infinita = pura conectividad, idéntico al
    comportamiento anterior). Un componente CAPADO se energiza sólo si `sum(capacidad de sus S) ≥ sum(consumo de
    sus L)` (cada carga consume `@demand` o 1 por default). Si el circuito pide de más:
      - sin `@priority` en sus cargas → la PROTECCIÓN lo DESENERGIZA entero (all-or-nothing, breaker tonto).
      - con `@priority` en alguna carga → LOAD-SHEDDING graceful (panel inteligente): se recorren las cargas de
        MAYOR a menor prioridad (desempate por coord) y se mantiene alimentada cada una que ENTRE en la capacidad
        restante; las demás se tiran. Greedy determinista O(n log n) — NO es subset-sum (no optimiza el subconjunto,
        rellena por prioridad). Los cables/fuentes siguen energizados; sólo las cargas tiradas quedan sin potencia.
    El gating por componente (no global) impide el CONTAGIO: un `@capacity` en un circuito NO afecta a otros.

    OJO — NO-MONOTONICIDAD: cerrar un `@breaker` MERGEA componentes, así que puede sumar demanda a un circuito
    capado y APAGAR una carga que antes estaba prendida. Es correcto (el oráculo lo modela) y el BFS de nav lo
    explora igual (toggle XOR), pero crea una familia de deadlocks (cerrar el breaker que sobrecarga el circuito
    que te lleva al breaker). Sigue siendo función PURA de `active_flags` → el cache de couple.py no se rompe."""
    def conducts(cell: Cell) -> bool:
        flag = channel.breakers.get(cell)
        return flag is None or flag in active_flags
    live = {c for c in channel.wires if conducts(c)}
    energized: set[Cell] = set()
    seen: set[Cell] = set()
    for root in live:
        if root in seen:
            continue
        comp: list[Cell] = []                              # el componente conexo de `root`
        stack = [root]
        seen.add(root)
        while stack:
            x, y, z = stack.pop()
            comp.append((x, y, z))
            for dx, dy in _DIRS:
                nb = (x + dx, y + dy, z)
                if nb in live and nb not in seen:
                    seen.add(nb)
                    stack.append(nb)
        comp_sources = [c for c in comp if c in channel.sources]
        if not comp_sources:                               # sin fuente → apagado
            continue
        if any(s in channel.caps for s in comp_sources):   # el circuito OPTÓ por el modelo de capacidad (local)
            # OJO (footgun): una fuente del componente SIN @capacity aporta capacidad ∞ → "des-capa" el circuito
            # entero (nunca sobrecarga). Si querés que el cap muerda, capá TODAS las fuentes del componente.
            total_cap = sum(channel.caps.get(s, float("inf")) for s in comp_sources)
            comp_loads = [l for l in comp if l in channel.loads]
            total_demand = sum(channel.demands.get(l, 1) for l in comp_loads)
            if total_demand > total_cap:                   # SOBRECARGA
                if not any(l in channel.priorities for l in comp_loads):
                    continue                               # sin prioridades → protección apaga todo (all-or-nothing)
                # LOAD-SHEDDING greedy: mantené las cargas de mayor prioridad que entren en la capacidad
                remaining = total_cap
                kept: set[Cell] = set()
                for l in sorted(comp_loads, key=lambda c: (-channel.priorities.get(c, 0), c)):
                    d = channel.demands.get(l, 1)
                    if d <= remaining:
                        kept.add(l)
                        remaining -= d
                energized.update(c for c in comp if c not in channel.loads or c in kept)  # cables sí, cargas tiradas no
                continue
        energized.update(comp)
    return energized


def all_powered(channel: ElectricChannel, active_flags: frozenset = frozenset()) -> dict[str, Any]:
    """Oráculo del canal eléctrico: ¿toda carga `L` está alimentada por una fuente `S` vía cables?
    `ok`=True sólo si TODA `L` está energizada (y hay al menos una `S`). `active_flags` = breakers cerrados.
    Determinista (BFS)."""
    if not channel.sources:
        return {"ok": False, "reason": "sin fuente S", "powered": [], "unpowered": sorted(channel.loads),
                "n_sources": 0, "n_loads": len(channel.loads)}
    energized = _powered_cells(channel, active_flags)
    powered = sorted(l for l in channel.loads if l in energized)
    unpowered = sorted(l for l in channel.loads if l not in energized)
    return {"ok": not unpowered, "powered": powered, "unpowered": unpowered,
            "n_sources": len(channel.sources), "n_loads": len(channel.loads)}


def powered_loads(channel: ElectricChannel, active_flags: frozenset = frozenset()) -> set[Cell]:
    """Conjunto de cargas `L` alimentadas dado qué breakers están cerrados (`active_flags`). El gancho del
    ACOPLE cross-aspecto: una compuerta de nav que sólo abre si su carga está energizada → gatear con esto."""
    energized = _powered_cells(channel, active_flags)
    return {l for l in channel.loads if l in energized}


def electric_markers(channel: ElectricChannel | None) -> dict[str, Any]:
    """Plan JSON-safe del canal eléctrico para RENDERIZARLO en los motores (paridad Godot/Unreal): fuentes,
    cargas (con su estado de potencia INICIAL = breakers abiertos), cables y breakers, en coords (x,y,z). El
    estado inicial es el correcto para mapas de una vía (determinista); en los de dos vías las cargas arrancan
    apagadas hasta que el jugador cierre el breaker (render dinámico = próximo paso). Vacío si no hay canal."""
    if channel is None:
        return {"sources": [], "loads": [], "wires": [], "breakers": []}
    energized = _powered_cells(channel, frozenset())          # estado inicial (sin breakers cerrados)
    plain_wires = sorted(channel.wires - channel.sources - channel.loads - set(channel.breakers))
    return {
        "sources": [list(s) for s in sorted(channel.sources)],
        "loads": [[x, y, z, (x, y, z) in energized] for (x, y, z) in sorted(channel.loads)],
        "wires": [list(w) for w in plain_wires],
        "breakers": [[x, y, z, channel.breakers[(x, y, z)]] for (x, y, z) in sorted(channel.breakers)],
    }


def render_electric_channel(channel: ElectricChannel) -> list[str]:
    """`ElectricChannel` → líneas del DSL (inversa de `parse_electric_channel`). Round-trip estable."""
    out: list[str] = []
    for z in sorted(channel.grid):
        out.append(f"[Electrico {z}]")
        out.extend(channel.grid[z])
    for (x, y, z), flag in sorted(channel.breakers.items()):
        out.append(f"@breaker {x},{y},{z} {flag}")
    for (x, y, z), n in sorted(channel.caps.items()):
        out.append(f"@capacity {x},{y},{z} {n}")
    for (x, y, z), n in sorted(channel.demands.items()):
        out.append(f"@demand {x},{y},{z} {n}")
    for (x, y, z), n in sorted(channel.priorities.items()):
        out.append(f"@priority {x},{y},{z} {n}")
    return out
