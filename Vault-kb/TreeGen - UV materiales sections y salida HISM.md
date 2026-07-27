---
title: "TreeGen: UV, materiales, sections y salida HISM"
aliases:
  - "UV Scale y Material del Graph"
  - "HISM Output"
  - "Mesh sections de Jam"
tags:
  - jam
  - graph
  - treegen
  - materials
  - uv
  - hism
  - performance
status: implementado
date: 2026-07-27
---

# TreeGen: UV, materiales, sections y salida HISM

## Resultado

Se cerró el primer bloque que faltaba de [[TreeGen - Asset Set Choose Asset y Copy Variants]]:
**fidelidad de materiales y rendimiento**. El árbol dejó de ser una única malla gris con vertex color
y pasó a tener dos salidas con roles distintos:

```text
Trunk Pipe ─┐
            ├→ Merge → Color → UV Scale → Material → Normals → Mesh to Static → Place
Branch Pipe ─┘

Choose Asset AF ──────────────────────────────→ HISM Output
```

La madera se hornea como StaticMesh; el follaje **no vuelve a la malla**: sale por instancias. Es la
misma división que usa la vegetación real de producción, y evita fusionar miles de cards en la
geometría del tronco.

## Los tres verbos

Los tres viven en el tab **Mesh**.

### UV Scale `M → M`

Escala un canal UV existente sin regenerar la malla. Parámetros `u`, `v`, `channel` (0..7) y el origen
`origin_u`/`origin_v` del escalado. Clona la entrada, así que la malla original sigue disponible para
otra rama del grafo.

Rechaza `u` o `v` en cero, canales fuera de 0..7 y cualquier número no finito.

### Material `M → M`

Asigna un material a **todos** los triángulos de la malla y deja el slot registrado hasta
`Mesh to Static`.

`DynamicMesh` transporta IDs de material pero no la lista de `MaterialInterface` correspondiente. Por
eso `mesh.py` mantiene un sidecar `_MESH_MATERIALS` que vive sólo durante Run y acompaña clones y
merges hasta que se crea el asset.

### HISM Output `AF → H`

Crea un actor con **un `HierarchicalInstancedStaticMeshComponent` por variante** y una instancia por
frame. Consume directamente la salida `AF` de `Choose Asset`, así que hereda las variantes, el modo de
selección y el seed sin pasar por geometría.

- Cada Static Mesh única se carga una sola vez, sin importar cuántos frames la repitan.
- Orientación idéntica a `Copy Mesh to Frames`: `X` sobre `frame.tangent`, `Z` sobre `frame.outward`.
- Corrección propia del asset: `asset_offset_*`, `asset_pitch/yaw/roll`, `asset_scale` y
  `inherit_scale`.
- Límite: 65.536 instancias por nodo.
- Si falla la carga de una variante a mitad de camino, el actor a medio poblar se destruye y el nodo
  devuelve error; no queda basura en el nivel.

`H` es un tipo **terminal**: no existe ningún verbo que lo consuma, por lo que la cadena de malla no
puede continuar después del HISM. Slate le da color propio (verde azulado).

`hism_output` **no** está en `tools.SIN_SPAWN`, así que su actor entra al ciclo normal
`Run → Bake / Discard` por diferencia de actores, igual que `Place`. Ver
[[Tarea - Preview transaccional y efectos de PCG]].

## Mesh sections: una por entrada del Merge

`mesh_merge` ya no aplasta los materiales de sus entradas. Cada input conserva sus IDs locales, que se
desplazan antes de concatenar:

```text
Bark  (id 0) ─┐
              ├→ Merge → ids 0 y 1 → StaticMesh con 2 sections
Leaf  (id 0→1)┘
```

`Mesh to Static` recorre la lista final y llama `set_material(slot, material)` por section. Un
material explícito **gana** sobre el lector implícito de Vertex Color: si el grafo asigna material, la
bandera `show_vertex_colors` deja de aplicarse.

## Cómo quedó el ejemplo

**File → Abrir ejemplo: frames de TreeGen** tiene ahora **21 nodos y 21 conexiones**. Cambios respecto
del corte anterior:

| Antes | Ahora |
|---|---|
| `foliage` = `Copy Variants` (malla) | `foliage` = `HISM Output` (instancias) |
| `Foliage Color` + `Final Merge` | eliminados: el follaje ya no vuelve a la malla |
| — | `wood_uv` = `UV Scale` u=2, v=6 sobre el canal 0 |
| — | `wood_material` = `Material` explícito |

El material del ejemplo es
`/Engine/EngineDebugMaterials/VertexColorMaterial.VertexColorMaterial`: es portable, demuestra la
asignación explícita **y** conserva visible el marrón `#76502F` que pinta el nodo `Color`. Por eso
`tree_asset` lleva `show_vertex_colors: false`; el material ya no es implícito, se elige a mano.

## Verificación

- Suite Python headless: **105/105 correctos**.
- Verificado en Unreal 5.7.4 real: `UV Scale`, `Material` y `Mesh to Static` corren sin error (ver
  la corrección de nombres de API más abajo).
- Pruebas nuevas: clonado y validación de `UV Scale`; asignación de slot, errores de carga y
  desplazamiento de IDs del `Merge`; material explícito ganándole al Vertex Color en `to_static`;
  agrupación de HISM por variante con una instancia por frame; `inherit_scale` on/off; destrucción del
  actor ante una variante inexistente; validaciones de entrada; publicación del actor runtime por el
  wrapper de `tools`.
- El ejemplo empaquetado se compila entero por Preflight y se afirma nodo por nodo y arista por
  arista, incluido que nada consume la salida `H`.
- Cobertura del spec: `in_name`/`out_name`/`aridad`/`asset_pin` de los tres verbos, y que
  `hism_output` no aparece en la Dash Bar ni en `SIN_SPAWN`.

## Corrección 2026-07-27 — los nombres de la API estaban mal y la suite no podía verlo

El primer Run real falló en `UV Scale`:

```text
[n24·mesh_uv_scale] AttributeError:
    type object 'GeometryScript_UVs' has no attribute 'scale_mesh_uvs'
```

El mangler de nombres de UE **parte las siglas**: `ScaleMeshUVs` no es `scale_mesh_uvs` sino
`scale_mesh_u_vs` (`UVs` → `U` + `Vs`), y `ClearMaterialIDs` es `clear_material_i_ds`
(`IDs` → `I` + `Ds`). `ID` suelto no se parte, por eso `get_max_material_id` sí es correcto.

Los tres nombres de este bloque estaban mal:

| Se llamaba | Se llama |
|---|---|
| `GeometryScript_UVs.scale_mesh_uvs` | `scale_mesh_u_vs` |
| `GeometryScript_Materials.clear_material_ids` | `clear_material_i_ds` |
| `GeometryScript_Materials.remap_material_ids` | `remap_material_i_ds` |

Los dos de materiales eran **latentes**: `merge` sólo llama a `remap` cuando alguna entrada ya tiene
material, y `assign_material` nunca llegó a correr por la cascada del primer error.

**La suite no podía detectarlo**: mockea `unreal`, así que un nombre inventado pasa verde. Era el
hueco que quedaba anotado como «falta la prueba en el editor real».

### El verificador

`tools/check_unreal_api.py` extrae cada `unreal.Clase.metodo` del código de Jam y comprueba contra un
editor vivo que exista, sugiriendo el candidato correcto por comparación sin guiones bajos:

```bash
UnrealEditor-Cmd <proyecto>.uproject -run=pythonscript \
    -script=<plugin>/tools/check_unreal_api.py -RenderOffScreen -unattended -nosplash -stdout
```

Encontró **4** rotos sobre 47 llamadas. El cuarto no era de este bloque: `materials.py` llamaba
`unreal.MaterialInstanceDynamic.create`, que no existe en Python (la fábrica es
`MaterialLibrary.create_dynamic_material_instance`). Estaba dentro de un `try/except` que devolvía el
material base, así que **los fantasmas y el gizmo venían saliendo opacos y sin color en silencio**.

`test_unreal_api_names.py` prueba el extractor headless y prohíbe las formas mal manglelizadas tanto
en el código como **en los stubs de la suite** — si un stub se escribe con el nombre malo, el test
verde vuelve a mentir.

### Prueba manual recomendada

1. Abrir el ejemplo y pulsar `✓ Compile`: sin errores.
2. `Run graph`: aparecen el actor `prev_*` del árbol y el actor `Jam_HISM_TreeGen_Foliage` con dos
   componentes HISM.
3. Comprobar en el StaticMesh generado que el slot 0 es el material asignado por el nodo, no el
   fallback de Vertex Color.
4. `Discard`: deben desaparecer los dos actores y el asset temporal.
5. `Run` + `Bake`: ambos actores quedan como `bake_*` y el asset se promueve.

## Archivos principales

- `Content/Python/jam/mesh.py`: `uv_scale`, `assign_material`, sidecar `_MESH_MATERIALS` y sections
  en `merge`/`to_static`.
- `Content/Python/jam/instances.py`: `from_selection` (HISM por variante).
- `Content/Python/jam/tools.py`: registro, wrappers, contratos `M`/`AF`/`H` e iconos.
- `Source/JamEditor/Private/SJamGraphEditor.cpp`: color del tipo `H`.
- `Resources/Examples/TreeGen-Curve-Frames.jamgraph`: ejemplo recableado.
- `Content/Python/tests/test_mesh.py`: regresiones del bloque.
- `Content/Python/jam/materials.py`: fábrica correcta de la instancia dinámica (fantasmas con color).
- `tools/check_unreal_api.py`: verificador de nombres de API contra un editor vivo.
- `Content/Python/tests/test_unreal_api_names.py`: extractor + prohibición de las formas mal
  manglelizadas, en el código y en los stubs.

## Cuánto falta en esta etapa TreeGen

Al escribir esta nota quedaba **un** bloque de los dos que listaba
[[TreeGen - Asset Set Choose Asset y Copy Variants]]: el ejemplo final de dos niveles y los presets.
También se cerró, en [[TreeGen - ejemplo de dos niveles y presets de Graph]]; **la etapa TreeGen está
terminada**.

Lo que sigue abierto no es de TreeGen sino del Graph en general: `Range`/`Remap` como verbos
generales, UV por sección (hoy `UV Scale` es global a la malla) y un verbo que consuma `H` si alguna
vez el HISM debe alimentar otra etapa.

## Relacionado

- [[TreeGen - Asset Set Choose Asset y Copy Variants]]
- [[TreeGen - Graph Curve N array y Pipe with Profile]]
- [[TreeGen - Copy Mesh to Frames A mas F a M]]
- [[TreeGen - auditoria de Blueprints funciones y flow real]]
- [[Tarea - Preview transaccional y efectos de PCG]]
- [[TreeGen - ejemplo de dos niveles y presets de Graph]]
- [[Oraculo de forma - comparar contra la malla de referencia]]
