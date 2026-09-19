# El verificador de relevo todavía exige el protocolo anterior

- ESTADO: ABIERTA
- PRIORIDAD: 38
- ETIQUETAS: proceso


## Qué se sabe

El script exige frontmatter, secciones históricas, árbol empujado y etiqueta de turno. La nueva fuente de trabajo es el tracker; esta tarea tiene orden explícita de no hacer push.

## Evidencia

tools/relevo.py; RELEVO.md; AGENTS.md. Inventario del 2026-09-19; las cifras históricas no son mediciones nuevas.

## Próximo paso

Diseñar la adaptación al tracker conservando tests, diferencial y vigencia del editor; no borrar el testigo ni cambiar sus sensores sin regenerar fixtures y verificar el diferencial.
