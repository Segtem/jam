# El escenario del corte 1 no tiene un arnés que lo ejerza de punta a punta

- ESTADO: CERRADA
- PRIORIDAD: 70
- ETIQUETAS: aura, colocacion


El plan está en Oracle: estudios/AURA-PROPIO-CORTE-1.md (tarea de Oracle 20260921-212821-aura-corte). Es el primer corte de un agente que coloca en Unreal y al que Oracle juzga: pedido → colocación provisional → sonda headless en JamPlayground → hechos L0 → oracle juzgar → corrección con testigos → confirmación.

## Qué hacer

Dos cubos de 100 cm contra un muro de 400x20x200 en JamPlayground: forzar el ROJO con penetración inyectada, corregir con los testigos y llegar al VERDE.

## Próximo paso

Leer el plan (sección correspondiente) y empezar.

### Nota (2026-09-30 10:09:07 UTC)

HECHO en 7717827 (tarea sonda-escena-l0): python tools/colocar_y_juzgar.py tools/aura/escenario1_mal.json → Unreal headless en JamPlayground → ROJO con testigos (colocacion.interpenetracion Caja_A↔Muro_Norte 9 cm; physics.tanda_sin_interpenetracion Caja_A↔Caja_B 69 cm); escenario1_bien.json (Caja_A a y=60, Caja_B a x=40, y=60, corregidas desde esos testigos) → VERDE en las 6 medidas de colocación. Re-corrido el 2026-09-29 con el catálogo que exige evidencia: mismos veredictos.
