# El Graph necesita proteger los cambios sin guardar

- ESTADO: ABIERTA
- PRIORIDAD: 72
- ETIQUETAS: graph


## Qué se sabe

«Añadir estado dirty y diálogo Guardar/Descartar/Cancelar antes de New, Open y cerrar la pestaña». La búsqueda actual en SJamGraphEditor.cpp no encuentra dirty ni Unsaved.

## Evidencia

Vault-kb/01-Graph/2026-07-25-PLAN-Persistencia-Segura-Diagramas-Graph-v1.0.md, Pendiente para cerrar.

## Próximo paso

Reproducir pérdida de cambios al abrir, crear y cerrar, implementar la guarda y verificar guardar, descartar y cancelar con diálogos reales.
