"""Sonda de editor: cada GENERADOR de la base común, corrido por el camino real del Graph en Unreal
(núcleo → `mesh.desde_malla`), medido por el motor y comparado con lo que Geometry Script producía
(el fixture `tests/fixtures/primitivas_unreal.json`). Tarea `base-comun`.

Compara triángulos, vértices (tras soldar), caja envolvente y área. Resultado en
`Saved/jam_comunes.json` y la marca `JAM_COMUNES`.
"""

import json
import os
import traceback

import unreal

FIXTURE = os.path.expanduser("~/Dev/jam/Content/Python/tests/fixtures/primitivas_unreal.json")
VOLCADOR = os.path.expanduser("~/Dev/jam/tools/experiments/volcar_primitivas_58.py")


def main():
    from jam import registro, tools
    funciones = {}
    exec(compile(open(VOLCADOR, encoding="utf-8").read().split("\ntry:\n    datos =")[0],
                 VOLCADOR, "exec"), funciones)
    medir = funciones["medir"]
    generadores = {v for v in registro.COMUNES if tools.REGISTRO[v].get("source")}
    filas, fallas = [], []
    for caso in json.load(open(FIXTURE, encoding="utf-8"))["casos"]:
        if caso["verbo"] not in generadores or "error" in caso:
            continue
        tools.limpiar_asset_producido_runtime(caso["verbo"])
        tools.REGISTRO[caso["verbo"]]["fn"](None, **caso["params"])
        m = medir(tools.dato_producido_runtime(caso["verbo"]))
        esperado = caso["motor"]
        igual = (m["triangulos"], m["vertices"], m["min"], m["max"]) == (
            esperado["triangulos"], esperado["vertices"], esperado["min"], esperado["max"]) and \
            abs(m["area"] - esperado["area"]) <= 1e-3 * max(1.0, esperado["area"])
        filas.append({"verbo": caso["verbo"], "params": caso["params"], "igual": igual,
                      "nucleo_en_unreal": {k: m[k] for k in ("triangulos", "vertices", "min", "max", "area")}})
        if not igual:
            fallas.append(f"{caso['verbo']} {caso['params']}: distinto de Geometry Script")
    return {"generadores": sorted(generadores), "casos": filas, "fallas": fallas}


try:
    r = main()
    resultado = {"veredicto": "VERDE" if not r["fallas"] and r["casos"] else "ROJO", **r}
except Exception:  # noqa: BLE001
    resultado = {"veredicto": "EXCEPCION", "excepcion": traceback.format_exc()}
destino = os.path.join(unreal.Paths.project_saved_dir(), "jam_comunes.json")
with open(destino, "w", encoding="utf-8") as f:
    json.dump(resultado, f, ensure_ascii=False, indent=1)
unreal.log(f"JAM_COMUNES {resultado['veredicto']} → {destino}")
