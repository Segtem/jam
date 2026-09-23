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

## Próximo paso

el paquete está listo para el juez ciego.

### Nota (2026-09-23 11:48:59 UTC)

2026-09-23, Claude: el juez ciego (sesión limpia) marcó como 'no' en P1 exactamente los 5 controles, y avisó que algunos se notan a simple vista (textos sobre una servilleta y una limonada). Controles tan obvios sólo prueban que el modelo distingue basura de prosa, no que lea con criterio. Para una próxima corrida, los controles tienen que ser plausibles: documentos del tema correcto con el defecto sutil (un título que promete algo que el cuerpo no cumple, rutas que no existen).
