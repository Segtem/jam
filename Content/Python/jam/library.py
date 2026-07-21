"""Biblioteca — el "Content Browser" de Jam: buscar assets del proyecto para colocar.

Equivalente al Content Browser de Dash (buscar en el proyecto/Megascans/etc.), pero acotado
por ahora a lo que ya vive en el proyecto (AssetRegistry). Devuelve StaticMesh; el que coloca
(`jam.place`) los spawnea. Fuentes externas (Fab/Megascans online) son un crecimiento posterior.
"""

from __future__ import annotations

import unreal

_SM_CLASS = unreal.TopLevelAssetPath("/Script/Engine", "StaticMesh")


def _registry() -> unreal.AssetRegistry:
    return unreal.AssetRegistryHelpers.get_asset_registry()


def buscar(query: str = "", *, limit: int = 25, raiz: str = "/Game") -> list[dict]:
    """Busca StaticMesh cuyo nombre contenga `query` (case-insensitive) bajo `raiz`.
    Devuelve dicts {'nombre', 'ruta'} (ruta = ObjectPath cargable), ordenados por nombre."""
    filt = unreal.ARFilter(
        class_paths=[_SM_CLASS], package_paths=[raiz], recursive_paths=True,
    )
    q = query.lower()
    out: list[dict] = []
    for ad in _registry().get_assets(filt):
        nombre = str(ad.asset_name)
        if q and q not in nombre.lower():
            continue
        ruta = f"{ad.package_name}.{ad.asset_name}"
        out.append({"nombre": nombre, "ruta": ruta})
    out.sort(key=lambda d: d["nombre"].lower())
    return out[:limit]


def cargar_malla(ruta: str) -> unreal.StaticMesh | None:
    """Carga el StaticMesh por su ObjectPath. None si no existe."""
    obj = unreal.load_asset(ruta)
    return obj if isinstance(obj, unreal.StaticMesh) else None
