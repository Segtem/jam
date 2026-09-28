# Jam fuera del motor: núcleo y adaptadores

- ESTADO: ABIERTA
- PRIORIDAD: 94
- ETIQUETAS: arquitectura, decision, commander

- Adjunto: [2026-09-27-JAM-FUERA-DEL-MOTOR.md](2026-09-27-JAM-FUERA-DEL-MOTOR.md)

## Por qué

2026-09-27, Brian: ¿Jam tiene que vivir dentro de Unreal, o puede ser un núcleo fuera del motor
(grafo, DSL, registro neutro de verbos, cálculo puro) con un adaptador por motor —Unreal, Godot,
Unity— que ejecuta lo que ese motor puede y declara sus capacidades? La propuesta, con la medición
del código, está en el adjunto. El acople de verdad está en `tools.py`, que mezcla la descripción
de cada verbo con su ejecución en el motor.

## Qué hacer

Nada hasta que Brian decida. Si va por este camino, las etapas y su criterio de hecho están en el
adjunto: 1) partir `tools.py` (registro neutro al núcleo, implementaciones a `adapter_unreal`; la
más barata y no rompe nada), 2) contrato JSON y adaptador de Unreal, 3) UI web, 4) adaptador de
Godot.

Una corrección a la medición del adjunto (2026-09-27, Claude): `tools.py` tiene 118 líneas con
`"fn":` escritas a mano, pero `tools.REGISTRO` carga **171** verbos: el resto se genera al importar.
Las 171 apuntan a funciones de `jam.tools`, así que la etapa 1 las abarca a todas, no a 116.

Relación con otras tareas: `dsl-grafos` suma a su pedido de diseño el criterio de esta nota (el
grafo y el DSL fuera del motor, sin `unreal`, sobre un registro neutro con capacidades); `jam-mcp`
queda más limpio afuera. La etapa 1 puede ir apenas termine `dsl-grafos`, o antes si se quiere que
su diseño nazca sobre el registro neutro.

## Próximo paso

**Decisión de Brian:** ¿se va por este camino?, y si sí, ¿la etapa 1 antes o después de
`dsl-grafos`?
