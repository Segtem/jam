---
title: "TreeGen: Graph Curve N[] y Pipe with Profile"
tipo: INFORME
version: "1.0"
aliases:
  - "Taper no lineal TreeGen"
  - "Pipe with Profile"
  - "Graph Curve N[]"
tags:
  - jam
  - graph
  - treegen
  - taper
  - procedural-mesh
  - scalar-field
status: implementado
area: 02-TreeGen
date: 2026-07-27
updated: 2026-07-27
---

# TreeGen: Graph Curve N[] y Pipe with Profile

## Resultado

Se eliminó la restricción que obligaba a todos los pipes de Jam a interpolar linealmente entre dos
radios. El nuevo flow es explícito y modular:

```text
Graph Curve N[] ───────────→ profile
                                │
Curve S ─────────→ Pipe with Profile ─────────→ Mesh M
```

El `Mesh Pipe` anterior permanece disponible y conserva exactamente su contrato lineal. Los graphs
existentes no necesitan migración.

## Graph Curve N[]

`Graph Curve` es un nodo fuente que genera una serie numérica inmutable sobre el dominio 0..1. Sus
modos son:

- `linear`: interpolación directa;
- `ease_in`: conserva más volumen al inicio y acelera el taper hacia el extremo;
- `ease_out`: reduce el volumen con más fuerza al inicio;
- `smooth`: smoothstep continuo entre extremos;
- `custom`: pasa por un punto intermedio editable con dos tramos suaves.

Parámetros principales:

- `start_value` y `end_value`: multiplicadores en los extremos;
- `power`: exponente de `ease_in/ease_out`;
- `midpoint` y `mid_value`: control intermedio de `custom`;
- `samples`: entre 2 y 256 muestras.

La salida `N[]` es genérica. Aunque el primer consumidor es el radio de un pipe, queda preparada para
futuros falloffs de distribución, escala, densidad o atributos.

## Pipe with Profile

`Pipe with Profile` recibe `S` por el pin principal y exige `N[]` por el pin lateral `profile`.
`radius` define el radio base y cada muestra calcula:

```text
radio local = radius × escala heredada de la curva × valor de Graph Curve
```

A diferencia de `AppendSimpleSweptPolygon`, que sólo acepta escalas inicial/final, el nodo usa
`AppendSweepPolygon` con un transform y una escala transversal por punto. Los frames se transportan
a lo largo de la curva para evitar saltos de orientación. El perfil se interpola por distancia de
arco, no simplemente por índice.

Validaciones:

- el pin `profile` debe estar conectado y ser `N[]`;
- los valores de radio deben ser finitos y no negativos;
- el perfil no puede ser completamente cero;
- se mantienen los límites de lados, samples y miter del pipe anterior.

## Interfaz Graph

- `N[]` tiene pin y cable ámbar claro, distinto de un único número `N`.
- Compile rechaza `N → profile` y explica `esperaba N[], recibió N`.
- Los dos nodos usan iconos Lucide existentes: `chart-spline` y `route`.
- El soporte de parámetros laterales tipados implementado para `A[]` se reutiliza sin excepciones
  especiales para el perfil.

## Ejemplo TreeGen actualizado

**File → Abrir ejemplo: frames de TreeGen** contiene ahora 21 nodos y 22 conexiones:

- tronco: perfil `custom`, `1 → 0.24`, control `0.58 : 0.72`, radio base 52 cm;
- ramas: perfil `ease_in`, `1 → 0.10`, power 1.8, radio base 12 cm;
- variantes de follaje y flow de frames permanecen conectados como antes.

Esto permite que el tronco mantenga masa en su zona media y que las ramas conserven grosor cerca del
nacimiento antes de afinarse con rapidez hacia las puntas.

## Validación

Prueba real en Unreal Engine 5.7 / `BotOOEditor`:

- Compile: **21 nodos correctos**.
- Graph Curve del tronco: 17 muestras, perfil custom correcto.
- Graph Curve de ramas: 13 muestras, perfil ease-in correcto.
- Trunk Pipe: 204 vértices.
- Branch Pipe: 18 sweeps y 1.386 vértices.
- Resultado completo: **2.289 vértices**.
- Static Mesh y actor temporal creados correctamente.
- `Discard` eliminó 1 actor y 1 asset; el `.uasset` temporal no quedó en disco.
- `JamEditor` recompiló y enlazó correctamente.
- Suite Python: **83/83 pruebas correctas**.

Las regresiones verifican extremos y muestreo del perfil, interpolación, escalas por punto, inyección
real del dato `N[]`, errores de pin desconectado y rechazo de un `N` simple.

## Archivos principales

- `Content/Python/jam/fields.py`: `ScalarSeries` y generador `graph_curve`.
- `Content/Python/jam/mesh.py`: `pipe_profile` y frames de sweep escalados.
- `Content/Python/jam/tools.py`: registro, wrappers y contratos `N[]`.
- `Source/JamEditor/Private/SJamGraphEditor.cpp`: color del nuevo tipo.
- `Resources/Examples/TreeGen-Curve-Frames.jamgraph`: diagrama de prueba actualizado.
- `Content/Python/tests/test_mesh.py`: regresiones puras y de Graph.

## Pendiente después de este corte

El flow creativo básico de TreeGen ya no está bloqueado por el taper. Quedaban dos bloques:

1. ~~UV, materiales, mesh sections y salida HISM para fidelidad y rendimiento de producción.~~ Hecho:
   [[2026-07-27-INFORME-TreeGen-UV-Materiales-Sections-HISM-v1.0|TreeGen: UV, materiales, sections y HISM]].
2. ~~Ejemplo final de dos niveles de ramas y presets reutilizables para comparar con TreeGen.~~ Hecho:
   [[2026-07-27-INFORME-TreeGen-Dos-Niveles-Presets-v1.0|TreeGen: ejemplo de dos niveles]]. Con eso la etapa TreeGen quedó cerrada.

`Range` y `Remap` separados siguen siendo verbos generales valiosos, pero no son necesarios para
controlar el radio: `Graph Curve` ya cubre el corte vertical completo.

## Relacionado

- [[2026-07-27-INFORME-TreeGen-Auditoria-Blueprints-Flow-Real-v1.0|TreeGen: auditoría de Blueprints y flow real]]
- [[2026-07-27-INFORME-TreeGen-Curve-Frames-FrameStream-v1.0|TreeGen: Curve Frames y FrameStream]]
- [[2026-07-27-INFORME-TreeGen-Branch-From-Frames-v1.0|TreeGen: Branch From Frames]]
- [[2026-07-27-INFORME-TreeGen-Asset-Set-Choose-Copy-Variants-v1.0|TreeGen: Asset Set, Choose Asset y Copy Variants]]
- [[2026-07-27-INFORME-TreeGen-Copy-Mesh-To-Frames-v1.0|TreeGen: Copy Mesh to Frames]]
- [[2026-07-27-INFORME-TreeGen-UV-Materiales-Sections-HISM-v1.0|TreeGen: UV, materiales, sections y HISM]]
- [[2026-07-27-INFORME-TreeGen-Dos-Niveles-Presets-v1.0|TreeGen: ejemplo de dos niveles]]
