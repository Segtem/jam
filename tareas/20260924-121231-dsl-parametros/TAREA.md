# El DSL descarta en silencio un parámetro mal escrito y no valida las opciones

- ESTADO: CERRADA
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

### Nota (2026-09-28 01:43:15 UTC)

2026-09-27, Claude: hecho. Un solo juicio en registro_core (param_desconocido y opcion_invalida: difflib da el más parecido y se listan los válidos) usado por las TRES rutas que leen params escritos: consola (panel.ejecutar_dsl, las dos ramas: ahora no corre y responde «[error] «verbo» no corrió»; los params se juzgan antes que el asset para que «biblioteca vacía» no tape el error), Compile del Graph (el desconocido ya era error: ahora sugiere; las opciones son nuevas) y preflight de Flow (Flow.validar no miraba params: ahora desconocidos y opciones, salvo cableados y expresiones =…). dsl.coaccionar devuelve frases enteras; t_pcg con preset rechaza en vez de ignorar. Presets de fábrica y Resources/Examples: ninguno trae un param u opción inválidos (medido). Tests: test_dsl_parametros.py, 11; contra HEAD fallan 8 (los verdes son controles de que lo bien escrito sigue corriendo). Editor (JamPlayground, tools/experiments/verifica_params_y_fuente_roja_58.py): VERDE — cownt=10 y pattern=poison no corren, sugieren count/poisson y la escena no cambia; count=3 pattern=grid coloca 3. Suite 1258 OK; oracle test VERDE (28/4/3, 1099, 448/448).

## Próximo paso

Ninguno. Los tipos ricos (vector, dominio, matriz) en los params escritos siguen en `dsl-grafos`.
