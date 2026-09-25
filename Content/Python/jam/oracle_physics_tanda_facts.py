"""Hechos L0 del resultado de ``drop(points)``, sin Unreal ni Oracle."""

from __future__ import annotations


def _plano(resultado: dict) -> dict:
    pieza = resultado["pieza"]
    a, loc = pieza.aabb, pieza.location
    return {
        "id": pieza.nombre,
        "ox": a.origin.x, "oy": a.origin.y, "oz": a.origin.z,
        "ex": a.extent.x, "ey": a.extent.y, "ez": a.extent.z,
        "lx": loc.x, "ly": loc.y, "lz": loc.z, "yaw": pieza.yaw,
        "apoyada": bool(resultado["apoyada"]),
        "apoyada_medible": True,
        "soporte": resultado.get("soporte") or "",
        "soporte_medible": resultado.get("soporte") is not None,
        "sobre_hermana": bool(resultado.get("sobre_hermana")),
    }


def hechos(resultados) -> dict:
    """Aplana cada resultado sin decidir si la tanda es aceptable."""
    return {"asentada": [_plano(resultado) for resultado in resultados]}
