"""Sonda de editor: coloca una ORDEN y vuelca la escena como hechos L0 para `oracle juzgar`.

Tarea `sonda-escena-l0` (plan: `commander/docs/AURA-PROPIO-CORTE-1.md`). La lanza
`tools/colocar_y_juzgar.py`; lee `Saved/Oracle/orden.json`:

    {"escena": [{"id", "asset", "loc": [x,y,z], "yaw", "escala": [sx,sy,sz]}, …],
     "tanda":  [ …lo mismo… ]}

En un nivel vacío propio (`/Game/Jam/Pruebas/Aura`, no se guarda) pone la `escena` como actores
normales y la `tanda` como Preview de Jam (tag `jam:preview`), y escribe `Saved/Oracle/escena.json`
con `ue.hechos_escena(tanda)`. `loc` es la ubicación del ACTOR (su pivote), tal cual la pide el agente.
"""

import json
import os
import traceback

import unreal

NIVEL = "/Game/Jam/Pruebas/Aura"
CARPETA = os.path.join(unreal.Paths.project_saved_dir(), "Oracle")


def _poner(item, preview):
    malla = unreal.EditorAssetLibrary.load_asset(item["asset"])
    if not isinstance(malla, unreal.StaticMesh):
        raise ValueError(f"{item['id']}: «{item['asset']}» no es una StaticMesh")
    x, y, z = item["loc"]
    actor = unreal.get_editor_subsystem(unreal.EditorActorSubsystem).spawn_actor_from_object(
        malla, unreal.Vector(x, y, z), unreal.Rotator(0.0, 0.0, float(item.get("yaw", 0.0))))
    actor.set_actor_scale3d(unreal.Vector(*item.get("escala", [1.0, 1.0, 1.0])))
    actor.set_actor_label(item["id"])
    if preview:
        actor.set_editor_property("tags", [unreal.Name("jam:preview")])
    return actor


def main():
    from jam import ue
    orden = json.load(open(os.path.join(CARPETA, "orden.json"), encoding="utf-8"))
    les = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
    if unreal.EditorAssetLibrary.does_asset_exist(NIVEL):
        les.load_level(NIVEL)
    else:
        les.new_level(NIVEL)
    for actor in ue.actores_nivel():
        if actor.get_components_by_class(unreal.StaticMeshComponent):
            unreal.EditorLevelLibrary.destroy_actor(actor)
    for item in orden.get("escena", []):
        _poner(item, preview=False)
    tanda = [_poner(item, preview=True) for item in orden.get("tanda", [])]
    return ue.hechos_escena(tanda)


try:
    hechos = main()
    marca = "OK"
except Exception:  # noqa: BLE001
    hechos = {"error": traceback.format_exc()}
    marca = "EXCEPCION"
os.makedirs(CARPETA, exist_ok=True)
with open(os.path.join(CARPETA, "escena.json"), "w", encoding="utf-8") as f:
    json.dump(hechos, f, ensure_ascii=False, indent=1)
unreal.log(f"JAM_ESCENA_L0 {marca}")
