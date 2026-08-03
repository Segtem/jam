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
