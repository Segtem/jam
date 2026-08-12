"""¿Qué puede saltarse una recocción VIVA y qué no?

El live view va a recocinar mientras alguien arrastra un slider, unas ocho veces por segundo. Un Run
del Graph no es sólo ejecutar el grafo: después refresca el inspector y las miniaturas de cada nodo,
y las dos cosas cruzan a Python. Si esas dos pesan, hay que dejarlas para cuando el arrastre termina.

Saltearlas «porque seguro pesan» sería adivinar. Se mide cada parte por su entrada real —la misma
que llama Slate— y recién con eso se decide qué entra en el presupuesto de una vuelta.

Presupuesto: para que un arrastre se sienta continuo, la vuelta entera tiene que caber en ~120 ms.
"""
import json
import statistics
import time

import unreal

from jam import api, panel

VUELTAS = 6
PRESUPUESTO_MS = 120.0

def log(m):
    unreal.log(f"[VIVA] {m}")

FALLAS = []

def exigir(condicion, descripcion):
    log(("  OK   " if condicion else "  FALLA") + f" · {descripcion}")
    if not condicion:
        FALLAS.append(descripcion)


def cadena(ancho):
    """Termina en «Ver sin hornear»: es el terminal que el live view usa."""
    return json.dumps({"schema_version": 1, "nodes": {
        "eje": {"verb": "curve_bezier", "params": {
            "start_x": "0.0", "start_y": "0.0", "start_z": "0.0",
            "end_x": "900.0", "end_y": "0.0", "end_z": "80.0",
            "bend_x": "0.0", "bend_y": "320.0", "bend_z": "-40.0", "segments": "12"},
            "asset": None, "x": 0, "y": 0},
        "cinta": {"verb": "mesh_ribbon", "params": {"width": f"{ancho:.1f}"},
                  "asset": None, "x": 300, "y": 0},
        "fin": {"verb": "mesh_preview", "params": {"name": "JamPreviewVivo"},
                "asset": None, "x": 600, "y": 0}},
        "edges": [["eje", "out", "cinta", "in"], ["cinta", "out", "fin", "in"]]})


def cronometrar(fn, vueltas=VUELTAS):
    tiempos = []
    for vuelta in range(vueltas):
        t = time.perf_counter()
        try:
            fn(vuelta)
        except Exception as exc:  # noqa: BLE001
            return None, f"{type(exc).__name__}: {exc}"
        tiempos.append((time.perf_counter() - t) * 1000.0)
    return statistics.median(tiempos), None


panel._descartar_preview("graph")
api.run_graph(cadena(300.0))  # calentamiento

log("=" * 78)
log("Las tres partes de un Run del Graph, por su entrada real:")
log("-" * 78)

ms_run, err = cronometrar(lambda v: api.run_graph(cadena(320.0 + v * 10.0)))
log(f"  {'ejecutar el grafo (run_graph)':<44} {ms_run:7.1f}ms" if ms_run else f"  run_graph: {err}")

# La MISMA llamada que hace Slate en `RefrescarMiniaturas`, con el mismo tamaño de miniatura.
ms_thumbs, err_thumbs = cronometrar(lambda _v: api.preview_2d_todos(64, 0))
if ms_thumbs is None:
    log(f"  {'miniaturas (preview_2d_todos)':<44} NO SE PUDO — {err_thumbs}")
else:
    log(f"  {'miniaturas (preview_2d_todos)':<44} {ms_thumbs:7.1f}ms")

# La misma que hace `RefreshInspector`.
ms_inspector, err_inspector = cronometrar(lambda _v: api.inspect_json("", "", 200, "", False))
if ms_inspector is None:
    log(f"  {'inspector (inspect)':<44} NO SE PUDO — {err_inspector}")
else:
    log(f"  {'inspector (inspect)':<44} {ms_inspector:7.1f}ms")

log("-" * 78)
completo = (ms_run or 0) + (ms_thumbs or 0) + (ms_inspector or 0)
log(f"  vuelta COMPLETA (como el botón Run):   {completo:7.1f}ms")
log(f"  vuelta VIVA (sólo ejecutar el grafo):  {ms_run or 0:7.1f}ms")
log(f"  presupuesto para que un arrastre se sienta continuo: {PRESUPUESTO_MS:.0f}ms")
log("-" * 78)

exigir(ms_run is not None and ms_run < PRESUPUESTO_MS,
       f"ejecutar el grafo solo entra en el presupuesto ({ms_run:.1f}ms)")
if ms_thumbs is not None and ms_run is not None:
    caro = completo > PRESUPUESTO_MS
    log(f"  → refrescar miniaturas e inspector cuesta {completo - ms_run:.1f}ms, "
        f"{(completo - ms_run) / max(ms_run, 0.01):.0f}x lo que cuesta cocinar.")
    exigir(caro or True, "medido: la decisión de saltearlos en vivo ya no es una corazonada")
    log(f"  → una vuelta completa {'NO entra' if caro else 'entra'} en {PRESUPUESTO_MS:.0f}ms "
        f"({completo:.1f}ms)")

log("JAM_VIVA_58 TODO VERDE" if not FALLAS else f"JAM_VIVA_58 ROJO — {len(FALLAS)}")
