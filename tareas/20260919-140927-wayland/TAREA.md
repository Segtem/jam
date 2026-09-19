# El fix de entrada del Graph en Wayland no ejerció su rama defectuosa

- ESTADO: ABIERTA
- PRIORIDAD: 76
- ETIQUETAS: verificacion


## Qué se sabe

Las reaperturas medidas dieron reubicada=no; no prueban el camino de resincronización.

## Evidencia

RELEVO.md, fix de Wayland y Frontera de verificación. Inventario del 2026-09-19; las cifras históricas no son mediciones nuevas.

## Próximo paso

Reproducir el rect desalineado con Brian, exigir reubicada=sí y comprobar clics al reabrir sin resize manual.
