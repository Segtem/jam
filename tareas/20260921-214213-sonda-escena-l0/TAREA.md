# La colocación no tiene una sonda headless que vuelque la escena como hechos L0

- ESTADO: CERRADA
- PRIORIDAD: 80
- ETIQUETAS: aura, colocacion


El plan está en Oracle: estudios/AURA-PROPIO-CORTE-1.md (tarea de Oracle 20260921-212821-aura-corte). Es el primer corte de un agente que coloca en Unreal y al que Oracle juzga: pedido → colocación provisional → sonda headless en JamPlayground → hechos L0 → oracle juzgar → corrección con testigos → confirmación.

## Qué hacer

Crear tools/experiments/sonda_colocacion_aura.py y la función en jam/ue.py que serialice pieza, vecina y asentamiento a Saved/Oracle/escena.json desde JamPlayground headless.

## Próximo paso

Leer el plan (sección correspondiente) y empezar.

### Nota (2026-09-29 23:30:37 UTC)

7717827: HECHO. python tools/colocar_y_juzgar.py <orden.json> → Unreal headless → Saved/Oracle/escena.json → oracle juzgar (6 medidas de colocación; código de salida de Oracle, 2 si el sensor falla o volcó menos piezas que las pedidas). Ejemplos: tools/aura/escenario1_{mal,bien}.json (el del plan): ROJO con testigos 9 y 69 cm / VERDE. Diferencias con el plan: (1) la tanda NO va en vecina (se mediría contra sí misma); los pares de la tanda los juzga physics.tanda_sin_interpenetracion vía la bolsa asentada. (2) snap.grilla/snap.yaw no se aplican: son la promesa del verbo snap y daban rojo en el escenario corregido. (3) El falso verde por evidencia vacía (riesgo 3 del plan) era real y se cerró en el juez: requiere en las cinco medidas + 5 casos de corpus. Siguiente natural: el agente (Claude/Codex) usando esto en bucle, y que el mismo volcado salga de Godot/Unity por el contrato (colocar ya devuelve las cajas de mundo; faltaría una op que liste la escena).
