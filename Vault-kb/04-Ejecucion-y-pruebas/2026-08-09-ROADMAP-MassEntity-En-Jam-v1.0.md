---
title: "MassEntity en Jam: de una prueba de núcleo a poblaciones autorables"
tipo: ROADMAP
version: "1.0"
date: 2026-08-09
updated: 2026-08-09
status: en-progreso
area: 04-Ejecucion-y-pruebas
tags:
  - massentity
  - massgameplay
  - graph
  - runtime
  - verificacion
aliases:
  - Roadmap MassEntity
  - Mass en Jam
---

# MassEntity en Jam: de una prueba de núcleo a poblaciones autorables

## Decisión de arquitectura

Mass entra como una familia de **distribución y simulación runtime**, no como generación de malla.
Consume los `F` que ya producen curvas, puntos y Scatter, y primero los convierte en una receta
durable. Los handles de entidad pertenecen a un `UWorld`, son efímeros y no se serializan en el
Graph.

```text
P/S → F ───────────────┐
                       ├→ receta Mass → población runtime
MassEntityConfig ──────┘
```

El cerebro conserva datos planos y no importa `unreal`. El adaptador Python sólo traduce `F` a
`FTransform`; crear, consultar y destruir entidades vive en un módulo C++ runtime, porque
`FMassEntityManager`, fragments y processors no tienen una frontera Python suficiente.

## Tipos previstos

| Tipo | Significado | Persistencia |
|---|---|---|
| `F` | transforms/frames espaciales existentes | sí |
| `MC` | referencia a un `UMassEntityConfigAsset` | sí |
| `MS` | receta de población: config, transforms, seed y presupuesto | sí |
| `MH` | población viva administrada por Jam | no; pertenece al mundo |

La prueba inicial todavía no introduce `MC`, `MS` ni `MH`: `mass_probe` deja pasar `F`, crea
entidades reales con `FTransformFragment`, las mide y las destruye en la misma operación. Así prueba
el núcleo sin prometer todavía una vida útil que Preview/Bake/Discard no sabe administrar.

## Fases

### Fase 0 — prueba vertical de MassEntity core

**Estado: implementada y verificada en UE 5.8.1.** El tutorial público creó 37 entidades válidas,
leyó un solo arquetipo con `FTransformFragment`, conservó los transforms y dejó 0/37 handles vivos
tras destruir. La suite pura mutó el juicio de limpieza y pasó de verde a rojo.

- Agregar un módulo `JamMass` runtime dependiente sólo de `MassCore` y `MassEntity`.
- Exponer un puente reflejado que reciba transforms.
- Crear un arquetipo con `FTransformFragment`, crear N entidades, leer sus fragments y destruirlas.
- Medir cantidad, arquetipo común, suma de posiciones y limpieza completa.
- Ejecutarlo desde `mass_probe` por el camino público Compile/Run de Jam dentro de UE 5.8.1.

Salida: sabemos si Jam puede gobernar el `FMassEntityManager` real sin activar todavía el plugin
experimental `MassGameplay`.

### Fase 1 — receta pura y ciclo Preview

**Estado: cerrada y verificada en UE 5.8.1.** `MS` conserva frames, ruta MC
reservada, seed y presupuesto; `MH` conserva únicamente identidad de población, mundo, cantidad y
la suma esperada para inspección. Ninguno importa Unreal y MH nunca se serializa.

`mass_spawn`, `mass_inspect` y `mass_clear` crean, miden y destruyen una población administrada por
el módulo C++. Preview trata poblaciones como efectos runtime transaccionales: un segundo Run
destruye la anterior, un Run fallido revierte la nueva y Discard la libera. Bake conserva la
población sólo durante la vida del `UWorld`; no crea Content ni estado durable. Clear es idempotente.
`OnWorldCleanup` y `ShutdownModule` llaman una limpieza global. Una sonda confirmó además que abrir
un mapa vacío retira el MH del mundo anterior. La sonda PIE mantuvo simultáneamente tres entidades
en el mundo editor y tres en el `UWorld` PIE: al terminar la sesión, las primeras siguieron vivas y
el MH de PIE pasó a «inexistente o ya liberada». Neutralizar deliberadamente el callback dejó ese
MH registrado como perteneciente a otro mundo y puso roja la misma prueba; restaurarlo volvió a
verde. Así queda discriminada tanto la ejecución real del delegate como su alcance por mundo.
Ese corte todavía mantenía MassGameplay apagado y `config_path` no gobernaba el arquetipo; la
Fase 2 cerró ambas fronteras sin cambiar el contrato de vida de MH.

- Introducir `MS` como dato puro y `mass_spec` (`F + MC → MS`).
- Introducir `MH` para una población viva, nunca serializable.
- Hacer `mass_spawn`, `mass_inspect` y `mass_clear`.
- Atar Run/Discard a destrucción y decidir qué significa Bake para una población runtime.
- Soltar poblaciones también al cambiar de mundo, cerrar PIE o descargar el módulo.

Verificado en esta vertical: 37 entidades; Run×2 reemplaza; Discard destruye; Bake conserva; Clear×2
deja cero vivas; cambiar a un mapa vacío limpia la población confirmada; cerrar PIE limpia sólo el
mundo que termina. La sonda reproducible es `tools/experiments/verifica_mass_pie_58.py`. El editor
completo repite después del marcador el `double free` histórico de desmontaje, que no se confunde
con el ciclo PIE ya observado.

### Fase 2 — autoría MassGameplay

**Estado: primera vertical cerrada y verificada en UE 5.8.1.** El plugin experimental
`MassGameplay` queda habilitado explícitamente. `mass_config` valida un
`UMassEntityConfigAsset` real y sólo publica MC cuando su template contiene
`FTransformFragment`; `mass_spec` recibe ese MC por un pin de dato. Jam distribuye
`/Jam/Mass/MC_JamSpatial` como configuración mínima portable.

La creación configurada pasa por `AJamMassSpawner`, no por el atajo directo del manager. Un
generador determinista de Jam entrega los transforms a `UMassSpawnLocationProcessor`, y el puente
retiene los handles que registró el spawner para inspección y limpieza. La sonda pública
`verifica_mass_gameplay_58.py` creó un config temporal, ejecutó MC→MS→MH, midió 37/37 entidades,
cero diferencias espaciales y cero vivas después de Discard. Quitar deliberadamente el
`FTransformFragment` del trait, recompilar y repetir puso rojo el mismo Run; restaurarlo volvió a
verde.

- Activar `MassGameplay` de forma explícita y tratar su estado experimental como riesgo declarado.
- Seleccionar/crear `UMassEntityConfigAsset` y validar traits.
- Crear/configurar `AMassSpawner` con generadores de transforms de Jam.
- Medir que la cantidad pedida coincide con la registrada por el spawner.

El ejemplo portable `Poblacion-MassGameplay-Ambiental.jamgraph` deja visible toda la cadena. Esta
fase **no** promete todavía representación, LOD, navegación ni comportamiento. También quedó
observado que un nodo fuente rojo no cancela la ejecución de todos sus dependientes: el Run global
queda rojo y revierte Preview, pero nodos posteriores pueden calcular con parámetros por defecto.
Eso es una frontera general de Flow, no una entidad Mass confirmada.

### Fase 3 — representación escalable

- Configurar `MassRepresentation` y `MassLOD`.
- Permitir actor de alta/baja resolución, ISM y representación nula.
- Medir distribución por representación y presupuesto, sin confundir entidades con actores.

### Fase 4 — comportamiento

- Traits acotados para movimiento, señales y StateTree.
- ZoneGraph sólo cuando un caso de BotOO necesite navegación de multitudes.
- Fragments y processors personalizados como extensiones C++ tipadas, no strings arbitrarios.

### Fase 5 — juego empaquetado y red

- Confirmar que las recetas generadas por Jam sobreviven cook/package.
- Presupuestos por plataforma y pruebas prolongadas.
- Replicación sólo para la fracción de la población que tenga una necesidad de juego demostrada.

## Medidas de la Fase 0

La sonda queda verde únicamente si:

- recibe entre 1 y 4096 transforms finitos;
- crea exactamente una entidad válida por transform;
- todas comparten el arquetipo pedido;
- cada `FTransformFragment` conserva la posición con tolerancia de `0,001 cm`;
- después de destruir, ninguno de sus handles sigue válido.

La prueba se muta al menos cambiando la cantidad o una coordenada esperada: tiene que ponerse roja.

## Qué no ve la Fase 0

- No prueba `UMassEntityConfigAsset`, traits de MassGameplay ni `AMassSpawner`.
- No ejecuta processors ni demuestra orden o determinismo multihilo.
- No prueba representación, LOD, StateTree, ZoneGraph, PIE, cook ni replicación.
- Destruye la población en la misma llamada: no prueba todavía el ciclo de vida entre frames.
- Una suma de posiciones detecta el cableado espacial de esta muestra, pero no identifica por sí sola
  toda permutación o compensación posible de transforms.

## Caso BotOO que debe gobernar la Fase 3

La base ambiental —por ejemplo ratas o insectos— ya se distribuye desde `F` y mide cantidad,
limpieza y presupuesto. El siguiente corte debe agregar una sola representación ISM/LOD, todavía
sin navegación. Recién después de medir esa representación se agrega comportamiento.

## Relacionado

- [[2026-07-27-INFORME-Puente-P-a-F-Ops-Flow-v1.0|Puente P → F]]
- [[2026-07-26-PLAN-Preview-Transaccional-Efectos-PCG-v1.0|Preview transaccional]]
- [[2026-08-02-ROADMAP-Nodos-Unreal-Engine-5-8-1-v1.0|Nodos nativos de UE 5.8.1]]
