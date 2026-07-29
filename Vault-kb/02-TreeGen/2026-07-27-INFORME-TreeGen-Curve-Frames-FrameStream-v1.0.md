---
title: "TreeGen: Curve Frames y contrato FrameStream F"
tipo: INFORME
version: "1.0"
aliases:
  - "Curve Frames"
  - "FrameStream F"
tags:
  - jam
  - graph
  - treegen
  - frames
  - procedural-mesh
status: implementado-base
area: 02-TreeGen
date: 2026-07-27
updated: 2026-07-27
---

# TreeGen: Curve Frames y contrato FrameStream F

## Resultado

Se implementó el primer bloque del flow modular de TreeGen: **Curve Frames**, un nodo `S → F` que
convierte una curva o colección de curvas en frames jerárquicos. El dato `F` queda tipado en Compile,
viaja en memoria durante Run y tiene color e icono propios en Jam Graph.

Este nodo no genera una malla por sí solo. Su objetivo es dejar visible y reutilizable la información
que TreeGen transporta internamente entre Trunk, Branch y Leaf. Sobre este contrato se implementarán
`Distribute Frames`, `Transform Frames` y `Branch From Frames`.

```text
Curve Bezier S
      │
      ▼
Curve Frames F
  ├─ posición + tangent + outward
  ├─ t sobre la curva
  ├─ parent_index + local_index
  ├─ scale + radius
  └─ seed + pivot_index
```

## Contrato implementado

`CurveFrame` conserva los datos geométricos existentes y agrega metadata de flow:

| Campo | Uso |
|---|---|
| `position` | posición del frame en espacio de la curva |
| `tangent` | dirección longitudinal |
| `outward` | eje exterior estable, incluso en curvas verticales |
| `parameter` | parámetro normalizado dentro de `start → end` |
| `parent_index` | curva padre dentro del `CurveSet` |
| `local_index` | muestra dentro de esa curva padre |
| `scale` | escala heredada de la curva padre |
| `radius` | radio interpolado y afectado por la escala padre |
| `seed` | semilla determinista por padre y muestra |
| `pivot_index` | índice global estable para jerarquía/Pivot Painter futuro |

`FrameSet` es una colección inmutable con `frames` y `parent_count`. Si entra un `CurveSet`, el nodo
samplea cada curva y conserva su procedencia; no aplana la jerarquía de manera irreversible.

## Parámetros de Curve Frames

- `count`: muestras por cada curva padre, de 1 a 512;
- `start` / `end`: dominio normalizado, con `0 ≤ start ≤ end ≤ 1`;
- `radial_offset`: desplazamiento desde el eje de la curva;
- `turns` / `angle_offset`: rotación del eje exterior alrededor de la tangente;
- `radius_start` / `radius_end`: metadata de taper para consumidores posteriores;
- `samples`: resolución usada al leer una spline de Unreal;
- `seed`: origen determinista para variaciones posteriores.

El nodo limita la salida a 4096 frames para evitar expansiones accidentales.

## Interfaz y ejemplo

- El pin/cable `F` usa un rosa oscuro distinto de `S`, `M`, `A` y `P`.
- El nodo usa el icono Lucide `axis-3d` en gris oscuro, igual que el resto de los nodos.
- Se agregó `Resources/Examples/TreeGen-Curve-Frames.jamgraph`.
- Se puede abrir desde **File → Abrir ejemplo: frames de TreeGen**.

El ejemplo contiene `Curve Bezier → Curve Frames`. Compile valida el tipado y Run debe reportar
`FRAMES F ✓ — 12 frames/1 curvas`. Conectar ese `F` a un consumidor `S`, por ejemplo `Mesh Pipe`, es
rechazado explícitamente con `esperaba S, recibió F`.

## Archivos modificados

- `Content/Python/jam/curve.py`: `FrameSet`, metadata de `CurveFrame` y `frame_stream`.
- `Content/Python/jam/tools.py`: runtime, registro y contrato `S → F` de `curve_frames`.
- `Source/JamEditor/Private/SJamGraphEditor.cpp`: color `F` y acceso al ejemplo.
- `Source/JamEditor/Public/SJamGraphEditor.h`: acción del ejemplo.
- `Resources/Icons/Lucide/icon-map.json`: icono del nodo.
- `Resources/Examples/TreeGen-Curve-Frames.jamgraph`: diagrama mínimo.
- `Content/Python/tests/test_mesh.py`: jerarquía, validación, runtime, spec y tipado.

## Validación

- Suite Python: **66/66 pruebas correctas**, incluida la publicación runtime del `FrameSet`.
- `BotOOEditor Linux Development`, Unreal Engine 5.7: compilación correcta.
- Se compilaron y enlazaron `Module.JamEditor.cpp` y `libUnrealEditor-JamEditor.so`.

## Continuación implementada

**Distribute Frames `F → F`** ya filtra el rango de cada padre y **Transform Frames `F → F`** ya
aplica posición, rotación y escala locales con variación determinista. Véanse
[[2026-07-27-INFORME-TreeGen-Distribute-Frames-v1.0|TreeGen: Distribute Frames]] y [[2026-07-27-INFORME-TreeGen-Transform-Frames-v1.0|TreeGen: Transform Frames]]. El siguiente corte es
**Branch From Frames `F → S`**, que ya está implementado en
[[2026-07-27-INFORME-TreeGen-Branch-From-Frames-v1.0|TreeGen: Branch From Frames]].

## Relacionado

- [[2026-07-27-INFORME-TreeGen-Auditoria-Blueprints-Flow-Real-v1.0|TreeGen: auditoría de Blueprints y flow real]]
- [[2026-07-27-INFORME-TreeGen-Distribute-Frames-v1.0|TreeGen: Distribute Frames]]
- [[2026-07-27-INFORME-TreeGen-Transform-Frames-v1.0|TreeGen: Transform Frames]]
- [[2026-07-27-INFORME-TreeGen-Branch-From-Frames-v1.0|TreeGen: Branch From Frames]]
- [[2026-07-26-INFORME-TreeGen-Replica-Jerarquica-Branch-Leaf-v1.0|TreeGen: réplica jerárquica de Branch y Leaf]]
- [[2026-07-26-INFORME-Graph-Tab-Mesh-Verbos-Malla-v1.0|Tab Mesh y verbos de malla]]
