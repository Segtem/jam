"""Sonda de editor: `dsl-grafos`, tramo 3 — lo que corre por texto aparece en el Graph abierto.

    UnrealEditor ~/Dev/games/JamPlayground/JamPlayground.uproject -RenderOffScreen -unattended \
      -nosplash -ExecCmds="Jam.AbrirGraph,py <esta ruta>"

Recorre el lazo entero a través de Slate: el Graph (C++) publica su grafo a Python en cada cambio
(`canvas_publicar`); `api.run` de un DOCUMENTO lo deja en el buzón; el Graph lo levanta
(`canvas_pendiente`), lo carga y vuelve a publicarlo. Si lo que el Graph publica al final trae los
nodos del texto con sus nombres, pasó por todas las piezas. Sale sola; resultado en
`Saved/jam_texto_canvas.json` y la marca `JAM_TEXTO_CANVAS` en el log.
"""

import json
import os
import time
import traceback

import unreal

MARCA = "JAM_TEXTO_CANVAS"
DOC = "caja = mesh_box size_x=50\nnormales = mesh_normals @caja\n"
T0 = time.time()
estado = {"paso": 0, "r": {}, "fallas": []}
manija = None


def terminar(veredicto):
    unreal.unregister_slate_post_tick_callback(manija)
    destino = os.path.join(unreal.Paths.project_saved_dir(), "jam_texto_canvas.json")
    with open(destino, "w", encoding="utf-8") as f:
        json.dump({"veredicto": veredicto, **estado["r"], "fallas": estado["fallas"]}, f,
                  ensure_ascii=False, indent=2)
    unreal.log(f"{MARCA} {veredicto} → {destino}")
    unreal.SystemLibrary.quit_editor()


def tick(_dt):
    try:
        from jam import api
        t = time.time() - T0
        r = estado["r"]
        if estado["paso"] == 0 and t > 3.0:
            r["publicado_al_abrir"] = bool(api._CANVAS["json"])
            if not r["publicado_al_abrir"]:
                estado["fallas"].append("el Graph no publicó su grafo al abrirse (¿se abrió el tab?)")
            r["run"] = api.run(DOC)
            estado["paso"] = 1
        elif estado["paso"] == 1 and t > 7.0:
            canvas = json.loads(api._CANVAS["json"] or "{}")
            nodos = canvas.get("nodes", {})
            r["nodos_en_el_canvas"] = {k: v.get("verb") for k, v in nodos.items()}
            r["size_x"] = nodos.get("caja", {}).get("params", {}).get("size_x")
            r["texto_del_canvas"] = json.loads(api.graph_text())["texto"]
            if r["nodos_en_el_canvas"] != {"caja": "mesh_box", "normales": "mesh_normals"}:
                estado["fallas"].append("el Graph no mostró el grafo que corrió por texto")
            if r["texto_del_canvas"] != DOC:
                estado["fallas"].append("el texto del canvas no es el que se escribió")
            terminar("VERDE" if not estado["fallas"] else "ROJO")
        elif t > 60.0:
            estado["fallas"].append("se agotó el tiempo")
            terminar("ROJO")
    except Exception:  # noqa: BLE001
        estado["r"]["excepcion"] = traceback.format_exc()
        terminar("EXCEPCION")


manija = unreal.register_slate_post_tick_callback(tick)
