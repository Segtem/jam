"""Corre el nodo `weight_material` en el editor REAL y comprueba que el material quedó como el IR.

La suite compara el IR contra la máscara de CPU: eso demuestra que la TRADUCCIÓN es correcta. Lo que
no puede ver es el tramo de Unreal, donde todo falla en silencio: un `set_editor_property` con el
nombre equivocado deja el nodo en su default, un enum mandado como texto lanza y se cuenta como
«propiedad ignorada», y un `connect_material_expressions` devuelve False y sigue.

Se corre por el camino de verdad —`Flow.evaluar` con las ops del adaptador—, que es el único que
prueba que el nodo terminal recibe el contexto del grafo y que el registro está bien armado.

    UnrealEditor-Cmd <proyecto>.uproject -run=pythonscript \\
        -script=<plugin>/tools/experiments/verifica_material_mascara.py \\
        -RenderOffScreen -unattended -nosplash -stdout

Salida en Saved/Logs/<proyecto>.log.
"""

from __future__ import annotations

import unreal

from jam import flow, scatter, shader, weight_material


FALLAS = []


def log(mensaje: str) -> None:
    unreal.log(f"[MASCARA] {mensaje}")


def exigir(condicion: bool, descripcion: str) -> None:
    log(("  OK   " if condicion else "  FALLA") + f" · {descripcion}")
    if not condicion:
        FALLAS.append(descripcion)


def armar() -> tuple:
    """La cadena: dos máscaras que se juntan, se endurecen y se recortan.

    Toca todo lo que el compilador sabe hacer —banda, ruido, combine, power, cull— para que una sola
    corrida cubra los cuatro tipos de nodo que pueden fallar al emitirse.
    """
    f = flow.Flow()
    fuente = f.add("pts_rect", {"cols": 4, "rows": 4, "size_x": 800.0, "size_y": 800.0}, nid="src")
    pendiente = f.add("weight_slope", {"min": 0.0, "max": 40.0, "soft": 8.0}, nid="pend")
    ruido = f.add("weight_noise", {"scale": 350.0, "seed": 5, "contrast": 1.3}, nid="ruido")
    junta = f.add("weight_combine", {"mode": "mul"}, nid="junta")
    duro = f.add("weight_power", {"k": 1.7}, nid="duro")
    recorte = f.add("weight_cull", {"threshold": 0.35, "soft": 0.0}, nid="corte")
    salida = f.add("weight_material", {"name": "M_JamMascaraSonda",
                                       "folder": "/Game/Jam/Materials"}, nid="mat")
    for origen, destino in ((fuente, pendiente), (fuente, ruido), (pendiente, junta),
                            (ruido, junta), (junta, duro), (duro, recorte), (recorte, salida)):
        f.connect(origen, destino)
    return f, salida


def main() -> None:
    log("=" * 70)
    flujo, terminal = armar()

    compilado = weight_material.desde_flow(flujo, terminal, nombre="M_JamMascaraSonda")
    if "error" in compilado:
        log(f"el compilador falló: {compilado['error']}")
        FALLAS.append("compilar")
        return
    grafo = compilado["grafo"]
    firma = shader.firma(grafo)
    log(f"IR: {firma['nodos']} nodos · {firma['aristas']} aristas · "
        f"profundidad {firma['profundidad']} · ops {compilado['ops']}")
    log(f"notas del compilador: {compilado['notas'] or 'ninguna (traducción exacta)'}")

    # --- el camino REAL: el evaluador del flow con las ops del adaptador ---
    try:
        flujo.evaluar(ops=scatter.ops_flow())
    except Exception as exc:  # noqa: BLE001
        exigir(False, f"Flow.evaluar explotó: {type(exc).__name__}: {exc}")
        return
    reporte = flujo.resultados.get(terminal, {}).get("out", {})
    if "error" in reporte:
        exigir(False, f"el nodo terminal reportó: {reporte['error']}")
        return
    exigir(bool(reporte.get("material")), f"el nodo corrió: {reporte.get('resumen')}")
    exigir("propiedades ignoradas" not in str(reporte.get("material", "")),
           f"ninguna propiedad quedó sin aplicar · {reporte.get('material')}")

    ruta = "/Game/Jam/Materials/M_JamMascaraSonda"
    material = unreal.EditorAssetLibrary.load_asset(ruta)
    if material is None:
        exigir(False, f"no se pudo releer {ruta}")
        return

    L = unreal.MaterialEditingLibrary
    exigir(L.get_num_material_expressions(material) == firma["nodos"],
           f"nodos en el asset: {L.get_num_material_expressions(material)} "
           f"(el IR dice {firma['nodos']})")

    # --- el recorte necesita blend enmascarado, si no la salida de opacidad no compila ---
    # Contra el enum, no contra su texto: `str()` de un enum de UE devuelve el repr entero
    # («<BlendMode.BLEND_MASKED: 1>»), así que comparar por sufijo da falso con el valor correcto.
    blend = material.get_editor_property("blend_mode")
    exigir(blend == unreal.BlendMode.BLEND_MASKED, f"blend_mode del material: {blend}")

    # --- los parámetros: la superficie que queda para retocar sin volver a correr el grafo ---
    escalares = sorted(str(n) for n in L.get_scalar_parameter_names(material))
    vectores = sorted(str(n) for n in L.get_vector_parameter_names(material))
    exigir(sorted(escalares + vectores) == sorted(firma["parametros"]),
           f"parámetros: {len(escalares)} escalares + {len(vectores)} vectores")
    exigir("Slope1_Min" in escalares and "Noise1_Scale" in escalares,
           "los nombres dicen de qué nodo del tab salieron")

    # --- las propiedades del ruido, que son lo que lo hace EL ruido de Jam y no otro ---
    ruidos = []
    pila, vistos = [], set()
    for nombre_prop in firma["salidas"]:
        nodo = L.get_material_property_input_node(material, getattr(unreal.MaterialProperty,
                                                                   nombre_prop))
        if nodo is None:
            exigir(False, f"{nombre_prop} quedó SIN conectar")
        else:
            pila.append(nodo)
    leidas = set()
    for nombre_prop in firma["salidas"]:
        nodo = L.get_material_property_input_node(material, getattr(unreal.MaterialProperty,
                                                                   nombre_prop))
        if nodo is not None:
            leidas.add((type(nodo).__name__[len("MaterialExpression"):], nombre_prop))
    while pila:
        nodo = pila.pop()
        if nodo.get_name() in vistos:
            continue
        vistos.add(nodo.get_name())
        if isinstance(nodo, unreal.MaterialExpressionNoise):
            ruidos.append(nodo)
        nombres = list(L.get_material_expression_input_names(nodo))
        for i, entrada in enumerate(L.get_inputs_for_material_expression(material, nodo)):
            if entrada is None:
                continue
            etiqueta = nombres[i] if i < len(nombres) else str(i)
            leidas.add((type(entrada).__name__[len("MaterialExpression"):],
                        type(nodo).__name__[len("MaterialExpression"):] + "." + etiqueta))
            pila.append(entrada)

    exigir(len(ruidos) == 1, f"hay {len(ruidos)} nodo(s) Noise alcanzables (se esperaba 1)")
    if ruidos:
        n = ruidos[0]
        configuracion = {p: n.get_editor_property(p)
                         for p in ("noise_function", "turbulence", "levels",
                                   "output_min", "output_max", "scale")}
        correcto = (configuracion["noise_function"] == unreal.NoiseFunction.NOISEFUNCTION_VALUE_ALU
                    and configuracion["turbulence"] is False
                    and configuracion["levels"] == 1
                    and configuracion["output_min"] == 0.0
                    and configuracion["output_max"] == 1.0)
        exigir(correcto, f"el Noise quedó como el de Jam: {configuracion}")

    # --- la topología leída DE VUELTA, no la que creímos escribir ---
    del_ir = set()
    for arista in grafo.aristas:
        tipo_origen = grafo.nodo(arista.desde).tipo
        if arista.es_salida_del_material:
            del_ir.add((tipo_origen, arista.hasta))
        else:
            del_ir.add((tipo_origen, grafo.nodo(arista.hasta).tipo + "." + arista.entrada))
    faltan, sobran = del_ir - leidas, leidas - del_ir
    exigir(not faltan and not sobran,
           f"topología leída == IR ({len(leidas)} de {len(del_ir)})"
           + (f" · FALTAN {sorted(faltan)[:4]}" if faltan else "")
           + (f" · SOBRAN {sorted(sobran)[:4]}" if sobran else ""))
    exigir(len(vistos) == firma["nodos"],
           f"nodos alcanzables desde las salidas: {len(vistos)} de {firma['nodos']}")

    # --- reemitir: el caso más común (retocar un número y volver a dar Run) ---
    flujo.evaluar(ops=scatter.ops_flow())
    material = unreal.EditorAssetLibrary.load_asset(ruta)
    exigir(L.get_num_material_expressions(material) == firma["nodos"],
           f"tras reemitir sigue habiendo {L.get_num_material_expressions(material)} nodos "
           f"(sin basura acumulada)")

    L.recompile_material(material)
    st = L.get_statistics(material)
    log(f"MaterialStatistics: PS={st.num_pixel_shader_instructions} "
        f"VS={st.num_vertex_shader_instructions} samplers={st.num_samplers}"
        + ("   (cero = los shaders no compilan en commandlet)"
           if st.num_pixel_shader_instructions == 0 else "   ¡AHORA SÍ MIDE!"))

    log("=" * 70)
    log("VEREDICTO: " + ("TODO VERDE" if not FALLAS else f"{len(FALLAS)} FALLA(S): {FALLAS}"))


main()
