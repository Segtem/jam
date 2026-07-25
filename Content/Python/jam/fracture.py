"""Fracture — CONVIERTE un StaticMesh en un DESTRUCTIBLE (Geometry Collection de Chaos) vía Dataflow.
Es un CONVERSOR, no un colocador: produce la GC y la deja como asset (y como asset activo). Colocarla
es trabajo de `place` (que ya maneja GCs). Así compone limpio: `asset → fracture → place` = UN
destructible. Jam decide (qué malla, cuántos pedazos), Dataflow ejecuta (adaptador, como PCG), place
coloca, el oráculo verifica.

EDITOR-ONLY: la autoría de Dataflow CUELGA headless (`-RenderOffScreen`); corre con el editor real,
que es donde Jam vive. Receta VERIFICADA en el spike del barril
(jam/tools/experiments/dataflow_barrel_spike.py): `FUniformFractureDataflowNode` genera los sitios
Voronoi internamente (Min/MaxVoronoiSites — NO hace falta cablear `Points`), + `FProximityDataflowNode`
(grafo de conexión) para que ROMPA, + umbrales de daño bajos en el componente (los defaults son
enormes: {500000,50000,5000}).

PENDIENTE — modo HUECO (barril/piñata): hoy Voronoi rellena el volumen sólido → pedazos macizos. El
fix (PDF «Rigging Moderno»): mesh→volumen, booleana de vaciado (FMeshBooleanDataflowNode +
FMakeCylinderMeshDataflowNode), y recién ahí fracturar. Se agrega como `hollow=true`.
"""

from __future__ import annotations

import re

import unreal

from . import library

CARPETA = "/Game/JamDF/Fractures"


def _slug(n: str) -> str:
    return re.sub(r"[^A-Za-z0-9]+", "_", n).strip("_") or "GC"


def _setp(df, node, prop, value):
    if isinstance(value, bool):
        value = "true" if value else "false"
    if not unreal.DataflowEditorBlueprintLibrary.set_dataflow_node_property(df, node, prop, str(value)):
        raise RuntimeError(f"set {node}.{prop}")


def _conn(df, a, ao, b, bi):
    if not unreal.DataflowEditorBlueprintLibrary.connect_dataflow_nodes(df, a, ao, b, bi):
        raise RuntimeError(f"connect {a}.{ao} -> {b}.{bi}")


def _vec(x, y, z) -> str:
    return f"X={x:.6f} Y={y:.6f} Z={z:.6f}"


def _fuente_hueca(df, DFE, mesh, thickness):
    """Rama HUECA (piñata/barril): StaticMesh→Mesh → cilindro interior → Transform → Boolean Difference
    → MeshToCollection. Vacía el volumen antes de fracturar → rompe en CÁSCARA, no en macizo. Devuelve
    el nodo cuya salida «Collection» alimenta la fractura. Receta verificada por Codex contra la fuente
    del motor. Dimensiona el cilindro interior desde la bbox del mesh."""
    box = mesh.get_bounding_box()
    mn, mx = box.min, box.max
    sx, sy, sz = mx.x - mn.x, mx.y - mn.y, mx.z - mn.z
    cx, cy = (mn.x + mx.x) * 0.5, (mn.y + mx.y) * 0.5
    t = float(thickness)
    radius = max(0.1, min(sx, sy) * 0.5 - t)
    height = max(0.1, sz - 2.0 * t)

    V = unreal.Vector2D
    src = DFE.add_dataflow_node(df, "FStaticMeshToMeshDataflowNode", "src", V(0, 0))
    cyl = DFE.add_dataflow_node(df, "FMakeCylinderMeshDataflowNode", "cyl", V(0, 220))
    xfm = DFE.add_dataflow_node(df, "FTransformMeshDataflowNode", "xfm", V(240, 220))
    sub = DFE.add_dataflow_node(df, "FMeshBooleanDataflowNode", "hollow", V(480, 100))
    col = DFE.add_dataflow_node(df, "FMeshToCollectionDataflowNode", "col", V(720, 100))

    _setp(df, src, "StaticMesh", mesh.get_path_name())
    _setp(df, cyl, "Radius1", radius)
    _setp(df, cyl, "Radius2", radius)
    _setp(df, cyl, "Height", height)
    _setp(df, cyl, "AngleSamples", 48)
    _setp(df, xfm, "Translate", _vec(cx, cy, mn.z + t))
    _setp(df, sub, "Operation", "Dataflow_MeshBoolean_Difference")

    _conn(df, src, "Mesh", sub, "Mesh1")            # barril
    _conn(df, cyl, "Mesh", xfm, "Mesh")
    _conn(df, xfm, "Mesh", sub, "Mesh2")            # menos el cilindro interior
    _conn(df, sub, "Mesh", col, "Mesh")             # cáscara → colección
    return col


def fracturar(asset, *, sites: int = 20, seed: int = 123, hollow: bool = False,
              thickness: float = 4.0, carpeta: str = CARPETA) -> dict:
    """StaticMesh (path o objeto) → Geometry Collection FRACTURADA. Autora el grafo Dataflow, liga la
    GC (con su terminal — sin eso sale vacía) y la regenera. `hollow` vacía el volumen antes de
    fracturar (barril/piñata → rompe en cáscara, no en macizo); `thickness` = espesor de pared (cm).
    Devuelve {gc, ruta, sites} o {error}."""
    mesh = library.cargar_malla(asset) if isinstance(asset, str) else asset
    if mesh is None:
        return {"error": f"«{asset}» no es un StaticMesh (fracture necesita una malla)."}

    DFE = unreal.DataflowEditorBlueprintLibrary
    DFB = unreal.DataflowBlueprintLibrary
    at = unreal.AssetToolsHelpers.get_asset_tools()
    base = _slug(mesh.get_name())
    df_ruta, gc_ruta = f"{carpeta}/DF_{base}", f"{carpeta}/GC_{base}"
    for p in (df_ruta, gc_ruta):
        if unreal.EditorAssetLibrary.does_asset_exist(p):
            unreal.EditorAssetLibrary.delete_asset(p)

    df = at.create_asset(f"DF_{base}", carpeta, unreal.Dataflow, unreal.DataflowAssetFactory())
    V = unreal.Vector2D
    # La FUENTE de la colección: hueca (mesh→boolean→collection) o sólida (staticmesh→collection).
    if hollow:
        fuente = _fuente_hueca(df, DFE, mesh, thickness)   # nodo con salida «Collection»
    else:
        fuente = DFE.add_dataflow_node(df, "FStaticMeshToCollectionDataflowNode", "src", V(0, 0))
        _setp(df, fuente, "StaticMesh", mesh.get_path_name())

    sel  = DFE.add_dataflow_node(df, "FCollectionTransformSelectionAllDataflowNode", "sel", V(1000, 200))
    frac = DFE.add_dataflow_node(df, "FUniformFractureDataflowNode", "frac", V(1240, 60))
    prox = DFE.add_dataflow_node(df, "FProximityDataflowNode", "prox", V(1480, 60))
    term = DFE.add_dataflow_node(df, "FGeometryCollectionTerminalDataflowNode", "term", V(1720, 60))

    _setp(df, frac, "MinVoronoiSites", int(sites))
    _setp(df, frac, "MaxVoronoiSites", int(sites))
    _setp(df, frac, "RandomSeed", int(seed))
    _setp(df, frac, "ChanceToFracture", 1.0)
    _setp(df, frac, "SplitIslands", True)
    _setp(df, prox, "bUseAsConnectionGraph", True)

    _conn(df, fuente, "Collection", sel, "Collection")
    _conn(df, fuente, "Collection", frac, "Collection")
    _conn(df, sel, "TransformSelection", frac, "TransformSelection")
    _conn(df, frac, "Collection", prox, "Collection")
    _conn(df, prox, "Collection", term, "Collection")
    unreal.EditorAssetLibrary.save_asset(df_ruta, only_if_is_dirty=False)

    gc = at.create_asset(f"GC_{base}", carpeta, unreal.GeometryCollection, unreal.GeometryCollectionFactory())
    inst = gc.get_editor_property("dataflow_instance")
    inst.set_editor_property("dataflow_asset", df)
    inst.set_editor_property("dataflow_terminal", term)
    gc.set_editor_property("dataflow_instance", inst)
    if not DFB.regenerate_asset_from_dataflow(gc):
        return {"error": "regenerate del Dataflow falló."}
    # material del static mesh → la GC (si no, queda gris)
    try:
        mats = mesh.get_editor_property("static_materials")
        m0 = mats[0].get_editor_property("material_interface") if mats else None
        if m0:
            gc.set_editor_property("materials", [m0, m0])
    except Exception:  # noqa: BLE001
        pass
    unreal.EditorAssetLibrary.save_asset(gc_ruta, only_if_is_dirty=False)
    return {"gc": gc, "ruta": gc_ruta, "sites": int(sites)}


def gc_path_for(asset) -> str:
    """Ruta DETERMINISTA de la GC que `fracture` produce para un mesh dado. La usa el grafo para pasar
    la GC aguas abajo (a `place`), en vez del mesh original — `fracture` es un CONVERSOR, no coloca."""
    nombre = asset.rsplit("/", 1)[-1].split(".")[0] if isinstance(asset, str) else asset.get_name()
    return f"{CARPETA}/GC_{_slug(nombre)}"
