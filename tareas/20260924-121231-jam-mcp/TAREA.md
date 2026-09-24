# Un agente no tiene cómo hablarle a Jam: falta un servidor MCP que exponga el DSL

- ESTADO: ABIERTA
- PRIORIDAD: 85
- ETIQUETAS: dsl, mcp, llm, commander


## Por qué

commander (`~/Dev/commander`, tareas `vision` y `harness`) pone el agente en un harness (`dsh`,
Claude Code, Codex) que habla por MCP. Oracle ya tiene un MCP; Jam se ejerce hoy sólo con sondas
headless (`tools/experiments/`), y un harness no tiene cómo hablarle.

## Qué hacer

Un servidor MCP que exponga Jam a un agente: leer el grafo como DSL, aplicar DSL, ejecutar, y volcar
la escena como hechos para Oracle (`sonda-escena-l0`). Es una capa delgada sobre el DSL de
`dsl-grafos`: si todo Jam se alcanza por el DSL, el MCP sólo lo transporta.

## Próximo paso

Esperar a `dsl-grafos`; mientras tanto, decidir dónde corre el servidor (dentro del editor o
afuera hablando con él).
