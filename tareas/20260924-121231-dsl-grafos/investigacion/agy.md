# Propuesta de Diseño: JamGraph DSL (Superficie Textual Canónica)

---

## 1. Definición Formal de «El Mismo Grafo» y Criterios de Equivalencia (Criterios 1, 7 y 8)

Para lograr una **ida y vuelta exacta** ($Texto \to Grafo \to Texto$ idempotente y $Grafo \to Texto \to Grafo$ isomórfico), la equivalencia entre dos instancias de [`JamGraph`](file:///home/workstation/Dev/jam/Content/Python/jam/graph.py#L68-L152) se define bajo el principio de **forma normal canónica**:

1. **Identidad topológica:** Mismo conjunto de identificadores de nodo semánticos. Las aristas son 4-tuplas exactas `(origen, origen_pin, destino, destino_pin)` ([graph.py:70-71](file:///home/workstation/Dev/jam/Content/Python/jam/graph.py#L70-L71)).
2. **Pines variádicos:** Para entradas con `aridad == -1` ([graph.py:462](file:///home/workstation/Dev/jam/Content/Python/jam/graph.py#L462), como `in` en `mesh_merge` o `weight_combine`), **el orden de las aristas entrantes importa** y se preserva estrictamente como lista de cables. En pines escalares con aridad 1, el orden de llegada no altera el resultado.
3. **Parámetros vs. Defaults:** 
   - En el DSL canónico, **todo parámetro igual a su valor por defecto declarado en el registro se omite** (garantizando diffs mínimos y economía de tokens).
   - Dos grafos son idénticos si, tras rellenar los parámetros ausentes con los defaults del registro neutro, los diccionarios de parámetros resueltos son iguales.
   - Si un parámetro recibe un cable aguas arriba ([graph.py:489](file:///home/workstation/Dev/jam/Content/Python/jam/graph.py#L489)), el valor escalar previo en `params` queda eclipsado y en el DSL se emite únicamente la conexión.
4. **Coerción y tipos ricos:** Se unifica la representación textual con [`math_core.texto_de_valor`](file:///home/workstation/Dev/jam/Content/Python/jam/math_core.py#L1179-L1208):
   - Flotantes: formato `.6g` (elimina ruido binario como `0.30000000000000004` sin truncar distancias reales en cm).
   - Booleanos: `true` / `false` en minúsculas.
   - Vectores (`V`): `(x, y, z)` ([math_core.py:140](file:///home/workstation/Dev/jam/Content/Python/jam/math_core.py#L140)).
   - Dominios (`D`): `(min, max)` ([math_core.py:454](file:///home/workstation/Dev/jam/Content/Python/jam/math_core.py#L454)).
   - Matrices (`MX`): `[m0, m1, ..., m15]`.
   - Cadenas/Rutas: texto directo si no contiene espacios; entrecomillado `"..."` si incluye espacios o caracteres especiales.
5. **Separación de Layout (Criterio 7):** El layout (`x`, `y`, `reroutes`, `comments` de [SJamGraphEditor.cpp:4216-4337](file:///home/workstation/Dev/jam/Source/JamEditor/Private/SJamGraphEditor.cpp#L4216-L4337)) **vive al pie del archivo en una sección dedicada `layout:`**. Si un LLM omite esta sección, el grafo compila perfectamente y el editor aplica el algoritmo determinista de [`layout.acomodar`](file:///home/workstation/Dev/jam/Content/Python/jam/layout.py#L162-L230). Si el texto contiene `layout:`, las posiciones y comentarios se restauran pixel por pixel.

---

## a. La Gramática (EBNF)

```ebnf
Documento      ::= ( Declaracion )* [ BloqueLayout ]
Declaracion    ::= DeclaracionNodo | ComandoConsola

DeclaracionNodo ::= Identificador ":" Verbo [ AssetRef ] ( Flag )* EOL ( Indent EntradaNodo EOL )*
ComandoConsola ::= Verbo [ AssetRef ] ( AsignacionParam )* EOL

Verbo          ::= Identificador | PrefijoFuncion Identificador
PrefijoFuncion ::= "fn:"
AssetRef       ::= CadenaOIdent
Flag           ::= "@bypass" | "@debug" | "@compact"

EntradaNodo    ::= PinIn | AsignacionParam
PinIn          ::= "in" "=" ( Conector | "[" Conector ( "," Conector )* "]" )
AsignacionParam::= Identificador "=" ( Expresion | Conector | Literal )

Conector       ::= Identificador [ "." Identificador ]
Expresion      ::= "=" CaracteresHastaFinLinea
Literal        ::= Booleano | Numero | Vector | Dominio | Matriz | ColorHex | Cadena

Vector         ::= "(" Numero "," Numero "," Numero ")"
Dominio        ::= "(" Numero "," Numero ")"
Matriz         ::= "[" Numero ( "," Numero ){15} "]"
ColorHex       ::= "#" HexHexHexHexHexHex
Booleano       ::= "true" | "false"
Numero         ::= ["-"] [0-9]+ ["." [0-9]+] [ ("e"|"E") ["+"|"-"] [0-9]+ ]

BloqueLayout   ::= "layout:" EOL ( Indent LineaLayout EOL )*
LineaLayout    ::= PosicionNodo | ComentarioBox | RerouteWire
PosicionNodo   ::= Identificador Numero "," Numero
ComentarioBox  ::= "comment" Identificador Cadena Numero "," Numero "," Numero "," Numero [ ColorHex ]
RerouteWire    ::= "reroute" Identificador "." Identificador "->" Identificador "." Identificador ( Numero "," Numero )+
```

---

## b. Ejemplos Reales Transcritos Enteros

### 1. `Resources/Examples/Cylinder-Strip.jamgraph`

```jam
x: series_range
    start = 0.0
    end = 720.0
    count = 7

y: graph_curve
    start_value = 0.0
    end_value = 0.0
    shape = custom
    power = 2.0
    midpoint = 0.48
    mid_value = 240.0
    samples = 7

z: graph_curve
    start_value = 0.0
    end_value = 180.0
    shape = custom
    power = 2.0
    midpoint = 0.62
    mid_value = -80.0
    samples = 7

polyline: curve_polyline
    x = x
    y = y
    z = z

smooth: curve_smooth
    in = polyline
    iterations = 3
    strength = 0.45
    preserve_ends = true
    samples = 32

uniformar: curve_resample
    in = smooth
    count = 31
    samples = 32

pipe: mesh_pipe
    in = uniformar
    radius_start = 26.0
    radius_end = 26.0
    sides = 12
    samples = 32
    capped = true
    profile_rotation = 0.0
    miter_limit = 2.5
    radius_from_parent = 0.0
    pivot_uvs = false

normals: mesh_normals
    in = pipe
    angle_weighted = true
    area_weighted = true

hornear: mesh_to_static
    in = normals
    name = SM_JamCylinderStrip
    folder = /Game/Jam/Meshes
    collision = true
    recompute_tangents = true
    show_vertex_colors = true

colocar: place
    in = hornear
    x = 0.0
    y = 0.0
    z = 0.0
    view = true
    surface = true
    anchor = base
    sink = 0.0
    align = false
    yaw = 0.0
    scale = 1.0

layout:
    x 40, 40
    y 40, 290
    z 40, 540
    polyline 360, 290
    smooth 680, 290
    uniformar 1000, 290
    pipe 1320, 290
    normals 1640, 290
    hornear 1960, 290
    colocar 2280, 290
```

---

### 2. `Resources/Examples/TreeGen-Curve-Frames.jamgraph`

```jam
curve: curve_bezier
    start_x = 0.0
    start_y = 0.0
    start_z = 0.0
    end_x = 40.0
    end_y = 0.0
    end_z = 600.0
    bend_x = 80.0
    bend_y = 30.0
    bend_z = 0.0
    segments = 16

frames: curve_frames
    in = curve
    count = 12
    start = 0.1
    end = 0.95
    radial_offset = 18.0
    turns = 2.0
    angle_offset = 0.0
    radius_start = 55.0
    radius_end = 8.0
    samples = 32
    seed = 1977

distribute: distribute_frames
    in = frames
    count = 18
    start = 0.15
    end = 0.92
    rotate_per_index = 137.5
    angle_offset = 0.0
    angle_jitter = 6.0
    parameter_jitter = 0.02
    seed = 1977

transform: transform_frames
    in = distribute
    offset_x = 0.0
    offset_y = 0.0
    offset_z = 12.0
    pitch = 8.0
    yaw = 0.0
    roll = 0.0
    scale = 0.85
    offset_jitter_x = 6.0
    offset_jitter_y = 4.0
    offset_jitter_z = 3.0
    pitch_jitter = 5.0
    yaw_jitter = 8.0
    roll_jitter = 12.0
    scale_jitter = 0.12
    inherit_scale = true
    seed = 1977

branches: branch_from_frames
    in = transform
    length_min = 180.0
    length_max = 300.0
    angle = 62.0
    angle_jitter = 8.0
    curl = 28.0
    curl_jitter = 12.0
    segments = 10
    inherit_scale = true
    seed = 1977

trunk_profile: graph_curve
    start_value = 1.0
    end_value = 0.24
    shape = custom
    power = 2.0
    midpoint = 0.58
    mid_value = 0.72
    samples = 17

trunk_pipe: mesh_pipe_profile
    in = curve
    profile = trunk_profile
    radius = 52.0
    sides = 12
    samples = 24
    capped = true
    profile_rotation = 0.0
    miter_limit = 4.0

branch_profile: graph_curve
    start_value = 1.0
    end_value = 0.1
    shape = ease_in
    power = 1.8
    midpoint = 0.5
    mid_value = 0.65
    samples = 13

branch_pipe: mesh_pipe_profile
    in = branches
    profile = branch_profile
    radius = 12.0
    sides = 7
    samples = 12
    capped = true
    profile_rotation = 0.0
    miter_limit = 4.0

merge: mesh_merge
    in = [trunk_pipe, branch_pipe]

color: mesh_color
    in = merge
    color = #76502F

wood_uv: mesh_uv_scale
    in = color
    u = 2.0
    v = 6.0
    channel = 0
    origin_u = 0.0
    origin_v = 0.0

wood_material: mesh_material
    in = wood_uv
    material = /Engine/EngineDebugMaterials/VertexColorMaterial.VertexColorMaterial

normals: mesh_normals
    in = wood_material
    angle_weighted = true
    area_weighted = true

tree_asset: mesh_to_static
    in = normals
    name = TreeGen_FrameFlow_Test
    folder = /Game/Jam/Meshes
    collision = true
    recompute_tangents = true
    show_vertex_colors = false

preview: place
    in = tree_asset
    x = 0.0
    y = 0.0
    z = 0.0
    view = false
    surface = false
    anchor = base
    sink = 0.0
    align = false
    yaw = 0.0
    scale = 1.0

frond_asset: asset PineFrond

leaf_card_asset: asset /Engine/BasicShapes/Plane.Plane

foliage_set: asset_set
    in = [frond_asset, leaf_card_asset]

foliage_choose: choose_asset
    in = transform
    assets = foliage_set
    mode = random
    seed = 3107

foliage: hism_output
    in = foliage_choose
    name = TreeGen_Foliage
    asset_offset_x = 0.0
    asset_offset_y = 0.0
    asset_offset_z = 0.0
    asset_pitch = 0.0
    asset_yaw = 0.0
    asset_roll = 0.0
    asset_scale = 1.0
    inherit_scale = true

layout:
    curve 30, 40
    frames 350, 40
    distribute 680, 40
    transform 1010, 40
    branches 1340, 40
    trunk_profile 1010, 540
    trunk_pipe 1340, 540
    branch_profile 1340, 300
    branch_pipe 1670, 40
    merge 2000, 280
    color 2250, 280
    wood_uv 2500, 280
    wood_material 2750, 280
    normals 3000, 280
    tree_asset 3250, 280
    preview 3520, 280
    frond_asset 1010, 760
    foliage 1670, 900
    leaf_card_asset 680, 960
    foliage_set 1010, 900
    foliage_choose 1340, 900
```

---

## c. Ejemplo Propio Completo

Este ejemplo demuestra:
1. Multi-salida con [`matrix_decompose`](file:///home/workstation/Dev/jam/Content/Python/jam/math_core.py#L1025-L1044) conectando la salida extra `eje_z` a un pin de datos.
2. Nodo de valor (`number`) cableado a un parámetro.
3. Expresión `=...` evaluada contra la tabla de variables.
4. Instancia de función con prefijo `fn:`.
5. Nodo con flag `@bypass` ([graph.py:503-513](file:///home/workstation/Dev/jam/Content/Python/jam/graph.py#L503-L513)).

```jam
base_trans: number
    value = 120.0
    min = 0.0
    max = 500.0

trans_matrix: matrix_from_trs
    translation = (0.0, 0.0, 100.0)
    rotation = (0.0, 45.0, 0.0)
    scale = (1.0, 1.0, 2.0)

decomp: matrix_decompose
    matriz = trans_matrix

generador_eje: fn:generar_cilindro_orientado
    direccion = decomp.eje_z
    altura = base_trans
    radio = =base_trans * 0.25

filtro_suavizado: mesh_relax @bypass
    in = generador_eje
    iterations = 5

salida_malla: mesh_normals
    in = filtro_suavizado
    angle_weighted = true
```

---

## d. Reglas del Impresor Canónico

El impresor canónico garantiza que cualquier representación de grafo en memoria se serialice a una única cadena idéntica byte a byte (`gofmt` style):

1. **Orden de Nodos:** 
   - Se ordenan por **orden topológico** (algoritmo Kahn de [`JamGraph.topo_order`](file:///home/workstation/Dev/jam/Content/Python/jam/graph.py#L92-L111)).
   - En caso de nodos hermanos independientes en la misma capa topológica, el desempate es estrictamente **alfabético por identificador de nodo**.
2. **Encabezado de Nodo:**
   - Sintaxis: `<id>: <verb>[ <asset>][ @flag1][ @flag2]`.
   - Si `asset` es nulo o vacío, no se imprime.
   - Flags en orden fijo: `@bypass`, `@debug`, `@compact`.
3. **Cuerpo del Nodo (orden de propiedades):**
   - Indentación estándar: exactamente 4 espacios.
   - Si el nodo tiene cable(s) en `in`, la línea `in = ...` se imprime **siempre en primer lugar**. Para aridad múltiple se imprime lista `in = [nodo1, nodo2]`.
   - Los parámetros restantes se emiten en el orden exacto en que están declarados en `params` de la metadata del registro neutro.
4. **Omisiones:**
   - Parámetros que coinciden en tipo y valor con su default declarado en el registro neutro **se omiten por completo**.
   - Parámetros que reciben conexión por cable se imprimen con el origen del cable: `param = nodo_origen.pin` (o `param = nodo_origen` si es `out`).
   - El parámetro `name` en nodos de valor (`number`, `text`, `boolean`) se omite si coincide con el propio `id` del nodo ([graph.py:477](file:///home/workstation/Dev/jam/Content/Python/jam/graph.py#L477)).
5. **Sección Layout:**
   - Se imprime al final si existen nodos con coordenadas.
   - Nodos ordenados alfabéticamente: `<id> <x>, <y>`.
   - Comentarios ordenados alfabéticamente: `comment <id> "<title>" <x>, <y>, <w>, <h> <#color>`.
   - Reroutes ordenados por la arista correspondiente.

---

## e. Edición Típica del Humano en el Canvas (Slate C++) y su Diff Limpio

### Caso de uso:
El usuario abre `Cylinder-Strip` en el editor visual. Inserta un nodo `mesh_relax` entre `pipe` y `normals`, ajusta `radius_start` de `pipe` de 26 a 32, y conecta el radio mediante el slider de la interfaz.

### Diff resultante en el DSL:

```diff
 pipe: mesh_pipe
     in = uniformar
-    radius_start = 26.0
+    radius_start = 32.0
     radius_end = 26.0
     sides = 12
     samples = 32
     capped = true
     profile_rotation = 0.0
     miter_limit = 2.5
     radius_from_parent = 0.0
     pivot_uvs = false
 
+relax: mesh_relax
+    in = pipe
+    iterations = 2
+
 normals: mesh_normals
-    in = pipe
+    in = relax
     angle_weighted = true
     area_weighted = true
 
 layout:
     ...
     pipe 1320, 290
+    relax 1480, 290
     normals 1640, 290
```
> **Observación:** El diff es estrictamente local (Criterio 5). No hay renumeración de IDs (`n1` $\to$ `n2`), no se desordenan las demás herramientas y la alteración de un parámetro ocupa exactamente una línea.

---

## f. Tres Mensajes de Error de Ejemplo con Línea

Siguiendo el estándar de [`ErrorSintaxis`](file:///home/workstation/Dev/jam/vendor/oracle-pkg/oracle_metalenguaje/nucleo/sintaxis.py#L56-L76):

### 1. Incompatibilidad de tipos en un cable
```text
línea 14, columna 5: el pin «in» de «pipe» espera una curva (S); recibió una malla dinámica (M) desde «normals.out»
  -> sugerencia: conectá «pipe.in» a la salida de un generador o filtro de curvas («curve_*»).
```

### 2. Verbo no disponible en el motor activo (Criterio 11)
```text
línea 22, columna 9: verbo «fracture» no disponible en motor «godot» (motor activo)
  -> motivo: Chaos Destruction solo está implementado en el adaptador «unreal».
  -> sugerencia: ejecutá este grafo con el backend de Unreal Engine o reemplazá por un operador de corte booleano.
```

### 3. Expresión que no resuelve por variable no declarada
```text
línea 8, columna 12: expresión sin resolver en parámetro «radio»: «=radioo * 1.5» — la variable «radioo» no existe en el grafo
  -> sugerencia: ¿quisiste decir «radio»? Variables disponibles: [«radio», «altura», «base_trans»].
```

---

## g. Integración y Arquitectura del Registro Neutro (Criterio 11)

### 1. Desacoplamiento del Núcleo vs. Adaptadores

```
              ┌────────────────────────────────────────────────────────┐
              │                NÚCLEO PURO (Sin Unreal)                │
              │  - jam/registro_neutro.py (catálogo declarativo puro)  │
              │  - jam/dsl_graph.py       (lexer, parser, impresor)    │
              │  - jam/graph.py           (JamGraph, compilar puro)    │
              │  - jam/math_core.py       (evaluador matemático puro)  │
              │  - jam/layout.py          (autolayout Sugiyama puro)   │
              └───────────────────────────┬────────────────────────────┘
                                          │ Protocolo JSON / Objetos DAG
                ┌─────────────────────────┼─────────────────────────┐
                ▼                         ▼                         ▼
   ┌─────────────────────────┐ ┌────────────────────┐ ┌─────────────────────────┐
   │    ADAPTADOR UNREAL     │ │  ADAPTADOR GODOT   │ │     CLIENTES Y MCP      │
   │ - jam/adapter_unreal/   │ │ - godot_plugin/    │ │ - jam-mcp (stdio)       │
   │ - tools.py (enlaza "fn")│ │ - ejecuta nativo   │ │ - Slate (C++ Editor)    │
   │ - spawn_actor, uobjects │ │   (ArrayMesh)      │ │ - Web UI (FastAPI)      │
   └─────────────────────────┘ └────────────────────┘ └─────────────────────────┘
```

- **`jam/registro_neutro.py`**: Nuevo módulo en el núcleo que contiene toda la estructura declarativa de [`tools.REGISTRO`](file:///home/workstation/Dev/jam/Content/Python/jam/tools.py#L1992-L2060) **sin el campo `"fn"`** y **sin `import unreal`**.
- Cada entrada define capacidades por motor:
  ```python
  "mesh_extrude": {
      "cat": "Mesh", "in_name": "M", "out_name": "M",
      "params": {"distance": 100.0, "direction": "0,0,1"},
      "motores": {
          "unreal": {"estado": "disponible"},
          "godot":  {"estado": "disponible", "via": "SurfaceTool"},
          "unity":  {"estado": "no_disponible", "motivo": "requiere paquete Splines/Mesh"}
      },
      "doc": "extruye las caras a lo largo de un vector"
  }
  ```
- **Comprobación estricta de pureza:** El núcleo se verifica en CI mediante:
  ```python
  sys.modules["unreal"] = None
  import jam.registro_neutro, jam.dsl_graph, jam.graph, jam.math_core
  ```

### 2. Integración con `api.run` y Consola de Una Línea (Criterio 6)
- [`api.run(comando)`](file:///home/workstation/Dev/jam/Content/Python/jam/api.py#L66-L68) evalúa la entrada:
  1. Si contiene saltos de línea o el patrón `^[a-zA-Z0-9_]+:`, se despacha a `dsl_graph.parsear(comando)` $\to$ compila a `JamGraph` $\to$ materializa en el canvas y ejecuta.
  2. Si es una línea única plana (`scatter SM_Rock count=20`), el parser genera un nodo efímero con ID autogenerado y mantiene el comportamiento interactivo histórico de consola (encadenando `t_place` automático si `necesita_instanciar`).

### 3. Integración con Slate C++
- Slate no requiere un parser de EBNF en C++. Mantiene su contrato JSON probado ([SJamGraphEditor.cpp:4216-4337](file:///home/workstation/Dev/jam/Source/JamEditor/Private/SJamGraphEditor.cpp#L4216-L4337)):
  - Al presionar **Exportar DSL / Copiar como texto**: C++ envía el JSON de `BuildJson()` a Python $\to$ `jam.dsl_graph.grafo_a_dsl(g)` $\to$ texto al portapapeles.
  - Al presionar **Importar DSL / Pegar texto**: C++ envía el texto a Python $\to$ `jam.dsl_graph.dsl_a_grafo(texto).to_json()` $\to$ C++ recibe el JSON y ejecuta [`LoadGraphJson()`](file:///home/workstation/Dev/jam/Source/JamEditor/Private/SJamGraphEditor.cpp#L5110-L5250).

### 4. Servidor `jam-mcp`
- Expone dos herramientas fundamentales para LLMs:
  - `get_active_graph() -> str`: Devuelve el grafo en canvas formateado en el DSL canónico.
  - `set_active_graph(dsl_text: str) -> dict`: Parsea el DSL, valida tipos/ciclos en preflight y actualiza el grafo visual en Slate y el runtime. Si hay errores, devuelve diagnósticos estructurados con línea y columna sin alterar el canvas.

---

## h. Alternativa Descartada y Análisis de Riesgos

### 1. La Mejor Alternativa Descartada: Sintaxis de Tuberías Lineales (Pipeline DSL)
- **Forma evaluada:** `curve_bezier | curve_frames count=12 | distribute_frames | branches` con bifurcaciones mediante variables `var_a = curve | trunk_pipe; (var_a, branches) | mesh_merge`.
- **Por qué se descartó:**
  1. Jam no es un pipeline UNIX lineal; es un **DAG ramificado con topologías complejas** (en `TreeGen`, la curva alimenta simultáneamente a `frames` y a `trunk_pipe`; `merge` combina dos ramas de mallas; `choose_asset` recibe de `transform` y de `foliage_set`).
  2. Forzar tuberías (`|`) introduce sintaxis auxiliar críptica para bifurcaciones y uniones, obligando al LLM a gestionar paréntesis, tuplas intermedias y bifurcadores no deterministas.
  3. La sintaxis declarativa basada en nodos y pines destino (`in = [a, b]`, `param = nodo.pin`) modela de forma isomórfica el dataflow real de Houdini/Grasshopper y Slate.

### 2. Riesgos de la Propuesta y Mitigaciones

| Riesgo Identificado | Causa Raíz | Estrategia de Mitigación |
|---|---|---|
| **Colisión de Identificadores** | Un usuario llama a un nodo igual que a un verbo o una variable (`curve: curve` o `x: x`). | La gramática separa sintácticamente la posición del identificador (`id:`) de la del verbo. Si hay variable matemática duplicada, [`compilar`](file:///home/workstation/Dev/jam/Content/Python/jam/graph.py#L478-L482) reporta duplicación antes de ejecutar. |
| **Desincronización de Layout** | El usuario edita la lógica por texto y no actualiza las coordenadas de `layout:`. | El bloque `layout:` es puramente opcional. Si un nodo no figura en `layout:`, [`layout.acomodar`](file:///home/workstation/Dev/jam/Content/Python/jam/layout.py#L162-L230) calcula su posición automática respetando la grilla. |
| **Divergencia entre Registro Neutro y Motor** | Un verbo declara params que el adaptador de un motor no soporta. | Medidas de oráculo automatizadas (`oracle-aceptacion` y `oracle-diferencial`) que comprueban por motor el contrato de cada verbo del registro neutro. |

---

## 9. Estimación de Implementación en Código Puro (Criterio 9)

- `Content/Python/jam/registro_neutro.py` (nuevo): ~450 líneas (extrayendo metadata pura de `tools.py`).
- `Content/Python/jam/dsl_graph.py` (nuevo: lexer, parser recursivo descendente, impresor canónico): ~650 líneas.
- `Content/Python/jam/graph.py` (adaptación menor para consumir `registro_neutro`): ~40 líneas modificadas.
- `Content/Python/tests/test_dsl_graph.py` (suite de tests de ida y vuelta exhaustiva): ~500 líneas.
- **Total estimado:** ~1640 líneas de Python puro (0 `import unreal`), manteniendo la suite de tests en tiempos inferiores a 1 segundo.
