"""Tender una superficie entre curvas, por el camino REAL del Graph — y juzgada por el oráculo.

Peldaño 6 de la escalera de Grasshopper Basics. Los tests puros fijan el winding contra el de la
cinta, pero eso compara dos buffers nuestros entre sí: si los DOS estuvieran dados vuelta, el test
seguiría verde. Acá la malla se construye de verdad y se le pregunta a `malla.cara_visible` —la
misma medida que en su primer uso encontró que `mesh_ribbon` entregaba el winding invertido con 790
tests en verde—.

La cadena es la de la escalera entera, de punta a punta: Unitario X → Línea por dirección → dos
curvas → Tender entre curvas. Cada peldaño usando el anterior, que es de lo que se trataba.
"""
import json

import unreal

from jam import api, curve, loft_core, mesh, oracle_malla_facts
from jam.graph import JamGraph


def log(m):
    unreal.log(f"[LOFT] {m}")


FALLAS = []


def exigir(condicion, descripcion):
    log(("  OK   " if condicion else "  FALLA") + f" · {descripcion}")
    if not condicion:
        FALLAS.append(descripcion)


log("=" * 78)
spec = {item["verbo"]: item for item in json.loads(api.spec_all())["tools"]}
exigir("mesh_loft" in spec, "el spec publica mesh_loft")
exigir(spec.get("mesh_loft", {}).get("label") == "Tender entre curvas", "se llama «Tender entre curvas»")

log("-" * 78)
log("La cadena entera de la escalera: vector → línea → dos curvas → superficie.")
g = JamGraph()
g.add("vector_unit_x", {"largo": 1}, nid="eje")
g.add("curve_line_sdl", {"origen": "0,180,0", "largo": 500}, nid="curva_a")
g.add("curve_line_sdl", {"origen": "0,-180,0", "largo": 500}, nid="curva_b")
g.add("mesh_loft", {"samples": 8}, nid="superficie")
g.connect("eje", "curva_a", "direccion")
g.connect("eje", "curva_b", "direccion")
g.connect("curva_a", "superficie", "in")
g.connect("curva_b", "superficie", "in")

compilado = json.loads(api.compile_graph_json(g.to_json()))
exigir(compilado.get("ok"), f"Compile de la cadena: {compilado}")
corrida = json.loads(api.run_graph_json(g.to_json()))
exigir(corrida.get("ok"), f"Run de la cadena: {corrida}")
reporte = corrida.get("report", "")
for linea in reporte.splitlines():
    if "superficie" in linea or "LOFT" in linea:
        log(f"  {linea[:110]}")
exigir("LOFT" in reporte, "la superficie se construyó")

log("-" * 78)
log("Y ahora el ORÁCULO sobre la malla de verdad, que es lo que los tests puros no pueden ver:")

# La misma superficie, construida por el adaptador real para poder medirla.
curva_a = curve.line((0.0, 180.0, 0.0), (500.0, 180.0, 0.0))["curve"]
curva_b = curve.line((0.0, -180.0, 0.0), (500.0, -180.0, 0.0))["curve"]
built = loft_core.loft_buffers([curva_a.points, curva_b.points], samples=8)
hechos = oracle_malla_facts.hechos(built["vertices"], built["triangles"], built["normals"])
caras = hechos["cara_malla"]
malas = [c for c in caras if float(c["acuerdo"]) <= 0.0]
log(f"  {len(caras)} caras · acuerdo mínimo {min(float(c['acuerdo']) for c in caras):+.3f}")
exigir(not malas, f"ninguna cara del loft está dada vuelta ({len(malas)} en rojo)")

# Y el control que hace la medida informativa: la MISMA superficie con las curvas al revés tiene
# que salir coherente igual —el loft se endereza solo— pero mirando para el otro lado.
built_vuelta = loft_core.loft_buffers([curva_b.points, curva_a.points], samples=8)
hechos_vuelta = oracle_malla_facts.hechos(
    built_vuelta["vertices"], built_vuelta["triangles"], built_vuelta["normals"])
malas_vuelta = [c for c in hechos_vuelta["cara_malla"] if float(c["acuerdo"]) <= 0.0]
exigir(not malas_vuelta,
       "invertir el orden de las curvas da vuelta la superficie pero NO la vuelve incoherente")

nz = [oracle_malla_facts.normal_de_cara(built["vertices"], t)[2] for t in built["triangles"]]
nz_vuelta = [oracle_malla_facts.normal_de_cara(built_vuelta["vertices"], t)[2]
             for t in built_vuelta["triangles"]]
exigir(all(z > 0 for z in nz) and all(z < 0 for z in nz_vuelta),
       "y el orden de los cables es lo que decide de qué lado mira")

log("-" * 78)
log("La curva recorrida al revés se endereza sola y lo dice:")
al_reves = loft_core.loft_buffers(
    [curva_a.points, tuple(reversed(curva_b.points))], samples=8)
exigir(al_reves["invertidas"] == 1, f"se avisa que hubo 1 curva dada vuelta ({al_reves})")
hechos_reves = oracle_malla_facts.hechos(
    al_reves["vertices"], al_reves["triangles"], al_reves["normals"])
exigir(not [c for c in hechos_reves["cara_malla"] if float(c["acuerdo"]) <= 0.0],
       "y la superficie enderezada sale coherente (sin enderezar saldría cruzada en X)")

log("-" * 78)
log("Y la escalera ENTERA, con el último peldaño: un solo riel movido hace el segundo.")
completa = JamGraph()
completa.add("vector_unit_x", {"largo": 1}, nid="eje")
completa.add("curve_line_sdl", {"origen": "0,0,0", "largo": 500}, nid="riel")
completa.add("vector_unit_z", {"largo": 200}, nid="arriba")
completa.add("curve_move", {}, nid="riel2")
completa.add("mesh_loft", {"samples": 8}, nid="superficie")
completa.connect("eje", "riel", "direccion")
completa.connect("riel", "riel2", "in")
completa.connect("arriba", "riel2", "desplazamiento")
completa.connect("riel", "superficie", "in")
completa.connect("riel2", "superficie", "in")
compilado_c = json.loads(api.compile_graph_json(completa.to_json()))
exigir(compilado_c.get("ok"), f"Compile de la escalera entera: {compilado_c}")
corrida_c = json.loads(api.run_graph_json(completa.to_json()))
exigir(corrida_c.get("ok"), f"Run de la escalera entera: {corrida_c}")
for linea in corrida_c.get("report", "").splitlines():
    if "riel2" in linea or "superficie" in linea:
        log(f"  {linea[:110]}")
exigir("MOVE S" in corrida_c.get("report", ""), "el riel se movió con un vector cableado")
exigir("LOFT M" in corrida_c.get("report", ""),
       "y la superficie se tendió entre el riel y su copia movida")

log("=" * 78)
log("JAM_LOFT_58 TODO VERDE" if not FALLAS else f"JAM_LOFT_58 ROJO — {len(FALLAS)}")
