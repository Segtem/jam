"""El ping-pong de ranuras POR EL CAMINO REAL: ¿bajó la recocción y sigue estando todo bien?

Los tests de `test_preview_transaction.py` miden la máquina de estados con un Unreal falso, y las
seis mutaciones que probé confirman que discriminan. Pero lo que motivó el cambio es un costo del
motor de verdad —`delete_asset` cuesta 142 ms— y la única forma de saber si el ahorro existe es
correr el Graph adentro del editor.

Se mide lo mismo que `mide_recoccion_58.py` para poder comparar contra el número de antes (215 ms),
y además se comprueba que el ahorro no se llevó puesto nada:

  · que la ranura ALTERNE de verdad entre corridas,
  · que el asset staged siga apareciendo donde tiene que aparecer,
  · que Bake promueva UN asset final y no dos —el riesgo propio de tener dos ranuras vivas—,
  · que Discard no deje basura en `/Game/JamPreview`.
"""
import json
import statistics
import time

import unreal

from jam import api, panel

VUELTAS = 6
FINAL_ESPERADO = "/Game/Jam/Meshes/SM_PingPong"

def log(m):
    unreal.log(f"[PINGPONG] {m}")

FALLAS = []

def exigir(condicion, descripcion):
    log(("  OK   " if condicion else "  FALLA") + f" · {descripcion}")
    if not condicion:
        FALLAS.append(descripcion)


def cadena(ancho):
    return json.dumps({"schema_version": 1, "nodes": {
        "eje": {"verb": "curve_bezier", "params": {
            "start_x": "0.0", "start_y": "0.0", "start_z": "0.0",
            "end_x": "900.0", "end_y": "0.0", "end_z": "80.0",
            "bend_x": "0.0", "bend_y": "320.0", "bend_z": "-40.0", "segments": "12"},
            "asset": None, "x": 0, "y": 0},
        "cinta": {"verb": "mesh_ribbon", "params": {"width": f"{ancho:.1f}"},
                  "asset": None, "x": 300, "y": 0},
        "fin": {"verb": "mesh_to_static", "params": {"name": "SM_PingPong"},
                "asset": None, "x": 600, "y": 0}},
        "edges": [["eje", "out", "cinta", "in"], ["cinta", "out", "fin", "in"]]})


def staged_vigente():
    registros = panel._PREVIEW_ASSETS_BY_OWNER.get("graph", [])
    return registros[0]["temp"] if registros else None


log("=" * 78)
# Arrancar de cero: un Preview heredado de otra corrida falsearía la primera vuelta.
panel._descartar_preview("graph")
for ruta in ("/Game/Jam/Meshes/SM_PingPong", "/Game/Jam/Meshes/SM_PingPong_2"):
    try:
        unreal.EditorAssetLibrary.delete_asset(ruta)
    except Exception:  # noqa: BLE001
        pass

api.run_graph(cadena(300.0))  # calentamiento
log("Recocción del mismo grafo horneando (lo que antes costaba 215,2 ms/vuelta)")
log("-" * 78)

tiempos, ranuras = [], []
for vuelta in range(VUELTAS):
    t = time.perf_counter()
    salida = api.run_graph(cadena(320.0 + vuelta * 10.0))
    tiempos.append((time.perf_counter() - t) * 1000.0)
    ranuras.append(staged_vigente())
    if "[error]" in salida:
        log(f"    ! {salida.splitlines()[0][:120]}")

mediana = statistics.median(tiempos)
log("  " + " ".join(f"{x:6.1f}" for x in tiempos) + f"   mediana {mediana:6.1f}ms")
log("  ranuras: " + " ".join((r or "?").rsplit("/", 1)[-1][:6] for r in ranuras))
log("-" * 78)

exigir(mediana < 215.2,
       f"la recocción horneando baja de los 215,2 ms de antes (dio {mediana:.1f}ms, "
       f"{215.2 / max(mediana, 0.01):.1f}x)")
exigir(len({r for r in ranuras if r}) == 2,
       f"la ruta staged ALTERNA entre dos ranuras y no más ({len({r for r in ranuras if r})} distintas)")
exigir(ranuras[0] and ranuras[0] == ranuras[2],
       "la tercera vuelta vuelve a la ranura de la primera (la basura no crece)")

vigente = staged_vigente()
exigir(bool(vigente) and unreal.EditorAssetLibrary.does_asset_exist(vigente),
       f"el asset staged vigente existe en Content ({vigente})")

log("-" * 78)
log("Bake: el riesgo propio de tener dos ranuras vivas es promover las DOS.")
reporte = panel._h_confirmar(owner="graph")
finales = [r for r in unreal.EditorAssetLibrary.list_assets(
    "/Game/Jam/Meshes", recursive=False, include_folder=False) if "SM_PingPong" in r]
log(f"  finales tras Bake: {finales}")
exigir(len(finales) == 1,
       f"Bake promueve UN asset final y no dos ({len(finales)}: {finales})")
exigir(not unreal.EditorAssetLibrary.does_directory_exist("/Game/JamPreview/graph")
       or not [p for p in unreal.EditorAssetLibrary.list_assets(
           "/Game/JamPreview/graph", recursive=True, include_folder=False) if "PingPong" in p],
       "Bake barre la ranura sobrante y no deja staging huérfano")

# Y otra vez desde cero, para medir el Discard.
for ruta in list(finales):
    try:
        unreal.EditorAssetLibrary.delete_asset(ruta.split(".", 1)[0])
    except Exception:  # noqa: BLE001
        pass
api.run_graph(cadena(400.0))
api.run_graph(cadena(410.0))
panel._h_descartar(owner="graph")
sobrantes = []
if unreal.EditorAssetLibrary.does_directory_exist("/Game/JamPreview/graph"):
    sobrantes = [p for p in unreal.EditorAssetLibrary.list_assets(
        "/Game/JamPreview/graph", recursive=True, include_folder=False) if "PingPong" in p]
exigir(not sobrantes, f"Discard no deja ninguna ranura atrás ({sobrantes})")

log("JAM_PINGPONG_58 TODO VERDE" if not FALLAS else f"JAM_PINGPONG_58 ROJO — {len(FALLAS)}")
