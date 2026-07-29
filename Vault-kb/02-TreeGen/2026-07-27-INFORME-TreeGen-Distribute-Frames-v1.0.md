---
title: "TreeGen: Distribute Frames F"
tipo: INFORME
version: "1.0"
aliases:
  - "Distribute Frames"
tags:
  - jam
  - graph
  - treegen
  - frames
  - distribution
status: implementado
area: 02-TreeGen
date: 2026-07-27
updated: 2026-07-27
---

# TreeGen: Distribute Frames F

## Resultado

Se implementó **Distribute Frames `F → F`**, el segundo bloque modular del flow de TreeGen. Recibe un
`FrameSet`, redistribuye muestras independientemente dentro de cada padre y publica otro `FrameSet`
sin perder radio, escala ni jerarquía.

```text
Curve S → Curve Frames F → Distribute Frames F
                               ├─ rango por padre
                               ├─ cantidad por padre
                               ├─ giro por índice
                               └─ jitter determinista
```

## Comportamiento

- Agrupa la entrada por `parent_index`; nunca redistribuye todo como una lista plana.
- Ordena cada grupo por `local_index` y `parameter`.
- `count` indica cuántos frames salen **por cada padre**.
- `start/end` recortan el dominio normalizado de cada padre.
- Interpola posición, tangente, eje exterior, parámetro, escala y radio.
- Reortogonaliza `outward` respecto de la tangente después de interpolar.
- `rotate_per_index` gira el eje exterior alrededor de la tangente, útil para filotaxis.
- `angle_jitter` y `parameter_jitter` usan un PRNG local por padre/muestra.
- Regenera `local_index`, `seed` y `pivot_index` de manera estable.
- Conserva `parent_index` y el `parent_count` del stream original.

Con la misma entrada, parámetros y `seed`, el resultado es exactamente reproducible.

## Parámetros

| Parámetro | Default | Función |
|---|---:|---|
| `count` | `12` | frames de salida por padre |
| `start` | `0.0` | inicio del dominio de cada padre |
| `end` | `1.0` | final del dominio de cada padre |
| `rotate_per_index` | `137.5°` | giro acumulado entre muestras |
| `angle_offset` | `0°` | rotación base |
| `angle_jitter` | `0°` | variación angular simétrica |
| `parameter_jitter` | `0` | variación normalizada dentro del dominio |
| `seed` | `7` | patrón determinista local |

El nodo admite entre 1 y 512 frames por padre y limita el resultado total a 4096 frames.

## Integración en Jam Graph

- Registro Graph-only dentro del tab `Mesh`.
- Entrada `F` y salida `F`; usa el color rosa definido para Frame Streams.
- Icono Lucide `list-filter` en gris oscuro.
- El compilador rechaza conexiones incompatibles como `Distribute Frames F → Mesh Pipe S`.
- El resultado viaja por `_RUNTIME_DATA_OUTPUTS` y puede encadenarse con otros consumidores `F`.

El ejemplo existente se amplió a:

```text
Curve Bezier → Curve Frames → Distribute Frames
```

Se abre desde **File → Abrir ejemplo: frames de TreeGen**. Al ejecutar debe informar:

```text
DISTRIBUTE F ✓ — 18 frames/1 padres · 0.15→0.92 · giro 137.5°
```

## Validación

- **69/69 pruebas Python correctas**.
- Cobertura de múltiples padres, interpolación, radio/escala, índices y pivotes.
- Cobertura de reproducibilidad con jitter y validación de límites.
- Ejecución integral `S → F → F` a través del runner real de Jam Graph.
- Spec dinámico verificado: el nuevo nodo aparece sin cambios adicionales en C++.
- JSON del ejemplo y mapa de iconos válidos; `git diff --check` correcto.
- La última compilación `BotOOEditor Linux Development` de este bloque de UI fue correcta; este
  corte no cambió código C++ y el registro se carga dinámicamente desde Python.

## Continuación implementada

**Transform Frames `F → F`** ya separa transform base y variación, opera en ejes locales y permite
rangos deterministas de posición, rotación y escala. Véase [[2026-07-27-INFORME-TreeGen-Transform-Frames-v1.0|TreeGen: Transform Frames]]. Esa
salida queda preparada para `Branch From Frames` y `Copy Mesh to Frames`.

## Relacionado

- [[2026-07-27-INFORME-TreeGen-Curve-Frames-FrameStream-v1.0|TreeGen: Curve Frames y FrameStream]]
- [[2026-07-27-INFORME-TreeGen-Transform-Frames-v1.0|TreeGen: Transform Frames]]
- [[2026-07-27-INFORME-TreeGen-Auditoria-Blueprints-Flow-Real-v1.0|TreeGen: auditoría de Blueprints y flow real]]
- [[2026-07-26-INFORME-TreeGen-Replica-Jerarquica-Branch-Leaf-v1.0|TreeGen: réplica jerárquica de Branch y Leaf]]
