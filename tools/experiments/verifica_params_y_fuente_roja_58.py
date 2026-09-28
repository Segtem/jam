"""Sonda de editor: `dsl-parametros` y `fuente-roja` por el camino real (api.run / Run del Graph).

    UnrealEditor ~/Dev/games/JamPlayground/JamPlayground.uproject -RenderOffScreen -unattended \
      -nosplash -ExecCmds="py <esta ruta>,QUIT_EDITOR"

Escribe el veredicto en el log (`JAM_PARAMS_FUENTE_ROJA …`) y en `Saved/jam_params_fuente_roja.json`
del proyecto host.
"""

import json
import os
import traceback

import unreal

MARCA = "JAM_PARAMS_FUENTE_ROJA"
CUBO = "/Engine/BasicShapes/Cube.Cube"

# Mass con una fuente que revienta en Run (37 frames para un presupuesto de 5) y un dependiente
# con efectos en escena (mass_spawn). Compile no lo ve: el presupuesto se juzga al correr.
GRAFO_MASS = {
    "nodes": {
        "recorrido": {"verb": "curve_bezier", "params": {"segments": "12"}, "x": 0, "y": 0},
        "frames": {"verb": "curve_frames", "params": {"count": "37"}, "x": 300, "y": 0},
        "receta": {"verb": "mass_spec", "params": {"budget": "5"}, "x": 600, "y": 0},
        "poblacion": {"verb": "mass_spawn", "params": {}, "x": 900, "y": 0},
        "medir": {"verb": "mass_inspect", "params": {}, "x": 1200, "y": 0},
    },
    "edges": [["recorrido", "out", "frames", "in"], ["frames", "out", "receta", "in"],
              ["receta", "out", "poblacion", "in"], ["poblacion", "out", "medir", "in"]],
}


def main():
    from jam import api, panel

    r = {}
    fallas = []

    # ---- dsl-parametros ----
    antes = len(unreal.EditorLevelLibrary.get_all_level_actors())
    r["cownt"] = api.run(f"scatter {CUBO} cownt=10")
    r["poison"] = api.run(f"scatter {CUBO} pattern=poison")
    despues = len(unreal.EditorLevelLibrary.get_all_level_actors())
    if "¿quisiste decir «count»?" not in r["cownt"]:
        fallas.append("cownt sin sugerencia")
    if "¿quisiste decir «poisson»?" not in r["poison"]:
        fallas.append("poison sin sugerencia")
    if despues != antes:
        fallas.append(f"un comando rechazado cambió la escena: {antes} → {despues} actores")
    r["bien"] = api.run(f"scatter {CUBO} count=3 pattern=grid")
    if "[error]" in r["bien"] or "no corrió" in r["bien"]:
        fallas.append("la línea bien escrita no corrió")
    r["descartar_bien"] = api.run("discard")

    # ---- fuente-roja ----
    envelope = json.loads(panel.ejecutar_grafo_json(json.dumps(GRAFO_MASS)))
    nodos = envelope.get("nodes", {})
    r["mass"] = {nid: v.get("estado") for nid, v in nodos.items()}
    r["mass_textos"] = {nid: v.get("texto") for nid, v in nodos.items()}
    r["mass_ok"] = envelope.get("ok")
    if r["mass"].get("receta") != "error":
        fallas.append(f"la fuente no quedó roja: {r['mass'].get('receta')}")
    for dep in ("poblacion", "medir"):
        if r["mass"].get(dep) != "cancelado":
            fallas.append(f"«{dep}» no quedó cancelado: {r['mass'].get(dep)}")
    if "«receta»" not in str(r["mass_textos"].get("medir")):
        fallas.append("el nieto no nombra la fuente")
    if envelope.get("ok") is not False:
        fallas.append("el Run no quedó rojo")

    r["fallas"] = fallas
    return r


try:
    resultado = main()
    veredicto = "VERDE" if not resultado["fallas"] else "ROJO"
except Exception:  # noqa: BLE001
    resultado = {"excepcion": traceback.format_exc()}
    veredicto = "EXCEPCION"

destino = os.path.join(unreal.Paths.project_saved_dir(), "jam_params_fuente_roja.json")
with open(destino, "w", encoding="utf-8") as f:
    json.dump({"veredicto": veredicto, **resultado}, f, ensure_ascii=False, indent=2)
unreal.log(f"{MARCA} {veredicto} → {destino}")
