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

### Nota (2026-09-28 14:05:31 UTC)

2026-09-28, Claude: jam-mcp 0.1.0 hecho en ~/Dev/jam-mcp (repo propio, local, commit 1c56ff5; sin remoto todavía). Decisión de dónde corre: AFUERA del editor (va con fuera-del-motor), sin dependencias, stdio JSON-RPC escrito a mano como oracle-mcp, y le habla al editor por HTTP local. Lado Jam: jam.web arranca solo con el editor (init_unreal.py; JAM_WEB=0 lo apaga; puerto ocupado = aviso, no fallo) y suma POST /api/<función> con lista blanca (leer_canvas, aplicar_texto, ayuda_texto, graph_text, graph_from_text, run_text, confirm, discard) en el game thread, con plazo de 600 s. api.leer_canvas / aplicar_texto: la versión es la HUELLA del texto canónico, no un contador (mover nodos o que el Graph republique lo que mandó el agente no cambian la versión; editar sí), y una versión vieja da conflicto con el texto actual sin pisar nada; lo pendiente que el Graph todavía no cargó cuenta como el grafo actual. api.ayuda_texto: sintaxis + categorías, firma de un verbo, búsqueda. Herramientas MCP: jam_read_graph, jam_apply_graph (text, version, run), jam_help, jam_preview (bake/discard). Verificación: Jam, test_api_agente.py 14 (mutantes: sin conflicto, sin lista blanca y versión por contador, los tres mueren); jam-mcp, tests/test_server.py 16 contra un editor falso; y tools/verifica_mcp_editor.py de punta a punta contra JamPlayground real: VERDE (la puerta abre sola, aplicar+correr deja los 4 nodos en ok, el canvas republica exactamente lo aplicado con la misma versión, una versión vieja da conflicto, discard descarta). Suite de Jam 1336 OK; oracle test VERDE.

## Próximo paso

1. Brian: ¿remoto para `~/Dev/jam-mcp` (Segtem/jam-mcp, privado como Jam?) y ¿se publica en PyPI como oracle-mcp? ¿Se registra en Claude Code / Codex?
2. Lo que pedía la tarea y falta: volcar la escena como hechos para Oracle (`sonda-escena-l0`), para que commander juzgue cada cambio.
3. Mientras el núcleo viva dentro del editor, `jam_help` necesita el editor abierto; con `fuera-del-motor` etapa 2 podría responder sin él.
