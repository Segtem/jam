"""Flow — el modelo Houdini/Grasshopper: por los cables viaja un STREAM DE PUNTOS con atributos, y
cada nodo lo lee y lo transforma. CEREBRO PURO (0 `import unreal`).

En Houdini un scatter no es «poné N copias»: es una cadena
    Scatter  →  Attribute Noise  →  Blast by slope  →  Randomize  →  Copy to Points
donde por el cable van PUNTOS (con P, N, slope, seed…) y cada nodo filtra o pinta atributos, hasta
que el último instancia geometría en los que sobrevivieron. Grasshopper es lo mismo con otro nombre.

Este módulo es ese sustrato: un DAG de nodos donde el dato que fluye es `list[Sample]` (ver
`jam.scatter_core`). Cada `kind` es una operación sobre streams. Las FUENTES no tienen entrada; las
MÁSCARAS toman un stream y devuelven otro; MERGE junta varios. El nodo terminal que instancia geometría
NO vive acá (necesita el motor) — lo registra el adaptador (`jam.scatter`) sobre este mismo evaluador.

Es el mismo grafo que `jam.graph` (Grasshopper de verbos), pero donde el cable transporta datos ricos
en vez de sólo el asset. Los dos conviven: un nodo `scatter` monolítico sigue siendo un verbo; esto es
para cuando querés abrirlo en fuente+máscaras, como en Houdini.
"""

from __future__ import annotations

from . import scatter_core as sc

# registro de operaciones de stream: kind -> (fn, n_entradas)
#   fn(entradas: list[list[Sample]], params: dict) -> list[Sample]
# n_entradas: 0 = fuente · 1 = filtro/pinta · -1 = variádico (merge)
OPS: dict = {}


def op(kind: str, entradas: int):
    def deco(fn):
        OPS[kind] = (fn, entradas)
        return fn
    return deco


# ---------- fuentes (sin entrada): región → puntos ----------

@op("source_grid", 0)
def _src_grid(_e, p):
    pts = sc.grid_jitter(p["centro"], p["semi"], int(p.get("cantidad", 24)),
                         int(p.get("seed", 0)), p.get("jitter", 0.4))
    return _samples_planos(pts, p)


@op("source_poisson", 0)
def _src_poisson(_e, p):
    pts = sc.poisson_disk(p["centro"], p["semi"], p.get("spacing", 150.0), int(p.get("seed", 0)))
    lim = int(p.get("cantidad", 0))
    if lim and len(pts) > lim:
        pts = pts[:lim]
    return _samples_planos(pts, p)


@op("source_radial", 0)
def _src_radial(_e, p):
    pts = sc.radial(p["centro"], min(p["semi"]), int(p.get("cantidad", 24)),
                    int(p.get("anillos", 3)), int(p.get("seed", 0)))
    return _samples_planos(pts, p)


def _samples_planos(pts, p):
    """Puntos (x,y) → Samples planos (slope 0). El adaptador reemplaza esto por raycast a la superficie
    real cuando corre dentro del editor (nodo `source_surface`); en puro, quedan a z=0."""
    from .geometry import Vec3
    z = p.get("suelo_z", 0.0)
    seed = int(p.get("seed", 0))
    return [sc.Sample(Vec3(x, y, z), Vec3(0.0, 0.0, 1.0), 0.0, sc.semilla_de(seed, x, y),
                      (0.0, 0.0)) for (x, y) in pts]


# ---------- máscaras (1 entrada): stream → stream ----------

@op("mask_slope", 1)
def _mk_slope(e, p):
    v, _ = sc.aplicar_mascaras(e[0], [sc.mask_slope(p.get("min", 0.0), p.get("max", 90.0))])
    return v


@op("mask_height", 1)
def _mk_height(e, p):
    v, _ = sc.aplicar_mascaras(e[0], [sc.mask_height(p.get("min", -1e12), p.get("max", 1e12))])
    return v


@op("mask_noise", 1)
def _mk_noise(e, p):
    v, _ = sc.aplicar_mascaras(e[0], [sc.mask_noise(
        p.get("threshold", 0.5), 1.0 / max(1.0, p.get("scale", 500.0)),
        int(p.get("seed", 0)), p.get("invert", False))])
    return v


@op("mask_density", 1)
def _mk_density(e, p):
    v, _ = sc.aplicar_mascaras(e[0], [sc.mask_density(p.get("keep", 1.0), int(p.get("seed", 0)))])
    return v


@op("mask_circle", 1)
def _mk_circle(e, p):
    v, _ = sc.aplicar_mascaras(e[0], [sc.mask_circle(
        p["centro"], p.get("radio", 300.0), p.get("keep_inside", True))])
    return v


@op("merge", -1)
def _merge(e, _p):
    out = []
    for stream in e:
        out.extend(stream)
    return out


# ---------- evaluación (orden topológico, como cualquier grafo dataflow) ----------

class Flow:
    """Grafo de operaciones de stream. `nodos`: id → {kind, params}. `enlaces`: [(origen, destino)],
    en orden (para nodos con varias entradas, el orden de los enlaces es el orden de las entradas)."""

    def __init__(self):
        self.nodos: dict[str, dict] = {}
        self.enlaces: list[tuple[str, str]] = []

    def add(self, kind: str, params: dict | None = None, nid: str | None = None) -> str:
        nid = nid or f"f{len(self.nodos) + 1}"
        self.nodos[nid] = {"kind": kind, "params": dict(params or {})}
        return nid

    def connect(self, origen: str, destino: str) -> None:
        if origen in self.nodos and destino in self.nodos:
            self.enlaces.append((origen, destino))

    def _entradas(self, nid: str) -> list[str]:
        return [a for a, b in self.enlaces if b == nid]

    def topo(self) -> list[str]:
        indeg = {n: 0 for n in self.nodos}
        adj: dict[str, list[str]] = {n: [] for n in self.nodos}
        for a, b in self.enlaces:
            adj[a].append(b)
            indeg[b] += 1
        cola = [n for n in self.nodos if indeg[n] == 0]
        orden = []
        while cola:
            n = cola.pop(0)
            orden.append(n)
            for m in adj[n]:
                indeg[m] -= 1
                if indeg[m] == 0:
                    cola.append(m)
        if len(orden) != len(self.nodos):
            raise ValueError("el flow tiene un ciclo")
        return orden

    def evaluar(self, ops: dict | None = None) -> dict[str, list]:
        """Corre el grafo; devuelve {id: stream}. `ops` permite sumar operaciones del adaptador
        (p.ej. `source_surface` que raycastea, o `instance` que spawnea) sin tocar este módulo."""
        tabla = {**OPS, **(ops or {})}
        salida: dict[str, list] = {}
        for nid in self.topo():
            nodo = self.nodos[nid]
            fn_ent = tabla.get(nodo["kind"])
            if fn_ent is None:
                salida[nid] = []
                continue
            fn, _n = fn_ent
            entradas = [salida.get(e, []) for e in self._entradas(nid)]
            salida[nid] = fn(entradas, nodo["params"])
        return salida
