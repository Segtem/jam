---
title: "TreeGen: ejemplo de dos niveles y presets de Graph"
tipo: INFORME
version: "1.0"
aliases:
  - "Árbol de dos niveles"
  - "Presets kind graph"
  - "Preset de un canvas de verbos"
tags:
  - jam
  - graph
  - treegen
  - presets
  - hierarchy
status: implementado
date: 2026-07-27
updated: 2026-07-27
---

# TreeGen: ejemplo de dos niveles y presets de Graph

## Resultado

Se cerró el segundo y último bloque de [[2026-07-27-INFORME-TreeGen-Asset-Set-Choose-Copy-Variants-v1.0|TreeGen: Asset Set, Choose Asset y Copy Variants]]. Son dos
entregables que se necesitan mutuamente: un ejemplo que ya vale la pena reusar, y un preset que
finalmente puede guardarlo.

## 1. El ejemplo de dos niveles

**File → Abrir ejemplo: árbol de dos niveles** (`TreeGen-Two-Level.jamgraph`): 28 nodos, 29 aristas.

```text
Trunk S ─┬─────────────────────────────→ Trunk Pipe ────┐
         │                                              │
         └→ F → Distribute → Transform → Branch L1 S ─┬─→ Branch Pipe ─┤
                                                      │                ├→ Merge → Color
                                                      └→ F → Distribute → Transform → Branch L2 S ─┬→ Twig Pipe ─┘
                                                                                                   │      ↓
                                                                                                   │  UV Scale → Material → Normals → Mesh to Static → Place
                                                                                                   │
                                                                                                   └→ F → Choose Asset → HISM Output
```

La clave es que **el nivel 2 es la misma cadena de cuatro verbos que el nivel 1**, enchufada a la
salida `S` del primero:

```text
S → Curve Frames → Distribute Frames → Transform Frames → Branch From Frames → S
```

Eso es lo que hace la réplica comparable con el original: TreeGen tampoco tiene un nodo «rama de
segundo orden», tiene el mismo actor `Branch` instanciado recursivamente. Acá se repite el patrón a
mano y se ve entero en el canvas.

### La jerarquía es real, no dos cadenas pegadas

Medido en el Preflight + runtime puro del ejemplo:

| Etapa | Resultado |
|---|---|
| Tronco | 19 puntos · 627 cm |
| Frames L1 | 10 frames / 1 curva |
| Ramas L1 | **12 ramas** · escala nominal 0.82 |
| Frames L2 | **72 frames / 12 curvas** |
| Ramitas L2 | **60 ramas** · escala nominal 0.62 |
| Frames de follaje | **180 frames / 60 curvas** |
| Barridos | 1 + 12 + 60 = **73 sweeps** |

La escala cae en cascada porque `Transform Frames` y `Branch From Frames` heredan la del padre: el
promedio de escala de las ramitas es **0.51 ≈ 0.82 × 0.62**, no el 0.62 nominal de su propio nivel.
La prueba afirma exactamente eso, y se verificó por mutación: poniendo `inherit_scale=false` en
`l2_transform` el promedio salta a 0.61 y el test falla. Sin esa herencia el árbol perdería la
lectura jerárquica: las ramitas saldrían tan gruesas como las ramas.

Cada nivel tiene además **su propio perfil de taper** (`Graph Curve N[]` → `Pipe with Profile`) y su
propio radio: 52 cm el tronco, 14 las ramas, 5 las ramitas. El follaje cuelga de las ramitas del
nivel 2, no del tronco.

### Cómo editarlo

- Más ramas madre: `l1_distribute.count`.
- Más ramitas por rama: `l2_distribute.count` (el total es `l1 × l2`).
- Un árbol distinto pero reproducible: cambiar los `seed` (1977 / 4021 / 8803).
- Un tercer nivel: duplicar la cadena de cuatro verbos y enchufarla a `l2_branches`.
- Otra silueta: `trunk_profile.shape` y `mid_value`.

El follaje usa `PineFrond` más `/Engine/BasicShapes/Plane.Plane` como segunda variante portable, la
misma convención que el ejemplo de un nivel.

## 2. Presets que sí corren un Graph de verbos

### El bug

`preset.desde_grafo()` marcaba **siempre** `kind: "flow"`, sin mirar el contenido. `preset.aplicar()`
mandaba todo lo que fuera `flow` a `panel.ejecutar_flow_json()`. O sea: guardar el canvas de TreeGen
como preset y aplicarlo lo corría con el evaluador de Flow, donde `curve_bezier`, `place` o
`mesh_pipe_profile` no existen. El botón «guardar preset» de la ventana Graph producía presets que no
podían funcionar.

Es el punto «guardar el kind real en los presets» de
[[2026-07-25-PLAN-Contrato-Unificado-Graph-Flow-Presets-Web-v1.0|Contrato unificado de ejecución]]; el resto de esa tarea sigue abierto.

### La corrección

`preset.kind_de_grafo()` decide leyendo el grafo, con la **misma** detección que ya usaba
`api.run_graph_json()`:

```text
todos los nodos son ops de flow → "flow"  → panel.ejecutar_flow_json
cualquier otro caso             → "graph" → panel.ejecutar_grafo_json
```

- `desde_grafo()` guarda el `kind` real; `api.preset_save_graph()` lo informa al confirmar.
- `aplicar()` rutea por ese kind y, si un preset viejo declara `flow` pero contiene verbos, **relee el
  grafo** y lo manda al runner correcto igual.
- `panel.ejecutar_grafo_json()` acepta `owner`. Un preset aplicado desde la Dash Bar corre como
  `dash`, así lo resuelven el Confirmar/Descartar de esa barra y no los de la ventana Graph.
- Un grafo mixto cae al runner de verbos y **Compile lo rechaza nombrando la op intrusa**
  (`[a·pts_line] verbo desconocido: «pts_line»`), en vez de ejecutar el runner equivocado en silencio.
  Para eso `JamGraph.from_json()` lee `kind` como fallback de `verb`: sólo para que el diagnóstico
  tenga nombre.
- Un preset `graph` sin grafo falla sin ejecutar nada.

### Efecto colateral arreglado: los acentos

`_slug()` tiraba todo lo que no fuera `a-z0-9`, así que «Árbol TreeGen dos niveles» se guardaba como
`rbol-treegen-dos-niveles.json`. Ahora translitera con `unicodedata` (`Diseño Ñandú` →
`diseno-nandu`). Importa más de lo que parece: `cargar()` resuelve por slug del nombre.

### Presets de fábrica

Dos nuevos en `presets/` (scope global, versionados con el plugin):

| Preset | kind | nodos |
|---|---|---|
| Árbol TreeGen dos niveles | `graph` | 28 |
| Árbol TreeGen un nivel | `graph` | 21 |

Cada uno lleva el grafo del ejemplo homónimo. Una prueba compara preset contra ejemplo nodo por nodo,
así que editar uno sin el otro rompe la suite a propósito.

## Verificación

- Suite Python headless: **105/105 correctos** (89 antes del bloque; `test_presets.py` suma 11 y
  `test_unreal_api_names.py` 4).
- El ejemplo de dos niveles compila entero por Preflight y se corre de verdad su tramo puro: los diez
  nodos en `ok` y los conteos 12 / 72 / 60 / 180 afirmados uno por uno.
- La cascada de escala se probó **por mutación**: romper `inherit_scale` hace fallar el test.
- Presets: detección de kind (flow / graph / mixto), ruteo al runner correcto con owner `dash`,
  reruteo de un preset viejo mal marcado, preset de comando intacto, preset roto sin grafo, y
  transliteración del slug.
- Los 6 presets de fábrica se validan: kind coherente con su contenido, scope, y slugs sin colisión.
- `BotOOEditor Linux Development` con Unreal 5.7.4: **Result: Succeeded**.
- `compileall` y `git diff --check`: limpios.

## Verificación en Unreal 5.7.4 real

El ejemplo se corrió en `BotOOEditor` por `UnrealEditor-Cmd -run=pythonscript -RenderOffScreen`
(recortando `place`, ver abajo): **27 nodos, 0 en error**.

| Nodo | Resultado real |
|---|---|
| `trunk_pipe` | 228 vértices · perfil custom 1→0.24 × 52 cm |
| `branch_pipe` | 1.056 vértices · **12 sweeps** · ease_in 1→0.1 × 14 cm |
| `twig_pipe` | 2.100 vértices · **60 sweeps** · ease_in 1→0.05 × 5 cm |
| `merge` | **3.384 vértices** |
| `wood_uv` | UV0 × (2, 8) |
| `wood_material` | material slot 0: VertexColorMaterial |
| `tree_asset` | StaticMesh en `/Game/JamPreview/graph/PV_*_SM_TreeGen_TwoLevel` |
| `foliage` | **180 instancias · 2 HISM** · Plane, PineFrond |

Los conteos del motor coinciden exactamente con los que afirma la suite headless (12 ramas, 72
frames/12 curvas, 60 ramitas, 180 frames de follaje).

Después se corrió `Discard` en **otro proceso**: recuperó el Preview desde los metadatos del asset,
borró el `.uasset` temporal y dejó `Content/JamPreview/graph/` vacío. Eso ejercita de paso la
recuperación sin actor de [[2026-07-26-PLAN-Preview-Transaccional-Efectos-PCG-v1.0|Preview transaccional y efectos de PCG]].

### Lo que NO se puede verificar headless

`place` crashea en un commandlet:

```text
SIGSEGV en UPlacementSubsystem::FindAssetFactoryFromAssetData
  ← EditorActorSubsystem.spawn_actor_from_object
```

No es un bug de Jam: `spawn_actor_from_object` necesita el editor de nivel, que un commandlet no
levanta. `hism_output` **sí** funciona headless porque usa `spawn_actor_from_class`, que no pasa por
el PlacementSubsystem. Conviene recordarlo: se puede automatizar todo el grafo menos el `Place` final.

### Prueba manual recomendada

1. **File → Abrir ejemplo: árbol de dos niveles**, luego `✓ Compile`: sin errores.
2. `Run graph`: un `prev_*` con el árbol y un `Jam_HISM_TreeGen_TwoLevel` con las 180 instancias.
3. Subir `l2_distribute.count` a 8 y volver a correr: más ramitas, mismo tronco.
4. Guardar el canvas como preset y confirmar que el mensaje dice `PRESET (graph) guardado ✓`.
5. Aplicar ese preset desde la Dash Bar: tiene que recrear el árbol y quedar en Preview de `dash`.

## Archivos principales

- `Resources/Examples/TreeGen-Two-Level.jamgraph`: el ejemplo nuevo.
- `Source/JamEditor/Private/SJamGraphEditor.cpp` y `.h`: entrada de menú `LoadTwoLevelExample`.
- `Content/Python/jam/preset.py`: `kind_de_grafo()`, ruteo de `aplicar()`, slug con acentos.
- `Content/Python/jam/panel.py`: `ejecutar_grafo_json(owner=…)`.
- `Content/Python/jam/api.py`: `preset_save_graph()` informa el kind real.
- `Content/Python/jam/graph.py`: `kind` como fallback de `verb` para diagnosticar grafos mixtos.
- `presets/arbol-treegen-*.json`: presets de fábrica.
- `Content/Python/tests/test_presets.py` y `test_mesh.py`: regresiones del bloque.

## Qué queda de TreeGen

**Nada de los dos bloques.** La etapa TreeGen está cerrada: flow creativo, taper no lineal, variantes
por frame, materiales/UV/HISM y ahora la réplica de dos niveles con presets.

Lo que sigue abierto ya no es TreeGen sino Graph en general:

- el contrato unificado completo de [[2026-07-25-PLAN-Contrato-Unificado-Graph-Flow-Presets-Web-v1.0|Contrato unificado de ejecución]]
  (grafo unificado vs. dos modos separados, `graph_kind` en el JSON, un solo envelope de resultado);
- que la ventana Graph pueda aplicar un preset, no sólo guardarlo — hoy aplicar vive en la Dash Bar;
- recursión real: un nodo que repita una subcadena N veces, en vez de duplicarla a mano en el canvas.

## Relacionado

- [[2026-07-27-INFORME-TreeGen-UV-Materiales-Sections-HISM-v1.0|TreeGen: UV, materiales, sections y HISM]]
- [[2026-07-27-INFORME-TreeGen-Asset-Set-Choose-Copy-Variants-v1.0|TreeGen: Asset Set, Choose Asset y Copy Variants]]
- [[2026-07-27-INFORME-TreeGen-Curve-N-Array-Pipe-With-Profile-v1.0|TreeGen: Curve N[] y Pipe with Profile]]
- [[2026-07-27-INFORME-TreeGen-Auditoria-Blueprints-Flow-Real-v1.0|TreeGen: auditoría de Blueprints y flow real]]
- [[2026-07-25-PLAN-Contrato-Unificado-Graph-Flow-Presets-Web-v1.0|Contrato unificado de ejecución]]
- [[2026-07-27-INFORME-Oraculo-De-Forma-Malla-Referencia-v1.0|Oráculo de forma]]
