"""Genera el config ambiental ISM con presupuesto LOD portable de Jam."""

from __future__ import annotations

import json

import unreal


PACKAGE = "/Jam/Mass/MC_JamAmbientBudget"
MESH = "/Engine/BasicShapes/Sphere.Sphere"


if unreal.EditorAssetLibrary.does_asset_exist(PACKAGE):
    raise RuntimeError(f"{PACKAGE} ya existe; no se reemplaza automáticamente")

factory = unreal.DataAssetFactory()
factory.set_editor_property("data_asset_class", unreal.MassEntityConfigAsset)
asset = unreal.AssetToolsHelpers.get_asset_tools().create_asset(
    "MC_JamAmbientBudget", "/Jam/Mass", unreal.MassEntityConfigAsset, factory)
if asset is None:
    raise RuntimeError("AssetTools no creó MC_JamAmbientBudget")

prepared = json.loads(str(unreal.JamMassLibrary.prepare_ambient_ism_budget_config(
    asset, MESH, 1500.0, 3500.0, 8000.0, 1, 1, 1)))
if not prepared.get("ok"):
    raise RuntimeError(f"no se preparó el perfil ISM presupuestado: {prepared}")
if not unreal.EditorAssetLibrary.save_loaded_asset(asset):
    raise RuntimeError("no se guardó MC_JamAmbientBudget")

unreal.log(
    "JAM_MASS_AMBIENT_BUDGET_CONFIG_58 TODO VERDE — "
    "ISM/ISM/ISM/None · máximos 1/1/1/ilimitado")
