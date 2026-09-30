# Revisión de Codex (2026-09-29)

**No encontré llamadas obsoletas que rompan estas cuatro sondas.** Sus archivos no cambiaron desde `d207caf`, y las APIs públicas que usan conservan sus firmas. Eso demuestra compatibilidad estática; **no confirma que hoy terminen verdes dentro de Unreal**.

No edité archivos, hice commits ni abrí motores. Comprobé firmas, registros, aritmética y expansión de funciones con `sys.modules["unreal"] = None` y bytecode deshabilitado.

### Resultado por sonda

| Sonda | Compatibilidad actual | Cifras y significado del verde |
|---|---|---|
| [`verifica_matrices_58.py`](/tmp/claude-1000/-home-workstation-Dev-jam/81582137-fff0-48ba-88ff-94b33db5dd67/scratchpad/wt/ev-codex/tools/experiments/verifica_matrices_58.py:46) | `api.spec_all`, `compile_graph_json`, `run_graph_json` y los métodos de `JamGraph` siguen disponibles con las mismas firmas. | Siguen siendo **11 verbos, 7 productores de `MX` y 4 salidas extra**. Conserva cobertura aritmética, pero no verifica una matriz aplicada por Unreal ni todas las rutas de ejecución. |
| [`verifica_multi_salida_58.py`](/tmp/claude-1000/-home-workstation-Dev-jam/81582137-fff0-48ba-88ff-94b33db5dd67/scratchpad/wt/ev-codex/tools/experiments/verifica_multi_salida_58.py:44) | Las APIs, pines y verbos usados siguen vigentes. `curve_line_sdl` ahora llega a `comun.py` mediante el adaptador; la sonda lo invoca por nombre de verbo, correctamente. | Todavía hay **dos verbos con `outs`**: `domain_construct` y `matrix_decompose`. Sigue ejercitando Run de geometría, pero sus comparaciones textuales permiten falsos verdes. |
| [`verifica_funcion_graph.py`](/tmp/claude-1000/-home-workstation-Dev-jam/81582137-fff0-48ba-88ff-94b33db5dd67/scratchpad/wt/ev-codex/tools/experiments/verifica_funcion_graph.py:24) | `collapse_function`, `function_manage`, `preset.borrar_funcion` y los campos `graph/tool/verbo/label/inputs/outputs` conservan el contrato usado. | Siguen siendo **dos instancias, cuatro nodos internos expandidos y seis nodos totales**, con firma `in:M → salida:M`. El verde sigue significando ABM y Compile; **nunca ejecuta el cilindro ni la función**. |
| [`verifica_ejemplos.py`](/tmp/claude-1000/-home-workstation-Dev-jam/81582137-fff0-48ba-88ff-94b33db5dd67/scratchpad/wt/ev-codex/tools/experiments/verifica_ejemplos.py:45) | La lectura de `examples.json` y `api.compile_graph_json` siguen siendo válidas. | **19 sigue siendo correcto para «Aprender»**, cuyo Slate todavía lee ese catálogo. El catálogo del editor web tiene **22**: agrega `tools/vitrina/base_comun.jam`, `colocar.jam` y `tubo_sobre_curva.jam`. Un verde de esta sonda sigue cubriendo únicamente los 19 originales y únicamente Compile. |

### Qué cambió sin romper estas llamadas

En `Content/Python/jam/graph.py:704`, la firma actual es:

```python
ejecutar_detalle(g, plan=None, almacen=None, adaptador=None)
```

El parámetro nuevo es opcional: sin él selecciona `jam.tools`. `panel.py` sigue llamándolo correctamente con `(g, plan)`.

En `Content/Python/jam/tools.py`, `REGISTRO` sigue siendo el diccionario importado de `registro.py`; el adaptador le incorpora las implementaciones. El ejecutor llama a `adaptador.implementacion(verbo)`. **Ninguna de estas cuatro sondas necesita reemplazar una llamada directa a `tools.t_*`: no las tiene.**

La mudanza sí cambia qué implementación debería quedar verificada. En particular, Compile de `mesh_cylinder` no ejecuta su nuevo generador común ni la conversión a `DynamicMesh`.

### Agujeros concretos del veredicto

- **Matrices, línea 50:** `corrio_limpio({"nodes": {}})` devuelve `True`; también acepta un resultado compuesto sólo por nodos `cancelado`. Lo comprobé ejecutando únicamente ese predicado.
- **Matrices, sección 4:** medir largos no distingue orientación, signo ni intercambio de ejes. Los tres ejes esperados tienen largo `1`; una rotación omitida puede pasar. La descripción «cada pin entrega su parte distinta» promete más que lo medido.
- **Matrices, sección 6:** `domain_construct → pts_line` cumple `Flow.solo_flow()`. Por `api.py:424` toma `panel.ejecutar_flow_json`, **no** `graph.ejecutar_detalle` ni `tools.implementacion`. La sección 7 también toma Flow y no comprueba que salgan siete puntos.
- **Multi-salida:** `"80" in reporte` acepta `resta = -80`. Las búsquedas de `"100"` y `"60"` tampoco están ligadas al valor exacto del nodo.
- **Multi-salida:** sus `r.get("ok")` **no están rotos actualmente**: los grafos de valores reciben `ok` por la rama especial de `panel.py:1050`; la cadena geométrica recibe el envelope de Graph. No corresponde aplicar aquí indiscriminadamente el diagnóstico de Flow sin `ok`.
- **Multi-salida:** aunque el encabezado promete Inspector, nunca llama a `api.inspect_json`. Buscar `RIBBON` tampoco mide la malla obtenida.
- **Ejemplos:** un catálogo vacío termina en `TODO VERDE`, y los tres `.jam` nuevos no se recorren.

Son límites de cobertura y discriminación; varios ya existían en la certificación vieja.

### Diff propuesto, sin aplicar

Mantendría las APIs públicas y reforzaría las observaciones. Estos fragmentos agregan comprobaciones; no reemplazan la futura corrida con motor.

```diff
--- a/tools/experiments/verifica_matrices_58.py
+++ b/tools/experiments/verifica_matrices_58.py
@@
-from jam import api
+from jam import api, flow, graph
@@
 def corrida(g):
-    return json.loads(api.run_graph_json(g.to_json()))
+    r = json.loads(api.run_graph_json(g.to_json()))
+    exigir(set(r.get("nodes", {})) == set(g.nodes),
+           "Run informa exactamente los nodos pedidos")
+    return r
@@
-    return not any(n.get("estado") == "error" for n in r.get("nodes", {}).values())
+    nodos = r.get("nodes", {})
+    return (bool(nodos) and r.get("ok") is not False
+            and all(n.get("estado") == "ok" for n in nodos.values()))
@@
-r = corrida(cadena)
+# Medir componentes distingue orientación, signo e intercambio de pines.
+componentes = {
+    "out": (10, 20, 30), "escala": (2, 3, 4),
+    "eje_x": (0, 1, 0), "eje_y": (-1, 0, 0), "eje_z": (0, 0, 1),
+}
+for pin in componentes:
+    for eje in "xyz":
+        nid = f"C_{pin}_{eje}"
+        cadena.add(f"vector_{eje}", {}, nid=nid)
+        cadena.connect("des", nid, "vector", pin)
+
+r = corrida(cadena)
 exigir(corrio_limpio(r), f"Run de la cadena entera: {r.get('report', r)}")
+medidos = graph.ultima_corrida()
+for pin, vector in componentes.items():
+    for eje, esperado in zip("xyz", vector):
+        medido = medidos.get(f"C_{pin}_{eje}")
+        exigir(isinstance(medido, (int, float))
+               and math.isclose(medido, esperado, abs_tol=1e-6),
+               f"{pin}.{eje}: {medido}, esperado {esperado}")
@@
 exigir(re.search(r"\b3\b", texto_linea) and not re.search(r"\b10\b", texto_linea),
        f"la línea salió con 3 puntos y no con el default de 10: «{texto_linea}»")
+inspeccion = json.loads(api.inspect_json("ln"))
+exigir(inspeccion.get("ok") and inspeccion.get("total") == 3,
+       f"Inspector mide tres puntos por Flow: {inspeccion}")
+
+# Repetir el mismo cable por Graph y el adaptador de herramientas.
+tg = JamGraph.from_json(t.to_json())
+tg.add("points_to_frames", {}, nid="frames")
+tg.connect("ln", "frames")
+exigir(not flow.Flow.from_json(tg.to_json()).solo_flow(),
+       "esta variante entra por el ejecutor Graph")
+exigir(compilado(tg).get("ok"), "Compile de la variante Graph")
+rg = corrida(tg)
+exigir(corrio_limpio(rg), f"Run por Graph: {rg}")
+inspeccion = json.loads(api.inspect_json("ln"))
+exigir(inspeccion.get("ok") and inspeccion.get("total") == 3,
+       f"Inspector mide tres puntos por Graph: {inspeccion}")
@@
 rb = corrida(base)
 exigir(corrio_limpio(rb), f"Run del grafo de siempre: {rb.get('report', rb)}")
+inspeccion = json.loads(api.inspect_json("ln"))
+exigir(inspeccion.get("ok") and inspeccion.get("total") == 7,
+       f"el cable principal entrega siete puntos: {inspeccion}")
```

Comprobé en Python puro las quince componentes propuestas y que agregar `points_to_frames` selecciona Graph y compila `count=3`. Falta verificar ese recorrido con el adaptador real.

```diff
--- a/tools/experiments/verifica_multi_salida_58.py
+++ b/tools/experiments/verifica_multi_salida_58.py
@@
 def corrida(g):
-    return json.loads(api.run_graph_json(g.to_json()))
+    r = json.loads(api.run_graph_json(g.to_json()))
+    nodos = r.get("nodes", {})
+    exigir(bool(nodos) and set(nodos) == set(g.nodes)
+           and r.get("ok") is not False
+           and all(n.get("estado") == "ok" for n in nodos.values()),
+           f"todos los nodos pedidos terminaron correctamente: {r}")
+    return r
+
+
+def numero(r, nid):
+    try:
+        return float(r["nodes"][nid]["texto"].rsplit(" = ", 1)[1])
+    except (KeyError, IndexError, ValueError, TypeError):
+        return float("nan")
@@
-exigir("100" in reporte, f"desde + hasta = 100: {reporte[:160]}")
+exigir(numero(r, "suma") == 100, f"desde + hasta = 100: {reporte[:160]}")
@@
-exigir("80" in rr.get("report", ""),
+exigir(numero(rr, "resta") == 80,
@@
-exigir("80" in ri.get("report", ""),
+exigir(numero(ri, "largo") == 80,
@@
-exigir("60" in rk.get("report", ""),
+exigir(numero(rk, "doble") == 60,
@@
 exigir("RIBBON" in rm.get("report", "").upper(),
        f"la cinta se construyó: {rm.get('report', '')[:160]}")
+inspeccion = json.loads(api.inspect_json("cinta"))
+exigir(inspeccion.get("ok") and inspeccion.get("total", 0) > 0,
+       f"Inspector encuentra vértices en la cinta: {inspeccion}")
```

Para ejemplos, conservaría los 19 del catálogo —incluyendo la detección de archivos faltantes— y sumaría los ejemplos públicos adicionales:

```diff
--- a/tools/experiments/verifica_ejemplos.py
+++ b/tools/experiments/verifica_ejemplos.py
@@
     with open(os.path.join(EJEMPLOS, "examples.json"), encoding="utf-8") as f:
         catalogo = json.load(f)["ejemplos"]
+    exigir(bool(catalogo), "el catálogo de Aprender no está vacío")
@@
-    log("=" * 70)
-    log("VEREDICTO: " + ("TODO VERDE" if not FALLAS else f"{len(FALLAS)} FALLA(S): {FALLAS}"))
+    web = json.loads(api.ejemplos())
+    exigir(bool(web), "el catálogo público de ejemplos no está vacío")
+    conocidos = {os.path.splitext(e["archivo"])[0] for e in catalogo}
+    nuevos = [e for e in web if e["nombre"] not in conocidos]
+    for entrada in nuevos:
+        nombre = entrada["nombre"]
+        exigir(entrada["corre"],
+               f"{nombre}: disponible en el motor · {entrada['faltan']}")
+        # El cargador público convierte los .jam en grafos.
+        grafo_json = api.ejemplo(nombre)
+        reporte = json.loads(api.compile_graph_json(grafo_json))
+        exigir(reporte.get("ok") and bool(reporte.get("nodes")),
+               f"{nombre} compila · {reporte.get('report', '')}")
+
+    log(f"cobertura: {len(catalogo)} tutoriales de Aprender + "
+        f"{len(nuevos)} ejemplos adicionales")
+    log("=" * 70)
+    log("VEREDICTO: " + ("TODO VERDE" if not FALLAS else f"{len(FALLAS)} FALLA(S): {FALLAS}"))
```

La sonda de funciones no necesita una adaptación funcional para conservar su alcance. Corregiría únicamente la receta del log:

```diff
--- a/tools/experiments/verifica_funcion_graph.py
+++ b/tools/experiments/verifica_funcion_graph.py
@@
-El veredicto confiable queda en ``BotOO/Saved/Logs/BotOO.log`` con el prefijo ``JAM_FUNCION_TEST``.
+El veredicto queda en el log más reciente del proyecto ejecutado, dentro de
+``Saved/Logs/``, excluyendo los archivos CRC, con el prefijo ``JAM_FUNCION_TEST``.
+Esta sonda verifica ABM y Compile; no ejecuta las herramientas geométricas.
```

**No adelantaría `verde_editor` con esta auditoría:** confirma que las sondas conservan sus contratos, identifica qué siguen midiendo y propone cómo ampliar su evidencia; no aporta una nueva certificación de Unreal.
