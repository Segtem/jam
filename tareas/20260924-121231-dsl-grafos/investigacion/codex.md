Propongo **un documento declarativo con nodos nombrados, cables explícitos y presentación conservada**. El texto describe el estado editable; ejecutar es otra operación sobre ese mismo estado. La unidad de ida y vuelta debe ser un `JamGraph` ampliado que conserve también presentación y referencias a funciones.

Hoy eso requiere cambios reales: `JamGraph.from_json` conserva `debug` y `bypass`, pero pierde `compact`, `reroutes` y `comments`; `to_json` sólo escribe nodos y aristas (`Content/Python/jam/graph.py:115–151`). El canvas sí guarda esos datos (`Source/JamEditor/Private/SJamGraphEditor.cpp:4216–4336`).

La auditoría tampoco debe tomarse como fotografía vigente: ya hay validación de parámetros y opciones, y cancelación por fallo aguas arriba (`Content/Python/jam/dsl.py:49–80`; `graph.py:515–558,762–787`).

**Sintaxis propuesta**

```ebnf
documento = "jam 1", NL, {funcion}, cuerpo ;
funcion   = "function", nombre, [identidad], "{", NL, cuerpo, "}", NL ;
cuerpo    = {nodo}, {cable}, [layout] ;
nodo      = nombre, ":", operacion, {parametro}, {atributo}, NL ;
operacion = identificador | "flow:", identificador | "fn:", nombre ;
parametro = nombre, "=", literal ;
atributo  = identidad | "@asset(", cadena, ")"
          | "@bypass" | "@debug" | "@compact" ;
identidad = "@id(", cadena, ")" ;
cable     = referencia, "->", referencia, NL ;
referencia = nombre, ".", nombre ;
layout    = "layout {", NL, {presentacion}, "}", NL ;
presentacion = nombre, ":", punto, NL
             | "route", referencia, "->", referencia, "=", lista_puntos, NL
             | "comment", nombre, "=", objeto, NL
             | "view", "=", objeto, NL ;
literal   = escalar_JSON | tupla_numerica | lista | objeto ;
punto     = "(", numero, ",", numero, ")" ;
nombre    = identificador_Unicode | cadena_JSON ;
```

Los nombres que admiten identificador se imprimen sin comillas; los demás, con comillas JSON. No hay conexiones implícitas ni abreviaturas de `out`/`in`.

`flow:` identifica el contrato de Flow cuando difiere del verbo homónimo. Es necesario resolver esa diferencia explícitamente: hoy Flow admite un stream para un variádico, mientras los wrappers incorporados al Graph fijan mínimo dos (`flow.py:1000–1005`; `tools.py:2955–2975`). Los valores compartidos tienen una sola identidad, sin prefijo. El importador identifica la ruta histórica una vez; el documento nuevo nunca cambia de ejecutor porque alguien agregó un nodo.

**Qué significa “el mismo grafo”**

Defino una normalización documental `N`, sin ejecutar ni resolver assets:

- Conserva identidades, nombres visibles, operaciones, parámetros escritos, referencias de funciones, flags, layout y **orden completo de nodos y aristas**.
- `"10"`, `10` y `10.0` conservan su representación y tipo almacenado. Pueden producir el mismo valor al ejecutar, pero son estados documentales distintos. La coerción pertenece a Compile.
- Un parámetro explícito igual al default **se escribe**. Uno ausente sigue ausente. También se conserva el valor local tapado por un cable.
- Ausencia y valor estructural vacío son equivalentes únicamente donde el esquema lo declara: `asset=null`, flags falsos, coordenadas cero, colecciones de presentación vacías y versión histórica ausente.
- Se ignoran espacios del JSON y orden de claves dentro de objetos; no se ignora el orden de nodos. La cola topológica actual respeta inserción (`graph.py:92–110`).
- El orden variádico importa: el ejecutor reúne entradas siguiendo las aristas (`graph.py:725–734,819–833`). No se ordenan cables por nombre.

Las leyes son:

```text
leer(imprimir(N(g))) = N(g)
imprimir(leer(t)) = t                 si t es canónico
formatear(formatear(t)) = formatear(t)
```

Esto es igualdad documental, no igualdad aproximada del resultado geométrico. Campos desconocidos que el impresor no pueda representar provocan error; nunca desaparecen. Oracle ya aplica esa defensa al imprimir casos (`vendor/oracle-pkg/oracle_metalenguaje/nucleo/caso.py:482–503`).

**Reglas del impresor**

Orden fijo: encabezado, definiciones, nodos, cables, layout. Conserva el orden almacenado de definiciones, nodos y cables; parámetros alfabéticos; atributos `id`, `asset`, `bypass`, `debug`, `compact`. Una línea por nodo y por cable, espacios uniformes, UTF-8 y salto final.

Layout: posiciones en orden de nodos; rutas en orden de aristas; comentarios en su orden almacenado. Los puntos intermedios conservan su secuencia. Al importar/exportar JSON, las rutas se traducen entre extremos nombrados e índices de arista; hoy esos índices son su clave (`SJamGraphEditor.cpp:4279–4306`).

Una posición omitida significa `(0, 0)`, no “recalcular layout”. La UI puede ofrecer acomodar nodos, pero eso constituye una edición persistida. `view` guarda cámara del canvas; es distinto del parámetro `view` de `place`. `BuildJson` actualmente no escribe esa cámara.

Los ejemplos siguientes conservan todos los parámetros presentes, incluso vacíos y defaults. Son transcripciones completas: **10 nodos/9 cables** y **21 nodos/21 cables**, respectivamente (`Resources/Examples/Cylinder-Strip.jamgraph:1–86`; `Resources/Examples/TreeGen-Curve-Frames.jamgraph:1–460`).

```text
jam 1
x: series_range count="7" end="720.0" start="0.0"
y: graph_curve end_value="0.0" mid_value="240.0" midpoint="0.48" power="2.0" samples="7" shape="custom" start_value="0.0"
z: graph_curve end_value="180.0" mid_value="-80.0" midpoint="0.62" power="2.0" samples="7" shape="custom" start_value="0.0"
polyline: curve_polyline x="" y="" z=""
smooth: curve_smooth iterations="3" preserve_ends="true" samples="32" strength="0.45"
uniformar: curve_resample count="31" samples="32"
pipe: mesh_pipe capped="true" miter_limit="2.5" pivot_uvs="false" profile_rotation="0.0" radius_end="26.0" radius_from_parent="0.0" radius_start="26.0" samples="32" sides="12"
normals: mesh_normals angle_weighted="true" area_weighted="true"
hornear: mesh_to_static collision="true" folder="/Game/Jam/Meshes" name="SM_JamCylinderStrip" recompute_tangents="true" show_vertex_colors="true"
colocar: place align="false" anchor="base" scale="1.0" sink="0.0" surface="true" view="true" x="0.0" y="0.0" yaw="0.0" z="0.0"

x.out -> polyline.x
y.out -> polyline.y
z.out -> polyline.z
polyline.out -> smooth.in
smooth.out -> uniformar.in
uniformar.out -> pipe.in
pipe.out -> normals.in
normals.out -> hornear.in
hornear.out -> colocar.in

layout {
  x: (40, 40)
  y: (40, 290)
  z: (40, 540)
  polyline: (360, 290)
  smooth: (680, 290)
  uniformar: (1000, 290)
  pipe: (1320, 290)
  normals: (1640, 290)
  hornear: (1960, 290)
  colocar: (2280, 290)
}
```

```text
jam 1
curve: curve_bezier bend_x="80" bend_y="30" bend_z="0" end_x="40" end_y="0" end_z="600" segments="16" start_x="0" start_y="0" start_z="0"
frames: curve_frames angle_offset="0" count="12" end="0.95" radial_offset="18" radius_end="8" radius_start="55" samples="32" seed="1977" start="0.10" turns="2"
distribute: distribute_frames angle_jitter="6" angle_offset="0" count="18" end="0.92" parameter_jitter="0.02" rotate_per_index="137.5" seed="1977" start="0.15"
transform: transform_frames inherit_scale="true" offset_jitter_x="6" offset_jitter_y="4" offset_jitter_z="3" offset_x="0" offset_y="0" offset_z="12" pitch="8" pitch_jitter="5" roll="0" roll_jitter="12" scale="0.85" scale_jitter="0.12" seed="1977" yaw="0" yaw_jitter="8"
branches: branch_from_frames angle="62" angle_jitter="8" curl="28" curl_jitter="12" inherit_scale="true" length_max="300" length_min="180" seed="1977" segments="10"
trunk_profile: graph_curve end_value="0.24" mid_value="0.72" midpoint="0.58" power="2.0" samples="17" shape="custom" start_value="1.0"
trunk_pipe: mesh_pipe_profile capped="true" miter_limit="4" profile="" profile_rotation="0" radius="52" samples="24" sides="12"
branch_profile: graph_curve end_value="0.10" mid_value="0.65" midpoint="0.5" power="1.8" samples="13" shape="ease_in" start_value="1.0"
branch_pipe: mesh_pipe_profile capped="true" miter_limit="4" profile="" profile_rotation="0" radius="12" samples="12" sides="7"
merge: mesh_merge
color: mesh_color color="#76502F"
wood_uv: mesh_uv_scale channel="0" origin_u="0.0" origin_v="0.0" u="2.0" v="6.0"
wood_material: mesh_material material="/Engine/EngineDebugMaterials/VertexColorMaterial.VertexColorMaterial"
normals: mesh_normals angle_weighted="true" area_weighted="true"
tree_asset: mesh_to_static collision="true" folder="/Game/Jam/Meshes" name="TreeGen_FrameFlow_Test" recompute_tangents="true" show_vertex_colors="false"
preview: place align="false" anchor="base" asset="" scale="1" sink="0" surface="false" view="false" x="0" y="0" yaw="0" z="0"
frond_asset: asset name="PineFrond"
foliage: hism_output asset_offset_x="0" asset_offset_y="0" asset_offset_z="0" asset_pitch="0" asset_roll="0" asset_scale="1.0" asset_yaw="0" inherit_scale="true" name="TreeGen_Foliage"
leaf_card_asset: asset name="/Engine/BasicShapes/Plane.Plane"
foliage_set: asset_set
foliage_choose: choose_asset assets="" mode="random" seed="3107"

curve.out -> frames.in
frames.out -> distribute.in
distribute.out -> transform.in
transform.out -> branches.in
curve.out -> trunk_pipe.in
trunk_profile.out -> trunk_pipe.profile
branches.out -> branch_pipe.in
branch_profile.out -> branch_pipe.profile
trunk_pipe.out -> merge.in
branch_pipe.out -> merge.in
merge.out -> color.in
frond_asset.out -> foliage_set.in
leaf_card_asset.out -> foliage_set.in
transform.out -> foliage_choose.in
foliage_set.out -> foliage_choose.assets
foliage_choose.out -> foliage.in
color.out -> wood_uv.in
wood_uv.out -> wood_material.in
wood_material.out -> normals.in
normals.out -> tree_asset.in
tree_asset.out -> preview.in

layout {
  curve: (30, 40)
  frames: (350, 40)
  distribute: (680, 40)
  transform: (1010, 40)
  branches: (1340, 40)
  trunk_profile: (1010, 540)
  trunk_pipe: (1340, 540)
  branch_profile: (1340, 300)
  branch_pipe: (1670, 40)
  merge: (2000, 280)
  color: (2250, 280)
  wood_uv: (2500, 280)
  wood_material: (2750, 280)
  normals: (3000, 280)
  tree_asset: (3250, 280)
  preview: (3520, 280)
  frond_asset: (1010, 760)
  foliage: (1670, 900)
  leaf_card_asset: (680, 960)
  foliage_set: (1010, 900)
  foliage_choose: (1340, 900)
}
```

**Valores, funciones y nombres**

Ejemplo propio:

```text
jam 1
function pulir {
  entrada: input name="curva" type="S"
  suavizado: curve_smooth iterations=2
  salida: output name="curva" type="S"

  entrada.out -> suavizado.in
  suavizado.out -> salida.in
}

cantidad: number max=100 min=0 name="cantidad" value=12
despiece: matrix_decompose matriz=(10, 0, 0, 0, 0, 20, 0, 0, 0, 0, 30, 0, 0, 0, 0, 1)
linea: curve_line desde=(0, 0, 0)
suave: curve_smooth strength=0.4 @bypass
muestreo: curve_resample count=12 samples="=cantidad * 2"
acabado: fn:pulir

despiece.escala -> linea.hasta
linea.out -> suave.in
suave.out -> muestreo.in
cantidad.out -> muestreo.count
muestreo.out -> acabado.curva
```

`matrix_decompose.escala` existe (`math_core.py:1024–1043`); `curve_line` acepta vectores escritos o cableados (`tools.py:2228–2235`). Las funciones actuales derivan firmas de `input`/`output` y se expanden antes de ejecutar (`funcion.py:91–114,431–537`). El documento propuesto conserva la instancia y su definición; la expansión sólo pertenece al plan.

Las dependencias de funciones se incluyen como definiciones congeladas, con identidad persistente mediante `@id` cuando difiere del nombre. No se reemplaza silenciosamente una función por la versión más reciente de la biblioteca. Hoy las instancias pueden usar identidades estables distintas de sus etiquetas (`funcion.py:237–265,551–576`).

Vector: `(1, 2, 3)`; dominio: `(0, 1)`; matriz: tupla de dieciséis componentes por filas. El tipo del pin determina su interpretación. Se conserva la forma visual de tupla de `texto_de_valor`, **pero no su redondeo `.6g` ni “16 números”**, que perderían información (`math_core.py:1179–1206,202–222`). El impresor numérico usa precisión suficiente para recuperar exactamente el valor almacenado.

Una expresión sigue siendo una cadena `"=cantidad * 2"`. No se transforma en cables ni se sustituye por su resultado. Se mantiene también el contrato especial de `math.expr`, actualmente sin prefijo obligatorio (`math_core.py:1251–1259`). La tabla usa `params.name` o el identificador del nodo (`math_core.py:1399–1409`).

El canvas muestra el nombre documental como título. Al crear, propone un nombre desde `label`: `suavizar_curva`, `suavizar_curva_2`; lo persiste y nunca renumera otros nodos. Para IDs históricos opacos, usa un nombre visible y conserva el ID mediante `@id("n17")`. Las claves técnicas de pines se muestran junto a su etiqueta cuando difieren; no se traducen identificadores al guardar.

**Edición humana y errores**

Insertar un nodo entre `smooth` y `uniformar` agrega su declaración al final, reemplaza el cable existente y agrega otro:

```diff
+desplazar: curve_move desplazamiento=(0, 0, 100)
-smooth.out -> uniformar.in
+smooth.out -> desplazar.in
+desplazar.out -> uniformar.in
```

Su posición agrega una línea de layout. Cambiar `strength` modifica una línea; recablear modifica una arista. Ninguna acción exige ordenar topológicamente el documento.

El lector devuelve ubicaciones por nodo, parámetro y cable, siguiendo el precedente de `sintaxis.leer_con_mapa` de Oracle (`nucleo/sintaxis.py:1419–1425`). Ejemplos:

```text
Línea 8, columna 24: «cownt» no existe en curve_resample.
Usá «count»; controla la cantidad de puntos.

Línea 19: despiece.escala entrega Vector; muestreo.count espera Número.
Conectá una salida numérica o agregá una operación que extraiga una componente.

Línea 5: «nanite» no disponible en este motor: Godot.
Este descriptor requiere Nanite de Unreal. Conectá Unreal o reemplazá el nodo.
```

**Integración y núcleo neutro**

Propongo separar lectura, validación estructural y preparación para ejecución. Se puede guardar y observar un grafo incompleto o no disponible en el motor conectado; Run se bloquea con diagnóstico. El compilador conserva pines, comodín, cardinalidad, aridad, entradas obligatorias/opcionales y reglas de bypass existentes (`graph.py:266–286,405–464,503–558,584–589`). `@debug` representa el display flag existente; `@compact`, presentación.

`@asset("ruta")` representa el campo del nodo; `asset="..."` sigue siendo un parámetro almacenado. `fuente.out -> destino.asset` representa el pin, validado contra el descriptor. No se confunden esas tres cosas.

El registro neutro debe contener el **registro final**, incluidos verbos generados, Flow, valores y firmas, sin importar `tools`. Hoy `dsl.py:19` importa `tools`, `tools.py:10` importa Unreal, `graph.py:519` vuelve a importar `tools` incluso dentro de validación y `funcion.py:141` hace lo mismo. Extraer únicamente el diccionario inicial sería insuficiente: se amplía y completa en `tools.py:2933–3007`.

Cada descriptor declara tipos explícitos, defaults, opciones, etiquetas, pines, mínimos, efectos y capacidades:

```text
nanite.capacidades = {
  unreal: {estado: "implementado", requiere: ["nanite"]},
  godot:  {estado: "no_disponible", motivo: "requiere Nanite de Unreal"},
  unity:  {estado: "no_disponible", motivo: "sin implementación de este contrato"}
}
```

Son declaraciones propuestas, no una certificación de adaptadores existentes. La disponibilidad efectiva cruza descriptor y capacidades anunciadas por la conexión. Los cálculos puros declaran ejecución en núcleo. Un motor ausente no elimina verbos de la ayuda.

En texto, `detalle: nanite` permanece idéntico; el visor muestra el diagnóstico asociado a su línea. La disponibilidad no contamina el archivo con flags variables según la máquina. Ayuda y autocompletado salen del mismo registro e incluyen tipos, ejemplos de cables y motivos de indisponibilidad.

El núcleo mantiene descriptores serializables; operaciones puras y extractores de salidas viven en tablas de ejecución separadas. Esto contempla los actuales lambdas de `outs` y `corte_principal` (`graph.py:189–248`). El adaptador Unreal conserva ejecución, resolución de assets/selección, preview, inspección y objetos nativos. Se inyecta como interfaz; el núcleo nunca lo importa.

`api.run(texto)` pasa por un servicio documental: lee, publica la revisión en el canvas, prepara y ejecuta. Hoy sólo delega al panel (`api.py:66–68`). C++ recibe JSON validado, aplica una transacción Undo y muestra diagnósticos; no implementa otro parser. También debe conservar tipos y presencia de parámetros sin convertir todo a strings al guardar, como hace hoy (`SJamGraphEditor.cpp:4230–4237`).

La consola antigua permanece como **entrada de compatibilidad**, no segunda forma canónica. `scatter SM_Rock count=20` se expande a `asset` + `scatter` + `place`, con cables explícitos. Se materializan defaults de comando y el asset de sesión resuelto: hoy la consola compone precisamente puntos y colocación, y sus defaults difieren del Graph (`panel.py:909–927`; `tools.py:2008–2018`). `confirm`, `discard`, `search` siguen siendo acciones de sesión.

MCP usa el mismo servicio: `leer_grafo → texto+revisión`, `aplicar_texto(texto,revisión_base)`, `validar`, `ejecutar`. Una revisión desactualizada devuelve conflicto; nunca pisa una edición humana.

**Alcance y riesgos**

Estimo 2.500–4.000 líneas nuevas/modificadas de producción, más declaraciones trasladadas y 1.000–1.500 de pruebas: `grafo_documento.py`, `grafo_sintaxis.py`, `registro.py`, `capacidades.py`, `ejecucion.py`; refactor de `graph`, `flow`, `funcion`, `dsl`, API/panel y adaptación de Slate.

La aceptación exige importar y ejercer lector, impresor, ayuda y validación —también errores— con `sys.modules["unreal"]=None`; comprobar ambas leyes sobre todos los ejemplos; mutar orden variádico, precisión, flags y rutas para demostrar discriminación; finalmente verificar texto→canvas→edición→texto en el editor real.

Descarto una sintaxis de llamadas anidadas, `suavizar(tubo(curva(...)))`: es breve para árboles, pero compartir nodos, conservar valores locales cableados y representar variádicos obliga a introducir referencias y excepciones.

Los riesgos principales son la migración de identidades, las divergencias Graph/Flow y conservar tipos al pasar por widgets de texto. El costo deliberado es mayor longitud —especialmente en grafos históricos llenos de defaults— a cambio de no perder ninguna decisión editable. No modifiqué archivos ni ejecuté Unreal; esto es una propuesta de diseño basada en la lectura del árbol.