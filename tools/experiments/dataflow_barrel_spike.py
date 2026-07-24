"""SPIKE (2026-07-24): barril DESTRUCTIBLE con Dataflow/Chaos, donde Jam sólo COLOCA. La AUTORÍA del
grafo está verificada contra la fuente del motor (Codex); el ROMPE-EN-PIE sigue EN DIAGNÓSTICO (con la
receta anterior sin puntos NO fracturaba; con puntos+proximity la GC tiene pedazos pero falta confirmar
que rompe al impacto). Correr en el editor INTERACTIVO (headless cuelga en FieldSystem/Dataflow).

EL BUG QUE COSTÓ (diagnosticado por Codex leyendo la fuente del motor): el barril fracturaba «vacío»
o caía entero por DOS motivos:
  1) FVoronoiFractureDataflowNode NO tiene una prop «NumSites»: tiene un INPUT `Points` (TArray<FVector>).
     Sin puntos NO corta (deja 1 pieza sólida). Hay que GENERAR los puntos:
        FBoundingBoxDataflowNode (de la colección) → FUniformScatterPointsDataflowNode_v2 (Min/MaxNumberOfPoints)
        → cablear `Points` al Voronoi.
  2) Para que ROMPA en PIE hace falta el GRAFO DE CONEXIÓN: un FProximityDataflowNode con
     bUseAsConnectionGraph=true. Y los umbrales de daño por defecto son ENORMES ({500000,50000,5000});
     hay que poner damage_model=USER_DEFINED_DAMAGE_THRESHOLD + damage_threshold bajo, clustering ON,
     object_type DYNAMIC, max_cluster_level/max_simulated_level altos, enable_damage_from_collision.
El material se lleva cableando `src.Materials`→`term.Materials` (+ InstancedMeshes) — si no, queda gris.

GOTCHAS de la API (todos verificados):
  - `set_dataflow_node_property(df, node, prop, VALOR)` toma el valor como STRING (object path para
    objetos; "true"/"false" para bools).
  - GC↔dataflow: `gc.dataflow_instance.dataflow_asset=df` + `.dataflow_terminal=<nombre del terminal>`;
    SIN el terminal la GC sale vacía (thumbnail damero). Luego `regenerate_asset_from_dataflow(gc)`.
  - Headless (`-RenderOffScreen`) CUELGA en `spawn(FieldSystemActor)` y corta en `add_dataflow_node`
    → correr con render real (DISPLAY del editor). Jam vive en el editor, así que está OK.
  - Conteo de pedazos: NO hay API Python (la GC no expone NumElements a py). En C++:
    `GC->GetGeometryCollection()->NumElements(FGeometryCollection::TransformGroup)`.

EXPLOSIÓN radial (pedazos disparados desde el centro) = PENDIENTE: es runtime — FieldSystemComponent
`apply_strain_field` (rompe) + `apply_radial_force` (empuja); necesita un disparador (BeginPlay de un BP).
Este spike deja el barril rompiéndose por IMPACTO; el estallido radial es el paso siguiente.

CÓMO CORRERLO (consola Python del editor):
  py exec(open("<ruta>/dataflow_barrel_spike.py").read())
"""
import unreal

MESH = "/Game/VictorianAlley/Meshes/SM_barrel_crates_single_barrel.SM_barrel_crates_single_barrel"
N_PEDAZOS = 20

DFE = unreal.DataflowEditorBlueprintLibrary
DFB = unreal.DataflowBlueprintLibrary
AT = unreal.AssetToolsHelpers.get_asset_tools()


def log(m):
    unreal.log("[barrel-spike] " + m)


def _setp(df, node, prop, value):
    if isinstance(value, bool):
        value = "true" if value else "false"
    if not DFE.set_dataflow_node_property(df, node, prop, str(value)):
        raise RuntimeError("set %s.%s falló" % (node, prop))


def _conn(df, a, ao, b, bi):
    if not DFE.connect_dataflow_nodes(df, a, ao, b, bi):
        raise RuntimeError("connect %s.%s -> %s.%s falló" % (a, ao, b, bi))


def autorar_fractura(mesh_path=MESH, ruta="/Game/JamDF/BarrelFrac", n=N_PEDAZOS):
    """Grafo Dataflow que SÍ fractura: StaticMesh_v2 → BoundingBox → UniformScatterPoints_v2 →
    VoronoiFracture_v2(Points) → Proximity(connection graph) → Terminal_v2(+Materials/+InstancedMeshes).
    Devuelve (df, nombre_del_terminal). CORRER EN EDITOR."""
    mesh = unreal.load_asset(mesh_path)
    carpeta, nombre = ruta.rsplit("/", 1)
    if unreal.EditorAssetLibrary.does_asset_exist(ruta):
        unreal.EditorAssetLibrary.delete_asset(ruta)
    df = AT.create_asset(nombre, carpeta, unreal.Dataflow, unreal.DataflowAssetFactory())

    V = unreal.Vector2D
    src  = DFE.add_dataflow_node(df, "FStaticMeshToCollectionDataflowNode_v2", "src",  V(0, 0))
    bbox = DFE.add_dataflow_node(df, "FBoundingBoxDataflowNode",               "bbox", V(220, 0))
    pts  = DFE.add_dataflow_node(df, "FUniformScatterPointsDataflowNode_v2",   "pts",  V(440, 0))
    frac = DFE.add_dataflow_node(df, "FVoronoiFractureDataflowNode_v2",        "frac", V(660, 0))
    prox = DFE.add_dataflow_node(df, "FProximityDataflowNode",                 "prox", V(880, 0))
    term = DFE.add_dataflow_node(df, "FGeometryCollectionTerminalDataflowNode_v2", "term", V(1100, 0))

    _setp(df, src, "StaticMesh", mesh.get_path_name())
    _setp(df, pts, "MinNumberOfPoints", n)
    _setp(df, pts, "MaxNumberOfPoints", n)
    _setp(df, pts, "RandomSeed", 123)
    _setp(df, frac, "ChanceToFracture", 1.0)
    _setp(df, frac, "SplitIslands", True)
    _setp(df, prox, "bUseAsConnectionGraph", True)

    _conn(df, src, "Collection", bbox, "Collection")
    _conn(df, bbox, "BoundingBox", pts, "BoundingBox")
    _conn(df, src, "Collection", frac, "Collection")
    _conn(df, pts, "Points", frac, "Points")
    _conn(df, frac, "Collection", prox, "Collection")
    _conn(df, prox, "Collection", term, "Collection")
    _conn(df, src, "Materials", term, "Materials")
    _conn(df, src, "InstancedMeshes", term, "InstancedMeshes")
    unreal.EditorAssetLibrary.save_asset(ruta, only_if_is_dirty=False)
    log("grafo de fractura autorado (con puntos + proximity): " + ruta)
    return df, term


def generar_gc(df, terminal, ruta="/Game/JamDF/BarrelGC"):
    """Crea la GeometryCollection, la liga al dataflow + FIJA EL TERMINAL (sin esto sale vacía) y la
    regenera. Devuelve la GC ya con geometría fracturada."""
    carpeta, nombre = ruta.rsplit("/", 1)
    if unreal.EditorAssetLibrary.does_asset_exist(ruta):
        unreal.EditorAssetLibrary.delete_asset(ruta)
    gc = AT.create_asset(nombre, carpeta, unreal.GeometryCollection, unreal.GeometryCollectionFactory())
    inst = gc.get_editor_property("dataflow_instance")
    inst.set_editor_property("dataflow_asset", df)
    inst.set_editor_property("dataflow_terminal", terminal)
    gc.set_editor_property("dataflow_instance", inst)
    assert DFB.regenerate_asset_from_dataflow(gc), "regenerate falló"
    unreal.EditorAssetLibrary.save_asset(ruta, only_if_is_dirty=False)
    log("GC regenerada: " + ruta)
    return gc


def colocar_barril_destructible(gc, centro):
    """El rol de JAM: colocar el GeometryCollectionActor con las props que hacen que ROMPA AL IMPACTO
    (umbrales bajos + clustering + connection graph ya en la GC). Devuelve el actor."""
    sub = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    actor = sub.spawn_actor_from_class(unreal.GeometryCollectionActor, centro)
    comp = actor.get_component_by_class(unreal.GeometryCollectionComponent)
    comp.set_rest_collection(gc, True)   # aplica defaults del asset; los de daño se pisan DESPUÉS
    comp.set_simulate_physics(True)

    def sp(prop, val):
        try:
            comp.set_editor_property(prop, val)
        except Exception as e:  # noqa: BLE001
            log("%s: %s" % (prop, type(e).__name__))

    sp("object_type", getattr(unreal.ObjectStateTypeEnum, "CHAOS_OBJECT_DYNAMIC", None))
    sp("enable_clustering", True)
    sp("max_cluster_level", 100)
    sp("max_simulated_level", 100)
    sp("damage_model", getattr(unreal.DamageModelTypeEnum,
                               "CHAOS_DAMAGE_MODEL_USER_DEFINED_DAMAGE_THRESHOLD", None))
    comp.set_enable_damage_from_collision(True)
    comp.set_damage_threshold([0.0])
    log("colocado: barril destructible (rompe al caer/impacto). Dale Play.")
    return actor


def main():
    df, term = autorar_fractura()
    gc = generar_gc(df, term)
    colocar_barril_destructible(gc, unreal.Vector(0, 0, 350))
    log("FIN — grafo autorado; el ROMPE-EN-PIE está en diagnóstico.")


if __name__ == "__main__":
    main()
