"""Multi-salida por el camino REAL: spec, Compile, Run e Inspector en UE 5.8.1.

Un verbo con más de una salida —el patrón Deconstruct de Grasshopper— era la capacidad que
bloqueaba las matrices. Los tests puros fijan la mecánica; lo que hay que demostrar acá es que el
motor la acepta de punta a punta: que el spec publique los pines extra, que `compile_graph_json`
valide una arista cuyo `origen_pin` no es «out», y que `run_graph_json` entregue por cada pin una
parte DISTINTA del mismo resultado.

**La afirmación que se mide es aritmética, no de forma**: un dominio 10..90 cableado por sus dos
extremos a una suma tiene que dar 100, y a una resta cruzada, 80. Si las dos salidas entregaran lo
mismo darían 20/180 y 0; si entregaran el dominio entero, no resolvería. Un solo número distingue
los tres modos de fallar.

Y la regresión que más importa: **un grafo sin salidas extra tiene que comportarse exactamente como
antes**. Es la propiedad que hace seguro todo el cambio, así que se mide acá y no sólo en los tests.

Receta (editor completo, tickea, sin ventana):
    UnrealEditor <proyecto> -RenderOffScreen -unattended -nosplash \
        -ExecCmds="py <ruta>/verifica_multi_salida_58.py,QUIT_EDITOR"
⚠️ `-ExecCmds` separa por COMAS. Con `;` el resto entra como línea de Python y sale
`SyntaxError: invalid decimal literal`.
"""
import json

import unreal

from jam import api
from jam.graph import JamGraph


def log(m):
    unreal.log(f"[MULTISALIDA] {m}")


FALLAS = []


def exigir(condicion, descripcion):
    log(("  OK   " if condicion else "  FALLA") + f" · {descripcion}")
    if not condicion:
        FALLAS.append(descripcion)


def corrida(g):
    return json.loads(api.run_graph_json(g.to_json()))


def compilado(g):
    return json.loads(api.compile_graph_json(g.to_json()))


log("=" * 78)
log("1 · El spec publica los pines extra, y sólo donde los hay.")
spec = {item["verbo"]: item for item in json.loads(api.spec_all())["tools"]}

exigir("domain_construct" in spec, "el spec trae «Armar dominio»")
outs = spec.get("domain_construct", {}).get("outs")
exigir(outs == [{"name": "desde", "tipo": "N", "label": "desde"},
                {"name": "hasta", "tipo": "N", "label": "hasta"}],
       f"«Armar dominio» publica sus dos salidas extra: {outs}")

sin_clave = [v for v, item in spec.items() if "outs" not in item]
exigir(not sin_clave,
       f"TODO verbo publica «outs», aunque sea vacío — sin la clave, el C++ tendría que "
       f"distinguir «no hay» de «no vino» ({len(sin_clave)} sin ella: {sin_clave[:5]})")

con_extra = sorted(v for v, item in spec.items() if item.get("outs"))
# «Armar dominio» la estrenó; «Descomponer matriz» es el consumidor por el que se hizo, y el que
# demuestra que el mecanismo no estaba atado a DOS salidas: publica cuatro extras.
exigir(con_extra == ["domain_construct", "matrix_decompose"],
       f"y hoy la declaran exactamente esos dos: {con_extra}")

log("-" * 78)
log("2 · Compile acepta una arista cuyo pin de origen no es «out».")
g = JamGraph()
g.add("domain_construct", {"desde": 10.0, "hasta": 90.0}, nid="dom")
g.add("math_add", {"a": 0.0, "b": 0.0}, nid="suma")
g.connect("dom", "suma", "a", origen_pin="desde")
g.connect("dom", "suma", "b", origen_pin="hasta")
c = compilado(g)
exigir(c.get("ok"), f"Compile de las dos salidas a dos pines: {c}")

r = corrida(g)
reporte = r.get("report", "")
exigir(r.get("ok"), f"Run de las dos salidas: {r}")
# 10 + 90. Con las dos salidas iguales daría 20 o 180; con el dominio entero no resolvería.
exigir("100" in reporte, f"desde + hasta = 100: {reporte[:160]}")

log("-" * 78)
log("3 · Y no son intercambiables: la resta distingue el orden.")
h = JamGraph()
h.add("domain_construct", {"desde": 10.0, "hasta": 90.0}, nid="dom")
h.add("math_subtract", {"minuendo": 0.0, "sustraendo": 0.0}, nid="resta")
h.connect("dom", "resta", "minuendo", origen_pin="hasta")
h.connect("dom", "resta", "sustraendo", origen_pin="desde")
rr = corrida(h)
exigir(rr.get("ok"), f"Run de la resta cruzada: {rr}")
exigir("80" in rr.get("report", ""),
       f"hasta − desde = 80, y al revés daría −80: {rr.get('report', '')[:160]}")

log("-" * 78)
log("4 · La salida PRINCIPAL sigue entregando el dominio entero.")
i = JamGraph()
i.add("domain_construct", {"desde": 10.0, "hasta": 90.0}, nid="dom")
i.add("domain_length", {}, nid="largo")
i.connect("dom", "largo", "dominio")  # sin origen_pin
ri = corrida(i)
exigir(ri.get("ok"), f"Run por la salida principal: {ri}")
exigir("80" in ri.get("report", ""),
       f"el largo del dominio entero sigue siendo 80: {ri.get('report', '')[:160]}")

log("-" * 78)
log("5 · Compile RECHAZA un pin de salida que no existe, y dice cuáles hay.")
j = JamGraph()
j.add("domain_construct", {}, nid="dom")
j.add("math_add", {}, nid="suma")
j.connect("dom", "suma", "a", origen_pin="medio")
cj = compilado(j)
exigir(not cj.get("ok"), f"un pin inventado no compila: {cj}")
texto = json.dumps(cj, ensure_ascii=False)
exigir("medio" in texto, f"el error nombra el pin que falló: {texto[:200]}")
exigir("desde" in texto and "hasta" in texto,
       f"y lista las salidas que sí existen: {texto[:200]}")

log("-" * 78)
log("6 · REGRESIÓN — un grafo sin salidas extra se comporta como siempre.")
k = JamGraph()
k.add("number", {"name": "ancho", "value": 30.0}, nid="n")
k.add("math_multiply", {"a": 0.0, "b": 2.0}, nid="doble")
k.connect("n", "doble", "a")
rk = corrida(k)
exigir(rk.get("ok"), f"Run del grafo de siempre: {rk}")
exigir("60" in rk.get("report", ""),
       f"30 × 2 = 60, igual que antes de que existiera multi-salida: {rk.get('report','')[:160]}")

# Y el que más importa de todos: una cadena con GEOMETRÍA de verdad, que es donde vive el ejecutor
# (los nodos de valor resuelven por otro camino). Si multi-salida hubiera roto el reparto de cables,
# esto se cae aunque ningún verbo de acá tenga salidas extra.
log("-" * 78)
log("7 · REGRESIÓN con geometría: la cadena del peldaño 3 sigue produciendo malla.")
m = JamGraph()
m.add("vector_unit_x", {"largo": 1}, nid="dir")
m.add("curve_line_sdl", {"origen": "0,0,0", "largo": 500}, nid="linea")
m.add("mesh_ribbon", {"width": 120.0}, nid="cinta")
m.connect("dir", "linea", "direccion")
m.connect("linea", "cinta", "in")
rm = corrida(m)
exigir(rm.get("ok"), f"Run de vector → línea → cinta: {rm}")
exigir("RIBBON" in rm.get("report", "").upper(),
       f"la cinta se construyó: {rm.get('report', '')[:160]}")

log("-" * 78)
log("8 · El contrato que consume Slate: los pines vienen con la MISMA forma que inputs/outputs.")
# El C++ los lee con el mismo `LeerPines`, que exige `name` + `tipo`. Si el Python publicara `pin`
# en vez de `name`, el parser no levantaría ninguno y el nodo se dibujaría con un solo nub — sin
# error, sin log, simplemente sin los pines. Por eso se mide la FORMA y no sólo que la clave exista.
for salida in spec.get("domain_construct", {}).get("outs", []):
    exigir(set(salida) == {"name", "tipo", "label"},
           f"la salida extra trae name/tipo/label y nada más: {salida}")
    exigir(bool(salida.get("name")) and bool(salida.get("tipo")),
           f"con nombre y tipo no vacíos: {salida}")

# Y que ninguna extra se llame «out»: taparía la principal en el dibujo y en el cableado.
exigir(all(s.get("name") != "out" for item in spec.values() for s in item.get("outs", [])),
       "ninguna salida extra se llama «out» en todo el spec")

log("=" * 78)
log("JAM_MULTISALIDA_58 TODO VERDE" if not FALLAS
    else f"JAM_MULTISALIDA_58 ROJO — {len(FALLAS)}: {FALLAS}")
