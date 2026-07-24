"""Biblioteca — el "Content Browser" de Jam: buscar assets del proyecto para colocar.

Equivalente al Content Browser de Dash, acotado a lo que ya vive en el proyecto (AssetRegistry).
Devuelve StaticMesh; el que coloca (`jam.place`) los spawnea.

Además del listado, expone el CONTEO REAL y las CARPETAS (con cuántas mallas tiene cada una): sin
eso la UI muestra "los primeros N" y parece que faltan assets. La ventana de Content usa
`carpetas()` como árbol y `buscar()` con `carpeta=` para filtrar.
"""

from __future__ import annotations

import unreal

_SM_CLASS = unreal.TopLevelAssetPath("/Script/Engine", "StaticMesh")


def _registry() -> unreal.AssetRegistry:
    return unreal.AssetRegistryHelpers.get_asset_registry()


def _todos(raiz: str = "/Game") -> list[dict]:
    """Todas las StaticMesh bajo `raiz` como dicts {'nombre','ruta','carpeta'} (sin filtrar ni cortar)."""
    filt = unreal.ARFilter(
        class_paths=[_SM_CLASS], package_paths=[raiz], recursive_paths=True,
    )
    out: list[dict] = []
    for ad in _registry().get_assets(filt):
        nombre = str(ad.asset_name)
        paquete = str(ad.package_name)
        out.append({"nombre": nombre,
                    "ruta": f"{paquete}.{nombre}",
                    "carpeta": paquete.rsplit("/", 1)[0]})
    return out


def buscar(query: str = "", *, limit: int = 25, raiz: str = "/Game",
           carpeta: str = "") -> list[dict]:
    """StaticMesh cuyo nombre contenga `query` (case-insensitive), opcionalmente dentro de `carpeta`.
    Devuelve dicts {'nombre','ruta','carpeta'} ordenados por nombre. `limit<=0` = sin tope."""
    return _filtrar(_todos(raiz), query, carpeta)[:limit] if limit > 0 \
        else _filtrar(_todos(raiz), query, carpeta)


def _filtrar(assets: list[dict], query: str, carpeta: str) -> list[dict]:
    q = (query or "").lower()
    c = (carpeta or "").rstrip("/")
    out = [a for a in assets
           if (not q or q in a["nombre"].lower())
           and (not c or a["carpeta"] == c or a["carpeta"].startswith(c + "/"))]
    out.sort(key=lambda d: d["nombre"].lower())
    return out


def carpetas(raiz: str = "/Game") -> list[dict]:
    """Carpetas que contienen StaticMesh, con su conteo: el «árbol» del Content browser.
    Ordenadas por cantidad (las gordas primero) — así los packs grandes saltan a la vista."""
    cuenta: dict[str, int] = {}
    for a in _todos(raiz):
        cuenta[a["carpeta"]] = cuenta.get(a["carpeta"], 0) + 1
    out = [{"ruta": k, "nombre": k[len(raiz) + 1:] or k, "count": v} for k, v in cuenta.items()]
    out.sort(key=lambda d: (-d["count"], d["ruta"]))
    return out


def buscar_json(query: str = "", *, limit: int = 200, carpeta: str = "") -> str:
    """Lo que consume el Content browser (C++ y web):
    {"total": cuántos matchean, "shown": cuántos van, "folders": [...], "assets": [...]}.
    `total` vs `shown` es lo que evita el "no veo todos los mesh"."""
    import json
    todos = _todos()
    hits = _filtrar(todos, query, carpeta)
    vista = hits[:limit] if limit > 0 else hits
    return json.dumps({"total": len(hits),
                       "shown": len(vista),
                       "all": len(todos),
                       "folders": carpetas(),
                       "assets": vista}, ensure_ascii=True)


def seleccion_ue() -> list[dict]:
    """Lo que está SELECCIONADO ahora mismo en el Content Browser de Unreal (sólo StaticMesh), como
    {'nombre','ruta','carpeta'}. Puente con el flujo normal del editor: elegís la malla donde
    siempre y Jam la toma, sin duplicar la navegación."""
    try:
        sel = unreal.EditorUtilityLibrary.get_selected_assets()
    except Exception:  # noqa: BLE001
        return []
    out: list[dict] = []
    for obj in sel or []:
        if not isinstance(obj, unreal.StaticMesh):
            continue
        paquete = obj.get_outer().get_path_name()
        out.append({"nombre": obj.get_name(),
                    "ruta": f"{paquete}.{obj.get_name()}",
                    "carpeta": paquete.rsplit("/", 1)[0]})
    return out


def cargar_malla(ruta: str) -> unreal.StaticMesh | None:
    """Carga el StaticMesh por su ObjectPath. None si no existe."""
    obj = unreal.load_asset(ruta)
    return obj if isinstance(obj, unreal.StaticMesh) else None


def es_geometry_collection(obj) -> bool:
    """¿Es una Geometry Collection (el asset destructible de Chaos)?"""
    return isinstance(obj, unreal.GeometryCollection)


def cargar_placeable(ruta: str):
    """Carga un asset COLOCABLE por su ObjectPath: StaticMesh (spawnea StaticMeshActor) o
    GeometryCollection (spawnea GeometryCollectionActor destructible). None si no es ninguno.
    `spawn_actor_from_object` elige el actor según el tipo — Jam sólo tiene que cargar el asset."""
    obj = unreal.load_asset(ruta)
    if isinstance(obj, (unreal.StaticMesh, unreal.GeometryCollection)):
        return obj
    return None
