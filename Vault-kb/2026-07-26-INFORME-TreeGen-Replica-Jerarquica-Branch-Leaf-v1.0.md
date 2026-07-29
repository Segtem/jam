---
title: "TreeGen: réplica jerárquica real de Branch y Leaf"
tipo: INFORME
version: "1.0"
aliases:
  - "Curve Branches"
  - "Mesh Leaf"
tags:
  - jam
  - graph
  - treegen
  - procedural-mesh
  - foliage
status: implementado
date: 2026-07-26
updated: 2026-07-26
---

# TreeGen: réplica jerárquica real de Branch y Leaf

## Por qué el árbol anterior parecía hecho de listones

La captura `ScreenShot00007.png` reveló que el ejemplo anterior no estaba reproduciendo el sistema
de follaje de TreeGen. Usaba `/Engine/BasicShapes/Plane.Plane`: una tarjeta cuadrada cuyo eje X local
se alineaba con la tangente de la rama. Al escalar X a `1.6` e Y a `0.42`, cada copia se convertía en
un rectángulo largo pegado a la rama.

TreeGen no usa ese Plane como follaje en sus árboles de ejemplo. Su Blueprint `Leaf` instancia mallas
de follaje completas con el pivote en la base:

- `TreeLeaves` para el abedul;
- `PineFrond` para el pino;
- `BambooLeaf_01/02/03` para el bambú;
- `PalmFrond_01/02` para la palmera.

Los FBX disponibles confirman que no son quads: `PineFrond` tiene 61 vértices y 41 polígonos;
`BambooLeaf_01` tiene 34 vértices y 19 polígonos. Cada asset ya es un pequeño racimo/fronda con
volumen y orientación propios.

## Qué hace realmente TreeGen

`/home/workstation/Dev/games/unreal/TreeGen` es un plugin content-only de Unreal 4.24. No tiene un
módulo C++ para portar: la implementación vive en Blueprints y `ProceduralMeshComponent`.

La jerarquía es:

```text
Trunk (Spline + mesh + transforms)
  ├─ Branch (N curvas/mallas + transforms hijas)
  │    └─ Leaf (N frondas por cada rama)
  └─ Leaf (frondas directamente sobre el tronco)
```

### Trunk

- Barre secciones radiales a lo largo de un `SplineComponent`.
- Expone `BaseRadius`, `Radius Segments` y `Length Segments`.
- Conserva transforms, tangentes, normales y radio para que los hijos se anclen sobre la superficie.

### Branch

- Recorre todos los transforms que produce el padre.
- Genera `Spawn Count` ramas dentro de `Parent Range`.
- Varía `Length Min Max`, rotación y escala con un `RandomStream` determinista.
- Usa `Rotation Per Index` para repartir las ramas alrededor del padre.
- `Scale/ParentLength` permite que las ramas se reduzcan hacia la copa.
- Produce nueva geometría y otra lista de transforms para la siguiente generación.

### Leaf

- Recorre todos los objetos del padre; no recibe una sola curva aislada.
- Selecciona aleatoriamente una malla de `Meshes[]`.
- Controla `Spawn Count`, `Parent Range`, radio, rotación, escala y `Rotate Per Index`.
- Puede heredar la escala del padre.
- Puede dibujar instancias HISM o incorporar las copias a la malla procedural final.

## Parámetros recuperados del pino del mapa de TreeGen

Se montó temporalmente el contenido 4.24 en Unreal 5.7 y se inspeccionaron los actores de
`/TreeGen/ExampleMap` sin modificar el proyecto original.

| Actor | Parámetros observados |
|---|---|
| `Trunk` | BaseRadius `68.106`, Radius Segments `16`, Length Segments `32` |
| `Branch` | Spawn Count `64`, Parent Range `0.20–0.92`, Length `300–400`, Radius Segments `4`, Length Segments `8` |
| `Leaf2` sobre tronco | Spawn Count `20`, Parent Range `0.14–0.98`, Rotate Per Index `137`, mesh `PineFrond` |
| `Leaf1` sobre ramas | Spawn Count `4` por rama, Parent Range `0.11–0.81`, Rotate Per Index `180`, Inherit Scale `true`, mesh `PineFrond` |

Esto explica por qué tres ramas manuales con planes no podían parecerse al original: TreeGen procesa
una lista de 64 ramas y coloca frondas completas tanto en el tronco como en cada rama.

## Implementación en Jam

### `CurveSet` por el pin S

El tipo visual `S` ahora puede transportar una sola `CurvePath` o un `CurveSet`. Es la semántica de
lista esperable en un graph inspirado en Grasshopper: un cable puede llevar muchas ramas sin crear
64 nodos duplicados.

`Mesh Pipe` y `Mesh Along Curve` se actualizaron para recorrer todas las curvas del conjunto.

### Nodo `Curve Branches` (`S → S`)

Genera múltiples ramas por cada curva padre con:

- `count`, `start`, `end`;
- `length_min/max`;
- `parent_scale_start/end` para taper de copa y radio;
- `angle`, `angle_jitter`;
- `rotate_per_index`, `azimuth`, `azimuth_jitter`;
- `bend`, `bend_jitter`, `radial_offset`;
- `segments`, `samples`, `seed`.

El seed usa un PRNG local: recompilar no cambia el árbol.

### Nodo `Mesh Leaf` (`S + A opcional → M`)

Es el equivalente portable de `Leaf` y ahora tiene dos modos. Sin conectar `A`, genera una hoja
lanceolada de ocho puntos con pivote en la base. Conecta un nodo `Asset` o `Pick` al nuevo pin `A` y
el nodo copia esa `StaticMesh` como fronda, conservando el flujo jerárquico por `S`. El asset es
opcional: Compile no rechaza el fallback, pero sí valida cualquier asset que se haya especificado.

Parámetros principales:

- distribución: `count`, `start/end`, `radial_offset`, `rotate_per_index`;
- racimo: `leaves_per_cluster`, `splay`, `lift`;
- forma procedural: `length`, `width`, `size_start/end`;
- fronda importada: `asset_scale` y corrección local `asset_pitch/yaw/roll`;
- variación: `rotation_jitter`, `scale_jitter`, `offset_jitter`, `seed`;
- jerarquía/render: `inherit_scale`, `double_sided`.

`double_sided` duplica sólo la hoja procedural. Una StaticMesh real conserva sus caras y material, de
modo que Jam no duplica toda su geometría. Esto evita z-fighting y coincide mejor con las frondas de
TreeGen, donde el material de follaje controla el render a dos caras.

Para probar la geometría original en BotOO, importar desde el Content Browser el FBX local:

```text
/home/workstation/Dev/games/unreal/TreeGen/Content/Examples/Meshes/PineFrond.fbx
```

Luego crear `Asset` o usar `Pick`, conectarlo al `A` de ambos `Mesh Leaf` y ajustar primero
`asset_scale`; si la nervadura no sale hacia la rama, corregir el eje con `asset_pitch/yaw/roll`.
Jam no copia ni redistribuye automáticamente ese asset del plugin 4.24.

El FBX mide aproximadamente `132 × 162 × 73 cm`; `asset_scale=1` conserva la escala usada por el
plugin. Como valores iniciales de orientación, probar `asset_yaw=-90` en las hojas del tronco y
`asset_yaw=-150` en las hojas de ramas, derivados de los rangos observados en `Leaf2` y `Leaf1`.

## Ejemplo actualizado

`Resources/Examples/TreeGen-Branched-Tree.jamgraph` ahora sigue la estructura real:

```text
Curve Bezier ─┬→ Mesh Pipe (tronco) ───────────────┐
              ├→ Curve Branches (64) → Mesh Pipe ─┼→ madera
              ├→ Mesh Leaf (20) ──────────────────┐
              └→ Curve Branches → Mesh Leaf (4) ──┴→ follaje

madera + follaje → Merge → Normals → To Static → Place
```

La lista de ramas usa el rango `0.20–0.92`, longitudes `300–400` y giro `137°`. El follaje del tronco
usa 20 racimos; cada rama recibe 4, como el pino inspeccionado. `parent_scale_end=0.32` y
`inherit_scale=true` reducen ramas y hojas hacia la copa.

## Verificación

- Suite Python: **62/62** pruebas aprobadas.
- Unreal Engine 5.7.4: **14/14** nodos del ejemplo en estado `ok`.
- Preview y Bake promovieron `/Game/Jam/Meshes/SM_TreeGen_Branched_Test`.
- Un Run posterior y Discard conservaron el actor y asset bakeados.
- Bounds medidos: aproximadamente `792 × 727 × 672 cm`.
- Material de visualización: `VertexColorMaterial`, con madera y follaje coloreados por vértice.
- Export visual de control: 16.996 triángulos; confirmó ramas radiales y hojas con silueta, sin los
  listones rectangulares de la captura anterior.
- Unreal Engine 5.7.4, prueba aislada del nuevo modo: el fallback produjo 8 copias y una StaticMesh
  conectada produjo 4 copias reales; el spec confirmó el pin `A` y los cuatro controles de transform.

## Diferencia deliberada respecto del plugin antiguo

Jam replica el comportamiento jerárquico y la distribución, no copia sus Blueprints ni sus `.uasset`.
`Mesh Leaf` admite una StaticMesh de follaje propia, y el flow modular ya acepta una **lista** de
meshes mediante `Asset Set`, selección determinista mediante `Choose Asset` y copiado mediante
`Copy Variants`. Aún falta conservar/asignar sus materiales de follaje al producir el StaticMesh
final.

## Archivos

- `Content/Python/jam/curve.py`: `CurveSet` y `curve.branches`.
- `Content/Python/jam/mesh.py`: Pipe/Along sobre listas y `mesh.leaf`.
- `Content/Python/jam/tools.py`: registro, tipos y parámetros de los dos nodos.
- `Resources/Examples/TreeGen-Branched-Tree.jamgraph`: ejemplo jerárquico actualizado.
- `Content/Python/tests/test_mesh.py`: regresiones de listas, taper y racimos.

## Relacionado

- [[2026-07-26-INFORME-TreeGen-Curvas-Pipe-Arbol-Ramificado-v1.0|TreeGen: curvas, Pipe y árbol]]
- [[2026-07-26-INFORME-TreeGen-Curve-Child-Ramas-Jerarquicas-v1.0|TreeGen: Curve Child]]
- [[2026-07-26-INFORME-TreeGen-Mesh-From-Asset-Along-Curve-v1.0|TreeGen: Mesh From Asset y Mesh Along Curve]]
- [[2026-07-26-INFORME-TreeGen-Follaje-Procedural-Variacion-v1.0|TreeGen: follaje procedural]]
- [[2026-07-27-INFORME-TreeGen-Asset-Set-Choose-Copy-Variants-v1.0|TreeGen: Asset Set, Choose Asset y Copy Variants]]
- [[2026-07-26-INFORME-Graph-Tab-Mesh-Verbos-Malla-v1.0|Tab Mesh y verbos de malla]]
