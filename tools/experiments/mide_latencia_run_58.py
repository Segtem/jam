"""¿Cuánto tarda un Run, y en qué se va el tiempo? Decide si el live view es viable.

Mide por separado lo que hoy está mezclado: compilar (cerebro puro), construir la geometría
(Geometry Script) y juzgar (el oráculo). Sin eso, «hacer caché» sería optimizar a ciegas.

Se usan tutoriales REALES como caso típico, no un grafo de laboratorio.
"""
import json, os, statistics, time
import unreal
from jam import api

RAIZ = "/home/workstation/Dev/jam"
EJEMPLOS = os.path.join(RAIZ, "Resources", "Examples")

def log(m): unreal.log(f"[LATENCIA] {m}")

def cronometrar(fn, vueltas=5):
    """Mediana de varias corridas: una sola medición mezcla el costo real con el arranque frío."""
    tiempos = []
    for _ in range(vueltas):
        t = time.perf_counter()
        try:
            fn()
        except Exception as exc:  # noqa: BLE001
            return None, f"{type(exc).__name__}: {exc}"
        tiempos.append((time.perf_counter() - t) * 1000.0)
    return tiempos, None

log("=" * 66)
catalogo = json.load(open(os.path.join(EJEMPLOS, "examples.json"), encoding="utf-8"))["ejemplos"]
casos = [e for e in catalogo if e["archivo"] in
         ("Borde-de-camino.jamgraph", "Muro-sobre-spline.jamgraph", "Primeros-pasos.jamgraph",
          "Terreno-con-ruido.jamgraph", "TreeGen-Stylized-Pine.jamgraph")]

log(f"{'tutorial':34} {'nodos':>5} {'compile':>10} {'run':>10}")
log("-" * 66)
for e in casos:
    grafo = open(os.path.join(EJEMPLOS, e["archivo"]), encoding="utf-8").read()
    nodos = len(json.loads(grafo).get("nodes") or {})

    t_compile, err_c = cronometrar(lambda: api.compile_graph_json(grafo))
    t_run, err_r = cronometrar(lambda: api.run_graph(grafo), vueltas=3)

    c = f"{statistics.median(t_compile):8.1f}ms" if t_compile else (err_c or "?")[:10]
    r = f"{statistics.median(t_run):8.1f}ms" if t_run else (err_r or "?")[:10]
    log(f"{e['titulo'][:34]:34} {nodos:>5} {c:>10} {r:>10}")

# ¿Cuánto cuesta lo puro vs lo que toca el motor? El compile no crea geometría; el run sí.
log("-" * 66)
grafo = open(os.path.join(EJEMPLOS, "Borde-de-camino.jamgraph"), encoding="utf-8").read()
t_c, _ = cronometrar(lambda: api.compile_graph_json(grafo), vueltas=20)
if t_c:
    log(f"compile x20 · mediana {statistics.median(t_c):.1f}ms · min {min(t_c):.1f} · max {max(t_c):.1f}")
    log(f"a esa velocidad, un cook por tecla daría {1000.0/max(statistics.median(t_c), 0.001):.0f} fps "
        f"SÓLO en la parte pura")
log("JAM_LATENCIA_58 MEDIDO")
