"""Conversión transaccional de StaticMesh a Nanite.

El asset fuente nunca se modifica. Si todavía no usa Nanite, Jam lo duplica a una ruta de Preview,
activa Nanite mediante ``StaticMeshEditorSubsystem`` y deja que ``panel`` resuelva Discard/Bake.
Esto hace que ``asset → nanite → place`` se comporte como cualquier otro conversor A → A.
"""

from __future__ import annotations

import re

import unreal

from . import library


CARPETA = "/Game/Jam/Nanite"


def _slug(nombre: str) -> str:
    return re.sub(r"[^A-Za-z0-9_]+", "_", str(nombre)).strip("_") or "StaticMesh"


def asset_path_for(asset, carpeta: str = CARPETA) -> str:
    """Ruta final determinista de la copia Nanite producida para ``asset``."""
    if isinstance(asset, str):
        nombre = asset.rsplit("/", 1)[-1].split(".", 1)[0]
    else:
        nombre = asset.get_name()
    return f"{carpeta}/{_slug(nombre)}_Nanite"


def _settings_enabled(settings) -> bool:
    try:
        return bool(settings.get_editor_property("enabled"))
    except Exception:  # noqa: BLE001
        return bool(getattr(settings, "enabled", False))


def _read_settings(mesh):
    """Lectura headless primero; el subsistema queda como compatibilidad para builds anteriores.

    UE 5.8.1 expone ``nanite_settings`` en el StaticMesh incluso cuando
    ``StaticMeshEditorSubsystem`` no existe en commandlet. Analizar no necesita un servicio de
    edición: sólo transformar/reconstruir lo necesita.
    """
    try:
        return mesh.get_editor_property("nanite_settings")
    except Exception:  # noqa: BLE001 — fallback de compatibilidad con la reflexión del motor
        subsystem = unreal.get_editor_subsystem(unreal.StaticMeshEditorSubsystem)
        if subsystem is None:
            raise RuntimeError(
                "StaticMeshEditorSubsystem no está disponible y el asset no expone nanite_settings")
        return subsystem.get_nanite_settings(mesh)


def analizar(asset, *, lod: int = 0) -> dict:
    """Lee la representación Nanite sin modificar el StaticMesh.

    Devuelve datos planos para que el juicio quede en :mod:`jam.nanite_core`. Los tres accessors de
    conteo son públicos en UE 5.8.1; cualquier ausencia o excepción se informa, no se reemplaza por
    cero porque eso confundiría «no pude medir» con «medí una representación vacía».
    """
    mesh = library.cargar_malla(asset) if isinstance(asset, str) else asset
    if mesh is None:
        return {"error": (
            f"«{asset}» no es un StaticMesh (el análisis Nanite necesita una malla estática).")}
    try:
        lod = int(lod)
        settings = _read_settings(mesh)
        from . import nanite_core
        return nanite_core.medida(
            asset=mesh.get_path_name(),
            enabled=_settings_enabled(settings),
            vertices=mesh.get_num_nanite_vertices(),
            triangles=mesh.get_num_nanite_triangles(),
            uv_channels=mesh.get_num_tex_coords(lod),
            lods=mesh.get_num_lods(),
            lod=lod,
        )
    except Exception as exc:  # noqa: BLE001 — frontera explícita de la API del motor
        return {"error": f"no pude medir Nanite: {type(exc).__name__}: {exc}"}


def validar(asset, *, lod: int = 0) -> dict:
    """Analiza y agrega un veredicto estructural, sin tocar el asset."""
    datos = analizar(asset, lod=lod)
    if "error" in datos:
        return datos
    from . import nanite_core
    return {
        **datos,
        "valido": nanite_core.es_valido(datos),
        "diagnosticos": nanite_core.diagnosticar(datos),
    }


def convertir(asset, *, carpeta: str = CARPETA) -> dict:
    """Devuelve ``{mesh, ruta, already}`` o ``{error}``.

    ``SetNaniteSettings(..., apply_changes=True)`` fuerza el rebuild de la malla duplicada. La ruta
    es temporal durante Run Graph y definitiva para callers de mantenimiento fuera de Preview.
    """
    mesh = library.cargar_malla(asset) if isinstance(asset, str) else asset
    if mesh is None:
        return {"error": f"«{asset}» no es un StaticMesh (Nanite necesita una malla estática)."}

    subsystem = unreal.get_editor_subsystem(unreal.StaticMeshEditorSubsystem)
    settings = subsystem.get_nanite_settings(mesh)
    source_path = mesh.get_path_name()
    if _settings_enabled(settings):
        return {"mesh": mesh, "ruta": source_path, "already": True}

    from . import panel
    final_path = asset_path_for(mesh, carpeta)
    output_path = panel.preview_asset_path(final_path)
    if unreal.EditorAssetLibrary.does_asset_exist(output_path):
        if not unreal.EditorAssetLibrary.delete_asset(output_path):
            return {"error": f"no pude limpiar el temporal Nanite «{output_path}»."}

    duplicate = unreal.EditorAssetLibrary.duplicate_asset(source_path, output_path)
    if duplicate is None:
        return {"error": f"no pude duplicar «{source_path}» como «{output_path}»."}

    try:
        duplicate_settings = subsystem.get_nanite_settings(duplicate)
        duplicate_settings.set_editor_property("enabled", True)
        # apply_changes=True llama PostEditChange y espera el rebuild que genera los datos Nanite.
        subsystem.set_nanite_settings(duplicate, duplicate_settings, True)
        if not _settings_enabled(subsystem.get_nanite_settings(duplicate)):
            raise RuntimeError("Unreal no conservó enabled=true después del rebuild")
        if not unreal.EditorAssetLibrary.save_asset(output_path, only_if_is_dirty=False):
            raise RuntimeError("Unreal no pudo guardar el StaticMesh convertido")
        # Permite recuperar Bake/Discard incluso cuando el grafo sólo produce Content y cero actores.
        panel.register_preview_asset(output_path)
    except Exception as exc:  # noqa: BLE001
        try:
            unreal.EditorAssetLibrary.delete_asset(output_path)
        except Exception:  # noqa: BLE001
            pass
        return {"error": f"falló el rebuild Nanite: {type(exc).__name__}: {exc}"}

    return {"mesh": duplicate, "ruta": output_path, "already": False}
