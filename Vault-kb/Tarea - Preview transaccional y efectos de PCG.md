---
title: "Tarea: Preview transaccional y efectos de PCG"
date: 2026-07-25
updated: 2026-07-26
status: en-progreso
priority: alta
area: Jam/Preview
tags:
  - jam
  - preview
  - unreal-engine
  - pcg
  - transactions
  - bug
---

# Tarea: Preview transaccional y efectos de PCG

## Estado actual

La transacción de actores nuevos y la primera transacción de assets de Content están implementadas.
PCG ya participa del ciclo completo:

```text
Compile → Run
          ├─ error    → rollback de actores + PCGGraph temporal
          ├─ Discard  → borra PCGVolume + PCGGraph temporal
          └─ Bake     → conserva PCGVolume + promueve PCGGraph a /Game/JamPCG
```

La tarea general permanece `en-progreso` porque `normalize`, la recuperación persistente de todos los
writers históricos sin actor, mutaciones de actores ya existentes y Undo/Redo todavía no cubren todo
el ciclo. El nuevo nodo Nanite sí cubre explícitamente el caso asset-only.

## Implementación — actores

- Los tags del nivel son la fuente de verdad; ya no se depende de una lista Python volátil.
- Cada actor temporal lleva `jam:preview` y `jam:preview-owner=<owner>`.
- `graph` y `dash` mantienen previews independientes.
- Un Run nuevo se prepara mientras el Preview anterior sigue vivo. Sólo un Run correcto lo reemplaza.
- Una excepción destruye los actores parciales y conserva el Preview anterior.
- Bake y Discard reconstruyen el estado recorriendo actores, incluso después de recargar Python.
- Borrar manualmente un actor no deja referencias Python inválidas.
- Si un nodo del Graph devuelve estado `error`, falla la ejecución completa y se hace rollback.

La ventana Graph expone `✓ Bake` y `✗ Discard` en la barra y en el menú `Solution`. Ambas acciones
están limitadas al owner `graph`; no afectan el Preview de Dash.

### Convención visible en el World Outliner

El estado del actor también se comunica mediante su nombre, sin reemplazar la seguridad de los tags:

| Acción | Nombre en Outliner | Estado real |
|---|---|---|
| `Compile` | no crea ni renombra actores | sólo valida lógica y contratos |
| `Run graph` | `prev_<nombre-original>` | conserva `jam:preview`; Discard puede borrarlo |
| `Discard` | el actor desaparece | se eliminan sólo actores todavía marcados como Preview |
| `Bake` | `bake_<nombre-original>` | se quitan los tags de Preview; ya no responde a Discard |

El nombre original se guarda codificado en `jam:preview-label=<base64>` mientras dura el Preview.
Esto permite recuperar el nombre incluso después de recargar Python, evita acumular prefijos al
reintentar y hace que un Bake fallido vuelva correctamente a `prev_*`. El prefijo es una señal visual;
la pertenencia a Preview siempre se decide por tag, de modo que escribir manualmente `bake_` en otro
actor no cambia su estado.

## Implementación — PCGGraph temporal

`pcg` salió de `tools.SIN_SPAWN`, por lo que su `PCGVolume` se trata como Preview. Además,
`pcg.realizar()` solicita a `panel.preview_asset_path()` la ruta donde debe construir el grafo:

```text
/Game/JamPreview/<owner>/PV_<run-id>_<nombre>
```

El par `{temp, final}` se serializa en un tag `jam:preview-assets=<base64-json>` del actor. Así el
registro también sobrevive a un reload de módulos y no depende de una referencia al UObject.

### Run y rollback

- El asset final bajo `/Game/JamPCG` no se toca durante Run.
- Si la tool falla después de crear el PCGGraph, rollback elimina el asset temporal y los actores
  parciales.
- Un Run correcto reemplaza el Preview anterior del mismo owner y limpia su asset temporal.
- Si Unreal rechaza esa limpieza, se conserva el actor anterior con su registro recuperable; no se
  pierde la ruta del huérfano.

### Discard

- Borra el PCGGraph temporal y luego el PCGVolume.
- Si Unreal no puede borrar el asset, conserva el actor y sus tags para permitir otro intento. El
  resultado informa `DESCARTE incompleto` en vez de ocultar el fallo.

### Bake

- Renombra el PCGGraph temporal a su ruta final bajo `/Game/JamPCG`.
- Nunca sobreescribe Content existente: si el nombre ya existe usa sufijos `_2`, `_3`, etc.
- Después de promover el asset quita del actor los tags de Preview y de assets.
- Si falla un rename, revierte los renames previos que pueda y deja el Preview disponible para
  reintentar o descartar.

### Fix 2026-07-26 — un `bake_*` perdía su PCGGraph en el Run siguiente

Se reprodujo el caso `Run → Bake → Run`: el `PCGVolume` baked podía conservar internamente la
referencia al UObject de la ruta temporal aun después de renombrar el asset. Al ejecutar de nuevo,
Unreal procesaba/liberaba ese objeto transitorio y el componente baked quedaba sin Graph, aunque el
actor `bake_*` siguiera visible.

La corrección agrega dos garantías:

- después de promover el asset, Bake carga explícitamente el `PCGGraph` final, lo reasigna al
  `PCGComponent`, verifica su Object Path y regenera el componente;
- cada escritura de tags se relee y verifica. Antes `ue.set_tags()` ocultaba excepciones, por lo que
  era posible mostrar el prefijo `bake_` aunque Unreal hubiera conservado `jam:preview`; ahora Bake se
  cancela y restaura `prev_*` si los tags no coinciden.

También se agregó rollback de las promociones si falla la reasignación. El test de regresión realiza
`Run → Bake → Run → Discard` y comprueba que el primer actor continúa en el nivel, sigue llamado
`bake_*` y conserva la ruta final bajo `/Game/JamPCG`.

### Fix 2026-07-26 — Fracture borraba la Geometry Collection del Bake anterior

El segundo reporte del usuario permitió identificar que el caso real era:

```text
Asset → Fracture → Place
```

El log de Unreal confirmó que cada Run llamaba a Fracture sobre la ruta determinista
`/Game/JamDF/Fractures/GC_<mesh>`. `fracture.fracturar()` eliminaba esa Geometry Collection antes de
recrearla. El actor `bake_Jam_GC_*` anterior no desaparecía necesariamente del Outliner, pero su
`rest_collection` quedaba sin asset; por eso el modelo visible desaparecía.

La corrección:

- crea tanto `DF_*` como `GC_*` en rutas únicas bajo `/Game/JamPreview/graph` durante Run;
- registra ambos assets para rollback, Discard y Bake;
- propaga desde Fracture la ruta temporal **real** al `Place` siguiente. Compile conserva la ruta
  final prevista, pero Run ya no reutiliza esa predicción para ejecutar consumidores;
- Bake promueve ambas rutas sin sobrescribir versiones anteriores;
- un Run posterior crea otra pareja temporal y no elimina ningún Dataflow/Geometry Collection baked.

Se agregaron dos regresiones puras: propagación runtime `Fracture temporal → Place` y
`Run → Bake → Run → Discard` conservando los dos assets finales y el primer actor baked.

### Mejora 2026-07-26 — Preview compuesto sólo por assets

El nodo [[Nodo Graph - Convert to Nanite]] puede ejecutarse como `Asset → Nanite`, sin crear actores.
Antes, el registro `{temp, final}` sólo sobrevivía si se podía adjuntar al tag de un actor, por lo que
Bake/Discard respondían que no existía Preview.

`panel.py` ahora conserva registros por owner y permite persistirlos como metadatos del propio asset
temporal (`JamPreviewOwner`/`JamPreviewFinal`). Bake, Discard y `hay_preview()` combinan actores,
registros en memoria y Content recuperado. La prueba real en UE 5.7.4 cubre
`Run → Bake → Run → Discard` sin actores y confirma que el primer asset baked permanece intacto.

## Archivos modificados

- `Content/Python/jam/panel.py`: staging, tags persistentes, rollback, promoción y limpieza de assets.
- `Content/Python/jam/pcg.py`: creación del PCGGraph en ruta temporal durante Preview.
- `Content/Python/jam/fracture.py`: Dataflow y Geometry Collection temporales durante Graph Preview.
- `Content/Python/jam/graph.py`: propagación runtime de la salida real de transformadores de assets.
- `Content/Python/jam/tools.py`: PCG vuelve al wrapper de Preview.
- `Content/Python/jam/api.py`: Bake/Discard con scope por owner.
- `Content/Python/jam/preset.py`: presets Flow identificados como owner `dash`.
- `Source/JamEditor/Private/SJamGraphEditor.cpp` y `.h`: acciones visibles de Bake/Discard.
- `Source/JamEditor/Private/JamEditorModule.cpp` y `.h`: puente Graph → Python por owner.
- `Content/Python/tests/test_preview_transaction.py`: contratos de transacción headless.

## Verificación 2026-07-26

- 12 pruebas de Preview: reemplazo por owner, rollback de actor/asset, recuperación desde tags,
  Discard con scope, limpieza de asset, Bake sin overwrite y conservación ante fallos de promoción o
  borrado, incluidas las regresiones `Bake → Run` de PCG y Fracture.
- 13 pruebas Graph, incluida la propagación de rutas producidas durante Run.
- Suite Jam completa: **31/31 tests correctos**.
- Todos los archivos Python bajo `Content/Python/jam`: sintaxis correcta.
- `git diff --check`: correcto.
- La fase C++ de la ventana Graph compiló y enlazó correctamente con Unreal 5.7.

Se intentó antes un smoke de spawning con `UnrealEditor-Cmd -nullrhi`, pero Unreal 5.7 produjo un
`SIGFPE` interno en `FSceneViewport::EnqueueBeginRenderFrame`/hit proxies antes de devolver el control
a Python. No se guardó el nivel temporal. La verificación real de spawn/PCG debe hacerse de forma
interactiva o con Unreal Automation en un entorno renderizable.

## Prueba manual recomendada

1. Reiniciar/recompilar el editor para cargar el módulo y Python actuales.
2. Ejecutar un Graph válido que contenga PCG.
3. Verificar un asset `PV_*` bajo `/Game/JamPreview/graph` y un `PCGVolume` marcado como Preview.
4. Pulsar `Discard`: ambos deben desaparecer.
5. Volver a ejecutar y pulsar `Bake`: el volumen debe quedar y el grafo debe moverse a
   `/Game/JamPCG/<nombre>`.
6. Repetir con un asset final del mismo nombre: debe aparecer `<nombre>_2`; el original no debe
   modificarse.
7. En el World Outliner comprobar `prev_<nombre>` después de Run y `bake_<nombre>` después de Bake.
8. Pulsar Discard tras Bake: debe informar que no hay Preview y conservar el actor `bake_*`.

## Alcance pendiente

- `fracture` usado sin un actor de salida (por ejemplo desde Dash): falta un manifiesto persistente de
  sesión donde guardar el registro; `Fracture → Place` dentro del Graph ya está transaccionado.
- `normalize`: archivo de kit y actores existentes modificados sin snapshot/rollback.
- Cambios y destrucciones de actores preexistentes; actualmente el diff cubre actores nuevos.
- Undo/Redo nativo de Unreal para Run, Bake y Discard.
- Varias ventanas Graph simultáneas: hoy comparten el owner `graph`; harían falta ids de sesión.
- Prueba automatizada dentro de un Unreal Editor renderizable para spawn, referencias PCG y rename.
- Extender `register_preview_asset()` a Fracture/otros writers históricos cuando puedan ejecutarse
  sin actor; Nanite ya persiste su manifiesto en el propio asset temporal.

## Criterios

- [x] Una tool que spawnea y luego falla no deja actores permanentes.
- [x] Tras reload, Jam recupera Preview desde tags.
- [x] Graph y Dash no descartan previews ajenos.
- [x] PCG Discard elimina volumen y asset temporal en la ruta normal.
- [x] PCG Bake no sobreescribe un asset final existente.
- [x] Un fallo de promoción/borrado conserva información suficiente para reintentar.
- [x] Outliner distingue `prev_*` de `bake_*` y Discard no toca actores baked.
- [x] `Fracture → Place` declara, propaga y resuelve Dataflow/Geometry Collection temporales.
- [ ] Todos los writers de sólo Content tienen manifiesto persistente; Nanite ya lo cumple, Fracture
  directo desde Dash todavía no.
- [ ] Mutaciones sobre actores existentes tienen rollback.
- [ ] Bake/Discard son Undoable mediante transacciones de Unreal.

## Relacionado

- [[Tarea - compilacion estricta y ciclo Preview Bake del Graph]]
- [[Tarea - errores y resultados observables de Flow]]
- [[Auditoria proactiva de Jam - 2026-07-25]]
