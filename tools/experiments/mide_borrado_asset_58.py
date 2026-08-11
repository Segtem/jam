"""¿Los 142 ms de borrar un asset son inevitables, o es la primitiva elegida?

`mide_asset_staging_58.py` dejó el costo ubicado pero no explicado: `delete_asset` cuesta ~142 ms y
el costo es por LLAMADA, no por asset —ocho sueltos cuestan 1146 ms y los mismos ocho en una pasada
de `delete_directory` cuestan 208 ms—. Eso huele a una pasada cara y fija adentro de cada borrado
(escaneo de referencias, recolección), no al trabajo de tirar un StaticMesh de 12 triángulos.

Si hay una forma más barata de sacar el asset de en medio, el arreglo es cambiar una línea en vez de
rediseñar el staging. Vale descartarlo antes de tocar la semántica transaccional del Preview, que es
una propiedad que alguien diseñó a propósito.

⚠️ La primera versión de esta sonda daba `delete_asset` = **0.0 ms**. Componía la ruta del asset con
el nombre visible de cada método —espacios y paréntesis adentro—, así que la ruta era inválida, el
asset nunca se creaba, y lo que medía era borrar la nada. Faltaba el control: **exigir que el asset
exista ANTES de borrarlo**. Un cronómetro sobre una operación que no ocurrió da un número precioso.
"""
import statistics
import time

import unreal

CARPETA = "/Game/JamBorradoMedicion"

def log(m):
    unreal.log(f"[BORRADO] {m}")


def malla():
    m = unreal.DynamicMesh()
    return unreal.GeometryScript_Primitives.append_box(
        m, unreal.GeometryScriptPrimitiveOptions(), unreal.Transform(),
        dimension_x=100.0, dimension_y=100.0, dimension_z=100.0)


M = malla()

def crear(ruta):
    o = unreal.GeometryScriptCreateNewStaticMeshAssetOptions()
    o.set_editor_property("enable_recompute_normals", False)
    o.set_editor_property("enable_recompute_tangents", False)
    unreal.GeometryScript_NewAssetUtils.create_new_static_mesh_asset_from_mesh(M, ruta, o)
    unreal.EditorAssetLibrary.save_asset(ruta, only_if_is_dirty=False)
    return ruta


def medir(clave, nombre, sacar, vueltas=4):
    """Cada vuelta crea su propio asset y comprueba que EXISTE antes de cronometrar.

    `clave` va aparte del nombre visible porque una ruta de asset no admite espacios ni paréntesis.
    """
    tiempos = []
    for i in range(vueltas):
        ruta = crear(f"{CARPETA}/PV_{clave}_{i}")
        if not unreal.EditorAssetLibrary.does_asset_exist(ruta):
            log(f"  {nombre:40} NO SE CREÓ «{ruta}» — descartada")
            return None
        t = time.perf_counter()
        try:
            sacar(ruta)
        except Exception as exc:  # noqa: BLE001
            log(f"  {nombre:40} NO DISPONIBLE — {type(exc).__name__}: {exc}")
            return None
        tiempos.append((time.perf_counter() - t) * 1000.0)
        if unreal.EditorAssetLibrary.does_asset_exist(ruta):
            log(f"  {nombre:40} NO LO SACÓ (sigue en su ruta) — descartada")
            return None
    mediana = statistics.median(tiempos)
    log(f"  {nombre:40} {mediana:7.1f}ms   {[f'{x:.0f}' for x in tiempos]}")
    return mediana


log("=" * 82)
crear(f"{CARPETA}/PV_calienta")
unreal.EditorAssetLibrary.delete_asset(f"{CARPETA}/PV_calienta")
log("Formas de sacar de en medio UN StaticMesh de 12 triángulos:")
log("-" * 82)

base = medir("borra", "delete_asset (lo que usa Jam hoy)",
             lambda r: unreal.EditorAssetLibrary.delete_asset(r))

cargado = medir("cargado", "delete_loaded_asset",
                lambda r: unreal.EditorAssetLibrary.delete_loaded_asset(
                    unreal.EditorAssetLibrary.load_asset(r)))

# La alternativa que NO borra: mover el asset a una ruta de descarte y barrer más tarde, en lote y
# fuera de la corrida interactiva. Si renombrar es barato, el borrado deja de estar en el camino.
renombrado = medir("renombra", "rename a una ruta de descarte",
                   lambda r: unreal.EditorAssetLibrary.rename_asset(r, r + "Descarte"))

log("-" * 82)
log("Y el barrido diferido, para saber qué costaría después:")
for cantidad in (1, 8):
    for i in range(cantidad):
        crear(f"{CARPETA}/basura/PV_{i}")
    t = time.perf_counter()
    unreal.EditorAssetLibrary.delete_directory(f"{CARPETA}/basura")
    ms = (time.perf_counter() - t) * 1000.0
    log(f"  barrer una carpeta de {cantidad:>2} en una pasada:  {ms:7.1f}ms  ({ms / cantidad:.1f}ms c/u)")

log("-" * 82)
if base and renombrado and renombrado < base * 0.5:
    log(f"→ RENOMBRAR saca el asset de en medio en {renombrado:.1f}ms contra {base:.1f}ms de borrarlo "
        f"({base / renombrado:.0f}x). El borrado puede diferirse a un barrido en lote, sin tocar la "
        f"semántica transaccional: el Preview anterior deja de estar en su ruta igual.")
elif base:
    log("→ Ninguna primitiva evita el costo: para ganar tiempo hay que dejar de sacar el asset en la "
        "corrida interactiva (ping-pong de rutas).")

unreal.EditorAssetLibrary.delete_directory(CARPETA)
log("JAM_BORRADO_58 LISTO")
