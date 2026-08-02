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


def asset_paths_for(asset, carpeta: str = CARPETA) -> tuple[str, str]:
    """Rutas finales deterministas (Dataflow, GeometryCollection) para una malla fuente."""
    nombre = asset.rsplit("/", 1)[-1].split(".")[0] if isinstance(asset, str) else asset.get_name()
    base = _slug(nombre)
    return f"{carpeta}/DF_{base}", f"{carpeta}/GC_{base}"


def _setp(df, node, prop, value):
    if isinstance(value, bool):
        value = "true" if value else "false"
    if not unreal.DataflowEditorBlueprintLibrary.set_dataflow_node_property(df, node, prop, str(value)):
        raise RuntimeError(f"set {node}.{prop}")


def _conn(df, a, ao, b, bi):
    if not unreal.DataflowEditorBlueprintLibrary.connect_dataflow_nodes(df, a, ao, b, bi):
        raise RuntimeError(f"connect {a}.{ao} -> {b}.{bi}")


def _setp_any(df, node, prop, valores):
    """Prueba varios valores para una prop (para enums donde no sé si toma el nombre o el DisplayName)."""
    for v in valores:
        if unreal.DataflowEditorBlueprintLibrary.set_dataflow_node_property(df, node, prop, str(v)):
            return
    raise RuntimeError(f"set {node}.{prop} (probé {valores})")


def _vec(x, y, z) -> str:
    # SetDataflowNodeProperty parsea FVector con FDefaultValueHelper::ParseVector → formato "x,y,z"
    # (comas), NO "X=.. Y=.. Z=..".
    return f"{x:.6f},{y:.6f},{z:.6f}"


def _usa_nanite(mesh) -> bool:
    """La GC es otro tipo de asset, pero debe heredar el modo de render de su StaticMesh fuente."""
    try:
        subsystem = unreal.get_editor_subsystem(unreal.StaticMeshEditorSubsystem)
        settings = subsystem.get_nanite_settings(mesh)
        return bool(settings.get_editor_property("enabled"))
    except Exception:  # noqa: BLE001
        return False


def _fuente_hueca(df, DFE, mesh, thickness):
    """Rama HUECA GENERAL (idea de Brian): le resta al modelo una COPIA de SÍ MISMO encogida hacia el
    centro → una CÁSCARA que sigue la silueta real, para CUALQUIER forma (barril, cajón, estatua), no
    sólo cilindros. Encoge con UniformScale=f alrededor de `ScalePivot`=centroide (el propio nodo hace
    la matemática del pivote). StaticMesh→Mesh → [Transform: encoge] → Boolean Difference (original −
    encogida) → MeshToCollection. Devuelve el nodo cuya salida «Collection» alimenta la fractura."""
    box = mesh.get_bounding_box()
    mn, mx = box.min, box.max
    sx, sy, sz = mx.x - mn.x, mx.y - mn.y, mx.z - mn.z
    cx, cy, cz = (mn.x + mx.x) * 0.5, (mn.y + mx.y) * 0.5, (mn.z + mx.z) * 0.5
    dmin = max(0.1, min(sx, sy, sz))
    # factor de encogido: la pared en la dimensión más chica ≈ thickness → f = 1 − 2·t/dmin
    f = max(0.05, 1.0 - 2.0 * float(thickness) / dmin)

    V = unreal.Vector2D
    src = DFE.add_dataflow_node(df, "FStaticMeshToMeshDataflowNode", "src", V(0, 0))
    xfm = DFE.add_dataflow_node(df, "FTransformMeshDataflowNode", "shrink", V(240, 220))
    sub = DFE.add_dataflow_node(df, "FMeshBooleanDataflowNode", "hollow", V(480, 100))
    col = DFE.add_dataflow_node(df, "FMeshToCollectionDataflowNode", "col", V(720, 100))

    _setp(df, src, "StaticMesh", mesh.get_path_name())
    _setp(df, xfm, "UniformScale", f)
    _setp(df, xfm, "ScalePivot", _vec(cx, cy, cz))     # escala alrededor del centroide
    _setp_any(df, sub, "Operation",
              ["Dataflow_MeshBoolean_Difference", "Difference",
               "EMeshBooleanOperationEnum::Dataflow_MeshBoolean_Difference"])

    _conn(df, src, "Mesh", sub, "Mesh1")     # original
    _conn(df, src, "Mesh", xfm, "Mesh")      # copia
    _conn(df, xfm, "Mesh", sub, "Mesh2")     # encogida hacia el centro
    _conn(df, sub, "Mesh", col, "Mesh")      # cáscara → colección
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
    df_final, gc_final = asset_paths_for(mesh, carpeta)
    # En Graph, panel registra ambos writers de Content y entrega rutas únicas bajo JamPreview. Así
    # un Run posterior jamás borra la GC que usa un actor ya baked. Fuera de Preview conserva el
    # comportamiento histórico de rutas deterministas.
    from . import panel
    df_ruta = panel.preview_asset_path(df_final)
    gc_ruta = panel.preview_asset_path(gc_final)
    for p in (df_ruta, gc_ruta):
        if unreal.EditorAssetLibrary.does_asset_exist(p):
            unreal.EditorAssetLibrary.delete_asset(p)

    df_carpeta, df_nombre = df_ruta.rsplit("/", 1)
    gc_carpeta, gc_nombre = gc_ruta.rsplit("/", 1)
    df = at.create_asset(df_nombre, df_carpeta, unreal.Dataflow, unreal.DataflowAssetFactory())
    V = unreal.Vector2D
    # La FUENTE de la colección: hueca (mesh→boolean→collection) o sólida (staticmesh→collection).
    if hollow:
        fuente = _fuente_hueca(df, DFE, mesh, thickness)   # nodo con salida «Collection»
        # El camino Mesh→boolean pierde metadata. Un conversor v2 paralelo provee únicamente el
        # array de materiales que el terminal necesita; su Collection no se usa.
        meta = DFE.add_dataflow_node(
            df, "FStaticMeshToCollectionDataflowNode_v2", "meta", V(720, 360))
        _setp(df, meta, "StaticMesh", mesh.get_path_name())
    else:
        fuente = DFE.add_dataflow_node(
            df, "FStaticMeshToCollectionDataflowNode_v2", "src", V(0, 0))
        _setp(df, fuente, "StaticMesh", mesh.get_path_name())
        meta = fuente

    sel  = DFE.add_dataflow_node(df, "FCollectionTransformSelectionAllDataflowNode", "sel", V(1000, 200))
    frac = DFE.add_dataflow_node(df, "FUniformFractureDataflowNode", "frac", V(1240, 60))
    prox = DFE.add_dataflow_node(df, "FProximityDataflowNode", "prox", V(1480, 60))
    term = DFE.add_dataflow_node(
        df, "FGeometryCollectionTerminalDataflowNode_v2", "term", V(1720, 60))

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
    # UE 5.8: el terminal v2 es quien persiste TODOS los materiales. Dejar este cable afuera y
    # asignar sólo el primer slot después fue la causa de las GCs grises/sin texturas.
    _conn(df, meta, "Materials", term, "Materials")
    if not hollow:
        _conn(df, meta, "InstancedMeshes", term, "InstancedMeshes")
        _conn(df, meta, "RootProxyMeshes", term, "RootProxyMeshes")
    unreal.EditorAssetLibrary.save_asset(df_ruta, only_if_is_dirty=False)

    gc = at.create_asset(
        gc_nombre, gc_carpeta, unreal.GeometryCollection, unreal.GeometryCollectionFactory())
    inst = gc.get_editor_property("dataflow_instance")
    inst.set_editor_property("dataflow_asset", df)
    inst.set_editor_property("dataflow_terminal", term)
    gc.set_editor_property("dataflow_instance", inst)
    # Fracture cambia el tipo de asset StaticMesh→GeometryCollection; no debe cambiar el modo de
    # render. Es el mismo contrato que usa Fracture Mode nativo de Epic al crear una GC.
    gc.set_editor_property("enable_nanite", _usa_nanite(mesh))
    if not DFB.regenerate_asset_from_dataflow(gc):
        return {"error": "regenerate del Dataflow falló."}
    unreal.EditorAssetLibrary.save_asset(gc_ruta, only_if_is_dirty=False)
    return {"gc": gc, "ruta": gc_ruta, "dataflow_ruta": df_ruta, "sites": int(sites)}


def gc_path_for(asset) -> str:
    """Ruta DETERMINISTA de la GC que `fracture` produce para un mesh dado. La usa el grafo para pasar
    la GC aguas abajo (a `place`), en vez del mesh original — `fracture` es un CONVERSOR, no coloca."""
    return asset_paths_for(asset)[1]
