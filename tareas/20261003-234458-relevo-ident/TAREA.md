# El relevo usa la identidad del testigo histórico

- ESTADO: ABIERTA
- PRIORIDAD: 80
- ETIQUETAS: 


## Evidencia

Al verificar la migración Oracle Task, `python tools/relevo.py --cerrar` pasó sus checks pero
creó el tag local `relevo/2026-10-03-claude-code`: lee saliente/entrante del frontmatter
histórico de RELEVO.md, no la identidad de quien realiza el turno. El archivo ya se declara
histórico y las tareas son la fuente de verdad. El tag generado no se empujó como relevo real.

## Próximo paso

Revisar cómo tomar la identidad vigente del turno sin usar el testigo histórico, añadir una
prueba que detecte el agente incorrecto y conservar los checks de vigencia del editor.
