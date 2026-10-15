# F2 renombra un nodo del grafo y reescribe sus cables

- ESTADO: ABIERTA
- PRIORIDAD: 60
- ETIQUETAS: dsl, graph

### Nota (2026-10-15 21:58:44 UTC)

Lo que quedó de 20260924-121231-dsl-grafos (su próximo paso, punto 2): F2 sobre un nodo del canvas lo renombra; el texto (jam/texto.py) reescribe cada cable @nombre que lo usa y el name de un valor, sin renombrar a ningún otro nodo (texto.py ya promete «no renombrar nunca a nadie» para los nodos nuevos). Prueba: ida y vuelta texto → grafo → texto con el nombre nuevo, y que un cable a un nodo renombrado siga conectado. También anotada ahí, sin bloquear: en Flow un variádico acepta un stream y en el Graph los wrappers piden mínimo dos (registro._registrar_ops_flow), que señaló Codex.
