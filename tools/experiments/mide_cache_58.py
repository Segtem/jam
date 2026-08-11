"""¿El caché ahorra de verdad? Mismo grafo dos veces, con y sin almacén.

Medido el 2026-08-11: 82–90% menos en la corrida repetida, con tasa de acierto 75%.

DUDA RESUELTA el 2026-08-11, y en dos partes:

1. **Los nodos SÍ construyen** — `BEZIER S ✓ 13 points`, `CONE M ✓ 192 triángulos`. El ahorro es
   sobre trabajo real, no sobre nodos vacíos.
2. **Pero estos números subestiman el Run completo.** En los dos grafos falla el nodo de hornear
   —«el asset final ya existe»— que es **el más caro de la cadena**, y falla RÁPIDO. Por eso acá da
   1,4 ms y la línea base daba 359: aquella incluía el horneado, la primera vez que el asset no
   existía.

**Consecuencia de diseño que hay que tener presente:** `mesh_to_static` produce `A` y por lo tanto
NO es cacheable —escribir en Content es un efecto—. O sea que el nodo más caro se paga siempre y el
ahorro real en un Run completo es bastante menor que este 87%.

Para el LIVE VIEW eso está bien: mientras se ajustan parámetros no se hornea nada, se mira la malla,
y ahí el caché rinde. Pero «87% más rápido» NO es una promesa válida sobre el Run completo.

Para medirlo bien: borrar los assets de salida antes de la corrida, o medir por `api.run_graph`
pasándole el almacén.
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
