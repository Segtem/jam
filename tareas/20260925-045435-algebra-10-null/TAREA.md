# Oracle álgebra 1.0 rechaza null: los fixtures de física lo usan en tiene_suelo, apoyado y tanda_completa

- ESTADO: ABIERTA
- PRIORIDAD: 80
- ETIQUETAS: oracle, fisica


## Por qué

Oracle `main` (tarea `algebra-10`, sin publicar todavía) implementa el álgebra 1.0: un campo `null`
explícito se rechaza al cargar la evidencia, y los predicados exigen booleanos estrictos. Medido el
2026-09-25 con el núcleo de esa rama: ROJO, con 10 desacuerdos del diferencial en `physics.json` y
`physics_tanda.json` (escenarios `sin_suelo`: `physics.tiene_suelo`, `physics.apoyado` y
`physics.tanda_completa` pasan a levantar error por `null` explícitos), además de fallas de mutación.

## Qué hacer

Decidir qué significa cada `null` en los fixtures de física (¿«no hay suelo», «no se midió»?),
modelarlo explícito (un `bool` más un campo que diga si se pudo medir) y regenerar los fixtures.
Volver a medir con el núcleo nuevo antes de subir el pin, cuando Oracle publique el álgebra 1.0.

### Nota (2026-09-25 12:12:40 UTC)

2026-09-25, Brian delegó en Claude: el null de los fixtures de física se modela explícito con un bool más su medibilidad (por ejemplo tiene_suelo más tiene_suelo_medible); cuando no se pudo medir, valor = false y *_medible = false, y las medidas filtran por *_medible. Oracle 0.31.0 publica el álgebra 1.0; Jam sigue fijado en 0.30.0 hasta migrar fixtures y medidas y medir en verde.

### Nota (2026-09-25 22:07:03 UTC)

2026-09-25 Codex: migré hechos de física y tanda a valores explícitos con marcas *_medible; gap y soporte sin suelo usan 0.0/"" con medibilidad falsa, y las medidas rechazan lo indecidible. Regeneré physics.json, physics_tanda.json y vault.json; agregué relación asentada, casos de corpus para ausencia e inconsistencia del emisor, y ajusté cotas de sombras según los recuentos medidos. Oracle 0.31.0 en venv temporal /tmp/jam-oracle-031-venv: oracle test --proyecto medidas --confiar-escalares VERDE; corpus 35, diferencial 1099/1099, mutación 448/448. Suite Jam 1241/1241; tools/vault.py verde; 91 JSON de medidas sin null. Instalación directa desde PyPI impedida por DNS del sandbox: usé rueda local oracle_metalenguaje-0.31.0 del árbol temporal de Oracle. No cambié pin ni hice commits.

### Nota (2026-09-25 22:07:45 UTC)

Chequeo obligatorio de relevo: python tools/relevo.py --cerrar informa ROJO por árbol sin commit, ausencia de origin/t-algebra-10-null y verde_editor viejo (d207caf). Los dos primeros son esperados por el pedido explícito de no hacer commits ni pushes; la verificación con motor y la actualización de verde_editor quedan para el cierre de Claude tras revisar y subir el pin.

## Próximo paso

Claude: revisar esta migración, instalar Oracle 0.31.0 desde PyPI cuando haya red, actualizar el pin y el wheel embebido, repetir Oracle y la suite del repo; luego cerrar la tarea según el protocolo de relevo.
