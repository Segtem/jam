"""La cadencia REAL del live view: el mismo grafo recocido una y otra vez.

Las dos mediciones anteriores contestaban una pregunta que no era la del live view. Un live view no
corre un grafo una vez: corre EL MISMO grafo cada vez que alguien mueve una perilla, y cada corrida
tiene que limpiar lo que dejó la anterior. Esa limpieza es parte del costo y hasta ahora quedaba
afuera del cronómetro o caía sobre la corrida equivocada.

Los tres defectos que arrastraban las mediciones previas, y cómo se corrigen acá:

  · **arranque frío** — la primera corrida del proceso pagaba la carga de clases y subsistemas.
    Se descarta una vuelta de calentamiento por terminal.
  · **orden** — alternar terminales hacía que la limpieza del asset horneado cayera sobre la corrida
    del preview. Cada terminal corre en su propia tanda, sin mezclarse.
  · **estado heredado** — el Preview arrastra lo que dejó el anterior. Se descarta el Preview entre
    tandas para que cada una empiece igual.

Lo que se mide es lo que el usuario va a sentir al arrastrar un slider.

⚠️ **Y por eso hay que correrla con el editor ANDANDO, no en commandlet.** Un cuarto defecto se
descubrió después, y era el más caro de todos: `-run=pythonscript` no tickea nunca, así que headless
el actor del preview no se spawnea de verdad y el horneado no espera los fences de render. Las dos
tablas, mismo grafo y mismas seis vueltas:

| recocción del mismo grafo | commandlet | editor andando |
|---|---|---|
| cadena sin terminal (el piso) | 1,4 ms | **1,8 ms** |
| `mesh_preview` (ver sin hornear) | 1,7 ms | **17,7 ms** |
| `mesh_to_static` (hornear) | 215,2 ms | **47,7 ms** |
| ventaja de no hornear | «129x» | **2,7x** |

La conclusión sobrevive —ver sin hornear es más barato y las dos caen debajo de los 100 ms— pero el
129x era del modo de medición. La sonda ahora se niega si la corren headless.
"""
import json
import statistics
import time

import unreal

from jam import api, panel

VUELTAS = 6

def log(m):
    unreal.log(f"[RECOCCION] {m}")

FALLAS = []

def exigir(condicion, descripcion):
    log(("  OK   " if condicion else "  FALLA") + f" · {descripcion}")
    if not condicion:
        FALLAS.append(descripcion)


def cadena(terminal, ancho):
    """El mismo grafo con UNA perilla movida: es exactamente lo que hace mover un slider."""
    nodos = {
        "eje": {"verb": "curve_bezier", "params": {
            "start_x": "0.0", "start_y": "0.0", "start_z": "0.0",
            "end_x": "900.0", "end_y": "0.0", "end_z": "80.0",
            "bend_x": "0.0", "bend_y": "320.0", "bend_z": "-40.0", "segments": "12"},
            "asset": None, "x": 0, "y": 0},
        "cinta": {"verb": "mesh_ribbon", "params": {"width": f"{ancho:.1f}"},
                  "asset": None, "x": 300, "y": 0},
    }
    aristas = [["eje", "out", "cinta", "in"]]
    if terminal:
        # El MISMO nombre en cada vuelta: recocinar es reemplazar, no acumular.
        nombre = "SM_Recoccion" if terminal == "mesh_to_static" else "JamPreviewRecoccion"
        nodos["fin"] = {"verb": terminal, "params": {"name": nombre},
                        "asset": None, "x": 600, "y": 0}
        aristas.append(["cinta", "out", "fin", "in"])
    return json.dumps({"schema_version": 1, "nodes": nodos, "edges": aristas})


def tanda(terminal, etiqueta):
    panel._descartar_preview("graph")  # cada tanda arranca sin heredar el Preview de la anterior
    api.run_graph(cadena(terminal, 300.0))  # calentamiento, fuera del cronómetro
    tiempos = []
    for vuelta in range(VUELTAS):
        t = time.perf_counter()
        salida = api.run_graph(cadena(terminal, 320.0 + vuelta * 10.0))
        tiempos.append((time.perf_counter() - t) * 1000.0)
        if "[error]" in salida:
            log(f"    ! {etiqueta}: {salida.splitlines()[0][:110]}")
    log(f"{etiqueta:>18}: " + " ".join(f"{t:6.1f}" for t in tiempos)
        + f"   mediana {statistics.median(tiempos):6.1f}ms")
    return statistics.median(tiempos)


def midiendo_headless() -> bool:
    """¿Esto corre en un commandlet, que no tickea nunca?

    No es un detalle de invocación: cambia el veredicto. Los mismos tres terminales dieron
    1,4 / 1,7 / 215,2 ms en `-run=pythonscript` y 1,8 / 17,7 / 47,7 con el loop del editor andando
    —«129x» contra «2,7x»—, porque headless ni el actor del preview se spawnea de verdad ni el
    horneado espera los fences de render que sí espera el editor. Se pregunta por la línea de
    comandos y no por adivinanza.
    """
    linea = str(getattr(unreal.SystemLibrary, "get_command_line", lambda: "")())
    return "-run=" in linea


log("=" * 78)
log(f"Recocción del mismo grafo, {VUELTAS} vueltas por terminal (ms por vuelta)")
exigir(not midiendo_headless(),
       "corriendo con el loop del editor andando (si no, estos números no valen: "
       'UnrealEditor … -RenderOffScreen -ExecCmds="py <script>,QUIT_EDITOR")')
log("-" * 78)
piso = tanda(None, "sin terminal")
horno = tanda("mesh_to_static", "hornear")
preview = tanda("mesh_preview", "ver sin hornear")

log("-" * 78)
log(f"  piso de la cadena:      {piso:7.1f}ms")
log(f"  hornear cada vuelta:    {horno:7.1f}ms   (+{horno - piso:.1f} sobre el piso)")
log(f"  ver sin hornear:        {preview:7.1f}ms   (+{preview - piso:.1f} sobre el piso)")
if preview > 0:
    log(f"  → ver sin hornear es {horno / max(preview, 0.01):.0f}x más rápido al recocinar")

log("-" * 78)
# 100 ms es el umbral clásico de «se siente instantáneo». No es un número que Jam inventó: es la
# frontera donde una acción deja de percibirse como respuesta y empieza a percibirse como espera.
exigir(preview < 100.0,
       f"recocinar sin hornear cae debajo de los 100ms que se sienten instantáneos "
       f"(dio {preview:.1f}ms)")
exigir(preview < horno,
       f"recocinar sin hornear es más barato que hornear (preview {preview:.1f}ms vs "
       f"horno {horno:.1f}ms)")

log("JAM_RECOCCION_58 TODO VERDE" if not FALLAS else f"JAM_RECOCCION_58 ROJO — {len(FALLAS)}")
