"""La malla de la BASE COMÚN: la geometría se calcula acá, igual para Unreal, Godot y Unity.

Tarea `base-comun`. Un verbo común (hoy `mesh_box`) produce una `Malla` en el núcleo, y cada motor
la vuelve suya con UNA primitiva de su adaptador —«malla desde datos»—: Unreal con
`append_buffers_to_mesh`, Godot con `ArrayMesh`, Unity con `Mesh`. Si un motor calculara la caja con
su propio código, la base no sería común: por eso el MISMO nombre corre el MISMO cálculo.

El formato es el de los buffers que ya usaban `ribbon_core` y `loft_core`: vértices partidos por
cara (una normal dura es un vértice por cara), triángulos, normal y UV0 por vértice. Es lo que come
cada motor sin traducción de topología.

El winding es el de Unreal, medido en `ribbon_core`: la cara que se dibuja es la que tiene
`(c - a) × (b - a)` hacia afuera. Acá no se deduce de la orientación de los ejes: cada triángulo se
comprueba contra la normal de su cara y se da vuelta si hace falta.

Cerebro puro: cero `import unreal`.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

Vec3 = tuple[float, float, float]


@dataclass(frozen=True)
class Malla:
    vertices: tuple[Vec3, ...]
    triangulos: tuple[tuple[int, int, int], ...]
    normales: tuple[Vec3, ...]
    uv0: tuple[tuple[float, float], ...]


class MallaError(ValueError):
    """Parámetros que no describen una malla. El mensaje dice cuál y qué vale."""


def _resta(a, b):
    return (a[0] - b[0], a[1] - b[1], a[2] - b[2])


def _cruz(a, b):
    return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0])


def _punto(a, b):
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def cara_frontal(v, tri) -> Vec3:
    """La normal de la cara que el motor DIBUJA, sin normalizar: `(c - a) × (b - a)`."""
    a, b, c = (v[i] for i in tri)
    return _cruz(_resta(c, a), _resta(b, a))


def _cara(vertices, triangulos, normales, uv0, origen, eje_u, eje_v, normal, nu, nv):
    """Una cara plana subdividida `nu × nv`, con su normal dura y UV de 0 a 1."""
    base = len(vertices)
    for j in range(nv + 1):
        for i in range(nu + 1):
            fu, fv = i / nu, j / nv
            vertices.append(tuple(origen[k] + eje_u[k] * fu + eje_v[k] * fv for k in range(3)))
            normales.append(normal)
            uv0.append((fu, fv))
    for j in range(nv):
        for i in range(nu):
            p00 = base + j * (nu + 1) + i
            p10, p01, p11 = p00 + 1, p00 + nu + 1, p00 + nu + 2
            for tri in ((p00, p10, p11), (p00, p11, p01)):
                if _punto(cara_frontal(vertices, tri), normal) < 0.0:
                    tri = (tri[0], tri[2], tri[1])
                triangulos.append(tri)


def caja(*, size_x: float = 100.0, size_y: float = 100.0, size_z: float = 100.0,
         steps_x: int = 0, steps_y: int = 0, steps_z: int = 0) -> Malla:
    """Caja con el pivote en la BASE (apoya sola): x e y centrados, z de 0 a `size_z`.

    `steps_*` son como en `AppendBox` de Geometry Script: VÉRTICES por arista, no cortes. 0, 1 y 2
    dan un solo segmento; 3, dos; 4, tres (`segmentos = max(steps, 2) - 1`). Medido contra el motor
    en `tools/experiments/verifica_caja_comun_58.py`; la primera versión suponía cortes y daba 104
    triángulos donde el motor da 20.
    """
    sx, sy, sz = float(size_x), float(size_y), float(size_z)
    if not all(math.isfinite(v) and v > 0.0 for v in (sx, sy, sz)):
        raise MallaError("size_x/y/z deben ser mayores que cero.")
    if min(int(steps_x), int(steps_y), int(steps_z)) < 0:
        raise MallaError("steps_x/y/z no pueden ser negativos.")
    nx, ny, nz = (max(int(p), 2) - 1 for p in (steps_x, steps_y, steps_z))
    x0, y0 = -sx / 2.0, -sy / 2.0
    v, t, n, uv = [], [], [], []
    # (origen, eje_u, eje_v, normal, nu, nv) de cada una de las seis caras
    for cara in (
        ((x0, y0, 0.0), (sx, 0, 0), (0, sy, 0), (0.0, 0.0, -1.0), nx, ny),   # base
        ((x0, y0, sz), (sx, 0, 0), (0, sy, 0), (0.0, 0.0, 1.0), nx, ny),     # tapa
        ((x0, y0, 0.0), (sx, 0, 0), (0, 0, sz), (0.0, -1.0, 0.0), nx, nz),   # -Y
        ((x0, -y0, 0.0), (sx, 0, 0), (0, 0, sz), (0.0, 1.0, 0.0), nx, nz),   # +Y
        ((x0, y0, 0.0), (0, sy, 0), (0, 0, sz), (-1.0, 0.0, 0.0), ny, nz),   # -X
        ((-x0, y0, 0.0), (0, sy, 0), (0, 0, sz), (1.0, 0.0, 0.0), ny, nz),   # +X
    ):
        _cara(v, t, n, uv, *cara)
    return Malla(tuple(v), tuple(t), tuple(n), tuple(uv))


# ---------------------------------------------------------------- hechos

def hechos(m: Malla) -> dict:
    """Lo que se compara entre motores —y lo que juzga Oracle—: no la cuenta de vértices, que cada
    motor parte distinto (Geometry Script comparte los de una arista dura; un buffer los repite),
    sino triángulos, posiciones distintas, caja envolvente y área, redondeados a 0,001 cm."""
    posiciones = {tuple(round(c, 3) for c in p) for p in m.vertices}
    area = sum(math.sqrt(_punto(c, c)) / 2.0 for c in (cara_frontal(m.vertices, tri)
                                                        for tri in m.triangulos))
    xs, ys, zs = zip(*m.vertices) if m.vertices else ((0.0,), (0.0,), (0.0,))
    return {"triangulos": len(m.triangulos), "posiciones": len(posiciones),
            "min": [round(min(xs), 3), round(min(ys), 3), round(min(zs), 3)],
            "max": [round(max(xs), 3), round(max(ys), 3), round(max(zs), 3)],
            "area": round(area, 3)}


def info(m: Malla) -> str:
    h = hechos(m)
    dx, dy, dz = (h["max"][i] - h["min"][i] for i in range(3))
    return f"{h['triangulos']} triángulos · {h['posiciones']} vértices · {dx:g}×{dy:g}×{dz:g}cm"


def a_dict(m: Malla) -> dict:
    """La malla como JSON: lo que viaja por el contrato hasta el adaptador de un motor."""
    return {"vertices": [list(p) for p in m.vertices], "triangulos": [list(t) for t in m.triangulos],
            "normales": [list(p) for p in m.normales], "uv0": [list(p) for p in m.uv0]}
