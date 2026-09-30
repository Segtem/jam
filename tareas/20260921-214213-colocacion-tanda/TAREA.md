# No hay medida que juzgue una tanda de piezas entre sí

- ESTADO: CERRADA
- PRIORIDAD: 72
- ETIQUETAS: aura, colocacion


El plan está en Oracle: estudios/AURA-PROPIO-CORTE-1.md (tarea de Oracle 20260921-212821-aura-corte). Es el primer corte de un agente que coloca en Unreal y al que Oracle juzga: pedido → colocación provisional → sonda headless en JamPlayground → hechos L0 → oracle juzgar → corrección con testigos → confirmación.

## Qué hacer

Medida colocacion.tanda_sin_interpenetracion con corpus de las dos polaridades y mutación; que exija requiere para salir SIN EVIDENCIA ante un volcado vacío, igual que el resto de las de colocación.

## Próximo paso

Leer el plan (sección correspondiente) y empezar.

### Nota (2026-09-30 10:09:07 UTC)

Cubierta por la medida que ya existe, sin crear otra: physics.tanda_sin_interpenetracion juzga los pares de la tanda (de asentada a unir asentada b donde a.id < b.id, una vez por par). hechos_escena.hechos emite la tanda en la bolsa asentada (7717827). Desde ese commit declara requiere asentada (SIN EVIDENCIA con tanda vacía, caso physics-tanda-005), tiene rojo en el borde y de distinta profundidad (physics-tanda-001/002), diferencial physics_tanda.json (80 mundos) y mutación completa (458/458 en el proyecto). En el escenario del corte 1 atrapó Caja_A↔Caja_B 69 cm. Una colocacion.tanda_sin_interpenetracion aparte sería la misma medida con otro nombre.
