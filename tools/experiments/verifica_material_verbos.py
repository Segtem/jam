"""Corre los verbos genéricos de material en el editor REAL y comprueba lo que Python no puede ver.

Tres cosas se verifican acá y en ningún otro lado:

1. **Que la tabla de firmas commiteada siga siendo cierta.** `jam/shader_firmas.py` está generado; si
   el motor cambia (o si el volcado salió mal) el verificador puro aceptaría cableados que Unreal
   rechaza, que es peor que no verificar nada.
2. **Que las propiedades genéricas se apliquen de verdad.** El adaptador ahora decide la conversión
   preguntándole a la propiedad qué tipo tiene, en vez de una lista de enums conocidos. Eso hay que
   probarlo con un enum, un color en hex, un bool y un número, por el camino real.
3. **Que un material armado con los verbos salga igual que uno escrito a mano.** Se arma el mismo
   grafo de las dos formas y se comparan las firmas.

    UnrealEditor-Cmd <proyecto>.uproject -run=pythonscript \\
        -script=<plugin>/tools/experiments/verifica_material_verbos.py \\
        -RenderOffScreen -unattended -nosplash -stdout

Salida en Saved/Logs/<proyecto>.log.
"""

from __future__ import annotations

import unreal

from jam import materials, shader, shader_firmas, tools


FALLAS = []


def log(mensaje: str) -> None:
    unreal.log(f"[VERBOS] {mensaje}")


def exigir(condicion: bool, descripcion: str) -> None:
    log(("  OK   " if condicion else "  FALLA") + f" · {descripcion}")
    if not condicion:
        FALLAS.append(descripcion)


def comprobar_firmas() -> None:
    """La tabla commiteada contra el motor, tipo por tipo."""
    material = unreal.AssetToolsHelpers.get_asset_tools().create_asset(
        "M_SondaVerbos", "/Game/Jam/_Sonda", unreal.Material, unreal.MaterialFactoryNew())
    if material is None:
        exigir(False, "no se pudo crear el material de sonda")
        return
    lib = unreal.MaterialEditingLibrary
    difieren, ausentes = [], []
    for tipo, esperadas in shader_firmas.ENTRADAS.items():
        clase = getattr(unreal, "MaterialExpression" + tipo, None)
        if clase is None:
            ausentes.append(tipo)
            continue
        try:
            nodo = lib.create_material_expression(material, clase, 0, 0)
        except Exception:  # noqa: BLE001
            ausentes.append(tipo)
            continue
        if nodo is None:
            ausentes.append(tipo)
            continue
        reales = tuple(str(x) for x in lib.get_material_expression_input_names(nodo))
        if reales != tuple(esperadas):
            difieren.append((tipo, esperadas, reales))
    exigir(not ausentes, f"todos los tipos de la tabla existen en el motor "
                         f"({len(shader_firmas.ENTRADAS)} tipos)"
           + (f" · AUSENTES {ausentes[:6]}" if ausentes else ""))
    exigir(not difieren, f"todas las firmas coinciden con el motor"
           + (f" · DIFIEREN {difieren[:3]}" if difieren else ""))
    unreal.EditorAssetLibrary.delete_asset("/Game/Jam/_Sonda/M_SondaVerbos")


def correr(verbo, entrada=None, **params):
    info = tools.REGISTRO[verbo]
    completos = dict(info["params"])
    completos.update(params)
    info["fn"](entrada, **completos)
    return tools.dato_producido_runtime(verbo)


def main() -> None:
    log("=" * 70)
    comprobar_firmas()

    # --- un material armado con los verbos, con propiedades de los cuatro tipos que se convierten ---
    g = correr("material_node", None, type="WorldPosition", id="pos")
    g = correr("material_node", g, type="Constant3Vector", id="plano",
               props="constant=#FFFF00")                       # texto hex → LinearColor
    g = correr("material_node", g, type="Multiply", id="xy", inputs="A=pos, B=plano")
    g = correr("material_node", g, type="Noise", id="ruido", inputs="World Position=xy",
               props="noise_function=NOISEFUNCTION_VALUE_ALU, turbulence=false, "
                     "levels=1, output_min=0.0, output_max=1.0")  # enum + bool + int + float
    g = correr("material_node", g, type="ScalarParameter", id="k",
               props="parameter_name=Contraste, default_value=1.5")
    g = correr("material_node", g, type="Power", id="p", inputs="Base=ruido, Exp=k")
    g = correr("material_node", g, type="Lerp", id="mezcla")      # alias: sale LinearInterpolate
    g = correr("material_node", g, type="VectorParameter", id="ca",
               props="parameter_name=ColorA, default_value=#3B3A36")
    g = correr("material_node", g, type="VectorParameter", id="cb",
               props="parameter_name=ColorB, default_value=#A8895E")
    g = correr("material_connect", g, from_node="ca", to_node="mezcla", to_input="A")
    g = correr("material_connect", g, from_node="cb", to_node="mezcla", to_input="B")
    g = correr("material_connect", g, from_node="p", to_node="mezcla", to_input="Alpha")
    g = correr("material_output", g, node="mezcla", target="MP_BASE_COLOR")

    exigir(g.nodo("mezcla").tipo == "LinearInterpolate",
           f"el alias «Lerp» se guardó como {g.nodo('mezcla').tipo}")
    exigir(shader.verificar(g) == [], f"el grafo armado con verbos verifica: {shader.verificar(g)}")

    salida = materials.emitir(
        shader.GrafoMaterial("M_JamVerbosSonda", g.nodos, g.aristas), "/Game/Jam/Materials")
    if "error" in salida:
        exigir(False, f"emitir falló: {salida['error']}")
        return
    log(f"emitido: {salida['info']}")
    exigir("propiedades ignoradas" not in salida["info"],
           "ninguna propiedad quedó sin aplicar")

    # --- ¿las propiedades quedaron con el VALOR pedido, o sólo «se aplicaron»? ---
    material = salida["material"]
    lib = unreal.MaterialEditingLibrary
    encontrados = {}
    pila = [lib.get_material_property_input_node(material, unreal.MaterialProperty.MP_BASE_COLOR)]
    vistos = set()
    while pila:
        nodo = pila.pop()
        if nodo is None or nodo.get_name() in vistos:
            continue
        vistos.add(nodo.get_name())
        encontrados.setdefault(type(nodo).__name__[len("MaterialExpression"):], []).append(nodo)
        pila.extend(lib.get_inputs_for_material_expression(material, nodo))

    ruidos = encontrados.get("Noise", [])
    exigir(len(ruidos) == 1, f"un solo Noise alcanzable ({len(ruidos)})")
    if ruidos:
        n = ruidos[0]
        estado = {p: n.get_editor_property(p)
                  for p in ("noise_function", "turbulence", "levels", "output_min", "output_max")}
        exigir(estado["noise_function"] == unreal.NoiseFunction.NOISEFUNCTION_VALUE_ALU
               and estado["turbulence"] is False and estado["levels"] == 1
               and estado["output_min"] == 0.0 and estado["output_max"] == 1.0,
               f"enum + bool + int + float aplicados desde texto: {estado}")

    planos = [n for n in encontrados.get("Constant3Vector", [])]
    exigir(len(planos) == 1, f"un Constant3Vector ({len(planos)})")
    if planos:
        color = planos[0].get_editor_property("constant")
        # #FFFF00 en sRGB → (1, 1, 0) en lineal: el amarillo puro no cambia al convertir.
        exigir(abs(color.r - 1.0) < 1e-3 and abs(color.g - 1.0) < 1e-3 and abs(color.b) < 1e-3,
               f"el color en hex llegó como LinearColor: {color}")

    escalares = sorted(str(x) for x in lib.get_scalar_parameter_names(material))
    vectores = sorted(str(x) for x in lib.get_vector_parameter_names(material))
    exigir(escalares == ["Contraste"] and vectores == ["ColorA", "ColorB"],
           f"parámetros: {escalares} + {vectores}")

    # --- el mismo grafo escrito a mano tiene que medir lo mismo ---
    a_mano = shader.vacio("M_JamVerbosSonda")
    for tipo, id_, entradas, props in (
            ("WorldPosition", "pos", {}, {}),
            ("Constant3Vector", "plano", {}, {"constant": shader.color_de_hex("#FFFF00")}),
            ("Multiply", "xy", {"A": "pos", "B": "plano"}, {}),
            ("Noise", "ruido", {"World Position": "xy"},
             {"noise_function": "NOISEFUNCTION_VALUE_ALU", "turbulence": False, "levels": 1,
              "output_min": 0.0, "output_max": 1.0}),
            ("ScalarParameter", "k", {}, {"parameter_name": "Contraste", "default_value": 1.5}),
            ("Power", "p", {"Base": "ruido", "Exp": "k"}, {}),
            ("LinearInterpolate", "mezcla", {}, {}),
            ("VectorParameter", "ca", {}, {"parameter_name": "ColorA",
                                           "default_value": shader.color_de_hex("#3B3A36")}),
            ("VectorParameter", "cb", {}, {"parameter_name": "ColorB",
                                           "default_value": shader.color_de_hex("#A8895E")})):
        a_mano, _ = shader.con_nodo(a_mano, tipo, id=id_, entradas=entradas, props=props)
    for desde, entrada in (("ca", "A"), ("cb", "B"), ("p", "Alpha")):
        a_mano = shader.con_cable(a_mano, desde, "mezcla", entrada)
    a_mano = shader.con_salida(a_mano, "mezcla", "MP_BASE_COLOR")
    exigir(shader.firma(a_mano) == shader.firma(g),
           "armar con verbos y escribir a mano dan el MISMO material")

    unreal.EditorAssetLibrary.delete_asset("/Game/Jam/Materials/M_JamVerbosSonda")
    log("=" * 70)
    log("VEREDICTO: " + ("TODO VERDE" if not FALLAS else f"{len(FALLAS)} FALLA(S): {FALLAS}"))


main()
