---
title: "Revisión integral de Jam, Oracle y Unreal Engine 5.8.1"
tipo: PLAN
version: "1.0"
date: 2026-08-02
updated: 2026-08-02
status: en-progreso
area: 00-Proceso
tags:
  - jam
  - oracle
  - unreal
  - ue-5-8
  - pcg
  - pve
aliases:
  - Revisión Jam UE 5.8.1
  - Certificación Jam 5.8.1
---

# Revisión integral de Jam, Oracle y Unreal Engine 5.8.1

## Decisión

Pausar momentáneamente las funciones nuevas del Graph y revisar Jam en este orden:

1. recuperar una puerta verde confiable;
2. certificar el desacople y la integración de Oracle;
3. recertificar cada superficie de Jam en Unreal Engine 5.8.1;
4. explorar MCP/Toolsets, PCG 5.8, PVE y Sandboxes en spikes aislados;
5. reordenar el roadmap con esa evidencia.

No se mezclan en un mismo cambio la migración de motor, el reemplazo de una referencia histórica y
la adopción de una función experimental. Si una prueba queda roja, primero se determina cuál de esas
tres fronteras rompió.

## Hallazgos de apertura

- El árbol llegó limpio y `relevo.py` declaró verde.
- La suite real tiene 507 tests y el Vault 50 documentos; `RELEVO.md` todavía publica 496 y 48.
- Jam consume la fachada `oracle_metalenguaje.Motor`; Oracle no importa Jam ni Unreal. El embedding
  y sus decisiones están documentados en
  [[2026-07-31-PLAN-Autonomia-Embedding-Oracle-P3-v1.0|P3 de Oracle]].
- La distribución continúa acoplada a la ubicación vendorizada mediante `jam.bridge`, aunque ese
  conocimiento está centralizado.
- En la apertura sólo `placement` y `snap` corrían en sombra. La revisión posterior incorporó
  `scatter`, el `spline` modular operativo y el juicio unitario de `physics`; gobiernan todavía sus
  referencias históricas.
- El diferencial completo abrió rojo: `medidas/diferencial/relevo.json` quedó vencido respecto de
  `proceso.verificacion_vigente`. Por lo tanto, el verde de apertura no estaba exigiendo todas las
  puertas que `RELEVO.md` afirmaba.
- La migración a UE 5.8.1 certificó la compilación C++ y el camino real de funciones del Graph, pero
  no todas las superficies que habían sido verificadas en 5.7.4.
- La receta permanente todavía menciona `BuildSettingsVersion.V6` y `Unreal5_7`, mientras BotOO ya
  usa correctamente `V7` y `Unreal5_8`.
- La regla arquitectónica «sólo `ue.py` importa Unreal» no describe el árbol actual. Esta deuda es
  anterior a la migración y se audita aparte para no disfrazar refactors como compatibilidad.

## Fase 0 — puertas confiables (completa)

### Trabajo

- Diagnosticar la frescura de `relevo.json` y regenerarlo sólo si sus ocho escenarios conservan la
  polaridad esperada.
- Ejecutar diferencial y mutación con `--confiar-escalares`.
- Hacer que el cierre de turno no afirme que Oracle está verde con fixtures vencidos.
- Actualizar conteos, agente entrante y recetas de motor sin reescribir evidencia histórica.
- Probar por mutación cualquier nueva puerta: romperla deliberadamente tiene que volver rojo el
  cierre.

### Terminado

- 512 tests de Jam verdes.
- Vault verde.
- Todos los fixtures diferenciales vigentes y sin desacuerdos.
- Todos los mutantes de medida actuales muertos o una excepción individual razonada.
- `relevo.py --cerrar` rechaza un fixture vencido.

### Resultado 2026-08-02

- La causa inicial no era un fixture para aceptar otra vez: Jam usaba la medida base compartida
  `proceso.verificacion_vigente` sin declarar `"catalogo_base": true` en `medidas/oracle.json`.
- Habilitado el catálogo, los ocho escenarios de relevo conservaron una polaridad verde y siete
  rojas; el Vault conservó una verde y diez rojas después de agregar este documento.
- El diferencial cerró 419 acuerdos globales y 2558 veredictos individuales estables.
- La mutación cerró 163/163 mutantes de medida, con 16490 detecciones evaluadas.
- `relevo.py` ahora ejecuta el diferencial tanto al abrir como al cerrar. Se quitó deliberadamente
  esa puerta de la apertura: el test falló; restaurada, la suite quedó verde.
- `VIVO` ahora nombra sólo `Source`, `Content/Python/init_unreal.py`, `Content/Python/jam` y
  `oraculo`: cambiar tests no finge que cambió el runtime. El límite quedó fijado por regresión.

## Fase 1 — certificar Oracle como biblioteca y como sombra (completa)

### Contratos

- Los consumidores del runtime sólo importan `oracle_metalenguaje`, nunca internals del vendor.
- `jam.bridge` es el único lugar que conoce la raíz vendorizada en el intérprete de Unreal.
- El mismo proyecto funciona desde el subtree y desde un wheel aislado.
- Una medida ausente, una excepción o un desacuerdo quedan observables y nunca gobiernan como verde.
- La referencia histórica continúa mandando hasta sostener diferencial, mutación y prueba real.

### Camino real

Ejecutar `placement` y `snap` desde el editor completo 5.8.1, no por el commandlet que carece de
`PlacementSubsystem`. Comprobar la referencia, el informe de `Motor`, la coincidencia y el cierre del
proceso por separado.

### Terminado

Una matriz por dominio declara sensor, medidas, referencia, autoridad, prueba real, punto ciego y
próximo paso. Nada se reemplaza sólo porque dos implementaciones coincidieron una vez.

### Resultado 2026-08-02

- `vendor/oracle/tools/verificar_instalacion.py` construyó e instaló el wheel en un entorno aislado:
  namespace único, siete entry points y dos motores independientes fuera del checkout.
- Un test recorre todo `Content/Python/jam/*.py`: ningún módulo importa `nucleo`, `catalogos` o
  `perfiles`, y sólo `bridge.py` conoce `vendor/oracle`. El test se probó introduciendo un import
  interno deliberado en `oracle_shadow.py`; quedó rojo y volvió a verde al restaurarlo.
- La abstracción no es total en las herramientas de autoría: `tools/emitir_hechos_vault.py`,
  `tools/emitir_hechos_relevo.py` y `tools/emitir_diferencial.py` todavía importan `nucleo.*` y
  `catalogos.*`. No afecta al runtime, pero los acopla al checkout hasta que Oracle publique una
  fachada de autoría equivalente a `Motor`.
- `tools/experiments/verifica_oracle_shadow.py` dejó un arnés reproducible para el editor completo.
  En UE 5.8.1 produjo dos coincidencias de placement, cuatro de snap y cuatro de `snap.al_ras`, más
  el marcador `JAM_ORACLE_SHADOW_58 TODO VERDE — placement=True snap=True por UE 5.8.1`.
- Después del marcador, el desmontaje volvió a caer con `double free or corruption (out)` y código
  139. La funcionalidad está verde; el ciclo de vida completo del editor continúa rojo.

| Dominio | Sensor / medidas | Autoridad actual | Evidencia real | Punto ciego principal |
|---|---|---|---|---|
| placement | `Pieza`/AABB → `colocacion.bounds`, `colocacion.interpenetracion` | referencia histórica | UE 5.8.1 coincide | AABB no ve la forma fina de la malla |
| snap | `Pieza`/AABB → grilla, yaw, contacto y cara compartida | referencia histórica | UE 5.8.1 coincide | sólo están declarados los defaults de tolerancia |
| vault | hechos documentales → 10 medidas | doble vía | 11/11 escenarios coinciden | forma y enlaces, no pertinencia ni verdad |
| relevo | testigo/git → 6 medidas | referencia + puerta diferencial | 8/8 escenarios coinciden | no prueba gestos manuales |
| scatter | instancia/configuración/conteo/cobertura → 4 medidas | referencia histórica + sombra | UE 5.8.1 coincide en sano y saturado | AABB y centros; el aviso contra escena sigue manual |
| spline modular | colocaciones realizadas/largo → cobertura y solape | referencia histórica + sombra | UE 5.8.1 coincide en sano y solapado | largo nominal; no ve forma fina ni cruces no adyacentes |
| physics unitario | pieza/soportes AABB → suelo y separación vertical | referencia histórica + sombra | UE 5.8.1 coincide en flotando, apoyado y hundido | no ve colisión fina, pendiente ni asentamiento por raycast |
| reemplazo, espacio | todavía sin sensor para `Motor` | referencia histórica | fuera de esta fase | migración pendiente |
| pared R7 | constructor legado sustituido por `spline` | referencia histórica | sólo selftest legado | no migrar mientras no vuelva a ser camino de producto |

### Extensión 2026-08-09 — primer dominio completo: scatter

- `scatter.cantidad`, `scatter.contencion`, `scatter.interpenetracion` y `scatter.cobertura` cubren
  las cuatro decisiones que gobiernan `oracle_scatter`; el aviso contra piezas preexistentes sigue
  siendo informativo y manual porque todavía no tiene una política binaria defendible.
- El sensor puro compartido evita que el fixture y el runtime aplanen la evidencia de dos maneras
  distintas. Cien mundos —20 sanos y 20 por defecto aislado— coinciden con la referencia.
- La migración encontró una trampa operativa: `place` informaba como cantidad pedida la cantidad de
  actores que Unreal ya había logrado crear. Ahora conserva el número de puntos vivos; un fallo de
  spawn ya puede volver roja la medida de cantidad.
- Cuatro reducciones de borde cerraron los mutantes que el generador realista no podía fijar:
  interpenetración efectiva de 0,5 cm, dos profundidades, cobertura inmediatamente inferior a 0,6
  y dos observaciones de cobertura. El proyecto queda en **189/189 mutantes muertos**.
- UE 5.8.1 ejecutó la referencia y `Motor` sobre actores reales: sano y saturado coincidieron, con
  marcador `placement=True snap=True scatter=True`. El SIGSEGV posterior de desmontaje permanece
  separado como deuda de ciclo de vida.

### Extensión 2026-08-09 — pared significa spline modular

- `oracle_pared` y `pared.construir` son la implementación R7 que estiraba segmentos; el Graph ya no
  los usa. El verbo vivo es `t_spline → spline.construir → spline_core`, que conserva el largo real
  de cada módulo. Migrar R7 habría mejorado únicamente un selftest de código legado.
- `spline.cobertura` fija el mínimo de 90% y `spline.sin_solape` la tolerancia longitudinal de 1 cm.
  Sesenta mundos diferenciales cubren cadena sana, cobertura baja y solape aislado.
- El runtime verificaba el plan completo aunque Unreal no hubiese creado alguno de sus actores.
  Ahora conserva las colocaciones realizadas y tanto la referencia como `Motor` juzgan esa lista;
  un fallo de spawn reduce cobertura en vez de publicar una cadena sana inexistente.
- Invertir deliberadamente cobertura produjo 40 desacuerdos; volver a juzgar el plan rompió la
  regresión específica. El total queda en **579 acuerdos / 3078 veredictos** y **201/201 mutantes**.
- UE 5.8.1 creó cinco módulos sanos y cinco solapados: cobertura 1.0, cuatro juntas defectuosas y dos
  coincidencias de sombra. El marcador final incluyó `spline=True`; el desmontaje posterior cayó con
  `invalid pointer` y señal 6, sin adelantar la frontera de ciclo de vida.

### Extensión 2026-08-10 — apoyo físico unitario

- El camino vivo sin flujo de puntos es `t_drop → physics.soltar → ue.physics_texto`. Su referencia
  distingue `sin_suelo`, `flotando`, `apoyado` y `hundido`; únicamente `apoyado` es éxito.
- Un sensor puro selecciona de forma independiente el soporte AABB válido más alto bajo la pieza y
  publica suelo, `gap` y relación de asentamiento. `physics.tiene_suelo` y `physics.apoyado`
  reexpresan el juicio con tolerancia declarada de 1 cm.
- Ochenta mundos —20 por estado— forman el diferencial. Invertir a propósito el comparador de
  apoyo produjo desacuerdos en los casos sano, flotante y hundido antes de restaurarlo. El total
  queda en **659 acuerdos / 3238 veredictos** y **219/219 mutantes muertos**.
- UE 5.8.1 ejecutó tres juicios por el adaptador real sobre actores de dimensiones no supuestas:
  200 cm flotando, 0 cm apoyado y 20 cm hundido. Las tres sombras coincidieron y el marcador incluyó
  `physics=True`; el desmontaje posterior volvió a caer, esta vez con señal 139.
- `drop` con un flujo de puntos usa otra política: raycasts y `physics_core.asentar_tanda`. No queda
  certificado por estas medidas y se conserva como frontera de auditoría separada.

## Fase 2 — recertificación completa en UE 5.8.1

Los informes 5.7.4 no se corrigen en masa: son evidencia fechada. Se crea una certificación nueva con
motor, commit, camino y marcador de log por superficie.

| Superficie | Puerta real |
|---|---|
| Build C++ | `BotOOEditor` con `-NoUBA`, `V7` y `Unreal5_8` |
| Slate | inicio/cierre, tres nomad tabs, gestos pendientes y Undo/Redo |
| Python de UE | clases, métodos, constructores, propiedades, enums y nombres dinámicos |
| Geometry Script | primitivas, UV, vertex color, materiales y Static Mesh |
| TreeGen | ejemplos, tipos, HISM y materiales |
| Nanite/Substrate | conversión, material real y costo donde el modo headless lo permita |
| PCG | autoría, cableado verificado, generación, Preview, Bake y Discard |
| Dataflow/Fracture | editor GUI cuando el camino headless cuelgue |
| Oracle | `placement`, `snap`, `scatter`, `spline` y `physics` unitario con sombra observable |
| Graph | funciones, dos instancias, compilación y gestos Slate |

### Resultado parcial 2026-08-02

La primera pasada quedó documentada en
[[2026-08-02-INFORME-Certificacion-Jam-UE-5-8-1-v1.0|la certificación 5.8.1]]. El inventario de
`tools/check_unreal_api.py` se amplió de 75 llamadas de clase a 98 símbolos de primer nivel más esas
75 llamadas; UE 5.8.1 reconoce todo. El build, los ocho ejemplos, material/UV y PCG real están
verdes. Faltan Slate manual, Nanite/Substrate, Dataflow/Fracture y el ciclo completo de Preview.

## Fase 3 — oportunidades de UE 5.8

### MCP y Toolset Registry

Probar primero tres herramientas de bajo riesgo: inspeccionar selección, crear Preview y compilar un
Graph. Unreal aporta transporte y descubrimiento; Jam conserva intención, transacción y Oracle. Toda
operación mutante debe seguir siendo Preview o vivir en un Sandbox antes de persistir.

### PCG 5.8

Comparar las funciones con firma de Jam con los subgrafos embebidos de PCG, y el autor actual con el
`PCGToolset` nativo. También estudiar atributos complejos, parámetros jerárquicos y edición manual.
No se reemplaza una herramienta propia sin un escenario equivalente y una medida que discrimine.

### Procedural Vegetation Editor

PVE sigue experimental y queda como dependencia opcional. El primer spike debe:

1. habilitar PVE, PCG, Dynamic Wind y Nanite en un entorno aislado;
2. cargar o crear una variación;
3. exportar una malla estática o esquelética con Nanite;
4. poblarla mediante PCG;
5. medir tipo de asset, bounds, materiales, skeleton, viento, Nanite y limpieza transaccional.

PVE no reemplaza inicialmente TreeGen: entra como otra fuente de assets. «Biológicamente correcto»
no se acepta como veredicto sin una medida defendible.

### Sandboxes

Comparar su aislamiento y persistencia selectiva con Preview/Bake/Discard. La adopción sólo avanza si
la recuperación tras error y la limpieza de assets quedan observables.

## Orden de ejecución

1. Fase 0 completa.
2. Fase 1 completa.
3. Matriz 5.8.1.
4. Spike MCP/Toolsets.
5. Spike PCG 5.8.
6. Spike PVE/Sandboxes.
7. Roadmap nuevo; recién ahí retomar Fase 7 del Graph.

## No hacer durante esta revisión

- No editar `vendor/oracle/` a mano.
- No borrar verificadores históricos mientras gobiernan la sombra.
- No actualizar «5.7.4» a «5.8.1» en informes viejos sin repetir su prueba.
- No hacer PVE una dependencia dura mientras sea experimental.
- No confundir compilación, existencia de API y funcionamiento real.
- No renombrar ids de nomad tabs.

## Fuentes externas

- [Unreal Engine 5.8 is now available](https://www.unrealengine.com/news/unreal-engine-5-8-is-now-available)
- [Unreal Engine 5.8 Release Notes](https://dev.epicgames.com/documentation/unreal-engine/unreal-engine-5-8-release-notes)
- [Procedural Vegetation Editor](https://dev.epicgames.com/documentation/en-us/unreal-engine/procedural-vegetation-editor-pve-in-unreal-engine)
- [Unreal MCP](https://dev.epicgames.com/documentation/unreal-engine/unreal-mcp-in-unreal-editor)

## Relacionado

- [[2026-07-30-INFORME-Oracle-Metalenguaje-De-Medidas-v1.0|Oracle: metalenguaje de medidas]]
- [[2026-07-31-PLAN-Autonomia-Embedding-Oracle-P3-v1.0|Autonomía de embedding de Oracle]]
- [[2026-07-29-ROADMAP-Accesibilidad-Graph-v1.0|Roadmap de accesibilidad del Graph]]
- [[2026-07-25-ROADMAP-Vision-Producto-Jam-v1.0|Visión de producto de Jam]]
