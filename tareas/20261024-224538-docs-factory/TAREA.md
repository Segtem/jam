# Documentar el uso de Oracle Factory en Jam

- ESTADO: CERRADA
- PRIORIDAD: 50
- ETIQUETAS:

## Pedido

Actualizar el README de Jam para explicar el flujo de Oracle Factory y enlazar las guías vigentes, sin actualizar dependencias ni cambiar Jam.

## Alcance realizado

Se documentan propuesta/spec, requisitos, medidas, revisión, juicio y cierre, el catálogo de medidas/ y la identidad del agente. Se enlazan tablero de VS Code y Live Share, conocimiento y guía de agentes, aclarando versión instalada, modelo por proyecto y MCP de sólo lectura. AGENTS.md conserva las versiones que usa el proyecto.

## Verificación y límite previo

Diff revisado y git diff --check correcto; los enlaces de las guías respondieron HTTP 200. La comprobación inicial python tools/relevo.py terminó con código 1: verde_editor (89eaa75, 2026-09-30) quedó VIEJO porque cambiaron cuatro archivos commiteados, por ejemplo Content/Python/jam/registro.py. Es una deuda previa del editor: este cambio documental no la corrige ni afirma una nueva validación de motor. No se tocan código, medidas, escenas, vendor ni dependencias.

## Próximo paso

No quedan ediciones pendientes en esta tarea documental. Brian autorizó integrar main y empujar a origin (1A, 2A y 3A para Oracle, Jam y LyraGASP). La publicación se comprueba comparando main con el SHA anunciado por origin; cualquier cambio de código o actualización de dependencias requiere su propio trabajo.
