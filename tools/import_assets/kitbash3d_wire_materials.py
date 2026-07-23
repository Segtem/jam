import unreal, os, glob
KB = "/home/workstation/Dev/assets/KitBash3D/Victorian"
DEST = "/Game/KitBash3D/Victorian"
TEXDIR = DEST + "/Textures"
tools = unreal.AssetToolsHelpers.get_asset_tools()
MEL = unreal.MaterialEditingLibrary
EAL = unreal.EditorAssetLibrary
CANALES = ("basecolor","normal","roughness","metallic")

# --- 1) importar las 48 texturas ---
files = sorted(glob.glob(os.path.join(KB, "Textures*", "KB3D_VIC_*.png")))
tasks = []
for fp in files:
    t = unreal.AssetImportTask()
    t.filename = fp; t.destination_path = TEXDIR
    t.automated = True; t.save = True; t.replace_existing = True
    tasks.append(t)
unreal.log(f"[MAT] importando {len(tasks)} texturas...")
tools.import_asset_tasks(tasks)
ar = unreal.AssetRegistryHelpers.get_asset_registry()
ar.scan_paths_synchronous([TEXDIR], force_rescan=True)

def tex(nombre, canal):
    return EAL.load_asset(f"{TEXDIR}/KB3D_VIC_{nombre}_{canal}")

# settings correctos por canal (normal=normalmap, no-color=linear)
grupos = sorted(set(os.path.basename(f).rsplit("_",1)[0].replace("KB3D_VIC_","") for f in files))
for g in grupos:
    for c in CANALES:
        a = tex(g, c)
        if not a: continue
        if c == "normal":
            a.set_editor_property("compression_settings", unreal.TextureCompressionSettings.TC_NORMALMAP)
            a.set_editor_property("srgb", False)
        elif c in ("roughness","metallic"):
            a.set_editor_property("srgb", False)
        EAL.save_loaded_asset(a)
unreal.log(f"[MAT] {len(grupos)} grupos: " + ", ".join(grupos))

# --- 2) master material ---
master_path = DEST + "/M_KB3D_Master"
if EAL.does_asset_exist(master_path):
    master = EAL.load_asset(master_path)
else:
    master = tools.create_asset("M_KB3D_Master", DEST, unreal.Material, unreal.MaterialFactoryNew())
    d = grupos[0]  # defaults desde el 1er grupo para que compile
    bc = MEL.create_material_expression(master, unreal.MaterialExpressionTextureSampleParameter2D, -500, -200)
    bc.set_editor_property("parameter_name", "BaseColor"); bc.set_editor_property("texture", tex(d,"basecolor"))
    MEL.connect_material_property(bc, "RGB", unreal.MaterialProperty.MP_BASE_COLOR)
    nm = MEL.create_material_expression(master, unreal.MaterialExpressionTextureSampleParameter2D, -500, 60)
    nm.set_editor_property("parameter_name", "Normal"); nm.set_editor_property("sampler_type", unreal.MaterialSamplerType.SAMPLERTYPE_NORMAL); nm.set_editor_property("texture", tex(d,"normal"))
    MEL.connect_material_property(nm, "RGB", unreal.MaterialProperty.MP_NORMAL)
    rg = MEL.create_material_expression(master, unreal.MaterialExpressionTextureSampleParameter2D, -500, 320)
    rg.set_editor_property("parameter_name", "Roughness"); rg.set_editor_property("sampler_type", unreal.MaterialSamplerType.SAMPLERTYPE_LINEAR_GRAYSCALE); rg.set_editor_property("texture", tex(d,"roughness"))
    MEL.connect_material_property(rg, "R", unreal.MaterialProperty.MP_ROUGHNESS)
    mt = MEL.create_material_expression(master, unreal.MaterialExpressionTextureSampleParameter2D, -500, 580)
    mt.set_editor_property("parameter_name", "Metallic"); mt.set_editor_property("sampler_type", unreal.MaterialSamplerType.SAMPLERTYPE_LINEAR_GRAYSCALE); mt.set_editor_property("texture", tex(d,"metallic"))
    MEL.connect_material_property(mt, "R", unreal.MaterialProperty.MP_METALLIC)
    MEL.recompile_material(master)
    EAL.save_loaded_asset(master)
unreal.log("[MAT] master OK")

# --- 3) 12 material instances ---
mi_de = {}
for g in grupos:
    mip = f"{DEST}/MI_KB3D_VIC_{g}"
    mi = EAL.load_asset(mip) if EAL.does_asset_exist(mip) else tools.create_asset(f"MI_KB3D_VIC_{g}", DEST, unreal.MaterialInstanceConstant, unreal.MaterialInstanceConstantFactoryNew())
    MEL.set_material_instance_parent(mi, master)
    for pn, cn in (("BaseColor","basecolor"),("Normal","normal"),("Roughness","roughness"),("Metallic","metallic")):
        a = tex(g, cn)
        if a: MEL.set_material_instance_texture_parameter_value(mi, pn, a)
    EAL.save_loaded_asset(mi)
    mi_de[g] = mi
unreal.log(f"[MAT] {len(mi_de)} material instances creadas")

# --- 4) asignar a los meshes por nombre de slot ---
SM = unreal.TopLevelAssetPath("/Script/Engine","StaticMesh")
metas = ar.get_assets(unreal.ARFilter(class_paths=[SM], package_paths=[DEST], recursive_paths=True))
asign = 0
for ad in metas:
    m = EAL.load_asset(f"{ad.package_name}.{ad.asset_name}")
    if not isinstance(m, unreal.StaticMesh): continue
    cambiado = False
    for i, sm in enumerate(m.static_materials):
        nombre = str(sm.material_slot_name).replace("KB3D_VIC_","")
        if nombre in mi_de:
            m.set_material(i, mi_de[nombre]); asign += 1; cambiado = True
    if cambiado: EAL.save_loaded_asset(m)
unreal.log(f"[MAT] slots asignados: {asign}")
unreal.log("[MAT] fin")
