"""Genera el config ambiental ISM portable de Jam con UE 5.8.1."""

from __future__ import annotations

import json

import unreal


PACKAGE = "/Jam/Mass/MC_JamAmbientISM"
MESH = "/Engine/BasicShapes/Sphere.Sphere"


if unreal.EditorAssetLibrary.does_asset_exist(PACKAGE):
    raise RuntimeError(f"{PACKAGE} ya existe; no se reemplaza automáticamente")

factory = unreal.DataAssetFactory()
factory.set_editor_property("data_asset_class", unreal.MassEntityConfigAsset)
asset = unreal.AssetToolsHelpers.get_asset_tools().create_asset(
    "MC_JamAmbientISM", "/Jam/Mass", unreal.MassEntityConfigAsset, factory)
if asset is None:
    raise RuntimeError("AssetTools no creó MC_JamAmbientISM")

prepared = json.loads(str(unreal.JamMassLibrary.prepare_ambient_ism_config(
    asset, MESH, 1500.0, 3500.0, 8000.0)))
if not prepared.get("ok"):
    raise RuntimeError(f"no se preparó el perfil ISM ambiental: {prepared}")
if not unreal.EditorAssetLibrary.save_loaded_asset(asset):
    raise RuntimeError("no se guardó MC_JamAmbientISM")

unreal.log("JAM_MASS_AMBIENT_CONFIG_58 TODO VERDE — ISM/ISM/ISM/None · 0/1500/3500/8000")
