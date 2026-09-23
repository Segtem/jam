# Resultado del piloto de prosa del vault

Corrida completa el 2026-09-23. **Recomendación: revisión a mano antes de adoptar una medida en sombra.**

Se conservaron el CRITERIO íntegro y los 20 registros (15 originales y 5 controles), sin editar título ni cuerpo. Se enviaron cinco lotes consecutivos de cuatro registros, con las tres preguntas independientes. Corte fijado antes de llamar: `p(sí) ≥ 0,5`; zona descriptiva cercana al corte: `[0,4; 0,6]`. No hubo ajustes ni reintentos después de ver el juicio.

## Acuerdo por pregunta

| Pregunta | Originales | Controles: acuerdo | Total | Claude sí/no (originales) | Jev sí/no (originales) |
|---|---:|---:|---:|---:|---:|
| P1 `tema_desarrollado` | 15/15 (100.0%) | 5/5 | 20/20 | 15/0 | 15/0 |
| P2 `referencia_concreta` | 14/15 (93.3%) | 5/5 | 19/20 | 15/0 | 14/1 |
| P3 `vigencia_delimitada` | 11/15 (73.3%) | 5/5 | 16/20 | 7/8 | 5/10 |

## Controles atrapados

| Pregunta | Jev contra defecto esperado | Claude contra defecto esperado |
|---|---:|---:|
| P1 | 5/5 | 5/5 |
| P2 | 5/5 | 5/5 |
| P3 | 5/5 | 5/5 |

Los cinco controles esperan **no en las tres preguntas**. Son degradaciones gruesas: atraparlos no demuestra sensibilidad a errores plausibles, citas inventadas o desactualización real. P1 y P2 tienen todos los originales positivos según Claude: no hay negativos naturales para estimar esos errores.

## Desacuerdos

- **dc5c58e4603 · vigencia_delimitada**: Claude sí, Jev no; p(sí)=0.38, p(no)=0.62. Documento: `Vault-kb/02-TreeGen/2026-07-27-INFORME-TreeGen-UV-Materiales-Sections-HISM-v1.0.md`. Justificación de Claude: Declara que la suite mockea unreal y por eso su verde no valida nombres de API. Cita: "**La suite no podía detectarlo**: mockea `unreal`, así que un nombre inventado pasa verde.".
- **dd04ee57e02 · vigencia_delimitada**: Claude sí, Jev no; p(sí)=0.31, p(no)=0.69. Documento: `Vault-kb/02-TreeGen/2026-07-26-INFORME-TreeGen-Curve-Child-Ramas-Jerarquicas-v1.0.md`. Justificación de Claude: Declara un cambio observable posterior que deja fuera de vigencia la descripción del ejemplo. Cita: "El ejemplo TreeGen vigente usa\n> `Curve Branches` para transportar 64 hijas en un solo cable `S`".
- **d1360d2d324 · vigencia_delimitada**: Claude no, Jev sí; p(sí)=0.53, p(no)=0.47. Documento: `Vault-kb/04-Ejecucion-y-pruebas/2026-07-25-INFORME-Auditoria-Proactiva-Jam-v1.0.md`. Justificación de Claude: Hay marcas temporales («al momento de la auditoría») y mención del checkout, pero no una condición explícita que limite la validez u obligue a revisar. Cita: "`git diff --check`: correcto al momento de la auditoría.".
- **d0622c3273e · vigencia_delimitada**: Claude sí, Jev no; p(sí)=0.30, p(no)=0.70. Documento: `Vault-kb/02-TreeGen/2026-07-27-INFORME-TreeGen-Asset-Set-Choose-Copy-Variants-v1.0.md`. Justificación de Claude: Declara un cambio posterior que invalida los conteos del ejemplo descritos arriba. Cita: "los 19 nodos y 20\n   conexiones de arriba quedaron en 21 y 21.".
- **d5349c3b488 · referencia_concreta**: Claude sí, Jev no; p(sí)=0.41, p(no)=0.59. Documento: `Vault-kb/04-Ejecucion-y-pruebas/2026-07-25-PLAN-Contratos-Defensivos-Tools-Assets-v1.0.md`. Justificación de Claude: Localiza riesgos en un archivo y funciones concretas. Cita: "`Drop`: si `place.colocar()` devuelve `None`, la fase de física recibe un actor inválido.".

La comparación mide acuerdo con Claude, no exactitud contra una verdad técnica. No se corrige el juicio para mejorar el acuerdo. Las probabilidades pertenecen a Jev; Claude entregó booleanos, no probabilidades. `p(no)` se calcula como complemento de `p(sí)`, no mediante otra llamada.

## Probabilidades y calibración descriptiva

| Pregunta | Brier originales / total | Originales cerca del corte |
|---|---:|---:|
| P1 | 0.0015 / 0.0014 | 0/15 |
| P2 | 0.0373 / 0.0282 | 1/15 |
| P3 | 0.1949 / 0.1474 | 6/15 |

Brier se calcula contra los booleanos de Claude. Una única muestra pequeña y controles artificiales no certifican calibración ni generalización. La tabla siguiente conserva los dos lados de las 60 respuestas; en cada celda: `Claude; p(sí) / p(no)`.

| ID | Tipo | P1 | P2 | P3 |
|---|---|---|---|---|
| d9d50e128d0 | original | sí; 0.97 / 0.03 | sí; 0.92 / 0.08 | no; 0.47 / 0.53 |
| d1b26a4702d | original | sí; 0.98 / 0.02 | sí; 0.79 / 0.21 | no; 0.40 / 0.60 |
| ddcc4b8bc68 | control | no; 0.03 / 0.97 | no; 0.03 / 0.97 | no; 0.04 / 0.96 |
| d42b3cb32d8 | original | sí; 0.97 / 0.03 | sí; 0.98 / 0.02 | no; 0.29 / 0.71 |
| d7122fdcb1d | control | no; 0.05 / 0.95 | no; 0.03 / 0.97 | no; 0.03 / 0.97 |
| d7dd1b4e57f | original | sí; 0.97 / 0.03 | sí; 0.86 / 0.14 | no; 0.18 / 0.82 |
| dbff9d1227b | original | sí; 0.94 / 0.06 | sí; 0.94 / 0.06 | no; 0.22 / 0.78 |
| dcd56f7d545 | control | no; 0.03 / 0.97 | no; 0.03 / 0.97 | no; 0.03 / 0.97 |
| d498676caf5 | original | sí; 0.98 / 0.02 | sí; 0.81 / 0.19 | no; 0.17 / 0.83 |
| dc600656334 | original | sí; 0.97 / 0.03 | sí; 0.71 / 0.29 | sí; 0.54 / 0.46 |
| d11fb0e3ed9 | original | sí; 0.97 / 0.03 | sí; 0.95 / 0.05 | sí; 0.64 / 0.36 |
| d916e186d3d | original | sí; 0.95 / 0.05 | sí; 0.95 / 0.05 | sí; 0.60 / 0.40 |
| dc5c58e4603 | original | sí; 0.97 / 0.03 | sí; 0.97 / 0.03 | sí; 0.38 / 0.62 |
| dd04ee57e02 | original | sí; 0.98 / 0.02 | sí; 0.93 / 0.07 | sí; 0.31 / 0.69 |
| dd273467fe6 | control | no; 0.02 / 0.98 | no; 0.02 / 0.98 | no; 0.03 / 0.97 |
| d1360d2d324 | original | sí; 0.94 / 0.06 | sí; 0.94 / 0.06 | no; 0.53 / 0.47 |
| d2d4bfa8813 | original | sí; 0.98 / 0.02 | sí; 0.97 / 0.03 | sí; 0.54 / 0.46 |
| d4db5b3d22e | control | no; 0.03 / 0.97 | no; 0.03 / 0.97 | no; 0.14 / 0.86 |
| d0622c3273e | original | sí; 0.98 / 0.02 | sí; 0.95 / 0.05 | sí; 0.30 / 0.70 |
| d5349c3b488 | original | sí; 0.93 / 0.07 | sí; 0.41 / 0.59 | no; 0.07 / 0.93 |

## Costo real informado por la API

Cinco HTTP 200, 60 respuestas, cero reintentos. Modelo efectivo: `typesafe/jev-1.13-20260917`. Total `usage.cost`: **USD 0.001954302** (0.195430200 centavos de dólar). No es una estimación por tarifas ni una auditoría de factura.
Tokens informados: 46531 de entrada y 1934 de salida. Suma de latencias HTTP: 3.011 s.

| Lote | Entrada | Salida | USD | Segundos |
|---|---:|---:|---:|---:|
| 1 | 14961 | 388 | 0.000628362 | 0.794 |
| 2 | 4715 | 382 | 0.000198030 | 0.527 |
| 3 | 6714 | 385 | 0.000281988 | 0.560 |
| 4 | 9209 | 385 | 0.000386778 | 0.503 |
| 5 | 10932 | 394 | 0.000459144 | 0.627 |

## Orden, integridad y límites

Respuestas crudas guardadas antes de abrir el juicio y selladas a las `2026-09-23T11:50:18.623012+00:00`. SHA-256 del juicio usado: `e9133ea32fdd668a7374072564de326549037d0971007d06aeeb71ced777dca5`. El usuario confirmó sesión limpia; el JSON no registra versión exacta ni fecha del juez.

Exposición del operador: `oracle tarea ver` mostró una nota previa que adelantaba el resultado P1 y la debilidad de controles. Se declaró antes de las llamadas. Ni esa nota, ni el juicio, ni la clave del operador se enviaron al modelo. No se afirma ceguera total del operador.

Validado: 20 ids únicos idénticos, 60 respuestas booleanas de Claude, 60 probabilidades válidas de Jev; reconstrucción desde HTTP idéntica al resumen; hashes de criterio, registros y respuestas intactos. Jev usa Noul y no devuelve citas ni justificaciones: conserva las preguntas semánticas, pero su formato de salida difiere de la plantilla de Claude. Véase [documentación de OpenRouter](https://openrouter.ai/blog/insights/what-is-jev/).

## Decisión y continuación

Recomiendo revisión a mano de los desacuerdos y del borde entre «limitación técnica» y «condición de vigencia» en P3. No basta el acuerdo de P1/P2 sobre controles obvios para promover el sensor. Tampoco descartaría la herramienta: el costo permite repetir un piloto mejor diseñado. Antes de considerar sombra, fijar un criterio aclarado con ejemplos positivos y negativos de P3 y una muestra independiente con defectos plausibles y ambas polaridades naturales por pregunta. No cambiar retroactivamente este criterio ni estas etiquetas.

P2 sólo mide una vía textual de contraste: **no verifica que una ruta exista**. P3 no certifica vigencia actual. Esta corrida no resuelve por sí sola la verdad de la documentación. No se creó medida, se modificó el vault ni se ejecutó el cierre global: el encargo limita toda escritura a esta tarea y prohíbe commits.

Artefactos: [protocolo](corrida-jev/protocolo-corrida.json), [sello previo](corrida-jev/sello-respuestas.json), [consumo](corrida-jev/consumo.json), [60 comparaciones](corrida-jev/comparaciones.json), [métricas](corrida-jev/analisis.json). Solicitudes y respuestas HTTP completas en `corrida-jev/solicitud-*.json` y `respuesta-cruda-*.json`. Recalcular sin red con `python tareas/20260923-111039-vault-prosa/comparar_jev.py`.
