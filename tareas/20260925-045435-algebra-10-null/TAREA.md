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

## Próximo paso

Leer los escenarios `sin_suelo` y decidir la forma.

### Nota (2026-09-25 12:12:40 UTC)

2026-09-25, Brian delegó en Claude: el null de los fixtures de física se modela explícito con un bool más su medibilidad (por ejemplo tiene_suelo más tiene_suelo_medible); cuando no se pudo medir, valor = false y *_medible = false, y las medidas filtran por *_medible. Oracle 0.31.0 publica el álgebra 1.0; Jam sigue fijado en 0.30.0 hasta migrar fixtures y medidas y medir en verde.
