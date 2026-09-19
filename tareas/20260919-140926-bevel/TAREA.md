# El join bevel cruza los bordes de la cinta

- ESTADO: ABIERTA
- PRIORIDAD: 80
- ETIQUETAS: malla


## Qué se sabe

Repro de tres puntos, 140 grados y width=600: una de seis caras invertida. Angostar y cambiar diagonal fueron refutados; tres caras del corpus son de esta familia.

## Evidencia

RELEVO.md, ESTADO DEL PLIEGUE; tools/clasifica_caras_rojas_ribbon.py. Inventario del 2026-09-19; las cifras históricas no son mediciones nuevas.

## Próximo paso

Trabajar aguas arriba en offset_points sobre el borde interior del join; conservar el repro y juzgar con malla.cara_visible, sin ajustar la medida al arreglo.
