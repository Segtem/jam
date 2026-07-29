---
title: "TreeGen: Branch From Frames F a S"
tipo: INFORME
version: "1.0"
aliases:
  - "Branch From Frames"
tags:
  - jam
  - graph
  - treegen
  - frames
  - branches
  - procedural-mesh
status: implementado
date: 2026-07-27
updated: 2026-07-27
---

# TreeGen: Branch From Frames F a S

## Resultado

Se implementó **Branch From Frames `F → S`**. Es el primer consumidor del nuevo Frame Stream que
vuelve a producir geometría: genera una `CurvePath` por cada frame y entrega todas las ramas dentro
de un `CurveSet`, listo para `Mesh Pipe` o para otro nivel de `Curve Frames`.

```text
Curve S
  → Curve Frames F
  → Distribute Frames F
  → Transform Frames F
  → Branch From Frames S
  → Mesh Pipe M
```

## Generación de las ramas

Cada rama comienza exactamente en `frame.position` y usa la base transformada:

- `angle=0°` continúa por `tangent`;
- `angle=90°` sale por `outward`;
- valores intermedios combinan ambas direcciones;
- `curl` añade ángulo progresivamente a lo largo de la rama.

La curva se integra por segmentos. En cada paso se recalcula la dirección con el ángulo y curl
correspondientes; por eso el resultado es un arco real y no una línea recta cuyo tip fue desplazado.

## Parámetros

| Parámetro | Default | Función |
|---|---:|---|
| `length_min` | `200 cm` | longitud mínima |
| `length_max` | `400 cm` | longitud máxima |
| `angle` | `55°` | salida desde la tangente hacia el eje exterior |
| `angle_jitter` | `0°` | variación simétrica del ángulo inicial |
| `curl` | `20°` | curvatura angular acumulada |
| `curl_jitter` | `0°` | variación simétrica de la curvatura |
| `segments` | `8` | resolución de la curva, entre 2 y 128 |
| `inherit_scale` | `true` | aplica `frame.scale` a longitud y grosor posterior |
| `seed` | `7` | patrón determinista local |

El nodo admite hasta 4096 curvas por evaluación.

## Jerarquía transportada por S

`CurvePath` se amplió con metadata opcional, sin romper sus constructores existentes:

- `source_parent_index`;
- `source_local_index`;
- `seed`;
- `pivot_index`;
- `parent_radius`.

La escala heredada continúa en `CurvePath.scale`. `Mesh Pipe` ya multiplica el radio del perfil por
esa escala, por lo que ramas pequeñas reducen tanto su longitud como su grosor.

Esta metadata permitirá crear otro nivel `S → F → S` y mantener la procedencia necesaria para Pivot
Painter y selección determinista de follaje.

## Integración en Jam Graph

- Entrada `F`, salida `S`.
- Nodo Graph-only del tab `Mesh`.
- Icono Lucide `workflow` en gris oscuro.
- Publica un `CurveSet` runtime mediante el transporte de datos ricos del Graph.
- `Mesh Pipe` acepta directamente su salida y realiza un sweep por cada rama.

## Ejemplo visible

`TreeGen-Curve-Frames.jamgraph`, accesible desde **File → Abrir ejemplo: frames de TreeGen**, ahora
contiene doce nodos:

```text
Curve Bezier ─────────────────────────────→ Trunk Pipe ─┐
      ↓                                                  │
Curve Frames → Distribute → Transform → Branch From F   │
                                              ↓          │
                                         Branch Pipe ────┤
                                                         ↓
                     Merge → Color → Normals → Static Mesh → Place
```

Compile no modifica la escena. Run crea el árbol como preview visible; Bake lo fija y Discard elimina
la pieza y el asset temporal.

## Validación real en Unreal 5.7

El ejemplo completo se ejecutó dentro de `BotOOEditor`:

- Compile: **12 nodos correctos**.
- Curve Frames: 12 frames iniciales.
- Distribute/Transform: 18 frames finales.
- Branch From Frames: **18 ramas de 10 segmentos**.
- Branch Pipe: **18 sweeps y 1.386 vértices**.
- Tronco + ramas combinados: **1.590 vértices**.
- Static Mesh temporal creada y actor colocado correctamente.
- Discard eliminó **1 actor y 1 asset temporal**; se comprobó que el `.uasset` ya no existe.

Validación adicional:

- **75/75 pruebas Python correctas**.
- Reproducibilidad, curl, escala, metadata, límites y errores cubiertos.
- Cadena headless `S → F → F → F → S` verificada mediante el runner real de Jam.
- `BotOOEditor Linux Development` recompiló correctamente con Unreal 5.7.
- `Module.JamEditor.cpp` y `libUnrealEditor-JamEditor.so` enlazaron correctamente.

## Continuación implementada

**Copy Mesh to Frames `A + F → M`** ya coloca hojas, frondas o corteza sobre los frames distribuidos y
transformados. Además, `Asset Set`, `Choose Asset` y `Copy Variants` ya reproducen listas de variantes
con selección determinista por frame. Véanse [[2026-07-27-INFORME-TreeGen-Copy-Mesh-To-Frames-v1.0|TreeGen: Copy Mesh to Frames]] y
[[2026-07-27-INFORME-TreeGen-Asset-Set-Choose-Copy-Variants-v1.0|TreeGen: Asset Set, Choose Asset y Copy Variants]].

## Relacionado

- [[2026-07-27-INFORME-TreeGen-Curve-Frames-FrameStream-v1.0|TreeGen: Curve Frames y FrameStream]]
- [[2026-07-27-INFORME-TreeGen-Distribute-Frames-v1.0|TreeGen: Distribute Frames]]
- [[2026-07-27-INFORME-TreeGen-Transform-Frames-v1.0|TreeGen: Transform Frames]]
- [[2026-07-27-INFORME-TreeGen-Copy-Mesh-To-Frames-v1.0|TreeGen: Copy Mesh to Frames]]
- [[2026-07-27-INFORME-TreeGen-Asset-Set-Choose-Copy-Variants-v1.0|TreeGen: Asset Set, Choose Asset y Copy Variants]]
- [[2026-07-27-INFORME-TreeGen-Auditoria-Blueprints-Flow-Real-v1.0|TreeGen: auditoría de Blueprints y flow real]]
- [[2026-07-26-INFORME-TreeGen-Replica-Jerarquica-Branch-Leaf-v1.0|TreeGen: réplica jerárquica de Branch y Leaf]]
