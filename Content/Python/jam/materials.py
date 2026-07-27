"""Material de los ayudantes visuales de Jam (fantasmas), con color y opacidad por parámetro.

Se fabrica UNA vez en `/Jam/Materials/M_JamGhost` (unlit + translúcido, con parámetros `Color` y
`Opacity`) y después cada fantasma usa una instancia dinámica con su propio color. Si por lo que sea
no se puede crear, se cae a los materiales translúcidos que ya trae el motor: el fantasma se ve
igual, sólo que sin control de color.
"""

from __future__ import annotations

import unreal

RUTA = "/Jam/Materials/M_JamGhost"

# Plan B: translúcidos del editor de físicas del motor (no tienen parámetro de color).
_FALLBACK = (
    "/Engine/EditorMaterials/PhAT_ElemSelectedMaterial",
    "/Engine/EditorMaterials/PhAT_ElemUnselectedMaterial",
)

_CACHE: dict = {"base": None, "intentado": False}


def _crear() -> unreal.Material | None:
    """Fabrica el material: unlit translúcido, Emissive=Color, Opacity=Opacity."""
    try:
        tools = unreal.AssetToolsHelpers.get_asset_tools()
        mat = tools.create_asset("M_JamGhost", "/Jam/Materials", unreal.Material,
                                 unreal.MaterialFactoryNew())
        if mat is None:
            return None
        mat.set_editor_property("blend_mode", unreal.BlendMode.BLEND_TRANSLUCENT)
        mat.set_editor_property("shading_model", unreal.MaterialShadingModel.MSM_UNLIT)
        mat.set_editor_property("two_sided", True)

        lib = unreal.MaterialEditingLibrary
        color = lib.create_material_expression(mat, unreal.MaterialExpressionVectorParameter, -400, 0)
        color.set_editor_property("parameter_name", "Color")
        color.set_editor_property("default_value", unreal.LinearColor(0.1, 0.5, 1.0, 1.0))
        opac = lib.create_material_expression(mat, unreal.MaterialExpressionScalarParameter, -400, 220)
        opac.set_editor_property("parameter_name", "Opacity")
        opac.set_editor_property("default_value", 0.35)

        lib.connect_material_property(color, "", unreal.MaterialProperty.MP_EMISSIVE_COLOR)
        lib.connect_material_property(opac, "", unreal.MaterialProperty.MP_OPACITY)
        lib.recompile_material(mat)
        unreal.EditorAssetLibrary.save_asset(RUTA, only_if_is_dirty=False)
        return mat
    except Exception as e:  # noqa: BLE001
        unreal.log_warning(f"[Jam] no pude fabricar {RUTA} ({e}); uso los translúcidos del motor.")
        return None


def base() -> unreal.MaterialInterface | None:
    """El material base de los fantasmas (cacheado). None si no hay ninguno usable."""
    if _CACHE["base"] is not None:
        return _CACHE["base"]
    try:
        if unreal.EditorAssetLibrary.does_asset_exist(RUTA):
            _CACHE["base"] = unreal.load_asset(RUTA)
    except Exception:  # noqa: BLE001
        pass
    if _CACHE["base"] is None and not _CACHE["intentado"]:
        _CACHE["intentado"] = True
        _CACHE["base"] = _crear()
    if _CACHE["base"] is None:
        for r in _FALLBACK:
            try:
                m = unreal.load_asset(r)
                if isinstance(m, unreal.MaterialInterface):
                    _CACHE["base"] = m
                    break
            except Exception:  # noqa: BLE001
                continue
    return _CACHE["base"]


def instancia(color: unreal.LinearColor, opacidad: float = 0.35, dueno=None):
    """Instancia dinámica del material base con ese color. None si no hay material."""
    b = base()
    if b is None:
        return None
    try:
        # `unreal.MaterialInstanceDynamic` NO expone `create` desde Python: la fábrica vive en
        # MaterialLibrary. Como el except devolvía el material base, el fantasma venía saliendo
        # opaco y sin color en silencio.
        mid = unreal.MaterialLibrary.create_dynamic_material_instance(dueno, b)
        if mid is None:
            return b
        mid.set_vector_parameter_value("Color", color)
        mid.set_scalar_parameter_value("Opacity", opacidad)
        return mid
    except Exception:  # noqa: BLE001
        return b   # sin parámetros (fallback del motor): al menos translúcido
