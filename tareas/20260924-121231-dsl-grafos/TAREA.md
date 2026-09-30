# El DSL no puede describir un grafo: no hay cables ni nodos con nombre, y no hay ida y vuelta con el canvas

- ESTADO: ABIERTA
- PRIORIDAD: 95
- ETIQUETAS: dsl, graph, llm, commander


## Por qué

Auditoría de [`dsl-llm`](../20260924-114746-dsl-llm/AUDITORIA.md), §1–3 y nivel 1: `dsl.parsear` lee
una línea por vez (`verbo [asset] [clave=valor]`), sin forma de conectar la salida de un verbo con la
entrada de otro. Eso deja 86 verbos fuera del alcance de un LLM: mallas, curvas, frames, materiales,
Mass y todo el flujo de puntos. Además, lo que corre por `api.run` no aparece en el canvas, y nada
convierte un `JamGraph` en DSL: el LLM y el humano trabajan sobre cosas distintas.

## Qué hacer

1. **Diseño primero, sin código**, con tres modelos a ciegas (Codex, agy, Claude), como se decidió en
   Oracle `repo-limpio`. El DSL de grafos tiene que ser una **superficie legible del mismo
   `JamGraph`**: nodos con nombre (no `n1`), cables por nombre de pin, parámetros tipados (vectores,
   dominios, matrices). Tiene que existir una conversión exacta en los dos sentidos (DSL → grafo →
   DSL da el mismo texto; grafo → DSL → grafo da el mismo grafo). Antecedente: la superficie infija
   de Oracle, que se lee tal cual como la forma canónica, con ida y vuelta verificada.
2. Después, implementar: `dsl → JamGraph` (lo que escribe el LLM aparece como nodos) y
   `JamGraph → dsl` (lo que edita el humano se lee como texto), con la ida y vuelta como test.
3. La consola de una línea sigue funcionando como caso particular.

### Nota (2026-09-28 01:45:28 UTC)

2026-09-27, Claude: pedido de diseño escrito en investigacion/pedido.txt: el mismo texto para los tres, a ciegas entre sí, con diez criterios escritos para elegir (ida y vuelta exacta y qué es «el mismo grafo», cobertura del modelo entero, escribible por un LLM, legible en el canvas, diffs limpios, la consola de una línea como caso particular, dónde vive el layout, literales ricos coherentes con texto_de_valor, cerebro puro, una sola forma canónica) y entregables comparables: gramática, Cylinder-Strip y TreeGen-Curve-Frames transcritos enteros, un ejemplo propio con multi-salida, valor cableado, expresión, función y bypass, reglas del impresor, errores con línea, integración con api.run/canvas/MCP y la alternativa descartada. Lanzados: agy (gemini-3.8-flash-high) en contenedor agy-naval sobre una copia git archive de HEAD, y un agente Claude nuevo sin el contexto de esta sesión. Codex (gpt-6-sol) vuelve el 2026-09-30.

## Dos de tres propuestas, versión 1 (2026-09-27, sin el criterio 11)

agy ([agy.md](investigacion/agy-v1.md), gemini-3.8-flash-high en contenedor) y un agente Claude sin
contexto ([claude.md](investigacion/claude-v1.md)). Codex vuelve el 2026-09-30. Lo verificado contra el
árbol está marcado; el resto es lo que cada uno afirma.

| criterio | agy | Claude |
|---|---|---|
| forma | un nodo por bloque: `nombre: verbo [flags]` y un atributo `pin = valor` por línea indentada | un nodo por línea: `nombre: verbo [asset] @entradas clave=valor +flags` |
| 1 · ida y vuelta | define «el mismo grafo»; pero imprime floats con `.6g` → **pierde precisión**, grafo→texto→grafo no es exacto | forma normal N(g) explícita (defaults llenados, tipos por pin, literal de pin cableado descartado, cables como conjunto salvo variádicos); `repr` sin pérdida |
| defaults | dice omitirlos, pero sus transcripciones los escriben (`start = 0.0` es el default de `series_range`, medido) | los omite; transcripciones calculadas contra REGISTRO (`view=true` en place: default False, medido) |
| 2 · cobertura | ejemplo propio con errores: `matrix_construct` **no existe**; `descomp.traslacion` no es una salida extra (lo es el principal); `mesh_simplify_count` no tiene `target_count` (medido) | ejemplo propio válido: todos los verbos y pines existen, incluidos `traslación`/`ángulo` Unicode y `@partes.eje_z` (medido); resuelve funciones por etiqueta con fallback a id |
| 3 · escribible por un LLM | verboso (un atributo por línea) | compacto; la ayuda se genera en la misma sintaxis (`firma(verbo)`) |
| 4 · nombres legibles | slug del verbo + sufijo | ídem, sin renombrar nunca lo existente; F2 para renombrar |
| 5 · diffs | el orden topológico se desempata **por posición x/y**: mover un nodo reordena el texto | postorden desde sumideros: un param o una inserción cambian sólo sus líneas; un recableado puede mover líneas (declarado) |
| 6 · consola | la línea vieja sigue por el camino histórico | ídem, y distingue comando (compone place) de nodo en documento |
| 7 · layout | en el texto (bloque `layout:` y `comment`): arrastrar ensucia el diff | fuera del texto, unido por nombre; reindexa `reroutes`; propone buzón C++ para escritor externo |
| 8 · literales ricos | `(x, y, z)`, `matrix(…16…)` | tuplas; tipo por pin, sin atajo de matriz |
| 9 · implementación | ~1055 líneas; propone `layout_core.py` nuevo aunque `layout.auto` ya existe (layout.py:137) | ~500 + 350 tests + 60 api + 250 C++; reusa `layout.auto` |
| 10 · forma única | sí | sí, con un superconjunto de entrada enumerado que el formateador normaliza (como Oracle) |
| hechos | varias citas imprecisas | cifras correctas: REGISTRO 171, VALORES 69, OPS 101, **88** verbos que exigen cable (la auditoría decía 86) — medido |

Encontrado de paso por Claude, a verificar: `compilar` nombra un nodo de valor `name or nid`
(graph.py:477) y `math_core.resolver` usa el default `"n"` (math_core.py:1399).

### Nota (2026-09-28 01:56:08 UTC)

2026-09-27, Claude: por pedido de Brian, el pedido suma el criterio 11 (núcleo fuera del motor: el grafo y el DSL no importan unreal, sobre un registro neutro con capacidades por motor; ver fuera-del-motor) y el entregable g lo cubre. Las dos respuestas de arriba son la versión 1, sin ese criterio: se relanzan agy y un Claude nuevo con el pedido actualizado, y Codex (2026-09-30) recibe el mismo.

## Versión 2, con el criterio 11 (2026-09-27)

Mismo pedido con el criterio 11, sobre una copia sin las respuestas v1 ni la tabla: agy
([agy.md](investigacion/agy.md)) y un Claude nuevo ([claude.md](investigacion/claude.md)).

| criterio | agy v2 | Claude v2 |
|---|---|---|
| forma | igual que v1: bloque por nodo, `pin = valor` por línea; flags `@bypass` | `nombre = verbo [posicional] @entradas clave=valor +bypass` (una línea por nodo, estilo SSA) |
| 1 · ida y vuelta | forma normal definida, pero sigue con `.6g` → **pierde precisión** | forma normal N(g) completa; `repr`; valores tipados por pin, incluido el `%.17g` que escribe el C++ |
| defaults | dice omitirlos y los imprime: `capped = true`, `profile_rotation = 0.0`, `pivot_uvs = false` en mesh_pipe son defaults (medido) | omitidos, comparados uno por uno contra el registro |
| 2 · cobertura | ejemplo propio con verbos **inexistentes**: `matrix_from_trs`, `mesh_relax` (medido) | todos los verbos y pines existen (medido); slot posicional declarado por verbo (asset, value, expr, name) |
| 5 · diffs | orden topológico con desempate alfabético: insertar un nodo lo mete en medio | **orden del documento** (el de creación): un nodo nuevo va al final, nada más se mueve; un param o un recableado tocan una línea |
| 7 · layout | en el texto (`layout:` con posiciones, comments y reroutes) | fuera del texto; unido por nombre; `textconv` de git para leer los `.jamgraph` como texto en los diffs |
| 11 · fuera del motor | `registro_neutro.py` con `motores: {unreal, godot, unity}` y motivo; error «no disponible en motor» con línea; CI con `unreal` bloqueado | `registro.py` (REGISTRO sin `fn`, con `motores` derivado: `*` si la implementación es pura, `unreal` para `t_*`, y `no_disponible` con el porqué); `tools.py` queda como adaptador con `IMPLEMENTA`; `compilar(motor=…)`; auditoría de capacidades declaradas contra implementadas. **Midió** qué módulos importan con `unreal` bloqueado: `dsl.py` NO (por `from . import tools`), contra lo que decía la nota de fuera-del-motor (verificado) |
| 9 · tamaño | ~1000 líneas | ~900 movidas de tools a registro, ~550 texto.py, ~300 C++, ~250 tests |
| hallazgos | — | bug de `funcion._copiar` sin `bypass` (verificado y arreglado en `bypass-funciones`); dos valores sin `name` se pisan (verificado, tarea `valor-sin-nombre`) |

La v2 de Claude y su v1 coinciden en lo esencial (una línea por nodo, `@` para cables, layout fuera,
forma normal con defaults omitidos) y difieren en `:` vs `=` y en el orden (postorden desde los
sumideros en v1; orden del documento en v2, que da diffs más estables).

### Nota (2026-09-28 02:53:25 UTC)

2026-09-27, DECISIÓN de Brian: se elige la propuesta de Claude v2 (investigacion/claude.md). Cuando vuelva Codex (2026-09-30) se le pasa el mismo pedido y se contrasta su respuesta con la elegida, sin reabrir la elección salvo que encuentre algo que la rompa. Se implementa después de la etapa 1 de fuera-del-motor.

### Nota (2026-09-28 10:07:35 UTC)

2026-09-28, Claude: tramo 1 hecho — jam/texto.py (núcleo, sin unreal): vocabulario (registro neutro + VALORES + ops de Flow + bordes de función), leer (texto → JamGraph, ErrorTexto con línea y columna), imprimir (forma canónica: una línea por nodo en orden del documento, posicional, @entradas, params en orden del registro sin defaults, +bypass/+debug), normal (forma normal tipada por pin: defaults, cableados, expresión implícita → «=…», valor sin name = id, cables como conjunto salvo el variádico), lineas (nodo → línea, para ubicar diagnósticos) y ayuda (firma en la misma sintaxis). Verificación: test_texto.py, 30 tests: sobre los 19 ejemplos y 3 presets de grafo, grafo→texto→grafo da la misma forma normal, el texto canónico es punto fijo, y el PLAN del Compile (orden, params resueltos, assets o diagnósticos) es idéntico para el original y el releído; Cylinder-Strip sale carácter por carácter como lo transcribió el diseño; el ejemplo propio del diseño (salida extra, valor cableado, expresiones, fn:, bypass, variádico) es canónico. Mutación a mano de texto.py: .6g, normal que ignora valores, variádico sin orden, bypass perdido y defaults no omitidos — mueren los cinco (el de .6g recién con el test de precisión que se agregó por eso). En el camino se cerró valor-sin-nombre (la regla name = id, que el texto necesita). Suite 1295 OK; oracle test VERDE. Pendiente: resolver las instancias fn: por etiqueta (hoy se escribe el verbo crudo, fn:<id>, y sus params van en orden alfabético) y el campo motores.

## Codex, contrastado con la elegida (2026-09-28)

Respondió el mismo pedido (v2, con el criterio 11) sobre la copia a ciegas, con `gpt-6-astra` (el
modelo de `~/.codex/config.toml`), 128 mil tokens: [codex.md](investigacion/codex.md). Propone otra
filosofía: igualdad **documental** —se conservan los defaults escritos, la representación de cada
string (`"10"` ≠ `10`), el literal tapado por un cable, el layout y las definiciones de funciones
congeladas dentro del documento—, con los cables en líneas propias (`a.out -> b.in`) y un
encabezado `jam 1`. Sus transcripciones son largas a propósito (Cylinder-Strip en 31 líneas).

No rompe la elegida: es el otro extremo del mismo compromiso, y Brian eligió el texto corto para el
LLM. Lo que se toma:

- **El literal tapado por un cable** no se pierde: `texto.aplicar` lo conserva del `.jamgraph` base
  (hecho en el tramo 2, con test).
- **Una divergencia real Graph/Flow**: en Flow un variádico acepta un stream; en el Graph, los
  wrappers fijan mínimo dos (`registro._registrar_ops_flow`). Queda anotado acá; no bloquea.
- Lo que señala de `graph.py:519`, `funcion.py:141` y `dsl.py:19` ya lo resolvió la etapa 1 de
  `fuera-del-motor` (su copia es anterior).
- Las funciones congeladas en el documento y `@id(...)` para ids opacos son la respuesta a lo que
  la elegida deja abierto (resolver `fn:` por etiqueta); se retoma cuando se haga eso.

### Nota (2026-09-28 10:11:11 UTC)

2026-09-28, Claude: tramo 2 hecho — la integración. texto.aplicar (puro): JSON del canvas desde el texto conservando layout por NOMBRE, nodos nuevos a la derecha de su fuente y nunca encima de otro, params completos con defaults (el canvas los guarda todos), el literal tapado por un cable conservado del base, reroutes reindexados por identidad del cable y comentarios tal cual. api.graph_text, api.graph_from_text (errores de lectura con línea y columna; diagnósticos del Compile en la línea de su nodo; devuelve el canónico) y api.run_text (corre por el MISMO run_graph_json del canvas; el reporte dice «línea N [nodo·verbo]»). api.run manda a run_text todo lo que tenga «nombre =»; la consola de una línea sigue igual. Tests: test_texto_api.py, 12 (mutantes a mano: encimar, reroute por índice viejo, layout no conservado y literal tapado, los cuatro mueren). Editor (JamPlayground, tools/experiments/verifica_texto_58.py): VERDE — un documento escrito a mano corre por api.run y coloca, cada nodo con su línea; uno con error no toca la escena y sugiere «caja»; Cylinder-Strip por texto da los mismos 10 estados y los mismos textos que por JSON. Suite 1307 OK; oracle test VERDE (28/4/3, 1099, 448/448).

### Nota (2026-09-28 10:20:13 UTC)

2026-09-28, Claude: tramo 3 hecho — el canvas (C++). (1) Ids legibles: AddNode pide el nombre a Python (texto.nombre_nuevo: el verbo, _2/_3 si existe, «funcion» para fn:, nunca renombra; n%d queda sólo de respaldo si Python no contesta). (2) La cartela del nodo dice «nombre · etiqueta» (sólo el nombre si no entra) con el nuevo SLATE_ARGUMENT NodeName. (3) Panel «✎ Texto» a la derecha del canvas (no una SWindow: no se acopla): el grafo escrito, Aplicar (graph_from_text + LoadGraphJson, diferido un frame por el crash de Prepass_Internal, un paso de Undo, conserva el documento), ↻ Del canvas, «● sin aplicar», y los errores por línea abajo; lo tipeado sin aplicar no se pisa. (4) Buzón: el Graph publica su grafo a Python en cada cambio (Marcar y RestaurarSnapshot → AlCambiarGrafo → api.canvas_publicar) y sondea api.canvas_pendiente cada 0,5 s; api.run de un documento lo deja ahí, así que lo que corre un agente aparece en el canvas abierto; graph_text() y run_text sin argumento parten del canvas. FJamEditorModule::LlamarApi (público) es la única vía nueva a Python. Nuevo comando de consola Jam.AbrirGraph para que una sonda abra el Graph (receta en AGENTS.md). Verificación: test_texto_canvas.py, 15 (nombres, buzón y el contrato con el .cpp: las funciones de api que el C++ llama existen, AddNode no emite n%d, cada cambio publica, Aplicar y el buzón cargan diferido); compilado con tools/build.py (al día); editor, tools/experiments/verifica_texto_canvas_58.py con el Graph abierto: VERDE — publica al abrir, api.run de un documento aparece en el canvas con sus nombres y params, y el texto del canvas es exactamente el escrito. Suite 1322 OK; oracle test VERDE (28/4/3, 1099, 448/448). Lo visual queda para Brian: gesto-texto.

## Próximo paso

1. `gesto-texto` (Brian mira el canvas).
2. Lo que falta del diseño: `motores` / `no_disponible` en el registro (criterio 11), las instancias `fn:` por etiqueta con su firma, y F2 para renombrar un nodo (reescribe cables y el `name` de un valor).
3. Con eso, `jam-mcp`: `leer_grafo` = `api.graph_text()`, `aplicar_texto` = `api.graph_from_text` / `run_text`, más la concurrencia por versión.

### Nota (2026-09-30 10:23:22 UTC)

2026-09-30, Claude: instancias fn: por NOMBRE — hecho. texto.vocabulario(funciones) acepta la biblioteca del usuario (las fichas de funcion.herramientas(), que el núcleo no lee: la pasa api._vocab); con ella imprimir escribe fn:<nombre> (entre comillas si tiene espacios) con las perillas en el orden de la firma, y leer resuelve el nombre al id. Va por id cuando el nombre es ambiguo (dos funciones iguales: leer el nombre es error y dice los ids) o choca con otro id, y sin biblioteca (fuera del motor) todo sigue por id. Un nombre mal escrito sugiere el parecido. test_texto_funciones.py (6); en el editor tools/experiments/verifica_texto_funciones_58.py VERDE (collapse_function real → graph_text escribe «f1 = "fn:Cilindro doblado sonda" @cil» → graph_from_text vuelve al mismo id, punto fijo); verifica_texto_58 sigue VERDE. Queda de esta tarea: F2 para renombrar (C++) y gesto-texto.
