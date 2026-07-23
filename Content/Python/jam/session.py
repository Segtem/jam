"""Estado de sesión de Jam — el ASSET ACTIVO, compartido por todas las interfaces. Puro (0 unreal).

Content deja de ser "una grilla dentro de un panel" y pasa a ser un ESTADO del cerebro: la ventana
de Content, la línea de comando (`asset SM_Foo`) y el nodo `asset` del grafo escriben todos acá, y
cualquier herramienta que no reciba asset explícito hereda éste. Una sola fuente de verdad.
"""

from __future__ import annotations

_ACTIVO: dict = {"ruta": None, "nombre": None}


def set_asset(ruta: str | None, nombre: str | None = None) -> None:
    _ACTIVO["ruta"] = ruta or None
    _ACTIVO["nombre"] = nombre or (ruta.rsplit(".", 1)[-1] if ruta else None)


def asset() -> str | None:
    """ObjectPath del asset activo (o None)."""
    return _ACTIVO["ruta"]


def nombre() -> str | None:
    return _ACTIVO["nombre"]


def limpiar() -> None:
    set_asset(None)
