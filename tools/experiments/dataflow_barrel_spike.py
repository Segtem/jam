"""SPIKE (2026-07-24): barril DESTRUCTIBLE con Dataflow/Chaos + explosión, donde Jam sólo COLOCA.

Pregunta de Brian: ¿se puede un barril + explosión con Dataflow, y Jam sólo lo coloca?
RESPUESTA MEDIDA: SÍ es scripteable de punta a punta — PERO hay que correrlo en el editor
INTERACTIVO, no headless (dos operaciones cuelgan/crashean sin GUI, y la simulación de física
sólo corre en PIE). Es el mismo patrón que el gotcha del landscape en pcg_spike.py.

QUÉ SE MIDIÓ (headless, `-RenderOffScreen`):
  ✓ Dataflow ES scripteable: `unreal.DataflowAssetFactory` crea el asset;
    `DataflowEditorBlueprintLibrary.add_dataflow_node / connect_dataflow_nodes /
    set_dataflow_node_property` autoran el grafo; `DataflowBlueprintLibrary.
    evaluate_terminal_node_by_name / regenerate_asset_from_dataflow / override_dataflow_variable_*`
    lo evalúan (las variables = nuestros number/text).
  ✓ El barril existe: SM_barrel_crates_group_a (VictorianAlley).
  ✓ `GeometryCollectionActor` COLOCA bien headless (el rol de «colocar» de Jam).
  ✓ `RadialFalloff` (strain: rompe) y `RadialVector` (impulso: dispersa) son instanciables — la
    explosión de Chaos es un FieldSystem con esos dos campos.
  ✗ HEADLESS CUELGA: `spawn_actor_from_class(unreal.FieldSystemActor, ...)` no retorna (exit 124).
  ✗ HEADLESS CORTA: `add_dataflow_node` sobre el asset recién creado corta la corrida (API de editor
    Experimental que espera el editor de Dataflow abierto).
  → La explosión (física Chaos) sólo se ve en PIE de todos modos. Jam vive EN el editor, así que
    esto corre donde tiene que correr; el headless es sólo el banco de pruebas y acá no aplica.

TIPOS DE NODO (registrados, para add_dataflow_node) y PINES (para connect):
  FStaticMeshToCollectionDataflowNode   (prop StaticMesh)      out: "Collection"
  FCollectionTransformSelectionAllDataflowNode                 in/out: "Collection"/"TransformSelection"
  FVoronoiFractureDataflowNode          in: "Collection","TransformSelection"  out: "Collection"
  FUniformFractureDataflowNode          (alternativa a Voronoi)
  FGeometryCollectionTerminalDataflowNode  (terminal: escribe la GC)  in: "Collection"
El pin de colección estándar se llama "Collection".

CÓMO CORRERLO (en el editor GUI, Tools → o consola Python del editor):
  py exec(open("<ruta>/dataflow_barrel_spike.py").read())
"""

import unreal


def log(m):
    unreal.log("[barrel-spike] " + m)


def autorar_fractura(static_mesh, ruta="/Game/JamDF/BarrelFrac"):
    """Autora un grafo Dataflow: StaticMesh → (selección) → VoronoiFracture → Terminal.
    Devuelve el UDataflow. CORRER EN EDITOR INTERACTIVO (headless cuelga)."""
    DFE = unreal.DataflowEditorBlueprintLibrary
    at = unreal.AssetToolsHelpers.get_asset_tools()
    carpeta, nombre = ruta.rsplit("/", 1)
    if unreal.EditorAssetLibrary.does_asset_exist(ruta):
        unreal.EditorAssetLibrary.delete_asset(ruta)
    df = at.create_asset(nombre, carpeta, unreal.Dataflow, unreal.DataflowAssetFactory())

    v = unreal.Vector2D
    n_src = DFE.add_dataflow_node(df, "FStaticMeshToCollectionDataflowNode", "src", v(0, 0))
    n_sel = DFE.add_dataflow_node(df, "FCollectionTransformSelectionAllDataflowNode", "sel", v(200, 120))
    n_fr = DFE.add_dataflow_node(df, "FVoronoiFractureDataflowNode", "frac", v(400, 0))
    n_tm = DFE.add_dataflow_node(df, "FGeometryCollectionTerminalDataflowNode", "term", v(620, 0))

    DFE.set_dataflow_node_property(df, n_src, "StaticMesh", static_mesh)
    DFE.connect_dataflow_nodes(df, n_src, "Collection", n_sel, "Collection")
    DFE.connect_dataflow_nodes(df, n_src, "Collection", n_fr, "Collection")
    DFE.connect_dataflow_nodes(df, n_sel, "TransformSelection", n_fr, "TransformSelection")
    DFE.connect_dataflow_nodes(df, n_fr, "Collection", n_tm, "Collection")
    unreal.EditorAssetLibrary.save_asset(ruta, only_if_is_dirty=False)
    log("grafo de fractura autorado: " + ruta)
    return df


def generar_gc(df, ruta="/Game/JamDF/BarrelGC"):
    """Crea una GeometryCollection, la liga al dataflow `df` Y —EL FIX CLAVE— fija el nodo TERMINAL en
    su DataflowInstance; sin el terminal, `regenerate` corre pero deja la GC VACÍA (thumbnail damero).
    Devuelve la GC ya con geometría fracturada. CORRER EN EDITOR."""
    at = unreal.AssetToolsHelpers.get_asset_tools()
    carpeta, nombre = ruta.rsplit("/", 1)
    if unreal.EditorAssetLibrary.does_asset_exist(ruta):
        unreal.EditorAssetLibrary.delete_asset(ruta)
    gc = at.create_asset(nombre, carpeta, unreal.GeometryCollection, unreal.GeometryCollectionFactory())
    inst = gc.get_editor_property("dataflow_instance")   # FDataflowInstance
    inst.set_editor_property("dataflow_asset", df)
    inst.set_editor_property("dataflow_terminal", "term")  # nombre del FGeometryCollectionTerminal
    gc.set_editor_property("dataflow_instance", inst)
    unreal.DataflowBlueprintLibrary.regenerate_asset_from_dataflow(gc)
    unreal.EditorAssetLibrary.save_asset(ruta, only_if_is_dirty=False)
    log("GC regenerada: " + ruta + " (verificar bounds != 0 = hay geometría)")
    return gc


def colocar_barril_destructible(gc_asset, centro):
    """El rol de JAM: colocar un GeometryCollectionActor (la GC fracturada) + un FieldSystemActor con
    RadialFalloff (strain=rompe) + RadialVector (impulso=dispersa) = la explosión. CORRER EN EDITOR."""
    sub = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    gc = sub.spawn_actor_from_class(unreal.GeometryCollectionActor, centro)
    comp = gc.get_component_by_class(unreal.GeometryCollectionComponent)
    if gc_asset is not None:
        comp.set_editor_property("rest_collection", gc_asset)
    # ROMPE AL CAER: enable_damage_from_collision estaba en False → caía entero. Con esto + umbral 0
    # se hace pedazos al impactar el piso (el «cae pero no rompe» de Brian).
    comp.set_editor_property("enable_clustering", True)
    comp.set_editor_property("enable_damage_from_collision", True)
    comp.set_editor_property("damage_threshold", [0.0])
    # ESTALLIDO (opcional): velocidad/giro iniciales. El enum es CHAOS_INITIAL_VELOCITY_USER_DEFINED.
    comp.set_editor_property("initial_velocity_type",
                             unreal.InitialVelocityTypeEnum.CHAOS_INITIAL_VELOCITY_USER_DEFINED)
    comp.set_editor_property("initial_linear_velocity", unreal.Vector(0, 0, 500))
    comp.set_editor_property("initial_angular_velocity", unreal.Vector(0, 0, 720))

    # Field system de Chaos: la explosión REAL (radial) es runtime — FieldSystemComponent.
    # apply_strain_field (rompe) + apply_radial_force (empuja). Necesita un disparador (BeginPlay de un
    # BP) para dispararse SOLA en Play; para el demo alcanza el rompe-al-caer de arriba.
    campo = sub.spawn_actor_from_class(unreal.FieldSystemActor, centro)
    log("colocado: barril destructible (rompe al caer) + FieldSystem. Dale Play.")
    return gc, campo


def main():
    import jam.library as library
    # UN barril SOLO (no el _group_a, que son varios barriles+cajones y no se lee como destructible)
    barril = library.buscar("SM_barrel_crates_single_barrel", limit=1)[0]
    sm = unreal.load_asset(barril["ruta"])
    log("barril: " + barril["nombre"])
    df = autorar_fractura(sm)
    gc = generar_gc(df)   # VERIFICADO: bounds (88.7, 70.2, 93.3) = geometría fracturada
    colocar_barril_destructible(gc, unreal.Vector(0, 0, 300))
    log("FIN — recordá: correr en el editor GUI (headless cuelga en FieldSystem/Dataflow)")


if __name__ == "__main__":
    main()
