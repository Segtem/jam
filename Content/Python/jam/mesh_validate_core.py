"""Juicio puro de salud topológica para una malla M."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class MeshFacts:
    vertices: int
    triangle_ids: int
    dense: bool
    closed: bool
    border_loops: int
    ambiguous_borders: bool
    components: int
    uv_channels: int
    material_ids: tuple[int, ...]
    material_slots: int


def judge(facts: MeshFacts, *, require_closed: bool = False, max_components: int = 0,
          require_uv: bool = False, require_materials: bool = False) -> tuple[str, ...]:
    """Devuelve defectos observables; vacío significa que pasó los requisitos pedidos."""
    limit = int(max_components)
    if limit < 0:
        raise ValueError("max_components debe ser 0 (sin límite) o un entero positivo.")
    defects = []
    if facts.vertices <= 0 or facts.triangle_ids <= 0:
        defects.append("malla vacía")
    if not facts.dense:
        defects.append("IDs de vértice/triángulo con huecos")
    if facts.ambiguous_borders:
        defects.append("bordes de topología ambigua")
    if require_closed and not facts.closed:
        defects.append(f"malla abierta ({facts.border_loops} bordes cerrados)")
    if limit and facts.components > limit:
        defects.append(f"{facts.components} componentes (máximo {limit})")
    if require_uv and facts.uv_channels <= 0:
        defects.append("sin canales UV")
    if require_materials and (not facts.material_ids or facts.material_slots <= 0):
        defects.append("sin Material IDs/slots verificables")
    return tuple(defects)


def summary(facts: MeshFacts) -> str:
    closed = "cerrada" if facts.closed else f"abierta/{facts.border_loops} loops"
    materials = (f"IDs {list(facts.material_ids)}/{facts.material_slots} slots"
                 if facts.material_ids else "sin Material IDs")
    return (f"{facts.vertices} verts · {facts.triangle_ids} tris · {facts.components} componentes · "
            f"{closed} · UV {facts.uv_channels} · {materials}")
