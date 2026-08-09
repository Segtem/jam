"""Contrato puro de la primera prueba MassEntity de Jam."""

from __future__ import annotations

from dataclasses import dataclass
import math


MAX_ENTITIES = 4096
POSITION_TOLERANCE_CM = 0.001


@dataclass(frozen=True)
class MassProbeBatch:
    """Frames validados que el adaptador traduce a ``FTransform``."""

    frames: tuple
    position_sum: tuple[float, float, float]

    def __len__(self) -> int:
        return len(self.frames)


def prepare(frame_set) -> dict:
    """Valida el dato F sin importar Unreal y construye la entrada acotada de la sonda."""
    from .curve import FrameSet

    if not isinstance(frame_set, FrameSet) or not frame_set.frames:
        return {"error": "mass_probe necesita un stream F válido y no vacío."}
    if len(frame_set.frames) > MAX_ENTITIES:
        return {"error": f"mass_probe no puede crear más de {MAX_ENTITIES} entidades."}

    sums = [0.0, 0.0, 0.0]
    for index, frame in enumerate(frame_set.frames):
        values = (*frame.position, *frame.tangent, *frame.outward, frame.scale)
        if len(frame.position) != 3 or len(frame.tangent) != 3 or len(frame.outward) != 3:
            return {"error": f"el frame {index} no tiene vectores de tres componentes."}
        try:
            values = tuple(float(value) for value in values)
        except (TypeError, ValueError):
            return {"error": f"el frame {index} contiene un valor no numérico."}
        if not all(math.isfinite(value) for value in values):
            return {"error": f"el frame {index} contiene un valor no finito."}
        if float(frame.scale) <= 0.0:
            return {"error": f"el frame {index} tiene escala no positiva."}
        for axis in range(3):
            sums[axis] += float(frame.position[axis])

    return {"batch": MassProbeBatch(tuple(frame_set.frames), tuple(sums))}


def judge(batch: MassProbeBatch, facts: dict) -> dict:
    """Juzga hechos del puente C++; nunca consulta el mundo por su cuenta."""
    if not isinstance(facts, dict):
        return {"ok": False, "defects": ["el puente Mass no devolvió hechos"]}
    if not facts.get("ok"):
        return {"ok": False, "defects": [str(facts.get("error") or "MassEntity falló")]}

    count = len(batch)
    defects = []
    expected_counts = {
        "requested": count,
        "created": count,
        "valid_before": count,
        "same_archetype": count,
        "transform_mismatches": 0,
        "valid_after": 0,
    }
    for field, expected in expected_counts.items():
        if facts.get(field) != expected:
            defects.append(f"{field}={facts.get(field)!r}, esperado {expected}")

    for axis, expected in zip("xyz", batch.position_sum):
        input_value = facts.get(f"input_sum_{axis}")
        observed = facts.get(f"observed_sum_{axis}")
        if not isinstance(input_value, (int, float)) or abs(input_value - expected) > POSITION_TOLERANCE_CM:
            defects.append(f"input_sum_{axis} no conserva la entrada")
        if not isinstance(observed, (int, float)) or abs(observed - expected) > POSITION_TOLERANCE_CM:
            defects.append(f"observed_sum_{axis} no conserva los fragments")

    return {
        "ok": not defects,
        "defects": defects,
        "info": (f"{count} entidades · 1 arquetipo · transforms conservados · "
                 "limpieza completa"),
    }
