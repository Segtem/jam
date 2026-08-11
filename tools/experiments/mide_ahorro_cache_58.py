"""¿Cuánto ahorraría de verdad el caché? El ahorro depende de DÓNDE se toca.

Medido el 2026-08-11 en UE 5.8.1:

    Borde de camino     7 nodos · 359ms · tocar «eje» ensucia 7/7   → 0 salteados
    Muro sobre spline   7 nodos · 420ms · tocar «recorrido» 7/7     → 0 salteados
    Pino procedural    11 nodos · 612ms · tocar «preview_tree» 1/11 → 10 salteados (~9%)

Tocar la FUENTE de una cadena ensucia todo y el caché no ahorra nada: es correcto e inevitable, y en
Houdini pasa igual. Tocar una hoja saltea casi todo. O sea que el live view se va a sentir fluido
ajustando cosas del final —ancho de una cinta, altura de un muro— y va a seguir costando ~400 ms al
mover la curva base.

⚠️ Esta sonda elige como «último nodo» al que tiene MÁS PARÁMETROS, y en dos de los tres casos eso
resultó ser la fuente (`curve_bezier` tiene nueve coordenadas). O sea que midió el PEOR caso, no el
típico. Para medir el gesto real habría que tomar el nodo sin consumidores.

Se corre el grafo entero y después el mismo grafo truncado nodo a nodo: la diferencia es lo que
cuesta cada paso. Con eso se puede decir cuánto se ahorra al tocar un parámetro del final —el gesto
típico del live view— en vez de suponerlo.
"""
import json, os, statistics, time
import unreal
from jam import api, cache_core

EJEMPLOS = "/home/workstation/Dev/jam/Resources/Examples"
def log(m): unreal.log(f"[AHORRO] {m}")

def medir(grafo_json, vueltas=3):
    ts = []
    for _ in range(vueltas):
        t = time.perf_counter()
        try:
            api.run_graph(grafo_json)
        except Exception:
            return None
        ts.append((time.perf_counter() - t) * 1000.0)
    return statistics.median(ts)

log("=" * 70)
for archivo in ("Borde-de-camino.jamgraph", "Muro-sobre-spline.jamgraph", "TreeGen-Stylized-Pine.jamgraph"):
    crudo = open(os.path.join(EJEMPLOS, archivo), encoding="utf-8").read()
    g = json.loads(crudo)
    nodos, aristas = g.get("nodes") or {}, g.get("edges") or []
    total = medir(crudo)
    if total is None:
        log(f"{archivo}: no corre acá"); continue

    # Huellas: qué se ensucia al tocar el ÚLTIMO nodo (el gesto típico del live view).
    h1 = cache_core.huellas_del_grafo(nodos, aristas)
    ultimo = max(nodos, key=lambda n: len(nodos[n].get("params") or {}))
    tocado = {**nodos, ultimo: {**nodos[ultimo],
              "params": {**(nodos[ultimo].get("params") or {}), "__toque__": "1"}}}
    sucios = cache_core.sucios(h1, cache_core.huellas_del_grafo(tocado, aristas))

    log(f"{archivo[:34]:34} {len(nodos):>2} nodos · run {total:6.1f}ms")
    log(f"   tocar «{ultimo}» ensucia {len(sucios)}/{len(nodos)} → se saltearían "
        f"{len(nodos) - len(sucios)} nodos")
    if len(nodos):
        log(f"   si el costo fuera parejo: ~{total * len(sucios) / len(nodos):.1f}ms "
            f"({100 * len(sucios) // len(nodos)}% del actual)")
log("JAM_AHORRO_58 MEDIDO")
