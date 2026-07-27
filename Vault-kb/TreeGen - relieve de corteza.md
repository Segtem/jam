---
title: "TreeGen: relieve de corteza"
aliases:
  - "Bark"
  - "Displace del tronco"
  - "Ruido de corteza"
tags:
  - jam
  - graph
  - treegen
  - procedural-mesh
  - corteza
status: implementado
date: 2026-07-27
---

# TreeGen: relieve de corteza

## De dónde sale

De mirar el árbol: el tronco era un cilindro naranja perfectamente liso. Es lo que más lo separaba de
verse hecho a mano.

TreeGen lo resuelve dibujando una textura a un **render target** y sampleándola por UV durante
`DrawRadius` para deformar el radio de cada anillo. Jam no necesita ese rodeo: puede calcular el
ruido directamente, y hacerlo en Python **puro** lo vuelve testeable sin motor.

## El verbo `Bark` `M → M`

Tab **Mesh**. Desplaza cada vértice **a lo largo de su propia normal** según un campo de ruido.
Desplazar por la normal y no radialmente desde el eje Z hace que funcione igual en un tronco vertical
que en una rama inclinada.

| Parámetro | Qué hace |
|---|---|
| `amplitud` | centímetros de relieve (±) |
| `escala` | frecuencia del ruido por cm |
| `alargue` | **la clave**: cuánto se estira el ruido a lo largo del eje |
| `octavas` | detalle fBm |
| `surcos` | 0 = bultos suaves, 1 = surcos marcados con lomos anchos |
| `seed` | reproducible |

### Por qué `alargue` es la clave

Un ruido isótropo da bultos de papa. La corteza son **surcos verticales**: frecuencia alta alrededor
del tronco, baja a lo largo. `alargue` comprime el eje Z del campo de ruido y produce exactamente eso.

Hay un test que lo fija como contrato: recorrer 100cm **alrededor** del tronco tiene que cambiar el
campo más de 3× que recorrer 100cm **hacia arriba**.

### Por qué `surcos`

La corteza real es asimétrica: grietas angostas y profundas entre lomos anchos y planos. Un ruido
simétrico se ve a goma. La transformación *ridged* (`1 - 2·|n|`) convierte los ceros del ruido en
crestas y el resto cae en surcos. `surcos` mezcla entre las dos.

## Arquitectura

- `Content/Python/jam/bark.py` — **puro**: value noise 3D interpolado, fBm, el campo de corteza y el
  desplazamiento. 10 tests headless.
- `Content/Python/jam/mesh.py` — `corteza()`: lee posiciones y normales, llama al núcleo puro,
  escribe de vuelta y recalcula normales.

### El gotcha de escritura de vértices

`GeometryScriptVectorList` **no se puede construir desde Python**: `set_editor_property("list", …)`
falla con las tres variantes de nombre, y `set_all_mesh_vertex_positions` con una lista vacía
**no da error, simplemente no hace nada**. Otro fallo silencioso.

Lo que sí funciona, verificado de punta a punta:

```text
get_all_vertex_positions(m, True)  →  VectorList (del tamaño correcto)
lista.set_vector_list_item(i, Vector)   ← muta en el lugar, devuelve bool
set_all_mesh_vertex_positions(m, lista)
```

## Verificación

Sobre un cilindro de radio 23 exacto:

```text
antes    radio min 23.00  max 23.00  sd 0.000
después  radio min 22.10  max 23.97  sd 0.381
vértices movidos >0.5mm: 690/720
```

## El bug que encontró el razonamiento, no la medición

`amplitud` es **absoluta**, así que tiene que ser menor que el radio más fino de la malla. El tronco
del ejemplo afinaba a `0.03 × 23cm = 0.69cm` y el relieve era `±1.5cm`: los vértices de la punta
cruzaban el eje e **invertían la geometría**.

La primera medición no lo mostró porque el tronco se inclina y se estaba midiendo el radio contra una
vertical fija en vez de contra el eje real de la curva. Salió por cálculo, no por medición.

Arreglado en los dos lados:

- el perfil del tronco deja de bajar a una aguja: `end_value` 0.03 → **0.08** (1.84cm de radio);
- el relieve del ejemplo baja a **1.2cm**;
- queda documentado en el docstring y en el `doc` del verbo;
- y hay un test que exige `amplitud < radio × end_value` en el ejemplo empaquetado.

La función pura no puede detectarlo sola porque no conoce el eje del barrido. Es una limitación real,
no un descuido: queda en manos de quien arma el grafo.

## En el ejemplo

La corteza va sobre el **tronco**, antes del merge:

```text
Trunk S → Trunk Pipe → Bark ─┐
Branch Pipe ─────────────────┼→ Merge → Color → UV → Material → …
Twig Pipe ───────────────────┘
```

No sobre el merge: las ramitas tienen 1.2cm de radio y un relieve de ±1.2cm las invertiría enteras.

El oráculo confirma que el relieve **no altera la forma**: silueta, perfil, esbeltez y conteos quedan
idénticos. Un ±1.2cm sobre un tronco de 23cm no mueve ninguna métrica global, que es exactamente lo
que se espera de un detalle de superficie.

## Lo que sigue

Esto es **geometría**, no textura. El tronco sigue siendo un color plano: falta un material de corteza
de verdad. El relieve le da silueta y sombreado propio, pero sin textura la lectura sigue siendo
sintética.

## Relacionado

- [[Oraculo de forma - comparar contra la malla de referencia]]
- [[TreeGen - ejemplo de dos niveles y presets de Graph]]
- [[TreeGen - auditoria de Blueprints funciones y flow real]]
