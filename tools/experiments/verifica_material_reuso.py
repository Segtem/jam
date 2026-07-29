"""Funciones de material, llamadas e instancias, por el camino real del ejecutor.

Es la investigación de materiales avanzados vuelta vocabulario. Tres cosas que sólo se pueden
comprobar con un editor:

1. **Una función se hornea del MISMO IR que un material.** El grafo cambia el nodo final
   (`FunctionOutput` en vez de una salida `MP_*`) y el contenedor; nada más.
2. **`material_call` DESCUBRE las entradas del asset.** Es el mismo trato que Jam le da a las 408
   expresiones del motor, y es lo que hace que una función propia se use igual que un nodo nativo.
3. **Una instancia aplica los parámetros que existen y DELATA los que no.** `set_material_instance_*`
   no protesta por un nombre inventado: sin comprobarlo, una instancia queda idéntica al padre y
   nadie se entera.

    UnrealEditor-Cmd <proyecto>.uproject -run=pythonscript \\
        -script=<plugin>/tools/experiments/verifica_material_reuso.py \\
        -RenderOffScreen -unattended -nosplash -stdout -AllowCommandletRendering
"""

from __future__ import annotations

import unreal

from jam import materials, shader, tools


FALLAS = []
CARPETA = "/Game/Jam/_Sonda"


def log(mensaje: str) -> None:
    unreal.log(f"[REUSO] {mensaje}")


def exigir(condicion: bool, descripcion: str) -> None:
    log(("  OK   " if condicion else "  FALLA") + f" · {descripcion}")
    if not condicion:
        FALLAS.append(descripcion)


def correr(verbo, entrada=None, **params):
    info = tools.REGISTRO[verbo]
    completos = dict(info["params"])
    completos.update(params)
    texto = info["fn"](entrada, **completos)
    return texto, tools.dato_producido_runtime(verbo)


def main() -> None:
    log("=" * 70)

    # --- 1. una función reusable, armada con los MISMOS verbos que un material ---
    _, g = correr("material_node", None, type="FunctionInput", id="ent",
                  props="input_name=Aspereza, input_type=FUNCTION_INPUT_SCALAR")
    _, g = correr("material_node", g, type="Constant", id="k", props="r=2.0")
    _, g = correr("material_node", g, type="Power", id="p", inputs="Base=ent, Exp=k")
    _, g = correr("material_node", g, type="FunctionOutput", id="sal",
                  inputs="None=p", props="output_name=Resultado")
    exigir(shader.es_funcion(g), "el grafo se reconoce como FUNCIÓN por su nodo final")
    exigir(shader.verificar(g) == [],
           f"y verifica sin alimentar ninguna salida MP_*: {shader.verificar(g)}")

    texto, _ = correr("material_function", g, name="MF_JamAspereza", folder=CARPETA,
                      description="Eleva la aspereza a una potencia. Sonda de Jam.")
    log(f"función: {texto}")
    ruta_funcion = f"{CARPETA}/MF_JamAspereza"
    exigir(unreal.EditorAssetLibrary.does_asset_exist(ruta_funcion),
           f"la función existe en {ruta_funcion}")

    # --- 2. la firma se DESCUBRE del asset ---
    descubiertas = materials.entradas_de_funcion(ruta_funcion)
    exigir(descubiertas == ["Aspereza"],
           f"entradas descubiertas del asset: {descubiertas} (se esperaba ['Aspereza'])")

    _, m = correr("material_node", None, type="Constant", id="valor", props="r=0.4")
    texto, m = correr("material_call", m, function=ruta_funcion, id="llamada",
                      inputs="Aspereza=valor")
    log(f"llamada: {texto}")
    exigir(m.nodo("llamada").firma == ("Aspereza",),
           f"el nodo lleva su firma descubierta: {m.nodo('llamada').firma}")

    try:
        correr("material_call", m, function=ruta_funcion, inputs="NoExiste=valor")
        exigir(False, "una entrada inventada TENDRÍA que rechazarse y pasó")
    except RuntimeError as exc:
        exigir("Aspereza" in str(exc),
               f"una entrada inventada dice cuáles hay: {str(exc)[:90]}")

    # --- 3. el material que usa la función compila y cuesta ---
    _, m = correr("material_node", m, type="ScalarParameter", id="rug",
                  props="parameter_name=Rugosidad, default_value=0.7")
    _, m = correr("material_node", m, type="VectorParameter", id="col",
                  props="parameter_name=Color, default_value=#8B6F47")
    _, m = correr("material_output", m, node="col", target="MP_BASE_COLOR")
    _, m = correr("material_output", m, node="llamada", target="MP_ROUGHNESS")
    texto, _ = correr("material_build", m, name="M_JamUsaFuncion", folder=CARPETA)
    log(f"material: {texto}")
    exigir("propiedades ignoradas" not in texto, "ninguna propiedad quedó sin aplicar")

    material = unreal.EditorAssetLibrary.load_asset(f"{CARPETA}/M_JamUsaFuncion")
    costo = materials.medir(material)
    exigir(costo["medido"], f"el material con función COMPILA: {materials.resumen_de_costo(costo)}")

    # --- 4. instancias: variantes sin recompilar ---
    texto, _ = correr("material_instance", None, parent=f"{CARPETA}/M_JamUsaFuncion",
                      name="MI_JamVariante", folder=CARPETA,
                      scalars="Rugosidad=0.15", vectors="Color=#3E5C3A")
    log(f"instancia: {texto}")
    instancia = unreal.EditorAssetLibrary.load_asset(f"{CARPETA}/MI_JamVariante")
    exigir(instancia is not None, "la instancia existe")
    if instancia is not None:
        L = unreal.MaterialEditingLibrary
        rug = L.get_material_instance_scalar_parameter_value(instancia, "Rugosidad")
        exigir(abs(rug - 0.15) < 1e-4, f"el parámetro escalar quedó aplicado: Rugosidad={rug}")
        base = L.get_material_default_scalar_parameter_value(material, "Rugosidad")
        exigir(abs(base - 0.7) < 1e-4,
               f"y el PADRE no se tocó: su default sigue en {base}")

    try:
        correr("material_instance", None, parent=f"{CARPETA}/M_JamUsaFuncion",
               name="MI_JamRota", folder=CARPETA, scalars="NoExiste=1.0")
        exigir(False, "un parámetro inventado TENDRÍA que delatarse y pasó")
    except RuntimeError as exc:
        exigir("NoExiste" in str(exc),
               f"un parámetro inventado se delata: {str(exc)[:100]}")

    # --- 5. la vía de ATRIBUTOS: apilar dos materiales enteros, sin assets de layer ---
    _, a = correr("material_node", None, type="Constant3Vector", id="roca",
                  props="constant=#6E6A63")
    _, a = correr("material_node", a, type="MakeMaterialAttributes", id="capa_a",
                  inputs="BaseColor=roca")
    _, a = correr("material_node", a, type="Constant3Vector", id="musgo",
                  props="constant=#4A5D3A")
    _, a = correr("material_node", a, type="MakeMaterialAttributes", id="capa_b",
                  inputs="BaseColor=musgo")
    _, a = correr("material_node", a, type="ScalarParameter", id="mezcla",
                  props="parameter_name=Musgo, default_value=0.35")
    _, a = correr("material_node", a, type="BlendMaterialAttributes", id="apilado",
                  inputs="A=capa_a, B=capa_b, Alpha=mezcla")
    _, a = correr("material_output", a, node="apilado", target="MP_MATERIAL_ATTRIBUTES")
    texto, _ = correr("material_build", a, name="M_JamApilado", folder=CARPETA,
                      use_attributes=True)
    log(f"apilado por atributos: {texto}")
    apilado = unreal.EditorAssetLibrary.load_asset(f"{CARPETA}/M_JamApilado")
    exigir(bool(apilado.get_editor_property("use_material_attributes")),
           "el material quedó en modo atributos (sin eso, el cable no hace nada)")
    costo_apilado = materials.medir(apilado)
    exigir(costo_apilado["medido"],
           f"el apilado COMPILA: {materials.resumen_de_costo(costo_apilado)}")

    for ruta in unreal.EditorAssetLibrary.list_assets(CARPETA, recursive=True):
        unreal.EditorAssetLibrary.delete_asset(ruta)
    log("=" * 70)
    log("VEREDICTO: " + ("TODO VERDE" if not FALLAS else f"{len(FALLAS)} FALLA(S): {FALLAS}"))


main()
