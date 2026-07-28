"""El oráculo de COSTO de materiales, medido en el editor. Necesita `-AllowCommandletRendering`.

Durante un tiempo quedó anotado que `MaterialStatistics` daba cero headless y que hacía falta el
editor GUI. Es falso: da cero **sin** `-AllowCommandletRendering`, porque sin RHI no hay
`FMaterialResource` para `GMaxRHIShaderPlatform` y `GetStatistics` sale por su valor por defecto.
Con el flag, las instrucciones se mueven con la complejidad y el oráculo de costo existe.

Esto lo fija para que no haya que volver a descubrirlo, y comprueba las tres cosas que lo hacen
utilizable:

    1. el número CRECE con la complejidad (si no, no mide nada, sólo devuelve una constante);
    2. el piso anotado en `materials.PISO` sigue siendo el piso;
    3. el presupuesto acepta lo barato y rechaza lo caro, por el camino del verbo.

Correr:

    UnrealEditor-Cmd <proyecto>.uproject -run=pythonscript \\
        -script=<plugin>/tools/experiments/verifica_costo_material.py \\
        -RenderOffScreen -unattended -nosplash -stdout -AllowCommandletRendering
"""

from __future__ import annotations

import unreal

from jam import materials, shader, tools


FALLAS = []


def log(mensaje: str) -> None:
    unreal.log(f"[COSTO] {mensaje}")


def exigir(condicion: bool, descripcion: str) -> None:
    log(("  OK   " if condicion else "  FALLA") + f" · {descripcion}")
    if not condicion:
        FALLAS.append(descripcion)


def encadenar(n: int, nombre: str) -> shader.GrafoMaterial:
    g = shader.vacio(nombre)
    g, _ = shader.con_nodo(g, "WorldPosition", id="pos")
    previo = ""
    for i in range(n):
        g, ruido = shader.con_nodo(g, "Noise", id=f"r{i}", entradas={"World Position": "pos"},
                                   props={"noise_function": "NOISEFUNCTION_VALUE_ALU",
                                          "levels": 4, "scale": 0.01 * (i + 1)})
        if not previo:
            previo = ruido
        else:
            g, previo = shader.con_nodo(g, "Add", id=f"s{i}",
                                        entradas={"A": previo, "B": ruido})
    return shader.con_salida(g, previo, "MP_BASE_COLOR")


def main() -> None:
    log("=" * 70)

    medidas = {}
    for n in (1, 4, 12):
        nombre = f"M_JamCosto{n}"
        salida = materials.emitir(encadenar(n, nombre), "/Game/Jam/_Sonda")
        if "error" in salida:
            exigir(False, f"n={n}: {salida['error']}")
            return
        medidas[n] = salida["costo"]
        log(f"n={n:2d} → {materials.resumen_de_costo(salida['costo'])}")

    exigir(all(m["medido"] for m in medidas.values()),
           "las tres mediciones son mediciones (no ceros disfrazados)")
    ps = [medidas[n]["ps"] for n in (1, 4, 12)]
    exigir(ps[0] < ps[1] < ps[2],
           f"el costo CRECE con la complejidad: {ps} (si fuera constante no mediría nada)")

    # --- el piso anotado sigue siendo el piso ---
    g = shader.vacio("M_JamPiso")
    g, c = shader.con_nodo(g, "Constant3Vector", props={"constant": (0.5, 0.5, 0.5)})
    g = shader.con_salida(g, c, "MP_BASE_COLOR")
    piso = materials.emitir(g, "/Game/Jam/_Sonda")["costo"]
    exigir(piso["ps"] == materials.PISO["ps"] and piso["vs"] == materials.PISO["vs"],
           f"el piso medido {piso['ps']}/{piso['vs']} == el anotado "
           f"{materials.PISO['ps']}/{materials.PISO['vs']}")
    exigir(medidas[1]["ps"] > piso["ps"],
           "un grafo con ruido cuesta más que el piso")

    # --- shading_model: el campo que estaba declarado y no se aplicaba ---
    sin_luz = shader.GrafoMaterial("M_JamUnlit", g.nodos, g.aristas, shading_model="MSM_UNLIT")
    salida = materials.emitir(sin_luz, "/Game/Jam/_Sonda")
    material = salida["material"]
    exigir(material.get_editor_property("shading_model") ==
           unreal.MaterialShadingModel.MSM_UNLIT,
           f"shading_model aplicado: {material.get_editor_property('shading_model')}")

    # --- el presupuesto, por el camino del verbo ---
    info = tools.REGISTRO["material_build"]
    barato = shader.vacio("M_JamPresupuesto")
    barato, c = shader.con_nodo(barato, "Constant3Vector", props={"constant": (0.2, 0.2, 0.2)})
    barato = shader.con_salida(barato, c, "MP_BASE_COLOR")
    params = dict(info["params"])
    params.update({"name": "M_JamPresupuesto", "folder": "/Game/Jam/_Sonda",
                   "max_instructions": materials.PISO["ps"] + 50})
    try:
        exigir("MATERIAL BUILD" in info["fn"](barato, **params),
               "un material barato pasa el presupuesto")
    except Exception as exc:  # noqa: BLE001
        exigir(False, f"el material barato NO pasó: {exc}")

    caro = encadenar(12, "M_JamPresupuestoCaro")
    params.update({"name": "M_JamPresupuestoCaro", "max_instructions": 500})
    try:
        info["fn"](caro, **params)
        exigir(False, "un material caro TENDRÍA que reprobar el presupuesto y pasó")
    except RuntimeError as exc:
        exigir("PRESUPUESTO" in str(exc), f"el caro reprueba y dice por qué: {str(exc)[:120]}")
    exigir(unreal.EditorAssetLibrary.does_asset_exist("/Game/Jam/_Sonda/M_JamPresupuestoCaro"),
           "el asset caro queda creado igual, para poder abrirlo y ver qué lo encareció")

    for ruta in unreal.EditorAssetLibrary.list_assets("/Game/Jam/_Sonda", recursive=True):
        unreal.EditorAssetLibrary.delete_asset(ruta)
    log("=" * 70)
    log("VEREDICTO: " + ("TODO VERDE" if not FALLAS else f"{len(FALLAS)} FALLA(S): {FALLAS}"))


main()
