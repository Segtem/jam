# Las relaciones de colocación no están declaradas

- ESTADO: ABIERTA
- PRIORIDAD: 75
- ETIQUETAS: aura, colocacion


El plan está en Oracle: estudios/AURA-PROPIO-CORTE-1.md (tarea de Oracle 20260921-212821-aura-corte). Es el primer corte de un agente que coloca en Unreal y al que Oracle juzga: pedido → colocación provisional → sonda headless en JamPlayground → hechos L0 → oracle juzgar → corrección con testigos → confirmación.

## Qué hacer

Declarar pieza, vecina y asentamiento en medidas/relaciones/ con unidades, que además baja la sombra meta.toda_cantidad_comparada_tiene_unidad_derivable (cota 54).

## Avance

- Se leyó la especificación del plan `AURA-PROPIO-CORTE-1.md`, el `AGENTS.md` de Jam y la estructura canónica de relaciones en Oracle (`nucleo/relacion.py`, `nucleo/unidad.py` y ejemplos en `relaciones/*.json`).
- Se declararon formalmente en `medidas/relaciones/` las tres relaciones solicitadas con campos escalares, tipos, unidades y alcances explícitos:
  - `medidas/relaciones/pieza.json`: campos `id` (`sin_unidad`), coordenadas de AABB y pivote `ox`, `oy`, `oz`, `ex`, `ey`, `ez`, `lx`, `ly`, `lz` (`cm`), y rotación `yaw` (`grados`), junto a su alcance que delimita la ausencia de observación de mallas complejas, concavidades ni oclusión.
  - `medidas/relaciones/vecina.json`: idéntica estructura y unidades para piezas vecinas del entorno.
  - `medidas/relaciones/asentamiento.json`: campos `pieza` (`sin_unidad`), `soporte` (`sin_unidad`), `tiene_suelo` (`sin_unidad`) y `gap` (`cm`), con alcance delimitando que mide soporte AABB y no landscapes continuos ni dinámicas Chaos.
- Nota de verificación: no se corrió ninguna verificación por shell ni suite de tests en esta sesión (restringido a modo sin shell).

## Próximo paso

Ejecutar por shell `oracle test --proyecto medidas --confiar-escalares` para comprobar la carga de las relaciones y medir el nuevo conteo de infracciones de `meta.toda_cantidad_comparada_tiene_unidad_derivable`, ajustando su cota en `medidas/oracle.json` si corresponde.

### Nota (2026-09-22 11:10:31 UTC)

2026-09-22, Claude: pieza no se redeclara — Oracle ya distribuye una relación pieza idéntica campo por campo, y declararla de nuevo hacía que el proyecto no cargara. Quedaron vecina y asentamiento. La deuda de unidades bajó de 54 a 51 y la cota de su sombra se bajó a 51 (meta.ninguna_cota_mas_alta_que_su_deuda lo exige). oracle test VERDE; suite 1240 sin fallas.
