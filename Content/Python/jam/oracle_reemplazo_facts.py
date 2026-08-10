"""Hechos L0 del reemplazo de blockout, independientes de Unreal y de Oracle."""

from __future__ import annotations


def hechos(pieza, objetivo: dict) -> dict:
    """Publica desvíos firmados sin decidir qué tolerancia es aceptable."""
    origen, extension = pieza.aabb.origin, pieza.aabb.extent
    return {"reemplazo": [{
        "id": pieza.nombre,
        "d_centro_x": origen.x - objetivo["cx"],
        "d_centro_y": origen.y - objetivo["cy"],
        "d_base": (origen.z - extension.z) - objetivo["base"],
        "d_footprint_x": extension.x - objetivo["ex"],
        "d_footprint_y": extension.y - objetivo["ey"],
    }]}
