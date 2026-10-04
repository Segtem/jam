# Migrar a Oracle Task 0.2.0

- ESTADO: CERRADA
- PRIORIDAD: 50
- ETIQUETAS: 


## Pedido

El usuario pidió el 2026-10-03 migrar todos los consumidores de trackertast a oracle-task y
luego retirar el paquete anterior de PyPI. Coordinación: tarea 20261003-183936-migrar-task del
repositorio Segtem/oracle. Se conservan IDs, documentos de tareas y el alias tasks.


## Verificación

AGENTS.md instala oracle-task==0.2.0. El relevo fuera del sandbox ejecutó los tests sin errores; sólo exige commitear los cambios. El Oracle vendorizado no usa el tracker para funcionar; su alias opcional se renovará con Oracle 0.38.2 publicado, sin editar el vendor a mano.


### Nota (2026-10-03 23:44:58 UTC)

Relevo pasó después del push. La etiqueta automática usa la identidad histórica del testigo; no se empujó como relevo real. La corrección se sigue en 20261003-234458-relevo-ident. Vendor Oracle queda pendiente de publicar 0.38.2, sin cambios manuales.

### Nota (2026-10-04 00:52:01 UTC)

PyPI Oracle 0.38.2 verificado. Tres pins renovados y vendor reinstalado desde el paquete publicado, sin editar su código a mano. Los 1448 tests Python pasaron. Tool global Oracle 0.38.2 y Oracle Task 0.2.0 desde PyPI. No hay cambios de C++ ni de catálogo. La etiqueta de relevo con identidad histórica no se empuja; se sigue en 20261003-234458-relevo-ident.

## Próximo paso

Ninguno en este consumidor. El retiro de trackertast se coordina en Oracle, tarea 20261003-183936-migrar-task.
