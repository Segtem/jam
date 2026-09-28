# Dos nodos de valor sin name se pisan en la tabla de variables sin que Compile lo vea

- ESTADO: CERRADA
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

### Nota (2026-09-28 10:05:40 UTC)

2026-09-28, Claude: hecho, con la regla que eligió dsl-grafos (Claude v2): un nodo de valor sin name se llama como el nodo. math_core.resolver leía el name EFECTIVO, que trae el default («n»); ahora lee el escrito, y sólo en los verbos que declaran name (compare_greater no lo declara y sigue llamándose por su id, como fijaba test_math). Tests: test_valor_sin_nombre.py, 3; los tres fallan contra HEAD. Suite 1266 OK; oracle test VERDE (28/4/3, 1099, 448/448). El Compile ya usaba name or nid, así que ahora las dos rutas coinciden.

## Próximo paso

Ninguno.
