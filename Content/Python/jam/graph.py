"""JamGraph — el sustrato tipo Grasshopper: un grafo de nodos donde CADA NODO es un comando de Jam
(un verbo de `jam.tools.REGISTRO`) y las aristas dan el orden de ejecución (dataflow).

Es la MISMA sustancia que el CLI/Dash Bar (verbos + params + oráculo), en otra vista: en vez de
escribir `scatter count=8` tenés un nodo «scatter» con un pin `count=8`. Correr el grafo = orden
topológico → ejecutar cada nodo con su tool → el oráculo verifica cada uno. El editor visual (Slate)
es una cara de esto; este archivo es la lógica, testeable headless.

Formato JSON (lo que intercambia con el editor en C++):
    {"nodes": {"n1": {"verb":"create_spline","params":{},"asset":null,"x":40,"y":60}, ...},
     "edges": [["n1","n2"]]}
"""

from __future__ import annotations

import json


class JamGraph:
    def __init__(self):
        self.nodes: dict[str, dict] = {}          # id → {verb, params, asset, x, y}
        self.edges: list[tuple[str, str]] = []    # (origen, destino): destino corre después

    # ---- construcción ----

    def add(self, verb: str, params: dict | None = None, asset: str | None = None,
            nid: str | None = None, x: float = 0.0, y: float = 0.0) -> str:
        nid = nid or f"n{len(self.nodes) + 1}"
        self.nodes[nid] = {"verb": verb, "params": dict(params or {}), "asset": asset,
                           "x": float(x), "y": float(y)}
        return nid

    def connect(self, origen: str, destino: str) -> None:
        if origen in self.nodes and destino in self.nodes:
            self.edges.append((origen, destino))

    # ---- orden topológico (Kahn); detecta ciclos ----

    def topo_order(self) -> list[str]:
        indeg = {n: 0 for n in self.nodes}
        adj: dict[str, list[str]] = {n: [] for n in self.nodes}
        for a, b in self.edges:
            if a in self.nodes and b in self.nodes:
                adj[a].append(b)
                indeg[b] += 1
        # cola estable: respeta el orden de inserción entre nodos sin dependencia
        cola = [n for n in self.nodes if indeg[n] == 0]
        orden: list[str] = []
        while cola:
            n = cola.pop(0)
            orden.append(n)
            for m in adj[n]:
                indeg[m] -= 1
                if indeg[m] == 0:
                    cola.append(m)
        if len(orden) != len(self.nodes):
            raise ValueError("el grafo tiene un ciclo (no se puede ordenar)")
        return orden

    # ---- serialización ----

    def to_json(self) -> str:
        return json.dumps({"nodes": self.nodes, "edges": [list(e) for e in self.edges]},
                          ensure_ascii=True)

    @classmethod
    def from_json(cls, s: str) -> "JamGraph":
        d = json.loads(s) if s else {}
        g = cls()
        g.nodes = {k: {"verb": v.get("verb", ""), "params": dict(v.get("params", {})),
                       "asset": v.get("asset"), "x": float(v.get("x", 0.0)), "y": float(v.get("y", 0.0))}
                   for k, v in d.get("nodes", {}).items()}
        g.edges = [(e[0], e[1]) for e in d.get("edges", []) if len(e) == 2]
        return g


# ---- ejecución (reusa las tools y el oráculo; asset por nodo) ----

def _resolver_asset(nombre: str | None) -> str | None:
    from . import library
    if nombre:
        if "/" in nombre or "." in nombre:   # ya es un ObjectPath
            return nombre
        hits = library.buscar(nombre, limit=1)
        return hits[0]["ruta"] if hits else None
    hits = library.buscar("", limit=1)       # default: 1º de la biblioteca
    return hits[0]["ruta"] if hits else None


def ejecutar(g: JamGraph) -> str:
    """Corre el grafo en orden topológico: cada nodo dispara su tool y su oráculo. Devuelve el
    reporte por nodo. Los actores quedan en el nivel (quien llama decide preview/confirm)."""
    from . import dsl, tools
    try:
        orden = g.topo_order()
    except ValueError as e:
        return f"[grafo] {e}"
    if not orden:
        return "[grafo] vacío — agregá nodos."
    lineas = []
    for nid in orden:
        n = g.nodes[nid]
        verb = n["verb"]
        info = tools.REGISTRO.get(verb)
        if not info:
            lineas.append(f"[{nid}·{verb}] verbo desconocido")
            continue
        asset = _resolver_asset(n.get("asset"))
        if not asset:
            lineas.append(f"[{nid}·{verb}] biblioteca vacía")
            continue
        kw, _desc = dsl.coaccionar(verb, {k: str(v) for k, v in n.get("params", {}).items()})
        try:
            txt = info["fn"](asset, **kw)
        except Exception as e:  # noqa: BLE001
            txt = f"[error] {type(e).__name__}: {e}"
        lineas.append(f"[{nid}·{verb}] {txt}")
    return "\n".join(lineas)
