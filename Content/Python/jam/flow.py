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
from .math_core import VALORES, VALOR_KINDS

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
    **VALORES,
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
    # Weight: máscaras ESCALARES 0..1 (el paradigma del shader de máscaras globales). Cada una MULTIPLICA
    # su gris en el `weight` del punto (encadenar = AND suave); los conectores lo reforman; `weight_cull`
    # lo vuelve decisión. Grafo Textura→Máscara→Conector→Aplicador, sobre puntos en vez de píxeles.
    "weight_slope":  {"cat": "Weight", "params": {"min": 0.0, "max": 30.0, "soft": 5.0},
                      "doc": "máscara suave por pendiente (0..1): 1 dentro de [min,max], borde de ancho `soft`"},
    "weight_height": {"cat": "Weight", "params": {"min": 0.0, "max": 500.0, "soft": 50.0},
                      "doc": "máscara suave por altura Z (como World Position Z → Smooth Step del shader)"},
    "weight_noise":  {"cat": "Weight", "params": {"scale": 500.0, "seed": 7, "contrast": 1.0},
                      "doc": "campo de ruido 0..1 (el Noise del shader); `contrast` = power sobre el gris"},
    "weight_radial": {"cat": "Weight", "params": {"cx": 0.0, "cy": 0.0, "radius": 300.0, "soft": 0.5},
                      "doc": "gradiente radial: 1 en el centro → 0 en `radius` (soft 0 = disco duro)"},
    "weight_invert": {"cat": "Weight", "params": {},
                      "doc": "invierte el gris (One Minus): weight → 1 − weight"},
    "weight_power":  {"cat": "Weight", "params": {"k": 2.0},
                      "doc": "contraste del gris (Power): weight → weight^k (k>1 endurece, <1 suaviza)"},
    "weight_curve":  {"cat": "Weight", "params": {"min": 0.0, "max": 1.0},
                      "doc": "remapea el gris con bordes suaves (Smooth Step sobre la máscara)"},
    "weight_combine": {"cat": "Weight", "aridad": -1, "params": {"mode": "mul", "t": 0.5},
                       "opciones": {"mode": ["mul", "add", "max", "min", "lerp"]},
                       "doc": "junta el gris de varias ramas paralelas (multiplicar/sumar máscaras)"},
    "weight_cull":   {"cat": "Weight", "params": {"threshold": 0.5, "seed": 7, "soft": 0.0},
                      "doc": "APLICADOR: corta por el gris. soft 0 = duro (≥ threshold) · 1 = densidad (prob = gris)"},
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
    # El otro terminal: en vez de instanciar geometría en los puntos que sobrevivieron, HORNEA la
    # cadena de Weight que llega hasta acá como un material. La misma máscara que dispersa, pinta.
    "weight_material": {"cat": "Output",
                        "params": {"name": "M_JamMascara", "folder": "/Game/Jam/Materials",
                                   "color_a": "#4D4A45", "color_b": "#AE9466", "rugosidad": 0.9},
                        "doc": "compila la cadena de Weight que entra acá a un MATERIAL "
                               "(la máscara que dispersa, pintada); salida A"},
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
    out_names = {"instance": "A", "weight_material": "A"}

    cats = ["Params", "Maths", "Source", "Vector", "Mask", "Weight", "Sets", "Transform", "Combine",
            "Output", "Display"]
    nodos = []
    for kind, m in OPS_META.items():
        ops_val = m.get("opciones", {})
        nodos.append({
            "verbo": kind,
            "label": m.get("label", kind),
            "cat": m["cat"],
            "doc": m["doc"],
            "source": bool(m.get("source", False)),
            "aridad": m.get("aridad", 0 if m.get("source") else 1),
            # Todo el flow no-fuente recibe un stream de puntos por su pin gordo.
            "in_name": "" if m.get("source", False) else "P",
            "out_name": m.get("out_name", out_names.get(kind, "P")),
            "out_label": m.get("out_label", ""),
            "params": [{"nombre": k, "label": m.get("etiquetas_params", {}).get(k, k),
                        "default": str(v), "tipo": tipo(v),
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


# ---------- Weight: máscaras ESCALARES 0..1 (el paradigma del shader de máscaras del arte técnico) ----------
# En vez de cullear duro, cada op ESCRIBE un campo 0..1 y lo MULTIPLICA en el `weight` del punto — encadenar
# máscaras = AND suave (como multiplicar máscaras de shader: «los ceros son anclas»). Los conectores
# (invert/power/curve) reforman ese gris; `weight_combine` junta ramas paralelas; `weight_cull` lo vuelve
# decisión (o densidad). Es el mismo grafo Textura→Máscara→Conector→Aplicador, pero sobre PUNTOS.

def _band(x: float, lo: float, hi: float, soft: float) -> float:
    """Banda 0..1: 1 dentro de [lo,hi], con bordes de ancho `soft` (0 = borde duro)."""
    return _smoothstep(lo - soft, lo, x) * (1.0 - _smoothstep(hi, hi + soft, x))


@op("weight_slope", 1)
def _w_slope(e, p):
    lo, hi, soft = p.get("min", 0.0), p.get("max", 90.0), p.get("soft", 5.0)
    return [s._replace(weight=s.weight * _band(s.slope, lo, hi, soft)) for s in e[0]]


@op("weight_height", 1)
def _w_height(e, p):
    lo, hi, soft = p.get("min", -1e12), p.get("max", 1e12), p.get("soft", 50.0)
    return [s._replace(weight=s.weight * _band(s.pos.z, lo, hi, soft)) for s in e[0]]


@op("weight_noise", 1)
def _w_noise(e, p):
    freq = 1.0 / max(1.0, p.get("scale", 500.0))
    seed = int(p.get("seed", 0))
    k = max(0.01, p.get("contrast", 1.0))
    return [s._replace(weight=s.weight * (sc.value_noise(s.pos.x, s.pos.y, freq, seed) ** k))
            for s in e[0]]


@op("weight_radial", 1)
def _w_radial(e, p):
    cx, cy, r = p.get("cx", 0.0), p.get("cy", 0.0), max(1.0, p.get("radius", 300.0))
    inner = r * (1.0 - _sat(p.get("soft", 0.5)))   # soft 0 = disco duro · 1 = gradiente desde el centro
    out = []
    for s in e[0]:
        d = ((s.pos.x - cx) ** 2 + (s.pos.y - cy) ** 2) ** 0.5
        out.append(s._replace(weight=s.weight * (1.0 - _smoothstep(inner, r, d))))
    return out


@op("weight_invert", 1)
def _w_invert(e, _p):
    return [s._replace(weight=1.0 - s.weight) for s in e[0]]


@op("weight_power", 1)
def _w_power(e, p):
    k = max(0.01, p.get("k", 2.0))
    return [s._replace(weight=_sat(s.weight) ** k) for s in e[0]]


@op("weight_curve", 1)
def _w_curve(e, p):
    lo, hi = p.get("min", 0.0), p.get("max", 1.0)
    return [s._replace(weight=_smoothstep(lo, hi, s.weight)) for s in e[0]]


@op("weight_combine", -1)
def _w_combine(e, p):
    """Junta el `weight` de VARIAS ramas paralelas elementwise (mismos puntos, mismo orden), como
    multiplicar/sumar máscaras de shader. mode: mul (AND) · add · max · min · lerp(t)."""
    ramas = [r for r in e if r]
    if not ramas:
        return []
    base = list(ramas[0])
    mode = str(p.get("mode", "mul"))
    t = p.get("t", 0.5)
    for otra in ramas[1:]:
        for i in range(min(len(base), len(otra))):
            a, b = base[i].weight, otra[i].weight
            w = (a * b if mode == "mul" else a + b if mode == "add"
                 else max(a, b) if mode == "max" else min(a, b) if mode == "min"
                 else a + (b - a) * t)   # lerp
            base[i] = base[i]._replace(weight=w)
    return base


@op("weight_cull", 1)
def _w_cull(e, p):
    """APLICADOR: vuelve el gris una decisión. soft=0 → deja los puntos con weight ≥ threshold (corte
    duro). soft=1 → los deja al azar DETERMINISTA con probabilidad = weight (densidad por máscara)."""
    thr = p.get("threshold", 0.5)
    soft = _sat(p.get("soft", 0.0))
    seed = int(p.get("seed", 0))
    out = []
    for s in e[0]:
        duro = s.weight >= thr
        blando = _rand(sc.semilla_de(seed, s.pos.x, s.pos.y)) < s.weight
        if (blando if soft >= 0.5 else duro):
            out.append(s)
    return out


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
    """Un Sample nuevo con la misma info pero otra posición (los Sample son inmutables). `_replace`
    conserva el resto de atributos, incluido el `weight` (que si no se perdería en cada transform)."""
    from .geometry import Vec3
    return s._replace(pos=Vec3(x, y, z))


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


def _sat(x: float) -> float:
    return 0.0 if x < 0.0 else (1.0 if x > 1.0 else x)


def _smoothstep(a: float, b: float, x: float) -> float:
    """El Smooth Step del shader: 0 debajo de `a`, 1 arriba de `b`, y una rampa suave (hermite) en el
    medio. Con a>b la rampa se invierte. Es el remap+clamp con bordes suaves."""
    if a == b:
        return 0.0 if x < a else 1.0
    t = _sat((x - a) / (b - a))
    return t * t * (3.0 - 2.0 * t)


# funciones disponibles en las expresiones (sin builtins peligrosos: se evalúa con __builtins__ vacío).
_FUNCS: dict = {
    "sin": _math.sin, "cos": _math.cos, "tan": _math.tan, "atan": _math.atan,
    "asin": _math.asin, "acos": _math.acos, "sqrt": _math.sqrt, "exp": _math.exp,
    "log": _math.log, "floor": _math.floor, "ceil": _math.ceil,
    "radians": _math.radians, "degrees": _math.degrees,
    "abs": abs, "min": min, "max": max, "round": round, "pow": pow,
    "clamp": lambda x, a, b: a if x < a else (b if x > b else x),
    "lerp": lambda a, b, t: a + (b - a) * t,
    "remap": lambda x, a, b, c, d: c + (d - c) * ((x - a) / (b - a)) if b != a else c,
    "rand": _rand,
    # conectores del arte técnico (los del shader de máscaras): saturate/one_minus/step/smoothstep.
    "saturate": lambda x: 0.0 if x < 0.0 else (1.0 if x > 1.0 else x),
    "one_minus": lambda x: 1.0 - x,
    "step": lambda edge, x: 0.0 if x < edge else 1.0,
    "smoothstep": _smoothstep,
}


#: Constantes con nombre, en las grafías con que la gente las escribe.
#:
#: Estaban sólo `pi` y `e` en minúscula, así que `=PI * 3` fallaba con «expresión sin resolver» y
#: nadie podía adivinar por qué. Se aceptan la mayúscula, la minúscula y el símbolo: quien viene de
#: una calculadora escribe `PI`, quien viene de Python escribe `pi`, y quien viene de un plano
#: escribe `π`. Las tres son la misma constante y ninguna es más correcta.
#:
#: ⚠️ Las variables del grafo GANAN sobre estas constantes (`ns.update(tabla)` va después), así que
#: alguien que llame `PHI` a un número suyo obtiene el suyo. Es lo correcto: lo que uno define en su
#: propio grafo manda sobre lo que trae la herramienta.
CONSTANTES: dict = {
    "PI": _math.pi, "pi": _math.pi, "π": _math.pi,
    # τ = 2π, la vuelta entera. Aparece en cualquier cuenta de circunferencia y ahorra el «* 2».
    "TAU": _math.tau, "tau": _math.tau, "τ": _math.tau,
    "E": _math.e, "e": _math.e, "EULER": _math.e, "euler": _math.e,
    # φ = (1+√5)/2, la proporción áurea. La usan los repartos en espiral —el ángulo de 137,5° que
    # ya aparece por default en `rotate_per_index` es 360°/φ².
    "PHI": (1.0 + _math.sqrt(5.0)) / 2.0, "phi": (1.0 + _math.sqrt(5.0)) / 2.0,
    "φ": (1.0 + _math.sqrt(5.0)) / 2.0,
}
_FUNCS.update(CONSTANTES)


def nombres_disponibles(tabla: dict) -> tuple[list[str], list[str], list[str]]:
    """`(variables, constantes, funciones)` que una expresión puede usar ahora mismo."""
    constantes = sorted(CONSTANTES)
    funciones = sorted(k for k in _FUNCS if k not in CONSTANTES)
    return sorted(tabla), constantes, funciones


def diagnosticar_expresion(expr, tabla: dict) -> str:
    """POR QUÉ no resolvió una expresión, con el nombre exacto y qué sí existe.

    Antes todas las fallas decían «expresión sin resolver», así que `=PI * 3` —una constante que no
    existía— y `=radioo * 2` —un nombre mal tipeado— daban el MISMO mensaje. Con eso no se puede
    saber si el error está en la idea o en una letra, que es lo único que uno necesita saber.
    """
    ns = dict(_FUNCS)
    ns.update(tabla)
    try:
        # La MISMA conversión que hace `_eval_expr`, no sólo el `eval`: sin el `float` de afuera,
        # una expresión que da un complejo —`i` sería el caso— resolvería acá y fallaría allá, y el
        # diagnóstico diría que está bien algo que no anda.
        valor = float(eval(str(expr), {"__builtins__": {}}, ns))  # noqa: S307
    except NameError as exc:
        import difflib
        nombre = str(exc).split("'")[1] if "'" in str(exc) else str(exc)
        variables, constantes, funciones = nombres_disponibles(tabla)
        # Se buscan parecidos primero entre las VARIABLES: si alguien tipeó mal un nombre suyo,
        # ofrecerle una función es ruido. Y el corte es alto (0,75) porque una sugerencia mala es
        # peor que ninguna — con 0,6, «altura» sugería «saturate», que manda a mirar otra cosa.
        cerca = (difflib.get_close_matches(nombre, variables, n=2, cutoff=0.75)
                 or difflib.get_close_matches(nombre, constantes + funciones, n=2, cutoff=0.75))
        partes = [f"no conozco «{nombre}»"]
        if cerca:
            partes.append(f"¿querías decir {' o '.join(cerca)}?")
        # El inventario va SIEMPRE, haya sugerencia o no: es la parte accionable del mensaje —qué
        # se puede usar ahora, o qué hacer si no hay nada—.
        partes.append(f"variables del grafo: {', '.join(variables)}" if variables
                      else "todavía no hay variables (agregá un nodo «number» y ponele nombre)")
        return " · ".join(partes)
    except ZeroDivisionError:
        return "división por cero"
    except SyntaxError:
        return "no se entiende como cuenta"
    except TypeError as exc:
        # El caso típico: una función con la cantidad de argumentos equivocada, o un valor que no
        # es un número real —`i` daría un complejo, y un parámetro tiene que ser un real finito—.
        return f"tipos que no se pueden operar ({exc})"
    except (ValueError, ArithmeticError) as exc:
        return f"la cuenta no da un número real ({exc})"
    if not _math.isfinite(valor):
        return "da infinito o NaN, que no sirve como valor de un parámetro"
    # Resolvió. Quien llama sólo pregunta cuando falló, así que devolver vacío es decir «acá no hay
    # nada que explicar» en vez de inventar una causa.
    return ""


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


def _es_numero(s: str) -> bool:
    try:
        float(s)
        return True
    except (TypeError, ValueError):
        return False


def _resolver_params(params: dict, tabla: dict, defaults: dict | None = None) -> dict:
    """Reemplaza cada param que sea EXPRESIÓN por su valor evaluado contra la tabla de variables:
    - «=expr»  → SIEMPRE se evalúa (explícito, sirve en cualquier campo).
    - En un campo NUMÉRICO (según `defaults`, el default del spec), un texto que NO es un número literal
      se trata como expresión también, SIN el «=» (`n*100` alcanza). Así una variable se usa igual que
      en Grasshopper, sin sintaxis extra. Los campos de TEXTO (anclas, nombres) pasan tal cual.
    Si la expresión no resuelve, el «=» cae a 0.0 y el implícito deja el literal (que coacciona al default)."""
    defaults = defaults or {}
    out = {}
    for k, v in params.items():
        if isinstance(v, str):
            s = v.strip()
            if s.startswith("="):
                r = _eval_expr(s[1:], tabla)
                out[k] = r if r is not None else 0.0
                continue
            d = defaults.get(k)
            if isinstance(d, (int, float)) and not isinstance(d, bool) and s and not _es_numero(s):
                r = _eval_expr(s, tabla)
                out[k] = r if r is not None else v
                continue
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

#: nodos de VALOR: no producen puntos; el registro compartido vive en ``jam.math_core``.


class FlowValidationError(ValueError):
    """El grafo no cumple el contrato de nodos/pines/aridad y no debe producir efectos.

    `diagnostics` conserva los errores por node id para que Slate pueda pintar exactamente el nodo
    responsable. La clave `_graph` se reserva para errores que no pertenecen a un único nodo.
    """

    def __init__(self, diagnostics: dict[str, list[str]]):
        self.diagnostics = diagnostics
        detalle = "; ".join(
            f"{nid}: {', '.join(mensajes)}" for nid, mensajes in diagnostics.items()
        )
        super().__init__(detalle or "flow inválido")


def _tipo_salida(kind: str) -> str:
    """Tipo público del pin `out`, compartido con el spec que consume Slate."""
    if kind in VALOR_KINDS:
        from .math_core import tipo_salida
        return tipo_salida(kind)
    if kind == "instance":
        return "A"
    return "P"


def _tipo_param(kind: str, pin: str) -> str | None:
    """Tipo de un pin de parámetro de Flow; None significa que el pin no existe."""
    if kind in VALOR_KINDS:
        from .math_core import tipo_param
        return tipo_param(kind, pin)
    defaults = OPS_META.get(kind, {}).get("params", {})
    if pin not in defaults:
        return None
    default = defaults[pin]
    if "spline" in pin.lower():
        return "S"
    if isinstance(default, bool):
        return "B"
    if isinstance(default, (int, float)):
        return "N"
    return "T"


class Flow:
    """Grafo de operaciones de stream, con conexión POR PIN (como Grasshopper). `nodos`: id →
    {kind, params}. `enlaces`: [(origen, origen_pin, destino, destino_pin)] en orden.

    Cada nodo tiene: un pin de salida «out» (a la derecha), un pin de entrada de stream «in» (el cable
    de puntos), y UN PIN POR PARÁMETRO a la izquierda. Cablear la salida de un `number`/`math` a un pin
    de parámetro (p.ej. `count`) ATA ese parámetro al valor de la variable — el equivalente visual de la
    expresión «=». Sólo los nodos con aridad `-1` aceptan varios cables en `in`; los demás reciben
    exactamente el número de streams declarado por su operación."""

    def __init__(self):
        self.nodos: dict[str, dict] = {}
        self.enlaces: list[tuple[str, str, str, str]] = []
        # Resultado efímero de la última evaluación. Mantiene metadata de UI fuera de `params`, para
        # no contaminar el JSON persistente con `_stats`, `_out` u otros datos del runtime.
        self.resultados: dict[str, dict] = {}

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

    def validar(self, ops: dict | None = None) -> dict[str, list[str]]:
        """Preflight puro: valida operaciones, endpoints, pines, tipos y cardinalidad.

        No llama ninguna operación ni toca Unreal. Devuelve `{node_id: [mensajes]}`; vacío significa
        que el Flow puede evaluarse. `ops` declara las implementaciones del adaptador Unreal.
        """
        tabla_fn = {**OPS, **(ops or {})}
        diagnosticos: dict[str, list[str]] = {}

        def error(nid: str, mensaje: str) -> None:
            mensajes = diagnosticos.setdefault(nid, [])
            if mensaje not in mensajes:
                mensajes.append(mensaje)

        aridades: dict[str, int | None] = {}
        for nid, nodo in self.nodos.items():
            kind = nodo.get("kind", "")
            meta = OPS_META.get(kind)
            implementacion = tabla_fn.get(kind)
            if kind in VALOR_KINDS:
                aridades[nid] = 0
            elif meta is not None:
                aridades[nid] = int(meta.get("aridad", 0 if meta.get("source") else 1))
                if implementacion is None:
                    error(nid, f"operación «{kind}» sin implementación disponible")
            elif implementacion is not None:  # compatibilidad con ops puras históricas
                aridades[nid] = int(implementacion[1])
            else:
                aridades[nid] = None
                error(nid, f"operación desconocida: «{kind}»")

        # Dos variables con el mismo nombre hacían que el orden de inserción decidiera silenciosamente.
        nombres: dict[str, str] = {}
        for nid, nodo in self.nodos.items():
            if nodo.get("kind") not in VALOR_KINDS:
                continue
            nombre = str(nodo.get("params", {}).get("name") or nid)
            anterior = nombres.get(nombre)
            if anterior is not None:
                error(anterior, f"nombre de variable duplicado: «{nombre}»")
                error(nid, f"nombre de variable duplicado: «{nombre}»")
            else:
                nombres[nombre] = nid

        streams_por_nodo = {nid: 0 for nid in self.nodos}
        params_por_pin: dict[tuple[str, str], int] = {}
        enlaces_vistos: set[tuple[str, str, str, str]] = set()
        for origen, origen_pin, destino, destino_pin in self.enlaces:
            enlace = (origen, origen_pin, destino, destino_pin)
            if enlace in enlaces_vistos:
                error(destino if destino in self.nodos else "_graph", "conexión duplicada")
                continue
            enlaces_vistos.add(enlace)

            if origen not in self.nodos:
                error(destino if destino in self.nodos else "_graph", f"origen inexistente: «{origen}»")
                continue
            if destino not in self.nodos:
                error(origen, f"destino inexistente: «{destino}»")
                continue
            if origen == destino:
                error(origen, "un nodo no puede conectarse a sí mismo")
            if origen_pin != PIN_OUT:
                error(origen, f"pin de salida desconocido: «{origen_pin}»")

            kind_origen = self.nodos[origen].get("kind", "")
            kind_destino = self.nodos[destino].get("kind", "")
            tipo_origen = _tipo_salida(kind_origen)
            if destino_pin == PIN_STREAM_IN:
                streams_por_nodo[destino] += 1
                tipo_destino = "P"
                if aridades.get(destino) == 0:
                    error(destino, "el nodo es fuente y no tiene entrada «in»")
            else:
                params_por_pin[(destino, destino_pin)] = params_por_pin.get((destino, destino_pin), 0) + 1
                tipo_destino = _tipo_param(kind_destino, destino_pin)
                if tipo_destino is None:
                    error(destino, f"pin de entrada desconocido: «{destino_pin}»")

            if tipo_destino is not None and tipo_origen != tipo_destino:
                error(origen, f"salida {tipo_origen} incompatible con {destino}.{destino_pin} ({tipo_destino})")
                error(destino, f"{destino_pin} esperaba {tipo_destino}, recibió {tipo_origen}")

        for nid, aridad in aridades.items():
            if aridad is None or aridad == 0:
                continue
            recibidas = streams_por_nodo[nid]
            if aridad == -1 and recibidas == 0:
                error(nid, "requiere al menos una conexión en «in»")
            elif aridad >= 0 and recibidas != aridad:
                error(nid, f"requiere {aridad} entrada(s) en «in»; recibió {recibidas}")

        for (nid, pin), cantidad in params_por_pin.items():
            if cantidad > 1:
                error(nid, f"el parámetro «{pin}» admite un solo cable; recibió {cantidad}")

        try:
            self.topo()
        except ValueError as exc:
            error("_graph", str(exc))

        # El preflight también resuelve los valores: dividir por cero o producir infinito es un
        # error de Compile, no algo que aparece recién al correr una herramienta.
        from .math_core import resolver
        _tabla, _por_nodo, errores_valor = resolver(
            self.nodos, self.enlaces, campo_verbo="kind", eval_expr=_eval_expr)
        for nid, mensajes in errores_valor.items():
            for mensaje in mensajes:
                error(nid, mensaje)
        return diagnosticos

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
        """Tabla por nombre, resuelta por el mismo núcleo que usa Graph."""
        return self._valores_resueltos()[0]

    def _valores_resueltos(self) -> tuple[dict, dict]:
        from .math_core import resolver
        tabla, por_nodo, _errores = resolver(
            self.nodos, self.enlaces, campo_verbo="kind", eval_expr=_eval_expr)
        return tabla, por_nodo

    def params_efectivos(self, nid: str, variables: dict, escalar_de: dict) -> dict:
        """Los params de `nid` como los ve la operación: primero se resuelven las EXPRESIONES «=»
        contra la tabla de variables, después pisa lo que llegue por CABLE a un pin de parámetro (un
        cable manda sobre el texto del campo, como en Grasshopper).

        Lo usan tanto `evaluar` como el compilador a material: si la regla viviera en dos lados, el
        material podría salir con otros números que la evaluación del mismo grafo.
        """
        nodo = self.nodos[nid]
        params = _resolver_params(nodo["params"], variables,
                                  OPS_META.get(nodo["kind"], {}).get("params"))
        for pin, origen in self._param_wires(nid).items():
            if escalar_de.get(origen) is not None:
                params[pin] = escalar_de[origen]
        return params

    def escalares_de_valor(self, variables: dict) -> dict:
        """El número que cada nodo `number`/`math` lleva por su cable a un pin de parámetro."""
        _tabla, por_nodo = self._valores_resueltos()
        return por_nodo

    def evaluar(self, ops: dict | None = None) -> dict[str, list]:
        """Corre el grafo; devuelve {id: stream}. Primero arma la tabla de variables (number/math) y con
        ella resuelve las EXPRESIONES de los params (los que empiezan con «=»). `ops` suma operaciones
        del adaptador (p.ej. `source_surface` que raycastea, o `instance` que spawnea) sin tocar esto."""
        tabla_fn = {**OPS, **(ops or {})}
        diagnosticos = self.validar(ops=ops)
        if diagnosticos:
            raise FlowValidationError(diagnosticos)
        self.resultados = {}
        variables, escalar_de = self._valores_resueltos()
        # escalar de cada nodo de valor (lo que un cable suyo lleva a un pin de parámetro).
        salida: dict[str, list] = {}
        for nid in self.topo():
            nodo = self.nodos[nid]
            kind = nodo["kind"]
            # nodos de valor: no producen puntos, aportan su número a la tabla (y lo dejan para la UI).
            if kind in VALOR_KINDS:
                nombre = str(nodo["params"].get("name") or nid)
                self.resultados[nid] = {"value": variables.get(nombre)}
                salida[nid] = []
                continue
            fn_ent = tabla_fn.get(kind)
            if fn_ent is None:
                # `validar()` lo detecta antes de ejecutar; esta guarda evita una omisión silenciosa si
                # en el futuro cambia la tabla entre preflight y evaluación.
                raise FlowValidationError({nid: [f"operación «{kind}» sin implementación disponible"]})
            fn, _n = fn_ent
            entradas = [salida.get(e, []) for e in self._entradas(nid)]
            params = self.params_efectivos(nid, variables, escalar_de)
            # El contexto del grafo, para las ops que COMPILAN la cadena en vez de consumir el stream
            # (el material de máscara lee la cadena de Weight que llega a su entrada). Las demás lo
            # ignoran, como ignoran cualquier clave que no sea suya.
            params["_flow"], params["_nid"] = self, nid
            salida[nid] = fn(entradas, params)
            resultado = {}
            if "_stats" in params:
                resultado["stats"] = params["_stats"]
            if "_out" in params:
                resultado["out"] = params["_out"]
            self.resultados[nid] = resultado
        return salida
