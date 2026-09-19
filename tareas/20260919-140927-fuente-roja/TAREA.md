# Un nodo fuente rojo permite ejecutar dependientes

- ESTADO: ABIERTA
- PRIORIDAD: 77
- ETIQUETAS: graph


## Qué se sabe

El Run global queda rojo y revierte Preview, pero no cancela todos los dependientes.

## Evidencia

RELEVO.md, MassGameplay Fase 2; Vault-kb/04-Ejecucion-y-pruebas/2026-08-09-ROADMAP-MassEntity-En-Jam-v1.0.md, Fase 2. Inventario del 2026-09-19; las cifras históricas no son mediciones nuevas.

## Próximo paso

Reproducir con una fuente Mass inválida y medir qué dependientes corren; definir y verificar la propagación del fallo sin efectos parciales.
