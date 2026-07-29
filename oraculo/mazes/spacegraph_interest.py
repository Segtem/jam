"""El GATE DE INTERÉS sobre grafos de misión — necesidad contrafáctica por ITEM.

Ganable ≠ divertido ([[entretenido-necesidad-contrafactual]]): una mecánica cuenta sólo si
QUITARLA cambia el óptimo. Este módulo porta `item_necessity` (maze3d) al grafo: por cada
puerta/compuerta/trampa se neutraliza SOLO ese item y se re-resuelve; si el veredicto y el largo
no cambian, es DECORATIVO (relleno). Una llave es decorativa si todas las puertas que abre lo
son (o no abre ninguna); un switch, si todos los gates Y hazards de su flag lo son; un shortcut
declarado (D3) es decorativo si quitar la ARISTA no cambia el óptimo (el loop-back que no
acorta nada es ruido). Un grafo LÓGICO tiene decorative == 0: cada item colocado IMPORTA.

`interest_report` es el gate de la galería LLM: ganable + piso de largo + ≥1 item + cero
decorativos. La medida de calidad espeja la del archivo de Capa 0
(`interés·1000 + min(largo, 999)`)."""

from __future__ import annotations

from dataclasses import replace

from oraculo.mazes.spacegraph import GraphEdge, SpaceGraph, solve_graph

MIN_STEPS = 6      # piso de largo: por debajo es un paseo, no un reto (análogo al de Capa 0)


def _solved(graph: SpaceGraph, max_states: int, flags0: frozenset[str] = frozenset()
            ) -> tuple[bool, int | None]:
    r = solve_graph(graph, max_states=max_states, flags0=flags0)
    return bool(r["solvable"]), r["optimal_steps"]


def _with_edges(graph: SpaceGraph, edges: list[GraphEdge]) -> SpaceGraph:
    return SpaceGraph(nodes=graph.nodes, edges=edges, space=graph.space, seed=graph.seed,
                      resources=dict(graph.resources))


def _with_node(graph: SpaceGraph, node_id: str, **changes) -> SpaceGraph:
    nodes = dict(graph.nodes)
    nodes[node_id] = replace(nodes[node_id], **changes)
    return SpaceGraph(nodes=nodes, edges=graph.edges, space=graph.space, seed=graph.seed,
                      resources=dict(graph.resources))


def item_necessity_graph(graph: SpaceGraph, max_states: int = 200_000, *,
                         flags0: frozenset[str] = frozenset()) -> dict:
    """Necesidad contrafáctica por item sobre el grafo. → {n_items, decorative_items,
    decorative: [descripciones legibles], per_item: {descripcion: bool necesario}}."""
    base_ok, base_len = _solved(graph, max_states, flags0)
    doors = [(i, e) for i, e in enumerate(graph.edges) if e.door_id is not None]
    gates = [(i, e) for i, e in enumerate(graph.edges) if e.gate_flag is not None]
    hazards = [n for n in graph.nodes.values() if n.hazard is not None]
    keys = [n for n in graph.nodes.values() if n.key is not None]
    switches = [n for n in graph.nodes.values() if n.switch is not None]
    shortcuts = [(i, e) for i, e in enumerate(graph.edges)
                 if e.kind == "shortcut" and e.door_id is None and e.gate_flag is None]
    n_items = len(doors) + len(gates) + len(hazards) + len(keys) + len(switches) + len(shortcuts)
    if not base_ok or n_items == 0:
        return {"n_items": n_items, "decorative_items": 0, "decorative": [], "per_item": {}}

    def unchanged(g2: SpaceGraph) -> bool:
        ok, ln = _solved(g2, max_states, flags0)
        return ok and ln == base_len

    per_item: dict[str, bool] = {}
    door_dec: dict[int, bool] = {}
    for i, e in doors:
        edges = list(graph.edges)
        edges[i] = replace(e, door_id=None)
        dec = unchanged(_with_edges(graph, edges))
        door_dec[i] = dec
        per_item[f"door {e.door_id} ({e.a}-{e.b})"] = not dec
    gate_dec: dict[int, bool] = {}
    for i, e in gates:
        edges = list(graph.edges)
        edges[i] = replace(e, gate_flag=None)
        dec = unchanged(_with_edges(graph, edges))
        gate_dec[i] = dec
        per_item[f"gate {e.gate_flag} ({e.a}-{e.b})"] = not dec
    hazard_dec: dict[str, bool] = {}
    for n in hazards:
        dec = unchanged(_with_node(graph, n.id, hazard=None))
        hazard_dec[n.id] = dec
        per_item[f"hazard ({n.id})"] = not dec
    for n in keys:                                   # llave = sus puertas
        opened = [i for i, e in doors if e.door_id == n.key]
        dec = not opened or all(door_dec.get(i, False) for i in opened)
        per_item[f"key {n.key} ({n.id})"] = not dec
    for n in switches:                               # switch = sus gates Y sus hazards
        gated = [i for i, e in gates if e.gate_flag == n.switch]
        armed = [h.id for h in hazards if h.hazard == n.switch]
        dec = ((not gated and not armed)
               or (all(gate_dec.get(i, False) for i in gated)
                   and all(hazard_dec.get(h, False) for h in armed)))
        per_item[f"switch {n.switch} ({n.id})"] = not dec
    for i, e in shortcuts:                           # shortcut sin gating: la ARISTA debe acortar
        edges = [x for j, x in enumerate(graph.edges) if j != i]
        dec = unchanged(_with_edges(graph, edges))
        per_item[f"shortcut ({e.a}-{e.b})"] = not dec

    decorative = sorted(d for d, necessary in per_item.items() if not necessary)
    return {"n_items": n_items, "decorative_items": len(decorative),
            "decorative": decorative, "per_item": per_item}


def interest_report(graph: SpaceGraph, *, min_steps: int = MIN_STEPS,
                    max_states: int = 200_000,
                    flags0: frozenset[str] = frozenset()) -> dict:
    """El GATE de la galería: {solvable, optimal_steps, n_items, decorative_items, decorative,
    interesting, quality, reasons}. `interesting` = ganable ∧ largo ≥ piso ∧ ≥1 item ∧ cero
    decorativos. `quality` espeja el archivo de Capa 0."""
    ok, steps = _solved(graph, max_states, flags0)
    nec = item_necessity_graph(graph, max_states=max_states, flags0=flags0)
    reasons: list[str] = []
    if not ok:
        reasons.append("no ganable")
    elif steps is not None and steps < min_steps:
        reasons.append(f"muy corto: {steps} < {min_steps} aristas")
    if nec["n_items"] == 0:
        reasons.append("sin mecánicas: es un paseo")
    if nec["decorative_items"]:
        reasons.append(f"{nec['decorative_items']} item(s) decorativos: "
                       + ", ".join(nec["decorative"][:3]))
    necessary = nec["n_items"] - nec["decorative_items"]
    return {"solvable": ok, "optimal_steps": steps,
            "n_items": nec["n_items"], "decorative_items": nec["decorative_items"],
            "decorative": nec["decorative"],
            "interesting": not reasons,
            "quality": (necessary * 1000.0 + min(steps or 0, 999)) if ok else 0.0,
            "reasons": reasons}
