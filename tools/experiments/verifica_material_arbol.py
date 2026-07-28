"""Emite el material de viento en el editor REAL y comprueba que quedó como lo describe el IR.

El verificador de `jam.shader` mira el grafo como dato: sabe que está bien armado, no que Unreal lo
haya construido. Entre las dos cosas hay un montón de silencio — un `set_editor_property` con el
nombre equivocado no falla, un `connect_material_expressions` devuelve `False` y sigue de largo.

Esto cierra ese hueco: emite el material, lo VUELVE A LEER del asset y compara la topología leída
contra la que describe el IR. Y de paso mide `MaterialStatistics`, que headless da cero — sirve para
dejar registrado si eso cambia.

    UnrealEditor-Cmd <proyecto>.uproject -run=pythonscript \\
        -script=<plugin>/tools/experiments/verifica_material_arbol.py \\
        -RenderOffScreen -unattended -nosplash -stdout

Salida en Saved/Logs/<proyecto>.log.
"""

from __future__ import annotations

import unreal

from jam import materials, shader


FALLAS = []


def log(mensaje: str) -> None:
    unreal.log(f"[ARBOL] {mensaje}")


def exigir(condicion: bool, descripcion: str) -> None:
    log(("  OK   " if condicion else "  FALLA") + f" · {descripcion}")
    if not condicion:
        FALLAS.append(descripcion)


def main() -> None:
    log("=" * 68)
    grafo = shader.viento_de_arbol()
    firma = shader.firma(grafo)
    log(f"IR: {firma['nodos']} nodos · {firma['aristas']} aristas · "
        f"profundidad {firma['profundidad']} · parámetros {firma['parametros']}")

    salida = materials.emitir(grafo, "/Game/Jam/Materials")
    if "error" in salida:
        log(f"emitir falló: {salida['error']}")
        FALLAS.append("emitir")
        return
    log(f"emitido: {salida['info']}")
    material = salida["material"]

    # Lo primero, porque es lo que la corrida anterior dejó pasar: el emisor CUENTA las propiedades
    # que Unreal ignoró, y una ignorada es un nodo mal configurado que la topología no ve. Un
    # `transform_type` que no se aplicó deja el transform en su default y el árbol se mueve mal,
    # con todos los cables conectados y el grafo «verde».
    exigir("propiedades ignoradas" not in salida["info"],
           "ninguna propiedad quedó sin aplicar")

    L = unreal.MaterialEditingLibrary

    # 1 — la cuenta de nodos que quedó en el asset
    exigir(L.get_num_material_expressions(material) == firma["nodos"],
           f"nodos en el asset: {L.get_num_material_expressions(material)} "
           f"(el IR dice {firma['nodos']})")

    # 2 — los parámetros, que son la superficie que queda para retocar
    escalares = sorted(str(n) for n in L.get_scalar_parameter_names(material))
    vectores = sorted(str(n) for n in L.get_vector_parameter_names(material))
    esperados = sorted(firma["parametros"])
    exigir(sorted(escalares + vectores) == esperados,
           f"parámetros descubribles: escalares={escalares} vectores={vectores}")

    # 3 — la topología leída DE VUELTA del material, no la que creímos escribir
    leidas = set()
    pila, vistos = [], set()
    for nombre_prop in firma["salidas"]:
        nodo = L.get_material_property_input_node(material, getattr(unreal.MaterialProperty,
                                                                   nombre_prop))
        if nodo is None:
            exigir(False, f"{nombre_prop} quedó SIN conectar")
            continue
        leidas.add((type(nodo).__name__[len("MaterialExpression"):], nombre_prop))
        pila.append(nodo)
    while pila:
        nodo = pila.pop()
        if nodo.get_name() in vistos:
            continue
        vistos.add(nodo.get_name())
        entradas = L.get_inputs_for_material_expression(material, nodo)
        nombres = list(L.get_material_expression_input_names(nodo))
        for i, entrada in enumerate(entradas):
            if entrada is None:
                continue
            etiqueta = nombres[i] if i < len(nombres) else str(i)
            leidas.add((type(entrada).__name__[len("MaterialExpression"):],
                        type(nodo).__name__[len("MaterialExpression"):] + "." + etiqueta))
            pila.append(entrada)

    # Lo mismo desde el IR, para comparar manzanas con manzanas.
    del_ir = set()
    for arista in grafo.aristas:
        tipo_origen = grafo.nodo(arista.desde).tipo
        if arista.es_salida_del_material:
            del_ir.add((tipo_origen, arista.hasta))
        else:
            del_ir.add((tipo_origen, grafo.nodo(arista.hasta).tipo + "." + arista.entrada))

    faltan = del_ir - leidas
    sobran = leidas - del_ir
    exigir(not faltan and not sobran,
           f"topología leída == IR ({len(leidas)} aristas leídas de {len(del_ir)})"
           + (f" · FALTAN {sorted(faltan)[:5]}" if faltan else "")
           + (f" · SOBRAN {sorted(sobran)[:5]}" if sobran else ""))

    exigir(len(vistos) == firma["nodos"],
           f"nodos alcanzables desde las salidas: {len(vistos)} de {firma['nodos']} "
           f"(uno inalcanzable es un nodo que no hace nada)")

    # 4 — el oráculo de costo, que headless viene en cero. Se registra por si cambia.
    L.recompile_material(material)
    st = L.get_statistics(material)
    log(f"MaterialStatistics: PS={st.num_pixel_shader_instructions} "
        f"VS={st.num_vertex_shader_instructions} samplers={st.num_samplers} "
        f"interpoladores={st.num_interpolator_scalars}"
        + ("   (cero = los shaders no compilan en commandlet; hay que medirlo en el editor GUI)"
           if st.num_pixel_shader_instructions == 0 else "   ¡AHORA SÍ MIDE!"))

    # 5 — el VERBO, por el camino que usa el ejecutor: `fn(entrada, **params)` con TODO lo que
    # declara el registro. Es donde se rompen los verbos nuevos, y ningún test de Python lo ve.
    from jam import tools
    info = tools.REGISTRO["material_wind"]
    try:
        salida_verbo = info["fn"](None, **info["params"])
        exigir("WIND MATERIAL" in salida_verbo, f"el verbo corre por el ejecutor: {salida_verbo[:80]}")
    except Exception as exc:  # noqa: BLE001
        exigir(False, f"el verbo explotó: {type(exc).__name__}: {exc}")

    log("=" * 68)
    log("VEREDICTO: " + ("TODO VERDE" if not FALLAS else f"{len(FALLAS)} FALLA(S): {FALLAS}"))


main()
