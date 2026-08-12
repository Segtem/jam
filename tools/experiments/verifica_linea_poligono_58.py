"""Línea, línea por dirección y polígono, por el camino REAL del Graph.

Peldaños 2, 3 y 4 de la escalera de Grasshopper Basics. Los tests puros fijan la geometría, pero lo
que hay que demostrar acá es que el motor los acepta como nodos: que el spec los publique, que
Compile los valide con sus pines de vector, y que una cadena `Unitario X → Línea por dirección →
Barrer` produzca una malla de verdad.

La prueba de fuego del peldaño 3 es el POLÍGONO: cerrar la polilínea tiene que dar una curva más
larga que la abierta, con un punto más, y decirlo en el reporte.

⚠️ **Esta sonda encontró un defecto que los 1053 tests puros no veían.** Un pin de dato OPCIONAL sin
cable recibía `None` y el valor ESCRITO en la ficha se perdía: alguien tipeaba «0,0,500» en el
extremo de una línea, veía el número en el nodo, y el verbo recibía nada. El peor tipo de silencio,
porque la interfaz muestra un valor que no se está usando. Ahora un pin opcional sin cable usa lo
escrito, que es además cómo funciona Grasshopper: toda entrada se puede tipear O cablear.
"""
import json
from pathlib import Path

import unreal

from jam import api
from jam.graph import JamGraph

RAIZ = Path("/home/workstation/Dev/jam")


def log(m):
    unreal.log(f"[LINEA] {m}")


FALLAS = []


def exigir(condicion, descripcion):
    log(("  OK   " if condicion else "  FALLA") + f" · {descripcion}")
    if not condicion:
        FALLAS.append(descripcion)


log("=" * 78)
spec = {item["verbo"]: item for item in json.loads(api.spec_all())["tools"]}
for verbo, etiqueta in (("curve_line", "Línea"), ("curve_line_sdl", "Línea por dirección")):
    exigir(verbo in spec, f"el spec publica {verbo}")
    exigir(spec.get(verbo, {}).get("label") == etiqueta, f"{verbo} se llama «{etiqueta}»")

log("-" * 78)
log("Una línea sin cablear nada: los extremos se escriben en la ficha.")
suelta = JamGraph()
suelta.add("curve_line", {"desde": "0,0,0", "hasta": "0,0,500"}, nid="linea")
compilado = json.loads(api.compile_graph_json(suelta.to_json()))
exigir(compilado.get("ok"),
       f"Compile acepta una línea sin cables (pines de vector OPCIONALES): {compilado}")
corrida = json.loads(api.run_graph_json(suelta.to_json()))
exigir(corrida.get("ok"), f"Run de la línea suelta: {corrida}")
exigir("500" in corrida.get("report", ""), f"la línea mide 500: {corrida.get('report','')[:120]}")

log("-" * 78)
log("Y la misma línea armada con vectores cableados (peldaños 1 y 4 juntos):")
cableada = JamGraph()
# La dirección va por X y no por Z: `mesh_ribbon` barre en el plano xy, así que una línea
# vertical mediría CERO ahí y el motor la rechaza con razón. La primera versión de esta sonda
# usaba Z y el rojo era del test, no del código.
cableada.add("vector_unit_x", {"largo": 1}, nid="arriba")
cableada.add("curve_line_sdl", {"origen": "0,0,0", "largo": 500}, nid="linea")
cableada.add("mesh_ribbon", {"width": 120.0}, nid="cinta")
cableada.connect("arriba", "linea", "direccion")
cableada.connect("linea", "cinta", "in")
compilado_cable = json.loads(api.compile_graph_json(cableada.to_json()))
exigir(compilado_cable.get("ok"), f"Compile de la cadena V→S→M: {compilado_cable}")
corrida_cable = json.loads(api.run_graph_json(cableada.to_json()))
exigir(corrida_cable.get("ok"), f"Run de la cadena V→S→M: {corrida_cable}")
exigir("RIBBON" in corrida_cable.get("report", "").upper(),
       f"la cinta se construyó sobre la línea: {corrida_cable.get('report','')[:160]}")

log("-" * 78)
log("El polígono: cerrar la polilínea con el interruptor del peldaño 0.")


def poligono(cerrada):
    g = JamGraph()
    g.add("series_range", {"count": 4, "start": 0.0, "end": 300.0}, nid="serie")
    g.add("boolean", {"value": cerrada}, nid="cerrar")
    g.add("curve_polyline", {}, nid="poli")
    g.connect("serie", "poli", "x")
    g.connect("serie", "poli", "y")
    g.connect("serie", "poli", "z")
    g.connect("cerrar", "poli", "closed")
    return g


for cerrada in (False, True):
    g = poligono(cerrada)
    compilado_poli = json.loads(api.compile_graph_json(g.to_json()))
    exigir(compilado_poli.get("ok"),
           f"Compile de la polilínea (cerrada={cerrada}): {compilado_poli}")
    corrida_poli = json.loads(api.run_graph_json(g.to_json()))
    reporte = corrida_poli.get("report", "")
    log(f"  cerrada={cerrada}: {reporte.splitlines()[0][:96] if reporte else corrida_poli}")
    exigir(corrida_poli.get("ok"), f"Run de la polilínea (cerrada={cerrada}): {corrida_poli}")
    exigir(("cerrada" in reporte) == cerrada,
           f"el reporte dice si está cerrada (cerrada={cerrada})")

log("-" * 78)
log("Peldaño 5 — Interpolar: la MISMA entrada que la polilínea, cambiando sólo el verbo.")


def por_los_puntos(verbo):
    g = JamGraph()
    g.add("series_range", {"count": 4, "start": 0.0, "end": 300.0}, nid="serie")
    g.add(verbo, {}, nid="curva")
    g.connect("serie", "curva", "x")
    g.connect("serie", "curva", "y")
    g.connect("serie", "curva", "z")
    return g


reportes = {}
for verbo in ("curve_polyline", "curve_interpolate"):
    g = por_los_puntos(verbo)
    compilado_c = json.loads(api.compile_graph_json(g.to_json()))
    exigir(compilado_c.get("ok"), f"Compile de {verbo}: {compilado_c}")
    corrida_c = json.loads(api.run_graph_json(g.to_json()))
    exigir(corrida_c.get("ok"), f"Run de {verbo}: {corrida_c}")
    reportes[verbo] = corrida_c.get("report", "")
    log(f"  {verbo}: {reportes[verbo].splitlines()[1][:96]}")

exigir("INTERPOLATE" in reportes["curve_interpolate"],
       "el verbo nuevo se identifica en el reporte")
exigir("de control" in reportes["curve_interpolate"],
       "y dice cuántos puntos de control tenía, que es lo que lo distingue de la polilínea")

# Y encadenado con lo del peldaño 3: una curva suave se puede barrer igual que una recta.
suave = por_los_puntos("curve_interpolate")
suave.add("mesh_ribbon", {"width": 80.0}, nid="cinta")
suave.connect("curva", "cinta", "in")
corrida_suave = json.loads(api.run_graph_json(suave.to_json()))
exigir(corrida_suave.get("ok"), f"barrer una curva interpolada: {corrida_suave}")

log("=" * 78)
log("JAM_LINEA_58 TODO VERDE" if not FALLAS else f"JAM_LINEA_58 ROJO — {len(FALLAS)}")
