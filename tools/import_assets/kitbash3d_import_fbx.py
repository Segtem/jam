import unreal, os, glob
FBX = "/home/workstation/Dev/assets/KitBash3D/Victorian/Victorian.fbx"
DEST = "/Game/KitBash3D/Victorian"
tools = unreal.AssetToolsHelpers.get_asset_tools()

# 1) importar el FBX (meshes separados + materiales + texturas que referencie)
task = unreal.AssetImportTask()
task.filename = FBX
task.destination_path = DEST
task.automated = True
task.save = True
task.replace_existing = True
ui = unreal.FbxImportUI()
ui.import_mesh = True
ui.import_as_skeletal = False
ui.import_materials = True
ui.import_textures = True
ui.mesh_type_to_import = unreal.FBXImportType.FBXIT_STATIC_MESH
ui.static_mesh_import_data.set_editor_property("combine_meshes", False)
ui.static_mesh_import_data.set_editor_property("import_uniform_scale", 1.0)
task.options = ui
unreal.log("[KB] importando FBX (puede tardar)...")
tools.import_asset_tasks([task])
imported = list(task.get_objects_exported() if hasattr(task,'get_objects_exported') else (task.imported_object_paths or []))
unreal.log(f"[KB] import terminado. objetos: {len(task.imported_object_paths or [])}")

# 2) contar StaticMeshes resultantes
ar = unreal.AssetRegistryHelpers.get_asset_registry()
ar.scan_paths_synchronous([DEST], force_rescan=True)
SM = unreal.TopLevelAssetPath("/Script/Engine","StaticMesh")
metas = ar.get_assets(unreal.ARFilter(class_paths=[SM], package_paths=[DEST], recursive_paths=True))
unreal.log(f"[KB] StaticMeshes en {DEST}: {len(metas)}")
for ad in list(metas)[:5]:
    unreal.log(f"[KB]   · {ad.asset_name}")
# materiales
MI = unreal.TopLevelAssetPath("/Script/Engine","Material")
mats = ar.get_assets(unreal.ARFilter(class_paths=[MI], package_paths=[DEST], recursive_paths=True))
unreal.log(f"[KB] Materials importados: {len(mats)}")
unreal.log("[KB] fin")
