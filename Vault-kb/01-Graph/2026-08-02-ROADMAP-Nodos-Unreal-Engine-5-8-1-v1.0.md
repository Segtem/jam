---
title: "Nodos de Unreal Engine 5.8.1 para Jam"
tipo: ROADMAP
version: "1.0"
date: 2026-08-02
updated: 2026-08-02
status: en-progreso
area: 01-Graph
tags:
  - jam
  - graph
  - unreal
  - ue-5-8
  - nanite
  - pcg
  - pve
  - dataflow
aliases:
  - Roadmap de nodos UE 5.8.1
  - Catálogo UE 5.8 para Jam
---

# Nodos de Unreal Engine 5.8.1 para Jam

## Decisión

Jam no replica uno por uno los grafos internos del motor. Traduce capacidades de UE 5.8.1 a verbos
de intención, compactos y verificables. El id estable pertenece a Jam; una clase experimental de
Epic queda detrás del adaptador y puede cambiar sin invalidar los presets.

El orden favorece primero APIs públicas y lecturas no destructivas; después integración PCG y PVE;
por último superficies experimentales o que sólo se pueden verificar con editor GUI.

## Entregas

### 1. Geometry Script y Nanite — en progreso

- `nanite_analyze`: lectura A → A de habilitación, vértices, triángulos, UV y LOD.
- `nanite_validate`: exige una representación habilitada y no vacía; deja pasar A.
- `mesh_simplify_count`, `mesh_simplify_tolerance`, `mesh_simplify_edge_length`.
- `mesh_remesh_uniform`, `mesh_remesh_adaptive` y variantes controladas por weight map.
- `mesh_noise_perlin`, `mesh_clean_material_ids`, `mesh_remap_materials`.
- `mesh_copy_static`, `mesh_copy_skeletal` y `mesh_validate`.
- `nanite_settings`, `nanite_foliage_settings`, `nanite_assembly`.

Los dos primeros nodos son deliberadamente de sólo lectura. No crean Preview, no ensucian el asset
y publican su veredicto en el Inspector. En UE 5.8.1 los accessors de `StaticMesh` para vértices y
triángulos Nanite y canales UV son públicos y BlueprintPure.

#### Primera evidencia

`nanite_analyze` y `nanite_validate` quedaron implementados como A → A con iconos y grupo propio.
El juicio vive en `nanite_core.py`, sin `unreal`; el adaptador lee `nanite_settings` directamente del
asset y los accessors públicos `get_num_nanite_vertices`, `get_num_nanite_triangles`,
`get_num_tex_coords` y `get_num_lods`.

La sonda `tools/experiments/verifica_nanite_diagnostics_58.py` recorrió spec, Compile y Run públicos
dentro de UE 5.8.1. Discriminó dos activos reales:

- `/Engine/EngineMeshes/Sphere`: Nanite apagado; Analyze verde y Validate rojo.
- `/Game/CasaKit/casa_kit`: Nanite habilitado; 416.179 triángulos, 1.202.673 vértices, un canal UV
  y un LOD; ambos nodos verdes.

Los dos Runs devolvieron `preview: false`: una lectura no reemplaza el Preview existente. El primer
intento descubrió que `StaticMeshEditorSubsystem` es `None` en commandlet; por eso el flag se lee del
asset. El subsistema queda reservado para convertir y reconstruir. Marcador:
`JAM_NANITE_DIAGNOSTICS_58 TODO VERDE`. El commandlet retorna 1 por los nueve paquetes ilegibles ya
conocidos de BotOO, no por la sonda.

La prueba se discriminó mutando temporalmente la regla «cero vértices es defecto»: quedó roja y fue
restaurada. Falta únicamente el gesto visual de insertar, cablear y ejecutar ambas fichas en Slate.

**Lo que no ven:** calidad visual, fidelidad del fallback, textura/material perdido, deformación,
overdraw, costo de render ni el resultado posterior de Fracture. Esos hechos no se infieren de los
conteos; necesitan sensores separados. La conservación de materiales y del flag Nanite en Fracture
se mantiene bajo la evidencia de
[[2026-08-02-INFORME-Nanite-Fracture-Dataflow-UE-5-8-v1.0]].

#### Segunda evidencia: Simplify

`mesh_simplify_count`, `mesh_simplify_tolerance` y `mesh_simplify_edge_length` quedaron
implementados como operadores no destructivos M → M dentro del grupo **Mesh → Optimizar**. Los tres
clonan la entrada, compactan la salida y comparten un contrato puro para método, costuras y peso de
regularización. El default `attributes` elige explícitamente `ATTRIBUTE_AWARE_V2`: en 5.8 el miembro
histórico `ATTRIBUTE_AWARE` pasó a significar sólo normales, aunque su nombre Python no lo diga.

La sonda `tools/experiments/verifica_mesh_simplify_58.py` recorrió spec, Compile, Run e Inspector
públicos dentro de UE 5.8.1. Sobre la misma esfera de 1.922 vértices midió:

- objetivo de 400 triángulos: **202 vértices**;
- tolerancia geométrica de 5 cm: **201 vértices**;
- arista objetivo de 20 cm: **332 vértices**.

Marcador: `JAM_MESH_SIMPLIFY_58 TODO VERDE`. La comprobación global quedó en **101 símbolos y 78
métodos reales**, todos existentes. El test discriminante reemplazó temporalmente V2 por la variante
sólo-normales y quedó rojo. Falta el gesto visual de insertar y correr las tres fichas en Slate.

**Lo que no ven:** silueta percibida, calidad de UV/tangentes, triángulos degenerados, costo de
render ni calidad de LOD. `edge_length` tampoco promete una remalla uniforme: la propia API permite
aristas mayores que el objetivo.

#### Puerta de Remesh

`ApplyUniformRemesh` sigue fuera del registro estable. El header público de Epic advierte que sus
resultados pueden ser no deterministas y cambiar entre versiones. La sonda
`tools/experiments/investiga_remesh_determinismo_58.py` obtuvo el mismo SHA-256 de posiciones y
topología en **16 corridas repartidas entre dos procesos** (486 vértices, 968 triángulos), pero eso
sólo demuestra repetibilidad para esta entrada y esta build; no anula el contrato advertido por el
motor. Antes de exponer `mesh_remesh_uniform/adaptive`, Jam necesita una categoría experimental o
un oráculo por tolerancia que no dependa de igualdad exacta.

#### Tercera evidencia: Material IDs

`mesh_remap_materials` y `mesh_clean_material_ids` quedaron implementados como operadores M → M
no destructivos dentro del grupo **Mesh → Materiales**. El primero fusiona una section en otra, pero
sólo si ambos IDs ya están usados: apuntar a un índice nuevo inventaría un slot sin material. El
segundo llama la compactación nativa y actualiza en el mismo paso el sidecar de `MaterialInterface`
que Jam transporta hasta `mesh_to_static`.

La sonda `tools/experiments/verifica_mesh_material_ids_58.py` construyó dos ramas con materiales
distintos y recorrió spec, Compile y Run públicos dentro de UE 5.8.1:

- `mesh_merge`: IDs `{0,1}` y **2 slots**;
- reasignación `1→0`: ID `{0}` y **2 slots** todavía conservados;
- limpieza: ID `{0}` y **1 slot**, sin el material ya inutilizado.

Marcador: `JAM_MESH_MATERIAL_IDS_58 TODO VERDE`. La comprobación global quedó en **102 símbolos y
81 métodos reales**, todos existentes. El test discriminante anuló temporalmente la defensa contra
un `to_id` inexistente y quedó rojo.

**Lo que no ven:** corrección visual del material, parámetros de una instancia, orden semántico de
sections ni intención artística. Sólo miden que IDs y slots sigan siendo una correspondencia válida.

#### Cuarta evidencia: Validar malla

`mesh_validate` quedó implementado como sensor M → M en **Mesh → Hornear**. No clona ni modifica la
entrada: mide vértices, rango de IDs de triángulo, densidad de IDs, cierre, lazos de borde ambiguos,
componentes conectados, canales UV y correspondencia entre Material IDs y slots. Por defecto sólo
rechaza defectos estructurales; cada grafo puede exigir además cierre, UV, materiales o un máximo de
componentes.

El juicio vive en `mesh_validate_core.py`, sin `unreal`. Un incumplimiento deliberado deja la ficha
naranja y hace observable la causa, pero conserva M para que el autor pueda inspeccionarla o
repararla aguas abajo. Un error de contrato —por ejemplo `max_components < 0`— sí queda rojo.

La sonda `tools/experiments/verifica_mesh_validate_58.py` recorrió spec, Compile y Run públicos en
UE 5.8.1: una esfera cerrada quedó verde, una grilla con `require_closed=true` quedó naranja por
«malla abierta», y en ambos casos la salida fue el mismo objeto M de entrada. Marcador:
`JAM_MESH_VALIDATE_58 TODO VERDE`. Los **102 símbolos y 81 métodos** usados por Jam siguen
existiendo en el motor. El test discriminante anuló temporalmente la regla de cierre y quedó rojo;
la suite completa quedó en **581 tests**.

**Lo que no ve:** triángulos degenerados o solapados, normales/tangentes incorrectas, estiramiento
UV, manifoldness interior, escala, silueta, calidad visual, costo de render ni intención artística.
Esos hechos requieren sensores separados; el nodo no los infiere de conteos generales.

#### Quinta evidencia: copiar Static y Skeletal Mesh

`mesh_copy_static` y `mesh_copy_skeletal` quedaron implementados como conversores A → M en
**Mesh → Hornear**. Ambos exponen tipo/índice de LOD y las opciones públicas de Build Settings,
tangentes y Build Scale. La ruta Static usa `CopyMeshFromStaticMeshV2` con materials por section;
la Skeletal usa `CopyMeshFromSkeletalMesh` y la lista de materiales específica del LOD. En ambos
casos esa lista entra al sidecar de M y puede llegar luego a `mesh_to_static`.

El viejo id `mesh_from_asset` sigue registrado como alias de la nueva copia Static, dentro de un
grupo **Compatibilidad**: los presets guardados no cambian de significado, pero las altas nuevas
muestran nombres explícitos. También se amplió la resolución de rutas A para admitir Skeletal Mesh;
cada consumidor todavía valida la clase concreta que sabe procesar.

La sonda `tools/experiments/verifica_mesh_copy_58.py` recorrió spec, Compile, Run y Discard públicos
en UE 5.8.1. Copió `/Engine/EngineMeshes/Sphere` con **266 vértices y 1 material**, y
`SKM_Quinn_Simple` con **43.761 vértices y 2 materiales**; además exigió UV/material válido en la
copia Static y comprobó que el alias histórico conserve el mismo sidecar. Marcador:
`JAM_MESH_COPY_58 TODO VERDE`. La puerta global quedó en **103 símbolos y 84 métodos**, todos
existentes. La suite suma **586 tests**; el mutante que habilitaba `hi_res` para Skeletal quedó rojo.

**Lo que no ve:** fidelidad visual entre el asset y M, morph targets, compatibilidad del skeleton,
animaciones, deformación de skin, integridad de pesos/huesos ni equivalencia entre LODs. La copia
nativa de Quinn advierte que deja vértices sin triángulos; Jam lo conserva en vez de compactar a
ciegas y `mesh_validate` puede hacerlo observable como IDs no densos.

### 2. PCG 5.8

- `pcg_editor_cameras`, `pcg_apply_spline`, `pcg_teleport`.
- `pcg_sort`, `pcg_class_from_attribute`, `pcg_complex_attribute`.
- `pcg_set_mesh_materials` y `pcg_static_mesh_gpu`.
- `pcg_manual_exclude`, `pcg_manual_transform`, `pcg_manual_restore`.
- `pcg_validate_graph`: verifica el grafo después de cada `add_edge`; la API no siempre falla fuerte.

La edición manual es no destructiva: Jam debe conservar qué proviene del generador y qué es override
humano. `Python Data Processor` queda como escape interno controlado, no como nodo de código libre.

### 3. Procedural Vegetation Editor

- Primer macro `vegetation_generate`: perfil → crecimiento → follaje → mesh → exportación.
- Descomposición avanzada: `vegetation_profile`, `vegetation_seed`, `vegetation_grow`,
  `vegetation_prune`, `vegetation_carve`, `vegetation_avoid`, `vegetation_graft`,
  `vegetation_foliage`, `vegetation_mesh`, `vegetation_skeleton_extract`,
  `vegetation_trunk_material` y `vegetation_export`.

PVE sigue experimental y será dependencia opcional. El código local de 5.8.1 ya marca
`PVPresetLoaderSettings` como deprecado: los presets de Jam guardarán intención/perfil, nunca el
nombre de esa clase interna. PVE no reemplaza TreeGen; entra primero como otra fuente de assets.

### 4. Dataflow, Fracture y Chaos

- `mesh_split_islands`, `mesh_remove_overlaps`, `mesh_convex_decompose`.
- `mesh_medial_skeleton`, `skeleton_subdivide`.
- `field_sample_float`, `field_sample_vector`.
- `fracture_mesh_cut`, `fracture_remove_small`.
- `dataflow_cache`, `chaos_cache_bake`, `chaos_cache_trim`, `chaos_cache_playback`.

La autoría de Dataflow se verifica únicamente por editor GUI mientras `add_dataflow_node` pueda
colgar headless. Tener una clase o compilar el plugin no cuenta como funcionamiento.

### 5. Mesh Terrain

- `terrain_create`, `terrain_from_mesh`, `terrain_layer`, `terrain_boolean`.
- `terrain_material`, `terrain_section`, `terrain_bake_section`, `terrain_to_pcg`.

Mesh Terrain es experimental, está deshabilitado en BotOO y gran parte de su editor vive en APIs
privadas. La primera integración sólo consultará y horneará secciones en un host aislado.

### 6. Mundo y producción

- `world_hlod_build_selection`, `world_hlod_build_region`, `world_streaming_validate`.
- `render_job`, `render_layer`, `render_output`.
- perfiles explícitos de MegaLights y Lumen.
- Cloth/Dataflow: crear, constraints, weight maps, simular y cachear.

## Puertas para todo nodo nuevo

1. Cerebro puro: defaults, dominio, texto y ceguera declarada sin `unreal`.
2. Adaptador fino: comprueba plugin/API y convierte objetos del motor en datos planos.
3. Compile y Run por Graph real; llamar una función directa no certifica el nodo.
4. Si modifica Content o escena, Preview/Bake/Discard o transacción equivalente.
5. El test discrimina con una mutación deliberada.
6. Experimental significa plugin opcional, error comprensible y cero clase interna persistida.

## Fuentes oficiales

- [Unreal Engine 5.8 is now available](https://www.unrealengine.com/news/unreal-engine-5-8-is-now-available)
- [Unreal Engine 5.8 Release Notes](https://dev.epicgames.com/documentation/unreal-engine/unreal-engine-5-8-release-notes)
- [Procedural Vegetation Editor](https://dev.epicgames.com/documentation/en-us/unreal-engine/procedural-vegetation-editor-pve-in-unreal-engine)
