"""Operadores de mallas de la BASE COMÚN: transformar y juntar.

Geometría calculada en el núcleo puro (cero `import unreal`), idéntica a la que Geometry Script
produce en Unreal Engine 5.8.

- `transformar`: escala, rota (convención FRotator de Unreal: Z arriba, mano izquierda) y traslada.
  Invierte el winding de los triángulos cuando el determinante de la escala es negativo para
  conservar la orientación exterior de las caras.
- `juntar`: combina dos o más mallas en una sola Malla (mesh_merge).
"""

from __future__ import annotations

import math

from . import malla_core


def _rot_x(ang_rad: float):
    c, s = math.cos(ang_rad), math.sin(ang_rad)
    return [[1.0, 0.0, 0.0], [0.0, c, -s], [0.0, s, c]]


def _rot_y(ang_rad: float):
    c, s = math.cos(ang_rad), math.sin(ang_rad)
    return [[c, 0.0, s], [0.0, 1.0, 0.0], [-s, 0.0, c]]


def _rot_z(ang_rad: float):
    c, s = math.cos(ang_rad), math.sin(ang_rad)
    return [[c, -s, 0.0], [s, c, 0.0], [0.0, 0.0, 1.0]]


def _mat_mul(a, b):
    return [[sum(a[i][k] * b[k][j] for k in range(3)) for j in range(3)] for i in range(3)]


def _mat_vec(m, v):
    return (m[0][0] * v[0] + m[0][1] * v[1] + m[0][2] * v[2],
            m[1][0] * v[0] + m[1][1] * v[1] + m[1][2] * v[2],
            m[2][0] * v[0] + m[2][1] * v[1] + m[2][2] * v[2])


def _rot_matrix_unreal(pitch: float, yaw: float, roll: float):
    """Matriz de rotación 3x3 de Unreal Engine para un FRotator(pitch, yaw, roll).

    En Unreal (sistema de coordenadas de mano izquierda, Z arriba, X adelante, Y derecha):
    Yaw gira alrededor de Z, Pitch alrededor de Y, Roll alrededor de X.
    Composición: Rz(yaw) * Ry(-pitch) * Rx(-roll).
    """
    rx = _rot_x(math.radians(-roll))
    ry = _rot_y(math.radians(-pitch))
    rz = _rot_z(math.radians(yaw))
    return _mat_mul(rz, _mat_mul(ry, rx))


def transformar(malla: malla_core.Malla, *,
                x: float = 0.0, y: float = 0.0, z: float = 0.0,
                pitch: float = 0.0, yaw: float = 0.0, roll: float = 0.0,
                scale_x: float = 1.0, scale_y: float = 1.0, scale_z: float = 1.0) -> malla_core.Malla:
    """Aplica escala, rotación (FRotator de Unreal) y traslación a una Malla.

    Si el determinante de la escala es negativo (reflexión espacial), invierte el winding de cada
    triángulo para que las caras frontales sigan apuntando hacia afuera.
    """
    if not isinstance(malla, malla_core.Malla):
        raise malla_core.MallaError("la entrada no es una malla procedural M")

    values = [x, y, z, pitch, yaw, roll, scale_x, scale_y, scale_z]
    try:
        x, y, z, pitch, yaw, roll, scale_x, scale_y, scale_z = (float(v) for v in values)
    except (TypeError, ValueError):
        raise malla_core.MallaError("la transformación contiene un número no finito.") from None

    if not all(math.isfinite(v) for v in (x, y, z, pitch, yaw, roll, scale_x, scale_y, scale_z)):
        raise malla_core.MallaError("la transformación contiene un número no finito.")
    if any(abs(v) < 1e-6 for v in (scale_x, scale_y, scale_z)):
        raise malla_core.MallaError("la escala no puede contener cero.")

    rot = _rot_matrix_unreal(pitch, yaw, roll)

    nuevos_v = []
    for v in malla.vertices:
        scaled = (v[0] * scale_x, v[1] * scale_y, v[2] * scale_z)
        rx, ry, rz = _mat_vec(rot, scaled)
        nuevos_v.append((rx + x, ry + y, rz + z))

    det_neg = (scale_x * scale_y * scale_z) < 0.0

    nuevas_n = []
    for n in malla.normales:
        # Transformación de normales con la inversa transpuesta
        ns = (n[0] / scale_x, n[1] / scale_y, n[2] / scale_z)
        rn = _mat_vec(rot, ns)
        mag = math.sqrt(rn[0] * rn[0] + rn[1] * rn[1] + rn[2] * rn[2])
        if mag > 1e-8:
            nuevas_n.append((rn[0] / mag, rn[1] / mag, rn[2] / mag))
        else:
            nuevas_n.append(rn)

    nuevos_t = []
    for t in malla.triangulos:
        if det_neg:
            nuevos_t.append((t[0], t[2], t[1]))
        else:
            nuevos_t.append(t)

    return malla_core.Malla(tuple(nuevos_v), tuple(nuevos_t), tuple(nuevas_n), malla.uv0)


def juntar(mallas) -> malla_core.Malla:
    """Combina dos o más mallas en una sola Malla (mesh_merge)."""
    items = list(mallas if isinstance(mallas, (list, tuple)) else (mallas,) if mallas is not None else ())
    if len(items) < 2 or any(not isinstance(m, malla_core.Malla) for m in items):
        raise malla_core.MallaError("mesh_merge necesita al menos dos entradas M válidas.")

    all_v, all_t, all_n, all_uv = [], [], [], []
    for m in items:
        offset = len(all_v)
        all_v.extend(m.vertices)
        all_n.extend(m.normales)
        all_uv.extend(m.uv0)
        for t in m.triangulos:
            all_t.append((t[0] + offset, t[1] + offset, t[2] + offset))

    return malla_core.Malla(tuple(all_v), tuple(all_t), tuple(all_n), tuple(all_uv))
