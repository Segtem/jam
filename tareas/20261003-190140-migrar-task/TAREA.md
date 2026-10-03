# Migrar a Oracle Task 0.2.0

- ESTADO: ABIERTA
- PRIORIDAD: 50
- ETIQUETAS: 


## Pedido

El usuario pidió el 2026-10-03 migrar todos los consumidores de trackertast a oracle-task y
luego retirar el paquete anterior de PyPI. Coordinación: tarea 20261003-183936-migrar-task del
repositorio Segtem/oracle. Se conservan IDs, documentos de tareas y el alias tasks.


## Verificación

AGENTS.md instala oracle-task==0.2.0. El relevo fuera del sandbox ejecutó los tests sin errores; sólo exige commitear los cambios. El Oracle vendorizado no usa el tracker para funcionar; su alias opcional se renovará con Oracle 0.38.2 publicado, sin editar el vendor a mano.

## Próximo paso

Después de publicar Oracle 0.38.2, reinstalar su wheel en vendor/oracle-pkg y actualizar los pins conforme a AGENTS.md. Coordinado en Oracle 20261003-183936-migrar-task.
