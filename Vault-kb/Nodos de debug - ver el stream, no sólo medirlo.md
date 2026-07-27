---
title: "Nodos de debug: ver el stream, no sólo medirlo"
aliases:
  - "Debug Frames"
  - "Debug Points"
  - "Ayudantes visuales del Graph"
tags:
  - jam
  - graph
  - debug
  - oraculo
status: implementado
date: 2026-07-27
---

# Nodos de debug: ver el stream, no sólo medirlo

## De dónde sale

Idea de Brian: *«¿podemos incorporar nodos debug? Assets como flecha, ejes, etc.»*

Llena un hueco real y complementario al oráculo. El oráculo **mide** el resultado final contra una
referencia; no deja **ver** lo que pasa a mitad de la cadena. Si los frames apuntan mal, o una máscara
mató los puntos equivocados, no hay forma de darse cuenta hasta que la malla final sale rara — y para
entonces ya no se sabe qué nodo tuvo la culpa.

Es exactamente el patrón que se viene repitiendo: **las métricas cazan lo que alguien formalizó, el
ojo caza lo demás**. Estos nodos le dan al ojo algo que mirar en el medio del grafo.

## Los dos verbos

### `Debug Frames` `F → M`

Tres ejes de colores sobre cada frame, con la convención de siempre —la misma que usa
`make_rot_from_xz` al orientar geometría, para que **lo que se ve sea lo que se orienta**:

```text
X rojo   = tangent   — hacia dónde crece
Y verde  = lateral   — cross(tangent, outward)
Z azul   = outward   — hacia afuera
```

Con `escalar_con_frame`, el largo de los ejes sigue la escala del frame. Eso es la mitad del valor: se
ve de un vistazo si la escala cae en cascada entre niveles o si una máscara la está manejando.
`solo_tangente` deja una sola flecha por frame cuando tres ejes tapan todo.

### `Debug Points` `P → M`

Un cubo por punto, con el **peso de la máscara como tamaño**. El detalle que lo hace útil: `minimo`
evita que un peso 0 lo vuelva invisible, así se distingue **«la máscara lo apagó»** de **«nunca
estuvo»** — que a ojo son lo mismo y significan cosas muy distintas.

## Por qué salen por `M` y no dibujan líneas

Podrían haber sido `draw_debug_line` transitorias. Salen por un cable `M` a propósito:

- se **mergean** con el resultado real, se hornean o se colocan sueltos;
- participan del Preview/Bake/Discard sin necesitar un camino aparte;
- son **verificables**: se puede afirmar sobre la geometría producida en un test headless, cosa
  imposible con un dibujo de viewport.

El costo es que hay que borrarlas después, y para eso ya existe `Discard`.

## Rendimiento

`append_mesh_transformed` acepta la **lista entera** de transforms, así que se construye una flecha
unitaria una vez y se estampa N veces en una sola llamada por eje: tres llamadas para cualquier
cantidad de frames, no una por flecha. Tope de 4096 elementos por nodo.

## Arquitectura

- `Content/Python/jam/debug.py` — **puro**: convierte frames en tramos `(origen, dirección, largo,
  eje)` y puntos en marcadores. Es lo que se prueba, y permite afirmar que el eje X **es** la
  tangente sin levantar el motor.
- `Content/Python/jam/mesh.py` — `debug_ejes()` y `debug_puntos()`: estampan la plantilla y pintan
  cada eje con su color.

Un detalle que el núcleo puro resuelve: si `tangent` y `outward` quedan **paralelos**, el producto
cruzado da cero y los ejes serían basura. Se elige una perpendicular estable y hay un test que exige
que los tres sigan siendo ortogonales en ese caso.

## Verificación

Corrido en UE 5.7.4 sobre la cadena Flow → Mesh, 7 nodos, 0 errores:

```text
[peso·weight_noise]   WEIGHT NOISE P ✓ — 9 puntos
[verpts·debug_points] DEBUG P M ✓ — 72 verts · 9 puntos · peso 0.33→0.73
[verfr·debug_frames]  DEBUG F M ✓ — 1080 verts · 9 frames · ejes XYZ
[juntar·mesh_merge]   MERGE M ✓ — 1152 verts
[malla·mesh_to_static] STATIC MESH ✓
```

Suite headless: **163/163** (`test_debug.py` es nuevo con 12).

## Relacionado

- [[Puente P a F - las ops de Flow como verbos del Graph]]
- [[Oraculo de forma - comparar contra la malla de referencia]]
