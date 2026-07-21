"""Maze 3D / vertical (E2 del eje estructural) — Capa 0 pura, verificable por BFS.

Prueba EL INSIGHT DEL GRAFO: el espacio es un GRAFO de celdas y el oráculo de winnability (BFS) es
AGNÓSTICO DEL EMBEDDING. Subir un piso no es geometría: es una ARISTA EN Z. Por eso la verticalidad
sale "gratis" y verificable — no la inyectamos, la MEDIMOS desde afuera (igual que `descriptors.py`
mide los mazes 2D y `gameenv/metrics.reachability` decide ganabilidad).

Modelo: un maze multi-piso = lista de pisos (cada piso un grid de chars 2D, misma convención que
`mazes/spec.py`: `#`=muro, `P`=player, `G`=goal, ` `/`.`=pasillo) + **conectores verticales**
(`#elemento "enlace vertical"` del catálogo): el char `H` (hueco/escalera) marca una celda transitable
que además **enlaza con la misma (x,y) del piso de arriba** (arista z↔z+1). El grafo resultante:
  - aristas horizontales: 4-dir dentro de un piso entre celdas transitables (como hoy).
  - aristas verticales: por cada conector (x,y,z), arista (x,y,z)↔(x,y,z+1) SI ambas celdas son
    transitables (si arriba hay muro, el hueco está tapado → sin arista; el BFS lo gatea solo).

`solve_3d` corre el BFS sobre ese grafo (mismo contrato que `reachability`: solvable True/False/None +
optimal_steps). `maze3d_descriptors` mide las dimensiones VERTICALES que la emergencia puede llenar.
"""
from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field, replace
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from src.jamscript.parser import JamSpec

WALL, PLAYER, GOAL, OPEN, CONNECTOR = "#", "P", "G", ".", "H"
_DIRS = [(1, 0), (-1, 0), (0, 1), (0, -1)]
# Escalera direccional: la flecha = dirección de ASCENSO en el plano (subís un piso moviéndote así).
# N=norte(-y, ^), S=sur(+y, v), E=este(+x, >), O=oeste(-x, <). El tope queda diagonal-arriba.
_STAIR_DELTA = {"N": (0, -1), "S": (0, 1), "E": (1, 0), "W": (-1, 0)}
# GRAVEDAD (mapas no-euclidianos): la dirección de "hacia dónde caen las cosas". 6 ejes; al entrar a la
# zona caés CONTINUO en esa dirección hasta una superficie. Distintas zonas = distinto "abajo".
_GRAV_DELTA = {"down": (0, 0, -1), "up": (0, 0, 1), "north": (0, -1, 0), "south": (0, 1, 0),
               "east": (1, 0, 0), "west": (-1, 0, 0)}

# transitable = cualquier char que no sea muro (espacio en blanco también cuenta como pasillo)
_BLOCKED = {WALL}


def _is_open_char(ch: str) -> bool:
    return ch not in _BLOCKED


@dataclass
class Maze3D:
    """Maze multi-piso como GRAFO de celdas (x,y,z).

    `floors[z]` = grid del piso z (lista de filas de chars). `connectors` = set de (x,y,z) donde hay
    una arista vertical entre el piso z y el z+1 en esa columna. `portals` = lista de aristas DIRIGIDAS
    (src→dst) entre celdas ARBITRARIAS (no-adyacentes, "no-euclidiano": E3 del eje estructural); un
    portal bidireccional son dos entradas (a→b y b→a). Construir con `from_layers` (parsea el char `H`
    a conectores) o pasando `connectors`/`portals` explícitos (uso programático); `add_portal` ayuda."""
    floors: list[list[str]]
    connectors: set[tuple[int, int, int]] = field(default_factory=set)
    portals: list[tuple[tuple[int, int, int], tuple[int, int, int]]] = field(default_factory=list)
    gravity: dict[tuple[int, int, int], str] = field(default_factory=dict)
    stairs: dict[tuple[int, int, int], str] = field(default_factory=dict)   # celda→dir (N/S/E/W): escalera direccional
    keys: dict[tuple[int, int, int], str] = field(default_factory=dict)     # celda→id: llave (pickup, prende un flag)
    doors: dict[tuple[int, int, int], str] = field(default_factory=dict)    # celda→id: puerta (transitable sólo con la llave)
    switches: dict[tuple[int, int, int], str] = field(default_factory=dict) # celda→flag: botón que TOGGLEA un flag de mundo
    gates: dict[tuple[int, int, int], str] = field(default_factory=dict)    # celda→flag: compuerta transitable sólo si el flag está ON
    hazards: dict[tuple[int, int, int], str] = field(default_factory=dict)  # celda→flag: TRAMPA MORTAL (entrar = DERROTA); ""=siempre, flag=mortal mientras ese flag esté OFF (un switch lo desarma)
    ladders: set[tuple[int, int, int]] = field(default_factory=set)         # celda con ESCALERA VERTICAL trepable (estilo terraza): misma arista z↔z+1 que el conector, pero se trepa de frente (render/feel distinto)
    conduits: set[tuple[int, int, int]] = field(default_factory=set)        # celda CONDUCTO (pasaje de techo bajo, hay que agacharse): celda abierta normal en el grafo (no gatea winnability — el crouch siempre está); render/feel
    seams: list[tuple[tuple[int, int, int], tuple[int, int, int], str]] = field(default_factory=list)  # COSTURA IMPOSIBLE: arista CONTINUA (a↔b) que pretende seamlessness en una dirección (N/S/E/O/up/down); como arista del grafo se transita igual que un portal (bidireccional), pero declara CONTINUIDAD → puede volver el espacio NO-EUCLIDIANO (no-embebible). La winnability la mide el BFS; la imposibilidad la mide graph_embeddability (holonomía)

    @classmethod
    def from_layers(cls, floors: list[list[str]],
                    extra_connectors: set[tuple[int, int, int]] | None = None) -> "Maze3D":
        """Construye desde una lista de pisos. Cada `H` (hueco/escalera) en (x,y) del piso z agrega
        un conector z↔z+1 en esa columna. `extra_connectors` se mergea (conectores sin char propio)."""
        connectors: set[tuple[int, int, int]] = set(extra_connectors or set())
        for z, grid in enumerate(floors):
            for y, row in enumerate(grid):
                for x, ch in enumerate(row):
                    if ch == CONNECTOR:
                        connectors.add((x, y, z))
        return cls(floors=floors, connectors=connectors)

    # ── geometría del grafo ──────────────────────────────────────────────────
    @property
    def n_floors(self) -> int:
        return len(self.floors)

    @property
    def width(self) -> int:
        return max((len(row) for grid in self.floors for row in grid), default=0)

    @property
    def height(self) -> int:
        return max((len(grid) for grid in self.floors), default=0)

    def char_at(self, x: int, y: int, z: int) -> str:
        if z < 0 or z >= len(self.floors):
            return WALL
        grid = self.floors[z]
        if y < 0 or y >= len(grid):
            return WALL
        row = grid[y]
        if x < 0 or x >= len(row):
            return WALL
        return row[x]

    def is_open(self, x: int, y: int, z: int) -> bool:
        """¿La celda (x,y,z) es transitable? (existe y no es muro)."""
        return _is_open_char(self.char_at(x, y, z))

    def stair_shafts(self) -> set[tuple[int, int, int]]:
        """Celdas-POZO: la celda directamente SOBRE la base de cada escalera direccional. El render la
        abre como hueco (para que la cabeza del player suba la rampa sin chocar el techo del piso de
        arriba); en el GRAFO no es transitable (te caerías al piso de abajo) → el BFS no rutea por ahí.
        Así el grafo verificado y el build jugable COINCIDEN (anti-inyección): una escalera direccional
        cuesta 2 celdas del piso de arriba (este pozo + el descanso diagonal donde emergés)."""
        return {(x, y, z + 1) for (x, y, z) in self.stairs}

    def open_cells(self) -> set[tuple[int, int, int]]:
        return {
            (x, y, z)
            for z in range(self.n_floors)
            for y in range(len(self.floors[z]))
            for x in range(len(self.floors[z][y]))
            if _is_open_char(self.floors[z][y][x])
        }

    def neighbors(self, cell: tuple[int, int, int]) -> list[tuple[int, int, int]]:
        """Vecinos en el grafo: 4-dir horizontal + verticales por conectores (ambos extremos abiertos)."""
        x, y, z = cell
        out: list[tuple[int, int, int]] = []
        for dx, dy in _DIRS:
            # no se entra a una celda-POZO (sobre la base de una escalera): es un hueco, te caerías.
            # El BFS la trata como no-transitable → coincide con el build (donde no hay piso ahí).
            if self.is_open(x + dx, y + dy, z) and (x + dx, y + dy, z - 1) not in self.stairs:
                out.append((x + dx, y + dy, z))
        # arista vertical hacia arriba: conector O escalera vertical en (x,y,z) → z+1
        if ((x, y, z) in self.connectors or (x, y, z) in self.ladders) and self.is_open(x, y, z + 1):
            out.append((x, y, z + 1))
        # arista vertical hacia abajo: conector/escalera en (x,y,z-1) (el de abajo apunta a este) → z-1
        if ((x, y, z - 1) in self.connectors or (x, y, z - 1) in self.ladders) and self.is_open(x, y, z - 1):
            out.append((x, y, z - 1))
        # aristas por PORTAL: arista DIRIGIDA src→dst entre celdas arbitrarias (no-euclidiano, E3).
        # one-way por construcción: solo la entrada src→dst está en la lista (la inversa, si existe,
        # es otra entrada). El BFS recorre esta arista como cualquier otra → winnability medida igual.
        for src, dst in self.portals:
            if src == (x, y, z) and self.is_open(*dst):
                out.append(dst)
        # COSTURAS IMPOSIBLES (E4): arista CONTINUA bidireccional a↔b. Para el BFS es una arista más
        # (la winnability se mide igual); su "imposibilidad" (no-euclidianidad) la mide graph_embeddability.
        for a, b, _dir in self.seams:
            if a == (x, y, z) and self.is_open(*b):
                out.append(b)
            elif b == (x, y, z) and self.is_open(*a):
                out.append(a)
        # GRAVEDAD (E4, no-euclidiano): en una zona de gravedad caés CONTINUO en su dirección hasta una
        # superficie. Arista dirigida (x,y,z)→aterrizaje (one-way: caés, no volvés salvo otra arista).
        g_dir = self.gravity.get((x, y, z))
        if g_dir is not None:
            land = self._fall_landing((x, y, z), g_dir)
            if land != (x, y, z):
                out.append(land)
        # ESCALERAS DIRECCIONALES: subo en la dirección de la flecha al piso de arriba (tope diagonal);
        # bajo si esta celda es el TOPE de alguna escalera. Bidireccional, gateado por celdas abiertas.
        sd = self.stairs.get((x, y, z))
        if sd is not None:
            dx, dy = _STAIR_DELTA[sd]
            top = (x + dx, y + dy, z + 1)
            if self.is_open(*top):
                out.append(top)
        for base, bd in self.stairs.items():
            dx, dy = _STAIR_DELTA[bd]
            if (base[0] + dx, base[1] + dy, base[2] + 1) == (x, y, z) and self.is_open(*base):
                out.append(base)
        return out

    def _fall_landing(self, cell: tuple[int, int, int], direction: str) -> tuple[int, int, int]:
        """Aterrizaje de una caída CONTINUA desde `cell` en `direction`: avanza mientras la próxima
        celda sea transitable; devuelve la última transitable (la superficie). Si no puede avanzar,
        devuelve `cell` (estás apoyado)."""
        dx, dy, dz = _GRAV_DELTA[direction]
        x, y, z = cell
        while self.is_open(x + dx, y + dy, z + dz):
            x, y, z = x + dx, y + dy, z + dz
        return (x, y, z)

    def find(self, ch: str) -> tuple[int, int, int] | None:
        for z in range(self.n_floors):
            for y, row in enumerate(self.floors[z]):
                x = row.find(ch)
                if x != -1:
                    return (x, y, z)
        return None


def _deadly(maze: Maze3D, cell: tuple[int, int, int], flags: frozenset) -> bool:
    """¿Pisar `cell` es MORTAL bajo el estado de mundo `flags`? Una trampa es mortal siempre (flag "")
    o mientras su flag esté OFF (un switch homónimo la DESARMA al prenderlo: flag ON = segura). Simétrica
    a la compuerta (que se ABRE con el flag ON): el mismo botón puede abrir una puerta y desactivar una trampa."""
    if cell not in maze.hazards:
        return False
    f = maze.hazards[cell]
    return f == "" or f not in flags


def solve_3d(maze: Maze3D, max_states: int = 200_000, *,
             flags0: frozenset = frozenset()) -> dict[str, Any]:
    """BFS de winnability sobre el grafo 3D, desde `P` hasta `G`. Mismo contrato que
    `gameenv/metrics.reachability`:

      solvable: True (hay camino) | False (espacio agotado, no hay) | None (presupuesto excedido).
      optimal_steps: largo del camino más corto, o None.
      path: lista de celdas (x,y,z) del camino óptimo, o [] si no hay.
      states_explored: celdas expandidas.

    `flags0` = flags de mundo ON desde el arranque (canal aparte, no toggleables por el jugador): el ACOPLE
    cross-aspecto los usa (ej. el canal ELÉCTRICO deja ON el flag de cada `@gate` cuya carga está alimentada).
    """
    start = maze.find(PLAYER)
    goal = maze.find(GOAL)
    empty: frozenset = frozenset()
    if start is None or goal is None or _deadly(maze, start, flags0):
        return {"solvable": False, "optimal_steps": None, "path": [], "states_explored": 0,
                "keys_at_goal": empty}

    def _collect(cell: tuple[int, int, int], held: frozenset) -> frozenset:
        return held | {maze.keys[cell]} if cell in maze.keys else held

    def _toggle(cell: tuple[int, int, int], flags: frozenset) -> frozenset:
        return flags ^ {maze.switches[cell]} if cell in maze.switches else flags

    # ESTADO = (celda, inventario de llaves, flags de MUNDO). Puerta=llave (inventario, permanente);
    # gate=flag de mundo (un switch lo togglea on↔off). Sin nada de esto degenera al BFS de celdas.
    # `flags0` arranca prendido (canal externo, ej. eléctrico) — los switches togglean sobre eso.
    start_state = (start, _collect(start, flags0), flags0)
    prev: dict = {start_state: None}
    queue: deque = deque([start_state])
    explored = 0

    while queue and explored < max_states:
        cur = queue.popleft()
        cell, held, flags = cur
        if cell == goal:
            path = [s[0] for s in _reconstruct(prev, cur)]
            return {"solvable": True, "optimal_steps": len(path) - 1,
                    "path": path, "states_explored": explored, "keys_at_goal": held}
        explored += 1
        for nxt in maze.neighbors(cell):
            if nxt in maze.doors and maze.doors[nxt] not in held:
                continue                                  # puerta cerrada: falta la llave
            if nxt in maze.gates and maze.gates[nxt] not in flags:
                continue                                  # compuerta cerrada: su flag está OFF
            if _deadly(maze, nxt, flags):
                continue                                  # trampa mortal armada: entrar = DERROTA → poda
            ns = (nxt, _collect(nxt, held), _toggle(nxt, flags))
            if ns not in prev:
                prev[ns] = cur
                queue.append(ns)

    solvable = False if explored < max_states else None
    return {"solvable": solvable, "optimal_steps": None, "path": [], "states_explored": explored,
            "keys_at_goal": empty}


def _reconstruct(prev: dict, goal):
    """Reconstruye la cadena de NODOS (estados o celdas) desde el inicio hasta `goal` via `prev`."""
    path = [goal]
    node = goal
    while prev[node] is not None:
        node = prev[node]
        path.append(node)
    path.reverse()
    return path


def add_portal(maze: Maze3D, a: tuple[int, int, int], b: tuple[int, int, int], *,
               one_way: bool = False) -> Maze3D:
    """Agrega un portal (arista DIRIGIDA) `a → b` al grafo del maze. Por default es bidireccional
    (agrega también `b → a`); `one_way=True` deja solo `a → b` (no se puede volver por el portal).
    Muta y devuelve el maze (para encadenar). El portal une celdas ARBITRARIAS — la winnability que
    abre se MIDE con `solve_3d`, no se inyecta (E3: aristas no-euclidianas verificables gratis)."""
    maze.portals.append((a, b))
    if not one_way:
        maze.portals.append((b, a))
    return maze


def add_seam(maze: Maze3D, a: tuple[int, int, int], b: tuple[int, int, int],
             direction: str = "north") -> Maze3D:
    """Agrega una COSTURA IMPOSIBLE entre `a` y `b`: una arista CONTINUA (transitable como un portal
    bidireccional) que pretende SEAMLESSNESS en `direction` (caminás hacia `direction` en `a` y emergés
    en `b` siguiendo). Si esa continuidad CONTRADICE la geometría de la grilla (cierra un ciclo con
    desplazamiento neto ≠ 0), el espacio se vuelve NO-EUCLIDIANO — lo MIDE `graph_embeddability`
    (E4: lo imposible es gratis y verificable). Muta y devuelve el maze."""
    if direction not in _GRAV_DELTA:
        raise ValueError(f"direccion de costura invalida: {direction!r} ({'/'.join(_GRAV_DELTA)})")
    maze.seams.append((a, b, direction))
    return maze


def graph_embeddability(maze: Maze3D) -> dict[str, Any]:
    """¿El grafo de traversal es EMBEBIBLE en un 3D euclidiano consistente, o tiene COSTURAS IMPOSIBLES?

    Propaga una posición por celda siguiendo el desplazamiento REAL de cada arista CONTINUA: grilla y
    enlaces verticales (conector/escalera) tienen delta = diferencia de coordenadas (siempre
    consistentes); una COSTURA impone un paso UNIDAD en su dirección. Una costura que cierra un ciclo con
    desplazamiento neto ≠ 0 = HOLONOMÍA no trivial = el espacio NO se puede dibujar plano (no-euclidiano).
    Portales y gravedad NO cuentan: son saltos DISCONTINUOS (no pretenden continuidad → no restringen la
    geometría). Union-find con offset vectorial. Devuelve {embeddable, n_seams, impossible_seams}."""
    parent: dict[tuple[int, int, int], tuple[int, int, int]] = {}
    off: dict[tuple[int, int, int], tuple[int, int, int]] = {}   # off[c] = pos[parent[c]] − pos[c]

    def find(c):                                                  # → (raíz, pos[raíz] − pos[c])
        if c not in parent:
            parent[c] = c; off[c] = (0, 0, 0)
            return c, (0, 0, 0)
        acc, node = (0, 0, 0), c
        while parent[node] != node:
            acc = (acc[0] + off[node][0], acc[1] + off[node][1], acc[2] + off[node][2])
            node = parent[node]
        return node, acc

    def union(a, b, delta) -> bool:                              # asegura pos[b] − pos[a] = delta
        ra, da = find(a)                                         # da = pos[ra] − pos[a]
        rb, db = find(b)                                         # db = pos[rb] − pos[b]
        if ra == rb:
            got = (da[0] - db[0], da[1] - db[1], da[2] - db[2])  # = pos[b] − pos[a] actual
            return got == delta
        parent[rb] = ra                                         # off[rb] = pos[ra] − pos[rb] = da − delta − db
        off[rb] = (da[0] - delta[0] - db[0], da[1] - delta[1] - db[1], da[2] - delta[2] - db[2])
        return True

    # 1) aristas CONTINUAS de la grilla / verticales (delta = diferencia real → nunca chocan entre sí)
    for c in maze.open_cells():
        x, y, z = c
        for dx, dy in _DIRS:
            n = (x + dx, y + dy, z)
            if maze.is_open(*n):
                union(c, n, (dx, dy, 0))
        if (c in maze.connectors or c in maze.ladders) and maze.is_open(x, y, z + 1):
            union(c, (x, y, z + 1), (0, 0, 1))
        sd = maze.stairs.get(c)
        if sd is not None:
            dx, dy = _STAIR_DELTA[sd]
            top = (x + dx, y + dy, z + 1)
            if maze.is_open(*top):
                union(c, top, (dx, dy, 1))
    # 2) COSTURAS: paso unidad en su dirección; la que NO cierra consistente = imposible (no-euclidiana)
    impossible = 0
    for a, b, direction in maze.seams:
        if not (maze.is_open(*a) and maze.is_open(*b)):
            continue
        if not union(a, b, _GRAV_DELTA[direction]):
            impossible += 1
    return {"embeddable": impossible == 0, "n_seams": len(maze.seams), "impossible_seams": impossible}


def add_gravity_zone(maze: Maze3D, cells: set[tuple[int, int, int]], direction: str = "down") -> Maze3D:
    """Marca una zona de gravedad (E4, no-euclidiano): en `cells` caés CONTINUO en `direction`
    (down/up/north/south/east/west) hasta una superficie. Muta y devuelve el maze."""
    if direction not in _GRAV_DELTA:
        raise ValueError(f"direccion de gravedad invalida: {direction!r} ({'/'.join(_GRAV_DELTA)})")
    for c in cells:
        maze.gravity[c] = direction
    return maze


def add_stair(maze: Maze3D, cell: tuple[int, int, int], direction: str) -> Maze3D:
    """Agrega una escalera DIRECCIONAL en `cell`: subís en `direction` (N/S/E/W) al piso de arriba
    (tope = celda diagonal-arriba en esa dirección), bajás por la inversa. Muta y devuelve el maze.
    La winnability que abre se MIDE con `solve_3d` (no se inyecta)."""
    if direction not in _STAIR_DELTA:
        raise ValueError(f"direccion de escalera invalida: {direction!r} (N/S/E/W)")
    maze.stairs[cell] = direction
    return maze


def add_key(maze: Maze3D, cell: tuple[int, int, int], key_id: str) -> Maze3D:
    """Pone una LLAVE `key_id` en `cell`: al pisarla, prende su flag en el inventario (mecánica de
    progresión tipo Valve). Muta y devuelve el maze."""
    maze.keys[cell] = key_id
    return maze


def add_door(maze: Maze3D, cell: tuple[int, int, int], key_id: str) -> Maze3D:
    """Pone una PUERTA en `cell`, transitable SÓLO si tenés la llave `key_id`. La celda debe ser
    transitable en la grilla (la puerta gatea el paso desde el ESTADO, no es un muro). El BFS keyed
    busca sobre (celda, llaves) → la winnability con gating se mide, no se inyecta."""
    maze.doors[cell] = key_id
    return maze


def add_switch(maze: Maze3D, cell: tuple[int, int, int], flag: str) -> Maze3D:
    """Pone un BOTÓN/SWITCH en `cell`: al pisarlo TOGGLEA el flag de mundo `flag` (on↔off, reversible).
    Controla compuertas remotas con el mismo flag (cableado tipo Valve). Muta y devuelve el maze."""
    maze.switches[cell] = flag
    return maze


def add_gate(maze: Maze3D, cell: tuple[int, int, int], flag: str) -> Maze3D:
    """Pone una COMPUERTA en `cell`, transitable SÓLO si el flag de mundo `flag` está ON (lo prende un
    switch homónimo). A diferencia de la puerta-con-llave, depende del ESTADO DE MUNDO, no del inventario."""
    maze.gates[cell] = flag
    return maze


def add_conduit(maze: Maze3D, cell: tuple[int, int, int]) -> Maze3D:
    """Marca `cell` como CONDUCTO: un pasaje de TECHO BAJO por el que hay que agacharse (estilo vent
    de Half-Life). En el grafo es una celda abierta normal (NO gatea winnability — el crouch siempre
    está disponible, así que el BFS la cruza); es render/feel: en Godot le pone un overhang bajo que
    bloquea al jugador parado y deja pasar al agachado. Muta y devuelve el maze."""
    maze.conduits.add(cell)
    return maze


def add_ladder(maze: Maze3D, cell: tuple[int, int, int]) -> Maze3D:
    """Pone una ESCALERA VERTICAL trepable (estilo terraza) en `cell`: agrega la arista z↔z+1 (igual que
    un conector, gateada por celdas abiertas) pero se trepa DE FRENTE (en Godot la subís como ladder, no
    como rampa). La winnability que abre la mide `solve_3d` (no se inyecta). Muta y devuelve el maze."""
    maze.ladders.add(cell)
    return maze


def add_hazard(maze: Maze3D, cell: tuple[int, int, int], flag: str = "") -> Maze3D:
    """Pone una TRAMPA MORTAL en `cell`: pisarla = DERROTA (estado terminal de pérdida, la otra mitad
    del MDP — ya no sólo "no llegás", podés PERDER). Con `flag` la trampa es CONDICIONAL: mortal mientras
    ese flag de mundo esté OFF, desarmada cuando un switch lo prende (laser-grid tipo Half-Life). Sin flag
    ("") es mortal siempre. El BFS busca el camino SEGURO (que no la pisa) → la winnability con riesgo se
    mide, no se inyecta. Muta y devuelve el maze."""
    maze.hazards[cell] = flag
    return maze


# ── NECESIDAD CONTRAFÁCTICA (interés / "entretenido"): una mecánica CUENTA sólo si quitarla rompe el
# nivel. Para cada mecánica presente, se NEUTRALIZA su efecto y se re-resuelve; es NECESARIA si el
# resultado óptimo cambia (se vuelve inganable, o el camino más corto cambia de largo). Mide diversión
# desde AFUERA (no inyecta diseño): una llave/puerta en línea (se agarra de paso) NO cuenta; una que
# obliga un DESVÍO sí. Primaria/secundaria queda para después: el desglose es POR TIPO. ──
# Mecánicas PRIMARIAS (estructura / progresión: gatean el avance o SON el camino) vs SECUNDARIAS
# (modificadores de riesgo/textura: condimentan pero no definen la topología). Una necesaria primaria
# pesa más en el interés que una secundaria. (conducto no entra: nunca gatea → no se testea.)
PRIMARY_MECHANICS = {"keys", "switches", "stairs", "ladders", "connectors", "portals", "gravity"}
SECONDARY_MECHANICS = {"hazards"}

_NEUTRALIZE = {
    "keys":       lambda m: replace(m, keys={}, doors={}),       # sin gating de inventario (puertas abiertas)
    "switches":   lambda m: replace(m, switches={}, gates={}),   # sin gating de mundo (compuertas abiertas)
    "hazards":    lambda m: replace(m, hazards={}),              # sin trampas mortales
    "stairs":     lambda m: replace(m, stairs={}),              # sin escaleras direccionales
    "portals":    lambda m: replace(m, portals=[]),             # sin portales
    "ladders":    lambda m: replace(m, ladders=set()),          # sin escaleras verticales
    "connectors": lambda m: replace(m, connectors=set()),       # sin conectores verticales
    "gravity":    lambda m: replace(m, gravity={}),             # sin zonas de gravedad
}


def _present_mechanics(maze: "Maze3D") -> list[str]:
    """Mecánicas cuyo CONSTRAINT existe en el maze (una llave sin puerta no gatea → no cuenta)."""
    flags = {
        "keys": bool(maze.doors), "switches": bool(maze.gates), "hazards": bool(maze.hazards),
        "stairs": bool(maze.stairs), "portals": bool(maze.portals), "ladders": bool(maze.ladders),
        "connectors": bool(maze.connectors), "gravity": bool(maze.gravity),
    }
    return [k for k, v in flags.items() if v]


def mechanic_necessity(maze: "Maze3D", max_states: int = 200_000) -> dict[str, Any]:
    """Test de necesidad contrafáctica de cada mecánica presente. Devuelve:
      present:    mecánicas cuyo constraint existe.
      necessary:  las que, al neutralizarse, CAMBIAN el resultado óptimo (winnability o largo) → importan.
      necessary_primary / necessary_secondary: las necesarias separadas por rol (estructura vs riesgo).
      decorative: presentes pero no necesarias (sacarlas no cambia nada → relleno).
      interest_score: PONDERADO = 2·(primarias necesarias) + 1·(secundarias necesarias). Premia que el
                      interés venga de la PROGRESIÓN, no sólo de condimento. 0 = paseo (nada importa).
      per_type:   {mecánica: bool necesaria}.
    Si el nivel no es ganable, interest_score 0 (no se puede medir interés sin solución)."""
    base = solve_3d(maze, max_states=max_states)
    present = _present_mechanics(maze)
    if base["solvable"] is not True:
        return {"present": present, "necessary": [], "necessary_primary": [], "necessary_secondary": [],
                "decorative": present, "interest_score": 0, "per_type": {m: False for m in present}}
    base_len = base["optimal_steps"]
    necessary: list[str] = []
    per_type: dict[str, bool] = {}
    for mech in present:
        r = solve_3d(_NEUTRALIZE[mech](maze), max_states=max_states)
        changed = (r["solvable"] is not True) or (r["optimal_steps"] != base_len)
        per_type[mech] = changed
        if changed:
            necessary.append(mech)
    decorative = [m for m in present if m not in necessary]
    necessary_primary = [m for m in necessary if m in PRIMARY_MECHANICS]
    necessary_secondary = [m for m in necessary if m in SECONDARY_MECHANICS]
    interest_score = 2 * len(necessary_primary) + len(necessary_secondary)
    return {"present": present, "necessary": necessary, "necessary_primary": necessary_primary,
            "necessary_secondary": necessary_secondary, "decorative": decorative,
            "interest_score": interest_score, "per_type": per_type}


def item_necessity(maze: "Maze3D", max_states: int = 200_000) -> dict[str, Any]:
    """Necesidad contrafáctica por ITEM INDIVIDUAL (no por tipo) → caza los items DESPARRAMADOS "sólo para
    decir que están". Para cada puerta/compuerta/trampa, la saca SOLA y re-resuelve: si el óptimo no cambia
    (ganable igual y mismo largo), ese item es DECORATIVO. Una llave es decorativa si todas las puertas que
    abre lo son (o no abre ninguna); un botón, si todas sus compuertas lo son. Un mapa LÓGICO tiene
    decorative_items == 0: cada item colocado IMPORTA. Devuelve {n_items, decorative_items, decorative_cells}."""
    base = solve_3d(maze, max_states=max_states)
    n_items = len(maze.doors) + len(maze.gates) + len(maze.hazards) + len(maze.keys) + len(maze.switches)
    if base["solvable"] is not True or n_items == 0:
        return {"n_items": n_items, "decorative_items": 0, "decorative_cells": []}
    base_len = base["optimal_steps"]

    def _dead(field: str, cell) -> bool:
        """¿Sacar SOLO el item en `cell` del campo `field` deja el óptimo igual? (→ decorativo)."""
        kept = {c: v for c, v in getattr(maze, field).items() if c != cell}
        r = solve_3d(replace(maze, **{field: kept}), max_states=max_states)
        return r["solvable"] is True and r["optimal_steps"] == base_len

    dec_cells: list[tuple[int, int, int]] = []
    door_dec = {c: _dead("doors", c) for c in maze.doors}     # puertas: gatean inventario
    gate_dec = {c: _dead("gates", c) for c in maze.gates}     # compuertas: gatean mundo
    for c, d in door_dec.items():
        if d:
            dec_cells.append(c)
    for c, d in gate_dec.items():
        if d:
            dec_cells.append(c)
    for c in maze.hazards:                                    # trampas: riesgo que (no) bloquea
        if _dead("hazards", c):
            dec_cells.append(c)
    for kc, kid in maze.keys.items():                         # llave decorativa = sólo abre puertas decorativas (o ninguna)
        opened = [dc for dc, k in maze.doors.items() if k == kid]
        if not opened or all(door_dec.get(dc, False) for dc in opened):
            dec_cells.append(kc)
    for sc, flag in maze.switches.items():                    # botón decorativo = sólo controla compuertas decorativas (o ninguna)
        controlled = [gc for gc, f in maze.gates.items() if f == flag]
        if not controlled or all(gate_dec.get(gc, False) for gc in controlled):
            dec_cells.append(sc)
    return {"n_items": n_items, "decorative_items": len(dec_cells), "decorative_cells": dec_cells}


def _manhattan3d(a: tuple[int, int, int], b: tuple[int, int, int]) -> int:
    return abs(a[0] - b[0]) + abs(a[1] - b[1]) + abs(a[2] - b[2])


def _normalize_layout(spec: "JamSpec") -> tuple[list[str], tuple[int, int] | None, tuple[int, int] | None]:
    """Traduce el layout 2D del JamSpec (chars arbitrarios + roles) a la convención canónica de Maze3D
    (`#`/`P`/`G`/`.`). Devuelve (grid_normalizado, pos_player, pos_goal). Cualquier char que no sea
    muro/player/goal (incl. el espacio) queda como pasillo `.`."""
    role_of = {s.name: s.role for s in spec.sprites}
    roles = {ch: role_of.get(name) for ch, name in spec.mapping.items()}
    grid: list[str] = []
    p_pos: tuple[int, int] | None = None
    g_pos: tuple[int, int] | None = None
    for y, row in enumerate(spec.layout):
        out = []
        for x, ch in enumerate(row):
            role = roles.get(ch)
            if role == "wall":
                out.append(WALL)
            elif role == "player":
                out.append(PLAYER)
                p_pos = (x, y)
            elif role == "goal":
                out.append(GOAL)
                g_pos = (x, y)
            else:
                out.append(OPEN)
        grid.append("".join(out))
    return grid, p_pos, g_pos


def stack_spec_vertical(spec: "JamSpec", n_floors: int = 3, *,
                        connector_cell: tuple[int, int] | None = None) -> Maze3D:
    """Apila el layout 2D de un JamSpec VERIFICADO en `n_floors` pisos, unidos por un conector vertical
    (shaft) piso-a-piso. NO inventa estructura: reusa la del maze ganable 2D y le agrega SOLO el eje Z,
    que sigue siendo verificable desde afuera por `solve_3d` (no inyectamos diseño, medimos winnability).

    Player en el piso 0, goal en el piso de arriba (`n_floors-1`), pisos intermedios = el mismo layout
    sin P/G. El conector va en una columna ABIERTA en todos los pisos (default: la del player, que por
    construcción es transitable en todos). Como cada piso comparte los mismos muros, una celda abierta
    en el piso base lo es en todos. Con `n_floors==1` degenera al maze 2D (P y G en el mismo piso)."""
    if n_floors < 1:
        raise ValueError("n_floors debe ser >= 1")
    base, p_pos, g_pos = _normalize_layout(spec)
    if p_pos is None or g_pos is None:
        raise ValueError("el spec necesita player (P) y goal (G) para apilar en vertical")
    if n_floors == 1:
        return Maze3D.from_layers([base])

    def _variant(keep_player: bool, keep_goal: bool) -> list[str]:
        rows = []
        for row in base:
            r = row
            if not keep_player:
                r = r.replace(PLAYER, OPEN)
            if not keep_goal:
                r = r.replace(GOAL, OPEN)
            rows.append(r)
        return rows

    floors: list[list[str]] = []
    for z in range(n_floors):
        floors.append(_variant(keep_player=(z == 0), keep_goal=(z == n_floors - 1)))

    cx, cy = connector_cell if connector_cell is not None else p_pos
    if not (0 <= cy < len(base) and 0 <= cx < len(base[cy]) and _is_open_char(base[cy][cx])):
        raise ValueError(f"connector_cell {(cx, cy)} no es una celda abierta del layout")
    connectors = {(cx, cy, z) for z in range(n_floors - 1)}
    return Maze3D.from_layers(floors, extra_connectors=connectors)


def portal_demo_from_spec(spec: "JamSpec", *, one_way: bool = True) -> Maze3D:
    """Demo de PORTAL (E3) sobre un elite real: un maze de un piso a partir del layout 2D ganable,
    + UN portal de atajo desde la celda del player hasta una celda abierta adyacente a la meta.
    No reescribe la estructura — el maze ya era ganable caminando; el portal es un atajo NO-EUCLIDIANO
    cuyo uso se MIDE (`solve_3d`/`portal_steps`), no se inyecta. One-way por default. Un piso."""
    base, p_pos, g_pos = _normalize_layout(spec)
    if p_pos is None or g_pos is None:
        raise ValueError("el spec necesita player (P) y goal (G) para el demo de portal")
    maze = Maze3D.from_layers([base])
    gx, gy = g_pos
    # destino: una celda abierta adyacente a la meta (no pisamos la meta misma); si no hay, la meta.
    dst = next(((gx + dx, gy + dy, 0) for dx, dy in _DIRS if maze.is_open(gx + dx, gy + dy, 0)),
               (gx, gy, 0))
    add_portal(maze, (p_pos[0], p_pos[1], 0), dst, one_way=one_way)
    return maze


def gravity_demo_from_spec(spec: "JamSpec") -> Maze3D:
    """Demo de GRAVEDAD (E4) sobre un elite real: un maze de dos pisos donde el player empieza
    arriba y la meta está abajo. Una zona de gravedad 'down' en la celda inicial permite la caída,
    haciendo ganable un goal que de otro modo sería inalcanzable (unidirectional)."""
    base, p_pos, g_pos = _normalize_layout(spec)
    if p_pos is None or g_pos is None:
        raise ValueError("el spec necesita player (P) y goal (G) para el demo de gravedad")
    f0 = [row.replace(PLAYER, OPEN) for row in base]
    f1 = [row.replace(GOAL, OPEN) for row in base]
    maze = Maze3D.from_layers([f0, f1])
    # Habilitar caída desde la posición inicial del player en el piso de arriba
    add_gravity_zone(maze, {(p_pos[0], p_pos[1], 1)}, "down")
    return maze


def _liminal3d(maze: Maze3D) -> dict[str, Any]:
    """Descriptores liminales (habilidad D) medidos sobre el Maze3D, por piso y agregados (la versión
    3D de `mazes/liminal.py`): room_ness (salas vs pasillos), sightline (visión recta más larga),
    sameness (repetitividad del tejido = falta de hitos). Pura medición desde afuera."""
    total_open = room_cells = sightline = 0
    patches: set = set()
    for grid in maze.floors:
        h = len(grid)

        def _open(x: int, y: int, g=grid, hh=h) -> bool:
            return 0 <= y < hh and 0 <= x < len(g[y]) and g[y][x] != WALL

        opens = [(x, y) for y in range(h) for x in range(len(grid[y])) if grid[y][x] != WALL]
        total_open += len(opens)
        for x, y in opens:
            if sum(_open(x + dx, y + dy) for dx, dy in _DIRS) >= 3:    # grado horizontal ≥3 = sala
                room_cells += 1
            patch = tuple(_open(x + dx, y + dy) for dy in (-1, 0, 1) for dx in (-1, 0, 1))
            patches.add(patch)
        w = max((len(r) for r in grid), default=0)
        for y in range(h):                                            # corridas horizontales
            run = 0
            for x in range(len(grid[y])):
                run = run + 1 if grid[y][x] != WALL else 0
                sightline = max(sightline, run)
        for x in range(w):                                            # corridas verticales (en el piso)
            run = 0
            for y in range(h):
                run = run + 1 if _open(x, y) else 0
                sightline = max(sightline, run)
    return {
        "room_ness": round(room_cells / total_open, 4) if total_open else 0.0,
        "sightline": sightline,
        "sameness":  round(max(0.0, 1 - len(patches) / total_open), 4) if total_open else 0.0,
    }


def maze3d_descriptors(maze: Maze3D, max_states: int = 200_000) -> dict[str, Any]:
    """Descriptores VERTICALES — las dimensiones que la verticalidad abre, medidas desde afuera:

      - solvable / solution_length: el GATE de winnability (BFS sobre el grafo 3D).
      - n_floors:    cuántos pisos tiene el espacio.
      - verticality: fracción de pasos del camino óptimo que son transiciones en Z (suben/bajan de
                     piso) / total de pasos. 0 = camino plano; alto = el camino trepa y desciende.
      - height_span: cuántos pisos abarca el camino óptimo (max z visitado − min z visitado).
      - n_connectors: cantidad de enlaces verticales del grafo (densidad del elemento "vertical").
      - n_portals:   aristas-portal dirigidas del grafo (E3; un portal bidireccional cuenta 2).
      - portal_span: distancia Manhattan-3D media de los portales (cuán "no-euclidianos" son: 0 si no
                     hay; alto = saltos largos entre celdas lejanas).
      - portal_steps: cuántos pasos del camino óptimo son saltos por portal (cuánto USA la solución la
                     no-euclidianidad). Cada salto = 1 paso aunque una el otro extremo del mapa.
      - n_gravity_cells: celdas con gravedad alterada.
      - gravity_flips:   cantidad de direcciones distintas presentes (0/1/2).
      - fall_steps:      cuántos pasos del camino óptimo son caídas por gravedad.
      - non_euclidean_steps: portal_steps + fall_steps.
    """
    res = solve_3d(maze, max_states=max_states)
    path: list[tuple[int, int, int]] = res["path"]
    steps = max(0, len(path) - 1)

    vertical_steps = sum(1 for a, b in zip(path, path[1:]) if a[2] != b[2])
    zs = [c[2] for c in path]
    height_span = (max(zs) - min(zs)) if zs else 0

    portal_set = set(maze.portals)
    portal_steps = sum(1 for a, b in zip(path, path[1:]) if (a, b) in portal_set)
    portal_span = (round(sum(_manhattan3d(s, d) for s, d in maze.portals) / len(maze.portals), 4)
                   if maze.portals else 0.0)

    fall_steps = sum(1 for a, b in zip(path, path[1:])
                     if a in maze.gravity and b == maze._fall_landing(a, maze.gravity[a]))
    n_gravity_cells = len(maze.gravity)
    gravity_flips = len(set(maze.gravity.values()))

    seam_pairs = {(a, b) for a, b, _ in maze.seams} | {(b, a) for a, b, _ in maze.seams}
    seam_steps = sum(1 for a, b in zip(path, path[1:]) if (a, b) in seam_pairs)
    emb = graph_embeddability(maze)
    non_euclidean_steps = portal_steps + fall_steps + seam_steps

    hazard_cells = set(maze.hazards)
    near_hazard_steps = sum(1 for c in path
                            if any((c[0] + dx, c[1] + dy, c[2]) in hazard_cells for dx, dy in _DIRS))

    nec = mechanic_necessity(maze, max_states=max_states)   # INTERÉS: qué mecánicas REALMENTE importan
    items = item_necessity(maze, max_states=max_states)     # COHERENCIA: items individuales que NO importan (relleno)

    return {
        "solvable":        res["solvable"],
        "solution_length": res["optimal_steps"],
        "n_floors":        maze.n_floors,
        "verticality":     round(vertical_steps / steps, 4) if steps else 0.0,
        "height_span":     height_span,
        "n_connectors":    len(maze.connectors),
        "n_ladders":       len(maze.ladders),
        "n_conduits":      len(maze.conduits),
        "n_portals":       len(maze.portals),
        "portal_span":     portal_span,
        "portal_steps":    portal_steps,
        "n_seams":         emb["n_seams"],                      # costuras imposibles declaradas
        "seam_steps":      seam_steps,                          # pasos del camino óptimo que cruzan una costura
        "embeddable":      emb["embeddable"],                   # ¿el espacio se puede dibujar plano? (False = NO-EUCLIDIANO)
        "impossibility_degree": emb["impossible_seams"],        # nº de costuras con holonomía no trivial (grado de imposibilidad)
        "n_gravity_cells": n_gravity_cells,
        "gravity_flips":   gravity_flips,
        "fall_steps":      fall_steps,
        "non_euclidean_steps": non_euclidean_steps,
        "n_keys":          len(maze.keys),
        "n_doors":         len(maze.doors),
        "lock_depth":      len(res.get("keys_at_goal", ())),    # llaves en mano al llegar = cuán gateado
        "n_switches":      len(maze.switches),
        "n_gates":         len(maze.gates),
        "n_hazards":       len(maze.hazards),
        "near_hazard_steps": near_hazard_steps,                 # pasos del camino seguro pegados a una trampa = TENSIÓN
        "interest_score":  nec["interest_score"],              # PONDERADO 2·primarias+1·secundarias (necesidad contrafáctica)
        "necessary_mechanics": nec["necessary"],               # las mecánicas que, sacadas, rompen el nivel
        "necessary_primary": nec["necessary_primary"],         # progresión que IMPORTA (estructura/gating)
        "necessary_secondary": nec["necessary_secondary"],     # riesgo/textura que IMPORTA (trampas)
        "decorative_mechanics": nec["decorative"],             # presentes pero relleno (sacarlas no cambia nada)
        "n_items":         items["n_items"],                   # items colocados (llaves/puertas/switches/compuertas/trampas)
        "decorative_items": items["decorative_items"],         # items INDIVIDUALES que no cambian el óptimo = DESPARRAMADOS
        "decorative_cells": items["decorative_cells"],         # dónde están (para el feedback al LLM)
        "open_cells":      len(maze.open_cells()),
        "states_explored": res["states_explored"],
        "dims":            [maze.width, maze.height, maze.n_floors],
        **_liminal3d(maze),                                    # room_ness / sightline / sameness (D)
    }
