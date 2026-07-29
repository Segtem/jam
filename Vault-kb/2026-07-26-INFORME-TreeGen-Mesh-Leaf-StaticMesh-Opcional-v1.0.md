---
title: "TreeGen: Mesh Leaf con StaticMesh opcional"
tipo: INFORME
version: "1.0"
aliases:
  - "Leaf Asset opcional"
  - "Fronda real en Jam Graph"
tags:
  - jam
  - graph
  - treegen
  - foliage
  - static-mesh
status: implementado
date: 2026-07-26
updated: 2026-07-26
---

# TreeGen: Mesh Leaf con StaticMesh opcional

## Resultado

`Mesh Leaf` pasó de ser sólo un generador de hojas estilizadas a tener el contrato:

```text
S (curva o CurveSet) ───────────────→ Mesh Leaf ─→ M
Asset / Pick ── A opcional ─────────↗
```

- Sin `A`: conserva exactamente el fallback procedural portable.
- Con `A`: copia la geometría del StaticMesh conectado y la distribuye en todos los frames de `S`.
- El pin no es obligatorio; Preflight sólo exige resolverlo cuando se conecta o se especifica un
  asset local.
- Una conexión `Text → A` sigue siendo inválida: debe pasar primero por `Asset`.

## Por qué hacía falta

TreeGen no genera una hoja simple en cada spawn. Sus ejemplos instancian frondas completas como
`PineFrond`, `TreeLeaves` o `BambooLeaf_01/02/03`. La jerarquía `Trunk → Branch → Leaf` ya estaba
replicada en Jam, pero sin una entrada de mesh real la silueta sólo podía aproximarse.

## Controles nuevos

| Parámetro | Función |
|---|---|
| `asset_scale` | escala uniforme previa de la fronda importada |
| `asset_pitch` | corrección del pitch local antes de distribuir copias |
| `asset_yaw` | corrección del yaw local |
| `asset_roll` | corrección del roll local |

La corrección se aplica una sola vez sobre la plantilla copiada. Luego cada instancia se orienta con
su eje X local en la dirección calculada por `Mesh Leaf`. `size_start/end`, `scale_jitter` e
`inherit_scale` continúan variando el tamaño por frame.

En modo asset, `length` y `width` no deforman la fronda: se preservan sus proporciones y se usa escala
uniforme. `double_sided` sólo duplica el fallback planar; una fronda real debe resolver las dos caras
en su propia geometría o material.

## Uso con las frondas locales de TreeGen

El plugin inspeccionado es content-only de Unreal 4.24 y Jam no redistribuye sus assets. Para una
prueba local:

1. Importar en BotOO el archivo
   `/home/workstation/Dev/games/unreal/TreeGen/Content/Examples/Meshes/PineFrond.fbx`.
2. Arrastrar un nodo `Asset` y elegir el StaticMesh importado, o seleccionarlo en Content Browser y
   usar `Pick`.
3. Conectar su salida `A` al pin lateral `A` de `Mesh Leaf`.
4. Conectar la misma salida a los Leaf de tronco y ramas si ambos deben usar `PineFrond`.
5. Empezar con `asset_scale=1`; corregir orientación con `asset_pitch/yaw/roll` según el eje de
   importación.

La inspección del FBX dio una caja aproximada de `132 × 162 × 73 cm`, así que `asset_scale=1` es un
buen punto de partida. Los actores originales varían la rotación Z a lo largo del padre: `Leaf2`
(tronco) parte cerca de `-90°`, y `Leaf1` (ramas) recorre aproximadamente `-120°…-180°`. Como primer
ajuste en Jam se puede probar `asset_yaw=-90` en el Leaf del tronco y `asset_yaw=-150` en el Leaf de
ramas; después afinar `splay`, `lift` y los jitter visualmente.

El ejemplo portable `TreeGen-Branched-Tree.jamgraph` se mantiene sin Asset para que Compile y Run
funcionen en cualquier proyecto. El pin nuevo permite reemplazar el fallback sin cambiar el resto de
la estructura.

## Verificación

- Suite headless: **62/62** pruebas aprobadas.
- Preflight cubre Leaf sin asset y Leaf con `Asset → A`.
- Unreal Engine 5.7.4 confirmó en runtime:
  - `asset_pin=true` en el spec;
  - presencia de los cuatro parámetros de transform;
  - 8 copias en el fallback procedural de prueba;
  - 4 copias de una StaticMesh real de prueba;
  - el modo StaticMesh no duplicó copias aunque `double_sided=true`.

## Archivos

- `Content/Python/jam/graph.py`: resolución de assets opcionales en Compile.
- `Content/Python/jam/tools.py`: contrato del pin `A`, parámetros y wrapper.
- `Content/Python/jam/mesh.py`: copia y distribución del StaticMesh/fallback.
- `Content/Python/tests/test_graph_preflight.py`: regresiones de preflight.
- `Content/Python/tests/test_mesh.py`: spec y geometría de ambos modos.

## Pendiente TreeGen

- Entrada de lista de StaticMeshes y selección por seed, equivalente a `Meshes[]`.
- Preservar o reasignar materiales/slots de follaje al pasar por `Mesh Merge → To Static`.
- Un preset de pino que use `PineFrond` cuando el asset exista, sin romper la versión portable.

## Relacionado

- [[2026-07-26-INFORME-TreeGen-Replica-Jerarquica-Branch-Leaf-v1.0|TreeGen: réplica jerárquica de Branch y Leaf]]
- [[2026-07-26-INFORME-TreeGen-Mesh-From-Asset-Along-Curve-v1.0|TreeGen: Mesh From Asset y Mesh Along Curve]]
- [[2026-07-26-INFORME-Graph-Tab-Mesh-Verbos-Malla-v1.0|Tab Mesh y verbos de malla]]
