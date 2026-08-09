"""Buffers puros para convertir una polilínea abierta en una cinta triangulada.

No importa ``unreal``: el adaptador fino de :mod:`jam.mesh` traduce estas tuplas a Geometry
Script. La costura longitudinal de UV necesita duplicar vértices en un recorrido cerrado; esa
política todavía no está implementada, por lo que el núcleo rechaza esos recorridos explícitamente.
"""

from __future__ import annotations

import math

from .curve_sampling_core import offset_points


def _cross(a, b):
    return (
        a[1] * b[2] - a[2] * b[1],
        a[2] * b[0] - a[0] * b[2],
        a[0] * b[1] - a[1] * b[0],
    )


def _normals(vertices, triangles):
    accumulated = [[0.0, 0.0, 0.0] for _ in vertices]
    for triangle in triangles:
        a, b, c = (vertices[index] for index in triangle)
        face = _cross(
            tuple(b[axis] - a[axis] for axis in range(3)),
            tuple(c[axis] - a[axis] for axis in range(3)),
        )
        if sum(component * component for component in face) < 1e-16:
            return None
        for index in triangle:
            for axis in range(3):
                accumulated[index][axis] += face[axis]
    result = []
    for normal in accumulated:
        length = math.sqrt(sum(component * component for component in normal))
        if length < 1e-8:
            return None
        result.append(tuple(component / length for component in normal))
    return tuple(result)


def ribbon_buffers(points, *, width: float = 360.0, plane: str = "xy",
                   join: str = "miter", miter_limit: float = 4.0,
                   uv_scale: float = 200.0) -> dict:
    """Construye vértices, triángulos, normales y UV0 de una cinta abierta.

    ``U`` acumula la distancia media recorrida por ambos bordes y la divide por ``uv_scale``;
    ``V`` cruza de izquierda (0) a derecha (1). Así un bevel conserva continuidad y una textura
    mantiene escala aun cuando los dos bordes no recorren exactamente la misma longitud.
    """
    try:
        source = tuple(tuple(float(value) for value in point) for point in points)
        width, uv_scale = float(width), float(uv_scale)
        plane, join = (str(value or "").strip().lower() for value in (plane, join))
        miter_limit = float(miter_limit)
    except (TypeError, ValueError, OverflowError):
        return {"error": "mesh_ribbon recibió puntos o parámetros inválidos."}
    if len(source) < 2 or any(len(point) != 3 for point in source):
        return {"error": "mesh_ribbon necesita una polilínea XYZ de al menos dos puntos."}
    if any(not all(math.isfinite(value) for value in point) for point in source):
        return {"error": "mesh_ribbon recibió una coordenada no finita."}
    if math.dist(source[0], source[-1]) < 1e-6:
        return {"error": "mesh_ribbon todavía no admite recorridos cerrados con costura UV."}
    if not math.isfinite(width) or not 0.01 <= width <= 1_000_000.0:
        return {"error": "width de mesh_ribbon debe estar entre 0.01 y 1000000 cm."}
    if not math.isfinite(uv_scale) or not 0.01 <= uv_scale <= 1_000_000.0:
        return {"error": "uv_scale de mesh_ribbon debe estar entre 0.01 y 1000000 cm."}

    common = {"distance": width * 0.5, "plane": plane, "join": join,
              "miter_limit": miter_limit}
    left = offset_points(source, side="left", **common)
    right = offset_points(source, side="right", **common)
    if "error" in left:
        return {"error": left["error"].replace("curve_offset", "mesh_ribbon")}
    if "error" in right:
        return {"error": right["error"].replace("curve_offset", "mesh_ribbon")}
    if len(left["points"]) != len(right["points"]):
        return {"error": "mesh_ribbon produjo bordes con distinta cantidad de muestras."}
    if len(left["points"]) * 2 > 4096:
        return {"error": "mesh_ribbon no puede producir más de 4096 vértices por recorrido."}

    vertices = tuple(
        point
        for pair in zip(left["points"], right["points"])
        for point in pair
    )
    triangles = tuple(
        triangle
        for index in range(len(left["points"]) - 1)
        for triangle in (
            (index * 2, index * 2 + 1, index * 2 + 2),
            (index * 2 + 1, index * 2 + 3, index * 2 + 2),
        )
    )
    normals = _normals(vertices, triangles)
    if normals is None:
        return {"error": "mesh_ribbon produjo un triángulo degenerado; revise ancho y curva."}

    u_values = [0.0]
    for index in range(1, len(left["points"])):
        step = (math.dist(left["points"][index - 1], left["points"][index])
                + math.dist(right["points"][index - 1], right["points"][index])) * 0.5
        u_values.append(u_values[-1] + step / uv_scale)
    uv0 = tuple(uv for u in u_values for uv in ((u, 0.0), (u, 1.0)))
    return {
        "vertices": vertices,
        "triangles": triangles,
        "normals": normals,
        "uv0": uv0,
        "width": width,
        "length_u": u_values[-1] * uv_scale,
        "bevels": left["bevels"],
        "info": (f"{len(vertices)} vértices · {len(triangles)} triángulos · "
                 f"ancho {width:g} cm · UV0 {u_values[-1]:.2f} U"),
    }
