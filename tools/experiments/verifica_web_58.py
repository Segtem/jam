"""Sonda de editor: la puerta web de Jam (`jam.web`, 127.0.0.1:8790) dentro de Unreal, por HTTP.

La levanta `init_unreal.py` al arrancar el editor, y es lo que usan el editor de nodos web y
`jam-mcp`. Ninguna otra sonda le hacía un pedido HTTP (lo encontró el inventario de `editor-vigente`).
Como `jam.web` resuelve cada pedido en el game thread, los pedidos salen de un hilo aparte mientras el
editor tickea; al terminar, la sonda cierra el editor sola.

    UnrealEditor ~/Dev/games/JamPlayground/JamPlayground.uproject -RenderOffScreen -unattended \
      -nosplash -ExecCmds="py <esta ruta>"          # sin QUIT_EDITOR: sale sola

Mide: la página del editor y un archivo estático; `estado` (motor unreal, conectado); el spec con
los verbos habilitados; los ejemplos; correr el ejemplo `base_comun` por `correr_grafo`, con cada nodo
en ok; y `preview discard`. Resultado en `Saved/jam_web.json` y la marca
`JAM_WEB`.
"""

import json
import os
import threading
import time
import traceback
import urllib.request

import unreal

MARCA = "JAM_WEB"
URL = "http://127.0.0.1:8790"
estado = {"fin": False, "r": {}, "fallas": []}


def exigir(cond, texto):
    if not cond:
        estado["fallas"].append(texto)
    return cond


def get(ruta):
    with urllib.request.urlopen(URL + ruta, timeout=60) as r:
        return r.status, r.read().decode("utf-8")


def api(nombre, *args):
    pedido = urllib.request.Request(f"{URL}/api/{nombre}", method="POST",
                                    data=json.dumps({"args": list(args)}).encode())
    with urllib.request.urlopen(pedido, timeout=600) as r:
        crudo = json.loads(r.read())["resultado"]
    return json.loads(crudo) if isinstance(crudo, str) else crudo


def pedidos():
    try:
        r = estado["r"]
        codigo, html = get("/")
        exigir(codigo == 200 and "Editor de nodos" in html, f"GET / no es el editor: {codigo}")
        codigo, js = get("/vendor/litegraph.js")
        exigir(codigo == 200 and len(js) > 100000, f"litegraph.js: {codigo} · {len(js)} bytes")
        r["estado"] = api("estado")
        exigir(r["estado"].get("motor") == "unreal" and r["estado"].get("conectado"),
               f"estado: {r['estado']}")
        spec = api("spec_editor")
        tools = spec.get("tools", [])
        r["verbos"] = len(tools)
        r["deshabilitados"] = sorted(t["verbo"] for t in tools if not t.get("disponible", True))
        exigir(len(tools) > 100 and not r["deshabilitados"],
               f"en Unreal todo verbo está habilitado: {len(tools)} verbos, "
               f"deshabilitados {r['deshabilitados'][:5]}")
        ejemplos = api("ejemplos")
        r["ejemplos"] = len(ejemplos)
        base = next((e for e in ejemplos if e.get("nombre") == "base_comun"), None)
        exigir(base is not None and base.get("corre"), f"base_comun entre los ejemplos: {base}")
        grafo = api("ejemplo", "base_comun")
        corrida = api("correr_grafo", json.dumps(grafo))
        nodos = corrida.get("nodes", {})
        r["correr"] = {n: v.get("estado") for n, v in nodos.items()}
        exigir(corrida.get("ok") and nodos and set(nodos) == set(grafo["nodes"])
               and all(v.get("estado") == "ok" for v in nodos.values()),
               f"correr base_comun: {corrida.get('report', corrida)[:600]}")
        r["discard"] = api("preview", "discard")
        exigir(r["discard"].get("ok"), f"discard: {r['discard']}")
    except Exception:  # noqa: BLE001
        estado["fallas"].append(traceback.format_exc())
    estado["fin"] = True


def tick(_dt):
    if not estado["fin"]:
        if time.time() - T0 > 900:
            estado["fallas"].append("plazo de 15 min vencido")
            estado["fin"] = True
        return
    unreal.unregister_slate_post_tick_callback(manija)
    veredicto = "ROJO" if estado["fallas"] else "VERDE"
    destino = os.path.join(unreal.Paths.project_saved_dir(), "jam_web.json")
    with open(destino, "w", encoding="utf-8") as f:
        json.dump({"veredicto": veredicto, **estado["r"], "fallas": estado["fallas"]}, f,
                  ensure_ascii=False, indent=1)
    unreal.log(f"{MARCA} {veredicto} → {destino}")
    unreal.SystemLibrary.quit_editor()


T0 = time.time()
manija = unreal.register_slate_post_tick_callback(tick)
threading.Thread(target=pedidos, daemon=True).start()
