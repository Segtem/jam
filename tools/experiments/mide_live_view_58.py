"""Dónde está REALMENTE el costo de un Run. Medido el 2026-08-11, sin errores:

    Borde de camino:  completo  68,8ms · geometría 1,0ms · HORNEADO  67,8ms (98,5%)
    Pino procedural:  completo 257,3ms · geometría 1,6ms · HORNEADO 255,7ms (99,4%)

**El caché de geometría no es la palanca del live view.** La geometría ya cuesta 1–1,6 ms: ahorrarle
el 92% son 1,5 ms. El 99% del costo es hornear a StaticMesh, y eso el caché NO puede tocarlo porque
produce un asset y escribir en Content es un efecto.

La palanca es NO HORNEAR: dibujar el preview con un `DynamicMeshComponent` en vez de crear un
StaticMesh lleva el cook de 68–257 ms a ~1–2 ms, sin caché de por medio. Dos órdenes de magnitud por
no hacer el trabajo, no por reusarlo. El horneado queda en Bake, una vez — que es como funciona
Houdini: cocina en memoria y escribe al disco sólo cuando se lo piden.

Se mide lo que importa por separado:
  A. Run COMPLETO con el asset de salida borrado antes: incluye el horneado real.
  B. El gesto del LIVE VIEW: recocinar tras tocar un parámetro, sin hornear.
"""
import json, os, statistics, time
import unreal
from jam import graph
from jam.cache import Almacen

EJEMPLOS = "/home/workstation/Dev/jam/Resources/Examples"
def log(m): unreal.log(f"[LIMPIO] {m}")

def borrar(rutas):
    for r in rutas:
        try:
            if unreal.EditorAssetLibrary.does_asset_exist(r):
                unreal.EditorAssetLibrary.delete_asset(r)
        except Exception:
            pass

def correr(g, plan, almacen=None):
    t = time.perf_counter()
    _r, por_nodo = graph.ejecutar_detalle(g, plan, almacen=almacen)
    return (time.perf_counter() - t) * 1000.0, por_nodo

log("=" * 74)
CASOS = {"Borde-de-camino.jamgraph": ["/Game/Jam/Meshes/SM_JamBordeCamino"],
         "TreeGen-Stylized-Pine.jamgraph": ["/Game/Jam/Meshes/SM_TreeGen_Pine_Test"]}

for archivo, assets in CASOS.items():
    crudo = open(os.path.join(EJEMPLOS, archivo), encoding="utf-8").read()
    g = graph.JamGraph.from_json(crudo)
    plan = graph.compilar(g)

    # A. Run completo, con el asset borrado: el horneado ocurre de verdad.
    borrar(assets)
    ms_completo, por_nodo = correr(g, plan)
    errores = sum(1 for r in por_nodo.values() if r.get("estado") == "error")
    log(f"{archivo[:30]:30} A · run completo (horneando): {ms_completo:7.1f}ms · errores={errores}")

    # B. El gesto del live view: SIN el nodo de hornear ni lo que cuelga de él.
    datos = json.loads(crudo)
    nodos = {k: v for k, v in (datos.get("nodes") or {}).items()
             if v.get("verb") not in ("mesh_to_static", "place", "hism_output")}
    aristas = [a for a in (datos.get("edges") or [])
               if a[0] in nodos and a[2] in nodos]
    g2 = graph.JamGraph.from_json(json.dumps(
        {"schema_version": 1, "nodes": nodos, "edges": aristas}))
    plan2 = graph.compilar(g2)

    sin_cache = statistics.median([correr(g2, plan2)[0] for _ in range(3)])
    a = Almacen()
    correr(g2, plan2, a)                                   # llena
    con_cache = statistics.median([correr(g2, plan2, a)[0] for _ in range(3)])
    e = a.estadisticas()
    ahorro = 100.0 * (sin_cache - con_cache) / sin_cache if sin_cache else 0.0
    log(f"{'':30} B · live view ({len(nodos)} nodos): sin {sin_cache:6.1f}ms → "
        f"con {con_cache:6.1f}ms = {ahorro:4.1f}% menos · {e['entradas']} en caché")
    log(f"{'':30}   el horneado que NO se cachea pesa "
        f"{ms_completo - sin_cache:7.1f}ms del total")
log("JAM_LIMPIO_58 MEDIDO")
