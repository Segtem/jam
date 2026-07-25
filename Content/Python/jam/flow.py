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
    # Params/Maths: el «cerebro paramétrico» de Grasshopper. NO producen puntos: aportan un VALOR con
    # nombre a una tabla de variables. Cualquier param de cualquier nodo puede ser una EXPRESIÓN
    # (empieza con «=») que se evalúa contra esa tabla → un slider maneja `count`, `spacing`, etc.
    "number": {"cat": "Params", "source": True, "params": {"name": "n", "value": 0.0},
               "doc": "variable: un número con nombre (como un Number Slider de Grasshopper)"},
    "math":   {"cat": "Maths", "source": True, "params": {"name": "m", "expr": "0"},
               "doc": "expresión sobre variables: sin/cos/sqrt/min/max/clamp/lerp/remap/rand (el Expression)"},
    "text":   {"cat": "Params", "source": True, "params": {"name": "t", "value": ""},
               "doc": "variable de TEXTO con nombre (para anclas, nombres de asset, modos…)"},
    "source_surface": {"cat": "Source", "source": True,
                       "params": {"area": 800.0, "count": 40, "pattern": "poisson",
                                  "spacing": 0.0, "seed": 7},
                       "opciones": {"pattern": ["poisson", "grid", "radial", "hexagonal", "triangular"]},
                       "doc": "puntos sobre la superficie real (raycast) — el Scatter SOP"},
    # Vector: GENERADORES de puntos planos (sin raycast), el tab Vector/Point de GH. Producen un stream
    # que después se transforma/enmascara/instancia (o se sube a la superficie con otro nodo).
    "pts_line":     {"cat": "Vector", "source": True,
                     "params": {"ax": 0.0, "ay": 0.0, "bx": 500.0, "by": 0.0, "count": 10, "seed": 0},
                     "doc": "puntos equiespaciados de A a B (Points on a line)"},
    "pts_circle":   {"cat": "Vector", "source": True,
                     "params": {"cx": 0.0, "cy": 0.0, "radius": 300.0, "count": 12, "seed": 0},
                     "doc": "puntos sobre una circunferencia (Points on a circle)"},
    "pts_rect":     {"cat": "Vector", "source": True,
                     "params": {"cx": 0.0, "cy": 0.0, "size_x": 600.0, "size_y": 600.0,
                                "cols": 5, "rows": 5, "seed": 0},
                     "doc": "grilla rectangular de cols×rows puntos (Rectangular grid)"},
    "pts_arc":      {"cat": "Vector", "source": True,
                     "params": {"cx": 0.0, "cy": 0.0, "radius": 300.0, "start_deg": 0.0,
                                "end_deg": 90.0, "count": 10, "seed": 0},
                     "doc": "puntos sobre un arco (Points on an arc)"},
    "mask_slope":   {"cat": "Mask", "params": {"min": 0.0, "max": 90.0},
                     "doc": "descarta por pendiente (Angle Mask)"},
    "mask_height":  {"cat": "Mask", "params": {"min": 0.0, "max": 0.0},
                     "doc": "recorta por altura (Min/Max Height); 0/0 = sin límite"},
    "mask_noise":   {"cat": "Mask", "params": {"threshold": 0.5, "scale": 500.0, "seed": 7},
                     "doc": "rompe la uniformidad → manchones (Noise Mask)"},
    "mask_density": {"cat": "Mask", "params": {"keep": 0.6, "seed": 7},
                     "doc": "conserva una fracción al azar (Add/Remove)"},
    # Sets: operaciones de LISTA sobre el stream (el tab Sets de GH) — reordenan/recortan los puntos.
    "cull_nth":     {"cat": "Sets", "params": {"n": 2, "offset": 0},
                     "doc": "conserva 1 de cada N puntos (Cull Nth) — diezma de forma regular"},
    "sub_list":     {"cat": "Sets", "params": {"start": 0, "count": 0},
                     "doc": "toma un tramo de la lista [start, start+count) (Sub List); count 0 = hasta el final"},
    "shift":        {"cat": "Sets", "params": {"by": 1},
                     "doc": "rota el orden de la lista `by` posiciones (Shift List)"},
    "reverse":      {"cat": "Sets", "params": {},
                     "doc": "invierte el orden de los puntos (Reverse List)"},
    "relax":        {"cat": "Sets", "params": {"min_dist": 100.0},
                     "doc": "descarta puntos más cerca que `min_dist` entre sí (cull duplicados / relax)"},
    # Transform: mueven/escalan/rotan/jitterean las POSICIONES del stream (el tab Transform de GH).
    "move":         {"cat": "Transform", "params": {"dx": 0.0, "dy": 0.0, "dz": 0.0},
                     "doc": "desplaza todos los puntos por (dx,dy,dz) — Move"},
    "scale_pts":    {"cat": "Transform", "params": {"factor": 1.0, "cx": 0.0, "cy": 0.0, "cz": 0.0},
                     "doc": "escala las posiciones desde un centro (0/0/0 = centroide del stream) — Scale"},
    "rotate_pts":   {"cat": "Transform", "params": {"deg": 0.0, "cx": 0.0, "cy": 0.0},
                     "doc": "rota las posiciones en Z alrededor de un centro (0/0 = centroide) — Rotate"},
    "jitter":       {"cat": "Transform", "params": {"amount": 20.0, "seed": 7},
                     "doc": "offset aleatorio DETERMINISTA por punto (Jitter) — rompe la regularidad"},
    "merge":        {"cat": "Combine", "aridad": -1, "params": {},
                     "doc": "junta varios streams de puntos en uno"},
    "weave":        {"cat": "Combine", "aridad": -1, "params": {},
                     "doc": "intercala varios streams alternando uno de cada uno (Weave)"},
    "info":         {"cat": "Display", "params": {},
                     "doc": "passthrough: reporta cantidad + caja (bbox) del stream (Panel/Info de GH)"},
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

    # nombre de la SALIDA de cada op (la «variable» que sale por el pin de salida, estilo GH):
    # P = stream de puntos · N = número · T = texto · A = actores instanciados.
    out_names = {"number": "N", "math": "N", "text": "T", "instance": "A"}

    cats = ["Params", "Maths", "Source", "Vector", "Mask", "Sets", "Transform", "Combine",
            "Output", "Display"]
    nodos = []
    for kind, m in OPS_META.items():
        ops_val = m.get("opciones", {})
        nodos.append({
            "verbo": kind,
            "cat": m["cat"],
            "doc": m["doc"],
            "source": bool(m.get("source", False)),
            "aridad": m.get("aridad", 0 if m.get("source") else 1),
            "out_name": out_names.get(kind, "P"),
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


# ---------- Vector: generadores de puntos planos (línea, círculo, grilla, arco) ----------

@op("pts_line", 0)
def _pts_line(_e, p):
    ax, ay = p.get("ax", 0.0), p.get("ay", 0.0)
    bx, by = p.get("bx", 500.0), p.get("by", 0.0)
    n = max(1, int(p.get("count", 10)))
    pts = [(ax + (bx - ax) * (i / (n - 1) if n > 1 else 0.0),
            ay + (by - ay) * (i / (n - 1) if n > 1 else 0.0)) for i in range(n)]
    return _samples_planos(pts, p)


@op("pts_circle", 0)
def _pts_circle(_e, p):
    import math
    cx, cy, r = p.get("cx", 0.0), p.get("cy", 0.0), p.get("radius", 300.0)
    n = max(1, int(p.get("count", 12)))
    pts = [(cx + r * math.cos(2 * math.pi * i / n), cy + r * math.sin(2 * math.pi * i / n))
           for i in range(n)]
    return _samples_planos(pts, p)


@op("pts_rect", 0)
def _pts_rect(_e, p):
    cx, cy = p.get("cx", 0.0), p.get("cy", 0.0)
    sx, sy = p.get("size_x", 600.0), p.get("size_y", 600.0)
    cols, rows = max(1, int(p.get("cols", 5))), max(1, int(p.get("rows", 5)))
    pts = []
    for j in range(rows):
        for i in range(cols):
            fx = (i / (cols - 1) - 0.5) if cols > 1 else 0.0
            fy = (j / (rows - 1) - 0.5) if rows > 1 else 0.0
            pts.append((cx + fx * sx, cy + fy * sy))
    return _samples_planos(pts, p)


@op("pts_arc", 0)
def _pts_arc(_e, p):
    import math
    cx, cy, r = p.get("cx", 0.0), p.get("cy", 0.0), p.get("radius", 300.0)
    a0, a1 = math.radians(p.get("start_deg", 0.0)), math.radians(p.get("end_deg", 90.0))
    n = max(1, int(p.get("count", 10)))
    pts = []
    for i in range(n):
        a = a0 + (a1 - a0) * (i / (n - 1) if n > 1 else 0.0)
        pts.append((cx + r * math.cos(a), cy + r * math.sin(a)))
    return _samples_planos(pts, p)


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


# ---------- Sets (listas): reordenan / recortan el stream, como el tab Sets de GH ----------

@op("cull_nth", 1)
def _cull_nth(e, p):
    n = max(1, int(p.get("n", 2)))
    off = int(p.get("offset", 0))
    return [s for i, s in enumerate(e[0]) if (i - off) % n == 0]


@op("sub_list", 1)
def _sub_list(e, p):
    start = max(0, int(p.get("start", 0)))
    count = int(p.get("count", 0))
    xs = e[0][start:]
    return xs[:count] if count > 0 else xs


@op("shift", 1)
def _shift(e, p):
    xs = e[0]
    if not xs:
        return xs
    k = int(p.get("by", 1)) % len(xs)
    return xs[k:] + xs[:k]


@op("reverse", 1)
def _reverse(e, _p):
    return list(reversed(e[0]))


@op("relax", 1)
def _relax(e, p):
    """Descarta puntos más cerca que `min_dist` de uno ya aceptado (cull duplicados / relax)."""
    d = p.get("min_dist", 100.0)
    d2 = d * d
    kept: list = []
    for s in e[0]:
        if all((s.pos.x - k.pos.x) ** 2 + (s.pos.y - k.pos.y) ** 2 >= d2 for k in kept):
            kept.append(s)
    return kept


# ---------- Transform: mueven / escalan / rotan / jitterean las POSICIONES del stream ----------

def _con_pos(s, x, y, z):
    """Un Sample nuevo con la misma info pero otra posición (los Sample son inmutables)."""
    from .geometry import Vec3
    return sc.Sample(Vec3(x, y, z), s.normal, s.slope, s.seed, s.uv)


def _centro(xs, p):
    """Centro para escala/rotación: el dado (cx/cy/cz) o, si es (0,0,0), el CENTROIDE del stream."""
    cx, cy, cz = p.get("cx", 0.0), p.get("cy", 0.0), p.get("cz", 0.0)
    if cx == 0.0 and cy == 0.0 and cz == 0.0 and xs:
        cx = sum(s.pos.x for s in xs) / len(xs)
        cy = sum(s.pos.y for s in xs) / len(xs)
        cz = sum(s.pos.z for s in xs) / len(xs)
    return cx, cy, cz


@op("move", 1)
def _move(e, p):
    dx, dy, dz = p.get("dx", 0.0), p.get("dy", 0.0), p.get("dz", 0.0)
    return [_con_pos(s, s.pos.x + dx, s.pos.y + dy, s.pos.z + dz) for s in e[0]]


@op("scale_pts", 1)
def _scale_pts(e, p):
    f = p.get("factor", 1.0)
    xs = e[0]
    cx, cy, cz = _centro(xs, p)
    return [_con_pos(s, cx + (s.pos.x - cx) * f, cy + (s.pos.y - cy) * f, cz + (s.pos.z - cz) * f)
            for s in xs]


@op("rotate_pts", 1)
def _rotate_pts(e, p):
    import math
    r = math.radians(p.get("deg", 0.0))
    ca, sa = math.cos(r), math.sin(r)
    xs = e[0]
    cx, cy, _cz = _centro(xs, p)
    out = []
    for s in xs:
        dx, dy = s.pos.x - cx, s.pos.y - cy
        out.append(_con_pos(s, cx + dx * ca - dy * sa, cy + dx * sa + dy * ca, s.pos.z))
    return out


@op("jitter", 1)
def _jitter(e, p):
    import random
    amt = p.get("amount", 20.0)
    seed = int(p.get("seed", 0))
    out = []
    for s in e[0]:
        rng = random.Random(sc.semilla_de(seed, s.pos.x, s.pos.y))
        out.append(_con_pos(s, s.pos.x + rng.uniform(-amt, amt),
                            s.pos.y + rng.uniform(-amt, amt), s.pos.z))
    return out


@op("merge", -1)
def _merge(e, _p):
    out = []
    for stream in e:
        out.extend(stream)
    return out


@op("weave", -1)
def _weave(e, _p):
    """Intercala varios streams: 1º de cada uno, 2º de cada uno… hasta agotar el más largo (Weave)."""
    out = []
    i = 0
    while any(i < len(stream) for stream in e):
        for stream in e:
            if i < len(stream):
                out.append(stream[i])
        i += 1
    return out


# ---------- Display: inspeccionar el stream (passthrough) ----------

@op("info", 1)
def _info(e, p):
    """Passthrough que MIDE el stream (cantidad + caja) y lo deja en `_stats` para que el nodo lo
    muestre en el canvas — como un Panel de GH. No modifica el stream."""
    xs = e[0]
    if xs:
        w = round(max(s.pos.x for s in xs) - min(s.pos.x for s in xs), 1)
        h = round(max(s.pos.y for s in xs) - min(s.pos.y for s in xs), 1)
        p["_stats"] = {"n": len(xs), "w": w, "h": h}
    else:
        p["_stats"] = {"n": 0}
    return xs


# ---------- variables + matemática (el «cerebro paramétrico» de Grasshopper) ----------

import math as _math


def _rand(semilla) -> float:
    """Aleatorio DETERMINISTA en [0,1) a partir de una semilla (como el Random de Grasshopper, pero
    puro: la misma semilla da el mismo número). Evita `random` global para que el grafo sea reproducible."""
    h = (int(semilla) * 2654435761) & 0xFFFFFFFF
    h ^= (h >> 16)
    h = (h * 2246822519) & 0xFFFFFFFF
    h ^= (h >> 13)
    return (h & 0xFFFFFF) / float(0x1000000)


# funciones disponibles en las expresiones (sin builtins peligrosos: se evalúa con __builtins__ vacío).
_FUNCS: dict = {
    "sin": _math.sin, "cos": _math.cos, "tan": _math.tan, "atan": _math.atan,
    "asin": _math.asin, "acos": _math.acos, "sqrt": _math.sqrt, "exp": _math.exp,
    "log": _math.log, "floor": _math.floor, "ceil": _math.ceil,
    "radians": _math.radians, "degrees": _math.degrees, "pi": _math.pi, "e": _math.e,
    "abs": abs, "min": min, "max": max, "round": round, "pow": pow,
    "clamp": lambda x, a, b: a if x < a else (b if x > b else x),
    "lerp": lambda a, b, t: a + (b - a) * t,
    "remap": lambda x, a, b, c, d: c + (d - c) * ((x - a) / (b - a)) if b != a else c,
    "rand": _rand,
}


def _eval_expr(expr, tabla: dict):
    """Evalúa una expresión matemática contra la tabla de variables + `_FUNCS`. Devuelve float, o None
    si referencia algo que todavía no existe (para que la resolución multi-pasada se asiente)."""
    ns = dict(_FUNCS)
    ns.update(tabla)
    try:
        return float(eval(str(expr), {"__builtins__": {}}, ns))  # noqa: S307 (expr del propio usuario)
    except (NameError, TypeError):
        return None   # variable aún no definida → otra pasada la resolverá
    except (ValueError, ZeroDivisionError, SyntaxError, ArithmeticError):
        return None


def _num(v, defecto=0.0) -> float:
    try:
        return float(v)
    except (TypeError, ValueError):
        return defecto


def _resolver_params(params: dict, tabla: dict) -> dict:
    """Reemplaza cada param que sea EXPRESIÓN (string que empieza con «=») por su valor evaluado contra
    la tabla. Los demás pasan tal cual. Si la expresión no resuelve, cae a 0.0 (para no romper el nodo)."""
    out = {}
    for k, v in params.items():
        if isinstance(v, str) and v.startswith("="):
            r = _eval_expr(v[1:], tabla)
            out[k] = r if r is not None else 0.0
        else:
            out[k] = v
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


#: pin de entrada del STREAM de puntos (el cable «gordo»). Los demás pines de entrada son PARÁMETROS
#: (count, spacing, keep…): un cable a ese pin ata el valor de una variable a ese parámetro, como en GH.
PIN_STREAM_IN = "in"
PIN_OUT = "out"

#: nodos de VALOR: no producen puntos, aportan un valor con nombre (number/math = número, text = texto).
VALOR_KINDS = ("number", "math", "text")


class Flow:
    """Grafo de operaciones de stream, con conexión POR PIN (como Grasshopper). `nodos`: id →
    {kind, params}. `enlaces`: [(origen, origen_pin, destino, destino_pin)] en orden.

    Cada nodo tiene: un pin de salida «out» (a la derecha), un pin de entrada de stream «in» (el cable
    de puntos), y UN PIN POR PARÁMETRO a la izquierda. Cablear la salida de un `number`/`math` a un pin
    de parámetro (p.ej. `count`) ATA ese parámetro al valor de la variable — el equivalente visual de la
    expresión «=». El pin «in» acepta varios cables (se juntan, como el input de lista de GH)."""

    def __init__(self):
        self.nodos: dict[str, dict] = {}
        self.enlaces: list[tuple[str, str, str, str]] = []

    def add(self, kind: str, params: dict | None = None, nid: str | None = None) -> str:
        nid = nid or f"f{len(self.nodos) + 1}"
        self.nodos[nid] = {"kind": kind, "params": dict(params or {})}
        return nid

    def connect(self, origen: str, destino: str, destino_pin: str = PIN_STREAM_IN,
                origen_pin: str = PIN_OUT) -> None:
        """Conecta `origen.origen_pin` → `destino.destino_pin`. Por defecto stream out→in; pasá
        `destino_pin="count"` (u otro parámetro) para atar una variable a ese parámetro (estilo GH)."""
        if origen in self.nodos and destino in self.nodos:
            self.enlaces.append((origen, origen_pin, destino, destino_pin))

    @classmethod
    def from_json(cls, s: str) -> "Flow":
        """Construye desde el JSON del canvas: {nodes:{id:{verb,params}}, edges:[…]}. Cada arista es
        `[from, to]` (stream out→in, compat) o `[from, from_pin, to, to_pin]` (conexión por pin)."""
        import json
        d = json.loads(s) if s else {}
        f = cls()
        for nid, nd in d.get("nodes", {}).items():
            kind = nd.get("verb") or nd.get("kind", "")
            f.nodos[nid] = {"kind": kind, "params": _coaccionar(kind, nd.get("params", {}))}
        for e in d.get("edges", []):
            if len(e) == 4:
                f.enlaces.append((e[0], e[1], e[2], e[3]))
            elif len(e) == 2:
                f.enlaces.append((e[0], PIN_OUT, e[1], PIN_STREAM_IN))
        return f

    def solo_flow(self) -> bool:
        """¿Todos los nodos son ops de flow? (para que el runner distinga flow de grafo de verbos)."""
        return bool(self.nodos) and all(n["kind"] in OPS_META for n in self.nodos.values())

    def _entradas(self, nid: str) -> list[str]:
        """Orígenes cableados al pin de STREAM «in» de `nid`, en orden (para merge = lista de entradas)."""
        return [a for a, ap, b, bp in self.enlaces if b == nid and bp == PIN_STREAM_IN]

    def _param_wires(self, nid: str) -> dict:
        """{ pin_de_parámetro: origen } de los cables que entran a un PARÁMETRO de `nid` (no al stream).
        Si un parámetro recibe varios cables, gana el último (como reconectar en GH)."""
        out: dict = {}
        for a, ap, b, bp in self.enlaces:
            if b == nid and bp not in (PIN_STREAM_IN,):
                out[bp] = a
        return out

    def topo(self) -> list[str]:
        indeg = {n: 0 for n in self.nodos}
        adj: dict[str, list[str]] = {n: [] for n in self.nodos}
        for a, ap, b, bp in self.enlaces:
            if a in self.nodos and b in self.nodos:
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

    def _valores(self) -> dict:
        """Tabla de variables { nombre: valor } de los nodos `number`/`math`. Resuelve por PASADAS
        (una expresión puede referenciar otra variable) hasta que se asienta o se agotan las pasadas."""
        val_nodos = [(nid, n) for nid, n in self.nodos.items() if n["kind"] in VALOR_KINDS]
        tabla: dict = {}
        for _ in range(len(val_nodos) + 1):
            cambio = False
            for nid, n in val_nodos:
                nombre = str(n["params"].get("name") or nid)
                if n["kind"] == "number":
                    v = _num(n["params"].get("value", 0.0))
                elif n["kind"] == "text":
                    v = str(n["params"].get("value", ""))
                else:
                    v = _eval_expr(n["params"].get("expr", "0"),
                                   {k: x for k, x in tabla.items() if isinstance(x, (int, float))})
                if v is not None and tabla.get(nombre) != v:
                    tabla[nombre] = v
                    cambio = True
            if not cambio:
                break
        return tabla

    def evaluar(self, ops: dict | None = None) -> dict[str, list]:
        """Corre el grafo; devuelve {id: stream}. Primero arma la tabla de variables (number/math) y con
        ella resuelve las EXPRESIONES de los params (los que empiezan con «=»). `ops` suma operaciones
        del adaptador (p.ej. `source_surface` que raycastea, o `instance` que spawnea) sin tocar esto."""
        tabla_fn = {**OPS, **(ops or {})}
        variables = self._valores()
        # escalar de cada nodo de valor (lo que un cable suyo lleva a un pin de parámetro).
        escalar_de = {nid: variables.get(str(n["params"].get("name") or nid))
                      for nid, n in self.nodos.items() if n["kind"] in VALOR_KINDS}
        salida: dict[str, list] = {}
        for nid in self.topo():
            nodo = self.nodos[nid]
            kind = nodo["kind"]
            # nodos de valor: no producen puntos, aportan su número a la tabla (y lo dejan para la UI).
            if kind in VALOR_KINDS:
                nombre = str(nodo["params"].get("name") or nid)
                nodo["params"]["_val"] = variables.get(nombre)
                salida[nid] = []
                continue
            fn_ent = tabla_fn.get(kind)
            if fn_ent is None:
                salida[nid] = []
                continue
            fn, _n = fn_ent
            entradas = [salida.get(e, []) for e in self._entradas(nid)]
            # primero resolver expresiones «=», después pisar con lo que llegue por CABLE a cada pin de
            # parámetro (un cable manda sobre el texto del campo, como en Grasshopper).
            params = _resolver_params(nodo["params"], variables)
            for pin, origen in self._param_wires(nid).items():
                if escalar_de.get(origen) is not None:
                    params[pin] = escalar_de[origen]
            salida[nid] = fn(entradas, params)
        return salida
