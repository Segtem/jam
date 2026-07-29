"""Corre el tutorial «Primer material» tal cual lo correría alguien que recién llega.

`verifica_ejemplos.py` comprueba que los tutoriales COMPILEN. Éste corre el de materiales de punta a
punta, porque lo que enseña depende de plomería nueva que sólo falla al ejecutarse: el pin `A` que
lleva la salida de `material_build` al `mesh_material` de la malla. Sin ese cable había que copiar la
ruta del material a mano de un nodo a otro — el paso manual que un grafo existe para eliminar.

    UnrealEditor-Cmd <proyecto>.uproject -run=pythonscript \\
        -script=<plugin>/tools/experiments/verifica_tutoriales_material.py \\
        -RenderOffScreen -unattended -nosplash -stdout -AllowCommandletRendering
"""

from __future__ import annotations

import json
import os

import unreal

from jam import api


FALLAS = []
RAIZ = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
EJEMPLOS = os.path.join(RAIZ, "Resources", "Examples")


def log(m: str) -> None:
    unreal.log(f"[TUTOMAT] {m}")


def exigir(condicion: bool, descripcion: str) -> None:
    log(("  OK   " if condicion else "  FALLA") + f" · {descripcion}")
    if not condicion:
        FALLAS.append(descripcion)


def correr_tutorial(archivo: str) -> dict:
    """Corre el tutorial SIN sus nodos `place`.

    Un commandlet no tiene nivel: `SpawnActor` no falla con una excepción, tira el proceso entero
    (crash en `InternalActorUtilitiesSubsystemLibrary::SpawnActor`). Colocar en la escena es
    justamente lo que hay que mirar con los ojos, y por eso `verifica_ejemplos.py` sólo compila.
    Acá se corre todo lo demás, que es donde vive la plomería que sí se puede juzgar sola.
    """
    with open(os.path.join(EJEMPLOS, archivo), encoding="utf-8") as f:
        datos = json.load(f)
    colocadores = {nid for nid, n in datos["nodes"].items() if n.get("verb") == "place"}
    datos["nodes"] = {nid: n for nid, n in datos["nodes"].items() if nid not in colocadores}
    datos["edges"] = [e for e in datos["edges"]
                      if e[0] not in colocadores and e[2] not in colocadores]
    if colocadores:
        log(f"    (sin {len(colocadores)} nodo(s) `place`: no hay nivel en un commandlet)")
    reporte = json.loads(api.run_graph_json(json.dumps(datos)))
    for nid, estado in reporte["nodes"].items():
        if estado["estado"] == "error":
            exigir(False, f"{archivo} · nodo «{nid}»: {estado['texto']}")
        else:
            log(f"    [{nid}] {estado['texto'][:150]}")
    return reporte


def main() -> None:
    log("=" * 70)

    log("── Primer material ──")
    correr_tutorial("Primer-material.jamgraph")

    ruta_material = "/Game/Jam/Materials/M_MiPrimerMaterial"
    material = unreal.EditorAssetLibrary.load_asset(ruta_material)
    exigir(material is not None, f"el tutorial creó {ruta_material}")
    if material is not None:
        escalares = [str(n) for n in
                     unreal.MaterialEditingLibrary.get_scalar_parameter_names(material)]
        exigir("Rugosidad" in escalares,
               f"con su parámetro retocable: {escalares}")

    # El Run del canvas es TRANSACCIONAL: hornea a `/Game/JamPreview/` y recién Bake lo fija en su
    # ruta final. Buscar la malla en `/Game/Jam/Meshes` daría «no existe» aunque todo haya andado.
    previas = [r for r in unreal.EditorAssetLibrary.list_assets("/Game/JamPreview", recursive=True)
               if "SM_MiPrimerMaterial" in r]
    exigir(bool(previas), f"la malla salió al preview transaccional: {previas[:1]}")
    malla = unreal.EditorAssetLibrary.load_asset(previas[0]) if previas else None
    if malla is not None:
        materiales = [m.material_interface for m in malla.get_editor_property("static_materials")]
        rutas = [m.get_path_name() if m else "None" for m in materiales]
        exigir(any(ruta_material in r for r in rutas),
               f"EL CABLE FUNCIONA: la malla lleva el material construido en el grafo → {rutas}")

    log("── UVs para texturar ──")
    correr_tutorial("UVs-para-texturar.jamgraph")
    uv = [r for r in unreal.EditorAssetLibrary.list_assets("/Game/JamPreview", recursive=True)
          if "SM_EscaleraUV" in r]
    exigir(bool(uv), f"el tutorial de UVs dejó su malla horneada: {uv[:1]}")

    log("=" * 70)
    log("VEREDICTO: " + ("TODO VERDE" if not FALLAS else f"{len(FALLAS)} FALLA(S): {FALLAS}"))


main()
