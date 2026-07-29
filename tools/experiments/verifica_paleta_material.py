"""Arma un material de subsurface REAL con la paleta de nodos individuales, ficha por ficha.

Es la prueba de que la paleta sirve para trabajar y no sólo para verse en el ribbon: se reconstruye
el grafo de un material de piel —dos tonos mezclados por una textura de ruido, rugosidad variable,
subsurface y normal— usando SÓLO los verbos `mat_*`, cada uno como lo llamaría un clic en su ficha.

De paso comprueba lo que más silenciosamente falla: que un `TextureSample` reciba de verdad su
textura (la referencia viaja como RUTA en el IR y hay que cargarla) y que el shading model de
subsurface se aplique, porque sin él la salida `MP_SUBSURFACE_COLOR` se conecta y no hace nada.

    UnrealEditor-Cmd <proyecto>.uproject -run=pythonscript \\
        -script=<plugin>/tools/experiments/verifica_paleta_material.py \\
        -RenderOffScreen -unattended -nosplash -stdout -AllowCommandletRendering
"""

from __future__ import annotations

import unreal

from jam import materials, shader, tools


FALLAS = []
CARPETA = "/Game/Jam/_Sonda"

# Texturas del motor, por si el proyecto no tiene una propia a mano. Se prueba en orden.
CANDIDATAS = (
    "/Engine/EngineMaterials/T_Default_Material_Grid_M",
    "/Engine/EngineResources/DefaultTexture",
    "/Engine/EngineMaterials/DefaultDiffuse",
    "/Engine/EngineMaterials/Good64x64TilingNoiseHighFreq",
)


def log(mensaje: str) -> None:
    unreal.log(f"[PALETA] {mensaje}")


def exigir(condicion: bool, descripcion: str) -> None:
    log(("  OK   " if condicion else "  FALLA") + f" · {descripcion}")
    if not condicion:
        FALLAS.append(descripcion)


def correr(verbo, entrada=None, **params):
    info = tools.REGISTRO[verbo]
    completos = dict(info["params"])
    completos.update(params)
    info["fn"](entrada, **completos)
    return tools.dato_producido_runtime(verbo)


def main() -> None:
    log("=" * 70)

    textura = next((r for r in CANDIDATAS
                    if unreal.EditorAssetLibrary.does_asset_exist(r)), "")
    exigir(bool(textura), f"hay una textura para muestrear: {textura or 'NINGUNA'}")
    if not textura:
        return

    # --- el grafo, ficha por ficha de la paleta ---
    g = correr("mat_color", None, id="tono_a", props="constant=#99401A")
    g = correr("mat_color", g, id="tono_b", props="constant=#DF744B")
    g = correr("mat_texture", g, id="ruido", props=f"texture={textura}")
    g = correr("mat_lerp", g, id="piel", inputs="A=tono_a, B=tono_b, Alpha=ruido.R")

    g = correr("mat_const", g, id="rug_min", props="r=0.2")
    g = correr("mat_const", g, id="rug_max", props="r=0.8")
    g = correr("mat_lerp", g, id="rugosidad", inputs="A=rug_min, B=rug_max, Alpha=ruido.R")

    g = correr("mat_color", g, id="sss", props="constant=#B30000")
    g = correr("mat_scalar", g, id="fuerza", props="parameter_name=Subsurface, default_value=1.0")
    g = correr("mat_mul", g, id="sss_final", inputs="A=sss, B=fuerza")

    g = correr("mat_color", g, id="normal_plana", props="constant=#8080FF")

    g = correr("material_output", g, node="piel", target="MP_BASE_COLOR")
    g = correr("material_output", g, node="rugosidad", target="MP_ROUGHNESS")
    g = correr("material_output", g, node="sss_final", target="MP_SUBSURFACE_COLOR")
    g = correr("material_output", g, node="normal_plana", target="MP_NORMAL")

    firma = shader.firma(g)
    log(f"grafo armado con la paleta: {firma['nodos']} nodos · {firma['aristas']} aristas · "
        f"salidas {firma['salidas']}")
    exigir(shader.verificar(g) == [], f"el grafo verifica: {shader.verificar(g)}")
    exigir(len(firma["salidas"]) == 4, "las cuatro salidas del material están alimentadas")

    # --- hornear como material de subsurface ---
    info = tools.REGISTRO["material_build"]
    params = dict(info["params"])
    params.update({"name": "M_JamPiel", "folder": CARPETA, "shading_model": "MSM_SUBSURFACE"})
    texto = info["fn"](g, **params)
    log(f"material: {texto}")
    exigir("propiedades ignoradas" not in texto, "ninguna propiedad quedó sin aplicar")

    material = unreal.EditorAssetLibrary.load_asset(f"{CARPETA}/M_JamPiel")
    exigir(material.get_editor_property("shading_model") ==
           unreal.MaterialShadingModel.MSM_SUBSURFACE,
           f"shading model: {material.get_editor_property('shading_model')} "
           "(sin subsurface, el cable a MP_SUBSURFACE_COLOR no hace nada)")

    # --- la textura llegó de verdad al nodo, que es lo que falla en silencio ---
    L = unreal.MaterialEditingLibrary
    muestras, pila, vistos = [], [], set()
    for prop in firma["salidas"]:
        nodo = L.get_material_property_input_node(material, getattr(unreal.MaterialProperty, prop))
        exigir(nodo is not None, f"{prop} quedó conectada")
        if nodo is not None:
            pila.append(nodo)
    while pila:
        nodo = pila.pop()
        if nodo.get_name() in vistos:
            continue
        vistos.add(nodo.get_name())
        if isinstance(nodo, unreal.MaterialExpressionTextureSample):
            muestras.append(nodo)
        pila.extend(x for x in L.get_inputs_for_material_expression(material, nodo) if x)

    exigir(len(muestras) == 1, f"hay {len(muestras)} TextureSample alcanzable(s)")
    if muestras:
        asignada = muestras[0].get_editor_property("texture")
        exigir(asignada is not None and asignada.get_path_name().startswith(textura),
               f"la textura llegó al nodo: {asignada.get_path_name() if asignada else 'NINGUNA'}")

    costo = materials.medir(material)
    exigir(costo["medido"], f"el material COMPILA: {materials.resumen_de_costo(costo)}")
    exigir(costo["texturas_ps"] >= 1,
           f"y de verdad muestrea una textura: {costo['texturas_ps']} lecturas en el pixel shader")

    # --- una variante, sin recompilar ---
    correr("material_instance", None, parent=f"{CARPETA}/M_JamPiel", name="MI_JamPielPalida",
           folder=CARPETA, scalars="Subsurface=0.35")
    instancia = unreal.EditorAssetLibrary.load_asset(f"{CARPETA}/MI_JamPielPalida")
    exigir(instancia is not None
           and abs(L.get_material_instance_scalar_parameter_value(instancia, "Subsurface")
                   - 0.35) < 1e-4,
           "la variante existe con su parámetro cambiado")

    for ruta in unreal.EditorAssetLibrary.list_assets(CARPETA, recursive=True):
        unreal.EditorAssetLibrary.delete_asset(ruta)
    log("=" * 70)
    log("VEREDICTO: " + ("TODO VERDE" if not FALLAS else f"{len(FALLAS)} FALLA(S): {FALLAS}"))


main()
