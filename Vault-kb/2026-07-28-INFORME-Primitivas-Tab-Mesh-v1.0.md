---
title: "Primitivas del tab Mesh"
tipo: INFORME
version: "1.0"
aliases:
  - "Box, cápsula, escaleras"
  - "Torno / Revolve"
  - "Primitivas de blockout"
tags:
  - jam
  - graph
  - procedural-mesh
  - blockout
status: implementado
date: 2026-07-28
updated: 2026-07-28
---

# Primitivas del tab Mesh

## Lo que faltaba

Jam tenía seis primitivas —triangle, quad, grid, cylinder, cone, sphere— y le faltaba **box**, que es
la más básica de todas. Geometry Script además regala varias que sirven directo para blockout de
nivel y no estaban expuestas.

## Las nueve nuevas

### Fuentes (`→ M`)

| Verbo | Para qué |
|---|---|
| **Box** | la caja que faltaba, con el pivote en la **base** |
| **Capsule** | la forma de blockout y colisión por excelencia |
| **Torus** | dona |
| **Disc** | disco plano; con `hole_radius` es un anillo y con los ángulos, una porción |
| **Round Rect** | rectángulo de esquinas redondeadas |
| **Stairs** | **escalera recta** — de lo que más se usa en un blockout |
| **Curved Stairs** | escalera curva; el signo de `curve_angle` elige el sentido |
| **Sphere Box** | esfera de topología cúbica: cuadrángulos parejos, sin los polos apretados de la lat/long |

Las que apoyan en el piso —box, capsule, stairs— usan `origin=BASE`, coherente con la filosofía de
anclas de Jam: una pieza con el pivote en la base es **tileable** sin corregir.

### Transformador (`S → M`)

**Revolve** — el **torno**. Revoluciona el perfil de una curva alrededor del eje Z, leyendo el perfil
en el plano XZ (`x` = distancia al eje, `z` = altura), que es como se dibuja un perfil de torno de
toda la vida.

Es la pieza **arquitectónica** que faltaba: columnas, balaustres, vasijas y molduras, que hasta ahora
había que aproximar con un pipe. Y compone con todo lo demás: `Curve Bezier → Revolve → Bark →
Material → Mesh to Static`.

Un `x` negativo se pliega sobre el eje (se toma la distancia), así que un perfil dibujado del lado
«equivocado» gira igual.

## Qué se validó

Lo que hace la geometría es Geometry Script; lo que agregan estos verbos es que **ningún parámetro
absurdo llegue al motor**, donde falla de formas raras o silenciosas:

- un toro con `minor_radius >= major_radius` cierra el agujero y se auto-interseca;
- un `corner_radius` mayor que la mitad del lado cruza las esquinas y da la malla vuelta;
- un `hole_radius` mayor que el radio, ángulos que no avanzan, escaleras de 0 o de 999 escalones;
- en el torno, un perfil **sobre el eje** no produce volumen: degenera en una línea.

## El bug que sólo apareció corriéndolo

Las ocho fuentes fallaron en el Run con:

```text
TypeError: t_mesh_box() takes 0 positional arguments but 1 positional argument were given
```

El ejecutor del Graph llama **siempre** `fn(entrada, **params)`, también a las fuentes — que ignoran
esa entrada pero tienen que aceptarla. La convención ya existía (`t_mesh_sphere(_input=None, *, …)`)
y yo escribí las nuevas con params sólo-keyword.

**Los tests no lo vieron porque llamaban a `mesh.box()` directo**, no al verbo a través del
ejecutor. Es el mismo patrón que ya se repitió: lo que se verifica con atajos propios no está
verificado.

El test que faltaba mira la **forma de la llamada**, no el resultado: cada verbo tiene que aceptar
exactamente un posicional y poder invocarse con él en `None`. Verificado por mutación — sacándole el
`_input` a `mesh_box`, falla.

## Verificación

Las nueve corriendo en UE 5.7.4, 0 errores:

```text
BOX M ✓ — 8 verts · 200×100×300cm
CAPSULE M ✓ — 98 verts · r40 + 200cm
TORUS M ✓ — 288 verts · R120/r30
DISC M ✓ — 48 verts · anillo r150
ROUND RECT M ✓ — 36 verts · 300×200 r40
STAIRS M ✓ — 206 verts · 12 escalones · sube 216cm en 336cm
CURVED STAIRS M ✓ — 268 verts · 14 escalones · 180° · sube 252cm
SPHERE BOX M ✓ — 296 verts · r100 · topología de caja
REVOLVE M ✓ — 362 verts · perfil de 15 puntos · 360°
```

Suite headless: **205/205** · `check_unreal_api`: 63 llamadas, todas válidas.

## Relacionado

- [[2026-07-27-INFORME-TreeGen-Curve-N-Array-Pipe-With-Profile-v1.0|TreeGen: Curve N[] y Pipe with Profile]]
- [[2026-07-27-INFORME-Nodos-De-Debug-Ver-El-Stream-v1.0|Nodos de debug: ver el stream]]
