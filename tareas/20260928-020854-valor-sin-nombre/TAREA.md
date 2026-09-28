# Dos nodos de valor sin name se pisan en la tabla de variables sin que Compile lo vea

- ESTADO: ABIERTA
- PRIORIDAD: 78
- ETIQUETAS: graph, dsl


## Por qué

Señalado por las dos propuestas de Claude para `dsl-grafos` y medido el 2026-09-27: `compilar`
detecta nombres duplicados con `name or nid` (graph.py:477), pero `math_core.resolver` toma el
default del param `name`, que es `"n"` (math_core.py:1399). Dos `number` sin `name` (ids `a` y `b`,
valores 3 y 7) compilan en verde y la tabla queda `{'n': 7.0}`: una expresión `=n` recibe el último,
en silencio.

## Qué hacer

Que las dos rutas usen el mismo nombre. Cuál (el id del nodo, como propone el diseño de
`dsl-grafos`, o el default `n` con el duplicado detectado) se decide con ese diseño.

## Próximo paso

Esperar la elección de `dsl-grafos`; después, un test que falle hoy con el caso de arriba.
