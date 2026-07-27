---
title: "Puente P → F: las ops de Flow como verbos del Graph"
aliases:
  - "Points to Frames"
  - "Puente Flow Mesh"
  - "Unificación de vocabularios"
tags:
  - jam
  - graph
  - flow
  - tipos
  - arquitectura
status: implementado
date: 2026-07-27
---

# Puente P → F: las ops de Flow como verbos del Graph

## El hueco, con número

Un inventario del vocabulario dio el dato que faltaba para dimensionar la tarea del contrato
unificado:

```text
Flow siempre produce            →  P (stream de puntos)
Verbos del Graph que consumen P →  0
```

**Cero.** Y del otro lado, los siete verbos de Place/Scatter son todos `A → A`. Flow desembocaba en
`instance`, que coloca el asset activo en cada punto, y ahí terminaba.

Dos mundos paralelos que nunca se tocaban:

```text
Flow:   source → máscaras → weights → instance → actores
Graph:  curva  → frames   → malla   → StaticMesh → place
```

Las 29 ops puras de Flow —poisson, máscaras de pendiente y altura, los nueve weights— no podían
alimentar ningún verbo de malla. Y los 34 verbos de malla no podían aprovechar ninguna distribución.

Peor: la paleta del canvas ya ofrecía las dos familias (`spec_all`), así que se podía **armar** un
grafo mixto que después no se podía **correr**: caía entero al runner de verbos, donde cada op de
Flow era desconocida.

## No hacía falta inventar nada

La observación de Brian que destrabó el diseño: *«nada de inventar, todo es un nodo»*. Y al mirar los
tipos, la conversión resultó ser literal:

```text
Sample     = (pos, normal, slope, seed, uv, weight)
CurveFrame = (position, tangent, outward, parameter, …, scale, seed, …)

pos    → position
normal → orientación
seed   → seed        (la variación de cada pieza sigue estable)
weight → scale       ← el que cambia todo
```

**Que el peso mande la escala es lo que vuelve útil todo el tab Weight.** Hasta ahora una máscara sólo
podía decidir si un punto sobrevivía (cull); ahora una máscara de ruido o de altura decide el
**tamaño** de cada pieza. Nueve ops de Weight ganaron un consumidor de golpe.

Lo único con margen de decisión era la orientación, y es un parámetro, no una invención:
`orientacion` = `normal` (crece perpendicular a la superficie, como una roca) o `vertical` (crece
hacia arriba pase lo que pase, como un árbol). Hay un test que los separa sobre una pared.

## Las 29 ops de Flow ahora son verbos del Graph

El ejecutor del Graph resultó ser genérico —`info["fn"](entrada, **params)` más
`dato_producido_runtime`—, así que envolver una op de Flow es mecánico:

```python
def _envolver_op_flow(kind: str, aridad: int):
    """Adapta la firma de una op de Flow —(list[stream], params) → stream— a la de un verbo."""
    def fn(entrada=None, **params):
        from . import flow
        implementacion = flow.OPS[kind][0]
        if aridad == 0:
            entradas = []
        elif aridad == -1:
            entradas = [e for e in (entrada or []) if e is not None]
        else:
            entradas = [entrada] if entrada is not None else []
        salida = implementacion(entradas, params)
        _RUNTIME_DATA_OUTPUTS[kind] = salida
        ...
```

Se registran con `in_name`/`out_name` = `P`, su categoría, su aridad y sus params. Consecuencias:

- **El Preflight las valida igual que a cualquier verbo**: tipos, cardinalidad, ciclos, params. Un
  `P` conectado donde se espera `S` lo rechaza con `esperaba S, recibió P`.
- El canvas gana siete pestañas nuevas (Vector, Mask, Weight, Sets, Transform, Combine, Display),
  porque se agregaron a `CATEGORIAS`.
- `spec_all()` dedupe: las ops llegaban por los dos lados y ahora gana la entrada del registro de
  verbos, que es la que trae el contrato de tipos.

Quedan afuera **dos**: `instance` y `source_surface`, cuyas funciones viven en el adaptador de Unreal
y no en el cerebro puro. Y `number`/`math`/`text`, que el Graph ya manejaba como nodos de VALOR.

Cero choques de nombre entre los dos vocabularios, verificado antes de tocar nada.

## Lo que ahora se puede expresar

Corrido de verdad en UE 5.7.4, 8 nodos, 0 errores:

```text
[pts·pts_rect]           PTS RECT P ✓ — 16 puntos
[perfil·graph_curve]     GRAPH CURVE N[] ✓ — 11 muestras · 1→0.12 · ease_in
[pend·weight_noise]      WEIGHT NOISE P ✓ — 16 puntos
[frames·points_to_frames] POINTS TO F ✓ — 16 frames desde P · orientación vertical ·
                          escala 0.26→0.90 desde el peso
[ramas·branch_from_frames] BRANCH FROM F ✓ — 16 ramas · hereda escala
[pipe·mesh_pipe_profile]  PIPE PROFILE M ✓ — 896 verts · 16 sweeps
[color·mesh_color]        COLOR M ✓ — vertex color #5A7A3A
[malla·mesh_to_static]    STATIC MESH ✓
```

Una máscara de ruido decidiendo el tamaño de dieciséis piezas de malla procedural. Antes de este
corte, esa cadena no existía en ningún runner.

## Sobre el «contrato unificado»

Esto **no** resuelve la tarea entera de
[[Tarea - contrato unificado de Graph Flow Presets y Web]] —no hay `graph_kind` en el JSON, ni un
envelope único de resultado, ni se decidió formalmente entre «grafo unificado» y «dos modos»— pero
resuelve su síntoma más caro: la paleta ofrecía composiciones que el producto no podía ejecutar.

De hecho elige de facto la opción 1 (grafo unificado) para las ops puras, y deja el runner de Flow
intacto para los grafos que son sólo de flow. Hay un test que lo fija: un grafo de puras ops sigue
siendo `solo_flow`.

## Vocabulario después de este corte

| | antes | ahora |
|---|---|---|
| verbos del Graph | 50 | **80** |
| tipos | 8 | **9** (entra `P`) |
| consumidores de `P` | 0 | **30** |
| pestañas del canvas | 10 | **17** |

## Verificación

- Suite headless: **151/151** (`test_puente_flow.py` es nuevo con 13).
- La cadena mixta compila y corre, y el contrato de tipos se sigue exigiendo a través del puente.
- Cada op pura envuelta conserva su aridad: fuente (0), filtro (1) y variádica (−1).
- El camino histórico no se rompe: un grafo de puras ops sigue yendo al evaluador de Flow.
- Corrida real en UE 5.7.4 hasta StaticMesh, con Discard limpiando el temporal.

## Relacionado

- [[Tarea - contrato unificado de Graph Flow Presets y Web]]
- [[TreeGen - auditoria de Blueprints funciones y flow real]]
- [[Oraculo de forma - comparar contra la malla de referencia]]
