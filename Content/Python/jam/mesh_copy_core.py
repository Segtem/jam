"""Contrato puro para leer LODs de Static/Skeletal Mesh como una malla M."""

from __future__ import annotations

from dataclasses import dataclass


_LOD_MEMBERS = {
    "max_available": "MAX_AVAILABLE",
    "hi_res": "HI_RES_SOURCE_MODEL",
    "source": "SOURCE_MODEL",
    "render": "RENDER_DATA",
}


@dataclass(frozen=True)
class CopyOptions:
    lod_member: str
    lod_index: int
    apply_build_settings: bool
    request_tangents: bool
    use_build_scale: bool


def options(*, lod_type: str = "max_available", lod_index: int = 0,
            apply_build_settings: bool = True, request_tangents: bool = True,
            use_build_scale: bool = True, skeletal: bool = False) -> CopyOptions:
    """Normaliza el contrato que después cruza el adaptador a structs/enums de UE."""
    kind = str(lod_type).strip().lower()
    if kind not in _LOD_MEMBERS:
        raise ValueError(f"lod_type desconocido: «{lod_type}» (hay {sorted(_LOD_MEMBERS)})")
    if skeletal and kind == "hi_res":
        raise ValueError("hi_res sólo existe para Static Mesh; Skeletal Mesh usa source o render.")
    index = int(lod_index)
    if index < 0:
        raise ValueError("lod_index debe ser cero o positivo.")
    return CopyOptions(
        lod_member=_LOD_MEMBERS[kind], lod_index=index,
        apply_build_settings=bool(apply_build_settings),
        request_tangents=bool(request_tangents), use_build_scale=bool(use_build_scale),
    )
