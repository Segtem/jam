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


# Metadata para la UI (categoría, params, aridad). Es DATO puro — incluye las ops del adaptador
# (source_surface, instance), cuyas FUNCIONES viven en `jam.scatter` pero cuya descripción no toca el
# motor. El canvas se arma desde acá; `Flow.evaluar` recibe las funciones del adaptador aparte.
# cat: Source (fuente, sin entrada) · Mask (filtra) · Combine · Output (instancia).
OPS_META: dict = {
    "source_surface": {"cat": "Source", "source": True,
                       "params": {"area": 800.0, "count": 40, "pattern": "poisson",
                                  "spacing": 0.0, "seed": 7},
                       "opciones": {"pattern": ["poisson", "grid", "radial", "hexagonal", "triangular"]},
                       "doc": "puntos sobre la superficie real (raycast) — el Scatter SOP"},
    "mask_slope":   {"cat": "Mask", "params": {"min": 0.0, "max": 90.0},
                     "doc": "descarta por pendiente (Angle Mask)"},
    "mask_height":  {"cat": "Mask", "params": {"min": 0.0, "max": 0.0},
                     "doc": "recorta por altura (Min/Max Height); 0/0 = sin límite"},
    "mask_noise":   {"cat": "Mask", "params": {"threshold": 0.5, "scale": 500.0, "seed": 7},
                     "doc": "rompe la uniformidad → manchones (Noise Mask)"},
    "mask_density": {"cat": "Mask", "params": {"keep": 0.6, "seed": 7},
                     "doc": "conserva una fracción al azar (Add/Remove)"},
    "merge":        {"cat": "Combine", "aridad": -1, "params": {},
                     "doc": "junta varios streams de puntos en uno"},
    "instance":     {"cat": "Output", "params": {"scale_min": 1.0, "scale_max": 1.0, "anchor": "base",
                                                 "align": False, "sink": 0.0},
                     "doc": "instancia el asset activo en cada punto (Copy to Points)"},
}


def spec_json() -> str:
    """El registro de ops de flow como JSON (mismo formato que `tools.spec_json`) para que el canvas
    dibuje los nodos. `source`=sin pin de entrada; `aridad -1`=varias entradas (merge)."""
    import json

    def tipo(v):
        if isinstance(v, bool):
            return "bool"
        if isinstance(v, int):
            return "int"
        if isinstance(v, float):
            return "float"
        return "str"

    cats = ["Source", "Mask", "Combine", "Output"]
    nodos = []
    for kind, m in OPS_META.items():
        ops_val = m.get("opciones", {})
        nodos.append({
            "verbo": kind,
            "cat": m["cat"],
            "doc": m["doc"],
            "source": bool(m.get("source", False)),
            "aridad": m.get("aridad", 0 if m.get("source") else 1),
            "params": [{"nombre": k, "default": str(v), "tipo": tipo(v),
                        "opciones": ops_val.get(k, [])} for k, v in m["params"].items()],
        })
    return json.dumps({"categorias": cats, "tools": nodos}, ensure_ascii=True)


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

def _coaccionar(kind: str, params: dict) -> dict:
    """Convierte cada param al tipo de su default en OPS_META (el canvas manda todo como string)."""
    spec = OPS_META.get(kind, {}).get("params", {})
    out = {}
    for k, v in params.items():
        d = spec.get(k)
        try:
            if isinstance(d, bool):
                out[k] = str(v).lower() in ("1", "true", "si", "sí", "yes", "on")
            elif isinstance(d, int):
                out[k] = int(float(v))
            elif isinstance(d, float):
                out[k] = float(v)
            else:
                out[k] = v
        except (TypeError, ValueError):
            out[k] = v
    return out


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

    @classmethod
    def from_json(cls, s: str) -> "Flow":
        """Construye desde el JSON del canvas: {nodes:{id:{verb,params}}, edges:[[from,to]]}. `verb`
        es el kind. Los params se coaccionan al tipo de su default en OPS_META."""
        import json
        d = json.loads(s) if s else {}
        f = cls()
        for nid, nd in d.get("nodes", {}).items():
            kind = nd.get("verb") or nd.get("kind", "")
            f.nodos[nid] = {"kind": kind, "params": _coaccionar(kind, nd.get("params", {}))}
        f.enlaces = [(e[0], e[1]) for e in d.get("edges", []) if len(e) == 2]
        return f

    def solo_flow(self) -> bool:
        """¿Todos los nodos son ops de flow? (para que el runner distinga flow de grafo de verbos)."""
        return bool(self.nodos) and all(n["kind"] in OPS_META for n in self.nodos.values())

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
