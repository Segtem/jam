"""Anidado verificable — el KEYSTONE del JamMap fractal (escala × aspecto).

Visión: [[2026-06-25-VISION-JamMap-Fractal-Multi-Escala-Multi-Aspecto-v1.0]]. Un JamMap deja de ser UN
mapa y pasa a ser un primitivo que **se anida en sí mismo**: una habitación dentro de una casa, una casa
dentro de una cuadra, una cuadra dentro de una ciudad. "X con X" a toda escala = la MISMA operación de
anidado, repetida — y RECURSIVA: el interior de una región puede ser, a su vez, otra composición anidada.

El problema #1 es la TRACTABILIDAD: verificar el todo expandiendo cada interior (BFS sobre BFS) explota, y
la Capa 0 existe *porque* verificar es barato. La solución es la **verificación jerárquica**:

  1. Se verifica un HIJO (¿sus puertos están internamente conectados?) y se lo CONGELA → un CONTRATO chico
     (qué puerto alcanza qué puerto adentro). Si el hijo es a su vez compuesto, su conectividad se computa
     usando los contratos de SUS hijos — la recursión se "aplana" un nivel por vez. Reusa la idea de la
     promoción (estructura congelada = identidad content-addressed) aplicada a un sub-mapa.
  2. El PADRE compone hijos **sólo por el contrato**: ve cada hijo como un nodo con aristas puerto↔puerto,
     NUNCA re-explora su interior — sin importar cuán profundo sea. BFS sobre CONTRATOS, no BFS sobre BFS.

La garantía que lo vuelve confiable (y la que testeamos): **verificar jerárquico da la MISMA winnability
que verificar plano** (expandiendo todo, a cualquier profundidad), pero explorando muchísimos menos
estados. `solve_hier` ≡ `solve_flat` en winnability, y `states_hier << states_flat`. Esa equivalencia es
el corazón del keystone.

Alcance v1 (honesto): el contrato es de NAVEGACIÓN PURA (conectividad estructural vía `Maze3D.neighbors`,
sin llaves/flags cruzando el borde del hijo). Las mecánicas dentro de un hijo se quedan adentro; el acople
cross-borde y cross-aspecto (gas+chispa, llave de una región que abre otra) es el riesgo #2 → v2. El eje
ASPECTO (canales eléctrico/gas, cada uno con su alfabeto chico y su oráculo) se monta sobre este mismo
mecanismo: un canal es otro JamMap sobre las mismas coordenadas, con su propio `seal`/contrato.
"""
from __future__ import annotations

import hashlib
import re
from collections import deque
from dataclasses import dataclass, field

from src.mazes.maze3d import GOAL, PLAYER, Maze3D

Cell = tuple[int, int, int]
Node = tuple[str, Cell]   # nodo del grafo COMPUESTO: (tag-de-ruta, celda). "@" = padre raíz; "r0", "r0/s0"… = instancias anidadas


# ── el hijo: un sub-JamMap (hoja o compuesto) con puertos ─────────────────────
@dataclass
class Region:
    """Un sub-JamMap con PUERTOS nombrados en su borde — las celdas por las que el padre se conecta a él.
    El `body` es un JamMap completo y verificable: o una HOJA (`Maze3D`) o un COMPUESTO (`HierMaze`, ya
    anidado). Hacia afuera, el hijo SÓLO expone sus puertos (encapsulamiento) — da igual qué tan profundo
    sea por dentro. `name` describe el tipo (ej. 'habitacion', 'casa', 'cuadra')."""
    body: "Maze3D | HierMaze"
    ports: dict[str, Cell]            # nombre → celda-puerto (debe ser transitable en el espacio TOP del body)
    name: str = "region"


@dataclass(frozen=True)
class RegionContract:
    """El hijo VERIFICADO y CONGELADO, colapsado a lo único que el padre necesita saber: qué puerto
    alcanza qué puerto por dentro. `region_id` es content-addressed (misma estructura = misma identidad,
    como un elite promovido; para un compuesto, incluye los ids de SUS contratos → recursivo). Esto es la
    "hoja verificada" de la jerarquía: el padre razona sobre esto, nunca sobre el interior."""
    region_id: str
    name: str
    ports: tuple[str, ...]
    reachable: frozenset[tuple[str, str]]   # pares (a, b): desde el puerto a se alcanza el puerto b adentro


# ── composición: el padre + hijos colocados ──────────────────────────────────
@dataclass
class Placement:
    """Un hijo COLOCADO en un padre: la región + su contrato sellado + el ALINEAMIENTO (qué celda del
    padre se conecta a qué puerto del hijo) + un id de instancia único (el mismo hijo puede colocarse
    varias veces). El alineamiento ES el contrato de conexión de borde: padre y hijo se pegan SÓLO por
    los puertos declarados."""
    region: Region
    contract: RegionContract
    align: dict[str, Cell]   # nombre-de-puerto → celda del PADRE que se conecta a ese puerto
    inst: str = "i0"


@dataclass
class HierMaze:
    """Un JamMap JERÁRQUICO: un padre (`Maze3D`, con su `P` player y `G` goal cuando es el mapa raíz) +
    hijos colocados. El padre y los hijos son todos JamMaps; la jerarquía los compone por contratos de
    puerto. Como una `Region` puede tener un `HierMaze` por `body`, la estructura es RECURSIVA a toda
    escala."""
    parent: Maze3D
    placements: list[Placement] = field(default_factory=list)


def _top_maze(body: "Maze3D | HierMaze") -> Maze3D:
    """El `Maze3D` del nivel SUPERIOR de un body: el maze mismo (hoja) o el padre de la composición."""
    return body if isinstance(body, Maze3D) else body.parent


# ── el sello: verificar + congelar un hijo (recursivo) ───────────────────────
def _structural_reachable(maze: Maze3D, start: Cell) -> set[Cell]:
    """Celdas alcanzables desde `start` por el grafo ESTRUCTURAL del maze (`neighbors`: 4-dir + verticales
    + portales/costuras…). Navegación pura: NO aplica gating de llaves/compuertas/trampas (eso lo resuelve
    `solve_3d` sobre el estado; el contrato v1 es de conectividad). BFS de conjunto alcanzable."""
    seen: set[Cell] = {start}
    queue: deque[Cell] = deque([start])
    while queue:
        c = queue.popleft()
        for n in maze.neighbors(c):
            if n not in seen:
                seen.add(n)
                queue.append(n)
    return seen


def _bfs_reach(adj: dict[Node, list[Node]], start: Node) -> set[Node]:
    """Conjunto de nodos alcanzables desde `start` en un grafo compuesto (para sellar un body compuesto:
    la conectividad puerto↔puerto se mide sobre el grafo JERÁRQUICO de su interior, usando sub-contratos)."""
    if start not in adj:
        return set()
    seen: set[Node] = {start}
    queue: deque[Node] = deque([start])
    while queue:
        c = queue.popleft()
        for n in adj.get(c, ()):  # noqa: B007
            if n not in seen:
                seen.add(n)
                queue.append(n)
    return seen


def _port_reachable_pairs(region: Region) -> set[tuple[str, str]]:
    """Pares (a, b) de puertos tales que desde a se alcanza b POR DENTRO de la región. Hoja → BFS
    estructural sobre el maze. Compuesto → BFS sobre el grafo jerárquico del interior (que ya usa los
    contratos de los sub-hijos, nunca sus interiores) — así la recursión se aplana un nivel por vez."""
    body = region.body
    pairs: set[tuple[str, str]] = set()
    if isinstance(body, Maze3D):
        for a_name, a_cell in region.ports.items():
            reach = _structural_reachable(body, a_cell)
            for b_name, b_cell in region.ports.items():
                if a_name != b_name and b_cell in reach:
                    pairs.add((a_name, b_name))
    else:
        g = hier_graph(body)          # interior colapsado a contratos (los puertos viven en el padre, tag "@")
        for a_name, a_cell in region.ports.items():
            reach = _bfs_reach(g, ("@", a_cell))
            for b_name, b_cell in region.ports.items():
                if a_name != b_name and ("@", b_cell) in reach:
                    pairs.add((a_name, b_name))
    return pairs


def _content_payload(region: Region) -> str:
    """Texto canónico para el hash content-addressed. Hoja → pisos + puertos. Compuesto → nombre + puertos
    + pisos del padre + (instancia, region_id del sub-contrato, alineamiento) de cada sub-hijo. Como los
    sub-`region_id` ya son content-addressed, el id de un compuesto es recursivamente estable."""
    body = region.body
    if isinstance(body, Maze3D):
        return repr((tuple(tuple(g) for g in body.floors), tuple(sorted(region.ports.items()))))
    return repr((
        region.name,
        tuple(sorted(region.ports.items())),
        tuple(tuple(g) for g in body.parent.floors),
        tuple(sorted(
            (pl.inst, pl.contract.region_id, tuple(sorted(pl.align.items())))
            for pl in body.placements
        )),
    ))


def seal_region(region: Region, *, dsl_text: str | None = None) -> RegionContract:
    """VERIFICA + CONGELA un hijo (paso-hoja de la jerarquía, recursivo): corre la conectividad interna
    entre cada par de puertos y devuelve el CONTRATO (pares puerto→puerto alcanzables). Content-addressed:
    el id sale del hash de la estructura, igual que un elite promovido — misma estructura, misma identidad,
    cacheable. Lanza si un puerto no es una celda transitable del espacio top (un puerto tapiado no existe)."""
    top = _top_maze(region.body)
    for name, cell in region.ports.items():
        if not top.is_open(*cell):
            raise ValueError(f"puerto {name!r} en {cell} no es una celda transitable de la region")
    reachable = _port_reachable_pairs(region)
    payload = dsl_text if dsl_text is not None else _content_payload(region)
    region_id = hashlib.sha1(payload.encode("utf-8")).hexdigest()[:8]
    return RegionContract(region_id, region.name, tuple(sorted(region.ports)), frozenset(reachable))


# ── los dos grafos compuestos: PLANO (caro, oráculo) vs JERÁRQUICO (barato) ───
def _expand_maze(adj: dict[Node, list[Node]], prefix: str, maze: Maze3D) -> None:
    """Vuelca el grafo estructural de un `Maze3D` en `adj`, con cada celda etiquetada `(prefix, celda)`."""
    for c in maze.open_cells():
        adj.setdefault((prefix, c), []).extend((prefix, n) for n in maze.neighbors(c))


def _attach(adj: dict[Node, list[Node]], parent_prefix: str, child_prefix: str, pl: Placement) -> None:
    """Aristas de BORDE (contrato de conexión): pega cada celda del padre a su puerto del hijo,
    bidireccional (una puerta se cruza en ambos sentidos)."""
    for port_name, parent_cell in pl.align.items():
        a: Node = (parent_prefix, parent_cell)
        b: Node = (child_prefix, pl.region.ports[port_name])
        adj.setdefault(a, []).append(b)
        adj.setdefault(b, []).append(a)


def _expand_flat(adj: dict[Node, list[Node]], prefix: str, body: "Maze3D | HierMaze") -> None:
    """Expande el interior COMPLETO de un body bajo `prefix`, RECURSIVO: si el body es compuesto, expande
    su padre y baja a cada sub-hijo (rutas anidadas `prefix/inst`). Es la verificación cara/ingenua (BFS
    sobre BFS sobre BFS…) que sirve de oráculo de referencia para la equivalencia."""
    if isinstance(body, Maze3D):
        _expand_maze(adj, prefix, body)
        return
    _expand_maze(adj, prefix, body.parent)
    for pl in body.placements:
        child = f"{prefix}/{pl.inst}"
        _expand_flat(adj, child, pl.region.body)
        _attach(adj, prefix, child, pl)


def flat_graph(hier: HierMaze) -> dict[Node, list[Node]]:
    """Grafo COMPUESTO PLANO: el padre raíz + el INTERIOR COMPLETO de cada hijo expandido a toda
    profundidad. La verificación cara; oráculo de referencia para la equivalencia."""
    adj: dict[Node, list[Node]] = {}
    _expand_maze(adj, "@", hier.parent)
    for pl in hier.placements:
        _expand_flat(adj, pl.inst, pl.region.body)
        _attach(adj, "@", pl.inst, pl)
    return adj


def hier_graph(hier: HierMaze) -> dict[Node, list[Node]]:
    """Grafo COMPUESTO JERÁRQUICO: el padre raíz + cada hijo COLAPSADO a su contrato (sólo nodos-puerto y
    aristas puerto↔puerto del contrato). NO expande interiores — a NINGUNA profundidad, porque el contrato
    del hijo ya encapsula su propia recursión. BFS sobre contratos. Es lo que hace tratable el anidado a
    toda escala."""
    adj: dict[Node, list[Node]] = {}
    _expand_maze(adj, "@", hier.parent)
    for pl in hier.placements:
        ports = pl.region.ports
        for a_name, b_name in pl.contract.reachable:     # aristas puerto↔puerto del CONTRATO (interior colapsado)
            adj.setdefault((pl.inst, ports[a_name]), []).append((pl.inst, ports[b_name]))
        for port_name in pl.align:                        # asegura que los nodos-puerto existan aunque no tengan contrato
            adj.setdefault((pl.inst, ports[port_name]), [])
        _attach(adj, "@", pl.inst, pl)
    return adj


# ── los oráculos de winnability sobre el grafo compuesto ─────────────────────
def _bfs(adj: dict[Node, list[Node]], start: Node, goal: Node) -> dict:
    """BFS genérico sobre un grafo de nodos. Devuelve {winnable, steps, states_explored} — mismo contrato
    espiritual que `solve_3d` pero sobre el grafo compuesto. `states_explored` = nodos sacados de la cola
    (la métrica de COSTO que distingue jerárquico de plano)."""
    if start not in adj:
        return {"winnable": False, "steps": None, "states_explored": 0}
    prev: dict[Node, int] = {start: 0}
    queue: deque[Node] = deque([start])
    explored = 0
    while queue:
        cur = queue.popleft()
        explored += 1
        if cur == goal:
            return {"winnable": True, "steps": prev[cur], "states_explored": explored}
        for nxt in adj.get(cur, ()):  # noqa: B007
            if nxt not in prev:
                prev[nxt] = prev[cur] + 1
                queue.append(nxt)
    return {"winnable": False, "steps": None, "states_explored": explored}


def _endpoints(parent: Maze3D) -> tuple[Node, Node]:
    start = parent.find(PLAYER)
    goal = parent.find(GOAL)
    if start is None or goal is None:
        raise ValueError("el padre necesita player (P) y goal (G)")
    return ("@", start), ("@", goal)


def solve_flat(hier: HierMaze) -> dict:
    """Winnability EXPANDIENDO todo (oráculo de referencia). Caro: explora cada celda de cada hijo, recursivo."""
    start, goal = _endpoints(hier.parent)
    return _bfs(flat_graph(hier), start, goal)


def solve_hier(hier: HierMaze) -> dict:
    """Winnability JERÁRQUICA: usa los contratos de los hijos, nunca su interior. Barato y — por
    construcción del contrato — con la MISMA winnability que `solve_flat` (lo que testeamos)."""
    start, goal = _endpoints(hier.parent)
    return _bfs(hier_graph(hier), start, goal)


def verify_hierarchical(hier: HierMaze) -> dict:
    """Reporte del keystone: corre ambos oráculos y CONFIRMA la equivalencia de winnability + cuánto
    AHORRA la jerarquía (estados plano vs jerárquico). El campo `equivalent` debe ser siempre True; si
    alguna vez es False, el contrato de algún hijo no captura su conectividad (bug del sello)."""
    flat = solve_flat(hier)
    hierr = solve_hier(hier)
    saved = flat["states_explored"] - hierr["states_explored"]
    return {
        "winnable": hierr["winnable"],
        "equivalent": flat["winnable"] == hierr["winnable"],
        "states_flat": flat["states_explored"],
        "states_hier": hierr["states_explored"],
        "states_saved": saved,
        "speedup": round(flat["states_explored"] / hierr["states_explored"], 2) if hierr["states_explored"] else None,
    }


# ── SURFACE EN EL DSL DE TEXTO (eje ESCALA: habitación→casa→cuadra…) ──────────────────────────────
# El anidado es dueño de su sintaxis (igual que nav vive en ascii_map y el recurso en resource). Sintaxis
# del ADR de vocabulario ([[2026-06-25-ADR-Vocabulario-JamMap-Canales-y-Directivas]]):
#   [Region <tipo>]            # un SUB-MAPA nombrado (su grilla; v1 = un piso) — el "X" que se anida
#   #####
#   #...#
#   #####
#   [Piso 0]                   # el PADRE raíz (con @ player y G goal)
#   ...
#   @region <inst> = <tipo>    # INSTANCIA un hijo de ese tipo
#   @port   <inst>.<p> x,y,z   # un PUERTO del hijo (celda de su borde, en coords del hijo)
#   @link   <inst>.<p> <-> x,y,z   # PEGA ese puerto a una celda del PADRE (contrato de borde)
_REGION_HDR = re.compile(r"^\[Region\s+(\w+)\]\s*$")
_REGION_RE = re.compile(r"@region\s+(\w+)\s*=\s*(\w+)")
_PORT_RE = re.compile(r"@port\s+(\w+)\.(\w+)\s+(\d+),(\d+),(\d+)")
_LINK_RE = re.compile(r"@link\s+(\w+)\.(\w+)\s*<->\s*(\d+),(\d+),(\d+)")


def parse_nested(text: str) -> "HierMaze | None":
    """DSL JamMap ANIDADO → `HierMaze` (o None si no trae `[Region]`/`@region`). Cada `[Region <tipo>]`
    define un sub-mapa; el padre lo INSTANCIA con `@region` y lo pega por `@port`/`@link`. Las regiones se
    SELLAN (contrato) → el `HierMaze` se verifica jerárquico (barato) ≡ plano. v1: regiones de un piso."""
    from src.mazes.ascii_map import parse as parse_nav
    region_rows: dict[str, list[str]] = {}
    parent_lines: list[str] = []
    cur: str | None = None
    for raw in text.splitlines():
        s = raw.strip()
        mr = _REGION_HDR.match(s)
        if mr:
            cur = mr[1]; region_rows[cur] = []
            continue
        if cur is not None and s and not s.startswith(("@", "[")):
            region_rows[cur].append(raw)            # fila de grilla del HIJO
            continue
        cur = None                                  # vacío / @ / otro header → fin del bloque region
        parent_lines.append(raw)

    regions: dict[str, str] = {m[1]: m[2] for m in (_REGION_RE.match(l.strip())
                                                    for l in parent_lines) if m}
    if not regions:
        return None
    ports: dict[str, dict[str, Cell]] = {}
    align: dict[str, dict[str, Cell]] = {}
    for l in parent_lines:
        if (m := _PORT_RE.match(l.strip())):
            ports.setdefault(m[1], {})[m[2]] = (int(m[3]), int(m[4]), int(m[5]))
        elif (m := _LINK_RE.match(l.strip())):
            align.setdefault(m[1], {})[m[2]] = (int(m[3]), int(m[4]), int(m[5]))

    parent = parse_nav("\n".join(parent_lines))      # el padre: las directivas anidadas las ignora (dígitos)
    placements: list[Placement] = []
    for inst, typ in regions.items():
        if typ not in region_rows:
            raise ValueError(f"@region {inst} = {typ}: no hay bloque [Region {typ}]")
        body = Maze3D.from_layers([region_rows[typ]])
        region = Region(body, ports.get(inst, {}), name=typ)
        contract = seal_region(region)
        placements.append(Placement(region, contract, align.get(inst, {}), inst=inst))
    return HierMaze(parent, placements)


def render_nested(hier: "HierMaze") -> list[str]:
    """`HierMaze` → líneas del DSL anidado (inversa de `parse_nested`; round-trip estable). v1: un piso por región."""
    from src.mazes.ascii_map import render as render_nav
    out: list[str] = []
    for name, body in {pl.region.name: pl.region.body for pl in hier.placements}.items():
        out.append(f"[Region {name}]")
        out += _top_maze(body).floors[0]
    out += render_nav(hier.parent).splitlines()
    for pl in hier.placements:
        out.append(f"@region {pl.inst} = {pl.region.name}")
        for p, c in pl.region.ports.items():
            out.append(f"@port {pl.inst}.{p} {c[0]},{c[1]},{c[2]}")
        for p, c in pl.align.items():
            out.append(f"@link {pl.inst}.{p} <-> {c[0]},{c[1]},{c[2]}")
    return out
