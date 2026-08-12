"""¿Qué puede saltarse una recocción VIVA y qué no?

El live view va a recocinar mientras alguien arrastra un slider, unas ocho veces por segundo. Un Run
del Graph no es sólo ejecutar el grafo: después refresca el inspector y las miniaturas de cada nodo,
y las dos cosas cruzan a Python. Si esas dos pesan, hay que dejarlas para cuando el arrastre termina.

Saltearlas «porque seguro pesan» sería adivinar. Se mide cada parte por su entrada real —la misma
que llama Slate— y recién con eso se decide qué entra en el presupuesto de una vuelta.

Presupuesto: para que un arrastre se sienta continuo, la vuelta entera tiene que caber en ~120 ms.

⚠️ **Corre sólo con el loop del editor andando** —se niega si no—, porque headless daba números que
no son de nadie: `run_graph` 1,7 ms contra los 20,1 reales. Las dos tablas:

| parte de la vuelta | commandlet | **editor andando** |
|---|---|---|
| ejecutar el grafo | 1,7 ms | **20,1 ms** |
| miniaturas | 1,8 ms | **1,7 ms** |
| inspector | 0,1 ms | **0,1 ms** |
| vuelta completa | 3,7 ms | **22,0 ms** |

**La decisión que sostiene esta sonda sale REFORZADA**: los accesorios eran la mitad de la vuelta
headless (1,9 de 3,7) y son el 8% de la de verdad (1,8 de 22,0). No hay que saltearlos en vivo, y la
vuelta entera entra seis veces en el presupuesto.
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


def midiendo_headless() -> bool:
    """¿Commandlet, que no tickea? Entonces estos números no son de nadie.

    Se pregunta por la línea de comandos y no por adivinanza. Medido: `run_graph` da 1,7 ms headless
    y 20,1 con el loop andando, porque headless el actor del preview no se spawnea de verdad.
    """
    linea = str(getattr(unreal.SystemLibrary, "get_command_line", lambda: "")())
    return "-run=" in linea


panel._descartar_preview("graph")
api.run_graph(cadena(300.0))  # calentamiento

log("=" * 78)
log("Las tres partes de un Run del Graph, por su entrada real:")
exigir(not midiendo_headless(),
       "corriendo con el loop del editor andando (si no, estos números no valen: "
       'UnrealEditor … -RenderOffScreen -ExecCmds="py <script>,QUIT_EDITOR")')
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
    accesorios = completo - ms_run
    log(f"  → refrescar miniaturas e inspector cuesta {accesorios:.1f}ms: "
        f"{accesorios / max(completo, 0.01) * 100:.0f}% de la vuelta y "
        f"{accesorios / max(PRESUPUESTO_MS, 0.01) * 100:.0f}% del presupuesto.")
    # Acá había un `exigir(caro or True, …)`: un assert que NO PUEDE FALLAR, escrito como si
    # hubiera verificado algo. La afirmación que de verdad sostiene la decisión —no hacer un
    # camino liviano aparte— es que la vuelta ENTERA entra en el presupuesto; esa sí es
    # falsable, y es la que se pregunta.
    exigir(completo < PRESUPUESTO_MS,
           f"la vuelta completa —cocinar Y refrescar— entra en {PRESUPUESTO_MS:.0f}ms "
           f"({completo:.1f}ms), así que no hace falta un camino liviano aparte")

log("JAM_VIVA_58 TODO VERDE" if not FALLAS else f"JAM_VIVA_58 ROJO — {len(FALLAS)}")
