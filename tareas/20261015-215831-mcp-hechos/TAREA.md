# jam-mcp vuelca la escena como hechos para Oracle

- ESTADO: ABIERTA
- PRIORIDAD: 70
- ETIQUETAS: dsl, mcp, commander, oracle

### Nota (2026-10-15 21:58:44 UTC)

Lo que quedó de 20260924-121231-jam-mcp: el MCP (Segtem/jam-mcp 0.2.0) expone jam_read_graph, jam_apply_graph, jam_help y jam_preview, pero no vuelca la escena como hechos para Oracle, que era parte de la tarea, para que commander juzgue cada cambio. La sonda ya existe (tarea 20260921-214213-sonda-escena-l0, cerrada): falta una herramienta del MCP que la corra y devuelva los hechos. Preguntas abiertas para Brian, de la misma tarea: ¿se publica jam-mcp en PyPI como oracle-mcp?; con el motor unreal, jam_help necesita el editor abierto (se resolvería con fuera-del-motor etapa 2).
