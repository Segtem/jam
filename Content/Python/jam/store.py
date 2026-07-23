"""Persistencia de Jam — adaptador chiquito: guarda/lee lo que el cerebro serializa.

Hoy sólo el kit (qué ancla tiene cada asset normalizado): se normaliza una vez y sobrevive al
reinicio del editor. El cerebro (`jam.kit`) no sabe de discos ni de Unreal; acá se resuelve DÓNDE.
"""

from __future__ import annotations

import os

_SUBDIR = "Jam"
_ARCHIVO = "kit_pivotes.json"
_CARGADO = {"si": False}


def _carpeta() -> str | None:
    try:
        import unreal
        base = unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir())
    except Exception:  # noqa: BLE001
        return None
    ruta = os.path.join(base, _SUBDIR)
    try:
        os.makedirs(ruta, exist_ok=True)
    except OSError:
        return None
    return ruta


def ruta_kit() -> str | None:
    c = _carpeta()
    return os.path.join(c, _ARCHIVO) if c else None


def guardar_kit() -> str | None:
    from . import kit
    p = ruta_kit()
    if not p:
        return None
    try:
        with open(p, "w", encoding="utf-8") as f:
            f.write(kit.to_json())
        return p
    except OSError:
        return None


def cargar_kit(forzar: bool = False) -> int:
    """Lee el kit del disco (una vez por sesión, salvo `forzar`). Devuelve cuántos assets trae."""
    from . import kit
    if _CARGADO["si"] and not forzar:
        return len(kit.todos())
    _CARGADO["si"] = True
    p = ruta_kit()
    if not p or not os.path.exists(p):
        return 0
    try:
        with open(p, encoding="utf-8") as f:
            return kit.from_json(f.read())
    except OSError:
        return 0
