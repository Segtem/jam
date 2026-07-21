"""JamPCG-DSL — el lenguaje/framework INTERMEDIO de PCG entre JamDSL (el esqueleto verificado, Capa 0) y el
juego vestido. Ver [[jampcg-dsl-direction]].

JamDSL es `texto → grafo verificado` (un `Maze3D` + su oráculo BFS). JamPCG-DSL es el HERMANO un nivel abajo:
`(JamMap CONGELADO + reglas + seed) → contenido concreto → RE-VERIFICADO`. Expande el esqueleto abstracto en
espacio poblado (props con footprint; ops estructurales tipo ramal), de forma PROCEDURAL y SEEDED (rangos, no
valores fijos → de UN esqueleto salen mil instancias).

La disciplina (por qué es seguro y no cae en Goodhart): el MISMO loop que un nivel arriba —
**generador NO-confiable + oráculo EXACTO** — aplicado al CONTENIDO:

    for seed in seeds:
        content = expand(jammap, program, seed)     # generador no-confiable (procedural)
        graph'  = abstract(content)                  # geometría/props → grafo
        if reverify preserva la winnability(jammap): keep(content)   # red de seguridad BFS

Dos amarras: (1) RESTRINGIDO — la topología del JamMap es una restricción DURA (el `expand` parte del esqueleto);
(2) RE-VERIFICADO — el contenido se RE-ABSTRAE al grafo y se re-corre el oráculo de JamDSL (`solve_3d`) → conserva
que el juego siga siendo ganable, o se DESCARTA. El content-spec es MOTOR-AGNÓSTICO (Godot/UE = receptores).

Este es el PRIMER CORTE (motor-agnóstico, sin motor): props semánticos con footprint (población que el oráculo
verifica: un prop que tapa el único camino se caza) + una op estructural (`@branch`, carva un ramal). El espacio
tipado (`@space hospital` + `program_satisfied`) y la fabricación (bind tag→mesh/textura, Capa 1) son cortes 2 y 3.
"""
from __future__ import annotations

import math
import random
import re
from collections import Counter, deque
from dataclasses import dataclass, field, replace
from typing import Any

from src.mazes.couple import powered_survival_horizon, solve_coupled, solve_powered_survival
from src.mazes.electric import ElectricChannel
from src.mazes.maze3d import GOAL, PLAYER, WALL, Maze3D, solve_3d
from src.mazes.resource import ResourceChannel, ResourceSpec, solve_survival, survival_horizon

Cell = tuple[int, int, int]
_DIR_DELTA = {"N": (0, -1), "S": (0, 1), "E": (1, 0), "W": (-1, 0)}


# ── EL PROGRAMA JamPCG (parseado del DSL) ────────────────────────────────────────────────────────
@dataclass(frozen=True)
class PropRule:
    """Regla de POBLACIÓN semántica. `at` set → UNA celda explícita (determinista); si no, `density` esparce
    props en las celdas transitables elegibles (procedural, seeded). `blocks`=True → el prop OCUPA la celda
    (footprint bloqueante) → el re-verificador lo ve como muro. `blocks`=False → decorativo (no bloquea)."""
    tag: str
    blocks: bool
    at: Cell | None = None
    density: float = 0.0


@dataclass(frozen=True)
class BranchOp:
    """Op ESTRUCTURAL: carva un ramal (dead-end) desde `cell` en dirección `dir` (N/S/E/W) de largo `length`
    → CAMBIA el grafo → dispara la re-verificación (un ramal mal puesto podría romper o atajar el reto)."""
    cell: Cell
    dir: str
    length: int


@dataclass
class PcgProgram:
    """El JamPCG-DSL parseado: seed + reglas de población + ops estructurales + (opcional) inflado de cuartos +
    TIPADO de espacio (`@space`/`@room_type`: declara la CATEGORÍA, no el layout — anti-inyección)."""
    seed: int = 0
    props: list[PropRule] = field(default_factory=list)
    branches: list[BranchOp] = field(default_factory=list)
    room: tuple[int, int] | None = None       # @room size a..b → INFLA cada celda en un cuarto de lado ∈ [a,b]
    space: str | None = None                  # @space hospital → el TIPO de espacio (afecta la generación/verificación)
    room_types: dict[Cell, str] = field(default_factory=dict)  # @room_type x,y,z ward → tipo semántico de un cuarto
    adjacent: tuple[tuple[str, str], ...] = ()  # @adjacent a b → adyacencia EXTRA del usuario (sobre las canónicas)


# ── EL CONTENIDO MATERIALIZADO (spec intermedio, MOTOR-AGNÓSTICO) ─────────────────────────────────
@dataclass(frozen=True)
class Prop:
    """Un prop COLOCADO: su tag semántico (`crate`/`bed`/…), la celda, si bloquea, y su TRANSFORMA dentro de la
    celda (V1 'vestido con sentido'): `rot` = yaw en grados (orientación derivada del contexto de muros),
    `offset` = corrimiento (dx,dy) en fracciones de celda hacia un muro. El tag se bindea a un mesh+textura en
    FABRICACIÓN (Capa 1). La transforma es DRESSING (no toca el footprint/celda que verifica el oráculo)."""
    tag: str
    cell: Cell
    blocks: bool
    rot: float = 0.0
    offset: tuple[float, float] = (0.0, 0.0)


@dataclass
class ContentSpec:
    """El contenido concreto de expandir un JamMap con un `PcgProgram`. MOTOR-AGNÓSTICO: Godot/UE lo consumen
    como receptores (paridad). `base` = la geometría (el `Maze3D` con los ramales ya carvados); `props` = la
    población semántica con footprint. `abstract()` lo re-abstrae a un grafo para re-verificarlo."""
    base: Maze3D
    props: list[Prop] = field(default_factory=list)
    resource: ResourceChannel | None = None   # canal recurso con las @source ya mapeadas a coords del inflado
    space: str | None = None                  # el TIPO de espacio (hospital/escuela/…) que este contenido realiza
    room_types: dict[Cell, str] = field(default_factory=dict)  # cuarto (por su ancla en el inflado) → tipo semántico
    room_sizes: dict[Cell, tuple[int, int]] = field(default_factory=dict)  # ancla → (w,h) del cuarto (para el minimapa)
    pitch: int = 1                            # paso del inflado (ancla = celda_fuente × pitch); 1 = sin inflar
    seed: int = 0                             # el seed que lo produjo (con el programa, reproduce este contenido)


# ── PARSE del DSL ────────────────────────────────────────────────────────────────────────────────
_PCG_SEED = re.compile(r"@seed\s+(\d+)\s*$")
_PCG_PROP_AT = re.compile(r"@prop\s+(\w+)\s+at\s+(\d+),(\d+),(\d+)\s+(blocks|free)\s*$")
_PCG_PROP_DENSITY = re.compile(r"@prop\s+(\w+)\s+density\s+(0(?:\.\d+)?|1(?:\.0+)?)\s+(blocks|free)\s*$")
_PCG_BRANCH = re.compile(r"@branch\s+(\d+),(\d+),(\d+)\s+([NSEW])\s+(\d+)\s*$")
_PCG_ROOM = re.compile(r"@room\s+size\s+(\d+)\.\.(\d+)\s*$")
_PCG_SPACE = re.compile(r"@space\s+(\w+)\s*$")
_PCG_ROOM_TYPE = re.compile(r"@room_type\s+(\d+),(\d+),(\d+)\s+(\w+)\s*$")
_PCG_ADJACENT = re.compile(r"@adjacent\s+(\w+)\s+(\w+)\s*$")


def parse_pcg(text: str) -> PcgProgram:
    """Escanea el JamPCG-DSL → `PcgProgram`. Ignora líneas en blanco y comentarios '#'."""
    prog = PcgProgram()
    for raw in text.splitlines():
        s = raw.strip()
        if not s or s.startswith("#"):
            continue
        if (m := _PCG_SEED.match(s)):
            prog.seed = int(m[1])
        elif (m := _PCG_SPACE.match(s)):
            prog.space = m[1]
        elif (m := _PCG_ROOM_TYPE.match(s)):
            prog.room_types[(int(m[1]), int(m[2]), int(m[3]))] = m[4]
        elif (m := _PCG_ADJACENT.match(s)):
            prog.adjacent = prog.adjacent + ((m[1], m[2]),)
        elif (m := _PCG_ROOM.match(s)):
            prog.room = (int(m[1]), int(m[2]))
        elif (m := _PCG_PROP_AT.match(s)):
            prog.props.append(PropRule(tag=m[1], at=(int(m[2]), int(m[3]), int(m[4])), blocks=m[5] == "blocks"))
        elif (m := _PCG_PROP_DENSITY.match(s)):
            prog.props.append(PropRule(tag=m[1], density=float(m[2]), blocks=m[3] == "blocks"))
        elif (m := _PCG_BRANCH.match(s)):
            prog.branches.append(BranchOp(cell=(int(m[1]), int(m[2]), int(m[3])), dir=m[4], length=int(m[5])))
    return prog


# ── EXPAND: JamMap + programa + seed → contenido concreto ─────────────────────────────────────────
def _mutable(floors: list[list[str]]) -> list[list[list[str]]]:
    return [[list(row) for row in grid] for grid in floors]


def _frozen(mfloors: list[list[list[str]]]) -> list[list[str]]:
    return [["".join(row) for row in grid] for grid in mfloors]


def _in_bounds(mfloors: list[list[list[str]]], x: int, y: int, z: int) -> bool:
    return 0 <= z < len(mfloors) and 0 <= y < len(mfloors[z]) and 0 <= x < len(mfloors[z][y])


# contexto de colocación (V1): direcciones de vecino en grid + mapeo facing→yaw. El pipe/duct/cable_tray
# corren por grid-y por default (mesh modelado sobre el eje Y de Blender) → yaw 90 los alinea a grid-x.
_PLACE_NBRS = [(1, 0), (-1, 0), (0, 1), (0, -1)]
_FACING_DEG = {(0, 1): 0.0, (1, 0): 90.0, (0, -1): 180.0, (-1, 0): 270.0}
_WALL_OFFSET = 0.30                                        # cuánto se arrima al muro (fracción de celda)


def _placement_transform(base: Maze3D, cell: Cell, placement: str) -> tuple[float, tuple[float, float]]:
    """(rot, offset) del prop según el contexto de MUROS de su celda (DRESSING, no toca el footprint).
    `wall` = arrimado a un muro mirando hacia adentro del cuarto; `along` = alineado al eje del pasillo
    (instalaciones de techo); resto = centrado. Determinista (elección canónica del muro → reproducible)."""
    x, y, z = cell
    if placement == "wall":
        walls = sorted((dx, dy) for dx, dy in _PLACE_NBRS if not base.is_open(x + dx, y + dy, z))
        if walls:
            wdx, wdy = walls[0]                            # muro elegido (orden canónico → reproducible)
            return _FACING_DEG[(-wdx, -wdy)], (wdx * _WALL_OFFSET, wdy * _WALL_OFFSET)
    elif placement == "along":
        opens = [(dx, dy) for dx, dy in _PLACE_NBRS if base.is_open(x + dx, y + dy, z)]
        horiz = any(dx != 0 for dx, dy in opens)
        vert = any(dy != 0 for dx, dy in opens)
        if horiz and not vert:                             # pasillo E-W → alinear la corrida a grid-x
            return 90.0, (0.0, 0.0)
    return 0.0, (0.0, 0.0)


def _place_props(base: Maze3D, program: PcgProgram) -> list[Prop]:
    """Puebla `base` con los props del programa (RNG seedeado, orden CANÓNICO → reproducible). Elegibles =
    celdas transitables que no son el player ni la meta. Compartido por el modo 1:1 y el inflado. Cada prop
    recibe su TRANSFORMA de colocación (rot/offset) según el contexto de muros y el `placement` de su tag."""
    from src.mazes.pcg_vocab import PROP_TAGS
    start, goal = base.find(PLAYER), base.find(GOAL)
    eligible = sorted(c for c in base.open_cells() if c != start and c != goal)
    rng = random.Random(program.seed)
    props: list[Prop] = []
    occupied: set[Cell] = set()
    pitch = pitch_of(program)

    def _room_type_of(cell: Cell) -> str | None:
        """Tipo de sala de una celda MATERIALIZADA: la celda-fuente es (x//pitch, y//pitch) y `program.room_types`
        está keyeado por celda-fuente (en 1:1 pitch=1 → la celda misma)."""
        return program.room_types.get((cell[0] // pitch, cell[1] // pitch, cell[2]))

    for rule in program.props:
        if rule.at is not None:                            # explícito (determinista)
            if rule.at in eligible and rule.at not in occupied:
                props.append(_mk_prop(base, rule.tag, rule.at, rule.blocks))
                if rule.blocks:
                    occupied.add(rule.at)
        else:                                              # por densidad (procedural, seeded)
            # V2: afinidad prop→tipo de sala — un prop por densidad sólo cae en cuartos donde tiene sentido
            # (cañería/conducto/bandeja = sólo circulación; planta = vestíbulo…). Vacío = a cualquier lado.
            affinity = PROP_TAGS[rule.tag].rooms if rule.tag in PROP_TAGS else ()
            for cell in eligible:
                if cell in occupied:
                    continue
                if affinity and _room_type_of(cell) not in affinity:
                    continue
                if rng.random() < rule.density:
                    props.append(_mk_prop(base, rule.tag, cell, rule.blocks))
                    if rule.blocks:
                        occupied.add(cell)
    return props


def _mk_prop(base: Maze3D, tag: str, cell: Cell, blocks: bool) -> Prop:
    """Un `Prop` con su TRANSFORMA de colocación (rot/offset) derivada del contexto de muros + el `placement` de
    su tag (corte V1). Compartido por `_place_props` (densidad/explícitos) y `_furnish_rooms` (recetas V3)."""
    from src.mazes.pcg_vocab import PROP_TAGS
    placement = PROP_TAGS[tag].placement if tag in PROP_TAGS else "center"
    rot, off = _placement_transform(base, cell, placement)
    return Prop(tag=tag, cell=cell, blocks=blocks, rot=rot, offset=off)


def _furnish_rooms(base: Maze3D, size: dict[Cell, tuple[int, int]], room_types: dict[Cell, str],
                   pitch: int, space: str | None, seed: int, taken: set[Cell]) -> list[Prop]:
    """V3 — AMOBLADO POR RECETA: cada cuarto TIPADO se amuebla con la receta de su tipo (props cuarto-locales
    contra las paredes LEJANAS, dejando libre la CIRCULACIÓN = fila/columna del ancla por donde entran los vanos).
    Pares semánticos: un acompañante NO-bloqueante junto a cada primario (iv_stand junto a bed, monitor sobre
    desk). La receta PROPONE; el oráculo (`reverify`) re-verifica el footprint → una que tapia el cuarto se
    descarta. Los items se FILTRAN a la paleta del @space. `taken` = celdas ya ocupadas por props previos.
    V4 — VARIEDAD: un RNG por-cuarto (seed del programa ⊕ el ancla) elige la PARED de arrimo (inferior vs derecha
    → camas en fila norte vs este), jitterea la cantidad y el lado del par → dos cuartos del mismo tipo/tamaño
    (en el mismo mapa o a distinto seed) se amueblan DISTINTO pero ambos válidos (anti-monocultura; cada seed de
    `materialize` es una instancia diversa)."""
    from src.mazes.pcg_vocab import PROP_TAGS, recipe_for
    start, goal = base.find(PLAYER), base.find(GOAL)
    occupied = set(taken)
    props: list[Prop] = []
    for c in sorted(size):
        ax, ay, az = c[0] * pitch, c[1] * pitch, c[2]
        recipe = recipe_for(room_types.get((ax, ay, az), ""), space)
        if recipe is None:
            continue
        w, h = size[c]
        room = {(ax + rx, ay + ry, az) for ry in range(h) for rx in range(w)}
        rng = random.Random(f"furnish:{seed}:{c}")         # subseed determinista por cuarto (str → estable)
        # amueblables = interior LEJOS de la circulación (rx≥1, ry≥1). V4: elegir una PARED lejana de arrimo
        # (inferior ry=h-1 o derecha rx=w-1) y llenar a lo largo de ella; completar con el resto de la zona
        # segura por si la receta pide más. Ambas paredes están fuera de la circulación (ancla en ry=0/rx=0).
        walls = []
        if h >= 2:
            walls.append([(ax + rx, ay + h - 1, az) for rx in range(w - 1, 0, -1)])   # pared inferior
        if w >= 2:
            walls.append([(ax + w - 1, ay + ry, az) for ry in range(h - 1, 0, -1)])   # pared derecha
        # tipos de ACOPIO se leen por el PERÍMETRO (informe de legibilidad): arrimar contra TODAS
        # las paredes lejanas, no una sola — un depósito con cajas al medio se lee garaje
        rtype = room_types.get((ax, ay, az), "")
        if rtype in ("storage", "library", "garage", "closet") and len(walls) == 2:
            wall = walls[0] + [c for c in walls[1] if c not in walls[0]]   # perímetro sin la esquina doble
        else:
            wall = rng.choice(walls) if walls else []
        rest = [(ax + rx, ay + ry, az) for ry in range(h - 1, 0, -1) for rx in range(w - 1, 0, -1)
                if (ax + rx, ay + ry, az) not in wall]
        furnish = wall + rest
        cap = len(furnish)
        if cap > 1 and rng.random() < 0.35:                # jitter de cantidad: a veces dejar aire (siempre ≥1)
            cap -= 1
        slot = placed = 0
        for tag in recipe.items:
            if placed >= cap:
                break
            blocks = PROP_TAGS[tag].blocks if tag in PROP_TAGS else True
            cell = None
            while slot < len(furnish):                     # próxima celda amueblable libre y abierta (no P/G)
                cand = furnish[slot]; slot += 1
                if cand not in occupied and cand not in (start, goal) and base.is_open(*cand):
                    cell = cand
                    break
            if cell is None:
                break                                      # cuarto lleno → el resto de la receta no entra
            props.append(_mk_prop(base, tag, cell, blocks))
            placed += 1
            if blocks:
                occupied.add(cell)
            pair = recipe.pairs.get(tag)                    # par semántico: acompañante NO-bloqueante vecino
            if pair:
                nbrs = [(cell[0] + dx, cell[1] + dy, cell[2]) for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1))]
                rng.shuffle(nbrs)                          # V4: lado del par variado
                for nb in nbrs:
                    if nb in room and nb not in occupied and nb not in (start, goal) and base.is_open(*nb):
                        props.append(_mk_prop(base, pair, nb, False))
                        break
    return props


def expand(source: Maze3D, program: PcgProgram, resource: ResourceChannel | None = None) -> ContentSpec:
    """Materializa el esqueleto `source` con el `program` (determinista dado `program.seed`). Si el programa
    declara `@room` → deriva a `inflate` (cada celda → un cuarto real; mapea el canal `resource` si se pasa).
    Si no, modo 1:1: aplica las ops ESTRUCTURALES (`@branch`) y la POBLACIÓN (el recurso queda tal cual, mismas
    coords). NO re-verifica (eso es `reverify`) — el `expand` es el generador no-confiable."""
    if program.room is not None:
        return inflate(source, program, resource)
    mfloors = _mutable(source.floors)
    # 1) ESTRUCTURAL: carvar ramales (turn '#' → '.') dentro de los límites de la grilla
    for b in program.branches:
        x, y, z = b.cell
        dx, dy = _DIR_DELTA[b.dir]
        for i in range(1, b.length + 1):
            nx, ny = x + dx * i, y + dy * i
            if _in_bounds(mfloors, nx, ny, z) and mfloors[z][ny][nx] == WALL:
                mfloors[z][ny][nx] = "."
    base = replace(source, floors=_frozen(mfloors))       # preserva puertas/gates/keys/switches/portales/…
    # 2) POBLACIÓN semántica
    return ContentSpec(base=base, props=_place_props(base, program), resource=resource,
                       space=program.space, room_types=dict(program.room_types), seed=program.seed)


# ── INFLADO DE CUARTOS: celda → cuarto real (corte 2, el "espacio real") ──────────────────────────
def pitch_of(program: PcgProgram) -> int:
    """El PASO de la grilla materializada = lado máximo de cuarto + 1 (la pared entre cuartos). Con esto el
    mapeo celda-fuente ↔ región materializada es fijo: la celda (x,y,z) ancla su cuarto en (x·pitch, y·pitch)."""
    return (program.room[1] + 1) if program.room else 1


def doorway_cell(u: Cell, v: Cell, pitch: int) -> Cell:
    """La celda-CHOKE del vano entre dos cuartos adyacentes `u`→`v` (E o S): siempre una celda de PASILLO (fuera
    de ambos cuartos, anclados en múltiplos de `pitch`). Bloquearla desconecta los cuartos (para tests/props)."""
    (ux, uy, uz), (vx, vy, _) = u, v
    if vx == ux + 1 and vy == uy:                          # vecino ESTE
        return ((ux + 1) * pitch - 1, uy * pitch, uz)
    if vy == uy + 1 and vx == ux:                          # vecino SUR
        return (ux * pitch, (uy + 1) * pitch - 1, uz)
    raise ValueError(f"doorway_cell sólo E/S: {u}→{v}")


# ── TAMAÑO DE CUARTO POR TIPO (calidad de lectura 2026-07-06): un pasillo se LEE pasillo porque es
# un TUBO angosto; un placard es chico; un ward/aula es grande. Perfiles CLAMPEADOS al `@room size
# a..b` del programa (el contrato del DSL manda); tipos sin perfil = rango funcional (≥2 para que
# la receta de amoblado tenga interior). La circulación se ELONGA sobre su eje de flujo (hacia
# dónde están sus vecinos abiertos) — double-loaded corridor, no plazoleta cuadrada.
_SIZE_PROFILE: dict[str, str] = {
    "corridor": "narrow", "hallway": "narrow",
    "restroom": "small", "bathroom": "small", "closet": "small", "storage": "small",
    "cubicle": "small", "nurse_station": "small",
    "ward": "big", "classroom": "big", "gym": "big", "cafeteria": "big", "library": "big",
    "operating_room": "big", "living_room": "big", "meeting_room": "big", "garage": "big",
}


def _room_size_for(rng: random.Random, rtype: str | None, rmin: int, rmax: int,
                   flow_x: bool) -> tuple[int, int]:
    """El (w, h) de un cuarto según su tipo, dentro de [rmin, rmax]. Consume rng de forma estable
    (una decisión por cuarto). `flow_x` = el eje dominante de sus vecinos abiertos (para elongar
    la circulación a lo largo del pasillo)."""
    clamp = lambda v: max(rmin, min(rmax, v))
    profile = _SIZE_PROFILE.get(rtype or "")
    if profile == "narrow":
        short, long_ = clamp(1), clamp(rmax)
        return (long_, short) if flow_x else (short, long_)
    if profile == "small":
        # chico pero AMUEBLABLE: 2×2 (la zona de recetas necesita interior rx≥1, ry≥1 — un
        # cubicle 1×N salía vacío). El clamp respeta programas con rmax=1.
        side = clamp(2)
        return (side, side)
    if profile == "big":
        lo = clamp(max(2, rmax - 1))
        return (rng.randint(lo, rmax), rng.randint(lo, rmax))
    lo = clamp(2)                                          # funcional default: con interior amueblable
    return (rng.randint(lo, rmax), rng.randint(lo, rmax))


def inflate(source: Maze3D, program: PcgProgram, resource: ResourceChannel | None = None) -> ContentSpec:
    """Materializa cada celda transitable del esqueleto en un CUARTO real (lado ∈ `@room size a..b`, seeded) en
    una grilla `pitch`× más grande, y carva un VANO entre cuartos cuyas celdas-fuente son adyacentes-y-abiertas
    (conserva la topología). El `base` resultante es un `Maze3D` común → `abstract`/`reverify`/`materialize` lo
    tratan igual (corren `solve_3d` sobre la geometría inflada). Si un vano requerido no conecta (o un prop lo
    tapa), P no llega a G → el oráculo lo caza. Mapea TODO el grafo nav del esqueleto: puertas/llaves/hazards/
    GATES al cuarto entero (constraints idempotentes de celda), los SWITCHES a una celda-panel 1×1 (togglear no
    es idempotente → el cuarto es un choke), y las aristas no-de-grilla —PORTALES y CONECTORES verticales— entre
    las anclas de los cuartos (inflado multi-piso/no-euclidiano). Canales eléctrico/recurso → corte siguiente."""
    rmin, rmax = program.room                              # type: ignore[misc]
    pitch = pitch_of(program)
    rng = random.Random(program.seed)
    open_src = source.open_cells()
    # Celdas-DISPOSITIVO que deben ir en un panel 1×1 (choke): el SWITCH (togglea, no idempotente) y la @SOURCE
    # de recurso (recarga cuantitativa; cubrir el cuarto = sobre-crédito → falso positivo en el oráculo). Un
    # panel 1×1 garantiza que traversar el cuarto = usar el dispositivo EXACTAMENTE una vez (fiel al esqueleto).
    panels = set(source.switches) | (set(resource.spec.sources) if resource is not None else set())
    size: dict[Cell, tuple[int, int]] = {}                 # tamaño seeded por cuarto (orden canónico → reproducible)
    open_src_set = set(open_src)
    for c in sorted(open_src):
        if c in panels:
            size[c] = (1, 1)
        else:
            # eje de flujo: hacia dónde se abre la celda (para elongar la circulación sobre él)
            ew = sum(1 for dx in (-1, 1) if (c[0] + dx, c[1], c[2]) in open_src_set)
            ns = sum(1 for dy in (-1, 1) if (c[0], c[1] + dy, c[2]) in open_src_set)
            size[c] = _room_size_for(rng, program.room_types.get(c), rmin, rmax, flow_x=ew >= ns)
    mw, mh = source.width * pitch, source.height * pitch
    mfloors: list[list[list[str]]] = []
    for z in range(source.n_floors):
        grid = [[WALL] * mw for _ in range(mh)]
        for (x, y, zz), (w, h) in size.items():            # carvar cada cuarto (anclado en x·pitch, y·pitch)
            if zz != z:
                continue
            for ry in range(h):
                for rx in range(w):
                    grid[y * pitch + ry][x * pitch + rx] = "."
        for (x, y, zz) in size:                             # carvar los vanos hacia el ESTE y el SUR
            if zz != z:
                continue
            if (x + 1, y, z) in size:                        # pasillo horizontal en la fila y·pitch
                for cx in range(x * pitch, (x + 1) * pitch + 1):
                    grid[y * pitch][cx] = "."
            if (x, y + 1, z) in size:                        # pasillo vertical en la columna x·pitch
                for cy in range(y * pitch, (y + 1) * pitch + 1):
                    grid[cy][x * pitch] = "."
        mfloors.append(grid)
    ps, gs = source.find(PLAYER), source.find(GOAL)        # P/G en el ancla de su cuarto
    if ps is not None:
        mfloors[ps[2]][ps[1] * pitch][ps[0] * pitch] = PLAYER
    if gs is not None:
        mfloors[gs[2]][gs[1] * pitch][gs[0] * pitch] = GOAL

    # Mapear los elementos IDEMPOTENTES del esqueleto (puerta/llave/hazard son constraints de CELDA) al cuarto
    # ENTERO: "la celda c está gateada" → "todo el cuarto de c lo está" (fiel: no se puede rodear el marcador
    # dentro del cuarto). La llave es pickup idempotente; el hazard, mortal en todo el cuarto. Gates+switches
    # (maquinaria de flags) y los canales eléctrico/recurso → corte siguiente (no son idempotentes / son externos).
    def room_cells(c: Cell) -> list[Cell]:
        x, y, z = c
        w, h = size[c]
        return [(x * pitch + rx, y * pitch + ry, z) for ry in range(h) for rx in range(w)]

    def anchor(c: Cell) -> Cell:
        return (c[0] * pitch, c[1] * pitch, c[2])

    doors = {mc: kid for c, kid in source.doors.items() if c in size for mc in room_cells(c)}
    keys = {mc: kid for c, kid in source.keys.items() if c in size for mc in room_cells(c)}
    hazards = {mc: fl for c, fl in source.hazards.items() if c in size for mc in room_cells(c)}
    gates = {mc: fl for c, fl in source.gates.items() if c in size for mc in room_cells(c)}  # idempotente → cuarto
    switches = {anchor(c): fl for c, fl in source.switches.items() if c in size}             # el panel 1×1
    # aristas NO-de-grilla del esqueleto → entre las ANCLAS de los cuartos (inflado multi-piso/no-euclidiano):
    portals = [(anchor(s), anchor(d)) for s, d in source.portals if s in size and d in size]
    connectors = {anchor(c) for c in source.connectors                                       # vertical z↔z+1
                  if c in size and (c[0], c[1], c[2] + 1) in size}
    # D3: los LADDERS del esqueleto también se mapean (misma arista z↔z+1 que el conector, mismo criterio de
    # ancla; antes se PERDÍAN en el inflado → un esqueleto ganable-sólo-por-escalera quedaba inganable y el
    # oráculo lo descartaba entero — fidelidad, no dressing)
    ladders = {anchor(c) for c in source.ladders
               if c in size and (c[0], c[1], c[2] + 1) in size}
    base = replace(Maze3D.from_layers(_frozen(mfloors)),
                   doors=doors, keys=keys, hazards=hazards, gates=gates, switches=switches,
                   portals=portals, connectors=connectors, ladders=ladders)
    # canal RECURSO: sólo las @source son coord-específicas → mapearlas a la ancla (panel 1×1). drain/cap/start
    # son globales (por recurso); @consume dispara por carga alimentada (coord eléctrico, no se infla).
    inflated_resource = resource
    if resource is not None:
        src_map = {anchor(c): deltas for c, deltas in resource.spec.sources.items() if c in size}
        inflated_resource = ResourceChannel(ResourceSpec(resource.spec.resources, src_map), resource.days)
    room_types = {anchor(c): t for c, t in program.room_types.items() if c in size}   # tipo por ancla del cuarto
    # los props EXPLÍCITOS (`at`) vienen en coords del esqueleto → remapear al cuarto (los de densidad van por
    # celda inflada, quedan igual). A la ESQUINA OPUESTA al ancla: el ancla y la primera fila/columna son la
    # CIRCULACIÓN del cuarto (por ahí entran los vanos) — un prop bloqueante ahí sellaba el cuarto entero
    # (bug cazado por el gate de alcanzabilidad 2026-07-02: la cama tapiaba su propio ward).
    def prop_spot(c: Cell) -> Cell:
        w, h = size[c]
        return (c[0] * pitch + w - 1, c[1] * pitch + h - 1, c[2])
    prop_rules = [replace(r, at=prop_spot(r.at)) if (r.at is not None and r.at in size) else r for r in program.props]
    props = _place_props(base, replace(program, props=prop_rules))
    # V3: amueblar cada cuarto tipado con la receta de su tipo (respetando lo ya ocupado por los props previos)
    taken = {p.cell for p in props if p.blocks}
    props = props + _furnish_rooms(base, size, room_types, pitch, program.space, program.seed, taken)
    return ContentSpec(base=base, props=props, resource=inflated_resource,
                       space=program.space, room_types=room_types,
                       room_sizes={anchor(c): wh for c, wh in size.items()},
                       pitch=pitch, seed=program.seed)


# ── ABSTRACT: contenido → grafo (el round-trip que habilita la re-verificación) ───────────────────
def abstract(content: ContentSpec) -> Maze3D:
    """Re-abstrae el contenido concreto de vuelta a un `Maze3D` (grafo) para poder re-correr el oráculo de
    JamDSL. La geometría (`base`) ya ES un grafo; el único aporte de la población es que un prop BLOQUEANTE
    ocupa su celda → la volvemos muro. Los canales/puertas/gates del esqueleto se arrastran intactos (viven en
    `base`). (Cortes futuros: cuartos inflados → colapsar a nodos; vanos → aristas.)"""
    mfloors = _mutable(content.base.floors)
    for p in content.props:
        if p.blocks:
            x, y, z = p.cell
            if _in_bounds(mfloors, x, y, z):
                mfloors[z][y][x] = WALL
    return replace(content.base, floors=_frozen(mfloors))


def _wall_off(maze: Maze3D, cells: set[Cell]) -> Maze3D:
    """`maze` con `cells` convertidas en muro (y limpiando gates/doors) → para medir reachability EVITANDO esas
    celdas. Sirve al invariante estricto: si el esqueleto NO es ganable evitando sus gates/doors (son necesarios)
    pero el contenido SÍ, el contenido creó un ATAJO que los saltea."""
    mfloors = _mutable(maze.floors)
    for (x, y, z) in cells:
        if _in_bounds(mfloors, x, y, z):
            mfloors[z][y][x] = WALL
    return replace(maze, floors=_frozen(mfloors), gates={}, doors={})


# ── REVERIFY: el oráculo re-corrido sobre el grafo re-abstraído (la RED DE SEGURIDAD) ─────────────
def reverify(content: ContentSpec, source: Maze3D, *, electric: ElectricChannel | None = None,
             couplings: dict[Cell, str] | None = None, resource: ResourceChannel | None = None,
             consumes: dict[Cell, dict[str, int]] | None = None, max_states: int = 200_000) -> dict[str, Any]:
    """¿El contenido PRESERVA la winnability del esqueleto? Corre el oráculo de JamDSL sobre `source` y sobre
    `abstract(content)` y compara. `preserved` = si el esqueleto era ganable, el contenido SIGUE siéndolo
    (un prop bloqueante que tapa el camino, un ramal que aísla, o el inflado que ALARGA el camino y agota el
    recurso, lo rompen → `preserved=False`). Es la RED DE SEGURIDAD BFS un nivel abajo: `expand` propone, esto
    dispone. CANAL-AWARE — elige el oráculo por los canales presentes (cada maze con SU spec de recurso: el
    `source` con coords fuente, el contenido con las @source ya infladas en `content.resource`):
      - recurso `@budget over days=N` (survive-N) → `horizon >= N` (con eléctrico+consume: powered; si no, base).
      - recurso + eléctrico + `@consume` (reach) → `solve_powered_survival` (el sistema tipo-VotV).
      - recurso solo (reach) → `solve_survival` (reach-alive).
      - eléctrico + `@power` → `solve_coupled` (rutea a dos vías si hay `@breaker`).
      - si no → `solve_3d` (nav). El eléctrico NO se infla (flags por nombre); sólo el recurso (@source)."""
    def _solve(maze: Maze3D, res: ResourceChannel | None) -> dict[str, Any]:
        if res is not None and res.days is not None:       # SURVIVE-N: la victoria es aguantar N pasos, no reach-G
            if electric is not None and consumes:
                h = powered_survival_horizon(maze, res, electric, couplings or {}, consumes, max_states)
            else:
                h = survival_horizon(maze, res.spec, max_states)
            ok = h["horizon"] >= res.days and not h.get("truncated")   # truncado = no certificado (conservador)
            return {"solvable": ok, "optimal_steps": None}
        if res is not None and electric is not None and consumes:
            return solve_powered_survival(maze, res, electric, couplings or {}, consumes, max_states)
        if res is not None:
            return solve_survival(maze, res.spec, max_states)
        if electric is not None and couplings:
            return solve_coupled(maze, electric, couplings, max_states)
        return solve_3d(maze, max_states)
    cnt_maze = abstract(content)
    src = _solve(source, resource)
    cnt = _solve(cnt_maze, content.resource if content.resource is not None else resource)
    src_ok, cnt_ok = bool(src["solvable"]), bool(cnt["solvable"])
    preserved = (not src_ok) or cnt_ok

    # INVARIANTE ESTRICTO: el contenido no debe crear un ATAJO que saltee un @gate/@door NECESARIO del esqueleto
    # (un @branch que carva un túnel alrededor de un gate → sigue ganable pero lo TRIVIALIZA — hueco Goodhart).
    no_shortcut = True
    if source.gates or source.doors:
        def _avoids(maze: Maze3D) -> bool:
            blocked = _wall_off(maze, set(maze.gates) | set(maze.doors))
            return bool(solve_3d(blocked, max_states)["solvable"])
        # si el esqueleto ya se gana EVITANDO sus gates/doors, no eran necesarios → no hay nada que trivializar;
        # si NO (son necesarios), el contenido tampoco debe poder evitarlos.
        no_shortcut = _avoids(source) or (not _avoids(cnt_maze))
    return {"preserved": preserved, "no_shortcut": no_shortcut, "source_solvable": src_ok,
            "content_solvable": cnt_ok, "source_steps": src["optimal_steps"], "content_steps": cnt["optimal_steps"]}


def materialize(source: Maze3D, program: PcgProgram, seeds, *, electric: ElectricChannel | None = None,
                couplings: dict[Cell, str] | None = None, resource: ResourceChannel | None = None,
                consumes: dict[Cell, dict[str, int]] | None = None, space_program: "SpaceProgram | None" = None,
                max_states: int = 200_000) -> dict[str, Any]:
    """El loop generador-no-confiable / oráculo-exacto: expande `source` con cada seed y SE QUEDA sólo con las
    instancias que RE-VERIFICAN (preservan la winnability canal-aware Y la estructura, sin atajos; y —si se pasa
    `space_program`— que además SATISFACEN EL PROGRAMA del tipo de espacio). De UN esqueleto verificado salen N
    instancias concretas, TODAS garantizadas jugables (y, con programa, espacios TIPADOS válidos)."""
    kept: list[ContentSpec] = []
    tried = 0
    for seed in seeds:
        tried += 1
        content = expand(source, replace(program, seed=seed), resource)
        r = reverify(content, source, electric=electric, couplings=couplings, resource=resource,
                     consumes=consumes, max_states=max_states)
        ok = r["preserved"] and r["no_shortcut"]           # ganable Y sin atajos que trivialicen
        if ok and space_program is not None:
            ok = program_satisfied(content, space_program)["ok"]   # + es un hospital/escuela VÁLIDO
        if ok:
            kept.append(content)
    return {"kept": kept, "tried": tried, "n_kept": len(kept), "n_discarded": tried - len(kept)}


# ── @SPACE TIPADO: el greybox se vuelve un hospital/escuela/… VERIFICADO (corte 3b) ───────────────
@dataclass(frozen=True)
class SpaceProgram:
    """El PROGRAMA de un tipo de espacio: qué DEBE tener un `space` válido (cantidades mínimas por tipo de sala
    + adyacencias requeridas entre tipos). Declara la CATEGORÍA y sus RELACIONES, NO el layout
    ([[tipo-de-espacio-semantico]]: 'declara categoría no inyecta diseño') → el gate `program_satisfied` verifica.
    `adjacent` = pares (a, b): debe existir al menos UN cuarto de tipo a pegado (con vano) a uno de tipo b —
    'hospital' deja de ser una etiqueta con conteo y pasa a ser una propiedad del GRAFO de cuartos."""
    space: str
    required: dict[str, int]                # tipo de sala → cantidad mínima (ej. hospital: nurse_station≥1, ward≥2)
    adjacent: tuple[tuple[str, str], ...] = ()   # pares de tipos que deben quedar ADYACENTES (≥1 instancia)
    circulation: tuple[str, ...] = ()       # tipos que son CIRCULACIÓN (pasillos): toda sala que no lo sea
                                            # debe tocar uno → el edificio es espina+salas, no un blob
    forbidden: tuple[tuple[str, str], ...] = ()  # pares que NO deben quedar pegados (zonificación: p.ej.
                                            # una sala de internación no da directo a la entrada)
    access_depth: dict[str, int] = field(default_factory=dict)  # tipo → profundidad MÍNIMA (saltos de
                                            # sala) desde la entrada: el gradiente público→privado. Un
                                            # quirófano en la puerta (depth 1) no es un hospital.
    ratio: tuple[tuple[str, str, int], ...] = ()  # (servido, por, n): al menos 1 `servido` cada `n`
                                            # de `por` — ej. ("restroom","ward",4) = 1 baño cada 4 salas
    zones: dict[str, tuple[str, ...]] = field(default_factory=dict)  # zona (ala) → tipos que la
                                            # componen. Dos salas de zonas DISTINTAS no pueden pegarse
                                            # directo: la transición es por circulación (edificio con
                                            # alas, no una mezcla). La circulación es neutra (conecta zonas)


def _reachable_cells(maze: Maze3D) -> set[Cell]:
    """Flood-fill ESTÁTICO desde P: celdas abiertas conectadas por grilla + conectores verticales + portales.
    Conservador a propósito: puertas/gates cuentan como transitables (en juego se abren con su llave/flag —
    la winnability fina ya la verifica el solver); acá cazamos lo SELLADO por muros o props bloqueantes."""
    start = maze.find(PLAYER)
    if start is None:
        return set()
    hops: dict[Cell, list[Cell]] = {}
    for s, d in maze.portals:
        hops.setdefault(s, []).append(d)
    seen, q = {start}, [start]
    while q:
        x, y, z = q.pop()
        nbrs = [(x + 1, y, z), (x - 1, y, z), (x, y + 1, z), (x, y - 1, z)]
        if (x, y, z) in maze.connectors:
            nbrs.append((x, y, z + 1))
        if (x, y, z - 1) in maze.connectors:
            nbrs.append((x, y, z - 1))
        nbrs += hops.get((x, y, z), [])
        for nb in nbrs:
            if nb not in seen and maze.is_open(*nb):
                seen.add(nb)
                q.append(nb)
    return seen


_STAIR_DELTA_V = {"N": (0, -1), "S": (0, 1), "E": (1, 0), "W": (-1, 0)}


def _vertical_room_links(maze: Maze3D, p: int) -> dict[Cell, set[Cell]]:
    """Enlaces VERTICALES entre celdas-grilla de salas: por cada escalera/conector, la celda de abajo se
    conecta con la de arriba. Con esto la profundidad de `access_depth` CRUZA pisos (subir = ganar
    profundidad): un quirófano un piso arriba de la entrada está legítimamente 'más adentro'."""
    links: dict[Cell, set[Cell]] = {}

    def add(a: Cell, b: Cell) -> None:
        links.setdefault(a, set()).add(b)
        links.setdefault(b, set()).add(a)

    for (sx, sy, sz) in set(getattr(maze, "connectors", ())) | set(getattr(maze, "ladders", ())):
        if maze.is_open(sx, sy, sz + 1):                   # conector/escalera trepable: misma columna
            add((sx // p, sy // p, sz), (sx // p, sy // p, sz + 1))
    for (sx, sy, sz), d in getattr(maze, "stairs", {}).items():
        dx, dy = _STAIR_DELTA_V.get(d, (0, 0))             # escalera direccional: el tope se corre
        if maze.is_open(sx + dx, sy + dy, sz + 1):
            add((sx // p, sy // p, sz), ((sx + dx) // p, (sy + dy) // p, sz + 1))
    return links


def program_satisfied(content: ContentSpec, program: SpaceProgram) -> dict[str, Any]:
    """Oráculo del espacio TIPADO: ¿el contenido es un `program.space` VÁLIDO? Tres chequeos:
      1. tipo correcto;
      2. cantidades mínimas por tipo de sala, contando SÓLO cuartos ALCANZABLES (un ward sellado por muros
         o tapado por props no es un ward — antes contaba igual: hueco cerrado 2026-07-02);
      3. adyacencias requeridas (`program.adjacent`): a y b con anclas de celdas-fuente vecinas (el inflado
         SIEMPRE carva vano entre cuartos fuente-adyacentes → vecindad de anclas = puerta real entre ambos).
    Generador propone el tipado, este oráculo acepta o descarta."""
    abstract_maze = abstract(content)                      # el maze reconstruido (lleva los conectores)
    reach = _reachable_cells(abstract_maze)                # props bloqueantes = muros (footprint real)

    def room_reachable(anchor: Cell) -> bool:
        w, h = content.room_sizes.get(anchor, (1, 1))
        ax, ay, az = anchor
        return any((ax + dx, ay + dy, az) in reach for dy in range(h) for dx in range(w))

    reachable_rooms = {a: t for a, t in content.room_types.items() if room_reachable(a)}
    counts = Counter(reachable_rooms.values())
    all_counts = Counter(content.room_types.values())
    right_space = content.space == program.space
    missing = {t: n for t, n in program.required.items() if counts.get(t, 0) < n}
    unreachable = {t: all_counts[t] - counts.get(t, 0) for t in program.required
                   if all_counts.get(t, 0) > counts.get(t, 0)}

    # adyacencia por celdas-FUENTE: ancla = fuente × pitch → vecinos ⇔ manhattan de fuentes == 1 (mismo piso)
    p = max(1, content.pitch)
    by_type: dict[str, list[Cell]] = {}
    for a, t in reachable_rooms.items():
        by_type.setdefault(t, []).append((a[0] // p, a[1] // p, a[2]))
    def _source_adjacent(ca: Cell, cb: Cell) -> bool:
        return ca[2] == cb[2] and abs(ca[0] - cb[0]) + abs(ca[1] - cb[1]) == 1

    adjacency_missing: list[tuple[str, str]] = []
    for ta, tb in program.adjacent:
        pairs = ((ca, cb) for ca in by_type.get(ta, []) for cb in by_type.get(tb, []))
        if not any(_source_adjacent(ca, cb) for ca, cb in pairs):
            adjacency_missing.append((ta, tb))

    # CIRCULACIÓN: toda sala alcanzable que no sea circulación debe tocar un cuarto de circulación
    # (pasillo). Sin esto, las salas cuelgan unas de otras y el edificio no lee como edificio.
    circ_cells = [c for t in program.circulation for c in by_type.get(t, [])]
    isolated: list[str] = []
    if program.circulation:
        for a, t in reachable_rooms.items():
            if t in program.circulation:
                continue
            src = (a[0] // p, a[1] // p, a[2])
            if not any(_source_adjacent(src, c) for c in circ_cells):
                isolated.append(t)
    isolated = sorted(set(isolated))

    # PROHIBIDO: pares que NO pueden quedar pegados (zonificación). Reporta los que SÍ lo están.
    forbidden_present: list[tuple[str, str]] = []
    for ta, tb in program.forbidden:
        pairs = ((ca, cb) for ca in by_type.get(ta, []) for cb in by_type.get(tb, []))
        if any(_source_adjacent(ca, cb) for ca, cb in pairs):
            forbidden_present.append((ta, tb))

    # ZONIFICACIÓN (access_depth): BFS de SALAS desde la entrada; cada tipo con profundidad mínima `d`
    # debe estar a ≥ d saltos de sala. El gradiente público→privado: lo público superficial, lo
    # privado/clínico profundo. Un quirófano en la puerta de calle no es un hospital. El BFS CRUZA PISOS
    # por las escaleras (subir un piso = un salto más adentro), así que lo privado puede vivir arriba.
    cell_type = {(a[0] // p, a[1] // p, a[2]): t for a, t in reachable_rooms.items()}
    too_shallow: list[str] = []
    if program.access_depth:
        vlinks = _vertical_room_links(abstract_maze, p)
        starts = [c for c, t in cell_type.items() if t == "entrance"]
        depth = {c: 0 for c in starts}
        dq = deque(starts)
        while dq:
            c = dq.popleft()
            for nb in cell_type:
                if nb not in depth and (_source_adjacent(c, nb) or nb in vlinks.get(c, ())):
                    depth[nb] = depth[c] + 1
                    dq.append(nb)
        for c, t in cell_type.items():
            need = program.access_depth.get(t)
            if need is not None and (c not in depth or depth[c] < need):
                too_shallow.append(t)
    too_shallow = sorted(set(too_shallow))

    # RATIO: conteos proporcionales — al menos 1 `servido` cada `n` de `por` (ej. 1 baño cada 4 salas).
    ratio_unmet: list[tuple[str, str, int]] = []
    for served, per, n in program.ratio:
        need = math.ceil(counts.get(per, 0) / n) if n > 0 else 0
        if counts.get(served, 0) < need:
            ratio_unmet.append((served, per, n))

    # ZONAS (alas): los tipos se agrupan en zonas; dos salas de zonas DISTINTAS no pueden pegarse
    # directo — la circulación (neutra) media la transición. Así el edificio tiene alas, no una mezcla.
    type_zone = {t: z for z, types in program.zones.items() for t in types}
    zone_leak: list[tuple[str, str]] = []
    if program.zones:
        zoned = [(c, type_zone[t]) for c, t in cell_type.items() if t in type_zone]
        seen_pairs: set[tuple[str, str]] = set()
        for i in range(len(zoned)):
            ca, za = zoned[i]
            for cb, zb in zoned[i + 1:]:
                if za != zb and _source_adjacent(ca, cb):
                    pair = tuple(sorted((za, zb)))
                    if pair not in seen_pairs:
                        seen_pairs.add(pair)
                        zone_leak.append(pair)

    ok = (right_space and not missing and not adjacency_missing
          and not isolated and not forbidden_present
          and not too_shallow and not ratio_unmet and not zone_leak)
    return {"ok": ok, "right_space": right_space, "missing": missing, "unreachable": unreachable,
            "adjacency_missing": adjacency_missing, "isolated": isolated,
            "forbidden_present": forbidden_present, "too_shallow": too_shallow,
            "ratio_unmet": ratio_unmet, "zone_leak": zone_leak,
            "counts": dict(counts), "space": content.space}


# ── FABRICACIÓN (Capa 1): bind tag SEMÁNTICO → asset CONCRETO, por motor (corte 3d) ────────────────
@dataclass(frozen=True)
class AssetBinding:
    """La tabla de FABRICACIÓN (Capa 1): liga los tags SEMÁNTICOS del contenido a assets CONCRETOS de un motor.
    Motor-específica → PARIDAD: el MISMO `ContentSpec` verificado + dos bindings (Godot / UE) = dos builds. El
    LOOK nunca entra al kernel ([[jamprotocol-graybox-capa0]]); acá se resuelve, ya con red de seguridad debajo."""
    props: dict[str, str] = field(default_factory=dict)      # tag de prop → ref de mesh (ej. 'crate' → 'SM_Crate.glb')
    materials: dict[str, str] = field(default_factory=dict)  # tipo de sala → ref de material (ej. 'ward' → 'M_Ward')


@dataclass
class FabricatedScene:
    """Plan de VESTIDO JSON-safe que un motor (Godot/UE) recibe como RECEPTOR: dónde va cada mesh y qué material
    lleva cada cuarto tipado. La geometría base (el `Maze3D`) se construye aparte (los render backends). GUARDRAIL:
    cada placement lleva su `blocks` (footprint VERIFICADO) → el motor DEBE darle colisión acorde (bloqueante =
    sólida) para no romper la winnability. `missing_*` = tags/tipos sin binding (no fabricables → avisar, no romper)."""
    space: str | None
    props: list[dict] = field(default_factory=list)          # [{mesh, x, y, z, blocks}]
    rooms: list[dict] = field(default_factory=list)          # [{room_type, material, x, y, z}]  (x,y,z = ancla)
    missing_props: list[str] = field(default_factory=list)
    missing_materials: list[str] = field(default_factory=list)


def fabricate(content: ContentSpec, binding: AssetBinding, *, strict: bool = True) -> FabricatedScene:
    """Viste un `ContentSpec` verificado con un `binding` de motor → `FabricatedScene` (plan JSON-safe para el
    receptor). Cada prop/tipo se resuelve a su asset; los que no tienen binding se reportan en `missing_*` (y,
    si `strict`, no se fabrican — nunca se inventa geometría que rompa el footprint verificado). Paridad: mismo
    `content`, distinto `binding` → distinto build, misma estructura garantizada."""
    from src.mazes.pcg_vocab import PROP_TAGS
    props_out: list[dict] = []
    missing_p: set[str] = set()
    for p in content.props:
        mesh = binding.props.get(p.tag)
        if mesh is None:
            # tag PROCEDURAL (D3): el visual lo fabrica el RECEPTOR desde el contenido (columna piso→techo de
            # pipe_vertical, como los cables) → pasa con mesh=None y NO es missing (no hay nada que curar)
            if not (p.tag in PROP_TAGS and PROP_TAGS[p.tag].procedural):
                missing_p.add(p.tag)
                if strict:
                    continue
        # el TAG viaja con el placement: los receptores derivan comportamiento semántico del contenido
        # (ej. light_panel → luz real en ambos motores; la luz SALE de lo fabricado, no de un rig aparte).
        # rot/ox/oy = la TRANSFORMA de colocación (V1): el receptor orienta y arrima el mesh al muro.
        props_out.append({"mesh": mesh, "tag": p.tag, "x": p.cell[0], "y": p.cell[1], "z": p.cell[2],
                          "blocks": p.blocks, "rot": p.rot, "ox": p.offset[0], "oy": p.offset[1]})
    rooms_out: list[dict] = []
    missing_m: set[str] = set()
    for anchor, rtype in sorted(content.room_types.items()):
        mat = binding.materials.get(rtype)
        if mat is None:
            missing_m.add(rtype)          # sin material del binding → el motor usa color determinista por tipo.
                                          # NO se omite (a diferencia de props): el tinte de sala es dressing
                                          # PLANO sobre el piso, no geometría — no puede romper el footprint.
        w, h = content.room_sizes.get(anchor, (1, 1))
        rooms_out.append({"room_type": rtype, "material": mat, "x": anchor[0], "y": anchor[1], "z": anchor[2],
                          "w": w, "h": h})
    return FabricatedScene(space=content.space, props=props_out, rooms=rooms_out,
                           missing_props=sorted(missing_p), missing_materials=sorted(missing_m))


def cook_props(content: ContentSpec, registry, *, seed: int | None = None):
    """J5 — wire al JamSpace: en vez de dejar cada `@prop` como PLACEHOLDER (tag → glb via AssetBinding), COCINA
    un asset VERIFICADO por la API de Jam para los tags que son familias registradas (bed, table, …); los demás
    siguen por binding. Devuelve un `jam_api.SceneAssets`. Determinista: seed del contenido + índice del prop.
    El Prop viaja como `key` de cada asset cocinado → el receptor lo coloca en su celda con su transforma."""
    from src.jam_api.scene import cook_scene
    base = content.seed if seed is None else seed
    return cook_scene(registry, [(p, p.tag) for p in content.props], seed=base)
