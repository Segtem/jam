---
title: "TreeGen: Transform Frames F"
aliases:
  - "Transform Frames"
tags:
  - jam
  - graph
  - treegen
  - frames
  - transform
status: implementado
date: 2026-07-27
---

# TreeGen: Transform Frames F

## Resultado

Se implementó **Transform Frames `F → F`**, el tercer bloque modular del flow de TreeGen. Permite
desplazar, orientar y escalar cada frame en su sistema local, con valores base y variaciones
deterministas independientes.

```text
Curve S
  → Curve Frames F
  → Distribute Frames F
  → Transform Frames F
       ├─ local offset
       ├─ yaw / pitch / roll
       ├─ scale + inherit scale
       └─ jitter por frame
```

## Sistema de coordenadas local

Cada `CurveFrame` se interpreta como una base ortonormal:

| Eje | Origen | Uso habitual |
|---|---|---|
| `X` | `tangent` | avance longitudinal sobre la rama |
| `Z` | `outward` | separación radial respecto del tronco/rama |
| `Y` | `Z × X` | desplazamiento lateral |

Los parámetros `offset_x/y/z` operan sobre esos ejes. Esto evita el problema de aplicar offsets en
World Space: la misma transformación funciona aunque la rama padre esté inclinada o girada.

Las rotaciones se componen sobre la base local actual:

- `yaw`: alrededor de `Z`;
- `pitch`: alrededor de `Y`;
- `roll`: alrededor de `X`.

Después de rotar, `tangent` y `outward` se normalizan y reortogonalizan para que los consumidores no
reciban una base deformada por error numérico.

## Escala y herencia

`scale` es un multiplicador uniforme. Con `inherit_scale=true`:

- la escala resultante es `frame.scale × scale`;
- los offsets locales también se multiplican por `frame.scale`.

Con `inherit_scale=false`, el nodo ignora la escala de entrada para esos dos cálculos. El `radius` se
conserva porque describe el radio del padre, no el tamaño del objeto que se copiará sobre el frame.

`scale_jitter` debe ser menor que `scale`; así ningún frame puede resultar degenerado o invertido.

## Variación determinista

Cada componente posee un rango simétrico opcional:

- `offset_jitter_x/y/z`;
- `pitch_jitter`, `yaw_jitter`, `roll_jitter`;
- `scale_jitter`.

La semilla de salida combina el `seed` del nodo con `frame.seed`, `parent_index` y `local_index`. El
mismo graph produce exactamente la misma transformación, pero cada frame recibe su propia variación.

Se preservan:

- `parent_index` y `local_index`;
- `parameter` y `radius`;
- `pivot_index`;
- `parent_count` del `FrameSet`.

## Integración en Jam Graph

- Nodo Graph-only dentro del tab `Mesh`.
- Entrada `F` y salida `F`, con el color rosa del Frame Stream.
- Icono Lucide `move-3d` en gris oscuro.
- El resultado se publica como dato runtime y puede encadenarse con futuros consumidores `F`.
- `inherit_scale` aparece como parámetro booleano.

El ejemplo accesible desde **File → Abrir ejemplo: frames de TreeGen** ahora contiene:

```text
Curve Bezier → Curve Frames → Distribute Frames → Transform Frames
```

Run evalúa los cuatro nodos y el último informa `TRANSFORM F ✓ — 18 frames`.

## Validación

- **72/72 pruebas Python correctas**.
- Offsets locales comprobados sobre una curva vertical.
- Rotación y reortogonalización verificadas.
- Herencia de escala activada y desactivada.
- Jitters reproducibles, límites y errores de escala degenerada.
- Ejecución integral `S → F → F → F` mediante el runner real de Jam Graph.
- Spec, JSON, icono Lucide y `git diff --check` correctos.
- No hubo cambios C++ en este corte: Jam construye el nodo desde el spec Python dinámico.

## Continuación implementada

**Branch From Frames `F → S`** ya crea una curva hija por frame usando la base transformada, conserva
jerarquía, escala y semilla, y permite longitud, ángulo, curl y segmentos. Con ese nodo el flow modular
vuelve a producir curvas que `Mesh Pipe` consume. Véase [[TreeGen - Branch From Frames F a S]].

## Relacionado

- [[TreeGen - Curve Frames y contrato FrameStream F]]
- [[TreeGen - Distribute Frames F]]
- [[TreeGen - Branch From Frames F a S]]
- [[TreeGen - auditoria de Blueprints funciones y flow real]]
- [[TreeGen - replica jerarquica real de Branch y Leaf]]
