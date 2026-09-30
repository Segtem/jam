"""Sonda de editor: una función del usuario en el texto, por su NOMBRE, con la biblioteca de verdad.

Tarea `dsl-grafos` («instancias fn: por etiqueta»). Colapsa una función como lo hace el canvas
(`api.collapse_function`), escribe el grafo padre con `api.graph_text` —la instancia tiene que salir
`fn:"<nombre>"`, no `fn:<id>`—, lo lee de vuelta con `api.graph_from_text` —la instancia vuelve al
mismo id y el Compile expande su interior—, y borra la función. Marca `JAM_TEXTO_FUNCIONES`.

    UnrealEditor ~/Dev/games/JamPlayground/JamPlayground.uproject -RenderOffScreen -unattended \
      -nosplash -ExecCmds="py <esta ruta>,QUIT_EDITOR"
"""

import json
import os
import traceback

import unreal

from jam import api
from jam.graph import JamGraph

MARCA = "JAM_TEXTO_FUNCIONES"
NOMBRE = "Cilindro doblado sonda"
fallas, r, verbo = [], {}, ""


def exigir(cond, texto):
    if not cond:
        fallas.append(texto)


try:
    plano = JamGraph()
    plano.add("mesh_cylinder", {"radius": 30.0}, nid="cil", x=0, y=20)
    plano.add("mesh_transform", {"scale_x": 2.0}, nid="t1", x=200, y=20)
    plano.add("mesh_normals", {}, nid="n1", x=400, y=20)
    plano.connect("cil", "t1")
    plano.connect("t1", "n1")
    colapsado = json.loads(api.collapse_function(NOMBRE, plano.to_json(), json.dumps(["t1", "n1"])))
    exigir(colapsado.get("ok"), f"collapse_function: {colapsado.get('report')}")
    verbo = colapsado["tool"]["verbo"]
    padre = json.dumps(colapsado["graph"])

    escrito = json.loads(api.graph_text(padre))
    r["texto"] = escrito.get("texto", "")
    exigir(f'"fn:{NOMBRE}"' in r["texto"] and verbo not in r["texto"],
           f"la instancia no se escribió por su nombre: {r['texto']!r}")

    leido = json.loads(api.graph_from_text(r["texto"], padre))
    exigir(leido.get("ok"), f"graph_from_text: {leido.get('errores')}")
    verbos = {n["verb"] for n in (leido.get("graph") or {}).get("nodes", {}).values()}
    exigir(verbo in verbos, f"la instancia no volvió al id {verbo}: {sorted(verbos)}")
    exigir(leido.get("canonico") == r["texto"], "el texto releído no es el mismo (punto fijo)")

    mal = json.loads(api.graph_from_text(r["texto"].replace(NOMBRE, NOMBRE + "x"), padre))
    r["error_mal_escrito"] = (mal.get("errores") or [{}])[0].get("mensaje", "")
    exigir(not mal.get("ok") and "quisiste decir" in r["error_mal_escrito"],
           f"un nombre mal escrito no sugirió el bueno: {mal.get('errores')}")
except Exception:  # noqa: BLE001
    fallas.append(traceback.format_exc())
finally:
    if verbo:
        api.function_manage("delete", verbo)

veredicto = "ROJO" if fallas else "VERDE"
destino = os.path.join(unreal.Paths.project_saved_dir(), "jam_texto_funciones.json")
with open(destino, "w", encoding="utf-8") as f:
    json.dump({"veredicto": veredicto, **r, "fallas": fallas}, f, ensure_ascii=False, indent=1)
unreal.log(f"{MARCA} {veredicto} → {destino}")
