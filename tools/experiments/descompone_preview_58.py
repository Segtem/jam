"""¿En qué se van los 517 ms de «Ver sin hornear»? Descomponer antes de optimizar.

La medición anterior dijo que `mesh_preview` costaba 517 ms contra 57 ms de `mesh_to_static`, y de
ahí salió la conclusión de que spawnear un actor es el cuello. Esa medición tiene un defecto de
diseño: corrió `mesh_preview` PRIMERO y una sola vez, así que el arranque frío del proceso —cargar
la clase, inicializar subsistemas, importar módulos— cayó entero sobre el primer caso.

Esta sonda separa tres cosas que allá estaban mezcladas:

  1. **Orden y calentamiento** — se alterna A/B con repeticiones y se descarta la primera vuelta.
  2. **Piso de la maquinaria** — una cadena que termina en `mesh_ribbon` no crea actor ni asset, pero
     paga igual el `_preview` entero. Ese es el costo que ninguno de los dos terminales puede evitar.
  3. **Adentro del delta** — se instrumentan las funciones REALES (`mesh.mostrar`, `_marcar_preview`,
     `_todos`) envolviéndolas con un cronómetro que llama a la original. No es un atajo: corre el
     mismo camino, sólo que cronometrado por tramos.
"""
import json
import statistics
import time

import unreal

from jam import api, mesh, panel

REPETICIONES = 4  # la primera se descarta

def log(m):
    unreal.log(f"[DESCOMPONE] {m}")

FALLAS = []

def exigir(condicion, descripcion):
    log(("  OK   " if condicion else "  FALLA") + f" · {descripcion}")
    if not condicion:
        FALLAS.append(descripcion)


# --- instrumentación: envuelve la función real, no la reemplaza -------------------------------
TRAMOS = {}

def cronometrar_tramo(modulo, nombre):
    original = getattr(modulo, nombre)

    def envuelto(*a, **kw):
        t = time.perf_counter()
        try:
            return original(*a, **kw)
        finally:
            TRAMOS.setdefault(nombre, []).append((time.perf_counter() - t) * 1000.0)

    envuelto.__wrapped__ = original
    setattr(modulo, nombre, envuelto)
    return original


def cadena(terminal, indice=0):
    """La misma cadena de la medición anterior, con el terminal como única variable."""
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
        nombre = (f"SM_Descompone_{indice}" if terminal == "mesh_to_static"
                  else f"JamPreviewDescompone_{indice}")
        nodos["fin"] = {"verb": terminal, "params": {"name": nombre},
                        "asset": None, "x": 600, "y": 0}
        aristas.append(["cinta", "out", "fin", "in"])
    return json.dumps({"schema_version": 1, "nodes": nodos, "edges": aristas})


def correr(terminal, indice):
    if terminal == "mesh_to_static":
        try:
            unreal.EditorAssetLibrary.delete_asset(f"/Game/Jam/Meshes/SM_Descompone_{indice}")
        except Exception:  # noqa: BLE001
            pass
    TRAMOS.clear()
    t = time.perf_counter()
    salida = api.run_graph(cadena(terminal, indice))
    ms = (time.perf_counter() - t) * 1000.0
    return ms, salida, {k: sum(v) for k, v in TRAMOS.items()}


log("=" * 74)
log(f"Actores en el nivel: {len(panel._todos())}")

cronometrar_tramo(mesh, "mostrar")
cronometrar_tramo(panel, "_marcar_preview")
cronometrar_tramo(panel, "_todos")
cronometrar_tramo(panel, "_destruir_actores")

CASOS = [("sin terminal", None), ("hornear", "mesh_to_static"), ("ver sin hornear", "mesh_preview")]

medidas = {etiqueta: [] for etiqueta, _ in CASOS}
tramos_por_caso = {etiqueta: [] for etiqueta, _ in CASOS}

log("-" * 74)
log(f"{'vuelta':>7}  " + "  ".join(f"{e:>16}" for e, _ in CASOS))
for vuelta in range(REPETICIONES):
    fila = []
    for etiqueta, terminal in CASOS:
        ms, salida, tramos = correr(terminal, vuelta)
        fila.append(ms)
        if vuelta:  # la primera vuelta es el arranque frío: se mide y se muestra, no se promedia
            medidas[etiqueta].append(ms)
            tramos_por_caso[etiqueta].append(tramos)
        if "[error]" in salida:
            log(f"    ! {etiqueta}: {salida.splitlines()[0][:110]}")
    marca = " (frío, descartada)" if vuelta == 0 else ""
    log(f"{vuelta:>7}  " + "  ".join(f"{m:>14.1f}ms" for m in fila) + marca)

log("-" * 74)
mediana = {e: statistics.median(v) for e, v in medidas.items() if v}
for etiqueta, _ in CASOS:
    log(f"  mediana {etiqueta:>16}: {mediana.get(etiqueta, float('nan')):8.1f}ms")

piso = mediana.get("sin terminal", 0.0)
horno = mediana.get("hornear", 0.0)
preview = mediana.get("ver sin hornear", 0.0)
log("")
log(f"  piso de la maquinaria (lo paga cualquier Run): {piso:8.1f}ms")
log(f"  extra de hornear:                              {horno - piso:8.1f}ms")
log(f"  extra de ver sin hornear:                      {preview - piso:8.1f}ms")

log("-" * 74)
log("Adentro del extra de «ver sin hornear»:")
if tramos_por_caso["ver sin hornear"]:
    claves = sorted({k for t in tramos_por_caso["ver sin hornear"] for k in t})
    for clave in claves:
        valores = [t.get(clave, 0.0) for t in tramos_por_caso["ver sin hornear"]]
        log(f"    {clave:>20}: {statistics.median(valores):8.1f}ms")
    total_tramos = sum(statistics.median([t.get(k, 0.0) for t in tramos_por_caso["ver sin hornear"]])
                       for k in claves)
    log(f"    {'suma de tramos':>20}: {total_tramos:8.1f}ms  de {preview:.1f}ms medidos")
log("")
log("Los mismos tramos al hornear (para comparar el piso):")
if tramos_por_caso["hornear"]:
    for clave in sorted({k for t in tramos_por_caso["hornear"] for k in t}):
        valores = [t.get(clave, 0.0) for t in tramos_por_caso["hornear"]]
        log(f"    {clave:>20}: {statistics.median(valores):8.1f}ms")

log("-" * 74)
# La pregunta que la sonda tiene que contestar, con un veredicto que se pueda releer mañana.
exigir(piso > 0.0, "la cadena sin terminal corre y deja un piso medible")
exigir(preview < 517.0,
       f"con el arranque frío descartado, ver sin hornear baja de los 517ms del primer informe "
       f"(dio {preview:.1f}ms)")

log("JAM_DESCOMPONE_PREVIEW_58 TODO VERDE" if not FALLAS
    else f"JAM_DESCOMPONE_PREVIEW_58 ROJO — {len(FALLAS)}")
