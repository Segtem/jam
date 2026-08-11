"""¿Dónde están los 155 ms que la descomposición no encontró?

`descompone_preview_58.py` midió el extra de «ver sin hornear» en 156 ms y encontró apenas 0.7 ms
repartidos entre `mesh.mostrar`, `_marcar_preview`, `_todos` y `_destruir_actores`. Cronometrar por
tramos elegidos a mano sólo encuentra lo que uno sospecha; el resto queda invisible.

Un perfilador no elige: mide todas las llamadas. Acá se perfila el Run entero por el camino real y
se listan las funciones por tiempo propio, para las tres variantes —sin terminal, hornear, ver sin
hornear— y se restan entre sí. Lo que aparezca arriba en «ver sin hornear» y no en las otras dos es
el costo que hay que atacar, sin haberlo adivinado antes.
"""
import cProfile
import io
import json
import pstats

import unreal

from jam import api


def log(m):
    unreal.log(f"[PERFIL] {m}")


def cadena(terminal, indice=0):
    nodos = {
        "eje": {"verb": "curve_bezier", "params": {
            "start_x": "0.0", "start_y": "0.0", "start_z": "0.0",
            "end_x": "900.0", "end_y": "0.0", "end_z": "80.0",
            "bend_x": "0.0", "bend_y": "320.0", "bend_z": "-40.0", "segments": "12"},
            "asset": None, "x": 0, "y": 0},
        "cinta": {"verb": "mesh_ribbon", "params": {"width": "360.0"}, "asset": None, "x": 300, "y": 0},
    }
    aristas = [["eje", "out", "cinta", "in"]]
    if terminal:
        nombre = (f"SM_Perfil_{indice}" if terminal == "mesh_to_static"
                  else f"JamPreviewPerfil_{indice}")
        nodos["fin"] = {"verb": terminal, "params": {"name": nombre},
                        "asset": None, "x": 600, "y": 0}
        aristas.append(["cinta", "out", "fin", "in"])
    return json.dumps({"schema_version": 1, "nodes": nodos, "edges": aristas})


def perfilar(terminal, etiqueta, vueltas=3):
    # Una vuelta en frío afuera del perfil: el arranque no es lo que se quiere retratar.
    api.run_graph(cadena(terminal, 90))
    perfil = cProfile.Profile()
    perfil.enable()
    for i in range(vueltas):
        api.run_graph(cadena(terminal, i))
    perfil.disable()

    buffer = io.StringIO()
    estadistica = pstats.Stats(perfil, stream=buffer)
    estadistica.sort_stats("tottime")

    log("=" * 78)
    log(f"{etiqueta}  ({vueltas} corridas)")
    log(f"{'propio/corrida':>15} {'llamadas':>10}  función")
    log("-" * 78)
    filas = []
    for clave, (_llamadas, nllamadas, tottime, cumtime, _) in estadistica.stats.items():
        archivo, linea, nombre = clave
        corto = archivo.split("/")[-1] if archivo != "~" else "<nativo>"
        filas.append((tottime / vueltas * 1000.0, nllamadas / vueltas,
                      f"{corto}:{linea}({nombre})"))
    filas.sort(reverse=True)
    for ms, llamadas, nombre in filas[:14]:
        if ms < 0.2:
            break
        log(f"{ms:13.1f}ms {llamadas:10.0f}  {nombre}")
    total = sum(f[0] for f in filas)
    log(f"{total:13.1f}ms  (total perfilado por corrida)")
    return {f[2]: f[0] for f in filas}


sin_terminal = perfilar(None, "SIN TERMINAL — el piso")
horneado = perfilar("mesh_to_static", "HORNEAR")
preview = perfilar("mesh_preview", "VER SIN HORNEAR")

log("=" * 78)
log("Lo que «ver sin hornear» paga y el piso NO paga (ordenado por diferencia):")
log("-" * 78)
diferencias = sorted(
    ((ms - sin_terminal.get(nombre, 0.0), nombre) for nombre, ms in preview.items()),
    reverse=True)
for delta, nombre in diferencias[:12]:
    if delta < 0.5:
        break
    log(f"{delta:13.1f}ms  {nombre}   (hornear: {horneado.get(nombre, 0.0):.1f}ms)")

log("JAM_PERFIL_PREVIEW_58 LISTO")
