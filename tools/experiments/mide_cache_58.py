"""¿El caché ahorra de verdad? Mismo grafo dos veces, con y sin almacén.

Medido el 2026-08-11: 82–90% menos en la corrida repetida, con tasa de acierto 75%.

⚠️ **Los números absolutos NO son comparables con `mide_latencia_run_58`** y hay que resolver eso
antes de creerles. Acá `ejecutar_detalle` directo da 1,4 ms donde `api.run_graph` daba 359: una
diferencia de 250× que el caché no explica. O `run_graph` hace mucho más —preview, marcado,
oráculo— o los nodos fallaron en silencio sin construir geometría, que es plausible sin asset
activo ni contexto de preview. En el segundo caso el 87% sería el ahorro de saltear nodos que no
hicieron nada, o sea ninguno.

Para cerrarlo: imprimir el estado por nodo y confirmar que construyen de verdad, o medir por el
mismo camino que la línea base (`api.run_graph`) pasándole el almacén.
"""
import json, os, statistics, time
import unreal
from jam import graph
from jam.cache import Almacen

EJEMPLOS = "/home/workstation/Dev/jam/Resources/Examples"
def log(m): unreal.log(f"[CACHE] {m}")

def correr(g, plan, almacen=None):
    t = time.perf_counter()
    graph.ejecutar_detalle(g, plan, almacen=almacen)
    return (time.perf_counter() - t) * 1000.0

log("=" * 72)
for archivo in ("Borde-de-camino.jamgraph", "Muro-sobre-spline.jamgraph",
                "TreeGen-Stylized-Pine.jamgraph"):
    crudo = open(os.path.join(EJEMPLOS, archivo), encoding="utf-8").read()
    g = graph.JamGraph.from_json(crudo)
    try:
        plan = graph.compilar(g)
    except Exception as exc:
        log(f"{archivo}: no compila acá ({exc})"); continue

    sin = statistics.median([correr(g, plan) for _ in range(3)])

    a = Almacen()
    primera = correr(g, plan, a)          # llena el caché
    repetidas = [correr(g, plan, a) for _ in range(3)]
    con = statistics.median(repetidas)
    e = a.estadisticas()

    ahorro = (100.0 * (sin - con) / sin) if sin else 0.0
    log(f"{archivo[:32]:32} sin {sin:6.1f}ms · 1ra {primera:6.1f}ms · repetida {con:6.1f}ms "
        f"→ {ahorro:5.1f}% menos")
    log(f"   caché: {e['entradas']} entradas · {e['aciertos']} aciertos / {e['fallos']} fallos "
        f"· tasa {e['tasa']:.0%}")
log("JAM_CACHE_58 MEDIDO")
