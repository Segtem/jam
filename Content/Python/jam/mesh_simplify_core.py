"""Contratos puros de simplificación de malla.

Geometry Script vive en :mod:`jam.mesh`; acá sólo se decide qué significa cada opción pública de
Jam. Mantener esta traducción sin ``unreal`` permite probar límites y la semántica de UE 5.8 sin
levantar el editor.
"""

from __future__ import annotations

from dataclasses import dataclass
import math


# Nombre público de Jam → miembro del enum Python de UE 5.8.1. ``attributes`` usa el algoritmo V2:
# desde 5.8, ``ATTRIBUTE_AWARE`` sólo considera normales aunque conserve el nombre histórico.
METHODS = {
    "standard": "STANDARD_QEM",
    "volume": "VOLUME_PRESERVING",
    "normals": "ATTRIBUTE_AWARE",
    "attributes": "ATTRIBUTE_AWARE_V2",
}


@dataclass(frozen=True)
class SimplifyOptions:
    method_member: str
    preserve_seams: bool
    regularize: float


def options(*, method: str = "attributes", preserve_seams: bool = True,
            regularize: float = 0.000001) -> SimplifyOptions:
    """Normaliza las opciones comunes y devuelve sólo datos portables."""
    nombre = str(method or "").strip().lower()
    if nombre not in METHODS:
        raise ValueError(
            f"method de simplificación: «{method}» (hay {sorted(METHODS)})")
    try:
        peso = float(regularize)
    except (TypeError, ValueError):
        raise ValueError("regularize debe ser un número entre 0 y 10.") from None
    if not math.isfinite(peso) or peso < 0.0 or peso > 10.0:
        raise ValueError("regularize debe ser un número finito entre 0 y 10.")
    return SimplifyOptions(METHODS[nombre], bool(preserve_seams), peso)


def triangle_target(value) -> int:
    """Valida la meta de triángulos sin imponer un mínimo geométrico arbitrario."""
    if isinstance(value, bool):
        raise ValueError("target_triangles debe ser un entero entre 1 y 10000000.")
    try:
        target = int(value)
    except (TypeError, ValueError, OverflowError):
        raise ValueError("target_triangles debe ser un entero entre 1 y 10000000.") from None
    if isinstance(value, float) and value != target:
        raise ValueError("target_triangles debe ser un entero entre 1 y 10000000.")
    if target < 1 or target > 10_000_000:
        raise ValueError("target_triangles debe estar entre 1 y 10000000.")
    return target


def distance(value, name: str) -> float:
    """Valida una distancia positiva en centímetros (la unidad nativa de Unreal)."""
    try:
        result = float(value)
    except (TypeError, ValueError):
        raise ValueError(f"{name} debe ser una distancia positiva en centímetros.") from None
    if not math.isfinite(result) or result <= 0.0:
        raise ValueError(f"{name} debe ser una distancia finita y positiva en centímetros.")
    return result
