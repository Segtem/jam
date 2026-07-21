"""G3b — el puente grafo→realizador: Maze3D SINTÉTICO desde (SpaceGraph, Embedding), escala ×2.

El realizador métrico (`floorplan.py`) y todo el dress (tipado, amoblado, iso-check) consumen
un Maze3D. Este módulo construye uno SINTÉTICO desde el grafo embebido, con una propiedad
DEMOSTRABLE que hace todo correcto por construcción:

**Escala ×2**: cada entidad del embedding (nodo o celda de ruta) va a coordenadas PARES
(2x, 2y); entre celdas consecutivas de cada cadena de arista se inserta la celda PUNTO MEDIO
(exactamente una coordenada impar). Consecuencias probadas:
  1. **Cero adyacencias espurias**: dos entidades distintas distan ≥2; un punto medio sólo es
     adyacente a las dos celdas de SU cadena (celdas par-par distan ≥2; medio-medio es
     imposible: requeriría coordenadas impar-impar; medio-entidad ajena requeriría que la otra
     cadena pisara una celda exclusiva de esta). El grafo de la grilla sintética ES el grafo
     fuente subdividido — ni una arista de más.
  2. **Toda arista gana ≥1 celda intermedia** → hay dónde pintar su mecánica de ARISTA como
     celda (door/gate = un VESTÍBULO de 1 celda entre los dos cuartos, la semántica exacta que
     `from_maze` define para la dirección inversa).
Las celdas intermedias SIN mecánica van al set de MERGE (pasillos que el realizador contrae) →
el grafo contraído del edificio es isomorfo al fuente subdividido, y el fuente subdividido es
homeomorfo al original. La winnability se re-verifica además por BFS (`solve_3d` del sintético
≡ `solve_graph` del original — el test de equivalencia)."""

from __future__ import annotations

from dataclasses import replace

from src.mazes.embedder import Embedding
from src.mazes.maze3d import Maze3D
from src.mazes.spacegraph import SpaceGraph

Cell = tuple[int, int, int]


def _mid(a: Cell, b: Cell) -> Cell:
    return ((a[0] + b[0]) // 2, (a[1] + b[1]) // 2, a[2])


def graph_to_maze(graph: SpaceGraph, emb: Embedding
                  ) -> tuple[Maze3D, set[Cell], dict[Cell, str]]:
    """→ (maze sintético, merge_cells (intermedios sin mecánica), cell→node_id de cada nodo).
    Requiere un Embedding VÁLIDO (check_embedding vacío) del MISMO grafo."""
    scale = lambda c: (c[0] * 2, c[1] * 2, c[2])
    pos = {nid: scale(c) for nid, c in emb.positions.items()}

    open_cells: set[Cell] = set(pos.values())
    merge: set[Cell] = set()
    doors: dict[Cell, str] = {}
    gates: dict[Cell, str] = {}
    connectors: set[Cell] = set()
    portals: list[tuple[Cell, Cell]] = []

    for i, e in enumerate(graph.edges):
        if e.kind == "cable":
            continue
        a, b = pos[e.a], pos[e.b]
        if e.kind == "portal":
            portals.append((a, b))
            continue
        if e.kind == "stair":
            lo = a if a[2] < b[2] else b
            connectors.add(lo)
            continue
        # cadena escalada: nodos + celdas de ruta ×2, con puntos medios intercalados
        chain = [a] + [scale(c) for c in emb.routes.get(i, [])] + [b]
        full: list[Cell] = [chain[0]]
        for prev, nxt in zip(chain, chain[1:]):
            full.append(_mid(prev, nxt))
            full.append(nxt)
        inner = full[1:-1]
        open_cells.update(inner)
        merge.update(inner)
        if e.door_id is not None or e.gate_flag is not None:
            # la mecánica de la arista vive en UNA celda intermedia (vestíbulo): la del medio
            vest = inner[len(inner) // 2]
            if e.door_id is not None:
                doors[vest] = e.door_id
            if e.gate_flag is not None:
                gates[vest] = e.gate_flag
            merge.discard(vest)                    # el vestíbulo NO se contrae (tiene mecánica)

    # grillas por piso (bounding box compacto + borde de muro)
    xs = [c[0] for c in open_cells] or [0]
    ys = [c[1] for c in open_cells] or [0]
    zs = [c[2] for c in open_cells] or [0]
    ox, oy = min(xs) - 1, min(ys) - 1
    w, h, nf = max(xs) - ox + 2, max(ys) - oy + 2, max(zs) + 1
    shift = lambda c: (c[0] - ox, c[1] - oy, c[2])

    start = graph.start()
    goal = graph.goal()
    grids: list[list[str]] = []
    open_shifted = {shift(c) for c in open_cells}
    p_cell = shift(pos[start]) if start else None
    g_cell = shift(pos[goal]) if goal else None
    for z in range(nf):
        rows = []
        for y in range(h):
            row = ""
            for x in range(w):
                cell = (x, y, z)
                if cell == p_cell:
                    row += "P"
                elif cell == g_cell:
                    row += "G"
                else:
                    row += "." if cell in open_shifted else "#"
            rows.append(row)
        grids.append(rows)

    maze = replace(
        Maze3D.from_layers(grids),
        connectors={shift(c) for c in connectors},
        portals=[(shift(a), shift(b)) for a, b in portals],
        doors={shift(c): v for c, v in doors.items()},
        gates={shift(c): v for c, v in gates.items()},
        keys={shift(pos[n.id]): n.key for n in graph.nodes.values() if n.key is not None},
        switches={shift(pos[n.id]): n.switch for n in graph.nodes.values() if n.switch is not None},
        hazards={shift(pos[n.id]): n.hazard for n in graph.nodes.values() if n.hazard is not None},
    )
    owner = {shift(pos[nid]): nid for nid in graph.nodes}
    return maze, {shift(c) for c in merge}, owner
