# El trabajo pendiente de Jam necesita un tracker único

- ESTADO: ABIERTA
- PRIORIDAD: 100
- ETIQUETAS: proceso


## Pedido y alcance

Origen: tarea `20260919-134424-tareas-jam` del tracker de Oracle, por pedido de Brian.
Inicializar el tracker, inventariar pendientes reales, cambiar el arranque, verificar y
confirmar sin push. La tarea de Oracle queda ABIERTA para revisión de Claude.

## Inventario y decisiones

Se leyeron AGENTS.md, RELEVO.md (agenda, frontera, gestos e historial), CLAUDE.md,
README.md, docs/Oraculo de Jam - guia completa.md mediante búsqueda de pendientes,
medidas/corpus/README.md, los catálogos de Reference/rhino-grasshopper, planes y roadmaps
referenciados del vault, medidas/oracle.json y los 65 commits recientes. El vault se conserva.
No se halló otro directorio de notas de estudio Markdown fuera del vault y Reference.

Quedaron 58 tareas: ésta y 57 pendientes o revisiones delimitadas, incluidos los gestos
sin cierre explícito. Cada una tiene evidencia, lo conocido y un próximo paso.
No se reabren bypass/comentarios (roadmap de accesibilidad §Fase 7, hechos el 4 y 5 de agosto),
matrices del cerebro, multi-salida, escalera de curvas, cache/live view ni optimización Bake
(ping-pong ya cerrado en RELEVO). Tampoco embedding, migración de espacio, testigos,
polaridad del corpus o mutantes de Oracle 0.10: el historial posterior los cerró.

Las cifras de AGENTS para sombras son históricas: la configuración vigente tiene cotas
54/41/16. Se separan esas tres deudas. Los catálogos comparativos no son encargos de
implementar cada componente. Las propuestas antiguas ambiguas tienen una tarea de revisión,
sin convertir navegación, red, NURBS o schema v2 en trabajo aprobado.

El testigo histórico sigue presente porque relevo.py lo consume. Su adaptación al tracker
es un pendiente separado; no se reescribieron sensores ni se eliminaron verificadores.
La vigencia del editor ya llegó roja antes de editar y tiene tarea propia.

## Próximo paso

Retomar con escritura habilitada en `.git`. Revisar y confirmar únicamente AGENTS.md,
CLAUDE.md, RELEVO.md y tareas/ con `20260919-140704-tracker: el tracker del proyecto`.
Repetir `oracle tarea revisar` y `oracle tarea hechos --git` y comprobar que los documentos
estén en HEAD. Registrar el resultado y cerrar esta tarea con el commit
`20260919-140704-tracker: done`. No hacer push. La vigencia del editor se resuelve en
`20260919-140926-editor-vigente`, sin falsear el campo para cerrar esta migración.
La tarea de Oracle permanece ABIERTA para que Claude revise.
