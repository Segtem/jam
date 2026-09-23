# Las defensas y alcances de las 83 medidas nunca se revisaron

- ESTADO: ABIERTA
- PRIORIDAD: 60
- ETIQUETAS: prosa, medidas


El hallazgo viene de Oracle (tarea 20260922-220029-jev-porque-v2): un juez ciego marcó 18 de 25 defensas de umbral como insuficientes, y un modelo barato (Jev, por OpenRouter) coincidió 15/15 con él y atrapó 10 de 10 textos deliberadamente vacíos, por centavos. El patrón para usarlo —relación declarada, medida que la juzga y sensor afuera— se está escribiendo en Oracle como ejemplo/sensor-prosa; ESTA tarea espera a que exista.

## Qué hacer

Pasar el mismo criterio de Oracle sobre las 83 medidas de `medidas/`: qué defensas permiten derivar el umbral y cuáles sólo dicen por qué la regla importa. Reescribir las insuficientes, sin inventar: si el número no se puede defender, se revisa el umbral. Empezar por las medidas con umbral distinto de cero, que son las que más se prestan a un número puesto a ojo.

## Próximo paso

Después de `20260923-111039-vault-prosa`: el mismo tratamiento, con el criterio ya probado.
