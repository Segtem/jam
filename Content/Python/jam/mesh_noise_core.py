"""Contrato puro del desplazamiento Perlin de mallas.

Geometry Script hace el cálculo sobre ``DynamicMesh``; este módulo decide qué parámetros son
admisibles sin importar ``unreal``. Así Compile/tests pueden defender el nodo sin arrancar el motor.
"""

from __future__ import annotations

from dataclasses import dataclass
import math


@dataclass(frozen=True)
class PerlinConfig:
    amplitud: float
    frecuencia: float
    seed: int
    por_normal: bool


def configurar(*, amplitud: float = 100.0, frecuencia: float = 0.003,
               seed: int = 7, por_normal: bool = True) -> PerlinConfig:
    """Valida el contrato estable de ``ApplyPerlinNoiseToMesh2`` de UE 5.8.

    La frecuencia se expresa en ciclos aproximados por centímetro porque Geometry Script evalúa
    ``PerlinNoise3D(frecuencia * posición)`` y Jam trabaja en centímetros.
    """
    try:
        a = float(amplitud)
        f = float(frecuencia)
        s = int(seed)
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValueError("amplitud, frecuencia y seed deben ser numéricos.") from exc
    if not math.isfinite(a) or a < 0.0:
        raise ValueError("amplitud debe ser finita y no negativa.")
    if not math.isfinite(f) or f <= 0.0:
        raise ValueError("frecuencia debe ser finita y mayor que cero.")
    if s < -(2 ** 31) or s > 2 ** 31 - 1:
        raise ValueError("seed debe entrar en un entero de 32 bits.")
    return PerlinConfig(a, f, s, bool(por_normal))
