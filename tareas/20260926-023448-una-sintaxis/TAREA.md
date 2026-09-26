# Migrar medidas, casos y relaciones de JSON escrito a mano a la superficie de Oracle

- ESTADO: CERRADA
- PRIORIDAD: 65
- ETIQUETAS: oracle, sintaxis

### Nota (2026-09-26 02:34:48 UTC)

2026-09-26, Claude: Oracle adopta una sola sintaxis para escribir (tarea una-sintaxis de Oracle): la superficie .oracle/.caso/.relacion; el JSON canónico queda como formato interno y Oracle lo sigue leyendo. Acá todo está en JSON a mano (41 medidas, 35 casos y 3 relaciones en medidas/). Cómo: cuando Oracle publique la versión con convertir-lote y .relacion (sintaxis 0.8), medir con esa versión, correr oracle convertir medidas/ --a-superficie (convierte sólo si el árbol canónico queda idéntico y reemplaza el archivo), revisar lo no convertible uno por uno, y dejar oracle test --proyecto medidas --confiar-escalares en VERDE con los mismos números. Los fixtures de medidas/diferencial/ NO se convierten: son datos generados. Después, meta.se_escribe_en_superficie queda en verde (o en sombra con cota si algo no se pudo convertir). Depende de Oracle: convertir-lote, relaciones-superficie y la publicación.

### Nota (2026-09-26 02:41:00 UTC)

2026-09-26, Claude: al subir a la versión de Oracle con sintaxis 0.8, cuatro casos tienen que declarar «espera: sin_evidencia» (la aceptación ahora exige un rojo MEDIDO salvo que el caso declare que espera SIN EVIDENCIA): geometria-011-al-ras-sin-piezas-no-concluye, geometria-013-comparte-cara-sin-evidencia-no-concluye, physics-004-apoyado-sin-asentamiento-no-concluye y scatter-006-cobertura-sin-evidencia-no-concluye (revisión estática de Codex; confirmar midiendo).

### Nota (2026-09-26 23:33:54 UTC)

2026-09-26, Claude: hecho con Oracle 0.32.0 (sintaxis 1.0). Medido ANTES de tocar nada: con 0.31.1 VERDE (aceptación 32/3); con 0.32.0 sin migrar ROJO por exactamente lo previsto: los cuatro casos sin evidencia y meta.se_escribe_en_superficie. oracle convertir medidas --a-superficie --escribir: 79 archivos (41 medidas, 35 casos, 3 relaciones), 0 no convertibles, árbol canónico idéntico. Los cuatro casos (geometria-011, geometria-013, physics-004, scatter-006) declaran espera: sin_evidencia. formatear: todo en forma única. meta.se_escribe_en_superficie en 0, sin sombra. Pin a 0.32.0 en los tres lugares (AGENTS.md dos, ORACLE_VERSION) y vendor/oracle-pkg reinstalado; la herramienta global oracle también en 0.32.0. Resultado: oracle test VERDE, aceptación 28 rojos / 4 sin evidencia esperada / 3 verdes (los mismos 35 casos), diferencial 1099, mutación 448/448; suite 1241 OK.
