"""Genera el config portable de patrulla ambiental Mass de Jam."""

from __future__ import annotations

import json

import unreal


PACKAGE = "/Jam/Mass/MC_JamAmbientPatrol"
MESH = "/Engine/BasicShapes/Sphere.Sphere"


# El asset se RECONFIGURA si ya existe, en vez de negarse. Negarse dejaba el único camino para
# cambiarle un parámetro en borrarlo a mano, y en modo unattended `create_asset` sobre algo existente
# devuelve None sin decir por qué. La configuración vive acá abajo, así que reaplicarla es
# idempotente: el mismo script produce el mismo asset lo haya creado él o no.
# Se INTENTA CARGAR primero y se crea sólo si no vino nada, así el script es idempotente y sirve
# para RECONFIGURAR. Va por `unreal.load_object` y no por `EditorAssetLibrary`: sobre el content de
# un PLUGIN y en commandlet, `does_asset_exist` devuelve False y `load_asset` devuelve None para un
# asset que existe —medido acá mismo—, mientras AssetTools se niega a crearlo porque sí existe.
try:
    asset = unreal.load_object(None, f"{PACKAGE}.MC_JamAmbientPatrol")
except Exception:
    asset = None
if asset is not None:
    unreal.log(f"[PATRULLA] {PACKAGE} ya existía: se reconfigura")
else:
    factory = unreal.DataAssetFactory()
    factory.set_editor_property("data_asset_class", unreal.MassEntityConfigAsset)
    asset = unreal.AssetToolsHelpers.get_asset_tools().create_asset(
        "MC_JamAmbientPatrol", "/Jam/Mass", unreal.MassEntityConfigAsset, factory)
if asset is None:
    raise RuntimeError("no se pudo obtener MC_JamAmbientPatrol")

prepared = json.loads(str(unreal.JamMassLibrary.prepare_ambient_patrol_config(
    asset, MESH, 1500.0, 3500.0, 8000.0, 800.0, 25.0, 0.7)))
if not prepared.get("ok"):
    raise RuntimeError(f"no se preparó la patrulla ambiental: {prepared}")
if not unreal.EditorAssetLibrary.save_loaded_asset(asset):
    raise RuntimeError("no se guardó MC_JamAmbientPatrol")

unreal.log(
    "JAM_MASS_AMBIENT_PATROL_CONFIG_58 TODO VERDE — "
    "ISM dinámica · velocidad 800 cm/s · radio 25 cm · variación 0.70")
