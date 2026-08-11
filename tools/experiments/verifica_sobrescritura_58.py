"""Sobrescribir un StaticMesh con Geometry Script: ¿REEMPLAZA o ACUMULA?

El ping-pong de ranuras apuesta a que escribir sobre una ruta ocupada reemplaza el asset. Medir el
tiempo dio una señal que contradice esa apuesta: sobrescribir cuesta 37–86 ms contra 5 de crear, y
**crece con cada vuelta**. Un costo que crece es lo que se ve cuando algo se acumula adentro del
paquete en vez de reemplazarse.

Si acumula, el ping-pong tiene un bug de correctitud —el Preview mostraría geometría vieja, o el
Bake promovería el objeto equivocado— y hay que cambiar el diseño. Un ahorro que devuelve el
resultado incorrecto no es un ahorro.

Se cocina la MISMA ruta con anchos distintos y se pregunta por el resultado, no por el reloj:
¿las cotas del asset siguen al último ancho pedido, o se quedaron en el primero?
"""
import unreal

CARPETA = "/Game/JamSobrescritura"
RUTA = f"{CARPETA}/PV_Prueba"

def log(m):
    unreal.log(f"[SOBRESCRIBE] {m}")

FALLAS = []

def exigir(condicion, descripcion):
    log(("  OK   " if condicion else "  FALLA") + f" · {descripcion}")
    if not condicion:
        FALLAS.append(descripcion)


def caja(ancho):
    m = unreal.DynamicMesh()
    return unreal.GeometryScript_Primitives.append_box(
        m, unreal.GeometryScriptPrimitiveOptions(), unreal.Transform(),
        dimension_x=float(ancho), dimension_y=100.0, dimension_z=100.0)


def escribir(ancho):
    o = unreal.GeometryScriptCreateNewStaticMeshAssetOptions()
    o.set_editor_property("enable_recompute_normals", False)
    o.set_editor_property("enable_recompute_tangents", False)
    resultado = unreal.GeometryScript_NewAssetUtils.create_new_static_mesh_asset_from_mesh(
        caja(ancho), RUTA, o)
    creado = resultado[0] if isinstance(resultado, tuple) else resultado
    unreal.EditorAssetLibrary.save_asset(RUTA, only_if_is_dirty=False)
    return creado


def ancho_en_disco():
    """Lo que un consumidor vería: se recarga por RUTA, no se usa el objeto devuelto."""
    asset = unreal.EditorAssetLibrary.load_asset(RUTA)
    if asset is None:
        return None
    cotas = asset.get_bounding_box()
    return float(cotas.max.x - cotas.min.x)


def objetos_en_el_paquete():
    """Cuántos StaticMesh viven en el paquete. Si crece, cada cocción dejó el anterior adentro."""
    paquete = unreal.find_package(RUTA)
    if paquete is None:
        return -1
    return len([o for o in unreal.find_objects_in_package(paquete)
                if isinstance(o, unreal.StaticMesh)]) if hasattr(unreal, "find_objects_in_package") else -1


log("=" * 78)
try:
    unreal.EditorAssetLibrary.delete_directory(CARPETA)
except Exception:  # noqa: BLE001
    pass

ANCHOS = (100.0, 300.0, 700.0, 1500.0)
log(f"{'vuelta':>7} {'ancho pedido':>13} {'ancho en disco':>15} {'objeto devuelto':>16}")
log("-" * 78)
devueltos = []
for vuelta, ancho in enumerate(ANCHOS):
    creado = escribir(ancho)
    devueltos.append(creado.get_path_name() if creado is not None else "None")
    en_disco = ancho_en_disco()
    log(f"{vuelta:>7} {ancho:13.0f} {(en_disco if en_disco is not None else -1):15.1f} "
        f"{devueltos[-1].rsplit('/', 1)[-1]:>16}")

log("-" * 78)
final = ancho_en_disco()
exigir(final is not None and abs(final - ANCHOS[-1]) < 1.0,
       f"el asset en disco tiene la geometría de la ÚLTIMA cocción "
       f"(esperado {ANCHOS[-1]:.0f}, encontrado {final})")
exigir(len(set(devueltos)) == 1,
       f"cada cocción devuelve EL MISMO objeto y no uno nuevo por vuelta "
       f"({len(set(devueltos))} distintos: {sorted(set(devueltos))[:3]})")

en_carpeta = unreal.EditorAssetLibrary.list_assets(CARPETA, recursive=True, include_folder=False)
exigir(len(en_carpeta) == 1,
       f"sobrescribir no deja assets extra en la carpeta ({len(en_carpeta)}: {en_carpeta})")

try:
    unreal.EditorAssetLibrary.delete_directory(CARPETA)
except Exception:  # noqa: BLE001
    pass
log("JAM_SOBRESCRIBE_58 TODO VERDE" if not FALLAS else f"JAM_SOBRESCRIBE_58 ROJO — {len(FALLAS)}")
