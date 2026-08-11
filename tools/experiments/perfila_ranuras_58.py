"""¿Por qué una ranura del ping-pong cuesta 85 ms y la otra 15?

`verifica_pingpong_58.py` bajó la recocción horneando de 215 ms a 50 ms de mediana, pero el detalle
por vuelta salió bimodal —15, 85, 16, 84, 12, 101— y perfectamente alternado con la ranura escrita.
Una mediana esconde eso: la mitad de las corridas cuesta seis veces la otra mitad.

Deducir de dónde sale la asimetría sería repetir el error de hoy. Se perfila: dos perfiles separados,
uno para las vueltas pares y otro para las impares, y se restan. Lo que aparezca en uno y no en el
otro es la causa, sin haberla adivinado.
"""
import cProfile
import io
import json
import pstats
import time

import unreal

from jam import api, panel

VUELTAS = 8

def log(m):
    unreal.log(f"[RANURAS] {m}")


def cadena(ancho):
    return json.dumps({"schema_version": 1, "nodes": {
        "eje": {"verb": "curve_bezier", "params": {
            "start_x": "0.0", "start_y": "0.0", "start_z": "0.0",
            "end_x": "900.0", "end_y": "0.0", "end_z": "80.0",
            "bend_x": "0.0", "bend_y": "320.0", "bend_z": "-40.0", "segments": "12"},
            "asset": None, "x": 0, "y": 0},
        "cinta": {"verb": "mesh_ribbon", "params": {"width": f"{ancho:.1f}"},
                  "asset": None, "x": 300, "y": 0},
        "fin": {"verb": "mesh_to_static", "params": {"name": "SM_Ranura"},
                "asset": None, "x": 600, "y": 0}},
        "edges": [["eje", "out", "cinta", "in"], ["cinta", "out", "fin", "in"]]})


def vigente():
    registros = panel._PREVIEW_ASSETS_BY_OWNER.get("graph", [])
    return (registros[0]["temp"].rsplit("/", 1)[-1] if registros else "?")


panel._descartar_preview("graph")
api.run_graph(cadena(300.0))  # calentamiento

pares, impares = cProfile.Profile(), cProfile.Profile()
tiempos, ranuras = [], []
for vuelta in range(VUELTAS):
    perfil = pares if vuelta % 2 == 0 else impares
    perfil.enable()
    t = time.perf_counter()
    api.run_graph(cadena(320.0 + vuelta * 10.0))
    ms = (time.perf_counter() - t) * 1000.0
    perfil.disable()
    tiempos.append(ms)
    ranuras.append(vigente())

log("=" * 80)
log("  " + "  ".join(f"{r[:5]}:{ms:.0f}ms" for r, ms in zip(ranuras, tiempos)))
log("=" * 80)


def filas(perfil, vueltas):
    estadistica = pstats.Stats(perfil, stream=io.StringIO())
    salida = {}
    for clave, (_ll, nll, tottime, _cum, _) in estadistica.stats.items():
        archivo, linea, nombre = clave
        corto = archivo.split("/")[-1] if archivo != "~" else "<nativo>"
        salida[f"{corto}:{linea}({nombre})"] = (tottime / vueltas * 1000.0, nll / vueltas)
    return salida


mitad = VUELTAS // 2
f_pares, f_impares = filas(pares, mitad), filas(impares, mitad)
etiqueta_par = ranuras[0][:5]
etiqueta_impar = ranuras[1][:5]

log(f"{'propio/corrida ' + etiqueta_par:>26} {'  ' + etiqueta_impar:>12}  {'llam.':>6}  función")
log("-" * 80)
todas = sorted(set(f_pares) | set(f_impares),
               key=lambda k: -abs(f_pares.get(k, (0, 0))[0] - f_impares.get(k, (0, 0))[0]))
for clave in todas[:12]:
    a, na = f_pares.get(clave, (0.0, 0.0))
    b, nb = f_impares.get(clave, (0.0, 0.0))
    if abs(a - b) < 0.3 and max(a, b) < 1.0:
        break
    log(f"{a:22.1f}ms {b:10.1f}ms  {na:3.0f}/{nb:<3.0f}  {clave}")

log("-" * 80)
log(f"  total perfilado {etiqueta_par}: {sum(v[0] for v in f_pares.values()):.1f}ms/corrida")
log(f"  total perfilado {etiqueta_impar}: {sum(v[0] for v in f_impares.values()):.1f}ms/corrida")
log("JAM_RANURAS_58 LISTO")
