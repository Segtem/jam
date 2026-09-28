# DSL de grafos para Jam: el texto como segunda vista del mismo `JamGraph`

## 0. La propuesta en cinco líneas

- **Una línea por nodo, al estilo SSA:** `nombre = verbo [posicional] @entrada… clave=valor… +bandera`. El nombre del nodo es su id en el `JamGraph`. Los ejemplos reales ya usan ids legibles como `polyline` o `trunk_pipe`.
- **`@` es la única marca de cable.** `@smooth` va al pin `in`; `profile=@trunk_profile` va a un parámetro; `@deco.escala` sale por una salida extra. Una palabra suelta sigue siendo el asset, como en la consola de hoy.
- **El layout no va en el texto.** Sigue en el `.jamgraph`, que no cambia (`schema_version` 1). Para los nodos que no tienen posición, el layout se deriva.
- **El núcleo no importa `unreal`.** Lo forman `registro.py` (la descripción de cada verbo, sin `"fn"`, y sus motores), `texto.py` (lector, impresor, forma normal y ayuda) y los módulos puros que ya existen. `tools.py` queda como adaptador de Unreal.
- **La forma canónica es lo que escribe el impresor, como en Oracle.** El lector acepta variantes (orden de parámetros, `0.10`, defaults escritos) y `formatear` las lleva a la forma canónica.

## 1. Qué es «el mismo grafo»

Dos grafos son iguales si tienen la misma **forma normal** `N(g)`. `N(g)` es una función pura de `texto.py`:

1. **Nodos.** Cuentan en el orden del documento: el orden del dict, que es el de creación en el canvas y el de las líneas en el texto. De cada nodo cuentan el id, el verbo, los parámetros normalizados y las banderas `bypass` y `debug` en `true`.
2. **Parámetros.** Se comparan **por valor tipado, no por string.** El tipo sale del registro: el default de Python, `data_params`, o `tipos` en `VALORES`.
   - `"0.10"`, `"0.1"` y el `0.10000000000000001` que escribe el C++ al cargar un número JSON con `%.17g` (SJamGraphEditor.cpp:5210 aprox.) son el mismo valor.
   - **Un parámetro igual a su default se omite.** Hoy el canvas escribe todos (`GetParamValues`, SJamGraphNode.cpp:1136), así que sin esta regla nunca habría ida y vuelta.
   - Un parámetro con cable pierde el valor escrito, porque el cable manda (graph.py:533-548).
   - Una expresión se guarda siempre como `"=…"`. Hoy un parámetro numérico con texto no numérico ya se evalúa como expresión aunque no lleve `=` (graph.py:326-330): son dos grafías de lo mismo, y se normalizan a una.
3. **Asset.** El asset local vive hoy en dos lugares: `nodo["asset"]` y `params["asset"]` (graph.py:610). La forma normal usa sólo `params["asset"]`, que es donde lo guarda el canvas.
4. **Nodos de valor con nombre** (`number`, `text`, `boolean`, `math`). El lector hace `params["name"] = id`, y el impresor omite `name` cuando coincide con el id. Hoy hay una inconsistencia: `resolver` toma el default `"n"` (math_core.py:1399), mientras que Compile usa el id (graph.py:477). Con dos `number` sin `name`, Compile no ve el duplicado y la tabla de variables se pisa. Escribir el nombre explícito lo evita.
5. **Aristas.** Son un **conjunto**, salvo el orden relativo de las que entran al `in` de un verbo variádico. Ese orden sí cuenta: `mesh_merge` y `weave` reciben la lista en el orden de las aristas (graph.py:728-733 y 819-833). `N` ordena las aristas por (orden del nodo destino, orden del pin: `in`, `asset` y después los parámetros en el orden del registro, posición dentro del variádico).
6. **No cuentan:** `x`, `y`, `compact`, `reroutes`, `comments` ni `view`.

**Test de ida y vuelta**, sobre los 20 `.jamgraph` de `Resources/Examples` y los presets:

- `N(leer(imprimir(g))) == N(g)`
- `imprimir(leer(t)) == t` para todo `t` canónico.

## a. Gramática

```
texto      = { [ nodo ] "\n" } ;                       (* sin comentarios en v1 *)
nodo       = nombre "=" verbo [ posicional ] { "@" ref } { param } { bandera } ;
nombre     = IDENT ;
verbo      = IDENT | "fn:" ( IDENT | CADENA ) ;
posicional = valor ;          (* el slot que declara el verbo: asset, value, expr o name *)
param      = CLAVE "=" ( valor | "@" ref ) ;
ref        = nombre [ "." PIN ] ;
valor      = NUMERO | "true" | "false" | tupla | PALABRA | CADENA ;
tupla      = "(" NUMERO { ", " NUMERO } ")" ;          (* 2 dominio · 3 vector · 16 matriz *)
bandera    = "+bypass" | "+debug" ;

IDENT   = [A-Za-z_][A-Za-z0-9_]*          (* también es nombre de variable en expresiones *)
CLAVE   = \w+ Unicode normalizado a NFC   (* ya existen «traslación», «ángulo»: math_core.py:945,963 *)
PALABRA = [A-Za-z0-9_./:-]+  que no sea NUMERO ni true/false    (* rutas /Game/…, anclas *)
CADENA  = "…" con escapes JSON
comando = verbo [ posicional ] { CLAVE "=" valor }     (* la consola: sin nombre y sin @ *)
```

Se permiten referencias hacia adelante: el grafo es declarativo y el orden de las líneas es el orden del documento.

## b. Los dos ejemplos, transcritos enteros

**Cylinder-Strip.jamgraph**

```
x = series_range end=720 count=7
y = graph_curve start_value=0 end_value=0 midpoint=0.48 mid_value=240 samples=7
z = graph_curve start_value=0 end_value=180 midpoint=0.62 mid_value=-80 samples=7
polyline = curve_polyline x=@x y=@y z=@z
smooth = curve_smooth @polyline iterations=3 strength=0.45
uniformar = curve_resample @smooth count=31
pipe = mesh_pipe @uniformar radius_start=26 radius_end=26 sides=12 samples=32 miter_limit=2.5
normals = mesh_normals @pipe
hornear = mesh_to_static @normals name=SM_JamCylinderStrip
colocar = place @hornear view=true
```

**TreeGen-Curve-Frames.jamgraph**

```
curve = curve_bezier end_x=40 end_z=600 bend_x=80 bend_y=30 segments=16
frames = curve_frames @curve start=0.1 end=0.95 radial_offset=18 turns=2 radius_start=55 radius_end=8 seed=1977
distribute = distribute_frames @frames count=18 start=0.15 end=0.92 angle_jitter=6 parameter_jitter=0.02 seed=1977
transform = transform_frames @distribute offset_z=12 pitch=8 scale=0.85 offset_jitter_x=6 offset_jitter_y=4 offset_jitter_z=3 pitch_jitter=5 yaw_jitter=8 roll_jitter=12 scale_jitter=0.12 seed=1977
branches = branch_from_frames @transform length_min=180 length_max=300 angle=62 angle_jitter=8 curl=28 curl_jitter=12 segments=10 seed=1977
trunk_profile = graph_curve end_value=0.24 midpoint=0.58 samples=17
trunk_pipe = mesh_pipe_profile @curve profile=@trunk_profile radius=52 sides=12 samples=24
branch_profile = graph_curve end_value=0.1 shape=ease_in power=1.8 midpoint=0.5 mid_value=0.65 samples=13
branch_pipe = mesh_pipe_profile @branches profile=@branch_profile radius=12 sides=7 samples=12
merge = mesh_merge @trunk_pipe @branch_pipe
color = mesh_color @merge color="#76502F"
wood_uv = mesh_uv_scale @color u=2 v=6
wood_material = mesh_material @wood_uv material=/Engine/EngineDebugMaterials/VertexColorMaterial.VertexColorMaterial
normals = mesh_normals @wood_material
tree_asset = mesh_to_static @normals name=TreeGen_FrameFlow_Test show_vertex_colors=false
preview = place @tree_asset surface=false
frond_asset = asset PineFrond
foliage = hism_output @foliage_choose
leaf_card_asset = asset /Engine/BasicShapes/Plane.Plane
foliage_set = asset_set @frond_asset @leaf_card_asset
foliage_choose = choose_asset @transform assets=@foliage_set seed=3107
```

Los parámetros omitidos los comparé uno por uno contra los defaults del registro, cargándolo con `unreal` simulado. Por ejemplo, `hism_output` tiene todos sus valores en default, y `preserve_ends=true` y `capped=true` son defaults. Salen las 21 aristas, con el orden del variádico conservado: `@trunk_pipe @branch_pipe` y `@frond_asset @leaf_card_asset`.

## c. Ejemplo propio

`hojas_de_pino` es una función hipotética de la biblioteca. Tiene la entrada `curva` (tipo S, un pin), la perilla `cantidad` y la salida `malla` (tipo M).

```
radio = number 40 max=200
alto = number 600 max=2000
mueve = matrix_translation traslación=(0, 0, 150)
deco = matrix_decompose matriz=@mueve
tallo = curve_line_sdl direccion=@deco.eje_z largo="=alto * 0.9"
movida = curve_move @tallo desplazamiento=@deco
suave = curve_smooth @movida iterations=3 +bypass
tubo = mesh_pipe @suave radius_start=@radio radius_end="=radio / 4"
hojas = fn:hojas_de_pino curva=@suave cantidad=24
todo = mesh_merge @tubo @hojas.malla
horno = mesh_to_static @todo name=SM_Tallo +debug
```

Qué cubre cada línea:

- **Salida extra:** `@deco.eje_z`. En cambio `@deco` a secas es la traslación, porque es el `corte_principal` (math_core.py:1034).
- **Nodo de valor cableado a un parámetro:** `radius_start=@radio`.
- **Expresiones:** `largo="=alto * 0.9"` y `radius_end="=radio / 4"`.
- **Instancia de función:** `hojas`.
- **Bypass:** `suave`. Se puede porque `curve_smooth` recibe S y produce S (`puede_bypass`, graph.py:45-64).

## d. Reglas del impresor canónico

1. **Una línea por nodo, en el orden del documento.** Sin líneas en blanco y con un salto de línea final. No se reordena topológicamente: con Kahn y cola FIFO, agregar un nodo corre la posición de otros que no tienen nada que ver.
2. **Orden dentro de la línea:** nombre, ` = `, verbo, posicional, entradas `@`, parámetros, banderas. Siempre un solo espacio.
3. **Posicional.** Sólo se escribe si el verbo declara el slot en el registro neutro (`"posicional"`) y el valor no es el default:
   - `asset` para los verbos con `asset_row`;
   - `name` para el verbo `asset`;
   - `value` para `number`, `text` y `boolean`;
   - `expr` para `math`.
4. **Entradas `@`.** Van en el orden de sus aristas, que sólo importa en los variádicos.
5. **Parámetros.** Van en el orden del registro, y el cable ocupa el lugar de su parámetro. Los parámetros que el registro no conoce se escriben igual, al final y en orden alfabético: el impresor nunca descarta nada y Compile los señala.
6. **Valores:**
   - Números en su `repr` más corto que conserva el valor, sin `.0` final: `720`, `0.45`, `-80`. Se usa `repr` y no el `.6g` de `texto_de_valor`, porque `.6g` pierde precisión.
   - Booleanos como `true` y `false`.
   - Vectores, dominios y matrices entre paréntesis, con `", "` entre componentes: es el formato de `texto_de_valor` (math_core.py:1179-1207), que `_vector`, `_dominio` y `_matriz` ya aceptan (math_core.py:126-150). Una matriz son 16 números en una línea.
   - Texto sin comillas si encaja en PALABRA. Si no, va entre comillas, y siempre las lleva cuando empieza con `=` o `@` o cuando dice `true`, `false` o parece un número.
7. **Se omite:** todo parámetro en su default, el `name` igual al id, `nodo["asset"]` nulo, las banderas apagadas y todo el layout.
8. **Verbos desconocidos** (de otro motor o una función que falta): se imprimen con sus parámetros tal cual, como texto crudo.

## e. Una edición típica en el canvas, vista como diff

En Cylinder-Strip, el humano mete un `mesh_weld` entre `pipe` y `normals`, sube `iterations` y recablea `hornear`:

```diff
-smooth = curve_smooth @polyline iterations=3 strength=0.45
+smooth = curve_smooth @polyline iterations=5 strength=0.45
-normals = mesh_normals @pipe
+normals = mesh_normals @mesh_weld
-hornear = mesh_to_static @normals name=SM_JamCylinderStrip
+hornear = mesh_to_static @pipe name=SM_JamCylinderStrip
+mesh_weld = mesh_weld @pipe
```

- **Nombre del nodo nuevo:** es el verbo, con `_2`, `_3`… si ya existe. Hoy el C++ genera `n%d` (SJamGraphEditor.cpp:2259); se cambia esa línea. El nombre es estable: sólo lo cambia un renombrado explícito.
- **Dónde aparece en el texto:** al final, así que ninguna otra línea se mueve.
- **Cambiar un parámetro o recablear** cambia exactamente la línea del nodo consumidor.

## f. Errores de ejemplo

Los errores de sintaxis traen línea y columna. Los de Compile, que hoy llegan por nodo, se traducen a línea: el lector y el impresor guardan de qué línea salió cada id. La redacción reutiliza `registro_core.param_desconocido` y `opcion_invalida`.

```
línea 3, col 38: la tupla «(0, 0, 150» no cierra — falta «)». Un vector es (x, y, z).
línea 7 (tubo): «@suve» no es un nodo de este grafo — ¿quisiste decir «suave»? Los nombres son lo que está a la izquierda del «=».
línea 2 (roca): «nanite» no disponible en este motor (godot): Nanite existe sólo en Unreal. Lo tienen: unreal. Sacá el nodo o corré contra Unreal.
```

## g. Integración

**Núcleo sin `unreal`.** Lo medí con `sys.modules["unreal"] = None`:

- Importan bien: `graph`, `math_core`, `flow`, `funcion`, `registro_core`, `layout`, `shader`, `pivot`, `letras`, `display_core`, `cache_core`, `jamtool_core` y `scatter_core`.
- Fallan `tools` (tools.py:10), `preset` y **`dsl`**. `dsl` falla por `from . import tools` en dsl.py:19. `2026-09-27-JAM-FUERA-DEL-MOTOR.md` dice que el DSL sólo alcanza `unreal` al ejecutar un verbo; para `dsl.py` eso no es cierto.

**Módulos nuevos o cambiados:**

| archivo | qué | estimado |
|---|---|---|
| `jam/registro.py` (nuevo, núcleo) | El literal `REGISTRO` **sin `"fn"`**, movido de tools.py:1992-2706, con el bucle de derivación (tools.py:2989-3011), `GRAPH_*`, `PARAMS_MUDADOS`, `PARAMS_ANGULARES` y `spec_json`. Suma los campos `posicional` y `motores`, y `firma(verbo)`, que une `REGISTRO`, `VALORES`, las ops que sólo existen en Flow (`source_surface`, `instance`, `weight_material`), `input`/`output` y las instancias `fn:`. | ~900 movidas, +80 |
| `jam/texto.py` (nuevo, núcleo) | Tokenizador, lector, impresor, forma normal `N`, mapa id→línea, `ayuda(filtro, motor)` y `formatear`. | ~550 |
| `jam/tools.py` → adaptador de Unreal | Se queda con las funciones `t_*` y un `IMPLEMENTA = {verbo: fn}`. Durante la migración sigue exponiendo `tools.REGISTRO` como vista (registro + `fn`) para no romper a nadie. | ~40 |
| `jam/graph.py` | `compilar(registro=None)` usa `registro.REGISTRO` en lugar de `tools` (graph.py:379-384), con los resolvedores de asset y de motor inyectados. `ejecutar_detalle` recibe el adaptador en vez de importar `tools` y `dsl` (graph.py:707, 849 y 882). | ~40 |
| `jam/dsl.py` | `coaccionar` lee `registro` y no `tools`. La consola no cambia. | ~5 |
| `jam/funcion.py` | **Bug encontrado:** `_copiar` (funcion.py:425-428) no copia `bypass`, y `expandir` la usa para todos los nodos del grafo padre (funcion.py:450). Un grafo que tiene una instancia de función pierde todos sus bypass y esos nodos corren. Se arregla en 1 línea. | ~2 |
| `jam/api.py` | `grafo_a_texto`, `texto_a_grafo`, `canvas_publicar`, `canvas_pendiente` y `ayuda_dsl`. | ~80 |
| C++ | 1) Un panel «Texto» con vista y Aplicar. 2) El nombre del nodo visible en la ficha, y F2 para renombrarlo con `JamPedirNombre`, que ya existe (SJamGraphEditor.cpp:3170). 3) El id del nodo nuevo sale del verbo. 4) El gancho en `Marcar()` y el sondeo del buzón. | ~300 |
| tests | Ida y vuelta de los examples, un fixture por rasgo, importar el núcleo con `unreal` bloqueado y la auditoría de capacidades. | ~250 |

**`api.run(texto)`.**

- **Una línea sin `=` y sin `@` es un comando.** Pasa por `panel.ejecutar_dsl` exactamente como hoy. Lo que cambia respecto a escribir esa línea como nodo de un grafo, dicho entero:
  - La consola sólo pasa los parámetros que se tipearon, así que mandan los defaults de la función de Python (`t_scatter` tiene `view=True`, tools.py:444), no los del registro (`view=False`, tools.py:2036).
  - La consola le compone un `place` oculto a los verbos que producen puntos (panel.py:897-927).
  - La consola toma el asset del picker.
  - La consola no aparece en el canvas.
- **Cualquier otro texto es un grafo.** `texto_a_grafo` lo lee y lo compila, lo deja en el buzón del canvas y lo corre con `run_graph_json`. El reporte vuelve con líneas en vez de ids.

**Canvas.**

- `Marcar()` (SJamGraphEditor.cpp:2664) ya calcula `BuildJson()` en cada edición. Ahí se suma `canvas_publicar(json)`, que le da a Python la última versión con un contador.
- El panel sondea `canvas_pendiente(version)` con un timer, igual que el de 20 Hz que ya hay (JamEditorModule.cpp:735), y aplica con `LoadGraphJson`, que cuenta como un solo paso de deshacer.
- `LoadGraphJson` exige `x` e `y` (SJamGraphEditor.cpp:5177). Por eso `texto_a_grafo(texto, canvas_json)`:
  - conserva por nombre la posición, `compact`, los `reroutes` (reindexados según la identidad de la arista, porque hoy se guardan por índice) y los comentarios;
  - a cada nodo nuevo lo pone a la derecha de su predecesor, a +320, que es el paso de los examples;
  - si el canvas está vacío, usa `layout.auto`.
- **Diffs limpios sin migrar el almacenamiento:** `.gitattributes` con `*.jamgraph diff=jam` y `textconv = python -m jam.texto imprimir`.

**MCP, fuera del motor.** Expone tres herramientas:

- `jam_leer()` devuelve `{version, texto}` con las líneas numeradas.
- `jam_aplicar(texto, base, correr)` devuelve el texto canónico más los diagnósticos por línea. Si el humano editó después de `base`, rechaza con «releé».
- `jam_ayuda(filtro)`.

Sólo importa el núcleo, y habla con el editor por el contrato JSON.

**Capacidades por motor.**

- Cada verbo del registro neutro declara `"motores"`. El default es derivado: `("*",)` si su implementación es pura (ops de Flow, nodos de valor, `_envolver_op_flow` en tools.py:2857) y `("unreal",)` para las funciones `t_*`.
- Un campo opcional `"no_disponible": {"godot": "Nanite existe sólo en Unreal"}` da el porqué.
- Al conectarse, el adaptador anuncia `capacidades()` (los verbos que implementa). `registro_core.auditar` marca lo que está declarado pero no implementado, y al revés.
- El texto no cambia según el motor. `compilar(motor=…)` produce el error del punto f, y `ayuda(motor)` lista al final los verbos no disponibles, cada uno con su porqué. Nunca hay un fallo mudo.

**Ayuda generada**, con la misma forma que la sintaxis:

```
curve_smooth @S → S · iterations=2 strength=0.5 preserve_ends=true samples=32 — …
place [asset] @A|A[] → A · x=0 y=0 z=0 view=false … points=@P? — …
matrix_decompose → V (+ .escala .eje_x .eje_y .eje_z : V) · matriz=(16 números) — …
```

## h. La alternativa que descarté y los riesgos

**La alternativa: tuberías** (`curve_bezier | curve_frames count=12 | …`). Es lo más natural para un LLM mientras la cadena es lineal. Pero los dos ejemplos tienen abanicos: `curve` alimenta a `frames` y a `trunk_pipe`, y `transform` alimenta a `branches` y a `foliage_choose`. Eso obliga a nombrar nodos de todos modos, y quedan dos maneras de escribir lo mismo, que es lo que prohíbe el criterio 10. Descarté también:

- **Aristas en líneas propias** (`a.out -> b.in`): nombra dos veces cada nodo, gasta más tokens y separa un nodo de sus entradas.
- **Layout dentro del texto:** mover un nodo ensuciaría el diff.

**Riesgos:**

1. **Omitir defaults.** Si cambia un default del registro, cambian los grafos escritos en texto. Se mitiga con un test que congele los defaults.
2. **Renombrar en el texto equivale a borrar y crear:** se pierden la posición y los reroutes. Renombrar en el canvas no rompe los cables, pero las expresiones que usan el nombre viejo quedan rotas hasta que Compile lo avisa con «¿quisiste decir…?».
3. **Funciones:** el verbo guardado es `fn:` más un uuid (funcion.py:71 y 253). El texto usa el nombre humano, así que dos funciones con el mismo nombre son ambiguas: el error lo dice, y el impresor cae al id.
4. **Sin comentarios en v1.** Un LLM que escriba `#` va a recibir un error. Llevarlos al canvas pide un campo `nota` por nodo en el C++.
5. **Forma normal de las aristas.** Fija el orden de las aristas, y con él el orden de ejecución entre nodos independientes que colocan cosas (el desempate de `topo_order`). Queda determinista, pero puede cambiar respecto de hoy.
6. **Edición simultánea** de humano y LLM: se cubre con el `base` de versión, que rechaza en vez de mezclar.
7. **Números que no coinciden con el pedido:** con `unreal` simulado el registro tiene **171** verbos y `cable_que_falta` da **88**, no 86. El pedido tiene cifras de antes de que crecieran.

**Qué leí y qué no.** Leí y comparé contra el árbol:

- `dsl.py`, `graph.py`, `registro_core.py` y `display_core.py`;
- la parte de `REGISTRO` y la derivación en `tools.py`;
- de `math_core.py`: `VALORES` (en parte), las coerciones, `texto_de_valor` y `resolver`;
- de `flow.py`: `Flow`, `OPS_META` y `_eval_expr`;
- de `funcion.py`: `herramienta`, `colapsar`, `expandir` y `listar_definiciones`;
- `api.py` y `panel.ejecutar_dsl`;
- en el C++: `BuildJson`, `LoadGraphJson`, `EstadoDelCanvas`, `Marcar` y la creación de ids.

La superficie de Oracle (`nucleo/sintaxis.py`) sólo la miré por encima.

Para las mediciones importé módulos con Python. Sin querer creé `Content/Python/jam/__pycache__` en la copia y lo borré enseguida; el resto de las corridas usó `python -B`. No hay ningún otro archivo modificado.