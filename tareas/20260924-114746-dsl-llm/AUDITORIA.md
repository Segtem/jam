# Auditoría Técnica: Brecha DSL ↔ Nodos para Creación por LLM

**Tarea:** `20260924-114746-dsl-llm`  
**Fecha:** 2026-09-24  
**Contexto:** Integración de Commander (`~/Dev/commander`) con Jam como superficie de creación híbrida LLM ↔ Humano.  
**Regla de rigor:** Toda afirmación respaldada con cita exacta `archivo:línea` inspeccionada en este turno. Cero supuestos no leídos.

---

## 1. Resumen Ejecutivo y Diagnóstico Estructural

El objetivo de Commander es que **un LLM cree mediante el DSL y un humano pueda seguir, observar y modificar esa creación en la interfaz de nodos de Slate, y viceversa**, operando ambos sobre el mismo grafo con un vocabulario idéntico y diagnósticos legibles.

La auditoría del código revela una **fractura arquitectónica fundamental**:

1. **El DSL actual es un invocador plano de comandos de un solo paso:** `dsl.parsear` ([dsl.py:25-46](../../Content/Python/jam/dsl.py#L25-L46)) solo admite líneas aisladas de la forma `verbo [asset] [clave=valor ...]`. No tiene concepto de grafo, tubería (`|`), encadenamiento ni asignación de variables.
2. **Cero ida y vuelta (Round-trip inexistente):**
   - No existe compilador DSL → Grafo. Ejecutar un comando DSL corre directamente la función de Python en runtime ([panel.py:873](../../Content/Python/jam/panel.py#L873), [panel.py:905](../../Content/Python/jam/panel.py#L905)), sin crear nodos ni aristas en `JamGraph`.
   - No existe descompilador Grafo → DSL. `JamGraph` únicamente serializa y deserializa a un diccionario JSON crudo con IDs técnicos (`n1`, `n2`) y tuplas de aristas ([graph.py:115-117](../../Content/Python/jam/graph.py#L115-L117), [graph.py:130-155](../../Content/Python/jam/graph.py#L130-L155)).
3. **86 de las herramientas de Jam son inaccesibles por el DSL:** Por diseño de seguridad de consola, `registro_core.cable_que_falta` ([registro_core.py:47-69](../../Content/Python/jam/registro_core.py#L47-L69)) y `dsl.ayuda` ([dsl.py:85-93](../../Content/Python/jam/dsl.py#L85-L93)) bloquean todo verbo que exija un cable (`min_inputs >= 1`).
4. **Coerción destructiva de parámetros:** `dsl.coaccionar` ([dsl.py:49-70](../../Content/Python/jam/dsl.py#L49-L70)) solo entiende `bool`, `int`, `float` o texto plano; tipos ricos como vectores (`V`), dominios (`D`) o matrices (`MX`) no tienen soporte y parámetros no reconocidos se descartan en silencio en rutas de ejecución ([graph.py:825](../../Content/Python/jam/graph.py#L825)).

---

## 2. Cobertura de Verbos y Operaciones (DSL vs. Graph vs. Slate)

### 2.1 La partición del registro por cables
El registro general de herramientas en [tools.py](../../Content/Python/jam/tools.py) contiene 186 herramientas ([RELEVO.md:1418](../../RELEVO.md#L1418)). Sin embargo:
- **Corren en consola:** ~80 verbos ([registro_core.py:71-74](../../Content/Python/jam/registro_core.py#L71-L74), [RELEVO.md:1381](../../RELEVO.md#L1381)).
- **Excluidos del DSL:** 86 verbos declarados en `tools.REGISTRO` que exigen un cable de entrada (`min_inputs >= 1` con tipo distinto de `""` y `"A"`). Al tipearlos, `panel.ejecutar_dsl` los rechaza explícitamente ([panel.py:879-883](../../Content/Python/jam/panel.py#L879-L883)).

### 2.2 Familias completas de Jam inaccesibles para el LLM vía DSL
Al no tener sintaxis para conectar la salida de un verbo con la entrada de otro, el LLM tiene vedadas las siguientes familias:

| Familia de Verbos | Tipo de Entrada Requerida | Verbos Afectados (ejemplos en [tools.py:2771-2801](../../Content/Python/jam/tools.py#L2771-L2801)) |
|---|---|---|
| **Modelado Procedural de Mallas** | `M` (DynamicMesh) | `mesh_transform`, `mesh_extrude`, `mesh_merge`, `mesh_weld`, `mesh_normals`, `mesh_simplify_count`, `mesh_simplify_tolerance`, `mesh_simplify_edge_length`, `mesh_uv_box`, `mesh_uv_unwrap`, `mesh_uv_pack`, `mesh_color`, `mesh_material` |
| **Curvas y Splines Procedurales** | `S` (Curva) | `curve_child`, `curve_noise`, `curve_frames`, `curve_move`, `curve_resample`, `curve_smooth`, `curve_fuse_collinear`, `curve_subdivide`, `curve_offset`, `curve_branches`, `mesh_along_curve`, `mesh_ribbon`, `mesh_pipe`, `mesh_loft`, `mesh_revolve` |
| **Instanciación y Frames** | `F` / `AF` (Frames) | `distribute_frames`, `transform_frames`, `branch_from_frames`, `choose_asset`, `copy_mesh_to_frames`, `copy_asset_selection`, `hism_output` |
| **Materiales / Shaders Procedurales** | `MT` (Grafo Material) | `material_node`, `material_connect`, `material_output`, `material_build`, `material_function`, `material_call` |
| **Mass Gameplay y Entidades** | `F`, `MS`, `MH` | `mass_probe`, `mass_spec`, `mass_spawn`, `mass_inspect`, `mass_clear` |
| **Operaciones de Stream Flow** | `P` (Puntos) | Todo el motor de `flow.py` ([flow.py:41-115](../../Content/Python/jam/flow.py#L41-L115)): máscaras (`mask_slope`, `mask_height`, `mask_noise`, `mask_density`), pesos escalares (`weight_slope`, `weight_height`, `weight_noise`, `weight_combine`, `weight_cull`), sets (`cull_nth`, `sub_list`, `shift`, `relax`), transformaciones de puntos (`move`, `scale_pts`, `rotate_pts`, `jitter`) |

### 2.3 Acoplamiento oculto e imperativo en la consola
Para permitir que un usuario humano tipee `scatter SM_Rock count=20` en la consola y aparezcan piedras en el nivel, `panel.ejecutar_dsl` aplica un truco ad-hoc:
- Si `tools.necesita_instanciar(verbo)` es `True` ([tools.py:433-439](../../Content/Python/jam/tools.py#L433-L439), cuando `out_name == "P"`), la consola ejecuta la función del verbo y acto seguido le encadena de forma oculta un `tools.t_place` ([panel.py:897-916](../../Content/Python/jam/panel.py#L897-L916)).
- En el Graph, esta composición es explícita mediante nodos y cables (`scatter` → cable de puntos → `instance`). El DSL carece de una forma para que el LLM decida si quiere instanciar o transferir los puntos a otro modificador.

---

## 3. Ida y Vuelta: DSL ↔ Nodos (Round-Trip)

### 3.1 Vía de ida: DSL → Nodos (Inexistente)
- El punto de entrada público para comandos DSL es `api.run(command)` ([api.py:66-68](../../Content/Python/jam/api.py#L66-L68)), que llama a `panel.ejecutar_dsl` ([panel.py:824-921](../../Content/Python/jam/panel.py#L824-L921)).
- Este camino **no interactúa en absoluto con `JamGraph` ni con el canvas de Slate**.
- Si el LLM escribe comandos DSL, en el canvas de nodos no aparece nada. Para crear nodos en el canvas, la única vía expuesta hoy es enviar un JSON crudo estructurado a `api.run_graph(json)` ([api.py:71-74](../../Content/Python/jam/api.py#L71-L74)) o manipular directamente las estructuras de `JamGraph.from_json` ([graph.py:130-155](../../Content/Python/jam/graph.py#L130-L155)).

### 3.2 Vía de vuelta: Grafo / Nodos → DSL (Inexistente)
- No existe ninguna función en todo el codebase que tome un `JamGraph` o un `Flow` y emita código DSL legible.
- La serialización del grafo es únicamente `JamGraph.to_json()` ([graph.py:115-117](../../Content/Python/jam/graph.py#L115-L117)):
  ```json
  {"nodes": {"n1": {"verb": "mesh_box", ...}, "n2": {"verb": "mesh_transform", ...}}, "edges": [["n1", "out", "n2", "in"]]}
  ```
- Si un humano edita el grafo en el viewport de Slate (añade un nodo, reconecta un cable, altera un parámetro), el LLM no tiene forma de leer el estado resultante en una representación textual DSL de alto nivel.

### 3.3 Disparidad de Identidad: Nombres y Etiquetas vs. IDs Técnicos
- **Pines:** En Slate C++, `FJamNodePin` ([SJamGraphNode.h:44-50](../../Source/JamEditor/Public/SJamGraphNode.h#L44-L50)) carece del campo `Label`. En [SJamGraphNode.cpp:555-564](../../Source/JamEditor/Private/SJamGraphNode.cpp#L555-L564), Slate dibuja `*InPin.Name` y `*OutPin.Name`. En nodos con multi-salida como `matrix_decompose` ([RELEVO.md:800-808](../../RELEVO.md#L800-L808)), el usuario ve `out (vector)` en vez de `traslación`, y `eje_x` en lugar de `eje X`.
- **Nodos:** Salvo los nodos de valor matemático que aceptan `params["name"]` ([flow.py:1025-1026](../../Content/Python/jam/flow.py#L1025-L1026)), los nodos del grafo carecen de identificador semántico legible ("malla_base", "filtro_pendiente"); se manejan por claves como `"n1"`, `"n2"`.

---

## 4. Manejo y Reporte de Errores para Modelos de Lenguaje

Para que un LLM trabaje de forma autónoma con un oráculo de verificación, el reporte de errores debe ser **determinista, estructurado y accionante (diciendo qué falló, por qué y cómo corregirlo)**. La auditoría muestra deficiencias críticas:

### 4.1 Descarte silencioso y rigidez en `dsl.coaccionar`
- `dsl.coaccionar(verbo, params)` ([dsl.py:49-70](../../Content/Python/jam/dsl.py#L49-L70)) busca el tipo de cada valor basándose exclusivamente en el tipo del valor por defecto en `tools.REGISTRO[verbo]["params"]`:
  - `bool` evalúa cadenas como `"true"`, `"si"`, etc. ([dsl.py:60-61](../../Content/Python/jam/dsl.py#L60-L61)).
  - `int` convierte con `int(float(v))` ([dsl.py:62-63](../../Content/Python/jam/dsl.py#L62-L63)).
  - `float` convierte con `float(v)` ([dsl.py:64-65](../../Content/Python/jam/dsl.py#L64-L65)).
  - Cualquier otro tipo queda como string crudo `out[k] = v` ([dsl.py:66-67](../../Content/Python/jam/dsl.py#L66-L67)).
- **Descarte silencioso de parámetros:**
  - Si el LLM pasa un parámetro no registrado en `params`, va a la lista `desconocidos` ([dsl.py:56](../../Content/Python/jam/dsl.py#L56)).
  - En `graph.py:825`: `kw, _desc = dsl.coaccionar(verb, ...)`. La variable `_desc` es **descartada sin advertencia ni error**. Si el LLM tipea un parámetro con un error tipográfico (`cownt=10`), el grafo compila y corre en verde con el valor por defecto sin avisar del fallo.
  - En `panel.py:918-919`: en comandos de consola solo se añade un texto al final `(ignoré params desconocidos: ...)`, sin detener la ejecución errónea.
- **Sin validación de dominios de opciones:** `tools.REGISTRO` declara opciones válidas en `info["opciones"]` (ej. `pattern`: `["poisson", "grid", ...]` en [flow.py:49](../../Content/Python/jam/flow.py#L49), o `method` en [tools.py:2593](../../Content/Python/jam/tools.py#L2593)). `dsl.coaccionar` no comprueba esta lista ni emite sugerencias cuando el valor es inválido.

### 4.2 El bug de propagación en cascada (`fuente-roja`)
- En `graph.ejecutar_detalle` ([graph.py:857-867](../../Content/Python/jam/graph.py#L857-L867)):
  - Si un nodo raíz o intermedio lanza una excepción en `info["fn"]`, se captura y se marca `estado = "error"` ([graph.py:860-863](../../Content/Python/jam/graph.py#L860-L863)).
  - La salida del nodo queda en `salida = None`, y `runtime_outputs[nid] = None` ([graph.py:865-866](../../Content/Python/jam/graph.py#L865-L866)).
  - **El ejecutor no cancela los nodos dependientes:** El bucle topológico prosigue. El siguiente nodo aguas abajo busca su entrada con `valor_por_el_cable` ([graph.py:804-809](../../Content/Python/jam/graph.py#L804-L809)), que devuelve `None`.
  - El nodo subsiguiente invoca `info["fn"](entrada, **kw)` con `entrada = None` ([graph.py:858](../../Content/Python/jam/graph.py#L858)).
  - Esto desata una cascada de excepciones espurias (`AttributeError: 'NoneType' object has no attribute ...`) a lo largo de toda la cadena ([RELEVO.md:315-316](../../RELEVO.md#L315-L316)). Para un LLM, este reporte envenena el contexto con múltiples fallos que esconden el único error original.

---

## 5. Estado de las 5 Tareas Abiertas Relacionadas

### 5.1 `etiquetas-pines`
- **Ubicación en código:** [Source/JamEditor/Public/SJamGraphNode.h:44-50](../../Source/JamEditor/Public/SJamGraphNode.h#L44-L50), [Source/JamEditor/Private/SJamGraphNode.cpp:531-575](../../Source/JamEditor/Private/SJamGraphNode.cpp#L531-L575), [RELEVO.md:795-817](../../RELEVO.md#L795-L817).
- **Problema:** `FJamNodePin` solo tiene `Name`, `DataType`, `TypeLabel`, `Color`. No posee `Label`. Al renderizar la fila de pines, `SJamGraphNode.cpp:563` imprime `*OutPin.Name`. En matrices y funciones compuestas, muestra nombres de identificador crudo (`out`, `eje_x`, `eje_y`, `eje_z`) en lugar de las etiquetas declaradas en el cerebro (`traslación`, `eje X`, `eje Y`, `eje Z`).
- **Estado:** Especificado con precisión en `RELEVO.md:809-813`, pendiente de implementación en C++ y test asociado.

### 5.2 `labels-tools`
- **Ubicación en código:** [Content/Python/jam/registro_core.py:114-116](../../Content/Python/jam/registro_core.py#L114-L116), [RELEVO.md:1418-1426](../../RELEVO.md#L1418-L1426).
- **Problema:** La auditoría del oráculo del registro registra exactamente 136 herramientas sin `label` humano explícito (ej. `mesh_weld` en vez de «Soldar bordes»).
- **Estado:** Deuda medida y acotada mediante test de regresión. Las categorías, docs, dominios y pines están sanos, pero los nombres en UI y ribbon siguen mostrando nombres técnicos en 136 casos.

### 5.3 `jamtool-ui`
- **Ubicación en código:** [Content/Python/jam/jamtool_core.py:1-175](../../Content/Python/jam/jamtool_core.py#L1-L175), [Content/Python/jam/jamtool.py:1-78](../../Content/Python/jam/jamtool.py#L1-L78), [Content/Python/jam/api.py:771-814](../../Content/Python/jam/api.py#L771-L814), [RELEVO.md:1459-1462](../../RELEVO.md#L1459-L1462).
- **Problema:** La especificación `.jamtool` portable con versionado, dependencias y cálculo de entrada de selección (`jamtool_core.entrada_de_seleccion`, [jamtool_core.py:38-65](../../Content/Python/jam/jamtool_core.py#L38-L65)) está terminada en Python y expuesta en `api.py`. Lo que resta es el soporte en Slate C++: botones Exportar/Importar y que la Dash Bar resuelva la selección activa del nivel al invocar la función.
- **Estado:** Backend puro y API completos (909 tests verdes); falta integración visual en C++.

### 5.4 `colocar-cli`
- **Ubicación en código:** [Content/Python/jam/tools.py:257-261](../../Content/Python/jam/tools.py#L257-L261), [AGENTS.md (tabla de trampas)](../../AGENTS.md), [RELEVO.md:1363-1406](../../RELEVO.md#L1363-L1406).
- **Problema:** En Unreal Engine headless (commandlet), `unreal.EditorLevelLibrary.spawn_actor_from_object` devuelve siempre `None` con aviso en log. Esto impide verificar de forma automatizada y sin GUI que comandos de colocación instancian actores válidos en escena.
- **Estado:** Atajado en tests puros verificando resolución de mallas y cálculo de transforms, requiriendo editor GUI para la prueba de colocación física en nivel.

### 5.5 `fuente-roja`
- **Ubicación en código:** [Content/Python/jam/graph.py:857-867](../../Content/Python/jam/graph.py#L857-L867), [RELEVO.md:315-317](../../RELEVO.md#L315-L317).
- **Problema:** Un fallo en un nodo fuente no cancela la ejecución de los nodos aguas abajo. Al recibir `entrada = None`, los nodos dependientes fallan con errores secundarios engañosos.
- **Estado:** Abierto y medido. Se requiere que el planificador omita dependientes cuando un ancestro esté en estado `"error"`, marcándolos como cancelados/omitidos por fallo upstream.

---

## 6. Jerarquía Priorizada de Bloqueos para el LLM

Ordenado estrictamente de mayor a menor impacto según cuánto le cierra el paso a un modelo de lenguaje para operar Jam:

### Nivel 1 — Bloqueo Arquitectónico Absoluto (Imposibilidad de operar)
1. **Inexistencia de sintaxis DSL para Grafos / DAGs:**
   - *Impacto:* El LLM no puede encadenar herramientas ni conectar cables mediante texto legible. Deja 86 verbos de modelado, curvas, shaders y mass gameplay totalmente inaccesibles sin recurrir a escribir JSON crudo de bajo nivel.
2. **Ausencia total de Ida y Vuelta (Round-Trip Graph ↔ DSL):**
   - *Impacto:* Rompe el principio de trabajo compartido humano-LLM. El humano edita en Slate y el LLM no puede "ver" el cambio en DSL; el LLM ejecuta comandos DSL y estos no se materializan en el canvas de nodos de Slate.

### Nivel 2 — Bloqueo de Confiabilidad y Diagnóstico (Alucinación y descarte silencioso)
3. **Coerción ciega y descarte silencioso en `dsl.coaccionar`:**
   - *Impacto:* Errores tipográficos en parámetros o parámetros no soportados se ignoran sin lanzar advertencia o error legible ([graph.py:825](../../Content/Python/jam/graph.py#L825)). Falta soporte para tipos ricos (vectores, dominios, matrices). Los mensajes no indican las opciones válidas declaradas en el registro.
4. **Cascada de errores engañosa por el bug `fuente-roja`:**
   - *Impacto:* Un error simple en un nodo inicial detona múltiples fallos derivados con `NoneType` a lo largo del grafo ([graph.py:858](../../Content/Python/jam/graph.py#L858)), desorientando los bucles de autorreparación del LLM.

### Nivel 3 — Desalineación Semántica y Ergonomía (Vocabulario compartido)
5. **Disparidad de etiquetas técnicas vs. humanas (`etiquetas-pines` y `labels-tools`):**
   - *Impacto:* El humano en Slate ve `out (vector)` o nombres en snake_case crudo ([SJamGraphNode.cpp:563](../../Source/JamEditor/Private/SJamGraphNode.cpp#L563)), mientras el LLM utiliza las etiquetas semánticas (`traslación`, `eje X`). La falta de etiquetas unificadas impide una conversación coherente entre usuario y asistente.
6. **Limitación de verificación headless (`colocar-cli`):**
   - *Impacto:* Impide verificar colocación física de actores en suites headless sin abrir GUI de Unreal.
7. **Integración pendiente de gestos en UI (`jamtool-ui`):**
   - *Impacto:* El usuario no puede disparar herramientas empaquetadas desde la Dash Bar en C++, aunque el LLM ya puede importarlas y exportarlas a nivel de API pura.
