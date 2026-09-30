# Un agente no puede colocar sin la interfaz de Slate

- ESTADO: ABIERTA
- PRIORIDAD: 78
- ETIQUETAS: aura, colocacion


El plan está en Oracle: estudios/AURA-PROPIO-CORTE-1.md (tarea de Oracle 20260921-212821-aura-corte). Es el primer corte de un agente que coloca en Unreal y al que Oracle juzga: pedido → colocación provisional → sonda headless en JamPlayground → hechos L0 → oracle juzgar → corrección con testigos → confirmación.

## Qué hacer

Un comando headless parametrizable (tools/jam_colocar.py o similar) que instancie actores con tag jam:preview y aplique transformaciones y snap sin interacción.

## Próximo paso

Leer el plan (sección correspondiente) y empezar.

### Nota (2026-09-30 10:09:07 UTC)

2026-09-30: la parte de colocar sin Slate está: tools/colocar_y_juzgar.py <orden.json> instancia en Unreal headless con tag jam:preview, con loc, yaw y escala por pieza, y vuelca los hechos (7717827). Falta lo de «aplicar snap»: la orden no tiene un paso de snap; hoy el agente corrige posiciones a mano desde los testigos.
