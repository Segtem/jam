"""Primitivas planas de la BASE COMÚN: quad, grid y disc.

Geometría calculada en el núcleo puro (cero `import unreal`), idéntica a la que Geometry Script
produce en Unreal Engine 5.8.

- `quad`: rectángulo simple (2 triángulos, 4 vértices).
- `grid`: grilla subdividida en el plano XY (columns × rows vértices).
- `disc`: disco o anillo en el plano XY; con `hole_radius` es anillo, con ángulos es porción.
"""

from __future__ import annotations

import math

from . import malla_core


def grid(*, width: float = 500.0, height: float = 500.0,
         columns: int = 6, rows: int = 6) -> malla_core.Malla:
    """Grilla plana en el plano XY centrada en el origen, subdividida columns × rows vértices.

    Normales duras hacia +Z. UV0 en [0, 1].
    """
    width, height = float(width), float(height)
    columns, rows = int(columns), int(rows)
    if not all(math.isfinite(v) and v > 0.0 for v in (width, height)):
        raise malla_core.MallaError("width y height deben ser mayores que cero.")
    if columns < 2 or rows < 2:
        raise malla_core.MallaError("columns y rows deben ser al menos 2 (cantidad de vértices).")

    nu = columns - 1
    nv = rows - 1
    x0, y0 = -width / 2.0, -height / 2.0
    v, t, n, uv = [], [], [], []
    normal = (0.0, 0.0, 1.0)

    for j in range(nv + 1):
        for i in range(nu + 1):
            fu, fv = i / nu, j / nv
            v.append((x0 + width * fu, y0 + height * fv, 0.0))
            n.append(normal)
            uv.append((fu, fv))

    for j in range(nv):
        for i in range(nu):
            p00 = j * (nu + 1) + i
            p10 = p00 + 1
            p01 = p00 + nu + 1
            p11 = p00 + nu + 2
            for tri in ((p00, p10, p11), (p00, p11, p01)):
                if malla_core._punto(malla_core.cara_frontal(v, tri), normal) < 0.0:
                    tri = (tri[0], tri[2], tri[1])
                t.append(tri)

    return malla_core.Malla(tuple(v), tuple(t), tuple(n), tuple(uv))


def quad(*, width: float = 100.0, height: float = 100.0) -> malla_core.Malla:
    """Quad plano en XY centrado en el origen (2 triángulos, 4 vértices)."""
    return grid(width=width, height=height, columns=2, rows=2)


def disc(*, radius: float = 100.0, sides: int = 24, start_angle: float = 0.0,
         end_angle: float = 360.0, hole_radius: float = 0.0) -> malla_core.Malla:
    """Disco o anillo plano en XY centrado en el origen.

    Con `hole_radius > 0` produce un anillo; con `start_angle` y `end_angle` produce una porción.
    Normales duras hacia +Z. UV0 proporcional en [0, 1] centrado en (0.5, 0.5).
    """
    radius, hole_radius = float(radius), float(hole_radius)
    start_angle, end_angle = float(start_angle), float(end_angle)
    sides = int(sides)
    if not math.isfinite(radius) or radius <= 0.0:
        raise malla_core.MallaError("radius debe ser mayor que cero.")
    if not math.isfinite(hole_radius) or hole_radius < 0.0 or hole_radius >= radius:
        raise malla_core.MallaError("hole_radius debe estar entre 0 y radius.")
    if not all(math.isfinite(v) for v in (start_angle, end_angle)) or end_angle <= start_angle:
        raise malla_core.MallaError("end_angle tiene que ser mayor que start_angle.")
    if sides < 3:
        raise malla_core.MallaError("sides debe ser al menos 3.")

    span = end_angle - start_angle
    es_cerrado = span >= 360.0 - 1e-6
    n_steps = sides if es_cerrado else max(sides - 1, 1)

    v, t, n, uv = [], [], [], []
    normal = (0.0, 0.0, 1.0)

    if hole_radius > 0.0:
        num_puntos = n_steps if es_cerrado else n_steps + 1
        for k in range(num_puntos):
            ang = start_angle + k * (span / n_steps)
            rad = math.radians(ang)
            ca, sa = math.cos(rad), math.sin(rad)
            # Vértice interior
            pi = (hole_radius * ca, hole_radius * sa, 0.0)
            v.append(pi)
            n.append(normal)
            uv.append((0.5 + 0.5 * (pi[0] / radius), 0.5 + 0.5 * (pi[1] / radius)))
            # Vértice exterior
            po = (radius * ca, radius * sa, 0.0)
            v.append(po)
            n.append(normal)
            uv.append((0.5 + 0.5 * (po[0] / radius), 0.5 + 0.5 * (po[1] / radius)))

        for k in range(n_steps):
            k_next = (k + 1) % num_puntos
            i_in, i_out = 2 * k, 2 * k + 1
            next_in, next_out = 2 * k_next, 2 * k_next + 1
            for tri in ((i_in, next_out, i_out), (i_in, next_in, next_out)):
                if malla_core._punto(malla_core.cara_frontal(v, tri), normal) < 0.0:
                    tri = (tri[0], tri[2], tri[1])
                t.append(tri)
    else:
        # Vértice central
        v.append((0.0, 0.0, 0.0))
        n.append(normal)
        uv.append((0.5, 0.5))

        num_puntos = n_steps if es_cerrado else n_steps + 1
        for k in range(num_puntos):
            ang = start_angle + k * (span / n_steps)
            rad = math.radians(ang)
            ca, sa = math.cos(rad), math.sin(rad)
            p = (radius * ca, radius * sa, 0.0)
            v.append(p)
            n.append(normal)
            uv.append((0.5 + 0.5 * ca, 0.5 + 0.5 * sa))

        for k in range(n_steps):
            k_next = (k + 1) % num_puntos
            tri = (0, 1 + k_next, 1 + k)
            if malla_core._punto(malla_core.cara_frontal(v, tri), normal) < 0.0:
                tri = (tri[0], tri[2], tri[1])
            t.append(tri)

    return malla_core.Malla(tuple(v), tuple(t), tuple(n), tuple(uv))
