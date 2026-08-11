"""«Ver sin hornear» por el camino REAL del Graph: Compile + Run, contra el mismo grafo horneando.

⚠️ La primera versión de esta sonda medía UNA corrida de cada terminal, alternadas, sin calentar, y
daba que hornear era 10x más rápido — lo contrario de la verdad. Tenía tres confusiones encima:
el arranque frío caía sobre el primer terminal medido; el orden hacía que la limpieza del asset
horneado se cobrara en la corrida del preview; y una sola vuelta no distingue costo de arranque.

Acá cada terminal corre su propia tanda, con calentamiento descartado y mediana de varias vueltas.
Ver `mide_recoccion_58.py`, que mide la cadencia del live view con el mismo cuidado.
"""
import json, statistics, time
import unreal
from jam import api, graph, panel

def log(m): unreal.log(f"[VERBO] {m}")
FALLAS = []
def exigir(c, d):
    log(("  OK   " if c else "  FALLA") + f" · {d}")
    if not c: FALLAS.append(d)

def cadena(ultimo):
    return json.dumps({"schema_version": 1, "nodes": {
        "eje": {"verb": "curve_bezier", "params": {"start_x": "0.0", "start_y": "0.0",
                "start_z": "0.0", "end_x": "900.0", "end_y": "0.0", "end_z": "80.0",
                "bend_x": "0.0", "bend_y": "320.0", "bend_z": "-40.0", "segments": "12"},
                "asset": None, "x": 0, "y": 0},
        "cinta": {"verb": "mesh_ribbon", "params": {"width": "360.0"}, "asset": None, "x": 300, "y": 0},
        "fin": {"verb": ultimo, "params": ({"name": "SM_PruebaHornear"} if ultimo == "mesh_to_static"
                else {"name": "JamPreviewVerbo"}), "asset": None, "x": 600, "y": 0}},
        "edges": [["eje", "out", "cinta", "in"], ["cinta", "out", "fin", "in"]]})

log("=" * 70)
medianas = {}
for ultimo in ("mesh_preview", "mesh_to_static"):
    g_json = cadena(ultimo)
    reporte = json.loads(api.compile_graph_json(g_json))
    malos = {n: e["texto"] for n, e in reporte["nodes"].items() if e.get("estado") == "error"}
    exigir(not malos, f"«{ultimo}» compila en el Graph ({malos or 'sin errores'})")

    # Cada terminal en su tanda y sin heredar el Preview del anterior: si no, el que corre segundo
    # paga el borrado del asset que dejó el primero, y la comparación mide otra cosa.
    panel._descartar_preview("graph")
    salida = api.run_graph(g_json)  # calentamiento
    ok = "error" not in salida.lower() or "✓" in salida
    exigir(ok, f"«{ultimo}» corre sin error")

    tiempos = []
    for _ in range(4):
        t = time.perf_counter()
        api.run_graph(g_json)
        tiempos.append((time.perf_counter() - t) * 1000.0)
    medianas[ultimo] = statistics.median(tiempos)
    log(f"  Run con «{ultimo}»: mediana {medianas[ultimo]:7.1f}ms  de {[f'{x:.1f}' for x in tiempos]}")

if len(medianas) == 2:
    a, b = medianas["mesh_preview"], medianas["mesh_to_static"]
    log("-" * 70)
    log(f"ver sin hornear {a:.1f}ms  ·  hornear {b:.1f}ms  →  {b/max(a,0.01):.0f}x más rápido")
    exigir(a < b, "ver sin hornear es más rápido que hornear, por el camino del Graph")

log("JAM_VERBO_PREVIEW_58 TODO VERDE" if not FALLAS else f"JAM_VERBO_PREVIEW_58 ROJO — {len(FALLAS)}")
