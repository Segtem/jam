"""Genera el config portable de patrulla ambiental Mass de Jam."""

from __future__ import annotations

import json

import unreal


PACKAGE = "/Jam/Mass/MC_JamAmbientPatrol"
MESH = "/Engine/BasicShapes/Sphere.Sphere"


if unreal.EditorAssetLibrary.does_asset_exist(PACKAGE):
    raise RuntimeError(f"{PACKAGE} ya existe; no se reemplaza automáticamente")

factory = unreal.DataAssetFactory()
factory.set_editor_property("data_asset_class", unreal.MassEntityConfigAsset)
asset = unreal.AssetToolsHelpers.get_asset_tools().create_asset(
    "MC_JamAmbientPatrol", "/Jam/Mass", unreal.MassEntityConfigAsset, factory)
if asset is None:
    raise RuntimeError("AssetTools no creó MC_JamAmbientPatrol")

prepared = json.loads(str(unreal.JamMassLibrary.prepare_ambient_patrol_config(
    asset, MESH, 1500.0, 3500.0, 8000.0, 800.0, 25.0)))
if not prepared.get("ok"):
    raise RuntimeError(f"no se preparó la patrulla ambiental: {prepared}")
if not unreal.EditorAssetLibrary.save_loaded_asset(asset):
    raise RuntimeError("no se guardó MC_JamAmbientPatrol")

unreal.log(
    "JAM_MASS_AMBIENT_PATROL_CONFIG_58 TODO VERDE — "
    "ISM dinámica · velocidad 800 cm/s · radio 25 cm")
