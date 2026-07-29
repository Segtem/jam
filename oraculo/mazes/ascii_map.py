"""JamMap — el DSL de mapa de Capa 0: un minimapa ASCII roguelike que es a la vez PREVIEW y
LENGUAJE DE DISEÑO INTERPRETABLE (texto editable ↔ grafo `Maze3D`).

La idea (Brian): el minimapa no es un dibujo de solo-lectura — es un lenguaje intermedio. `render()`
serializa un `Maze3D` a texto; `parse()` lo vuelve a un `Maze3D`. Round-trip: mover un glifo en el
texto = mover el elemento en el grafo, y `solve_3d` re-verifica la ganabilidad. Es la encarnación de
"Capa 0 = DSL con el juego en su esencia matemática, probable en greybox" — un glifo por elemento,
toda la estructura compuesta de un vistazo, sin lanzar Godot.

Python PURO sobre el grafo. Elementos CELDA-LOCAL (muro/player/goal, escaleras, gravedad) viven en la
grilla; elementos NO-LOCALES (portales = aristas dirigidas entre celdas arbitrarias) viven en
directivas de cabecera `@portal ...` (no se pueden representar con un glifo por celda). Ambas partes
son editables a mano.

Formato:
    # comentario / leyenda (se ignora al parsear)
    @portal x,y,z -> x,y,z            ← portal bidireccional
    @portal x,y,z -> x,y,z one_way    ← arista dirigida
    @gravity x,y,z up                 ← gravedad invertida (la "down" se ve como ~ en la grilla)
    [Piso 0]
    #######
    #@..^.#
    #~...G#
    #######
    [Piso 1]
    ...
"""
from __future__ import annotations

import re
import string

from oraculo.mazes.maze3d import _STAIR_DELTA, GOAL, OPEN, PLAYER, WALL, Maze3D

# Un glifo por elemento celda-local. Escaleras DIRECCIONALES (^ sube, v baja); < > reservados para
# conectores horizontales/one-way en el plano (cuando el modelo los tenga).
G_WALL = "#"
G_OPEN = "."
G_PLAYER = "@"
G_GOAL = "G"
G_SHAFT = "H"           # conector vertical recto (se rendea como rampa fina caminable)
G_LADDER = "I"          # escalera VERTICAL trepable (estilo terraza; misma arista que H, se trepa de frente)
G_STAIR_TOP = "o"       # HUECO: el tope donde LLEGA una escalera/conector del piso de abajo
G_STAIR_SHAFT = "O"     # POZO de escalera direccional: hueco SOBRE la base (reservado, NO transitable: caés al piso de abajo)
G_SWITCH = "&"          # botón/switch (togglea un flag de mundo; el cableado va en @switch)
G_GATE = "="            # compuerta (transitable si su flag está ON; el flag va en @gate)
G_HAZARD = "X"          # trampa mortal (pisarla = DERROTA; condicional a un flag via @hazard)
G_CONDUIT = "c"         # conducto (pasaje de techo bajo: hay que agacharse; celda abierta en el grafo)
G_GRAVITY_DOWN = "~"    # zona de gravedad hacia abajo (la "up" va en cabecera @gravity)
G_PORTAL_IN = "Ω"       # boca de portal (ayuda visual; la arista vive en @portal)
G_PORTAL_OUT = "*"      # salida de portal
G_SEAM = "%"            # COSTURA IMPOSIBLE (ayuda visual en ambos extremos; la arista+dirección viven en @seam)

# Escaleras DIRECCIONALES: la flecha = dirección de ASCENSO en el plano (subís un piso moviéndote así).
# ^=norte sube, v=sur sube, >=este sube, <=oeste sube.
_STAIR_GLYPH = {"N": "^", "S": "v", "E": ">", "W": "<"}
_GLYPH_STAIR = {g: d for d, g in _STAIR_GLYPH.items()}

_LEGEND = [
    (G_PLAYER, "player"), (G_GOAL, "meta"), (G_WALL, "muro"), (G_OPEN, "pasillo"),
    ("^", "escalera sube↑N"), ("v", "sube↓S"), (">", "sube→E"), ("<", "sube←O"),
    (G_STAIR_TOP, "hueco (tope de escalera)"), (G_STAIR_SHAFT, "pozo de escalera (no se pisa)"),
    (G_SHAFT, "conector vertical"), (G_LADDER, "escalera vertical"),
    (G_GRAVITY_DOWN, "gravedad"),
    (G_PORTAL_IN, "portal entra"), (G_PORTAL_OUT, "portal sale"), (G_HAZARD, "trampa mortal"),
    (G_CONDUIT, "conducto (agacharse)"), (G_SEAM, "costura imposible (@seam)"),
]


# ── render: Maze3D → texto DSL ───────────────────────────────────────────────
def _is_stair_top(maze: Maze3D, cell: tuple[int, int, int]) -> bool:
    """¿En `cell` LLEGA una escalera (diagonal) o un conector vertical desde el piso de abajo? Si sí,
    se dibuja un hueco 'o' en vez de piso, para que la conexión entre pisos se VEA (legibilidad del DSL)."""
    x, y, z = cell
    if (x, y, z - 1) in maze.connectors or (x, y, z - 1) in maze.ladders:   # conector/escalera vertical que sube acá
        return True
    return any((sx + _STAIR_DELTA[sd][0], sy + _STAIR_DELTA[sd][1], sz + 1) == cell
               for (sx, sy, sz), sd in maze.stairs.items())


def glyph_at(maze: Maze3D, x: int, y: int, z: int) -> str:
    """Glifo de la celda por PRECEDENCIA: estructural-fijo (muro/player/goal) gana; luego elementos
    sobre celda abierta (escalera > portal > gravedad); si nada, pasillo."""
    ch = maze.char_at(x, y, z)
    if ch == WALL:
        return G_WALL
    if ch == PLAYER:
        return G_PLAYER
    if ch == GOAL:
        return G_GOAL
    cell = (x, y, z)
    sd = maze.stairs.get(cell)
    if sd is not None:
        return _STAIR_GLYPH[sd]
    if cell in maze.connectors:
        return G_SHAFT
    if cell in maze.ladders:
        return G_LADDER                        # escalera vertical trepable (se trepa de frente, no rampa)
    if (x, y, z - 1) in maze.stairs:           # POZO: directamente sobre la base de una escalera → hueco reservado (no se pisa)
        return G_STAIR_SHAFT
    if _is_stair_top(maze, cell):              # acá LLEGA una escalera/conector de abajo → hueco, no piso
        return G_STAIR_TOP
    for src, dst in maze.portals:
        if src == cell:
            return G_PORTAL_IN
        if dst == cell:
            return G_PORTAL_OUT
    if any(cell == a or cell == b for a, b, _ in maze.seams):   # extremo de costura imposible (la dirección va en @seam)
        return G_SEAM
    if cell in maze.gravity:
        return G_GRAVITY_DOWN
    if cell in maze.keys:
        return maze.keys[cell]                 # llave: su id en minúscula (a, b, c…)
    if cell in maze.doors:
        return maze.doors[cell].upper()        # puerta: el id en MAYÚSCULA (A requiere la llave a)
    if cell in maze.switches:
        return G_SWITCH                        # botón (el flag que togglea va en @switch)
    if cell in maze.gates:
        return G_GATE                          # compuerta (el flag que la abre va en @gate)
    if cell in maze.hazards:
        return G_HAZARD                        # trampa mortal (el flag que la desarma va en @hazard)
    if cell in maze.conduits:
        return G_CONDUIT                       # conducto (pasaje de techo bajo: agacharse)
    return G_OPEN


def render_floor(maze: Maze3D, z: int) -> list[str]:
    """Un piso a filas ASCII con los glifos de todos los elementos."""
    grid = maze.floors[z]
    width = max((len(row) for row in grid), default=0)
    return ["".join(glyph_at(maze, x, y, z) for x in range(width)) for y in range(len(grid))]


def ascii_floors(maze: Maze3D) -> list[list[str]]:
    """Todos los pisos como paneles (para que el dashboard los maquete como quiera)."""
    return [render_floor(maze, z) for z in range(maze.n_floors)]


def used_legend(maze: Maze3D) -> list[tuple[str, str]]:
    """Sólo los glifos que aparecen en este maze."""
    present = {glyph_at(maze, x, y, z)
               for z in range(maze.n_floors)
               for y in range(len(maze.floors[z]))
               for x in range(len(maze.floors[z][y]))}
    leg = [(g, name) for g, name in _LEGEND if g in present]
    if maze.keys:                                         # llaves/puertas: glifos variables (a/A, b/B…)
        leg.append(("a-z", "llave"))
    if maze.doors:
        leg.append(("A-Z", "puerta (su llave)"))
    if maze.switches:
        leg.append((G_SWITCH, "botón (@switch)"))
    if maze.gates:
        leg.append((G_GATE, "compuerta (@gate)"))
    if maze.hazards:
        leg.append((G_HAZARD, "trampa mortal (@hazard si es condicional)"))
    return leg


def _portal_directives(maze: Maze3D) -> list[str]:
    """Aristas-portal → directivas `@portal`. Detecta pares bidireccionales (a→b y b→a) para emitir
    una sola línea; el resto sale como one_way."""
    edges = set(maze.portals)
    seen: set = set()
    out: list[str] = []
    for a, b in maze.portals:
        if (a, b) in seen:
            continue
        if (b, a) in edges:
            out.append(f"@portal {a[0]},{a[1]},{a[2]} -> {b[0]},{b[1]},{b[2]}")
            seen.add((a, b)); seen.add((b, a))
        else:
            out.append(f"@portal {a[0]},{a[1]},{a[2]} -> {b[0]},{b[1]},{b[2]} one_way")
            seen.add((a, b))
    return out


def render(maze: Maze3D, *, legend: bool = True) -> str:
    """Serializa un `Maze3D` al DSL JamMap (texto editable, parseable de vuelta con `parse`)."""
    lines: list[str] = ["# JamMap DSL — Capa 0 (edita los glifos; se reinterpreta a un grafo verificable)"]
    lines += _portal_directives(maze)
    lines += [f"@gravity {x},{y},{z} {d}" for (x, y, z), d in sorted(maze.gravity.items()) if d != "down"]
    lines += [f"@seam {a[0]},{a[1]},{a[2]} -> {b[0]},{b[1]},{b[2]} {d}" for a, b, d in maze.seams]
    lines += [f"@switch {x},{y},{z} {f}" for (x, y, z), f in sorted(maze.switches.items())]
    lines += [f"@gate {x},{y},{z} {f}" for (x, y, z), f in sorted(maze.gates.items())]
    # trampa CONDICIONAL (flag != "") → cabecera; la mortal-siempre se ve sólo por su glifo X en la grilla
    lines += [f"@hazard {x},{y},{z} {f}" for (x, y, z), f in sorted(maze.hazards.items()) if f != ""]
    for z in range(maze.n_floors):
        lines.append(f"[Piso {z}]")
        lines += render_floor(maze, z)
    if legend:
        leg = used_legend(maze)
        if leg:
            lines.append("# " + "  ".join(f"{g}={name}" for g, name in leg))
    return "\n".join(lines)


# ── parse: texto DSL → Maze3D ────────────────────────────────────────────────
_CELL_RE = re.compile(r"(-?\d+)\s*,\s*(-?\d+)\s*,\s*(-?\d+)")
_PORTAL_RE = re.compile(r"@portal\s+(.+?)\s*->\s*(.+?)(\s+one_way)?\s*$")
_GRAVITY_RE = re.compile(r"@gravity\s+(.+?)\s+(down|up|north|south|east|west)\s*$")
_SEAM_RE = re.compile(r"@seam\s+(.+?)\s*->\s*(.+?)\s+(down|up|north|south|east|west)\s*$")
_SWITCH_RE = re.compile(r"@switch\s+(.+?)\s+(\S+)\s*$")
_GATE_RE = re.compile(r"@gate\s+(.+?)\s+(\S+)\s*$")
_HAZARD_RE = re.compile(r"@hazard\s+(.+?)\s+(\S+)\s*$")
_FLOOR_RE = re.compile(r"^\[Piso\s+(\d+)\]\s*$")
_SPACE_RE = re.compile(r"@space\s+(\w+)\s*$")
# llaves = minúsculas (id) salvo las reservadas; puertas = MAYÚSCULAS salvo las reservadas.
_KEY_CHARS = set(string.ascii_lowercase) - {"o", "v", "x", "c"}   # o=tope, v=escalera sur, x=trampa, c=conducto
_DOOR_CHARS = set(string.ascii_uppercase) - {"G", "H", "X", "I", "O"}  # G=meta, H=conector, X=trampa, I=escalera vertical, O=pozo de escalera
# una fila de grilla = SOLO glifos (incl. letras de llave/puerta + &/= switch/gate + X trampa + I escalera + c conducto + O pozo)
_GRID_CHARS = set("#.@G^v<>HIoO~Ω*%&=Xc ") | _KEY_CHARS | _DOOR_CHARS


def _cell(s: str) -> tuple[int, int, int]:
    m = _CELL_RE.search(s)
    if not m:
        raise ValueError(f"celda invalida: {s!r}")
    return (int(m[1]), int(m[2]), int(m[3]))


def parse_space(text: str) -> str | None:
    """La directiva `@space <tipo>` (cabecera): declara QUÉ tipo de espacio va a ser este esqueleto
    (hospital/school/…). Patrón canal: no toca el grafo nav — es el CONTRATO con JamPCG, y el oráculo
    lo gatea (vocabulario + `space_realizable` en eval_jammap; `program_satisfied` al materializar).
    None si el DSL no la declara."""
    for raw in text.splitlines():
        m = _SPACE_RE.match(raw.strip())
        if m:
            return m[1]
    return None


def parse(text: str) -> Maze3D:
    """Interpreta el DSL JamMap → `Maze3D`. Inversa de `render` (round-trip estable). Las escaleras
    se derivan del glifo `^` (el `v` es el landing, se lee como pasillo); los portales/gravity-up de
    las directivas de cabecera; la gravedad-down del glifo `~`."""
    portals: list[tuple[tuple[int, int, int], tuple[int, int, int]]] = []
    gravity: dict[tuple[int, int, int], str] = {}
    stairs: dict[tuple[int, int, int], str] = {}
    keys: dict[tuple[int, int, int], str] = {}
    doors: dict[tuple[int, int, int], str] = {}
    switches: dict[tuple[int, int, int], str] = {}
    gates: dict[tuple[int, int, int], str] = {}
    hazards: dict[tuple[int, int, int], str] = {}
    ladders: set[tuple[int, int, int]] = set()
    conduits: set[tuple[int, int, int]] = set()
    seams: list[tuple[tuple[int, int, int], tuple[int, int, int], str]] = []
    floors_map: dict[int, list[str]] = {}
    cur: int | None = None

    for raw in text.splitlines():
        line = raw.rstrip()
        s = line.strip()
        if not s:
            continue
        mf = _FLOOR_RE.match(s)
        if mf:
            cur = int(mf[1]); floors_map.setdefault(cur, [])
            continue
        if s.startswith("["):                  # OTRO canal ([Electrico], [Recurso]…): termina el piso nav
            cur = None                         # (sus filas no se slurpean a la grilla de navegación)
            continue
        if s.startswith("@portal"):
            mp = _PORTAL_RE.match(s)
            if mp:
                a, b, one_way = _cell(mp[1]), _cell(mp[2]), bool(mp[3])
                portals.append((a, b))
                if not one_way:
                    portals.append((b, a))
            cur = None
            continue
        if s.startswith("@gravity"):
            mg = _GRAVITY_RE.match(s)
            if mg:
                gravity[_cell(mg[1])] = mg[2]
            cur = None
            continue
        if s.startswith("@seam"):                 # COSTURA IMPOSIBLE: arista continua a↔b en una dirección
            mse = _SEAM_RE.match(s)
            if mse:
                seams.append((_cell(mse[1]), _cell(mse[2]), mse[3]))
            cur = None
            continue
        if s.startswith("@switch"):
            ms = _SWITCH_RE.match(s)
            if ms:
                switches[_cell(ms[1])] = ms[2]
            cur = None
            continue
        if s.startswith("@gate"):
            mt = _GATE_RE.match(s)
            if mt:
                gates[_cell(mt[1])] = mt[2]
            cur = None
            continue
        if s.startswith("@hazard"):              # trampa CONDICIONAL: la ata a un flag (mortal si OFF)
            mh = _HAZARD_RE.match(s)
            if mh:
                hazards[_cell(mh[1])] = mh[2]     # el header gana (el glifo X de la grilla queda como marcador)
            cur = None
            continue
        if s.startswith("@space"):               # tipo de espacio declarado (lo lee parse_space; acá sólo
            cur = None                           # cortamos el piso para que la línea no se slurpee como fila)
            continue
        if line.lstrip().startswith("# "):      # comentario/leyenda (hash + espacio): ignorar
            continue
        # fila de grilla SOLO si estamos en un piso y todo son glifos (si no, es comentario/leyenda)
        if cur is not None and all(c in _GRID_CHARS for c in line):
            floors_map[cur].append(line)

    if not floors_map:
        raise ValueError("el DSL no tiene ningun [Piso N]")

    # construir floors (chars canonicos) + conectores desde los glifos de la grilla
    n = max(floors_map) + 1
    floors: list[list[str]] = []
    connectors: set[tuple[int, int, int]] = set()
    for z in range(n):
        grid_rows = floors_map.get(z, [])
        out_rows: list[str] = []
        for y, row in enumerate(grid_rows):
            chars: list[str] = []
            for x, g in enumerate(row):
                if g == G_WALL:
                    chars.append(WALL)
                elif g == G_PLAYER:
                    chars.append(PLAYER)
                elif g == G_GOAL:
                    chars.append(GOAL)
                else:
                    chars.append(OPEN)          # escalera/portal/gravity/conector → celda transitable
                    if g in _GLYPH_STAIR:
                        stairs[(x, y, z)] = _GLYPH_STAIR[g]
                    elif g == G_SHAFT:
                        connectors.add((x, y, z))
                    elif g == G_LADDER:
                        ladders.add((x, y, z))           # escalera vertical trepable
                    elif g == G_CONDUIT:
                        conduits.add((x, y, z))          # conducto (techo bajo, agacharse)
                    elif g == G_STAIR_TOP:
                        pass                              # hueco decorativo (tope de escalera/conector): es pasillo
                    elif g == G_STAIR_SHAFT:
                        pass                              # POZO: se DERIVA de la escalera de abajo (stair_shafts); el glifo es visual
                    elif g == G_SEAM:
                        pass                              # COSTURA: la arista+dirección vienen del header @seam; el glifo es visual
                    elif g == G_GRAVITY_DOWN:
                        gravity.setdefault((x, y, z), "down")
                    elif g == G_HAZARD:
                        hazards.setdefault((x, y, z), "") # trampa mortal-siempre (un @hazard previo la deja condicional)
                    elif g in _KEY_CHARS:
                        keys[(x, y, z)] = g               # llave con id = la letra minúscula
                    elif g in _DOOR_CHARS:
                        doors[(x, y, z)] = g.lower()      # puerta que requiere la llave homónima
            out_rows.append("".join(chars))
        floors.append(out_rows)

    return Maze3D(floors=floors, connectors=connectors, portals=portals,
                  gravity=gravity, stairs=stairs, keys=keys, doors=doors,
                  switches=switches, gates=gates, hazards=hazards, ladders=ladders,
                  conduits=conduits, seams=seams)
