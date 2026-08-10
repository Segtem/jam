"""Hechos L0 del asentamiento unitario, independientes de Unreal y de Oracle."""

from __future__ import annotations


def hechos(pieza, soportes, *, tol: float = 1.0) -> dict:
    """Mide soporte y gap con una implementación contrastable contra `geometry.soporte_top`."""
    a = pieza.aabb
    mejor = None
    for soporte in soportes:
        s = soporte.aabb
        if abs(s.origin.x - a.origin.x) > s.extent.x + a.extent.x:
            continue
        if abs(s.origin.y - a.origin.y) > s.extent.y + a.extent.y:
            continue
        top = s.origin.z + s.extent.z
        if top > a.origin.z + tol:
            continue
        if mejor is None or top > mejor[0]:
            mejor = (top, soporte.nombre)

    base = a.origin.z - a.extent.z
    return {"asentamiento": [{
        "pieza": pieza.nombre,
        "tiene_suelo": mejor is not None,
        "gap": None if mejor is None else base - mejor[0],
        "soporte": None if mejor is None else mejor[1],
    }]}
