---
title: "La escalera de Grasshopper Basics como paso de los verbos"
tipo: ROADMAP
version: "1.0"
date: 2026-08-12
updated: 2026-08-12
status: en-progreso
area: 01-Graph
tags:
  - jam
  - graph
  - verbos
  - roadmap
  - grasshopper
---

# La escalera de Grasshopper Basics como paso de los verbos

Brian trajo [An Introduction to Grasshopper](https://baharmon.github.io/basics) (Brendan Harmon, LSU)
y pidió ponerla **en paso para los verbos**, como la Fase 1 de
[[2026-08-02-PLAN-Verbos-Math-Numeros-Vectores-Matrices-v1.0|Math]] fue la escalera de los escalares.

Sirve para eso mejor que el catálogo de los 11 tabs que ya teníamos en
`Reference/rhino-grasshopper/`. Ese cataloga **todo el vocabulario**, que es un mapa; esto es un
**camino**: el orden exacto en que una persona que nunca vio un grafo llega a modelar una superficie.
Un catálogo dice qué falta; una escalera dice **en qué orden importa**, y ese orden no es el nuestro
sino el de alguien que enseña esto hace años.

La escalera es: **punto → línea → polilínea → curva → superficie**. Cada peldaño usa lo del anterior.

## La auditoría, medida contra el registro real

No de memoria: los 200 verbos de `tools.REGISTRO` + `flow.OPS_META` + `math_core.VALORES`.

| peldaño | componente del tutorial | en Jam |
|---|---|---|
| Puntos | Number Slider | ✅ `number` |
| | Panel | ✅ el Inspector |
| | **Construct Point** (x,y,z → punto) | ❌ **falta** |
| | Point / Boolean Toggle (Params) | ⚠️ `boolean` **recién hecho**; falta el contenedor Point |
| Líneas | **Line** (dos puntos) | ⚠️ `pts_line` reparte N puntos sobre el segmento, no lo produce como curva |
| | **Line SDL** (origen + dirección + largo) | ❌ **falta** (y necesita vectores) |
| | **Unit X / Unit Z** | ❌ **falta el TIPO vector** |
| | Move | ⚠️ `move` para puntos, `mesh_transform` para mallas; no para curvas |
| Polilíneas | Polyline | ✅ `curve_polyline` |
| | cerrar con Boolean → polígono | ⚠️ `curve_polyline` **no tiene** parámetro de cierre |
| Curvas | **Interpolate** (curva por puntos de control) | ❌ **falta** — `curve_bezier` es otra cosa |
| | Range | ✅ `series_range` |
| | Sine | ✅ `math_sin` (Fase 1 de Math, 2026-08-12) |
| Superficies | Plane Surface | ≈ `mesh_grid` |
| | Box 2Pt / Center Box | ≈ `mesh_box` (por tamaño, no por dos puntos) |
| | **Boundary Surfaces** | ❌ **falta** |
| | **Ruled Surface** | ❌ **falta** |
| | **Loft** | ❌ **falta** |
| | Extrude | ✅ `mesh_extrude` |

## Lo que la escalera enseña sobre nuestro hueco

Los tres faltantes grandes —Unit X/Z, Line SDL, Loft— **no son verbos sueltos: son un tipo que no
tenemos.** Jam maneja `N` (número), `T` (texto), `B` (booleano), `P` (puntos), `S` (curva), `F`
(frames), `M` (malla), `A` (asset)… y **ningún vector**. Sin `V` no hay dirección que cablear, y sin
dirección no hay Line SDL, ni Move con vector, ni normales manipulables.

Eso coincide exactamente con la **Fase 2 del plan de Math** (vectores y matrices), que quedó
desbloqueada al cerrar la Fase 1. La escalera de Harmon confirma el orden desde afuera: el vector no
es un lujo matemático, es lo que hace falta para dibujar la segunda figura del tutorial.

## Los peldaños, en orden

**0. Interruptor booleano.** ✅ HECHO 2026-08-12. El hueco medido: **43 verbos con 70 parámetros
booleanos y CERO nodos capaces de producir un booleano**. Las comparaciones producían `B` pero no
había de dónde sacar un «sí» constante, así que esos 70 parámetros sólo se tocaban a mano en cada
ficha y nunca se manejaban desde el lienzo. Gotcha que quedó fijado en test: `bool("false")` en
Python es **True** —toda cadena no vacía lo es— y los params viajan como TEXTO, así que un
interruptor apagado se habría leído prendido al abrir un `.jamgraph`, con el nodo dibujándose bien.

**1. El tipo vector `V` y sus constructores.** Unit X/Y/Z, Construir vector, Descomponer, sumar,
escalar, largo, normalizar, producto punto y cruz. Es la Fase 2 de Math y el desbloqueo de todo lo
demás. Decidir antes: si `V` es un tipo propio o un `N[]` de tres — un `N[]` ahorra tipo y hace que
todo lo de series funcione gratis, pero deja pasar cablear una serie de 7 números donde va una
dirección, que es el error que un tipo existe para atajar.

**2. Construir punto y línea.** `point` (x,y,z → `P` de un punto) y `curve_line` (dos puntos → `S`).
Hoy `pts_line` reparte puntos SOBRE un segmento, que es otra cosa: no se puede cablear el segmento
a nada que espere una curva.

**3. Cerrar la polilínea.** Un parámetro de cierre en `curve_polyline`, cableado desde el
interruptor del peldaño 0 — que es exactamente el gesto del tutorial para hacer un polígono.

**4. Line SDL y Move sobre curvas.** Ya con `V`.

**5. Interpolate.** Curva suave que PASA por los puntos, contra `curve_bezier` que los usa de
control. Son dos cosas distintas y el tutorial enseña la primera; hoy sólo tenemos la segunda.

**6. Superficies regladas: Ruled Surface y Loft.** Dos curvas → malla. Es el paso donde la escalera
se junta con lo que Jam ya hace bien (`mesh_ribbon` es un caso particular de esto), y donde va a
volver a aparecer el moño del bevel de `ribbon_core` si no se resolvió antes.

## Lo que NO se toma del tutorial

Es de **NURBS**, y Jam produce mallas dinámicas de Geometry Script. Loft y Boundary Surface se van a
implementar como triangulación, no como superficie paramétrica: la escalera aporta el ORDEN y el
vocabulario, no la representación. Anotarlo importa porque «Loft» va a significar algo distinto acá
que en Rhino, y quien venga de Rhino va a esperar lo otro.

Relacionado: [[2026-08-02-PLAN-Verbos-Math-Numeros-Vectores-Matrices-v1.0|verbos de Math]] ·
[[2026-08-03-ROADMAP-Catalogo-Matematico-Ampliado-v1.0|catálogo matemático ampliado]].
