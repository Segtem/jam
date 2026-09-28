"""Primitivas de revolución de la BASE COMÚN: cilindro, cono y esfera.

Tarea `base-comun`. La geometría se calcula acá en el núcleo (puro, cero `import unreal`)
y cada motor la materializa con su primitiva «malla desde datos».

Normales duras en tapas y caras planas; normales suaves en paredes cilíndricas/cónicas y esferas.
UV0 de 0 a 1 razonable para texturado.

El winding sigue la convención de Unreal: la cara frontal dibujada es (c - a) × (b - a).
"""

from __future__ import annotations

import math

from . import malla_core


def cilindro(
    *,
    radius: float = 50.0,
    height: float = 200.0,
    sides: int = 16,
    height_steps: int = 1,
    capped: bool = True,
) -> malla_core.Malla:
    """Cilindro con pivote en la BASE (apoya solo): x e y centrados, z de 0 a `height`.

    `height_steps` sigue a Geometry Script: 0 da 1 segmento de altura, 1 da 2, etc.
    (`segmentos_altura = height_steps + 1`).
    """
    try:
        r, h = float(radius), float(height)
        s, hs = int(sides), int(height_steps)
    except (TypeError, ValueError, OverflowError):
        raise malla_core.MallaError("parámetros de tipo inválido.") from None

    if not all(math.isfinite(v) and v > 0.0 for v in (r, h)):
        raise malla_core.MallaError("radius y height deben ser mayores que cero.")
    if s < 3 or hs < 0:
        raise malla_core.MallaError("sides debe ser al menos 3 y height_steps no puede ser negativo.")

    n_seg = hs + 1
    dz = h / n_seg
    v, t, n, uv = [], [], [], []

    # Costado (pared cilíndrica con normales suaves)
    base_costado = len(v)
    for k in range(n_seg + 1):
        z = k * dz
        fv = k / n_seg
        for i in range(s + 1):
            fu = i / s
            th = 2.0 * math.pi * (i % s) / s
            cos_th, sin_th = math.cos(th), math.sin(th)
            v.append((r * cos_th, r * sin_th, z))
            n.append((cos_th, sin_th, 0.0))
            uv.append((fu, fv))

    for k in range(n_seg):
        for i in range(s):
            p00 = base_costado + k * (s + 1) + i
            p10 = p00 + 1
            p01 = base_costado + (k + 1) * (s + 1) + i
            p11 = p01 + 1
            th_mid = 2.0 * math.pi * (i + 0.5) / s
            n_esp = (math.cos(th_mid), math.sin(th_mid), 0.0)
            for tri in ((p01, p10, p00), (p10, p01, p11)):
                if malla_core._punto(malla_core.cara_frontal(v, tri), n_esp) < 0.0:
                    tri = (tri[0], tri[2], tri[1])
                t.append(tri)

    if capped:
        # Tapa inferior (z = 0, normal dura hacia abajo (0, 0, -1))
        c0_idx = len(v)
        v.append((0.0, 0.0, 0.0))
        n.append((0.0, 0.0, -1.0))
        uv.append((0.5, 0.5))
        base_tapa0 = len(v)
        for i in range(s):
            th = 2.0 * math.pi * i / s
            cos_th, sin_th = math.cos(th), math.sin(th)
            v.append((r * cos_th, r * sin_th, 0.0))
            n.append((0.0, 0.0, -1.0))
            uv.append((0.5 + 0.5 * cos_th, 0.5 + 0.5 * sin_th))
        for i in range(s):
            i1 = (i + 1) % s
            tri = (base_tapa0 + i1, c0_idx, base_tapa0 + i)
            if malla_core._punto(malla_core.cara_frontal(v, tri), (0.0, 0.0, -1.0)) < 0.0:
                tri = (tri[0], tri[2], tri[1])
            t.append(tri)

        # Tapa superior (z = height, normal dura hacia arriba (0, 0, 1))
        c1_idx = len(v)
        v.append((0.0, 0.0, h))
        n.append((0.0, 0.0, 1.0))
        uv.append((0.5, 0.5))
        base_tapa1 = len(v)
        for i in range(s):
            th = 2.0 * math.pi * i / s
            cos_th, sin_th = math.cos(th), math.sin(th)
            v.append((r * cos_th, r * sin_th, h))
            n.append((0.0, 0.0, 1.0))
            uv.append((0.5 + 0.5 * cos_th, 0.5 + 0.5 * sin_th))
        for i in range(s):
            i1 = (i + 1) % s
            tri = (base_tapa1 + i, c1_idx, base_tapa1 + i1)
            if malla_core._punto(malla_core.cara_frontal(v, tri), (0.0, 0.0, 1.0)) < 0.0:
                tri = (tri[0], tri[2], tri[1])
            t.append(tri)

    return malla_core.Malla(tuple(v), tuple(t), tuple(n), tuple(uv))


def cono(
    *,
    base_radius: float = 60.0,
    top_radius: float = 0.0,
    height: float = 200.0,
    sides: int = 16,
    height_steps: int = 4,
    capped: bool = True,
) -> malla_core.Malla:
    """Cono o tronco de cono con pivote en la BASE: x e y centrados, z de 0 a `height`.

    Reproduce la topología de `AppendCone` de Geometry Script:
    `segmentos_altura = height_steps + 1`. Cuando `top_radius == 0.0`, el motor genera
    los quads con vértices coincidentes en el ápice y tapa superior degenerada si `capped=True`.
    """
    try:
        br, tr, h = float(base_radius), float(top_radius), float(height)
        s, hs = int(sides), int(height_steps)
    except (TypeError, ValueError, OverflowError):
        raise malla_core.MallaError("parámetros de tipo inválido.") from None

    if not all(math.isfinite(v) for v in (br, tr, h)) or br <= 0.0 or tr < 0.0 or h <= 0.0:
        raise malla_core.MallaError("base_radius/height deben ser positivos y top_radius no puede ser negativo.")
    if s < 3 or hs < 1:
        raise malla_core.MallaError("sides debe ser al menos 3 y height_steps al menos 1.")

    n_seg = hs + 1
    dz = h / n_seg
    dr = (tr - br) / n_seg
    slope = (br - tr) / h
    hyp = math.hypot(1.0, slope)
    nz_wall = slope / hyp
    nr_wall = 1.0 / hyp

    v, t, n, uv = [], [], [], []

    # Costado cónico con normales suaves
    base_costado = len(v)
    for k in range(n_seg + 1):
        z = k * dz
        r = br + k * dr
        fv = k / n_seg
        for i in range(s + 1):
            fu = i / s
            th = 2.0 * math.pi * (i % s) / s
            cos_th, sin_th = math.cos(th), math.sin(th)
            v.append((r * cos_th, r * sin_th, z))
            n.append((nr_wall * cos_th, nr_wall * sin_th, nz_wall))
            uv.append((fu, fv))

    for k in range(n_seg):
        for i in range(s):
            p00 = base_costado + k * (s + 1) + i
            p10 = p00 + 1
            p01 = base_costado + (k + 1) * (s + 1) + i
            p11 = p01 + 1
            th_mid = 2.0 * math.pi * (i + 0.5) / s
            n_esp = (nr_wall * math.cos(th_mid), nr_wall * math.sin(th_mid), nz_wall)
            for tri in ((p01, p10, p00), (p10, p01, p11)):
                if malla_core._punto(malla_core.cara_frontal(v, tri), n_esp) < 0.0:
                    tri = (tri[0], tri[2], tri[1])
                t.append(tri)

    if capped:
        # Tapa inferior (z = 0, normal dura hacia abajo (0, 0, -1))
        c0_idx = len(v)
        v.append((0.0, 0.0, 0.0))
        n.append((0.0, 0.0, -1.0))
        uv.append((0.5, 0.5))
        base_tapa0 = len(v)
        for i in range(s):
            th = 2.0 * math.pi * i / s
            cos_th, sin_th = math.cos(th), math.sin(th)
            v.append((br * cos_th, br * sin_th, 0.0))
            n.append((0.0, 0.0, -1.0))
            uv.append((0.5 + 0.5 * cos_th, 0.5 + 0.5 * sin_th))
        for i in range(s):
            i1 = (i + 1) % s
            tri = (base_tapa0 + i1, c0_idx, base_tapa0 + i)
            if malla_core._punto(malla_core.cara_frontal(v, tri), (0.0, 0.0, -1.0)) < 0.0:
                tri = (tri[0], tri[2], tri[1])
            t.append(tri)

        # Tapa superior (z = height, normal dura hacia arriba (0, 0, 1))
        c1_idx = len(v)
        v.append((0.0, 0.0, h))
        n.append((0.0, 0.0, 1.0))
        uv.append((0.5, 0.5))
        base_tapa1 = len(v)
        for i in range(s):
            th = 2.0 * math.pi * i / s
            cos_th, sin_th = math.cos(th), math.sin(th)
            v.append((tr * cos_th, tr * sin_th, h))
            n.append((0.0, 0.0, 1.0))
            if tr > 0.0:
                uv.append((0.5 + 0.5 * cos_th, 0.5 + 0.5 * sin_th))
            else:
                uv.append((0.5, 0.5))
        for i in range(s):
            i1 = (i + 1) % s
            tri = (base_tapa1 + i, c1_idx, base_tapa1 + i1)
            if malla_core._punto(malla_core.cara_frontal(v, tri), (0.0, 0.0, 1.0)) < 0.0:
                tri = (tri[0], tri[2], tri[1])
            t.append(tri)

    return malla_core.Malla(tuple(v), tuple(t), tuple(n), tuple(uv))


def esfera(
    *,
    radius: float = 100.0,
    latitude_steps: int = 8,
    longitude_steps: int = 12,
) -> malla_core.Malla:
    """Esfera lat/long centrada en el origen con normales suaves.

    `latitude_steps` cuenta niveles de latitud de polo a polo (mínimo 4).
    `longitude_steps` cuenta sectores longitudinales (mínimo 4).
    """
    try:
        r = float(radius)
        lat_steps, lon_steps = int(latitude_steps), int(longitude_steps)
    except (TypeError, ValueError, OverflowError):
        raise malla_core.MallaError("parámetros de tipo inválido.") from None

    if not math.isfinite(r) or r <= 0.0:
        raise malla_core.MallaError("radius debe ser mayor que cero.")
    if lat_steps < 4 or lon_steps < 4:
        raise malla_core.MallaError("latitude_steps y longitude_steps deben ser al menos 4.")

    n_lat = lat_steps - 1
    n_lon = lon_steps
    v, t, n, uv = [], [], [], []

    # Cuadrícula de vértices (n_lat + 1) × (n_lon + 1) para costura UV continua en 0..1
    for k in range(n_lat + 1):
        phi = -math.pi / 2.0 + k * (math.pi / n_lat)
        z = r * math.sin(phi)
        rk = r * math.cos(phi)
        fv = k / n_lat
        for i in range(n_lon + 1):
            fu = i / n_lon
            th = 2.0 * math.pi * (i % n_lon) / n_lon
            cos_th, sin_th = math.cos(th), math.sin(th)
            x = rk * cos_th
            y = rk * sin_th
            v.append((x, y, z))
            if k == 0:
                n.append((0.0, 0.0, -1.0))
            elif k == n_lat:
                n.append((0.0, 0.0, 1.0))
            else:
                n.append((x / r, y / r, z / r))
            uv.append((fu, fv))

    # Casquete polo sur
    for i in range(n_lon):
        p_sur = i
        p0 = (n_lon + 1) + i
        p1 = p0 + 1
        tri = (p0, p1, p_sur)
        mid_th = 2.0 * math.pi * (i + 0.5) / n_lon
        mid_phi = -math.pi / 2.0 + 0.5 * (math.pi / n_lat)
        n_esp = (math.cos(mid_phi) * math.cos(mid_th), math.cos(mid_phi) * math.sin(mid_th), math.sin(mid_phi))
        if malla_core._punto(malla_core.cara_frontal(v, tri), n_esp) < 0.0:
            tri = (tri[0], tri[2], tri[1])
        t.append(tri)

    # Bandas intermedias de quads
    for k in range(1, n_lat - 1):
        for i in range(n_lon):
            p00 = k * (n_lon + 1) + i
            p10 = p00 + 1
            p01 = (k + 1) * (n_lon + 1) + i
            p11 = p01 + 1
            mid_th = 2.0 * math.pi * (i + 0.5) / n_lon
            mid_phi = -math.pi / 2.0 + (k + 0.5) * (math.pi / n_lat)
            n_esp = (math.cos(mid_phi) * math.cos(mid_th), math.cos(mid_phi) * math.sin(mid_th), math.sin(mid_phi))
            for tri in ((p01, p11, p10), (p10, p00, p01)):
                if malla_core._punto(malla_core.cara_frontal(v, tri), n_esp) < 0.0:
                    tri = (tri[0], tri[2], tri[1])
                t.append(tri)

    # Casquete polo norte
    for i in range(n_lon):
        p_norte = n_lat * (n_lon + 1) + i
        p0 = (n_lat - 1) * (n_lon + 1) + i
        p1 = p0 + 1
        tri = (p0, p_norte, p1)
        mid_th = 2.0 * math.pi * (i + 0.5) / n_lon
        mid_phi = math.pi / 2.0 - 0.5 * (math.pi / n_lat)
        n_esp = (math.cos(mid_phi) * math.cos(mid_th), math.cos(mid_phi) * math.sin(mid_th), math.sin(mid_phi))
        if malla_core._punto(malla_core.cara_frontal(v, tri), n_esp) < 0.0:
            tri = (tri[0], tri[2], tri[1])
        t.append(tri)

    return malla_core.Malla(tuple(v), tuple(t), tuple(n), tuple(uv))
