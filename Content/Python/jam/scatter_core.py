"""Scatter — CEREBRO PURO (0 `import unreal`; corre en python3 pelado).

El estado del arte (Dash de PolygonFlow) no es "poné N copias": es una TUBERÍA —
    generar candidatos  →  muestrear la superficie  →  MÁSCARAS que filtran  →  variación
donde las máscaras (pendiente, altura, ruido, proximidad, densidad…) se COMPONEN. Ahí está la
riqueza de la herramienta. Todo eso es geometría y decisiones deterministas: vive acá, sin motor.

El adaptador (`jam.scatter`) hace lo único que necesita a Unreal: raycastear cada candidato contra la
superficie real para llenar el `Sample` (posición, normal, pendiente, altura) y después spawnear con
`place`. Este módulo no sabe qué es un actor.

Un `Sample` = un candidato ya muestreado: dónde cae, cómo está la superficie ahí, y su semilla propia
(para que la variación sea estable aunque se reordene la lista).
"""

from __future__ import annotations

import math
import random
from collections import namedtuple

from .geometry import Vec3

# pos: punto en la superficie · normal: normal de la superficie · slope: grados desde la horizontal
# (0 = piso plano, 90 = pared) · seed: semilla estable de esta instancia · uv: coords 0..1 en la región
# weight: máscara ESCALAR 0..1 del punto (el gris de una máscara de shader) — la escriben/combinan las
# ops de Weight y un aplicador la vuelve decisión (cull) o escala. Default 1.0 = «pasa entero».
Sample = namedtuple("Sample", "pos normal slope seed uv weight", defaults=(1.0,))


# ---------- generadores de candidatos (x,y) en una región [centro ± semi] ----------

def grid_jitter(centro, semi, cantidad, seed, jitter=0.4):
    """Grilla pareja que cubre la región, cada punto sacudido dentro de su celda. Determinista.
    Devuelve exactamente `cantidad` puntos (x,y) en orden fila×columna."""
    rng = random.Random(seed)
    cx, cy = centro
    sx, sy = semi
    aspecto = (sx / sy) if sy else 1.0
    cols = max(1, round(math.sqrt(max(1, cantidad) * aspecto)))
    filas = max(1, math.ceil(cantidad / cols))
    celda_x, celda_y = 2 * sx / cols, 2 * sy / filas
    pts = []
    for r in range(filas):
        for c in range(cols):
            if len(pts) >= cantidad:
                break
            bx = cx - sx + (c + 0.5) * celda_x
            by = cy - sy + (r + 0.5) * celda_y
            jx = rng.uniform(-jitter, jitter) * celda_x * 0.5
            jy = rng.uniform(-jitter, jitter) * celda_y * 0.5
            pts.append((bx + jx, by + jy))
    return pts


def poisson_disk(centro, semi, radio, seed, k=30, maximo=100000):
    """Muestreo por disco de Poisson (Bridson): puntos con separación mínima `radio` cm, distribución
    orgánica sin grumos ni patrón de grilla. Devuelve tantos como entren. Es lo que da un scatter que
    parece natural en vez de sembrado a máquina."""
    rng = random.Random(seed)
    cx, cy = centro
    sx, sy = semi
    if radio <= 0:
        return []
    cell = radio / math.sqrt(2)
    gw = max(1, int(math.ceil(2 * sx / cell)))
    gh = max(1, int(math.ceil(2 * sy / cell)))
    grid = [[-1] * gw for _ in range(gh)]
    pts = []
    activos = []

    def celda(p):
        gx = min(gw - 1, max(0, int((p[0] - (cx - sx)) / cell)))
        gy = min(gh - 1, max(0, int((p[1] - (cy - sy)) / cell)))
        return gx, gy

    def libre(p):
        if not (cx - sx <= p[0] <= cx + sx and cy - sy <= p[1] <= cy + sy):
            return False
        gx, gy = celda(p)
        for iy in range(max(0, gy - 2), min(gh, gy + 3)):
            for ix in range(max(0, gx - 2), min(gw, gx + 3)):
                j = grid[iy][ix]
                if j >= 0:
                    q = pts[j]
                    if (q[0] - p[0]) ** 2 + (q[1] - p[1]) ** 2 < radio * radio:
                        return False
        return True

    p0 = (rng.uniform(cx - sx, cx + sx), rng.uniform(cy - sy, cy + sy))
    pts.append(p0)
    activos.append(0)
    gx, gy = celda(p0)
    grid[gy][gx] = 0

    while activos and len(pts) < maximo:
        idx = rng.choice(activos)
        base = pts[idx]
        puesto = False
        for _ in range(k):
            ang = rng.uniform(0, 2 * math.pi)
            rad = rng.uniform(radio, 2 * radio)
            cand = (base[0] + math.cos(ang) * rad, base[1] + math.sin(ang) * rad)
            if libre(cand):
                pts.append(cand)
                activos.append(len(pts) - 1)
                gx, gy = celda(cand)
                grid[gy][gx] = len(pts) - 1
                puesto = True
                break
        if not puesto:
            activos.remove(idx)
    return pts


def hexagonal(centro, semi, paso, seed, jitter=0.0):
    """Grilla HEXAGONAL (Vector/Grid de GH): filas desfasadas media celda → empaque hexagonal. `paso`
    = separación entre centros (cm). Bueno para adoquines/mosaicos sin el patrón cuadrado obvio."""
    rng = random.Random(seed)
    cx, cy = centro
    sx, sy = semi
    dy = paso * math.sqrt(3) / 2.0
    pts = []
    fila = 0
    y = cy - sy
    while y <= cy + sy:
        offset = (paso / 2.0) if (fila % 2) else 0.0
        x = cx - sx + offset
        while x <= cx + sx:
            jx = rng.uniform(-jitter, jitter) * paso
            jy = rng.uniform(-jitter, jitter) * paso
            pts.append((x + jx, y + jy))
            x += paso
        y += dy
        fila += 1
    return pts


def triangular(centro, semi, paso, seed, jitter=0.0):
    """Grilla TRIANGULAR (Vector/Grid de GH): igual que hexagonal pero con densidad mayor; acá se
    modela como hexagonal con paso reducido (los centros triangulares equivalen a hex más denso)."""
    return hexagonal(centro, semi, paso * 0.9, seed, jitter)


def radial(centro, radio, cantidad, anillos, seed, jitter=0.0):
    """Anillos concéntricos de puntos alrededor de `centro` (el Radial Scatter de Dash)."""
    rng = random.Random(seed)
    cx, cy = centro
    pts = []
    anillos = max(1, anillos)
    por_anillo = max(1, cantidad // anillos)
    for a in range(anillos):
        r = radio * (a + 1) / anillos
        for i in range(por_anillo):
            if len(pts) >= cantidad:
                break
            ang = 2 * math.pi * i / por_anillo + rng.uniform(-jitter, jitter)
            rr = r + rng.uniform(-jitter, jitter) * radio
            pts.append((cx + math.cos(ang) * rr, cy + math.sin(ang) * rr))
    return pts


# ---------- ruido de valor 2D (para máscara de ruido y variación) ----------

def grados_pendiente(normal) -> float:
    """Grados desde la horizontal: 0 = piso plano (normal vertical), 90 = pared.

    El valor absoluto no es cosmético: un techo tiene la normal apuntando para abajo y es tan
    «plano» como el piso. Sin él, un alero mediría 180° y ninguna máscara de ángulo lo tomaría.

    Vive acá y no en el adaptador porque la usan dos: el raycast que arma los `Sample`, y el
    compilador a material, que tiene que sacar el MISMO número de la normal del vértice.
    """
    nz = max(-1.0, min(1.0, float(normal.z if hasattr(normal, "z") else normal[2])))
    return 90.0 - math.degrees(math.asin(abs(nz)))


def _hash2(ix, iy, seed):
    h = (ix * 374761393 + iy * 668265263 + seed * 2246822519) & 0xFFFFFFFF
    h = (h ^ (h >> 13)) * 1274126177 & 0xFFFFFFFF
    return ((h ^ (h >> 16)) & 0xFFFFFFFF) / 0xFFFFFFFF


def _smooth(t):
    return t * t * (3 - 2 * t)


def value_noise(x, y, freq, seed):
    """Ruido de valor en [0,1], suave, determinista. `freq` = celdas por unidad de mundo (1/cm)."""
    fx, fy = x * freq, y * freq
    ix, iy = math.floor(fx), math.floor(fy)
    tx, ty = _smooth(fx - ix), _smooth(fy - iy)
    a = _hash2(ix, iy, seed)
    b = _hash2(ix + 1, iy, seed)
    c = _hash2(ix, iy + 1, seed)
    d = _hash2(ix + 1, iy + 1, seed)
    return (a * (1 - tx) + b * tx) * (1 - ty) + (c * (1 - tx) + d * tx) * ty


# ---------- máscaras: cada una es Sample -> keep(bool). Se COMPONEN. ----------
# Devuelven closures para que `seed`/umbral queden capturados y la tubería sea una lista de callables.

def mask_slope(min_deg=0.0, max_deg=90.0):
    """Descarta lo que esté fuera del rango de pendiente (Angle Mask de Dash): p.ej. sólo en lo
    plano (0–20°) para que las cosas no queden pegadas a las paredes."""
    def m(s: Sample) -> bool:
        return min_deg - 1e-6 <= s.slope <= max_deg + 1e-6
    return m


def mask_height(min_z=-1e12, max_z=1e12):
    """Recorta por altura (Min/Max Height Mask): nada de nieve bajo cierta cota, etc."""
    def m(s: Sample) -> bool:
        return min_z - 1e-6 <= s.pos.z <= max_z + 1e-6
    return m


def mask_noise(threshold=0.5, freq_cm=0.002, seed=0, invert=False):
    """Rompe la uniformidad (Noise Mask): mantiene donde el ruido supera el umbral → claros y
    manchones en vez de un tapiz parejo. `freq_cm` en 1/cm (0.002 ≈ manchas de ~500 cm)."""
    def m(s: Sample) -> bool:
        v = value_noise(s.pos.x, s.pos.y, freq_cm, seed)
        keep = v >= threshold
        return (not keep) if invert else keep
    return m


def mask_density(keep_fraction=1.0, seed=0):
    """Add/Remove Mask: conserva una fracción al azar (estable por la semilla de cada Sample)."""
    def m(s: Sample) -> bool:
        return random.Random(s.seed ^ (seed * 2654435761)).random() < keep_fraction
    return m


def mask_circle(centro, radio, keep_inside=True):
    """Object/Proximity Mask simple: dentro o fuera de un círculo (un claro, un borde)."""
    cx, cy = centro
    r2 = radio * radio
    def m(s: Sample) -> bool:
        dentro = (s.pos.x - cx) ** 2 + (s.pos.y - cy) ** 2 <= r2
        return dentro if keep_inside else not dentro
    return m


def aplicar_mascaras(samples, mascaras):
    """Pasa los samples por la tubería de máscaras (AND de todas). Devuelve (sobreviven, descartes)."""
    viven, mueren = [], []
    for s in samples:
        if all(m(s) for m in mascaras):
            viven.append(s)
        else:
            mueren.append(s)
    return viven, mueren


# ---------- variación por instancia (escala, yaw), estable por la semilla del Sample ----------

def variacion(sample, escala=(1.0, 1.0), yaw_rango=360.0, escala_por_eje=False):
    """(escala, yaw) para una instancia, deterministas por su semilla. `escala`=(min,max) uniforme."""
    rng = random.Random(sample.seed)
    lo, hi = escala
    if escala_por_eje:
        s = (rng.uniform(lo, hi), rng.uniform(lo, hi), rng.uniform(lo, hi))
    else:
        e = rng.uniform(lo, hi)
        s = (e, e, e)
    yaw = rng.uniform(0.0, yaw_rango)
    return s, yaw


def radio_footprint(aabb):
    """Radio en planta (XY) de la caja de una malla: su «huella» para no pisarse con las vecinas.
    Es lo que convierte una separación adivinada a mano en una separación que respeta el tamaño real
    del asset — el paso que le faltaba a scatter para que el oráculo no encuentre nada clavado."""
    return math.hypot(aabb.extent.x, aabb.extent.y)


def dedup_por_radio(samples, radios, factor=1.0):
    """Elimina, greedy, los samples cuya huella se solaparía con una ya aceptada. `radios` = radio de
    footprint por sample (índice a índice). Modela cada huella como una CAJA (semilado = radio) y las
    rechaza si sus cajas se solapan en AMBOS ejes — el mismo criterio que el oráculo (AABB), no un
    círculo: dos círculos que no se tocan pueden tener AABBs que sí (vecinos en diagonal). Puro: sólo
    puntos y radios. Devuelve (aceptados, rechazados)."""
    aceptados, idx_ok, rechazados = [], [], []
    for i, s in enumerate(samples):
        ri = radios[i] * factor
        choca = False
        for k in idx_ok:
            q = samples[k]
            suma = ri + radios[k] * factor
            if abs(s.pos.x - q.pos.x) < suma and abs(s.pos.y - q.pos.y) < suma:
                choca = True
                break
        if choca:
            rechazados.append(s)
        else:
            aceptados.append(s)
            idx_ok.append(i)
    return aceptados, rechazados


def semilla_de(seed_base, x, y):
    """Semilla estable por posición (no por índice): reordenar la lista no cambia la variación."""
    ix, iy = int(round(x)), int(round(y))
    return (_hash_int(ix) ^ _hash_int(iy) ^ (seed_base * 2654435761)) & 0xFFFFFFFF


def _hash_int(n):
    n &= 0xFFFFFFFF
    n = (n ^ (n >> 16)) * 0x45d9f3b & 0xFFFFFFFF
    n = (n ^ (n >> 16)) * 0x45d9f3b & 0xFFFFFFFF
    return n ^ (n >> 16)


def repartir_o_apilar(samples, radios, *, apilar: bool):
    """Qué puntos sobreviven: los que no se pisan (repartir), o TODOS (apilar).

    El dedup por huella descarta lo que se solaparía en XY, y para un reparto plano eso es lo
    correcto: dos piezas cruzadas se ven mal y nadie las quiso ahí. Con física es exactamente al
    revés — solaparse es la CONDICIÓN para que algo se apile, y la caída resuelve el cruce
    verticalmente, que es como lo resuelve el mundo.

    Tenerlo escrito acá y no como un `if` adentro de la tool no es prolijidad: es la única regla del
    pincel que decide si el resultado es una capa o una pila, y en la primera corrida real borró 16
    de 24 piezas justo cuando se había bajado el spacing para amontonarlas.

    Devuelve (aceptados, rechazados), igual que `dedup_por_radio`.
    """
    if apilar:
        return list(samples), []
    return dedup_por_radio(samples, radios, 1.0)
