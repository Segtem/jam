# Las salidas múltiples muestran identificadores en vez de etiquetas

- ESTADO: ABIERTA
- PRIORIDAD: 90
- ETIQUETAS: graph


## Qué se sabe

La fila usa OutPin.Name; dominio aparece como out y los ejes como eje_x. La etiqueta ya existe en el spec.

## Evidencia

RELEVO.md, 0-decies-bis; Reference/Dominio.png; Source/JamEditor/Private/SJamGraphNode.cpp, filas OutPin.Name. Inventario del 2026-09-19; las cifras históricas no son mediciones nuevas.

## Próximo paso

Separar identidad y etiqueta en la presentación; conservar ids de cables y presets, compilar y verificar dominio y matriz por el camino real.
