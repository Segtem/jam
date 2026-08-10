---
title: "Certificación de Jam en Unreal Engine 5.8.1"
tipo: INFORME
version: "1.0"
date: 2026-08-02
updated: 2026-08-02
status: en-progreso
area: 04-Ejecucion-y-pruebas
tags:
  - jam
  - unreal
  - ue-5-8
  - oracle
  - pcg
  - geometry-script
  - materiales
aliases:
  - Certificación Jam 5.8.1
---

# Certificación de Jam en Unreal Engine 5.8.1

## Veredicto de esta pasada

La base automatizable de Jam funciona en **Unreal Engine 5.8.1**: compila, sus APIs Python existen,
los ocho ejemplos compilan, los tutoriales de material y UV ejecutan, PCG genera, Nanite→Fracture
conserva materiales y la sombra de Oracle coincide. La certificación completa sigue abierta porque
faltan gestos Slate, Substrate y el ciclo manual de Preview/Bake/Discard.

Motor: `5.8.1-0+UE5`. Commit de partida: `bc0bd89`. Proyecto host:
`/home/workstation/Dev/games/BotOO`.

## Matriz

| Superficie | Camino real | Resultado | Frontera pendiente |
|---|---|---|---|
| Build C++ | `Build.sh BotOOEditor … -NoUBA` con Target V7/Unreal5_8 | **verde**, 12,31 s; JamEditor ya estaba al día | forzar recompilación cuando cambie C++ |
| API Python | `UnrealEditor-Cmd` + `tools/check_unreal_api.py` | **98 símbolos + 75 métodos existentes** | propiedades/métodos de instancia y nombres construidos dinámicamente |
| Catálogo Aprender | Compile público de los ocho `.jamgraph` | **8/8 verdes**: Geometry, cuatro TreeGen, Debug, material y UV | correr/inspeccionar los ejemplos que colocan actores |
| Material + Geometry/UV | `verifica_tutoriales_material.py` con commandlet rendering | **TODO VERDE**: material, parámetro, cable al mesh, Static Mesh transaccional, proyección y pack UV | inspección visual y costo con GUI cuando corresponda |
| PCG | editor completo + `-ExecCmds`, 90 ticks | **verde**: 3 nodos, 4/4 cables, preset 600 cm, hex/triangular, 287 HISM | Preview/Bake/Discard manual y PCG 5.8 nuevo |
| Graph funciones | `verifica_funcion_graph.py` | **verde en 5.8.1**: id estable, guardar, firma, dos instancias y Compile | ABM, `Ctrl+G` y pines múltiples con las manos |
| Oracle | editor completo/commandlet + sondas específicas | **función verde**: placement, snap, `snap.al_ras`, scatter, spline, physics, reemplazo y espacio coinciden | espacio cubre el subconjunto vivo; desmontaje del editor completo falla; commandlet hereda 9 paquetes rotos de BotOO |
| MassEntity | sondas `verifica_mass_*_58.py` | **verde**: MS/MH, PIE por mundo, MC→MS→MH, LOD por distancia y presupuesto 1/1/1 con control ilimitado High=4 | sin actores high/low, navegación ni comportamiento |
| Slate | build y carga de `JamEditor` | módulo cargado | tabs, historial, gestos y Undo/Redo en GUI |
| Nanite | editor GUI + `verifica_nanite_fracture_58.py` | **verde**: copia Nanite y GC con `EnableNanite=true` | inspección visual y materiales incompatibles |
| Dataflow/Fracture | editor GUI, nodos y terminal v2 | **verde**: GC regenerada; 2/2 materiales distintos conservados | rotura en PIE y shutdown con señal 11 |
| Substrate | no corrido todavía | pendiente | conversión, material y medición real |

## Qué amplió esta revisión

`tools/check_unreal_api.py` sólo extraía `unreal.Clase.metodo`. Ahora también registra cada símbolo
de primer nivel: funciones del módulo, constructores, tipos y enums. La prueba headless se rompió a
propósito haciendo invisible `get_editor_subsystem`; falló y volvió a verde al restaurar el patrón.
En el motor real aparecieron 98 símbolos y 75 llamadas de clase, todos presentes.

El smoke `pcg_presets_test.py` también reveló una expectativa vieja. Preview conserva el nombre del
volumen, pero muestra `prev_JamPCG_…`; la sonda exigía que el label comenzara por `JamPCG`. El primer
run quedó rojo aunque el log mostraba 4/4 cables. Se cambió la identificación a tipo `PCGVolume` más
el nombre estable, y el segundo run completó 90 ticks, midió 287 instancias y salió con código 0.

## Rojos que no pertenecen a Jam

Los commandlets terminan con código 1 aunque el script reporte verde porque el Asset Registry de
BotOO encuentra nueve paquetes cuyo primer valor no es `PACKAGE_FILE_TAG`:

- tres meshes bajo `JamSpace/Mod_puerta`, `JamSpace/Mod_panel` y `JamMS/Resto`;
- seis texturas D/N de los packs de bricks Orange, Scruffy Red y Black.

No se tocaron: son estado del proyecto host y no evidencia de compatibilidad de Jam. Hasta que BotOO
los repare, la autoridad es el marcador específico del script en `Saved/Logs/BotOO.log`, acompañado
por la lista explícita de errores del host; el exit code solo no puede ser puerta verde.

El otro rojo sí cruza Jam, pero está delimitado: tanto `verifica_oracle_shadow.py` como la nueva
sonda Nanite/Fracture emiten su marcador verde y después el editor cae durante shutdown con código
139. Por eso la matriz separa **función** de **ciclo de vida**.

La repetición del 2026-08-09 amplió la sonda Oracle a `scatter`. Sobre actores creados por el editor,
el reparto sano quedó verde, el saturado produjo 36 pares interpenetrados y ambas evaluaciones de
`Motor` coincidieron con la referencia. El marcador final fue
`JAM_ORACLE_SHADOW_58 TODO VERDE — placement=True snap=True scatter=True por UE 5.8.1`; después se
repitió la señal 11 histórica durante el desmontaje.

La sonda de presupuesto Mass repitió el defecto de desmontaje después de medir su marcador verde.
Un control mínimo que sólo abrió y cerró BotOO lo reprodujo, y también lo hizo con
`-DisablePlugins=Jam`: el heap corrupto del shutdown pertenece al host/editor de esta instalación,
no al camino Mass ni al plugin Jam cargado. Sigue siendo un rojo real del entorno y no se usa el
marcador funcional para declararlo resuelto.

La extensión siguiente probó el reemplazo operativo de la pared R7: `spline` coloca módulos sin
estirarlos. Una cadena de cinco piezas dio cobertura 1.0; otra con `gap` negativo produjo cinco
piezas y cuatro juntas solapadas. Las dos evaluaciones de `Motor` coincidieron y el marcador terminó
en `placement=True snap=True scatter=True spline=True`. Tras escribirlo, el shutdown abortó con
`munmap_chunk(): invalid pointer` y señal 6; la función está verde y el ciclo de vida continúa rojo.

La repetición del 2026-08-10 agregó el juicio físico unitario que usa `drop` sin puntos. El selftest
dejó de suponer el tamaño de un cubo y construyó flotación, apoyo y hundimiento desde los AABB reales
del asset elegido. UE midió respectivamente 200, 0 y -20 cm de separación; las tres evaluaciones de
`Motor` coincidieron con la referencia y el marcador terminó en
`placement=True snap=True scatter=True spline=True physics=True`. El editor cayó después del
marcador con señal 139. En ese corte, el asentamiento de una tanda por raycasts seguía fuera de la
certificación.

La extensión de lotes cerró esa frontera con `verifica_physics_paint_58.py`: tres cubos reales
terminaron con bases 0/100/200 cm pese a entrar fuera de orden; una pieza ignoró correctamente el
Preview anterior, y cuatro piezas sobre Landscape recibieron cotas por raycast en vez del top global
del AABB. Las tres sombras `physics.tanda` coincidieron. El marcador
`JAM_PHYSICS_PAINT_58 TODO VERDE` se emitió antes del código 1 causado exclusivamente por los nueve
paquetes inválidos ya delimitados de BotOO.

La extensión siguiente incorporó `replace` por el editor completo. Un reemplazo ajustado preservó
centro, base y planta; el asset a escala nativa rompió la planta por `(-98,5, -107,0)` cm; y un
tercer actor desplazado 10 cm rompió centro y base conservando el footprint. Las tres evaluaciones
de `Motor` coincidieron y el marcador terminó en
`placement=True snap=True scatter=True spline=True physics=True reemplazo=True`. El shutdown
posterior repitió `double free or corruption` y señal 6.

La repetición final del 2026-08-10 incorporó el grafo de espacio que el adaptador de nivel produce
hoy: entrada, extracción, llaves y puertas. El sensor independiente recorre estados `(nodo, llaves)`
y tres medidas exigen inicio único, meta única y extracción alcanzable. El diferencial cubre 100
mundos; invertir la regla de alcance hizo fallar 60. En el editor, la sonda creó cinco actores,
escribió y volvió a leer sus tags `jam:*`, certificó el mapa ganable, quitó el enlace a la llave y
certificó el rojo. Cuatro sombras coincidieron y el marcador terminó en `espacio=True`; el shutdown
posterior repitió señal 6. Switches, hazards, flags, recursos, tareas, canales y subgrafos sin aplanar
se rechazan explícitamente: no forman parte todavía del contrato vivo de `nivel.py`.

La sonda final de MassEntity cerró la Fase 1 en un PIE real. Conservó una población de tres
entidades en el mundo editor, creó otra de tres dentro del `UWorld` PIE y pidió el fin de la sesión.
Después de `CleanupWorld`, la población del editor seguía íntegra y el identificador PIE ya no
existía. Con `ClearAllPopulations(World)` neutralizado y el mutante recompilado, la misma sonda quedó
roja porque el registro retenía las tres entidades del mundo destruido; restaurar y recompilar
devolvió `JAM_MASS_PIE_58 TODO VERDE`. El desmontaje posterior repitió el `double free` conocido,
después del marcador y fuera de la frontera PIE observada.

La vertical siguiente cerró la autoría mínima de MassGameplay. Un
`UMassEntityConfigAsset` temporal recibió `UJamMassTransformTrait`, `mass_config` publicó MC sólo
después de observar un template espacial y el Graph conectó MC con MS. `mass_spawn` creó 37
entidades mediante `AJamMassSpawner` y `UMassSpawnLocationProcessor`; `mass_inspect` confirmó ruta
del config, clase del spawner y cero transforms distintos, y Discard dejó cero vivas. Al recompilar
un mutante sin `FTransformFragment`, el mismo Run quedó rojo en `mass_config`; restaurar devolvió
`JAM_MASS_GAMEPLAY_58 TODO VERDE`. Jam incluye además el config portable
`/Jam/Mass/MC_JamSpatial`.

La vertical de representación agrega `/Jam/Mass/MC_JamAmbientISM`: un trait Stationary y tres
procesadores Jam aislados por tag habilitan la cadena que Epic deja dinámica. En PIE jugable, cuatro
entidades delante del viewer resolvieron High/Medium/Low/Off una vez cada una; tres eligieron ISM y
la cuarta `None`. Los cuatro descriptores de malla fueron válidos y Clear dejó cero vivas. La prueba
usa PlayerController, frustum y ticks reales: Simulate sin viewer había enviado todo a Off y sirvió
para discriminar la frontera. Todavía no certifica saturación de presupuesto, representación Actor
ni comportamiento.

## Próximo bloque

1. Cerrar Slate/Graph con los cinco gestos pedidos en `RELEVO.md`.
2. Correr Preview/Bake/Discard de PCG y colocación de ejemplos en una sesión visible.
3. Certificar Substrate y la rotura de Geometry Collections en PIE.
4. Recién entonces abrir spikes aislados de MCP/Toolsets, PCG 5.8, PVE y Sandboxes.

## Relacionado

- [[2026-08-02-PLAN-Revision-Jam-Oracle-UE-5-8-v1.0|Plan de revisión integral]]
- [[2026-07-30-INFORME-Oracle-Metalenguaje-De-Medidas-v1.0|Oracle: metalenguaje de medidas]]
- [[2026-07-29-INFORME-Funciones-Graph-Firma-v1.0|Funciones Graph con firma]]
- [[2026-08-02-INFORME-Nanite-Fracture-Dataflow-UE-5-8-v1.0|Nanite a Fracture en UE 5.8]]
