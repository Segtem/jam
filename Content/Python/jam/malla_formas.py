"""Primitivas de formas de la BASE COMÚN: triángulo, cápsula, toro, rectángulo
redondeado, escalera lineal, escalera curva y esfera de topología cúbica.

Tarea `base-comun`. La geometría se calcula acá en el núcleo puro (sin dependencias del motor)
y cada motor la materializa con su primitiva «malla desde datos».

Normales duras en caras planas y facetadas; normales suaves en superficies continuas
(cápsula, toro, esfera de caja). UV0 razonable en [0, 1].

El winding sigue la convención de Unreal: la cara frontal que se dibuja tiene (c - a) × (b - a).
"""

from __future__ import annotations

import math

from . import malla_core


def triangulo(*, size: float = 100.0) -> malla_core.Malla:
    """Triángulo equilátero en el plano XY centrado en el baricentro con normal hacia +Z."""
    try:
        s = float(size)
    except (TypeError, ValueError, OverflowError):
        raise malla_core.MallaError("parámetros de tipo inválido.") from None

    if not math.isfinite(s) or s <= 0.0:
        raise malla_core.MallaError("size debe ser mayor que cero.")

    height = math.sqrt(3.0) * s * 0.5
    # Puntos según la convención de Geometry Script (append_triangulated_polygon):
    p0 = (-s * 0.5, -height / 3.0, 0.0)
    p1 = (s * 0.5, -height / 3.0, 0.0)
    p2 = (0.0, height * 2.0 / 3.0, 0.0)

    normal = (0.0, 0.0, 1.0)
    tri = (1, 0, 2)
    v = (p0, p1, p2)
    n = (normal, normal, normal)
    uv = ((0.0, 0.0), (1.0, 0.0), (0.5, 1.0))

    if malla_core._punto(malla_core.cara_frontal(v, tri), normal) < 0.0:
        tri = (tri[0], tri[2], tri[1])

    return malla_core.Malla(v, (tri,), n, uv)


def capsula(
    *,
    radius: float = 30.0,
    length: float = 150.0,
    hemisphere_steps: int = 5,
    sides: int = 12,
) -> malla_core.Malla:
    """Cápsula (cilindro con dos casquetes semiesféricos) con pivote en la BASE (z = 0 a 2*r + length)."""
    try:
        r, l = float(radius), float(length)
        hs, s = int(hemisphere_steps), int(sides)
    except (TypeError, ValueError, OverflowError):
        raise malla_core.MallaError("parámetros de tipo inválido.") from None

    if not all(math.isfinite(v) for v in (r, l)) or r <= 0.0 or l < 0.0:
        raise malla_core.MallaError("radius debe ser mayor que cero y length no puede ser negativo.")
    if hs < 1 or s < 3:
        raise malla_core.MallaError("hemisphere_steps al menos 1 y sides al menos 3.")

    n_hemi = max(1, hs - 1)
    v, t, n, uv = [], [], [], []

    # Construir niveles de latitud de arriba (polo norte) hacia abajo (polo sur):
    # Cada nivel: (z, r_nivel, nz, nr)
    niveles = []
    # 1. Polo norte:
    niveles.append(((2.0 * r + l), 0.0, 1.0, 0.0))
    # 2. Hemisferio superior (excluyendo polo norte, hasta ecuador superior):
    for k in range(1, n_hemi + 1):
        phi = k * (0.5 * math.pi) / n_hemi
        z = (r + l) + r * math.cos(phi)
        rk = r * math.sin(phi)
        niveles.append((z, rk, math.cos(phi), math.sin(phi)))
    # 3. Ecuador inferior del cilindro:
    niveles.append((r, r, 0.0, 1.0))
    # 4. Hemisferio inferior:
    for k in range(1, n_hemi):
        phi = k * (0.5 * math.pi) / n_hemi
        z = r - r * math.sin(phi)
        rk = r * math.cos(phi)
        niveles.append((z, rk, -math.sin(phi), math.cos(phi)))
    # 5. Polo sur:
    niveles.append((0.0, 0.0, -1.0, 0.0))

    nivel_indices = []
    altura_total = 2.0 * r + l
    for z, rk, nz, nr in niveles:
        if rk < 1e-9:
            idx = len(v)
            v.append((0.0, 0.0, z))
            n.append((0.0, 0.0, nz))
            uv.append((0.5, 0.0 if z > r else 1.0))
            nivel_indices.append([idx])
        else:
            indices = []
            fv = (altura_total - z) / altura_total
            for i in range(s):
                th = 2.0 * math.pi * i / s
                cos_th, sin_th = math.cos(th), math.sin(th)
                idx = len(v)
                v.append((rk * cos_th, rk * sin_th, z))
                n.append((nr * cos_th, nr * sin_th, nz))
                uv.append((i / s, fv))
                indices.append(idx)
            nivel_indices.append(indices)

    for k in range(len(niveles) - 1):
        top_idx = nivel_indices[k]
        bot_idx = nivel_indices[k + 1]
        if len(top_idx) == 1:
            # Abanico desde polo norte
            p_pole = top_idx[0]
            for i in range(s):
                i_next = (i + 1) % s
                tri = (p_pole, bot_idx[i_next], bot_idx[i])
                th_mid = 2.0 * math.pi * (i + 0.5) / s
                n_esp = (math.cos(th_mid), math.sin(th_mid), 1.0)
                if malla_core._punto(malla_core.cara_frontal(v, tri), n_esp) < 0.0:
                    tri = (tri[0], tri[2], tri[1])
                t.append(tri)
        elif len(bot_idx) == 1:
            # Abanico hacia polo sur
            p_pole = bot_idx[0]
            for i in range(s):
                i_next = (i + 1) % s
                tri = (top_idx[i], top_idx[i_next], p_pole)
                th_mid = 2.0 * math.pi * (i + 0.5) / s
                n_esp = (math.cos(th_mid), math.sin(th_mid), -1.0)
                if malla_core._punto(malla_core.cara_frontal(v, tri), n_esp) < 0.0:
                    tri = (tri[0], tri[2], tri[1])
                t.append(tri)
        else:
            # Banda de quads con diagonal top_0 -> bot_1
            for i in range(s):
                i_next = (i + 1) % s
                p_top_0 = top_idx[i]
                p_top_1 = top_idx[i_next]
                p_bot_0 = bot_idx[i]
                p_bot_1 = bot_idx[i_next]
                tri1 = (p_top_0, p_top_1, p_bot_1)
                tri2 = (p_bot_1, p_bot_0, p_top_0)
                th_mid = 2.0 * math.pi * (i + 0.5) / s
                n_esp = (math.cos(th_mid), math.sin(th_mid), 0.0)
                for tri in (tri1, tri2):
                    if malla_core._punto(malla_core.cara_frontal(v, tri), n_esp) < 0.0:
                        tri = (tri[0], tri[2], tri[1])
                    t.append(tri)

    return malla_core.Malla(tuple(v), tuple(t), tuple(n), tuple(uv))


def toro(
    *,
    major_radius: float = 100.0,
    minor_radius: float = 25.0,
    major_steps: int = 24,
    minor_steps: int = 12,
) -> malla_core.Malla:
    """Toro centrado en el origen en el plano XY con normales suaves."""
    try:
        R, r = float(major_radius), float(minor_radius)
        ms, ns = int(major_steps), int(minor_steps)
    except (TypeError, ValueError, OverflowError):
        raise malla_core.MallaError("parámetros de tipo inválido.") from None

    if not all(math.isfinite(v) and v > 0.0 for v in (R, r)):
        raise malla_core.MallaError("major_radius y minor_radius deben ser mayores que cero.")
    if r >= R:
        raise malla_core.MallaError("minor_radius tiene que ser menor que major_radius o el toro se cierra.")
    if ms < 3 or ns < 3:
        raise malla_core.MallaError("major_steps y minor_steps deben ser al menos 3.")

    v, t, n, uv = [], [], [], []
    grid = []
    for i in range(ms):
        th = 2.0 * math.pi * i / ms
        cos_th, sin_th = math.cos(th), math.sin(th)
        fila = []
        for j in range(ns):
            phi = 2.0 * math.pi * j / ns
            cos_phi, sin_phi = math.cos(phi), math.sin(phi)
            x_rel = R + r * cos_phi
            x = x_rel * cos_th
            y = x_rel * sin_th
            z = r * sin_phi
            nx = cos_phi * cos_th
            ny = cos_phi * sin_th
            nz = sin_phi
            idx = len(v)
            v.append((x, y, z))
            n.append((nx, ny, nz))
            uv.append((i / ms, j / ns))
            fila.append(idx)
        grid.append(fila)

    for i in range(ms):
        i_next = (i + 1) % ms
        for j in range(ns):
            j_next = (j + 1) % ns
            p00 = grid[i][j]
            p01 = grid[i][j_next]
            p10 = grid[i_next][j]
            p11 = grid[i_next][j_next]

            # Diagonal coincidente con Geometry Script: (p01 - p10)
            tri1 = (p00, p10, p01)
            tri2 = (p10, p11, p01)

            th_mid = 2.0 * math.pi * (i + 0.5) / ms
            phi_mid = 2.0 * math.pi * (j + 0.5) / ns
            n_esp = (
                math.cos(phi_mid) * math.cos(th_mid),
                math.cos(phi_mid) * math.sin(th_mid),
                math.sin(phi_mid),
            )
            for tri in (tri1, tri2):
                if malla_core._punto(malla_core.cara_frontal(v, tri), n_esp) < 0.0:
                    tri = (tri[0], tri[2], tri[1])
                t.append(tri)

    return malla_core.Malla(tuple(v), tuple(t), tuple(n), tuple(uv))


def rect_redondeado(
    *,
    size_x: float = 200.0,
    size_y: float = 200.0,
    corner_radius: float = 20.0,
    steps_round: int = 6,
) -> malla_core.Malla:
    """Rectángulo redondeado plano en XY centrado en el origen con normal hacia +Z.

    Sigue la convención de `AppendRoundRectangleXY` de Geometry Script: `size_x` y `size_y`
    definen el rectángulo interior y las 4 esquinas circulares de radio `corner_radius` se
    ubican en (±size_x/2, ±size_y/2), extendiendo las dimensiones totales a (size_x + 2*r, size_y + 2*r).
    """
    try:
        sx, sy, cr = float(size_x), float(size_y), float(corner_radius)
        sr = int(steps_round)
    except (TypeError, ValueError, OverflowError):
        raise malla_core.MallaError("parámetros de tipo inválido.") from None

    if not all(math.isfinite(v) and v > 0.0 for v in (sx, sy)):
        raise malla_core.MallaError("size_x y size_y deben ser mayores que cero.")
    if not math.isfinite(cr) or cr <= 0.0 or cr > min(sx, sy) / 2.0:
        raise malla_core.MallaError("corner_radius debe caber en la mitad del lado más corto.")
    if sr < 1:
        raise malla_core.MallaError("steps_round debe ser al menos 1.")

    cx = sx / 2.0
    cy = sy / 2.0
    r = cr
    n_seg = max(sr, 3) + 1

    v, t, n, uv = [], [], [], []
    normal = (0.0, 0.0, 1.0)
    w_tot = sx + 2.0 * r
    h_tot = sy + 2.0 * r

    def add_quad(p00, p10, p11, p01):
        idx_base = len(v)
        for p in (p00, p10, p11, p01):
            v.append((p[0], p[1], 0.0))
            n.append(normal)
            uv.append(((p[0] + cx + r) / w_tot, (p[1] + cy + r) / h_tot))
        tri1 = (idx_base, idx_base + 1, idx_base + 2)
        tri2 = (idx_base, idx_base + 2, idx_base + 3)
        for tri in (tri1, tri2):
            if malla_core._punto(malla_core.cara_frontal(v, tri), normal) < 0.0:
                tri = (tri[0], tri[2], tri[1])
            t.append(tri)

    # 1. Centro: [-cx, cx] x [-cy, cy]
    add_quad((-cx, -cy), (cx, -cy), (cx, cy), (-cx, cy))
    # 2. Lado -X
    add_quad((-cx - r, -cy), (-cx, -cy), (-cx, cy), (-cx - r, cy))
    # 3. Lado +X
    add_quad((cx, -cy), (cx + r, -cy), (cx + r, cy), (cx, cy))
    # 4. Lado -Y
    add_quad((-cx, -cy - r), (cx, -cy - r), (cx, -cy), (-cx, -cy))
    # 5. Lado +Y
    add_quad((-cx, cy), (cx, cy), (cx, cy + r), (-cx, cy + r))

    # 4 esquinas en abanico
    esquinas = [
        ((-cx, -cy), 1.5 * math.pi, math.pi),
        ((-cx, cy), math.pi, 0.5 * math.pi),
        ((cx, -cy), 1.5 * math.pi, 2.0 * math.pi),
        ((cx, cy), 0.0, 0.5 * math.pi),
    ]
    for (center_x, center_y), a_start, a_end in esquinas:
        c_idx = len(v)
        v.append((center_x, center_y, 0.0))
        n.append(normal)
        uv.append(((center_x + cx + r) / w_tot, (center_y + cy + r) / h_tot))

        arc_pts = []
        for s in range(n_seg + 1):
            ang = a_start + s * (a_end - a_start) / n_seg
            px = center_x + r * math.cos(ang)
            py = center_y + r * math.sin(ang)
            idx = len(v)
            v.append((px, py, 0.0))
            n.append(normal)
            uv.append(((px + cx + r) / w_tot, (py + cy + r) / h_tot))
            arc_pts.append(idx)

        for s in range(n_seg):
            tri = (c_idx, arc_pts[s], arc_pts[s + 1])
            if malla_core._punto(malla_core.cara_frontal(v, tri), normal) < 0.0:
                tri = (tri[0], tri[2], tri[1])
            t.append(tri)

    return malla_core.Malla(tuple(v), tuple(t), tuple(n), tuple(uv))


def escalera(
    *,
    step_width: float = 150.0,
    step_height: float = 18.0,
    step_depth: float = 28.0,
    steps: int = 10,
    floating: bool = False,
) -> malla_core.Malla:
    """Escalera recta alineada en +X con normales duras por cara."""
    try:
        sw, sh, sd = float(step_width), float(step_height), float(step_depth)
        st = int(steps)
        fl = bool(floating)
    except (TypeError, ValueError, OverflowError):
        raise malla_core.MallaError("parámetros de tipo inválido.") from None

    if not all(math.isfinite(v) and v > 0.0 for v in (sw, sh, sd)):
        raise malla_core.MallaError("step_width/height/depth deben ser mayores que cero.")
    if st < 1 or st > 256:
        raise malla_core.MallaError("steps debe estar entre 1 y 256.")

    v, t, n, uv = [], [], [], []
    y0 = -sw / 2.0
    y1 = sw / 2.0
    total_x = st * sd
    total_z = st * sh

    def add_tri(p1, p2, p3, normal):
        idx_base = len(v)
        for p in (p1, p2, p3):
            v.append(p)
            n.append(normal)
            uv.append(((p[0] / total_x) if total_x > 0 else 0.0,
                       (p[2] / total_z) if total_z > 0 else 0.0))
        tri = (idx_base, idx_base + 1, idx_base + 2)
        if malla_core._punto(malla_core.cara_frontal(v, tri), normal) < 0.0:
            tri = (tri[0], tri[2], tri[1])
        t.append(tri)

    def add_quad(p00, p10, p11, p01, normal):
        add_tri(p00, p10, p11, normal)
        add_tri(p00, p11, p01, normal)

    def add_quad_trasera(x, z_a, z_b):
        add_tri((x, y1, z_a), (x, y0, z_a), (x, y0, z_b), (1.0, 0.0, 0.0))
        add_tri((x, y0, z_b), (x, y1, z_b), (x, y1, z_a), (1.0, 0.0, 0.0))

    def add_quad_fondo(x_a, x_b, z):
        add_tri((x_a, y1, z), (x_a, y0, z), (x_b, y0, z), (0.0, 0.0, -1.0))
        add_tri((x_b, y0, z), (x_b, y1, z), (x_a, y1, z), (0.0, 0.0, -1.0))

    if not fl:
        # Huellas (+Z)
        for k in range(st):
            x_a = k * sd
            x_b = (k + 1) * sd
            z = (k + 1) * sh
            add_quad((x_a, y0, z), (x_b, y0, z), (x_b, y1, z), (x_a, y1, z), (0.0, 0.0, 1.0))

        # Contrahuellas (-X)
        for k in range(st):
            x = k * sd
            z_a = k * sh
            z_b = (k + 1) * sh
            add_quad((x, y0, z_a), (x, y1, z_a), (x, y1, z_b), (x, y0, z_b), (-1.0, 0.0, 0.0))

        # Base inferior (-Z)
        for k in range(st):
            x_a = k * sd
            x_b = (k + 1) * sd
            add_quad_fondo(x_a, x_b, 0.0)

        # Trasera (+X)
        x_max = st * sd
        for h in range(st):
            z_a = h * sh
            z_b = (h + 1) * sh
            add_quad_trasera(x_max, z_a, z_b)

        # Laterales (+Y y -Y)
        for k in range(st):
            x_a = k * sd
            x_b = (k + 1) * sd
            for h in range(k + 1):
                z_a = h * sh
                z_b = (h + 1) * sh
                add_quad((x_a, y1, z_a), (x_b, y1, z_a), (x_b, y1, z_b), (x_a, y1, z_b), (0.0, 1.0, 0.0))
                add_quad((x_a, y0, z_a), (x_a, y0, z_b), (x_b, y0, z_b), (x_b, y0, z_a), (0.0, -1.0, 0.0))

    else:
        # Floating
        for k in range(st):
            x_a = k * sd
            x_mid = (k + 1) * sd
            x_end = min((k + 2) * sd, st * sd)
            z_bot = k * sh
            z_top = (k + 1) * sh

            add_quad((x_a, y0, z_top), (x_mid, y0, z_top), (x_mid, y1, z_top), (x_a, y1, z_top), (0.0, 0.0, 1.0))
            add_quad((x_a, y0, z_bot), (x_a, y1, z_bot), (x_a, y1, z_top), (x_a, y0, z_top), (-1.0, 0.0, 0.0))
            if k == 0:
                add_quad_fondo(x_a, x_mid, 0.0)
                add_quad_fondo(x_mid, x_end, 0.0)
            elif k < st - 1:
                add_quad_fondo(x_mid, x_end, z_bot)
            add_quad_trasera(x_end, z_bot, z_top)

            add_quad((x_a, y1, z_bot), (x_mid, y1, z_bot), (x_mid, y1, z_top), (x_a, y1, z_top), (0.0, 1.0, 0.0))
            add_quad((x_a, y0, z_bot), (x_a, y0, z_top), (x_mid, y0, z_top), (x_mid, y0, z_bot), (0.0, -1.0, 0.0))
            if x_end > x_mid:
                add_quad((x_mid, y1, z_bot), (x_end, y1, z_bot), (x_end, y1, z_top), (x_mid, y1, z_top), (0.0, 1.0, 0.0))
                add_quad((x_mid, y0, z_bot), (x_mid, y0, z_top), (x_end, y0, z_top), (x_end, y0, z_bot), (0.0, -1.0, 0.0))

    return malla_core.Malla(tuple(v), tuple(t), tuple(n), tuple(uv))


def escalera_curva(
    *,
    step_width: float = 150.0,
    step_height: float = 18.0,
    inner_radius: float = 200.0,
    curve_angle: float = 90.0,
    steps: int = 12,
    floating: bool = False,
) -> malla_core.Malla:
    """Escalera curva helicoidal con normales duras por cara."""
    try:
        sw, sh = float(step_width), float(step_height)
        ir, ca = float(inner_radius), float(curve_angle)
        st = int(steps)
        fl = bool(floating)
    except (TypeError, ValueError, OverflowError):
        raise malla_core.MallaError("parámetros de tipo inválido.") from None

    if not all(math.isfinite(v) and v > 0.0 for v in (sw, sh, ir)):
        raise malla_core.MallaError("step_width/height e inner_radius deben ser mayores que cero.")
    if not math.isfinite(ca) or abs(ca) < 1.0 or abs(ca) > 360.0:
        raise malla_core.MallaError("curve_angle debe estar entre 1 y 360 grados (con signo para el sentido).")
    if st < 1 or st > 256:
        raise malla_core.MallaError("steps debe estar entre 1 y 256.")

    v, t, n, uv = [], [], [], []
    r0 = ir
    r1 = ir + sw
    start_ang = 0.0 if ca >= 0.0 else 180.0
    d_ang = ca / st
    es_negativo = ca < 0.0
    total_z = st * sh

    def p(r_val, ang_deg, z_val):
        rad = math.radians(ang_deg)
        return (r_val * math.cos(rad), r_val * math.sin(rad), z_val)

    def add_tri(p1, p2, p3, n_esp):
        idx_base = len(v)
        for pt in (p1, p2, p3):
            v.append(pt)
            n.append(n_esp)
            r_pt = math.hypot(pt[0], pt[1])
            u = (r_pt - r0) / sw if sw > 0 else 0.0
            fv = pt[2] / total_z if total_z > 0 else 0.0
            uv.append((u, fv))
        tri = (idx_base, idx_base + 1, idx_base + 2)
        if malla_core._punto(malla_core.cara_frontal(v, tri), n_esp) < 0.0:
            tri = (tri[0], tri[2], tri[1])
        t.append(tri)

    def add_huella(a_a, a_b, z):
        p00 = p(r0, a_a, z)
        p10 = p(r1, a_a, z)
        p11 = p(r1, a_b, z)
        p01 = p(r0, a_b, z)
        if not es_negativo:
            add_tri(p10, p00, p01, (0.0, 0.0, 1.0))
            add_tri(p01, p11, p10, (0.0, 0.0, 1.0))
        else:
            add_tri(p00, p10, p11, (0.0, 0.0, 1.0))
            add_tri(p11, p01, p00, (0.0, 0.0, 1.0))

    def add_contrahuella(a, z_a, z_b):
        rad = math.radians(a)
        sign = 1.0 if d_ang >= 0 else -1.0
        n_tan = (sign * math.sin(rad), -sign * math.cos(rad), 0.0)
        p00 = p(r0, a, z_a)
        p10 = p(r1, a, z_a)
        p11 = p(r1, a, z_b)
        p01 = p(r0, a, z_b)
        if not es_negativo:
            add_tri(p10, p00, p01, n_tan)
            add_tri(p01, p11, p10, n_tan)
        else:
            add_tri(p00, p10, p11, n_tan)
            add_tri(p11, p01, p00, n_tan)

    def add_fondo(a_a, a_b, z):
        p00 = p(r0, a_a, z)
        p10 = p(r1, a_a, z)
        p11 = p(r1, a_b, z)
        p01 = p(r0, a_b, z)
        if not es_negativo:
            add_tri(p00, p10, p11, (0.0, 0.0, -1.0))
            add_tri(p11, p01, p00, (0.0, 0.0, -1.0))
        else:
            add_tri(p10, p00, p01, (0.0, 0.0, -1.0))
            add_tri(p01, p11, p10, (0.0, 0.0, -1.0))

    def add_trasera(a, z_a, z_b):
        rad = math.radians(a)
        sign = 1.0 if d_ang >= 0 else -1.0
        n_tan_fin = (-sign * math.sin(rad), sign * math.cos(rad), 0.0)
        p00 = p(r0, a, z_a)
        p10 = p(r1, a, z_a)
        p11 = p(r1, a, z_b)
        p01 = p(r0, a, z_b)
        if not es_negativo:
            add_tri(p00, p10, p11, n_tan_fin)
            add_tri(p11, p01, p00, n_tan_fin)
        else:
            add_tri(p10, p00, p01, n_tan_fin)
            add_tri(p01, p11, p10, n_tan_fin)

    def add_pared_int(a_a, a_b, z_a, z_b):
        rad_mid = math.radians((a_a + a_b) / 2.0)
        n_int = (-math.cos(rad_mid), -math.sin(rad_mid), 0.0)
        p00 = p(r0, a_a, z_a)
        p10 = p(r0, a_b, z_a)
        p11 = p(r0, a_b, z_b)
        p01 = p(r0, a_a, z_b)
        add_tri(p00, p10, p11, n_int)
        add_tri(p11, p01, p00, n_int)

    def add_pared_ext(a_a, a_b, z_a, z_b):
        rad_mid = math.radians((a_a + a_b) / 2.0)
        n_ext = (math.cos(rad_mid), math.sin(rad_mid), 0.0)
        p00 = p(r1, a_a, z_a)
        p10 = p(r1, a_b, z_a)
        p11 = p(r1, a_b, z_b)
        p01 = p(r1, a_a, z_b)
        add_tri(p11, p10, p00, n_ext)
        add_tri(p00, p01, p11, n_ext)

    if not fl:
        for k in range(st):
            a_a = start_ang + k * d_ang
            a_b = start_ang + (k + 1) * d_ang
            add_huella(a_a, a_b, (k + 1) * sh)
            add_contrahuella(a_a, k * sh, (k + 1) * sh)
            add_fondo(a_a, a_b, 0.0)
            add_trasera(start_ang + ca, k * sh, (k + 1) * sh)
            for h in range(k + 1):
                z_a = h * sh
                z_b = (h + 1) * sh
                add_pared_int(a_a, a_b, z_a, z_b)
                add_pared_ext(a_a, a_b, z_a, z_b)
    else:
        for k in range(st):
            a_a = start_ang + k * d_ang
            a_mid = start_ang + (k + 1) * d_ang
            k_end = min(k + 2, st)
            a_end = start_ang + k_end * d_ang
            z_bot = k * sh
            z_top = (k + 1) * sh

            add_huella(a_a, a_mid, z_top)
            add_contrahuella(a_a, z_bot, z_top)
            if k == 0:
                add_fondo(a_a, a_mid, 0.0)
                add_fondo(a_mid, a_end, 0.0)
            elif k < st - 1:
                add_fondo(a_mid, a_end, z_bot)
            add_trasera(a_end, z_bot, z_top)

            add_pared_int(a_a, a_mid, z_bot, z_top)
            add_pared_ext(a_a, a_mid, z_bot, z_top)
            if k_end > k + 1:
                add_pared_int(a_mid, a_end, z_bot, z_top)
                add_pared_ext(a_mid, a_end, z_bot, z_top)

    return malla_core.Malla(tuple(v), tuple(t), tuple(n), tuple(uv))


def esfera_caja(*, radius: float = 80.0, steps: int = 6) -> malla_core.Malla:
    """Esfera de topología cúbica (cube mapping normalizado) centrada en el origen con normales suaves.

    `steps` define la resolución por arista de cada una de las 6 caras del cubo (1 a 64).
    La proyección utiliza la transformación no lineal de Cube Mapping para distribución equitativa de quads.
    """
    try:
        r = float(radius)
        st = int(steps)
    except (TypeError, ValueError, OverflowError):
        raise malla_core.MallaError("parámetros de tipo inválido.") from None

    if not math.isfinite(r) or r <= 0.0:
        raise malla_core.MallaError("radius debe ser mayor que cero.")
    if st < 1 or st > 64:
        raise malla_core.MallaError("steps debe estar entre 1 y 64.")

    N = max(st - 1, 1)
    v, t, n, uv = [], [], [], []

    caras = [
        ((-1.0, -1.0, -1.0), (2.0, 0, 0), (0, 2.0, 0), (0.0, 0.0, -1.0)),  # -Z
        ((-1.0, -1.0, 1.0), (2.0, 0, 0), (0, 2.0, 0), (0.0, 0.0, 1.0)),    # +Z
        ((-1.0, -1.0, -1.0), (2.0, 0, 0), (0, 0, 2.0), (0.0, -1.0, 0.0)),  # -Y
        ((-1.0, 1.0, -1.0), (2.0, 0, 0), (0, 0, 2.0), (0.0, 1.0, 0.0)),   # +Y
        ((-1.0, -1.0, -1.0), (0, 2.0, 0), (0, 0, 2.0), (-1.0, 0.0, 0.0)),  # -X
        ((1.0, -1.0, -1.0), (0, 2.0, 0), (0, 0, 2.0), (1.0, 0.0, 0.0)),   # +X
    ]

    for origen, eu, ev, n_cara in caras:
        base = len(v)
        for j in range(N + 1):
            for i in range(N + 1):
                fu, fv = i / N, j / N
                px = origen[0] + eu[0] * fu + ev[0] * fv
                py = origen[1] + eu[1] * fu + ev[1] * fv
                pz = origen[2] + eu[2] * fu + ev[2] * fv

                x2, y2, z2 = px * px, py * py, pz * pz
                sx = px * math.sqrt(max(0.0, 1.0 - y2 * 0.5 - z2 * 0.5 + y2 * z2 / 3.0))
                sy = py * math.sqrt(max(0.0, 1.0 - x2 * 0.5 - z2 * 0.5 + x2 * z2 / 3.0))
                sz = pz * math.sqrt(max(0.0, 1.0 - x2 * 0.5 - y2 * 0.5 + x2 * y2 / 3.0))
                norm = math.hypot(sx, sy, sz)
                nx, ny, nz = sx / norm, sy / norm, sz / norm
                v.append((nx * r, ny * r, nz * r))
                n.append((nx, ny, nz))
                uv.append((fu, fv))

        for j in range(N):
            for i in range(N):
                p00 = base + j * (N + 1) + i
                p10, p01, p11 = p00 + 1, p00 + N + 1, p00 + N + 2
                for tri in ((p00, p10, p11), (p00, p11, p01)):
                    c_front = malla_core.cara_frontal(v, tri)
                    c_mid = [(v[tri[0]][k] + v[tri[1]][k] + v[tri[2]][k]) / 3.0 for k in range(3)]
                    if malla_core._punto(c_front, c_mid) < 0.0:
                        tri = (tri[0], tri[2], tri[1])
                    t.append(tri)

    return malla_core.Malla(tuple(v), tuple(t), tuple(n), tuple(uv))
