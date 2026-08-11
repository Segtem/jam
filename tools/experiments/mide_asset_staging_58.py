"""¿Se puede evitar el borrado de 157 ms del asset staged? Medir las opciones antes de elegir.

`mide_recoccion_58.py` dejó ubicado el costo: recocinar un grafo que hornea cuesta 215 ms y la
mayoría —157 ms— es **borrar el StaticMesh temporal que dejó la vuelta anterior**, cuatro veces lo
que cuesta escribirlo. Antes de rediseñar el staging conviene saber de dónde sale ese número, porque
cada rediseño posible cuesta algo distinto:

  · **sobrescribir** la misma ruta en vez de borrar y crear otra — mata el borrado, pero rompe la
    garantía de rollback: el Preview anterior se pierde antes de saber si el nuevo salió bien.
  · **ping-pong** entre dos rutas — conserva el rollback (la vuelta N+1 pisa la basura de N-1, no la
    de N) y tampoco borra. Sólo sirve si sobrescribir es realmente más barato que borrar+crear.
  · **diferir** el borrado fuera de la corrida interactiva — conserva todo, pero deja basura viva.
  · **borrar en lote** la carpeta del owner — sólo ayuda si el costo es por pasada y no por asset.

Esta sonda mide las primitivas para poder elegir con números. NO decide: el diseño que salga de acá
se verifica después por el camino real del Graph.
"""
import statistics
import time

import unreal

from jam import mesh

CARPETA = "/Game/JamPreviewMedicion"

def log(m):
    unreal.log(f"[STAGING] {m}")


def malla():
    """Una malla chica y real: lo que se mide es el asset, no construir la geometría."""
    m = unreal.DynamicMesh()
    return unreal.GeometryScript_Primitives.append_box(
        m, unreal.GeometryScriptPrimitiveOptions(), unreal.Transform(),
        dimension_x=100.0, dimension_y=100.0, dimension_z=100.0)


def opciones():
    o = unreal.GeometryScriptCreateNewStaticMeshAssetOptions()
    o.set_editor_property("enable_recompute_normals", False)
    o.set_editor_property("enable_recompute_tangents", False)
    o.set_editor_property("enable_collision", True)
    return o


def crear(ruta, m):
    unreal.GeometryScript_NewAssetUtils.create_new_static_mesh_asset_from_mesh(m, ruta, opciones())
    unreal.EditorAssetLibrary.save_asset(ruta, only_if_is_dirty=False)


def cronometrar(fn, vueltas=5):
    tiempos = []
    for i in range(vueltas):
        t = time.perf_counter()
        fn(i)
        tiempos.append((time.perf_counter() - t) * 1000.0)
    return statistics.median(tiempos), tiempos


m = malla()
log("=" * 78)
log(f"Malla de prueba: {unreal.GeometryScript_MeshQueries.get_num_triangle_i_ds(m)} triángulos")

# calentamiento: la primera creación del proceso paga la carga del pipeline de assets
crear(f"{CARPETA}/PV_calienta", m)
unreal.EditorAssetLibrary.delete_asset(f"{CARPETA}/PV_calienta")

log("-" * 78)

# --- 1. crear en ruta nueva (lo que cuesta escribir) -------------------------------------------
def crear_nuevo(i):
    crear(f"{CARPETA}/PV_nuevo_{i}", m)

ms_crear, crudos_crear = cronometrar(crear_nuevo)
log(f"  crear en ruta NUEVA:            {ms_crear:7.1f}ms   {[f'{x:.0f}' for x in crudos_crear]}")

# --- 2. borrar uno por uno (lo que cuesta hoy la recocción) ------------------------------------
def borrar_uno(i):
    unreal.EditorAssetLibrary.delete_asset(f"{CARPETA}/PV_nuevo_{i}")

ms_borrar, crudos_borrar = cronometrar(borrar_uno)
log(f"  borrar uno por uno:             {ms_borrar:7.1f}ms   {[f'{x:.0f}' for x in crudos_borrar]}")

# --- 3. sobrescribir la MISMA ruta sin borrar antes --------------------------------------------
# Si Geometry Script acepta pisar un asset existente, el ping-pong es viable sin borrar nunca.
crear(f"{CARPETA}/PV_pisado", m)
sobrescribe = {"ok": None}

def sobrescribir(_i):
    resultado = unreal.GeometryScript_NewAssetUtils.create_new_static_mesh_asset_from_mesh(
        m, f"{CARPETA}/PV_pisado", opciones())
    creado = resultado[0] if isinstance(resultado, tuple) else resultado
    sobrescribe["ok"] = creado is not None
    unreal.EditorAssetLibrary.save_asset(f"{CARPETA}/PV_pisado", only_if_is_dirty=False)

try:
    ms_sobre, crudos_sobre = cronometrar(sobrescribir, vueltas=4)
    log(f"  sobrescribir la misma ruta:     {ms_sobre:7.1f}ms   {[f'{x:.0f}' for x in crudos_sobre]}"
        f"   (creó: {sobrescribe['ok']})")
except Exception as exc:  # noqa: BLE001
    ms_sobre = None
    log(f"  sobrescribir la misma ruta:     NO SE PUEDE — {type(exc).__name__}: {exc}")

# --- 4. borrar en lote: ¿el costo es por asset o por pasada? -----------------------------------
for cantidad in (1, 4, 8):
    for i in range(cantidad):
        crear(f"{CARPETA}/lote/PV_lote_{i}", m)
    t = time.perf_counter()
    unreal.EditorAssetLibrary.delete_directory(f"{CARPETA}/lote")
    ms = (time.perf_counter() - t) * 1000.0
    log(f"  borrar carpeta de {cantidad:>2} assets:      {ms:7.1f}ms   ({ms / cantidad:.1f}ms por asset)")

# --- 5. ¿y borrar N sueltos, uno por uno? --------------------------------------------------------
for i in range(8):
    crear(f"{CARPETA}/sueltos/PV_suelto_{i}", m)
t = time.perf_counter()
for i in range(8):
    unreal.EditorAssetLibrary.delete_asset(f"{CARPETA}/sueltos/PV_suelto_{i}")
ms_sueltos = (time.perf_counter() - t) * 1000.0
log(f"  borrar 8 sueltos uno por uno:   {ms_sueltos:7.1f}ms   ({ms_sueltos / 8:.1f}ms por asset)")

log("-" * 78)
log("Qué habilita cada número:")
if ms_sobre is not None and sobrescribe["ok"]:
    log(f"  · sobrescribir cuesta {ms_sobre:.1f}ms contra {ms_borrar + ms_crear:.1f}ms de borrar+crear "
        f"→ ping-pong {'VIABLE' if ms_sobre < ms_borrar + ms_crear else 'NO ayuda'}")
else:
    log("  · sobrescribir no está disponible: el ping-pong tendría que borrar igual")
log(f"  · el costo del borrado es por {'PASADA (el lote ayuda)' if ms_sueltos / 8 > ms_borrar * 0.6 else 'ASSET (el lote no ayuda)'}")

unreal.EditorAssetLibrary.delete_directory(CARPETA)
log("JAM_STAGING_58 LISTO")
