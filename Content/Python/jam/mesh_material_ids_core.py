"""Reglas puras para operar Material IDs de una DynamicMesh.

Los IDs son índices, no materiales. Este módulo valida la intención antes de que el adaptador toque
Geometry Script y evita crear referencias a slots inexistentes.
"""

from __future__ import annotations

from dataclasses import dataclass


MAX_MATERIAL_ID = 1_000_000


def material_id(value, name: str) -> int:
    if isinstance(value, bool):
        raise ValueError(f"{name} debe ser un ID entero no negativo.")
    try:
        result = int(value)
    except (TypeError, ValueError, OverflowError):
        raise ValueError(f"{name} debe ser un ID entero no negativo.") from None
    if isinstance(value, float) and value != result:
        raise ValueError(f"{name} debe ser un ID entero no negativo.")
    if result < 0 or result > MAX_MATERIAL_ID:
        raise ValueError(f"{name} debe estar entre 0 y {MAX_MATERIAL_ID}.")
    return result


@dataclass(frozen=True)
class RemapPlan:
    from_id: int
    to_id: int
    used_before: tuple[int, ...]
    used_after: tuple[int, ...]


def remap_plan(from_value, to_value, used_ids) -> RemapPlan:
    """Valida una fusión de sections: origen y destino tienen que existir."""
    source = material_id(from_value, "from_id")
    target = material_id(to_value, "to_id")
    used = tuple(sorted({int(value) for value in used_ids if int(value) >= 0}))
    if not used:
        raise ValueError("la malla no tiene Material IDs habilitados.")
    if source == target:
        raise ValueError("from_id y to_id son iguales; la reasignación no haría nada.")
    if source not in used:
        raise ValueError(f"from_id {source} no está usado; la malla usa {list(used)}.")
    if target not in used:
        raise ValueError(
            f"to_id {target} no está usado y no tiene un slot verificable; la malla usa {list(used)}.")
    after = tuple(value for value in used if value != source)
    return RemapPlan(source, target, used, after)


def compact_mapping(used_ids) -> dict[int, int]:
    """Mapa determinista que debe producir CompactMaterialIDs si no hay slots duplicados."""
    used = sorted({int(value) for value in used_ids if int(value) >= 0})
    if not used:
        raise ValueError("la malla no tiene Material IDs habilitados.")
    return {old: new for new, old in enumerate(used)}
