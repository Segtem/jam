"""Sonda de editor: `dsl-grafos` — el texto de un grafo corre por el Run del canvas.

    UnrealEditor ~/Dev/games/JamPlayground/JamPlayground.uproject -RenderOffScreen -unattended \
      -nosplash -ExecCmds="py <esta ruta>,QUIT_EDITOR"

Resultado en `Saved/jam_texto.json` del proyecto y la marca `JAM_TEXTO` en el log.
"""

import json
import os
import traceback

import unreal

MARCA = "JAM_TEXTO"
EJEMPLO = os.path.expanduser("~/Dev/jam/Resources/Examples/Cylinder-Strip.jamgraph")
ESCRITO = """\
caja = mesh_box
tubo = mesh_normals @caja
hornear = mesh_to_static @tubo name=SM_JamTextoSonda
colocar = place @hornear view=true
"""


def actores():
    return len(unreal.EditorLevelLibrary.get_all_level_actors())


def main():
    from jam import api

    r, fallas = {}, []

    # 1. Un documento escrito a mano, por api.run: el reporte ubica cada nodo en su línea.
    r["escrito"] = api.run(ESCRITO)
    for n in ("línea 1 [caja·", "línea 4 [colocar·"):
        if n not in r["escrito"]:
            fallas.append(f"el reporte no dice «{n}»")
    if "[error]" in r["escrito"] or "✗" in r["escrito"].split("\n")[0]:
        fallas.append("el documento escrito no corrió en verde")
    r["descartar_1"] = api.discard()

    # 2. Un documento con error no corre ni cambia la escena.
    antes = actores()
    r["con_error"] = api.run("caja = mesh_box\ncolocar = place @cajaa\n")
    if actores() != antes:
        fallas.append("un texto con error cambió la escena")
    if "¿quisiste decir «caja»?" not in r["con_error"]:
        fallas.append("el error no sugiere «caja»")

    # 3. Ida y vuelta por el motor: el ejemplo como texto corre igual que su .jamgraph.
    with open(EJEMPLO, encoding="utf-8") as f:
        original = f.read()
    t = json.loads(api.graph_text(original))["texto"]
    por_json = json.loads(api.run_graph_json(original))
    api.discard()
    por_texto = json.loads(api.run_text(t, original))
    api.discard()
    r["estados_json"] = {k: v.get("estado") for k, v in por_json.get("nodes", {}).items()}
    r["estados_texto"] = {k: v.get("estado") for k, v in por_texto.get("nodes", {}).items()}
    r["textos_iguales"] = {k: por_json["nodes"][k].get("texto") == v.get("texto")
                           for k, v in por_texto.get("nodes", {}).items() if k in por_json["nodes"]}
    if r["estados_json"] != r["estados_texto"] or not por_texto.get("ok"):
        fallas.append("el ejemplo por texto no dio los mismos estados que por JSON")
    if not all(r["textos_iguales"].values()):
        fallas.append("algún nodo reportó distinto por texto que por JSON")
    r["fallas"] = fallas
    return r


try:
    resultado = main()
    veredicto = "VERDE" if not resultado["fallas"] else "ROJO"
except Exception:  # noqa: BLE001
    resultado = {"excepcion": traceback.format_exc()}
    veredicto = "EXCEPCION"

destino = os.path.join(unreal.Paths.project_saved_dir(), "jam_texto.json")
with open(destino, "w", encoding="utf-8") as f:
    json.dump({"veredicto": veredicto, **resultado}, f, ensure_ascii=False, indent=2)
unreal.log(f"{MARCA} {veredicto} → {destino}")
