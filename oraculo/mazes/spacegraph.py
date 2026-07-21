"""JamSpace GRAFO-PRIMERO (G1) — el modelo canónico y su oráculo.

DECISIÓN bendecida (Brian 2026-07-07, ver DECISION-JamSpace-Grafo-Primero en el vault): la
fuente de verdad de JamSpace es el GRAFO ANOTADO — nodos = cuartos/zonas (tipo + intención
métrica + mecánicas de nodo), aristas = conexiones (clase + mecánicas de ARISTA: la llave y el
flag viven en la puerta, donde siempre debieron). La grilla ASCII pasa a ser UNA notación de
entrada (importador `from_maze`); la geometría es una etapa de REALIZACIÓN aparte (floorplan =
primer realizador, verificado por isomorfismo).

Este módulo es el CONTRATO de G1: el modelo + el oráculo de winnability grafo-nativo + los
chequeos estáticos de realizabilidad (rechazo temprano barato, informe de embedding 2026-07-07).
Los canales (eléctrico/recurso/tareas) se portan en un corte posterior (G1.5) sobre este mismo
modelo. La sintaxis de TEXTO del DSL (G0/G2) se define aparte, informada por la investigación
mission/space — este modelo es independiente de la notación.

Semánticas del oráculo (decisiones de contrato):
- Traversal por ARISTA: `door_id` exige tener la llave; `gate_flag` exige el flag ON.
- `key` de nodo: pickup idempotente al ENTRAR al nodo.
- `switch` de nodo: al visitar el nodo el jugador PUEDE togglear el flag (el estado se BIFURCA:
  presionar o no). Nota: en la grilla pisar el switch FORZABA el toggle; el grafo modela la
  elección real del jugador — superset honesto, documentado como divergencia consciente.
- `hazard` de nodo: no se puede ENTRAR con la trampa armada (flag "" = armada siempre → nodo
  intransitable; flag no-vacío = el flag ON la desarma). Igual que el oráculo de grilla
  (entrar = derrota ⇒ el BFS lo prohíbe).
- `optimal_steps` = ARISTAS recorridas (no comparable con los pasos de celda del legacy).
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from itertools import combinations

from .maze3d import Maze3D  # re-cableado 2026-07-21: era `src.mazes.maze3d`

# "shortcut" = atajo DECLARADO (intención cíclica, D3 del informe mission/space): misma semántica
# de traversal que una arista gateada, pero el generador declara que ES un loop-back a propósito
# (el gate de interés puede premiarlo; un shortcut sin gating es relleno y se descarta)
EDGE_KINDS = ("door", "open", "stair", "portal", "shortcut", "cable")
NAV_EDGE_KINDS = ("door", "open", "stair", "portal", "shortcut")
# "cable" (Corte 2) = arista del CANAL ELÉCTRICO: conduce energía entre nodos, NO es un paso
# navegable por sí sola. El oráculo eléctrico (spacegraph_channels.all_powered_graph) hace BFS
# sobre estas aristas desde las fuentes; la nav (solve_graph) las ignora.


@dataclass(frozen=True)
class GraphNode:
    """Un cuarto/zona. `type` = tipo del vocabulario PCG (ward/corridor/...); `dims` = intención
    métrica opcional (ancho, profundidad en m — el realizador la respeta como objetivo);
    mecánicas de NODO: `key` (se levanta acá), `switch` (acá se puede togglear ese flag),
    `hazard` (trampa; "" = siempre armada, "f" = el flag f la desarma). `floor` = piso sugerido
    (la jerarquía real de sub-grafos llega en G4)."""
    id: str
    type: str | None = None
    dims: tuple[float, float] | None = None
    key: str | None = None
    switch: str | None = None
    hazard: str | None = None
    start: bool = False
    goal: bool = False
    floor: int = 0
    # tags INFORMATIVOS (D5 del informe mission/space): intención categórica (hub/leaf/tension)
    # para nichos MAP-Elites y realizadores. REGLA DURA de la spec: un tag JAMÁS es condición de
    # pasaje del oráculo — si un tag necesita dientes, pasa a `program` (regla verificable).
    tags: tuple[str, ...] = ()
    # canales NO-nav (Corte 2, G1.5) — aspectos extra verificados por spacegraph_channels:
    # `power` ∈ {"source","load",None}: nodo del canal eléctrico (source genera, load debe quedar
    # energizada vía aristas cable). `drain`/`refill` = (recurso, monto): entrar al nodo consume/
    # repone ese recurso (BFS presupuestado de solve_survival_graph, con piso `lo` y overfill finito).
    power: str | None = None
    drain: tuple[str, int] | None = None
    refill: tuple[str, int] | None = None
    # jerarquía (Corte 3, G4): si `expand` está, este nodo se EXPANDE a ese sub-grafo; sus aristas
    # se re-conectan a los `ports` del sub-grafo. El oráculo APLANA (flatten_hierarchy) antes de
    # resolver/realizar — jerárquico ≡ plano. None = nodo hoja (retro-compatible).
    expand: str | None = None
    # canal de TAREAS-DAG (Ronda 2, Corte 3): `(task_id, deps)` — el nodo hospeda esa tarea, que se
    # completa al ENTRAR si sus `deps` (ids de otras tareas) ya están hechas. Ganar exige todas las
    # tareas hechas + goal (solve_tasks_graph en spacegraph_channels). None = sin tarea.
    task: tuple[str, tuple[str, ...]] | None = None


@dataclass(frozen=True)
class GraphEdge:
    """Una conexión. `kind` ∈ EDGE_KINDS ('open' = vano sin hoja; 'door' puede llevar mecánica;
    'stair' = vertical; 'portal' = no-euclidiana). Las MECÁNICAS DE ARISTA viven acá:
    `door_id` (llave que la abre) y/o `gate_flag` (flag que la abre). No dirigida."""
    a: str
    b: str
    kind: str = "door"
    door_id: str | None = None
    gate_flag: str | None = None


@dataclass(frozen=True)
class Subgraph:
    """Un sub-grafo reusable (Corte 3, G4): un módulo espacial que un nodo `@expand` inserta. `ports`
    = ids de nodos-puerto (en orden de declaración) que ligan a las aristas del nodo expandido; los
    sub-grafos NO tienen start/goal (son interiores). `flatten_hierarchy` los inlina."""
    id: str
    nodes: dict[str, GraphNode] = field(default_factory=dict)
    edges: list[GraphEdge] = field(default_factory=list)
    ports: list[str] = field(default_factory=list)


@dataclass
class SpaceGraph:
    """El grafo anotado completo. `nodes` por id; `edges` no dirigidas (a↔b). `space` = el tipo
    de espacio declarado (`@space`, programa de la Pista U); `seed` = del `@seed` del texto."""
    nodes: dict[str, GraphNode] = field(default_factory=dict)
    edges: list[GraphEdge] = field(default_factory=list)
    space: str | None = None
    seed: int = 0
    # presupuestos del canal RECURSO (Corte 2): `nombre → (start, lo, hi)`, del `@resource fuel 10 0 10`.
    # Vacío = el grafo no declara canal recurso (retro-compatible).
    resources: dict[str, tuple[int, int, int]] = field(default_factory=dict)
    # sub-grafos declarados para la jerarquía (Corte 3): `id → Subgraph`. Vacío = grafo plano.
    subgraphs: dict[str, "Subgraph"] = field(default_factory=dict)

    def start(self) -> str | None:
        return next((n.id for n in self.nodes.values() if n.start), None)

    def goal(self) -> str | None:
        return next((n.id for n in self.nodes.values() if n.goal), None)

    def neighbors(self, node_id: str) -> list[tuple[str, "GraphEdge"]]:
        """Vecinos con su arista (no dirigida)."""
        out = []
        for e in self.edges:
            if e.a == node_id:
                out.append((e.b, e))
            elif e.b == node_id:
                out.append((e.a, e))
        return out


def solve_graph(graph: SpaceGraph, max_states: int = 200_000, *,
                flags0: frozenset[str] = frozenset()) -> dict:
    """El oráculo de winnability GRAFO-NATIVO: BFS sobre (nodo, llaves, flags) con las semánticas
    del docstring del módulo. → {"solvable", "optimal_steps" (aristas), "path" (ids de nodos del
    camino óptimo), "states_explored", "truncated" (True si max_states cortó — conservador:
    truncado ⇒ no certificado)}. Sin start o sin goal → solvable False (con razón en "reason")."""
    start = graph.start()
    goal = graph.goal()
    if start is None:
        return {"solvable": False, "optimal_steps": None, "path": [], "states_explored": 0,
                "truncated": False, "reason": "missing start"}
    if goal is None:
        return {"solvable": False, "optimal_steps": None, "path": [], "states_explored": 0,
                "truncated": False, "reason": "missing goal"}
    if start not in graph.nodes or goal not in graph.nodes:
        return {"solvable": False, "optimal_steps": None, "path": [], "states_explored": 0,
                "truncated": False, "reason": "start/goal reference missing"}

    empty = frozenset()
    initial_flags = frozenset(flags0)

    def _deadly(node: GraphNode, flags: frozenset[str]) -> bool:
        return node.hazard is not None and (node.hazard == "" or node.hazard not in flags)

    def _collect(node: GraphNode, keys: frozenset[str]) -> frozenset[str]:
        return keys | {node.key} if node.key is not None else keys

    def _path(prev: dict[tuple[str, frozenset[str], frozenset[str]], tuple | None],
              state: tuple[str, frozenset[str], frozenset[str]]) -> list[str]:
        states = [state]
        cur = state
        while prev[cur] is not None:
            cur = prev[cur]
            states.append(cur)
        states.reverse()
        out: list[str] = []
        for node_id, _keys, _flags in states:
            if not out or out[-1] != node_id:
                out.append(node_id)
        return out

    start_node = graph.nodes[start]
    if _deadly(start_node, initial_flags):
        return {"solvable": False, "optimal_steps": None, "path": [], "states_explored": 0,
                "truncated": False, "reason": "start blocked by hazard"}

    start_state = (start, _collect(start_node, empty), initial_flags)
    dist: dict[tuple[str, frozenset[str], frozenset[str]], int] = {start_state: 0}
    prev: dict[tuple[str, frozenset[str], frozenset[str]], tuple | None] = {start_state: None}
    queue: deque[tuple[str, frozenset[str], frozenset[str]]] = deque([start_state])
    explored = 0

    while queue:
        cur = queue.popleft()
        node_id, keys, flags = cur
        if node_id == goal:
            path = _path(prev, cur)
            return {"solvable": True, "optimal_steps": dist[cur], "path": path,
                    "states_explored": explored, "truncated": False}
        if explored >= max_states:
            return {"solvable": False, "optimal_steps": None, "path": [],
                    "states_explored": explored, "truncated": True, "reason": "max_states"}
        explored += 1

        node = graph.nodes[node_id]
        if node.switch is not None:
            toggled_flags = flags ^ {node.switch}
            nxt = (node_id, keys, frozenset(toggled_flags))
            if dist[cur] < dist.get(nxt, float("inf")):
                dist[nxt] = dist[cur]
                prev[nxt] = cur
                queue.appendleft(nxt)

        for next_id, edge in graph.neighbors(node_id):
            if edge.kind == "cable":
                continue
            if edge.door_id is not None and edge.door_id not in keys:
                continue
            if edge.gate_flag is not None and edge.gate_flag not in flags:
                continue
            next_node = graph.nodes.get(next_id)
            if next_node is None or _deadly(next_node, flags):
                continue
            next_keys = _collect(next_node, keys)
            nxt = (next_id, next_keys, flags)
            nd = dist[cur] + 1
            if nd < dist.get(nxt, float("inf")):
                dist[nxt] = nd
                prev[nxt] = cur
                queue.append(nxt)

    return {"solvable": False, "optimal_steps": None, "path": [],
            "states_explored": explored, "truncated": False}


def realizable_static(graph: SpaceGraph) -> list[str]:
    """Rechazo TEMPRANO de grafos irrealizables/malformados (antes de intentar embedder o
    realizador): lista de fallas, vacía = pasa.
    - Referencias rotas (arista a nodo inexistente), aristas duplicadas (mismo par), self-loops,
      `kind` fuera de EDGE_KINDS, ids repetidos... (integridad).
    - Exactamente un start y un goal.
    - Conectividad (ignorando mecánicas): todo nodo alcanzable desde start por aristas.
    - PLANARIDAD barata (informe de embedding): E > 3V - 6 ⇒ no planar ⇒ falla. Poda recursiva
      de nodos de grado ≤ 2 y detección de K5/K3,3 en el residuo (los portales NO cuentan para
      planaridad — son no-euclidianos a propósito; las stairs tampoco: conectan pisos).
    - Grado ≤ 8 por nodo (límite del realizador Kandinsky-style; advertencia dura por ahora)."""
    failures: list[str] = []

    ids = [node.id for node in graph.nodes.values()]
    seen_ids: set[str] = set()
    duplicate_ids: set[str] = set()
    for node_id in ids:
        if node_id in seen_ids:
            duplicate_ids.add(node_id)
        seen_ids.add(node_id)
    for node_id in sorted(duplicate_ids):
        failures.append(f"id de nodo duplicado: {node_id}")
    for key, node in graph.nodes.items():
        if key != node.id:
            failures.append(f"nodo guardado bajo id inconsistente: {key} != {node.id}")

    valid_pairs: set[tuple[tuple[str, str], str]] = set()
    duplicate_pairs: set[tuple[str, str]] = set()
    degree: dict[str, int] = {node_id: 0 for node_id in graph.nodes}
    for edge in graph.edges:
        if edge.kind not in EDGE_KINDS:
            failures.append(f"kind invalido en arista {edge.a}-{edge.b}: {edge.kind}")
        if edge.a == edge.b:
            failures.append(f"self-loop: {edge.a}")
            continue
        if edge.a not in graph.nodes or edge.b not in graph.nodes:
            failures.append(f"referencia rota en arista {edge.a}-{edge.b}")
            continue
        pair = tuple(sorted((edge.a, edge.b)))
        aspect = "cable" if edge.kind == "cable" else "physical"
        pair_key = (pair, aspect)
        if pair_key in valid_pairs:
            duplicate_pairs.add(pair)
        valid_pairs.add(pair_key)
        if edge.kind != "cable":
            degree[edge.a] += 1
            degree[edge.b] += 1
    for a, b in sorted(duplicate_pairs):
        failures.append(f"arista duplicada: {a}-{b}")

    starts = [node.id for node in graph.nodes.values() if node.start]
    goals = [node.id for node in graph.nodes.values() if node.goal]
    if len(starts) != 1:
        failures.append(f"se requiere exactamente 1 start (hay {len(starts)})")
    if len(goals) != 1:
        failures.append(f"se requiere exactamente 1 goal (hay {len(goals)})")

    if len(starts) == 1 and graph.nodes:
        adj: dict[str, set[str]] = {node_id: set() for node_id in graph.nodes}
        for edge in graph.edges:
            if (edge.kind != "cable" and edge.a in graph.nodes
                    and edge.b in graph.nodes and edge.a != edge.b):
                adj[edge.a].add(edge.b)
                adj[edge.b].add(edge.a)
        reached: set[str] = set()
        queue = deque([starts[0]])
        while queue:
            node_id = queue.popleft()
            if node_id in reached:
                continue
            reached.add(node_id)
            queue.extend(adj[node_id] - reached)
        missing = set(graph.nodes) - reached
        if missing:
            failures.append(f"grafo no conectado: {','.join(sorted(missing))}")

    plane_edges = [
        tuple(sorted((edge.a, edge.b)))
        for edge in graph.edges
        if edge.kind not in {"stair", "portal", "cable"}
        and edge.a in graph.nodes
        and edge.b in graph.nodes
        and edge.a != edge.b
    ]
    plane_pairs = set(plane_edges)
    v = len(graph.nodes)
    e = len(plane_pairs)
    if v >= 3 and e > 3 * v - 6:
        failures.append(f"no planar barato: E={e} > 3V-6={3 * v - 6}")

    plane_adj: dict[str, set[str]] = {node_id: set() for node_id in graph.nodes}
    for a, b in plane_pairs:
        plane_adj[a].add(b)
        plane_adj[b].add(a)

    # Aproximacion barata: poda grado<=2 y busca K5/K3,3 literales en el residuo.
    # No intenta deteccion general de minors; el realizador sigue siendo el juez final.
    residue = set(graph.nodes)
    changed = True
    while changed:
        changed = False
        low_degree = {node_id for node_id in residue if len(plane_adj[node_id] & residue) <= 2}
        if low_degree:
            residue -= low_degree
            changed = True

    for group in combinations(sorted(residue), 5):
        if all(b in plane_adj[a] for a, b in combinations(group, 2)):
            failures.append(f"subgrafo K5 en residuo planar: {','.join(group)}")
            break

    found_k33 = False
    for group in combinations(sorted(residue), 6):
        group_set = set(group)
        first = group[0]
        for left_tail in combinations(group[1:], 2):
            left = {first, *left_tail}
            right = group_set - left
            if all(b in plane_adj[a] for a in left for b in right):
                failures.append("subgrafo K3,3 en residuo planar: "
                                f"{','.join(sorted(left))}|{','.join(sorted(right))}")
                found_k33 = True
                break
        if found_k33:
            break

    # V1: el grado IN-PLANE (open/door/shortcut) se capea en 4 — un nodo de una celda en la
    # grilla sintetica del puente solo puede recibir 4 cadenas ortogonales (los hubs multi-celda
    # llegan en V2). stairs/portales no consumen adyacencia de grilla y van aparte (cap total 8).
    plane_deg: dict[str, int] = {node_id: 0 for node_id in graph.nodes}
    for edge in graph.edges:
        if (edge.kind not in ("stair", "portal", "cable")
                and edge.a in plane_deg and edge.b in plane_deg):
            plane_deg[edge.a] += 1
            plane_deg[edge.b] += 1
    for node_id, deg in sorted(plane_deg.items()):
        if deg > 4:
            failures.append(f"grado in-plane > 4 (V1): {node_id} tiene {deg}")
    for node_id, deg in sorted(degree.items()):
        if deg > 8:
            failures.append(f"grado > 8: {node_id} tiene {deg}")

    return failures


def from_maze(maze: Maze3D, *, prune_unreachable: bool = True) -> SpaceGraph:
    """El IMPORTADOR legacy: grilla → grafo. Celdas abiertas = nodos (id determinista "x,y,z"),
    adyacencias = aristas `open` (in-plane), conectores/escaleras = `stair`, portales = `portal`.
    Mecánicas de CELDA → su lugar correcto: una celda-puerta d se convierte en nodo normal cuyas
    aristas llevan TODAS `door_id=d` (entrar exige la llave — la misma semántica que el mapeo del
    transpilador); celda-gate igual con `gate_flag`; llave/switch/hazard quedan como mecánica de
    nodo; P/G → start/goal. El archivo MAP-Elites entero sigue siendo válido vía esta función.

    `prune_unreachable` (default True): los mazes generados traen BOLSONES de celdas abiertas
    tapiadas que el BFS del juego nunca visita (ruido del generador, no contenido — medido:
    20/78 niveles del archivo). El importador es fiel AL JUEGO, no al ruido: poda las
    componentes que no contienen el start. Sin start (o con False), importa todo tal cual."""
    def _id(cell: tuple[int, int, int]) -> str:
        x, y, z = cell
        return f"{x},{y},{z}"

    graph = SpaceGraph()
    open_cells = sorted(maze.open_cells(), key=lambda c: (c[2], c[1], c[0]))
    open_cell_set = set(open_cells)
    for cell in open_cells:
        x, y, z = cell
        graph.nodes[_id(cell)] = GraphNode(
            id=_id(cell),
            key=maze.keys.get(cell),
            switch=maze.switches.get(cell),
            hazard=maze.hazards.get(cell),
            start=maze.char_at(x, y, z) == "P",
            goal=maze.char_at(x, y, z) == "G",
            floor=z,
        )

    portal_pairs = {frozenset((_id(a), _id(b))) for a, b in maze.portals}
    edge_by_pair: dict[tuple[str, str], GraphEdge] = {}

    def _edge_kind(a: tuple[int, int, int], b: tuple[int, int, int]) -> str:
        ids = frozenset((_id(a), _id(b)))
        if ids in portal_pairs:
            return "portal"
        if a[2] != b[2]:
            return "stair"
        return "open"

    def _edge_restrictions(a: tuple[int, int, int], b: tuple[int, int, int]) -> tuple[str | None, str | None]:
        door_ids = sorted({maze.doors[c] for c in (a, b) if c in maze.doors})
        gate_flags = sorted({maze.gates[c] for c in (a, b) if c in maze.gates})
        # Limitacion conocida del importador: una arista no dirigida solo porta un door_id
        # y un gate_flag. Si dos celdas-puerta/gate adyacentes tienen ids distintos, se elige
        # el menor id canonico y el caso queda para el parser grafo-nativo.
        door_id = door_ids[0] if door_ids else None
        gate_flag = gate_flags[0] if gate_flags else None
        return door_id, gate_flag

    def _put_edge(a: tuple[int, int, int], b: tuple[int, int, int]) -> None:
        if _id(a) not in graph.nodes:
            return
        if _id(b) not in graph.nodes:
            return
        ida, idb = _id(a), _id(b)
        key = tuple(sorted((ida, idb)))
        door_id, gate_flag = _edge_restrictions(a, b)
        kind = _edge_kind(a, b)
        prev = edge_by_pair.get(key)
        if prev is None:
            edge_by_pair[key] = GraphEdge(key[0], key[1], kind=kind, door_id=door_id, gate_flag=gate_flag)
            return
        # Si una portal/stair coincide con una arista plana, conservamos la intencion mas expresiva.
        kinds = {"open": 0, "stair": 1, "portal": 2, "door": 0, "shortcut": 0}
        edge_by_pair[key] = GraphEdge(
            prev.a,
            prev.b,
            kind=kind if kinds[kind] > kinds[prev.kind] else prev.kind,
            door_id=prev.door_id or door_id,
            gate_flag=prev.gate_flag or gate_flag,
        )

    for cell in open_cells:
        for nxt in maze.neighbors(cell):
            if nxt in open_cell_set:
                _put_edge(cell, nxt)

    graph.edges = [edge_by_pair[key] for key in sorted(edge_by_pair)]

    if prune_unreachable and (start_id := graph.start()) is not None:
        # componente del start por CONECTIVIDAD (ignora mecánicas — sólo existencia de arista)
        seen = {start_id}
        frontier = [start_id]
        while frontier:
            nid = frontier.pop()
            for nb, _e in graph.neighbors(nid):
                if nb not in seen:
                    seen.add(nb)
                    frontier.append(nb)
        graph.nodes = {nid: n for nid, n in graph.nodes.items() if nid in seen}
        graph.edges = [e for e in graph.edges if e.a in seen and e.b in seen]
    return graph


def normalize_hubs(graph: SpaceGraph, max_plane_degree: int = 4) -> SpaceGraph:
    """Divide los nodos-DISTRIBUIDOR (SIN mecánica ni start/goal) cuyo grado in-plane excede el
    límite V1 en una CADENA de segmentos del mismo tipo (`pasillo → pasillo, pasillo__b, ...`).
    Transformación que PRESERVA LA MISIÓN: contraer la cadena devuelve el nodo original — y el
    realizador la funde en UN solo cuarto-corredor (merge), que es exactamente la intención del
    autor (un pasillo real distribuye a muchos cuartos). Los hubs CON mecánica no se tocan
    (que `realizable_static` los rechace honesto: partir un cuarto-llave sí cambiaría el juego).
    El instinto vino del LLM: qwen3-coder diseña pasillos de grado 10+ porque las casas reales
    son así (2026-07-08)."""
    from dataclasses import replace as _replace

    g = SpaceGraph(nodes=dict(graph.nodes), edges=list(graph.edges),
                   space=graph.space, seed=graph.seed, resources=dict(graph.resources))
    while True:
        plane_deg: dict[str, list[int]] = {nid: [] for nid in g.nodes}
        for idx, e in enumerate(g.edges):
            if e.kind not in ("stair", "portal", "cable"):
                plane_deg[e.a].append(idx)
                plane_deg[e.b].append(idx)
        hub = next((nid for nid, idxs in sorted(plane_deg.items())
                    if len(idxs) > max_plane_degree
                    and g.nodes[nid].key is None and g.nodes[nid].switch is None
                    and g.nodes[nid].hazard is None
                    and not g.nodes[nid].start and not g.nodes[nid].goal), None)
        if hub is None:
            # hubs CON mecánica: extraer un LOBBY (antesala libre que absorbe el exceso de
            # conexiones; el cuarto-mecánica queda colgado con grado bajo). OJO: esto puede
            # debilitar pickups forzados (el tráfico de paso ya no cruza el cuarto) — por eso
            # normalizar PROPONE y la cadena de oráculos aguas abajo (solve + interés) dispone.
            mech_hub = next((nid for nid, idxs in sorted(plane_deg.items())
                             if len(idxs) > max_plane_degree), None)
            if mech_hub is None:
                return g
            from dataclasses import replace as _r
            lobby = f"{mech_hub}__lobby"
            proto = g.nodes[mech_hub]
            g.nodes[lobby] = GraphNode(id=lobby, type=proto.type, floor=proto.floor)
            idxs = plane_deg[mech_hub]
            for idx in idxs[max_plane_degree - 1:]:      # deja (max-1) aristas + la del lobby
                e = g.edges[idx]
                g.edges[idx] = _r(e, a=lobby) if e.a == mech_hub else _r(e, b=lobby)
            g.edges.append(GraphEdge(mech_hub, lobby, kind="open"))
            continue
        idxs = plane_deg[hub]
        # cadena de segmentos: cada uno toma hasta 2 aristas externas (+2 de la cadena = 4)
        import math
        n_seg = max(2, math.ceil(len(idxs) / 2))
        seg_ids = [hub] + [f"{hub}__{chr(98 + i)}" for i in range(n_seg - 1)]
        proto = g.nodes[hub]
        for sid in seg_ids[1:]:
            g.nodes[sid] = _replace(proto, id=sid)
        for k, idx in enumerate(idxs):               # round-robin: 2 externas por segmento
            e = g.edges[idx]
            sid = seg_ids[min(k // 2, n_seg - 1)]
            if e.a == hub:
                g.edges[idx] = _replace(e, a=sid)
            else:
                g.edges[idx] = _replace(e, b=sid)
        for a, b in zip(seg_ids, seg_ids[1:]):       # la cadena que los une
            g.edges.append(GraphEdge(a, b, kind="open"))
