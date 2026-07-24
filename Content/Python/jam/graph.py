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


#: pin de entrada «gordo» (orden de ejecución + el asset que viaja por el cable). Cualquier OTRO pin
#: de entrada es un PARÁMETRO del verbo (x, anchor, count…) o el pin especial `asset`.
PIN_IN = "in"
PIN_OUT = "out"
PIN_ASSET = "asset"

#: nodos de VALOR (de `jam.flow`): no ejecutan un verbo, aportan un valor con nombre que se puede
#: cablear a cualquier pin de parámetro. number/math = número · text = texto (anclas, nombres…).
VALOR_KINDS = ("number", "math", "text")


class JamGraph:
    def __init__(self):
        self.nodes: dict[str, dict] = {}          # id → {verb, params, asset, x, y}
        # (origen, origen_pin, destino, destino_pin)
        self.edges: list[tuple[str, str, str, str]] = []

    # ---- construcción ----

    def add(self, verb: str, params: dict | None = None, asset: str | None = None,
            nid: str | None = None, x: float = 0.0, y: float = 0.0) -> str:
        nid = nid or f"n{len(self.nodes) + 1}"
        self.nodes[nid] = {"verb": verb, "params": dict(params or {}), "asset": asset,
                           "x": float(x), "y": float(y)}
        return nid

    def connect(self, origen: str, destino: str, destino_pin: str = PIN_IN,
                origen_pin: str = PIN_OUT) -> None:
        """Conecta `origen.origen_pin` → `destino.destino_pin`. Por defecto out→in (el cable «gordo»,
        por el que viaja el asset). Pasá `destino_pin="x"` (o `"asset"`, `"anchor"`…) para cablear un
        PARÁMETRO: el valor del nodo de origen maneja ese parámetro, como en Grasshopper."""
        if origen in self.nodes and destino in self.nodes:
            self.edges.append((origen, origen_pin, destino, destino_pin))

    # ---- orden topológico (Kahn); detecta ciclos ----

    def topo_order(self) -> list[str]:
        indeg = {n: 0 for n in self.nodes}
        adj: dict[str, list[str]] = {n: [] for n in self.nodes}
        for a, _ap, b, _bp in self.edges:
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

    # ---- valores: los nodos number/math/text aportan una tabla de variables ----

    def valores(self) -> dict:
        """{ nombre: valor } de los nodos de VALOR. Resuelve por pasadas (una expresión puede
        referenciar otra variable). Reusa el evaluador puro de `jam.flow`."""
        from .flow import _eval_expr, _num
        val_nodos = [(nid, n) for nid, n in self.nodes.items() if n["verb"] in VALOR_KINDS]
        tabla: dict = {}
        for _ in range(len(val_nodos) + 1):
            cambio = False
            for nid, n in val_nodos:
                p = n.get("params", {})
                nombre = str(p.get("name") or nid)
                if n["verb"] == "number":
                    v = _num(p.get("value", 0.0))
                elif n["verb"] == "text":
                    v = str(p.get("value", ""))
                else:
                    v = _eval_expr(p.get("expr", "0"),
                                   {k: x for k, x in tabla.items() if isinstance(x, (int, float))})
                if v is not None and tabla.get(nombre) != v:
                    tabla[nombre] = v
                    cambio = True
            if not cambio:
                break
        return tabla

    @classmethod
    def from_json(cls, s: str) -> "JamGraph":
        d = json.loads(s) if s else {}
        g = cls()
        g.nodes = {k: {"verb": v.get("verb", ""), "params": dict(v.get("params", {})),
                       "asset": v.get("asset"), "x": float(v.get("x", 0.0)), "y": float(v.get("y", 0.0))}
                   for k, v in d.get("nodes", {}).items()}
        # aristas: [from, from_pin, to, to_pin] (por pin) o [from, to] (compat: out→in)
        for e in d.get("edges", []):
            if len(e) == 4:
                g.edges.append((e[0], e[1], e[2], e[3]))
            elif len(e) == 2:
                g.edges.append((e[0], PIN_OUT, e[1], PIN_IN))
        return g


# ---- ejecución (reusa las tools y el oráculo; asset por nodo) ----

def _resolver_asset(nombre: str | None) -> str | None:
    from . import library, session
    if nombre:
        if "/" in nombre or "." in nombre:   # ya es un ObjectPath
            return nombre
        hits = library.buscar(nombre, limit=1)
        return hits[0]["ruta"] if hits else None
    if session.asset():                      # lo elegido en Content
        return session.asset()
    hits = library.buscar("", limit=1)       # default: 1º de la biblioteca
    return hits[0]["ruta"] if hits else None


def _entradas(g: "JamGraph", nid: str) -> list[str]:
    """Orígenes cableados al pin «gordo» (in): de ahí hereda el asset si no tiene uno propio."""
    return [a for a, _ap, b, bp in g.edges if b == nid and bp == PIN_IN]


def _param_wires(g: "JamGraph", nid: str) -> dict:
    """{ pin_de_parámetro: origen } de los cables que entran a un PARÁMETRO (o al pin `asset`).
    Si un pin recibe varios cables, gana el último (como reconectar en Grasshopper)."""
    out: dict = {}
    for a, _ap, b, bp in g.edges:
        if b == nid and bp != PIN_IN:
            out[bp] = a
    return out


def _estado(texto: str) -> str:
    """Convención de Grasshopper llevada al oráculo: cada nodo se pinta por su VEREDICTO.
    error (rojo) = reventó · warn (naranja) = el oráculo dice REVISAR ✗ · ok (verde) = ✓."""
    if texto.startswith("[error]"):
        return "error"
    if "✗" in texto:
        return "warn"
    return "ok" if "✓" in texto else "info"


def ejecutar(g: JamGraph) -> str:
    """Reporte de texto de correr el grafo (ver `ejecutar_detalle`)."""
    return ejecutar_detalle(g)[0]


def ejecutar_detalle(g: JamGraph) -> tuple[str, dict]:
    """Corre el grafo en orden topológico: cada nodo dispara su tool y su oráculo. Devuelve
    (reporte, {nid: {'estado','texto'}}) — el estado es lo que pinta cada nodo en el canvas.
    Los actores quedan en el nivel (quien llama decide preview/confirm)."""
    from . import dsl, tools
    por_nodo: dict[str, dict] = {}
    try:
        orden = g.topo_order()
    except ValueError as e:
        return f"[grafo] {e}", por_nodo
    if not orden:
        return "[grafo] vacío — agregá nodos.", por_nodo
    lineas = []
    # asset que sale de cada nodo por su pin: el nodo «asset» lo produce, los demás lo dejan pasar.
    # Como corremos en orden topológico, aguas abajo ya está resuelto cuando se lo pide.
    porta: dict[str, str | None] = {}
    # valor que sale de cada nodo de VALOR (number/math/text), para cablear a pines de parámetro.
    tabla = g.valores()
    valor_de = {nid: tabla.get(str(n.get("params", {}).get("name") or nid))
                for nid, n in g.nodes.items() if n["verb"] in VALOR_KINDS}

    for nid in orden:
        n = g.nodes[nid]
        verb = n["verb"]

        # nodos de VALOR: no ejecutan verbo; aportan su valor (y lo muestran en el nodo).
        if verb in VALOR_KINDS:
            nombre = str(n.get("params", {}).get("name") or nid)
            v = valor_de.get(nid)
            txt = f"{nombre} = {v}" if v is not None else f"{nombre} = (sin resolver)"
            lineas.append(f"[{nid}·{verb}] {txt}")
            por_nodo[nid] = {"estado": "ok" if v is not None else "warn", "texto": txt}
            continue

        info = tools.REGISTRO.get(verb)
        if not info:
            lineas.append(f"[{nid}·{verb}] verbo desconocido")
            por_nodo[nid] = {"estado": "error", "texto": "verbo desconocido"}
            continue

        # params del nodo + lo que llegue por CABLE a cada pin de parámetro (el cable MANDA).
        params = {k: v for k, v in n.get("params", {}).items() if k != PIN_ASSET}
        wires = _param_wires(g, nid)
        for pin, origen in wires.items():
            if pin == PIN_ASSET:
                continue
            if origen in valor_de and valor_de[origen] is not None:
                params[pin] = valor_de[origen]
            elif porta.get(origen):        # cablear un nodo de asset a un param: pasa su ruta
                params[pin] = porta[origen]

        # ASSET: pin cableado > el escrito en el pin/nodo > el del cable «gordo» > sesión/biblioteca.
        pedido = None
        if PIN_ASSET in wires:
            o = wires[PIN_ASSET]
            pedido = porta.get(o) or (valor_de.get(o) if isinstance(valor_de.get(o), str) else None)
        if not pedido:
            # ojo: `params` (ya pisado por los cables), no `n["params"]` — si un `text` maneja el
            # `name` del nodo `asset`, el nombre pedido tiene que ser EL DEL CABLE.
            pedido = (n.get("asset") or n.get("params", {}).get(PIN_ASSET)
                      or (params.get("name") if verb == "asset" else None))
        if not pedido:   # sin asset propio: hereda el del cable (nodo «asset» aguas arriba)
            pedido = next((porta[e] for e in _entradas(g, nid) if porta.get(e)), None)
        asset = _resolver_asset(pedido)
        porta[nid] = asset
        if not asset:
            lineas.append(f"[{nid}·{verb}] biblioteca vacía")
            por_nodo[nid] = {"estado": "error", "texto": "biblioteca vacía"}
            continue

        kw, _desc = dsl.coaccionar(verb, {k: str(v) for k, v in params.items()})
        try:
            txt = info["fn"](asset, **kw)
        except Exception as e:  # noqa: BLE001
            txt = f"[error] {type(e).__name__}: {e}"
        lineas.append(f"[{nid}·{verb}] {txt}")
        por_nodo[nid] = {"estado": _estado(txt), "texto": txt}
    return "\n".join(lineas), por_nodo
