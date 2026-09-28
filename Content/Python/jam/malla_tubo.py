"""Tubo sobre una curva de la BASE COMÚN: tubo / mesh_pipe.

Geometría calculada en el núcleo puro (cero `import unreal`), idéntica a la que Geometry Script
produce en Unreal Engine 5.8 con `AppendSimpleSweptPolygon`.

Barre un perfil regular de `sides` lados a lo largo de una curva S con taper lineal de `radius_start`
a `radius_end`, rotado `profile_rotation` grados, ingleteado en las esquinas con `miter_limit`, y
tapado si `capped` es True.
"""

from __future__ import annotations

import math
from typing import Any

from . import curve, malla_core

Vec3 = tuple[float, float, float]


def _dot(a: tuple[float, ...], b: tuple[float, ...]) -> float:
    return sum(x * y for x, y in zip(a, b))


def _cross(a: Vec3, b: Vec3) -> Vec3:
    return (
        a[1] * b[2] - a[2] * b[1],
        a[2] * b[0] - a[0] * b[2],
        a[0] * b[1] - a[1] * b[0],
    )


def _length(a: tuple[float, ...]) -> float:
    return math.sqrt(sum(x * x for x in a))


def _normalize(a: Vec3) -> Vec3:
    l = _length(a)
    return tuple(x / l for x in a) if l > 1e-12 else a  # type: ignore[return-value]


def _quat_from_two_vectors(u: Vec3, v: Vec3) -> tuple[float, float, float, float]:
    u_norm = _normalize(u)
    v_norm = _normalize(v)
    d = _dot(u_norm, v_norm)
    if d > 0.99999999:
        return (1.0, 0.0, 0.0, 0.0)
    if d < -0.99999999:
        axis = _cross((1.0, 0.0, 0.0), u_norm)
        if _length(axis) < 1e-6:
            axis = _cross((0.0, 1.0, 0.0), u_norm)
        axis_n = _normalize(axis)
        return (0.0, axis_n[0], axis_n[1], axis_n[2])
    c = _cross(u_norm, v_norm)
    w = 1.0 + d
    norm = math.sqrt(w * w + _dot(c, c))
    return (w / norm, c[0] / norm, c[1] / norm, c[2] / norm)


def _quat_rotate(q: tuple[float, float, float, float], v: Vec3) -> Vec3:
    w, x, y, z = q
    vx, vy, vz = v
    ix = w * vx + y * vz - z * vy
    iy = w * vy + z * vx - x * vz
    iz = w * vz + x * vy - y * vx
    iw = -x * vx - y * vy - z * vz
    return (
        ix * w + iw * -x + iy * -z - iz * -y,
        iy * w + iw * -y + iz * -x - ix * -z,
        iz * w + iw * -z + ix * -y - iy * -x,
    )


def _tubo_path(path: curve.CurvePath, *, radius_start: float = 30.0, radius_end: float = 5.0,
               sides: int = 10, capped: bool = True, profile_rotation: float = 0.0,
               miter_limit: float = 4.0, radius_from_parent: float = 0.0) -> malla_core.Malla:
    """Calcula la malla tubular para un único CurvePath."""
    puntos = path.points
    n_puntos = len(puntos)

    path_scale = float(getattr(path, "scale", 1.0))
    base = radius_start
    punta = radius_end
    parent = float(getattr(path, "parent_radius", 0.0))
    if radius_from_parent > 0.0 and parent > 1e-6:
        razon = radius_end / radius_start
        base = parent * radius_from_parent
        punta = base * razon

    r_start = base * path_scale
    r_end = punta * path_scale

    seg_lens = [math.dist(puntos[i], puntos[i + 1]) for i in range(n_puntos - 1)]
    total_len = sum(seg_lens)
    if total_len < 1e-4:
        raise malla_core.MallaError("mesh_pipe recibió una curva de longitud cero.")

    cum_lens = [0.0]
    for l in seg_lens:
        cum_lens.append(cum_lens[-1] + l)

    radios = [r_start + (r_end - r_start) * (cum_lens[i] / total_len) for i in range(n_puntos)]
    tangents = [_normalize(tuple(puntos[i + 1][k] - puntos[i][k] for k in range(3))) for i in range(n_puntos - 1)]

    # Unreal usa la rotación con signo horario opuesto sobre el perfil inicial
    rot_rad = -math.radians(profile_rotation)

    # Marco inicial en el primer segmento: rotación mínima desde (0, 0, 1) a la tangente
    q_init = _quat_from_two_vectors((0.0, 0.0, 1.0), tangents[0])
    x_curr = _quat_rotate(q_init, (1.0, 0.0, 0.0))
    y_curr = _quat_rotate(q_init, (0.0, 1.0, 0.0))

    rings: list[list[Vec3]] = []
    normals_rings: list[list[Vec3]] = []
    dr = r_end - r_start
    slope = dr / total_len

    for k in range(n_puntos):
        r = radios[k]
        ring: list[Vec3] = []
        n_ring: list[Vec3] = []
        t_k = (tangents[0] if k == 0
               else (tangents[-1] if k == n_puntos - 1
                     else _normalize(tuple(tangents[k - 1][j] + tangents[k][j] for j in range(3)))))

        if k == 0 or k == n_puntos - 1:
            for i in range(sides):
                th = rot_rad + 2.0 * math.pi * i / sides
                p = puntos[k]
                x_dir = math.cos(th)
                y_dir = math.sin(th)
                pt = tuple(p[j] + r * x_dir * x_curr[j] + r * y_dir * y_curr[j] for j in range(3))
                ring.append(pt)  # type: ignore[arg-type]
                n_rad = tuple(x_dir * x_curr[j] + y_dir * y_curr[j] for j in range(3))
                n_suave = _normalize(tuple(n_rad[j] - slope * t_k[j] for j in range(3)))
                n_ring.append(n_suave)
        else:
            v_in = tangents[k - 1]
            v_out = tangents[k]
            n_miter = _normalize(tuple(v_in[j] + v_out[j] for j in range(3)))
            denom = _dot(v_in, n_miter)
            b_axis = _cross(v_in, v_out)
            len_b = _length(b_axis)

            for i in range(sides):
                th = rot_rad + 2.0 * math.pi * i / sides
                x_dir = math.cos(th)
                y_dir = math.sin(th)
                v_trans = tuple(r * x_dir * x_curr[j] + r * y_dir * y_curr[j] for j in range(3))

                if len_b < 1e-8 or (denom > 0.0 and (1.0 / denom) <= miter_limit):
                    factor = _dot(v_trans, n_miter) / denom
                    pt = tuple(puntos[k][j] + v_trans[j] - factor * v_in[j] for j in range(3))
                else:
                    u_b = _normalize(b_axis)
                    comp_b = _dot(v_trans, u_b)
                    v_b = tuple(comp_b * u_b[j] for j in range(3))
                    u_miter = _normalize(_cross(n_miter, u_b))
                    u_in_perp = _normalize(_cross(v_in, u_b))
                    comp_perp = _dot(v_trans, u_in_perp)
                    v_in_plane = tuple(comp_perp * miter_limit * u_miter[j] for j in range(3))
                    pt = tuple(puntos[k][j] + v_b[j] + v_in_plane[j] for j in range(3))

                ring.append(pt)  # type: ignore[arg-type]
                n_rad = _normalize(v_trans)
                n_suave = _normalize(tuple(n_rad[j] - slope * t_k[j] for j in range(3)))
                n_ring.append(n_suave)

            # Transportar el marco hacia el siguiente segmento
            q_trans = _quat_from_two_vectors(v_in, v_out)
            x_curr = _quat_rotate(q_trans, x_curr)
            y_curr = _quat_rotate(q_trans, y_curr)

        rings.append(ring)
        normals_rings.append(n_ring)

    vertices: list[Vec3] = []
    triangulos: list[tuple[int, int, int]] = []
    normales: list[Vec3] = []
    uv0: list[tuple[float, float]] = []

    # Vértices del manto lateral
    for k in range(n_puntos):
        v_coord = cum_lens[k] / total_len
        for i in range(sides):
            vertices.append(rings[k][i])
            normales.append(normals_rings[k][i])
            uv0.append((i / sides, v_coord))

    def v_idx(k_idx: int, i_idx: int) -> int:
        return k_idx * sides + (i_idx % sides)

    # Triángulos laterales (winding de Unreal, caras frontales hacia afuera)
    for k in range(n_puntos - 1):
        for i in range(sides):
            i_next = (i + 1) % sides
            p0 = v_idx(k, i)
            p1 = v_idx(k, i_next)
            q0 = v_idx(k + 1, i)
            q1 = v_idx(k + 1, i_next)
            triangulos.append((q0, p1, p0))
            triangulos.append((p1, q0, q1))

    if capped:
        # Tapa start (base): normal dura hacia -tangents[0]
        n_cap_start = tuple(-x for x in tangents[0])
        base_start = len(vertices)
        for i in range(sides):
            th = rot_rad + 2.0 * math.pi * i / sides
            vertices.append(rings[0][i])
            normales.append(n_cap_start)  # type: ignore[arg-type]
            uv0.append((0.5 + 0.5 * math.cos(th), 0.5 + 0.5 * math.sin(th)))

        for j in range(sides - 2):
            if j == 0:
                p_a, p_b, p_c = 0, 1, sides - 1
            else:
                p_a, p_b, p_c = sides - j, 1, sides - j - 1
            triangulos.append((base_start + p_a, base_start + p_b, base_start + p_c))

        # Tapa end (punta): normal dura hacia +tangents[-1]
        n_cap_end = tangents[-1]
        base_end = len(vertices)
        for i in range(sides):
            th = rot_rad + 2.0 * math.pi * i / sides
            vertices.append(rings[-1][i])
            normales.append(n_cap_end)
            uv0.append((0.5 + 0.5 * math.cos(th), 0.5 + 0.5 * math.sin(th)))

        for j in range(sides - 2):
            if j == 0:
                p_a, p_b, p_c = sides - 1, 1, 0
            else:
                p_a, p_b, p_c = sides - j - 1, 1, sides - j
            triangulos.append((base_end + p_a, base_end + p_b, base_end + p_c))

    return malla_core.Malla(tuple(vertices), tuple(triangulos), tuple(normales), tuple(uv0))


def _unir_mallas(mallas: list[malla_core.Malla]) -> malla_core.Malla:
    """Concatena múltiples mallas tubulares en una sola."""
    if not mallas:
        return malla_core.Malla((), (), (), ())
    if len(mallas) == 1:
        return mallas[0]
    vertices: list[Vec3] = []
    triangulos: list[tuple[int, int, int]] = []
    normales: list[Vec3] = []
    uv0: list[tuple[float, float]] = []
    offset = 0
    for m in mallas:
        vertices.extend(m.vertices)
        normales.extend(m.normales)
        uv0.extend(m.uv0)
        triangulos.extend((t[0] + offset, t[1] + offset, t[2] + offset) for t in m.triangulos)
        offset += len(m.vertices)
    return malla_core.Malla(tuple(vertices), tuple(triangulos), tuple(normales), tuple(uv0))


def tubo(curva: Any, *, radius_start: float = 30.0, radius_end: float = 5.0,
         sides: int = 10, samples: int = 16, capped: bool = True,
         profile_rotation: float = 0.0, miter_limit: float = 4.0,
         radius_from_parent: float = 0.0, pivot_uvs: bool = False) -> malla_core.Malla:
    """Barre un perfil regular de `sides` lados a lo largo de una o varias curvas S con taper lineal.

    Parámetros y validaciones compatibles 1:1 con `mesh.pipe` de Unreal Engine 5.8:
    - `curva`: `curve.CurvePath`, `curve.CurveSet` o secuencia de puntos XYZ.
    - `radius_start`: radio inicial en el arranque de la curva (> 0.0).
    - `radius_end`: radio final en la punta de la curva (>= 0.0).
    - `sides`: cantidad de lados del polígono regular del perfil (>= 3).
    - `samples`: cantidad de muestras al remuestrear la curva (>= 2).
    - `capped`: si True, cierra los dos extremos con tapas poligonales planas.
    - `profile_rotation`: rotación del perfil en grados alrededor del eje tangencial.
    - `miter_limit`: factor límite para ingletes en esquinas (>= 1.0).
    - `radius_from_parent`: fracción del grosor heredado del padre (TreeGen).
    - `pivot_uvs`: conserva la firma de Unreal; en el núcleo la Malla no porta canales UV extra.
    """
    try:
        radius_start, radius_end = float(radius_start), float(radius_end)
        sides, samples = int(sides), int(samples)
        profile_rotation, miter_limit = float(profile_rotation), float(miter_limit)
        radius_from_parent = float(radius_from_parent)
    except (TypeError, ValueError, OverflowError):
        raise malla_core.MallaError("los parámetros de mesh_pipe deben ser numéricos.")

    values = (radius_start, radius_end, profile_rotation, miter_limit)
    if not all(math.isfinite(value) for value in values) or radius_start <= 0.0 or radius_end < 0.0:
        raise malla_core.MallaError("radius_start debe ser positivo y radius_end no puede ser negativo.")
    if sides < 3 or samples < 2:
        raise malla_core.MallaError("sides debe ser al menos 3 y samples al menos 2.")
    if miter_limit < 1.0:
        raise malla_core.MallaError("miter_limit debe ser al menos 1.")
    if not math.isfinite(radius_from_parent) or radius_from_parent < 0.0:
        raise malla_core.MallaError("radius_from_parent no puede ser negativo.")

    paths = curve.paths_of(curva, samples=samples)
    if not paths and isinstance(curva, (list, tuple)) and len(curva) >= 2:
        try:
            pt_tuples = tuple(tuple(float(c) for c in p) for p in curva)
            if all(len(p) == 3 for p in pt_tuples):
                paths = (curve.CurvePath(pt_tuples),)
        except (TypeError, ValueError):
            pass

    if not paths:
        raise malla_core.MallaError("mesh_pipe necesita una curva S válida con al menos dos puntos.")
    if any(path.length < 1e-4 for path in paths):
        raise malla_core.MallaError("mesh_pipe recibió una curva de longitud cero.")

    mallas = [
        _tubo_path(
            path,
            radius_start=radius_start,
            radius_end=radius_end,
            sides=sides,
            capped=bool(capped),
            profile_rotation=profile_rotation,
            miter_limit=miter_limit,
            radius_from_parent=radius_from_parent,
        )
        for path in paths
    ]

    return _unir_mallas(mallas)
