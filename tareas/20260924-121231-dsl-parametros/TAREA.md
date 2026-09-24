# El DSL descarta en silencio un parámetro mal escrito y no valida las opciones

- ESTADO: ABIERTA
- PRIORIDAD: 90
- ETIQUETAS: dsl, llm


## Por qué

Auditoría de [`dsl-llm`](../20260924-114746-dsl-llm/AUDITORIA.md), §4.1: `graph.py:825` descarta
`_desc`, los parámetros que `dsl.coaccionar` no reconoce. Si el LLM escribe `cownt=10`, el grafo corre
en verde con el valor por defecto. La consola sólo agrega «(ignoré params desconocidos)» y sigue. Y
`coaccionar` no compara contra `info["opciones"]` del registro (por ejemplo, `pattern` en
`flow.py:49`), así que un valor inválido pasa.

## Qué hacer

Un parámetro desconocido o una opción inválida es un error que dice qué falló, cuáles son los
válidos y el más parecido («¿quisiste decir count?»), en el grafo y en la consola, con un test que
falle hoy. Tipos ricos (vector, dominio, matriz) quedan para `dsl-grafos`.

## Próximo paso

Implementar. Es acotado y no depende del diseño de `dsl-grafos`.
