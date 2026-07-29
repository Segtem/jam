"""Canales NO-nav sobre SpaceGraph (Corte 2 / G1.5).

Porta al grafo de misión los dos oráculos que ya existían sobre grilla:
- eléctrico: componentes conexos por aristas ``kind=="cable"`` desde fuentes;
- recurso: BFS de navegación aumentado por un presupuesto escalar.

Las aristas ``cable`` no son pasos navegables. El canal eléctrico las usa como su propio grafo;
la navegación y supervivencia recorren sólo aristas físicas.
"""

from __future__ import annotations

from collections import deque
from typing import Any, Iterable

from oraculo.mazes.spacegraph import GraphNode, SpaceGraph, solve_graph


POWER_FLAG_PREFIX = "powered:"


def powered_flag(load_id: str) -> str:
    """Flag de mundo que una carga energizada deja ON para gates de navegación."""
    return f"{POWER_FLAG_PREFIX}{load_id}"


def powered_loads_graph(graph: SpaceGraph) -> set[str]:
    """Ids de nodos ``power=="load"`` energizados por alguna fuente vía aristas cable."""
    energized = _energized_nodes(graph)
    return {node.id for node in graph.nodes.values()
            if node.power == "load" and node.id in energized}


def powered_flags_graph(graph: SpaceGraph) -> frozenset[str]:
    """Flags ``powered:<load_id>`` derivados del estado eléctrico estático del grafo."""
    return frozenset(powered_flag(load_id) for load_id in powered_loads_graph(graph))


def all_powered_graph(graph: SpaceGraph) -> list[str]:
    """Lista de fallas eléctricas; vacía = toda carga está alimentada.

    Igual que ``electric.all_powered`` en espíritu: una carga sólo está ON si pertenece a un
    componente de cableado que contiene al menos una fuente. Si no hay cargas, el canal no exige
    nada (retro-compatible).
    """
    loads = sorted(node.id for node in graph.nodes.values() if node.power == "load")
    if not loads:
        return []

    sources = sorted(node.id for node in graph.nodes.values() if node.power == "source")
    if not sources:
        return [f"carga {load_id} sin energia: no hay fuente" for load_id in loads]

    energized = _energized_nodes(graph)
    return [f"carga {load_id} sin energia" for load_id in loads if load_id not in energized]


def dag_check_graph(graph: SpaceGraph) -> list[str]:
    """Sanidad del DAG de tareas grafo-nativo.

    Vacío = no hay tareas o el DAG es sano. Las dependencias desconocidas y ciclos se reportan
    antes de gastar BFS, igual que el canal legacy de grilla.
    """
    tasks = [(node.id, node.task[0], tuple(node.task[1]))
             for node in graph.nodes.values()
             if node.task is not None]
    if not tasks:
        return []

    ids = {task_id for _node_id, task_id, _deps in tasks}
    failures: list[str] = []
    for _node_id, task_id, deps in sorted(tasks, key=lambda item: item[1]):
        for dep in sorted(dep for dep in deps if dep not in ids):
            failures.append(f"dep fantasma de {task_id}: {dep}")

    indeg = {task_id: len([dep for dep in deps if dep in ids])
             for _node_id, task_id, deps in tasks}
    out: dict[str, list[str]] = {task_id: [] for task_id in ids}
    for _node_id, task_id, deps in tasks:
        for dep in deps:
            if dep in ids:
                out[dep].append(task_id)

    queue: deque[str] = deque(sorted(task_id for task_id, n in indeg.items() if n == 0))
    seen = 0
    while queue:
        cur = queue.popleft()
        seen += 1
        for nxt in sorted(out[cur]):
            indeg[nxt] -= 1
            if indeg[nxt] == 0:
                queue.append(nxt)

    if seen < len(ids):
        cyclic = ",".join(sorted(task_id for task_id, n in indeg.items() if n > 0))
        failures.append(f"ciclo en el DAG de tareas: {cyclic}")
    return failures


def solve_tasks_graph(graph: SpaceGraph, max_states: int = 200_000, *,
                      flags0: Iterable[str] = frozenset()) -> dict[str, Any]:
    """BFS start->goal completando tareas con dependencias.

    Estado = navegación grafo-nativa + tareas hechas + tareas pisadas antes de tiempo. Si no hay
    tareas, delega exactamente a ``solve_graph`` para preservar retro-compatibilidad. Al entrar a un
    nodo con tarea, se completa si sus dependencias ya están hechas; si se pisa antes de tiempo, esa
    visita no cuenta para el orden válido de esa ruta.
    """
    tasks_by_node = {
        node.id: (node.task[0], tuple(node.task[1]))
        for node in graph.nodes.values()
        if node.task is not None
    }
    if not tasks_by_node:
        return solve_graph(graph, max_states=max_states, flags0=frozenset(flags0))

    sanity = dag_check_graph(graph)
    if sanity:
        return {"solvable": False, "optimal_steps": None, "path": [], "states_explored": 0,
                "completed_order": [], "dag": sanity, "truncated": False,
                "reason": "DAG de tareas invalido"}

    start = graph.start()
    goal = graph.goal()
    if start is None:
        return {"solvable": False, "optimal_steps": None, "path": [], "states_explored": 0,
                "completed_order": [], "dag": sanity, "truncated": False,
                "reason": "missing start"}
    if goal is None:
        return {"solvable": False, "optimal_steps": None, "path": [], "states_explored": 0,
                "completed_order": [], "dag": sanity, "truncated": False,
                "reason": "missing goal"}
    if start not in graph.nodes or goal not in graph.nodes:
        return {"solvable": False, "optimal_steps": None, "path": [], "states_explored": 0,
                "completed_order": [], "dag": sanity, "truncated": False,
                "reason": "start/goal reference missing"}

    initial_flags = frozenset(flags0)
    empty = frozenset()
    all_tasks = frozenset(task_id for task_id, _deps in tasks_by_node.values())

    def deadly(node: GraphNode, flags: frozenset[str]) -> bool:
        return node.hazard is not None and (node.hazard == "" or node.hazard not in flags)

    def collect(node: GraphNode, keys: frozenset[str]) -> frozenset[str]:
        return keys | {node.key} if node.key is not None else keys

    def complete(node_id: str, done: frozenset[str],
                 missed: frozenset[str]) -> tuple[frozenset[str], frozenset[str]]:
        task = tasks_by_node.get(node_id)
        if task is None:
            return done, missed
        task_id, deps = task
        if task_id in done or task_id in missed:
            return done, missed
        if set(deps) <= done:
            return done | {task_id}, missed
        return done, missed | {task_id}

    def path(prev: dict, state) -> list[str]:
        states = [state]
        cur = state
        while prev[cur] is not None:
            cur = prev[cur]
            states.append(cur)
        states.reverse()
        out: list[str] = []
        for node_id, _keys, _flags, _done, _missed in states:
            if not out or out[-1] != node_id:
                out.append(node_id)
        return out

    def completed_order(prev: dict, state) -> list[str]:
        states = [state]
        cur = state
        while prev[cur] is not None:
            cur = prev[cur]
            states.append(cur)
        states.reverse()
        out: list[str] = []
        seen: set[str] = set()
        for _node_id, _keys, _flags, done, _missed in states:
            for task_id in sorted(done - frozenset(seen)):
                out.append(task_id)
                seen.add(task_id)
        return out

    start_node = graph.nodes[start]
    if deadly(start_node, initial_flags):
        return {"solvable": False, "optimal_steps": None, "path": [], "states_explored": 0,
                "completed_order": [], "dag": sanity, "truncated": False,
                "reason": "start blocked by hazard"}

    done0, missed0 = complete(start, empty, empty)
    start_state = (start, collect(start_node, empty), initial_flags, done0, missed0)
    dist = {start_state: 0}
    prev = {start_state: None}
    queue: deque = deque([start_state])
    explored = 0

    while queue:
        cur = queue.popleft()
        node_id, keys, flags, done, missed = cur
        if node_id == goal and done == all_tasks:
            return {"solvable": True, "optimal_steps": dist[cur], "path": path(prev, cur),
                    "states_explored": explored, "completed_order": completed_order(prev, cur),
                    "dag": sanity, "truncated": False}
        if explored >= max_states:
            return {"solvable": False, "optimal_steps": None, "path": [],
                    "states_explored": explored, "completed_order": [], "dag": sanity,
                    "truncated": True, "reason": "max_states"}
        explored += 1

        node = graph.nodes[node_id]
        if node.switch is not None:
            toggled_flags = flags ^ {node.switch}
            nxt = (node_id, keys, frozenset(toggled_flags), done, missed)
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
            if next_node is None or deadly(next_node, flags):
                continue
            next_done, next_missed = complete(next_id, done, missed)
            nxt = (next_id, collect(next_node, keys), flags, next_done, next_missed)
            nd = dist[cur] + 1
            if nd < dist.get(nxt, float("inf")):
                dist[nxt] = nd
                prev[nxt] = cur
                queue.append(nxt)

    return {"solvable": False, "optimal_steps": None, "path": [], "states_explored": explored,
            "completed_order": [], "dag": sanity, "truncated": False}


def solve_survival_graph(graph: SpaceGraph, resource: str, max_states: int = 200_000, *,
                         flags0: Iterable[str] = frozenset()) -> dict[str, Any]:
    """BFS start->goal con un recurso entero acotado.

    ``graph.resources[resource]`` define ``(start, lo, hi)``. Al entrar a un nodo se aplica su
    ``refill`` de ese recurso y luego su ``drain``; si el nivel queda bajo ``lo``, ese camino
    muere. La spec de Corte 2 permite que un refill genere buffer por encima de ``hi``; para
    mantener finito el espacio de estados, el overfill se acota por la suma de refills declarados.
    La navegación respeta puertas, gates, switches y hazards como ``solve_graph``; las aristas
    cable se ignoran.
    """
    start = graph.start()
    goal = graph.goal()
    if resource not in graph.resources:
        return {"solvable": False, "optimal_steps": None, "path": [], "states_explored": 0,
                "levels_at_goal": None, "truncated": False, "reason": f"missing resource {resource}"}
    if start is None:
        return {"solvable": False, "optimal_steps": None, "path": [], "states_explored": 0,
                "levels_at_goal": None, "truncated": False, "reason": "missing start"}
    if goal is None:
        return {"solvable": False, "optimal_steps": None, "path": [], "states_explored": 0,
                "levels_at_goal": None, "truncated": False, "reason": "missing goal"}
    if start not in graph.nodes or goal not in graph.nodes:
        return {"solvable": False, "optimal_steps": None, "path": [], "states_explored": 0,
                "levels_at_goal": None, "truncated": False, "reason": "start/goal reference missing"}

    initial, lo, hi = graph.resources[resource]
    overfill_hi = hi + sum(node.refill[1] for node in graph.nodes.values()
                           if node.refill is not None and node.refill[0] == resource)
    initial_flags = frozenset(flags0)
    empty = frozenset()

    def deadly(node: GraphNode, flags: frozenset[str]) -> bool:
        return node.hazard is not None and (node.hazard == "" or node.hazard not in flags)

    def collect(node: GraphNode, keys: frozenset[str]) -> frozenset[str]:
        return keys | {node.key} if node.key is not None else keys

    def apply_node(level: int, node: GraphNode, *, apply_drain: bool) -> int | None:
        value = level
        if node.refill is not None and node.refill[0] == resource:
            value += node.refill[1]
        if apply_drain and node.drain is not None and node.drain[0] == resource:
            value -= node.drain[1]
        if value < lo:
            return None
        return min(value, overfill_hi)

    def path(prev: dict, state) -> list[str]:
        states = [state]
        cur = state
        while prev[cur] is not None:
            cur = prev[cur]
            states.append(cur)
        states.reverse()
        out: list[str] = []
        for node_id, _keys, _flags, _level in states:
            if not out or out[-1] != node_id:
                out.append(node_id)
        return out

    start_node = graph.nodes[start]
    if deadly(start_node, initial_flags):
        return {"solvable": False, "optimal_steps": None, "path": [], "states_explored": 0,
                "levels_at_goal": None, "truncated": False, "reason": "start blocked by hazard"}

    level0 = apply_node(initial, start_node, apply_drain=False)
    if level0 is None:
        return {"solvable": False, "optimal_steps": None, "path": [], "states_explored": 0,
                "levels_at_goal": None, "truncated": False, "reason": f"resource {resource} below floor"}

    start_state = (start, collect(start_node, empty), initial_flags, level0)
    dist = {start_state: 0}
    prev = {start_state: None}
    queue: deque = deque([start_state])
    explored = 0

    while queue:
        cur = queue.popleft()
        node_id, keys, flags, level = cur
        if node_id == goal:
            return {"solvable": True, "optimal_steps": dist[cur], "path": path(prev, cur),
                    "states_explored": explored, "levels_at_goal": {resource: level},
                    "truncated": False}
        if explored >= max_states:
            return {"solvable": False, "optimal_steps": None, "path": [],
                    "states_explored": explored, "levels_at_goal": None,
                    "truncated": True, "reason": "max_states"}
        explored += 1

        node = graph.nodes[node_id]
        if node.switch is not None:
            toggled_flags = flags ^ {node.switch}
            nxt = (node_id, keys, frozenset(toggled_flags), level)
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
            if next_node is None or deadly(next_node, flags):
                continue
            next_level = apply_node(level, next_node, apply_drain=True)
            if next_level is None:
                continue
            nxt = (next_id, collect(next_node, keys), flags, next_level)
            nd = dist[cur] + 1
            if nd < dist.get(nxt, float("inf")):
                dist[nxt] = nd
                prev[nxt] = cur
                queue.append(nxt)

    return {"solvable": False, "optimal_steps": None, "path": [], "states_explored": explored,
            "levels_at_goal": None, "truncated": False}


def _energized_nodes(graph: SpaceGraph) -> set[str]:
    cable_adj: dict[str, set[str]] = {node_id: set() for node_id in graph.nodes}
    for edge in graph.edges:
        if edge.kind != "cable" or edge.a not in graph.nodes or edge.b not in graph.nodes:
            continue
        cable_adj[edge.a].add(edge.b)
        cable_adj[edge.b].add(edge.a)

    energized: set[str] = set()
    queue: deque[str] = deque(sorted(node.id for node in graph.nodes.values()
                                     if node.power == "source"))
    while queue:
        node_id = queue.popleft()
        if node_id in energized:
            continue
        energized.add(node_id)
        queue.extend(sorted(cable_adj[node_id] - energized))
    return energized
