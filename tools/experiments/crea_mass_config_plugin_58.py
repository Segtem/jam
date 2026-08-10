"""Crea el config espacial mínimo distribuido por Jam en ``/Jam/Mass``.

Es una herramienta de mantenimiento: se ejecuta una vez cuando hay que regenerar el ``.uasset``
con UE 5.8.1. No reemplaza ni modifica un asset existente para evitar duplicar traits en silencio.
"""

from __future__ import annotations

import json

import unreal


PACKAGE = "/Jam/Mass/MC_JamSpatial"


if unreal.EditorAssetLibrary.does_asset_exist(PACKAGE):
    raise RuntimeError(f"{PACKAGE} ya existe; no se reemplaza automáticamente")

factory = unreal.DataAssetFactory()
factory.set_editor_property("data_asset_class", unreal.MassEntityConfigAsset)
asset = unreal.AssetToolsHelpers.get_asset_tools().create_asset(
    "MC_JamSpatial", "/Jam/Mass", unreal.MassEntityConfigAsset, factory)
if asset is None:
    raise RuntimeError("AssetTools no creó MC_JamSpatial")

prepared = json.loads(str(unreal.JamMassLibrary.prepare_transform_config(asset)))
if not prepared.get("ok"):
    raise RuntimeError(f"no se agregó UJamMassTransformTrait: {prepared}")
if not unreal.EditorAssetLibrary.save_loaded_asset(asset):
    raise RuntimeError("no se guardó MC_JamSpatial")

unreal.log("JAM_MASS_CONFIG_PLUGIN_58 TODO VERDE — /Jam/Mass/MC_JamSpatial")
