"""Mide los nodos de material que necesita el compilador de Weight, ANTES de escribirlo.

El tab Weight evalúa máscaras 0..1 en CPU con `smoothstep`, `acos`, ruido de valor y unas cuantas
operaciones aritméticas. Para compilar eso a GPU hace falta saber tres cosas de cada tipo de
`MaterialExpression`, y las tres se adivinan mal:

    1. si el tipo EXISTE con el nombre que uno cree (`SmoothStep`? `Arccosine`? `Step`?);
    2. cómo se llaman sus entradas (los de una sola entrada la llaman "None");
    3. qué propiedades tiene y con qué valores por defecto — el rango de salida de `Noise` decide
       si el ruido de GPU vive en [0,1] como el de CPU o en [-1,1] y hay que remapearlo.

Correr:

    UnrealEditor-Cmd <proyecto>.uproject -run=pythonscript \\
        -script=<plugin>/tools/experiments/sonda_weight_nodos.py \\
        -RenderOffScreen -unattended -nosplash -stdout

Salida en Saved/Logs/<proyecto>.log.
"""

from __future__ import annotations

import unreal


CANDIDATOS = [
    # la forma de la banda y de la rampa
    "SmoothStep", "Step", "LinearInterpolate", "Clamp", "Saturate", "OneMinus", "Power",
    # la pendiente
    "Arccosine", "ArccosineFast", "VertexNormalWS", "PixelNormalWS", "DotProduct", "Abs",
    # la posición y el radio
    "WorldPosition", "ComponentMask", "Constant", "Constant2Vector", "Constant3Vector",
    "Distance", "Subtract", "Divide", "Multiply", "Add", "Min", "Max", "Length",
    # el ruido
    "Noise",
    # el aplicador
    "Ceil", "Floor", "If",
    # los parámetros
    "ScalarParameter", "VectorParameter",
]

# De estos interesa el DEFAULT, porque decide si hay que remapear.
PROPIEDADES = {
    "Noise": ["scale", "quality", "noise_function", "turbulence", "levels",
              "output_min", "output_max", "level_scale", "tiling", "repeat_size"],
    "WorldPosition": ["world_position_shader_offset"],
    "ComponentMask": ["r", "g", "b", "a"],
    "SmoothStep": [],
}


def log(m: str) -> None:
    unreal.log(f"[WSONDA] {m}")


def main() -> None:
    log("=" * 70)
    material = unreal.AssetToolsHelpers.get_asset_tools().create_asset(
        "M_SondaWeight", "/Game/Jam/_Sonda", unreal.Material, unreal.MaterialFactoryNew())
    if material is None:
        log("no se pudo crear el material de sonda")
        return

    L = unreal.MaterialEditingLibrary
    faltan = []
    for nombre in CANDIDATOS:
        clase = getattr(unreal, "MaterialExpression" + nombre, None)
        if clase is None:
            faltan.append(nombre)
            log(f"  AUSENTE   MaterialExpression{nombre}")
            continue
        try:
            nodo = L.create_material_expression(material, clase, 0, 0)
        except Exception as exc:  # noqa: BLE001
            log(f"  NO CREA   {nombre}: {type(exc).__name__}: {exc}")
            continue
        entradas = [str(x) for x in L.get_material_expression_input_names(nodo)]
        log(f"  OK        {nombre:20s} entradas={entradas}")
        for prop in PROPIEDADES.get(nombre, []):
            try:
                log(f"                {prop} = {nodo.get_editor_property(prop)!r}")
            except Exception as exc:  # noqa: BLE001
                log(f"                {prop} — NO EXISTE ({type(exc).__name__})")

    log("-" * 70)
    log(f"ausentes: {faltan}")

    # Los valores del enum de la función de ruido: el que replica al `value_noise` de CPU es el de
    # valor, y el nombre exacto del miembro es lo que hay que escribir en el IR.
    funciones = [x for x in dir(unreal.NoiseFunction) if x.isupper()]
    log(f"NoiseFunction: {funciones}")

    unreal.EditorAssetLibrary.delete_asset("/Game/Jam/_Sonda/M_SondaWeight")
    log("=" * 70)


main()
