"""Matrices 4×4 por el camino REAL: spec, Compile y Run en UE 5.8.1.

Los tests puros fijan la aritmética. Lo que hay que demostrar acá es que el motor la acepta de punta
a punta: que el spec publique el tipo `MX` y las cuatro salidas extra de «Descomponer matriz», que
`compile_graph_json` valide aristas cuyo `origen_pin` no es «out», y que `run_graph_json` entregue
por cada pin una parte DISTINTA de la misma descomposición.

**Lo que se mide es aritmético, no de forma.** Una cadena traslación(10,20,30) × rotación(90° sobre
Z) × escala(2,3,4), descompuesta, tiene que devolver esos mismos números. Si las cinco salidas
entregaran lo mismo, o si alguna entregara la tupla entera, ninguno de los largos daría lo que da.

Y la que más importa, porque salía VERDE antes de este turno: **una salida extra cableada al
parámetro de una TOOL tiene que llegar rebanada**. `domain_construct.desde` → `pts_line.count` le
entregaba al verbo el dominio ENTERO, `(10.0, 90.0)` en vez de `10.0`, con el Compile en verde.
Había cuatro rutas que reparten cables y sólo dos rebanaban.

Receta (editor completo, tickea, sin ventana):
    UnrealEditor <proyecto> -RenderOffScreen -unattended -nosplash \
        -ExecCmds="py <ruta>/verifica_matrices_58.py,QUIT_EDITOR"
⚠️ `-ExecCmds` separa por COMAS. Con `;` el resto entra como línea de Python y sale
`SyntaxError: invalid decimal literal`.
"""
import json
import math
import re

import unreal

from jam import api
from jam.graph import JamGraph


def log(m):
    unreal.log(f"[MATRICES] {m}")


FALLAS = []


def exigir(condicion, descripcion):
    log(("  OK   " if condicion else "  FALLA") + f" · {descripcion}")
    if not condicion:
        FALLAS.append(descripcion)


def corrida(g):
    return json.loads(api.run_graph_json(g.to_json()))


def corrio_limpio(r) -> bool:
    """El Run no dejó ningún nodo en error.

    NO se pregunta por `ok`: un grafo de puras ops de Flow sale por `ejecutar_flow_json`, que
    devuelve el envelope **sin esa clave**, así que `r.get("ok")` da `None` y un Run perfecto se
    lee como fallado. El veredicto por nodo está en las dos rutas.
    """
    return not any(n.get("estado") == "error" for n in r.get("nodes", {}).values())


def compilado(g):
    return json.loads(api.compile_graph_json(g.to_json()))


VERBOS = ["matrix_identity", "matrix_translation", "matrix_rotation", "matrix_scale_matrix",
          "matrix_multiply", "matrix_inverse", "matrix_transpose", "matrix_determinant",
          "matrix_transform_point", "matrix_transform_direction", "matrix_decompose"]

log("=" * 78)
log("1 · El spec publica los once verbos, con su tipo y su grupo.")
spec = {item["verbo"]: item for item in json.loads(api.spec_all())["tools"]}

faltan = [v for v in VERBOS if v not in spec]
exigir(not faltan, f"los once están en el spec (faltan: {faltan})")

producen_mx = sorted(v for v in VERBOS if spec.get(v, {}).get("out_name") == "MX")
exigir(producen_mx == sorted(["matrix_identity", "matrix_translation", "matrix_rotation",
                              "matrix_scale_matrix", "matrix_multiply", "matrix_inverse",
                              "matrix_transpose"]),
       f"siete producen una matriz y los otros cuatro no: {producen_mx}")

grupos = {spec.get(v, {}).get("grupo") for v in VERBOS}
exigir(grupos == {"Matriz"},
       f"los once caen en el grupo «Matriz» del ribbon (grupos vistos: {grupos})")

sin_doc = [v for v in VERBOS if not spec.get(v, {}).get("doc")]
exigir(not sin_doc, f"ninguno queda sin doc: sin ella el tooltip es lo único que hay y va vacío "
                    f"({sin_doc})")

log("-" * 78)
log("2 · «Descomponer matriz» publica CUATRO salidas extra, con la forma que lee Slate.")
outs = spec.get("matrix_decompose", {}).get("outs", [])
exigir([o.get("name") for o in outs] == ["escala", "eje_x", "eje_y", "eje_z"],
       f"los cuatro pines extra, en orden: {[o.get('name') for o in outs]}")
exigir(all(set(o) == {"name", "tipo", "label"} and o["tipo"] == "V" for o in outs),
       f"cada uno con name/tipo/label y tipo vector: {outs}")
# Multi-salida se estrenó con DOS. Cuatro es lo que demuestra que el mecanismo no estaba atado
# a ese número: el C++ arma una fila por pin leyendo el spec, no una lista fija.
exigir(len(outs) == 4, f"y son cuatro, no dos: {len(outs)}")

log("-" * 78)
log("3 · Compile: una arista desde un pin extra es válida, y una desde un pin inventado NO.")
g = JamGraph()
g.add("matrix_translation", {"traslación": "10,20,30"}, nid="t", x=0, y=0)
g.add("matrix_decompose", {}, nid="d", x=200, y=0)
g.add("vector_length", {}, nid="l", x=400, y=0)
g.connect("t", "d", "matriz")
g.connect("d", "l", "vector", "eje_z")
c = compilado(g)
exigir(c.get("ok"), f"Compile acepta el cable desde «eje_z»: {c.get('report', c)}")

malo = JamGraph.from_json(g.to_json())
malo.edges = [e for e in malo.edges if e[1] != "eje_z"]
malo.connect("d", "l", "vector", "eje_w")
cm = compilado(malo)
exigir(not cm.get("ok"), "Compile RECHAZA un pin de salida que no existe")
exigir("eje_w" in json.dumps(cm), f"y dice cuál: {cm.get('report', cm)}")

log("-" * 78)
log("4 · Run: la descomposición devuelve los números que se le metieron.")
# traslación(10,20,30) × rotación(90° sobre Z) × escala(2,3,4).
cadena = JamGraph()
cadena.add("matrix_translation", {"traslación": "10,20,30"}, nid="tr", x=0, y=0)
cadena.add("matrix_rotation", {"eje": "0,0,1", "ángulo": 90.0}, nid="rot", x=0, y=120)
cadena.add("matrix_scale_matrix", {"escala": "2,3,4"}, nid="esc", x=0, y=240)
cadena.add("matrix_multiply", {}, nid="rs", x=200, y=180)
cadena.add("matrix_multiply", {}, nid="todo", x=400, y=90)
cadena.add("matrix_decompose", {}, nid="des", x=600, y=90)
cadena.connect("rot", "rs", "a")
cadena.connect("esc", "rs", "b")
cadena.connect("tr", "todo", "a")
cadena.connect("rs", "todo", "b")
cadena.connect("todo", "des", "matriz")
# Un largo por pin: cinco números que sólo salen si cada pin entrega SU parte.
largos = {"out": math.sqrt(10 ** 2 + 20 ** 2 + 30 ** 2),   # la traslación
          "escala": math.sqrt(2 ** 2 + 3 ** 2 + 4 ** 2),
          "eje_x": 1.0, "eje_y": 1.0, "eje_z": 1.0}         # los ejes son unitarios
for i, pin in enumerate(largos):
    cadena.add("vector_length", {}, nid=f"L{pin}", x=800, y=i * 90)
    cadena.connect("des", f"L{pin}", "vector", pin)

r = corrida(cadena)
exigir(corrio_limpio(r), f"Run de la cadena entera: {r.get('report', r)}")
reporte = r.get("report", "")
for pin, esperado in largos.items():
    # El nodo de valor se imprime como «nombre = valor» en el reporte del Run.
    marca = f"L{pin} = "
    trozo = reporte.split(marca, 1)[1].split("\n", 1)[0].strip() if marca in reporte else ""
    try:
        medido = float(trozo)
    except ValueError:
        medido = float("nan")
    # La tolerancia es la del DISPLAY, no la de la cuenta: el nodo escribe con `.6g`, así que
    # 37.416574 se dibuja «37.4166». Sigue discriminando de sobra — cualquier pin que entregara la
    # parte de otro daría un número distinto en el primer decimal, no en el cuarto.
    exigir(abs(medido - esperado) < 1e-3,
           f"el pin «{pin}» entrega su parte: largo {medido} (esperado {esperado:.6f})")

log("-" * 78)
log("5 · El pin principal entrega la TRASLACIÓN, no la tupla de cinco.")
# Primer verbo con `corte_principal`: su valor guardado son los cinco vectores y ningún pin lo
# muestra tal cual. Sin el corte, `out` diría «vector» y entregaría cinco — y `vector_length`
# fallaría con «un vector son tres números; llegaron 5».
exigir("llegaron 5" not in reporte,
       "ningún pin recibió la tupla entera en vez de su rebanada")

log("-" * 78)
log("6 · LA REGRESIÓN: una salida extra cableada al parámetro de una TOOL llega rebanada.")
# Salía verde antes de este turno. `domain_construct.desde` → `pts_line.count` le entregaba al
# verbo el dominio ENTERO. Esta es la ruta que no rebanaba, y no la ejercía ningún test.
t = JamGraph()
t.add("domain_construct", {"desde": 3, "hasta": 90}, nid="dom", x=0, y=0)
t.add("pts_line", {"ax": 0.0, "ay": 0.0, "bx": 500.0, "by": 0.0}, nid="ln", x=200, y=0)
t.connect("dom", "ln", "count", "desde")
ct = compilado(t)
exigir(ct.get("ok"), f"Compile del cable a un param de tool: {ct.get('report', ct)}")
rt = corrida(t)
exigir(corrio_limpio(rt), f"Run: {rt.get('report', rt)}")
# `desde` vale 3, así que la línea tiene que producir TRES puntos. Y con el bug NO fallaba: la
# tupla se stringifica a «(3.0, 90.0)», `dsl.coaccionar` no la reconoce, **descarta el parámetro en
# silencio** y la línea corre con su default de 10. Por eso el número medido es el veredicto: un
# «ok» acá no distingue el arreglo del defecto.
texto_linea = rt.get("nodes", {}).get("ln", {}).get("texto", "")
log(f"       texto del nodo de la línea: «{texto_linea}»")
exigir(re.search(r"\b3\b", texto_linea) and not re.search(r"\b10\b", texto_linea),
       f"la línea salió con 3 puntos y no con el default de 10: «{texto_linea}»")

log("-" * 78)
log("7 · REGRESIÓN: un grafo SIN salidas extra se comporta exactamente como antes.")
# Es la propiedad que hace seguro todo esto, así que se mide acá y no sólo en los tests puros.
base = JamGraph()
base.add("number", {"name": "n", "value": 7}, nid="n", x=0, y=0)
base.add("pts_line", {"ax": 0.0, "ay": 0.0, "bx": 500.0, "by": 0.0}, nid="ln", x=200, y=0)
base.connect("n", "ln", "count")
rb = corrida(base)
exigir(corrio_limpio(rb), f"Run del grafo de siempre: {rb.get('report', rb)}")

log("-" * 78)
log("8 · Una matriz singular y una que espeja se NIEGAN, con el motivo adentro.")
for params, palabra, quien in (
        ({"escala": "1,1,0"}, "singular", "matrix_inverse"),
        ({"escala": "-1,1,1"}, "espeja", "matrix_decompose")):
    x = JamGraph()
    x.add("matrix_scale_matrix", params, nid="s", x=0, y=0)
    x.add(quien, {}, nid="q", x=200, y=0)
    x.connect("s", "q", "matriz")
    cx = compilado(x)
    exigir(not cx.get("ok"), f"{quien} con {params} no sale en verde")
    exigir(palabra in json.dumps(cx, ensure_ascii=False),
           f"y el diagnóstico dice «{palabra}»: {json.dumps(cx, ensure_ascii=False)[:200]}")

log("=" * 78)
log("JAM_MATRICES_58 TODO VERDE" if not FALLAS
    else f"JAM_MATRICES_58 ROJO — {len(FALLAS)}: {FALLAS}")
