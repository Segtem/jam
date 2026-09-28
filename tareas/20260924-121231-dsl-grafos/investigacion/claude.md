# DSL de grafos para Jam: una sola superficie de texto para el `JamGraph`

**Qué propongo, en una línea:** cada línea es un nodo, `nombre: verbo [asset] @entradas… clave=valor… +banderas`. El nombre del nodo **es** la clave del JSON del canvas. Un cable es `@nodo` o `@nodo.pin`. El layout **no** va en el texto: queda en el `.jamgraph` y se une por nombre.

Estado medido (con `unreal` simulado en memoria, sin escribir archivos): el `REGISTRO` tiene 171 verbos, `VALORES` 69 nodos de valor y `flow.OPS_META` 101 ops. De esas ops, 3 no están en `REGISTRO` (`source_surface`, `instance`, `weight_material`). Hoy **88** verbos exigen un cable (`registro_core.cable_que_falta`, registro_core.py:47-68), no 86.

---

## a. Gramática

```ebnf
documento = { linea "\n" } ;
linea     = "" | nodo ;
nodo      = [ NOMBRE ":" ] verbo [ asset ] { entrada } { param } { bandera } ;
verbo     = VERBO | "fn:" ( NOMBRE | CADENA ) ;
asset     = PALABRA | CADENA ;                 (* posicional, sin @ *)
entrada   = "@" ref ;                          (* cable al pin principal «in», en orden *)
param     = CLAVE "=" ( valor | "@" ref ) ;    (* literal o cable a ese pin *)
ref       = NOMBRE [ "." PIN ] ;               (* sin ".pin" = «out» *)
valor     = NUMERO | "true" | "false" | PALABRA | CADENA | tupla ;
tupla     = "(" NUMERO { ", " NUMERO } ")" ;   (* 2 = dominio, 3 = vector, 16 = matriz *)
bandera   = "+bypass" | "+debug" ;
NOMBRE    = [A-Za-z_][A-Za-z0-9_]* ;           (* ASCII: también es variable de expresión *)
CLAVE,PIN = letra { letra | dígito | "_" } ;   (* Unicode NFC: existen «ángulo», «traslación», «dirección» *)
PALABRA   = [^\s"@(+=][^\s"]*  que no sea NUMERO ni true/false ;
CADENA    = cadena JSON entre comillas dobles ;
```

Decisiones de la gramática:

- **Expresiones.** Una expresión es una CADENA que empieza con `=`: `largo="=alto * 1.5"`. Es exactamente el string que el grafo ya evalúa en cualquier parámetro (graph.py:322). No se inventó sintaxis nueva.
- **Sin comentarios.** No hay `#`: un comentario no sobrevive al canvas, y aceptarlo para después tirarlo sería un silencio. `#76502F` es una PALABRA válida.
- **Tipado.** El tipo de un literal lo decide el pin, no la forma: el default del registro, `data_params` o `VALORES[...]["tipos"]`. `name=123` en un parámetro de texto guarda `"123"`.

## b. Los dos ejemplos, enteros

Ninguno de los dos tiene `debug`, `bypass` ni `compact`. Las posiciones quedan en el `.jamgraph`.

```
x: series_range end=720 count=7
y: graph_curve start_value=0 end_value=0 midpoint=0.48 mid_value=240 samples=7
z: graph_curve start_value=0 end_value=180 midpoint=0.62 mid_value=-80 samples=7
polyline: curve_polyline x=@x y=@y z=@z
smooth: curve_smooth @polyline iterations=3 strength=0.45
uniformar: curve_resample @smooth count=31
pipe: mesh_pipe @uniformar radius_start=26 radius_end=26 sides=12 samples=32 miter_limit=2.5
normals: mesh_normals @pipe
hornear: mesh_to_static @normals name=SM_JamCylinderStrip
colocar: place @hornear view=true
```

```
curve: curve_bezier end_x=40 end_z=600 bend_x=80 bend_y=30 segments=16
frames: curve_frames @curve start=0.1 end=0.95 radial_offset=18 turns=2 radius_start=55 radius_end=8 seed=1977
distribute: distribute_frames @frames count=18 start=0.15 end=0.92 angle_jitter=6 parameter_jitter=0.02 seed=1977
transform: transform_frames @distribute offset_z=12 pitch=8 scale=0.85 offset_jitter_x=6 offset_jitter_y=4 offset_jitter_z=3 pitch_jitter=5 yaw_jitter=8 roll_jitter=12 scale_jitter=0.12 seed=1977
frond_asset: asset PineFrond
leaf_card_asset: asset /Engine/BasicShapes/Plane.Plane
foliage_set: asset_set @frond_asset @leaf_card_asset
foliage_choose: choose_asset @transform assets=@foliage_set seed=3107
foliage: hism_output @foliage_choose
trunk_profile: graph_curve end_value=0.24 midpoint=0.58 samples=17
trunk_pipe: mesh_pipe_profile @curve profile=@trunk_profile radius=52 sides=12 samples=24
branches: branch_from_frames @transform length_min=180 length_max=300 angle=62 angle_jitter=8 curl=28 curl_jitter=12 segments=10 seed=1977
branch_profile: graph_curve end_value=0.1 shape=ease_in power=1.8 midpoint=0.5 mid_value=0.65 samples=13
branch_pipe: mesh_pipe_profile @branches profile=@branch_profile radius=12 sides=7 samples=12
merge: mesh_merge @trunk_pipe @branch_pipe
color: mesh_color @merge color=#76502F
wood_uv: mesh_uv_scale @color u=2 v=6
wood_material: mesh_material @wood_uv material=/Engine/EngineDebugMaterials/VertexColorMaterial.VertexColorMaterial
normals: mesh_normals @wood_material
tree_asset: mesh_to_static @normals name=TreeGen_FrameFlow_Test show_vertex_colors=false
preview: place @tree_asset surface=false
```

Cómo salieron: los parámetros que quedan son exactamente los que difieren del default. Lo calculé en memoria contra `REGISTRO`. Por ejemplo `view=true` en `colocar`, porque el default del grafo es `False` (tools.py:2016). En cambio `miter_limit="4"` desaparece porque es igual al default `4.0`, y `"asset": ""` de `preview` también, porque vacío es igual a ausente.

## c. Ejemplo propio

`fn:"Hoja de pino"` es una función **hipotética**, con pin `rama:S`, perilla `largo` y salida `malla:M`.

```
sube: matrix_translation traslación=(0, 0, 250)
ang: number value=30 max=90
giro: matrix_rotation eje=(1, 0, 0) ángulo=@ang
m: matrix_multiply a=@sube b=@giro
partes: matrix_decompose matriz=@m
alto: number value=400 min=100 max=800
eje: curve_line_sdl origen=@partes direccion=@partes.eje_z largo="=alto * 1.5"
suave: curve_resample @eje count=16
tronco: mesh_pipe @suave radius_start=40 radius_end=12 sides=12
hoja: fn:"Hoja de pino" rama=@suave largo=120
malla: mesh_merge @tronco @hoja.malla
normals: mesh_normals @malla +bypass
hornear: mesh_to_static @normals name=SM_Arbolito
colocar: place @hornear
```

Qué muestra cada línea:

- **Salida extra:** `@partes.eje_z`. Y `@partes` a secas entrega la traslación, que es el `corte_principal` (math_core.py:1024-1043).
- **Nodo de valor cableado a un parámetro:** `ángulo=@ang`.
- **Expresión:** `"=alto * 1.5"`.
- **Instancia de función:** `hoja`.
- **Bypass:** `mesh_normals` puede llevarlo porque es M→M (`puede_bypass`, graph.py:45).
- **Variádico:** `mesh_merge` recibe dos entradas, en orden.

## d. El impresor canónico y qué es «el mismo grafo»

**Forma normal N(g).** Dos grafos son el mismo si tienen la misma N. N se arma así:

1. **Nodos por nombre.** Cada nodo es (verbo, parámetros efectivos, `debug`, `bypass`).
2. **Parámetros efectivos:**
   - Se llenan los defaults, así que omitir un default y escribirlo dan lo mismo.
   - Cada valor se convierte al tipo de su pin: `"10"` y `10` son iguales en un pin `int`, y `"0,0,300"` y `(0, 0, 300)` son iguales en un pin `V`.
   - Una expresión implícita en un pin numérico (`n*100`, aceptada en graph.py:327) se normaliza a `=n*100`.
   - El literal de un parámetro **cableado** se descarta, porque el cable manda (graph.py:489). El que todavía no se descartaba era un pin de datos opcional con literal, y el ejecutor ya lo ignora si hay cable.
3. **Asset.** `node["asset"]` y `params["asset"]` son un solo campo; el compilador ya los trata así (graph.py:610).
4. **Nombre de los nodos de valor.** En un nodo de valor, un `name` ausente vale el nombre del nodo. Esto arregla una inconsistencia real: `compilar` usa `name or nid` (graph.py:477), mientras que `resolver` usa el default `"n"` (math_core.py:1399).
5. **Cables.** Son un conjunto, salvo en el pin `in` de un verbo variádico (`aridad == -1`, graph.py:462), donde **el orden importa**: `mesh_loft` y `asset_set` dependen de él.
6. **Fuera de N:** `x`, `y`, `compact`, `reroutes`, `comments`, `view` y `schema_version`.

**Orden de los nodos: postorden desde los sumideros.**
- Los sumideros (nodos sin consumidores) van por nombre.
- Antes de cada nodo se imprimen sus dependencias no impresas, recorridas en el orden de sus pines: asset, entradas `in` en su orden y después los parámetros en orden del registro.
- Una variable citada en una expresión cuenta como dependencia **para el orden** (se detecta con la misma regex de math_core.py:1325). Por eso `alto` aparece justo antes de `eje`.

El resultado: cada valor se define inmediatamente antes de su primer uso, y una cadena se lee de arriba abajo.

**Orden dentro de una línea:**
1. `nombre:` y el verbo.
2. El asset: `params["asset"]` en los verbos con `asset_row`, o `name` en el verbo `asset`, que es la convención de la consola (panel.py:876).
3. Las entradas `@…`.
4. Los parámetros en el orden del registro, que es el orden en que la ficha los dibuja (tools.py:3104).
5. `+bypass`, `+debug`.

**Qué se omite:** los parámetros iguales a su default, el `name` de un nodo de valor cuando es igual al nombre del nodo, y `.out` en las referencias.

**Literales:**
- Números en su `repr` más corto; un float entero se escribe sin `.0` (`720`).
- Booleanos `true`/`false`.
- Una cadena va sin comillas si cabe en PALABRA; si no, como cadena JSON.
- Tuplas `(a, b, c)` con `", "`: la misma forma que `texto_de_valor` (math_core.py:1179-1207), pero **sin pérdida** (`repr` en vez de `.6g`) y sin el atajo «16 números» para las matrices. El lector guarda `"a,b,c"`, igual que el canvas.

**Forma única.** Como en Oracle, el lector acepta un superconjunto pequeño y enumerado:
- línea sin `nombre:`;
- `sí/no/1/on`;
- los alias `n/s/h/t` (dsl.py:22);
- comillas de más;
- tuplas sin espacio.

`api.graph_format` lo lleva a la forma única. Los tests fijan dos cosas: que imprimir y releer un texto canónico da el mismo texto, y que `normal(leer(imprimir(g))) == normal(g)` para los 20 ejemplos de `Resources/Examples`, más un nodo por cada verbo con parámetros al azar.

**Nombres nuevos.** Valen para una línea sin nombre y para un nodo creado en el canvas:
- La base es el verbo sin su prefijo de familia (`mesh_`, `curve_`, `math_`, `matrix_`, `vector_`, `domain_`, `series_`, `weight_`, `mask_`, `mat_`, `material_`, `mass_`, `time_`, `compare_`, `pts_`, `reroute_`). Así `curve_noise` da `noise` y `mesh_to_static` da `to_static`.
- En un nodo de valor, la base es el default de su `name` (`n`, `t`, `b`, `m`).
- En una instancia de función, el nombre de la función en minúsculas y con `_`.
- Si la base ya existe, se agrega el sufijo *máximo existente + 1* (`noise2`).
- **Nunca se renombra un nodo que ya existe.** Los ids viejos `n7` se imprimen tal cual; migrarlos es una acción explícita, `api.graph_rename_legible`.

**Instancias de función.** Se imprime la etiqueta de la definición (`fn:"Hoja de pino"`). El lector la resuelve contra `funcion.listar_definiciones()` para obtener el `funcion_id`. Si dos definiciones comparten etiqueta, se imprime el id (`fn:f_…`, funcion.py:71). Si no, perdería la ida y vuelta.

## e. Edición típica en el canvas, vista como diff

**1. Suelta `curve_noise` sobre el cable `smooth → uniformar`.** El canvas ya divide el cable (SJamGraphEditor.cpp:3911-3925). El nombre nuevo es `noise`:
```diff
 smooth: curve_smooth @polyline iterations=3 strength=0.45
+noise: curve_noise @smooth
-uniformar: curve_resample @smooth count=31
+uniformar: curve_resample @noise count=31
```

**2. Cambia `sides` en `pipe`:** cambia una sola línea.
```diff
-pipe: mesh_pipe @uniformar radius_start=26 radius_end=26 sides=12 samples=32 miter_limit=2.5
+pipe: mesh_pipe @uniformar radius_start=26 radius_end=26 sides=16 samples=32 miter_limit=2.5
```

**3. Recablea `trunk_pipe.profile` desde `branch_profile` (TreeGen).** Cambia la línea de `trunk_pipe`. `branch_profile` sube para quedar antes de su primer uso, y `trunk_profile`, que quedó sin consumidor, pasa a ser sumidero y baja al final. **Un recableado puede mover líneas; un parámetro o una inserción no.**

## f. Tres errores

Todos siguen el mismo formato: `línea N[, columna C]: qué — cómo seguir`. La API los devuelve además como `{linea, columna, nodo, mensaje}`.

```
línea 5, columna 32: «iterations» suelto sería el asset, pero `curve_smooth` no recibe asset
  — ¿quisiste escribir `iterations=3`?
línea 8 (normals): «in» esperaba M (malla) y `@smooth` entrega S (curva)
  — una curva se vuelve malla con mesh_pipe, mesh_ribbon, mesh_loft, mesh_revolve…
línea 7, columna 38: `partes` (matrix_decompose) no tiene la salida «eje_w»
  — tiene out, escala, eje_x, eje_y, eje_z; ¿quisiste decir «eje_x»?
```

De dónde sale cada uno:
- **El primero** es del lector.
- **El segundo** sale de `compilar` (graph.py:445). Como el diagnóstico viene por nid y **el nid es el nombre de una línea**, todo el Compile queda ubicado por línea sin trabajo extra. La sugerencia se deriva del registro: los verbos con `in_name=S` y `out_name=M`.
- **El tercero** reusa graph.py:428 más `_parecido` (registro_core.py:71).

## g. Integración

**Cerebro puro: `Content/Python/jam/texto.py` (nuevo, cero `unreal`, unas 500 líneas).**
- `leer(texto, vocab)` devuelve `(JamGraph, líneas_por_nodo)` o `ErrorTexto(linea, columna, msg)`.
- `imprimir(g, vocab)`.
- `normal(g)`.
- `aplicar(texto, json_base)`, que une el layout.
- `nombre_nuevo(verbo, usados)`.
- `firma(verbo)`: la ayuda generada, escrita **en la misma sintaxis**. Por ejemplo `curve_smooth @S iterations=2 strength=0.5 preserve_ends=true samples=32 → S`.

`vocab` es `REGISTRO ∪ VALORES ∪ OPS_META ∪ input/output ∪ fn:`, el mismo universo que `api.spec_all` (api.py:281). Tiene que ser idéntico, porque `LoadGraphJson` rechaza un verbo que no conoce (SJamGraphEditor.cpp:5172).

**Cómo `aplicar` une el layout:**
- Un nodo que sobrevive conserva `x`, `y` y `compact` por nombre.
- Un nodo nuevo va 320 px a la derecha de su primera fuente (el paso de los ejemplos). Si no tiene fuente, se pone a la izquierda de su primer consumidor. Si todo el grafo es nuevo, se usa `layout.auto` (layout.py:137).
- Los `reroutes` se **reindexan** por identidad del cable, porque hoy la clave es el índice de la arista (SJamGraphEditor.cpp:4262-4306) y el orden de las aristas cambia.
- Los `comments` pasan tal cual.

**Tamaño estimado:** unas 500 líneas de `texto.py`, unas 350 de tests, unas 60 de `api` y unas 250 de C++. `dsl.py` se achica, porque `parsear` pasa a delegar en el lexer; hoy usa `shlex` (dsl.py:28).

**`api` y `panel`:**
- Funciones nuevas en `api`: `graph_text(json)`, `graph_from_text(texto, base_json)` → `{ok, graph, errores, canonico}`, `run_text(texto)` (Compile y Run con diagnósticos por línea), `graph_format(texto)`.
- `api.run` (api.py:66) no cambia de firma. `panel.ejecutar_dsl` (panel.py:830) detecta `:` o `@` o varias líneas y ahí manda el texto por `graph_from_text` y el runner del grafo.

**Consola (criterio 6).** `scatter SM_Rock count=20` sigue siendo una línea válida. En la consola sigue siendo un **comando**: usa los defaults de la función (`view=True`) y compone el `place` (panel.py:909-927), igual que hoy. En un documento, la misma línea es un **nodo** con los defaults del registro, y ahí `scatter SM_Rock` es un error («`scatter` no recibe asset: cablealo a `points` de un `place`»).

Lo que cambia en la consola:
- las comillas simples de `shlex` ya no se aceptan;
- un literal con tipo inválido falla en vez de coaccionarse;
- una línea con `nombre:` o `@` pasa a ser un fragmento de grafo.

**Canvas (C++):**
1. **`AddNode`** deja de emitir `n%d` (SJamGraphEditor.cpp:2259) y usa `nombre_base`. Ese campo viaja en `spec_json`, como hoy viaja la `letra` (tools.py:3082); el C++ sólo agrega el sufijo.
2. **La cabecera muestra el nombre** además de la etiqueta. Hoy sólo muestra `Label` (SJamGraphEditor.cpp:2373). Con F2 se renombra: se validan el regex y la unicidad, se reescriben los cables y, en un nodo de valor, también `name` si coincidía con el nombre viejo.
3. **Pestaña «Texto».** En cada paso del historial muestra `graph_text(BuildJson())`. «Aplicar» llama a `graph_from_text` y después a `LoadGraphJson`, que ya valida todo antes de tocar nada y registra un solo paso de deshacer (SJamGraphEditor.cpp:5099-5160). Los errores enlazan a su línea.
4. **Buzón.** Hoy el C++ sólo llama a Python; no hay forma de que Python le empuje algo. Se agrega:
   - un temporizador de 0,25 s que llama `_a.canvas_buzon(version)`, y
   - `_a.canvas_publicar(json)` en cada cambio,

   para que un escritor externo lea y escriba el grafo vivo.

**MCP.** Tres herramientas:
- `leer_grafo()` devuelve `{texto, version}`.
- `aplicar_texto(texto, version)` devuelve errores por línea, o el texto canónico más el resultado del Compile. Si la versión cambió porque el humano editó entretanto, lo rechaza con el texto fresco (concurrencia optimista).
- `correr()` y `ayuda(verbo|familia)` con las firmas.

El LLM siempre recibe de vuelta la forma canónica, y así la aprende.

## h. La alternativa descartada y los riesgos

**La mejor alternativa descartada: sintaxis de tubería o anidada**, del estilo `curve_bezier(end_z=600) | curve_frames(count=12) | …`.
- A favor: es más corta en cadenas y no pide nombres.
- En contra: un DAG con abanico (`curve` alimenta a `frames` y a `trunk_pipe`) obliga a nombrar igual. Quedarían dos formas de escribir lo mismo (en línea y con nombre), y eso rompe el criterio 10.
- Además, insertar un nodo reescribe una expresión anidada entera, y el diff deja de ser por línea.

**También descarté poner el layout en el texto** (sufijos `@ (x, y)`): arrastrar un nodo ensuciaría el diff, y el LLM pagaría tokens por algo que no decide.

**Riesgos:**
1. **Omitir defaults.** Si cambia un default en el registro, cambia un texto que se guardó *como texto*. El `.jamgraph` no se ve afectado, porque el canvas escribe todos los valores (SJamGraphEditor.cpp:4231). Mitigación: el almacenamiento sigue siendo el JSON, y un cambio de default se trata como hoy `PARAMS_MUDADOS`.
2. **Estabilidad del orden.** No es absoluta: un recableado o un sumidero nuevo que comparte ancestros mueve líneas.
3. **El nombre es la identidad.** Renombrar no reescribe las expresiones que citan la variable; el Compile avisa con «¿quisiste decir?».
4. **Reroutes por índice.** Si la unión se equivoca, pega los puntos de paso al cable equivocado.
5. **Texto dentro del texto.** Los nodos `mat_*` guardan un mini-lenguaje (`inputs`, `props`) que queda como cadena opaca.
6. **Claves Unicode.** Hay que normalizar a NFC; `angulo` sin tilde se resuelve con la sugerencia.
7. **Literal de un parámetro cableado.** Se pierde: si después se desconecta, vuelve el default.
8. **Etiquetas de funciones.** Renombrar una función cambia el texto de todos los grafos que la usan.