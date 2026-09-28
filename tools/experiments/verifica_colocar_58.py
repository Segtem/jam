"""Sonda de editor: los casos de colocación de la base común (`casos_colocar.py`), corridos en Unreal
por el camino real del Graph (`api.run_text`), y la caja de mundo de cada instancia que colocó el
último paso, medida por el motor (`get_actor_bounds`). Es la referencia de `verifica_colocar.py`.

Corre en un nivel vacío propio (`/Game/Jam/Pruebas/Colocar`, que no se guarda): el nivel del banco
tiene piso, y el raycast de `surface` pegaría ahí antes que en el piso del caso.
Resultado en `Saved/jam_colocar.json` y la marca `JAM_COLOCAR`.
"""

import json
import os
import sys
import traceback

import unreal

sys.path.insert(0, os.path.expanduser("~/Dev/jam/tools/experiments"))
import casos_colocar as cc  # noqa: E402

NIVEL = "/Game/Jam/Pruebas/Colocar"


def _actores():
    return {a.get_path_name(): a for a in unreal.EditorLevelLibrary.get_all_level_actors()
            if isinstance(a, unreal.StaticMeshActor)}


def _caja(actor):
    origen, extension = actor.get_actor_bounds(False)
    return {"min": [round(origen.x - extension.x, 3), round(origen.y - extension.y, 3),
                    round(origen.z - extension.z, 3)],
            "max": [round(origen.x + extension.x, 3), round(origen.y + extension.y, 3),
                    round(origen.z + extension.z, 3)]}


def main():
    from jam import api
    les = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
    if unreal.EditorAssetLibrary.does_asset_exist(NIVEL):
        les.load_level(NIVEL)
    else:
        les.new_level(NIVEL)
    for actor in unreal.EditorLevelLibrary.get_all_level_actors():
        if isinstance(actor, (unreal.StaticMeshActor, unreal.DynamicMeshActor)):
            unreal.EditorLevelLibrary.destroy_actor(actor)
    casos, errores = {}, {}
    for nombre, pasos in cc.CASOS:
        api.discard()
        for paso in pasos:
            if paso == cc.FIJAR:
                api.confirm()
                continue
            antes = set(_actores())
            r = json.loads(api.run_text(paso, '{"nodes": {}, "edges": []}'))
            if not r.get("ok"):
                errores[nombre] = r.get("errores") or r.get("report")
                break
        nuevos = [a for p, a in _actores().items() if p not in antes]
        casos[nombre] = sorted((_caja(a) for a in nuevos), key=lambda c: (c["min"], c["max"]))
    api.discard()
    return {"casos": casos, "errores": errores}


try:
    resultado = main()
    resultado["veredicto"] = "ROJO" if resultado["errores"] else "OK"
except Exception:  # noqa: BLE001
    resultado = {"veredicto": "EXCEPCION", "excepcion": traceback.format_exc()}
destino = os.path.join(unreal.Paths.project_saved_dir(), "jam_colocar.json")
with open(destino, "w", encoding="utf-8") as f:
    json.dump(resultado, f, ensure_ascii=False, indent=1)
unreal.log(f"JAM_COLOCAR {resultado['veredicto']} → {destino}")
