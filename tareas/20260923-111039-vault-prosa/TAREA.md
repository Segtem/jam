# El vault se verifica por su forma, no por lo que dice

- ESTADO: ABIERTA
- PRIORIDAD: 70
- ETIQUETAS: vault, prosa, jev


El hallazgo viene de Oracle (tarea 20260922-220029-jev-porque-v2): un juez ciego marcó 18 de 25 defensas de umbral como insuficientes, y un modelo barato (Jev, por OpenRouter) coincidió 15/15 con él y atrapó 10 de 10 textos deliberadamente vacíos, por centavos. El patrón para usarlo —relación declarada, medida que la juzga y sensor afuera— se está escribiendo en Oracle como ejemplo/sensor-prosa; ESTA tarea espera a que exista.

## El hueco

`tools/vault.py` comprueba nombre, frontmatter, carpeta y enlaces de los 70 documentos: la FORMA.
Nada comprueba que un documento **diga** lo que promete su título ni que una guía siga describiendo
lo que el código hace hoy. Un documento puede estar impecable de forma y mentir entero.

## Qué hacer

1. Tres o cuatro preguntas de sí o no por documento, escritas y con ejemplos de cada lado **antes**
   de correr nada. Por ejemplo: ¿el cuerpo trata del tema que anuncia el título?; ¿cita rutas o
   comandos que hoy existen en el repo?; ¿dice cuándo dejaría de ser válido?
2. **Juicio a ciegas primero**, sobre una muestra de 15 documentos, con controles: 5 documentos
   degradados a propósito, mezclados y sin marcar.
3. Correr el sensor, comparar, y anotar acuerdo, controles y costo.
4. Si el acuerdo es bueno: emitir los hechos como relación y agregar la medida **en sombra**, nunca
   directo a rojo. Si es malo: escribirlo y cerrar.

⚠ Un sensor probabilístico no decide: propone. Y la medida que use sus filas tiene que declarar en
su `alcance` que las produjo un modelo.


### Nota (2026-09-23 11:48:59 UTC)

2026-09-23, Claude: el juez ciego (sesión limpia) marcó como 'no' en P1 exactamente los 5 controles, y avisó que algunos se notan a simple vista (textos sobre una servilleta y una limonada). Controles tan obvios sólo prueban que el modelo distingue basura de prosa, no que lea con criterio. Para una próxima corrida, los controles tienen que ser plausibles: documentos del tema correcto con el defecto sutil (un título que promete algo que el cuerpo no cumple, rutas que no existen).

### Nota (2026-09-23 11:52:29 UTC)

Corrida Jev completa: typesafe/jev-1.13-20260917, mismo CRITERIO íntegro y 20 registros, cinco lotes de cuatro; 60 respuestas crudas guardadas y selladas antes de abrir juicio-ciego-claude.json y clave-operador.json. Exposición parcial del operador por nota previa de TAREA declarada antes de llamar; no enviada a Jev. Acuerdo en originales P1 15/15, P2 14/15, P3 11/15; controles 5/5 en cada pregunta. USD 0,001954302 según usage.cost, cinco HTTP 200, sin reintentos. RESULTADO.md conserva probabilidades de ambos lados, desacuerdos, costo, límites y recomendación: revisión a mano antes de sombra, especialmente P3; controles actuales demasiado gruesos. Integridad verificada sobre 20 ids y 60 respuestas. Escritura sólo en esta tarea; sin commits ni cierre global. Artefactos reproducibles en corrida-jev/; comparar_jev.py recalcula sin red.

## Próximo paso

Revisar a mano los cinco desacuerdos detallados en RESULTADO.md (uno en P2, cuatro en P3), sin alterar el juicio ciego ni esta corrida. Acordar si P3 incluye limitaciones técnicas o exige condiciones de vigencia; fijar la aclaración y ejemplos antes de otra prueba. Preparar después un piloto independiente con controles plausibles y ambas polaridades naturales por pregunta. No incorporar todavía una medida en sombra. La corrida del modelo y su comparación están completas; no hay bloqueo técnico.

### Nota (2026-09-23 11:58:57 UTC)

2026-09-23, revisión de Claude: coincido con revisión a mano. P1 15/15 y P2 14/15 son buenas, pero los controles eran obvios, así que 5/5 no prueba discriminación fina. P3 (vigencia) queda en 11/15 y es justo la pregunta que más interesa: 13 de 20 documentos no dicen hasta cuándo vale lo que afirman.
