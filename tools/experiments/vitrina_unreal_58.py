"""La vitrina de la base común en Unreal: el MISMO texto que en Godot y Unity, guardado en un nivel
para abrirlo y mirarlo (`/Game/Jam/Vitrina`). Tarea `base-comun`.

    JAM_VITRINA=<archivo con el texto> UnrealEditor JamPlayground.uproject -RenderOffScreen -unattended \
      -nosplash -ExecCmds="py <esta ruta>,QUIT_EDITOR"

Con `JAM_VITRINA_LEER=1` no escribe: reabre el nivel y cuenta lo que quedó (la prueba de que se
guardó de verdad). Resultado en `Saved/jam_vitrina.json` y la marca `JAM_VITRINA`.
"""

import json
import os
import traceback

import unreal

NIVEL = "/Game/Jam/Vitrina"


def mallas_del_nivel():
    q = unreal.GeometryScript_MeshQueries
    salida = {}
    for actor in unreal.EditorLevelLibrary.get_all_level_actors():
        if isinstance(actor, unreal.DynamicMeshActor):
            dm = actor.get_dynamic_mesh_component().get_dynamic_mesh()
            salida[actor.get_actor_label()] = int(q.get_num_triangle_i_ds(dm))
    return salida


def main():
    les = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
    if os.environ.get("JAM_VITRINA_LEER"):
        les.load_level(NIVEL)
        return {"leido": mallas_del_nivel()}
    from jam import api
    texto = open(os.environ["JAM_VITRINA"], encoding="utf-8").read()
    les.new_level(NIVEL)
    r = json.loads(api.run_text(texto, '{"nodes": {}, "edges": []}'))
    confirmado = api.confirm()
    guardado = les.save_current_level()
    return {"ok": r.get("ok"), "errores": r.get("errores"), "confirm": confirmado,
            "guardado": bool(guardado), "en_el_nivel": mallas_del_nivel()}


try:
    resultado = {"veredicto": "OK", **main()}
except Exception:  # noqa: BLE001
    resultado = {"veredicto": "EXCEPCION", "excepcion": traceback.format_exc()}
destino = os.path.join(unreal.Paths.project_saved_dir(), "jam_vitrina.json")
with open(destino, "w", encoding="utf-8") as f:
    json.dump(resultado, f, ensure_ascii=False, indent=2)
unreal.log(f"JAM_VITRINA {resultado['veredicto']} → {destino}")
