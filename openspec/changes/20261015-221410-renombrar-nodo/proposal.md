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
- **La variable de un nodo de valor conserva su nombre**: al renombrar un valor sin `name` propio,
  se le fija `name` con el nombre viejo, así la variable y las expresiones que la usan no cambian.
  Uno que ya tiene `name` lo conserva.
- La lógica de renombrar pasa a `web/renombrar.js`, una función pura que el editor usa y que se
  prueba con `node`, sin navegador.
- **`tools/emitir_hechos_pruebas.py`** corre por nombre los casos de contrato de un cambio y emite
  un hecho por caso, para que las medidas de Oracle juzguen pruebas: sirve también para los
  próximos cambios de Factory en Jam.

## Out of scope

- Renombrar escribiendo en el panel de texto (eso ya es editar el texto).
- Reescribir expresiones (Brian eligió que la variable conserve su nombre).

## Human decisions

- Brian, 2026-10-15: la variable de un valor conserva su nombre al renombrar el nodo; las medidas
  se juzgan con un emisor de hechos de pruebas.
