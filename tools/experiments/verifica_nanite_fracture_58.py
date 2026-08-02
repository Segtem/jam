"""Verifica en el editor GUI UE 5.8.1: StaticMesh → Nanite → Fracture.

No sirve headless: `add_dataflow_node` es uno de los caminos medidos que cuelgan sin editor real.
Elige una malla del proyecto con al menos dos materiales, trabaja sólo sobre assets efímeros bajo
`/Game/JamVerification` y los borra al terminar. Veredicto: `JAM_NANITE_FRACTURE_TEST` en BotOO.log.

Receta:
  UnrealEditor BotOO.uproject -ExecutePythonScript=/ruta/absoluta/a/este/script.py
"""

from __future__ import annotations

import unreal

from jam import fracture, nanite


CARPETA = "/Game/JamVerification/NaniteFracture58"
CREADOS: list[str] = []


def _nanite(mesh) -> bool:
    subsystem = unreal.get_editor_subsystem(unreal.StaticMeshEditorSubsystem)
    return bool(subsystem.get_nanite_settings(mesh).get_editor_property("enabled"))


def _materiales(asset, propiedad: str) -> list[str]:
    salida = []
    for slot in asset.get_editor_property(propiedad):
        material = slot.get_editor_property("material_interface") if propiedad == "static_materials" else slot
        if material:
            salida.append(material.get_path_name())
    return salida


def _malla_multimaterial():
    registry = unreal.AssetRegistryHelpers.get_asset_registry()
    clase = unreal.TopLevelAssetPath("/Script/Engine", "StaticMesh")
    for data in registry.get_assets_by_class(clase, True):
        mesh = data.get_asset()
        if mesh and len(_materiales(mesh, "static_materials")) >= 2:
            return mesh
    raise RuntimeError("no encontré una StaticMesh con dos materiales para discriminar la copia")


try:
    fuente = _malla_multimaterial()
    originales = _materiales(fuente, "static_materials")
    salida_nanite = nanite.convertir(fuente, carpeta=CARPETA)
    if salida_nanite.get("error"):
        raise RuntimeError(salida_nanite["error"])
    mesh_nanite = salida_nanite["mesh"]
    if not salida_nanite.get("already"):
        CREADOS.append(salida_nanite["ruta"])
    if not _nanite(mesh_nanite):
        raise RuntimeError("la salida intermedia no conservó Nanite")

    salida_gc = fracture.fracturar(mesh_nanite, sites=8, seed=581, carpeta=CARPETA)
    if salida_gc.get("error"):
        raise RuntimeError(salida_gc["error"])
    CREADOS.extend([salida_gc["ruta"], salida_gc["dataflow_ruta"]])
    gc = salida_gc["gc"]
    materiales_gc = _materiales(gc, "materials")
    faltantes = [m for m in originales if m not in materiales_gc]
    if faltantes:
        raise RuntimeError(
            f"la GC perdió materiales: faltan={faltantes} fuente={originales} gc={materiales_gc}")
    if not bool(gc.get_editor_property("enable_nanite")):
        raise RuntimeError("la Geometry Collection salió con EnableNanite=false")

    unreal.log(
        "JAM_NANITE_FRACTURE_TEST TODO VERDE — "
        f"fuente={fuente.get_path_name()} materiales={len(originales)} "
        f"gc_materiales={len(materiales_gc)} nanite_gc=true")
except Exception as exc:  # noqa: BLE001
    unreal.log_error(f"JAM_NANITE_FRACTURE_TEST ROJO — {type(exc).__name__}: {exc}")
finally:
    for ruta in reversed(CREADOS):
        if unreal.EditorAssetLibrary.does_asset_exist(ruta):
            unreal.EditorAssetLibrary.delete_asset(ruta)
    unreal.SystemLibrary.quit_editor()
