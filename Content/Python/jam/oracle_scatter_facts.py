"""Hechos L0 del dominio scatter, compartidos por runtime y diferencial.

Este módulo es cerebro puro: conoce ``geometry.Pieza`` y el contrato de datos de Jam, pero no
importa Unreal ni ejecuta Oracle. Así el fixture y la sombra miden exactamente la misma evidencia.
"""

from __future__ import annotations


def _plano(pieza) -> dict:
    a, loc = pieza.aabb, pieza.location
    return {
        "id": pieza.nombre,
        "ox": a.origin.x, "oy": a.origin.y, "oz": a.origin.z,
        "ex": a.extent.x, "ey": a.extent.y, "ez": a.extent.z,
        "lx": loc.x, "ly": loc.y, "lz": loc.z, "yaw": pieza.yaw,
    }


def _cobertura(piezas, centro, semi, grilla: int) -> dict:
    cx, cy = centro
    sx, sy = semi
    celdas = set()
    if sx > 0 and sy > 0:
        for pieza in piezas:
            x, y = pieza.aabb.origin.x, pieza.aabb.origin.y
            gx = min(grilla - 1, max(0, int((x - (cx - sx)) / (2 * sx) * grilla)))
            gy = min(grilla - 1, max(0, int((y - (cy - sy)) / (2 * sy) * grilla)))
            celdas.add((gx, gy))
    total = grilla * grilla
    return {
        "ocupadas": len(celdas),
        "total": total,
        "fraccion": len(celdas) / total if total else 0.0,
    }


def hechos(piezas, centro, semi, cantidad_pedida: int, *, grilla: int = 3) -> dict:
    """Aplana una tanda sin decidir si sus valores son aceptables."""
    piezas = list(piezas)
    cx, cy = centro
    sx, sy = semi
    return {
        "instancia": [_plano(pieza) for pieza in piezas],
        "scatter_config": [{"cx": cx, "cy": cy, "sx": sx, "sy": sy}],
        "conteo_scatter": [{"pedidas": cantidad_pedida, "obtenidas": len(piezas)}],
        "cobertura_scatter": [_cobertura(piezas, centro, semi, grilla)],
    }
