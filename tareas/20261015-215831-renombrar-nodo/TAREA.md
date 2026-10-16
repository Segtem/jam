# F2 renombra un nodo del grafo y reescribe sus cables

- ESTADO: CERRADA
- PRIORIDAD: 60
- ETIQUETAS: dsl, graph

### Nota (2026-10-15 21:58:44 UTC)

Lo que quedó de 20260924-121231-dsl-grafos (su próximo paso, punto 2): F2 sobre un nodo del canvas lo renombra; el texto (jam/texto.py) reescribe cada cable @nombre que lo usa y el name de un valor, sin renombrar a ningún otro nodo (texto.py ya promete «no renombrar nunca a nadie» para los nodos nuevos). Prueba: ida y vuelta texto → grafo → texto con el nombre nuevo, y que un cable a un nodo renombrado siga conectado. También anotada ahí, sin bloquear: en Flow un variádico acepta un stream y en el Graph los wrappers piden mínimo dos (registro._registrar_ops_flow), que señaló Codex.

### Nota (2026-10-16 10:08:32 UTC)

Hecho en el cambio de Factory 20261015-221410-renombrar-nodo (merge 9e21577), el primero de Factory en Jam: F2 renombra el nodo seleccionado en el editor web; un valor nace y se carga con name igual a su nombre (antes nacía con el default n); al renombrarlo conserva su variable; una operación math_* que usa una expresión no se renombra (lo comprueba el Compile del núcleo). El editor real se prueba en node (tests/editor_en_node.js, sin sockets), y tools/emitir_hechos_pruebas.py con medidas/contratos/<ID>.json emite hechos de pruebas para las medidas. Seis vueltas de codex y agy.
