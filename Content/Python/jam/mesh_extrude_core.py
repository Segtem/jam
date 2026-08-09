"""Contrato puro de extrusión lineal para superficies abiertas.

Geometry Script multiplica ``Direction * Distance`` sin normalizar la dirección. Jam sí la
normaliza: la perilla ``distance`` conserva así su unidad en centímetros y no cambia de significado
cuando el autor escribe, por ejemplo, ``(0, 0, 2)`` en vez de ``(0, 0, 1)``.
"""

from __future__ import annotations

from dataclasses import dataclass
import math


@dataclass(frozen=True)
class ExtrudeConfig:
    distance: float
    direction: tuple[float, float, float]
    uv_scale: float
    uv_factor: float


def configurar(*, distance: float = 300.0, direction_x: float = 0.0,
               direction_y: float = 0.0, direction_z: float = 1.0,
               uv_scale: float = 100.0) -> ExtrudeConfig:
    """Valida una extrusión y convierte centímetros por UV al factor nativo ``1/cm``."""
    try:
        distance, uv_scale = float(distance), float(uv_scale)
        direction = (float(direction_x), float(direction_y), float(direction_z))
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValueError(
            "distance, dirección y uv_scale de mesh_extrude deben ser numéricos.") from exc
    if not math.isfinite(distance) or not 0.01 <= distance <= 1_000_000.0:
        raise ValueError("distance de mesh_extrude debe estar entre 0.01 y 1000000 cm.")
    if not math.isfinite(uv_scale) or not 0.01 <= uv_scale <= 1_000_000.0:
        raise ValueError("uv_scale de mesh_extrude debe estar entre 0.01 y 1000000 cm por UV.")
    if not all(math.isfinite(component) for component in direction):
        raise ValueError("la dirección de mesh_extrude debe ser finita.")
    length = math.sqrt(sum(component * component for component in direction))
    if length < 1e-8:
        raise ValueError("la dirección de mesh_extrude no puede ser cero.")
    normalized = tuple(component / length for component in direction)
    return ExtrudeConfig(distance, normalized, uv_scale, 1.0 / uv_scale)
