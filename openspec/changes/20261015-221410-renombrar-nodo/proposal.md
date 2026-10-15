# F2 renombra un nodo y la variable de un valor conserva su nombre

## Why

En el editor de nodos web (`Content/Python/jam/web/`) un nodo se renombra sólo desde su menú
contextual, y no hay atajo. Además, un nodo de valor sin `name` propio da su nombre a su variable
(`graph.compilar`: `params.name or nid`), así que renombrarlo cambia el nombre de la variable y rompe
cada expresión que la usaba por el nombre viejo, sin aviso.

Es lo que quedó de `20260924-121231-dsl-grafos` (su próximo paso, punto 2: «F2 para renombrar un
nodo»), en la tarea `20261015-215831-renombrar-nodo`. El Graph de C++ está congelado (decisión de
Brian del 2026-09-30, `mudar-a-web`): esto va en el editor web.

## What changes

- **F2 renombra el nodo seleccionado**, igual que «Renombrar…» del menú: el mismo diálogo y las
  mismas reglas (un identificador, que no exista ya). Los cables lo siguen, porque se arman por el
  nombre al pasar el grafo a JSON.
- **La variable de un nodo de valor conserva su nombre**: al renombrar un valor, su `name` se
  conserva (y se fija en el nombre viejo si estaba vacío), así la variable y las expresiones que la
  usan no cambian.
- **Un nodo de valor nace y se carga con `name` igual a su nombre**, como dicen el texto
  (`texto.py`) y el Compile. Hoy el editor le pone el default de su parámetro (`n`, `t`, `b`, `m`):
  dos `number` nuevos chocan por variable duplicada, y un grafo cargado sin `name` cambia de variable
  en silencio (hallazgo de agy, vuelta 1).
- **Una operación `math_*`** se llama siempre como su nodo (no tiene `name`): si una expresión la
  usa, el editor no la renombra y dice cuál la usa; si nadie la usa, la renombra. Lo comprueba el
  Compile del núcleo (`compilar_grafo`), no una copia de sus reglas.
- La lógica de renombrar pasa a `web/renombrar.js`, una función pura. El editor entero se prueba en
  `node`: LiteGraph real, el editor real con un DOM mínimo de prueba, y el servidor real del núcleo
  (`jam.servidor`) detrás.
- **`tools/emitir_hechos_pruebas.py`** corre los casos de contrato de un cambio y emite un hecho por
  caso, para que las medidas de Oracle juzguen pruebas: sirve también para los próximos cambios de
  Factory en Jam. Los casos salen de un contrato del cambio (`medidas/contratos/<ID>.json`), y la
  corrida sólo es completa si cada requisito del cambio tiene casos y todos corrieron (hallazgo de
  codex y agy, vuelta 1).

## Out of scope

- Renombrar escribiendo en el panel de texto (eso ya es editar el texto).
- Reescribir expresiones (Brian eligió que la variable conserve su nombre).

## Human decisions

- Brian, 2026-10-15: la variable de un valor conserva su nombre al renombrar el nodo; las medidas
  se juzgan con un emisor de hechos de pruebas.
- Brian, 2026-10-15 (vuelta 1): una operación `math_*` que una expresión usa no se renombra; F2 y la
  serialización del editor se prueban con LiteGraph real en `node`.
