---
title: "Tarea: compilación estricta y ciclo Preview/Bake del Graph"
date: 2026-07-25
status: en-progreso
priority: alta
area: JamEditor/Graph
tags:
  - jam
  - graph-editor
  - dataflow
  - validation
  - preview
  - technical-debt
aliases:
  - Graph usa asset activo sin conexión
  - Preflight del Graph
  - Preview y Bake del Graph
---

# Tarea: compilación estricta y ciclo Preview/Bake del Graph

## Avance 2026-07-26 — Preflight implementado

La primera etapa ya está integrada: el Graph ahora se compila por completo antes de abrir o reemplazar
un Preview. `Run graph` reutiliza el mismo plan validado, por lo que una falla de estructura, tipos,
parámetros o resolución de assets no ejecuta ninguna tool ni descarta el Preview anterior.

### Contrato aplicado

- `Place`, `Snap` y el resto de los consumidores aceptan assets sólo por cable `Asset/Pick`, campo
  `asset` explícito o entrada principal `A` compatible.
- Un campo vacío ya no consulta `session.asset()` ni el primer resultado de la biblioteca. La Dash Bar
  conserva ese flujo cómodo, pero queda fuera del contrato del Graph.
- `Asset` exige nombre u `ObjectPath` existente y colocable; un nombre corto debe coincidir exactamente.
- `Pick` exige una `StaticMesh` seleccionada en el Content Browser al momento de compilar.
- Se validan antes de ejecutar: nodos y pines, endpoints, tipos `A/P/N/T/B/S`, cardinalidad, duplicados,
  autoconexiones, ciclos, variables duplicadas, expresiones y parámetros.
- Los errores vuelven por `node id`; el canvas pinta en rojo el nodo afectado. Los errores globales,
  como un ciclo, se muestran en todos los nodos.

### Interfaz

Se agregó `✓ Compile` junto a `Run graph` y `Compile / Validate` en el menú `Solution`. Esta acción
llama `jam.api.compile_graph_json()`, consulta lo necesario del Asset Registry/Content Browser y no
crea actores ni abre Preview. `Run graph` realiza de todos modos el mismo Preflight automáticamente;
el botón explícito sirve para diagnosticar antes de ejecutar.

### Implementación principal

- [`graph.compilar()`](../Content/Python/jam/graph.py) produce un `GraphPlan` con orden, parámetros,
  variables y assets ya resueltos; `graph.ejecutar_detalle()` consume ese plan.
- [`panel.ejecutar_grafo_json()`](../Content/Python/jam/panel.py) compila antes de `_preview`.
- [`api.compile_graph_json()`](../Content/Python/jam/api.py) expone el Preflight a cualquier interfaz.
- [`tools.REGISTRO`](../Content/Python/jam/tools.py) publica el contrato Graph (`source`, aridad, tipos,
  pin y requisito de asset) en la misma fuente de verdad que usa Slate.
- `SJamGraphEditor` y `FJamEditorModule` conectan la nueva acción de Compile con Python.

### Verificación realizada

- 20 tests puros correctos: 8 de Flow y 12 de Graph Preflight.
- Los tests de Graph cubren específicamente que un asset activo de sesión **no** rescata un `Place`
  vacío, además de `Asset/Pick`, assets inexistentes, tipos, parámetros, cardinalidad y ciclos.
- 43 archivos Python de Jam + tests: sintaxis correcta.
- Smoke real en `UnrealEditor-Cmd` contra el Asset Registry: `Place` vacío rechazado y
  `Asset → Place`/asset explícito resueltos con una `StaticMesh` real, sin ejecutar tools.
- `BotOOEditor Linux Development` compiló correctamente con Unreal 5.7.
- `git diff --check`: correcto.

### Alcance que sigue pendiente

El Graph ya expone `Bake` y `Discard`; la transacción revierte spawns parciales, recupera Preview desde
tags y aísla Graph/Dash. El `PCGGraph` también usa staging temporal y Bake sin overwrite. Todavía falta
transaccionar los demás efectos sobre Content (`fracture`, `normalize`) y cambios sobre actores
preexistentes. También sigue pendiente la semántica `AssetPath` frente a `ActorRef` de `Place → Snap`.

## Bug confirmado

Al ejecutar un grafo con `Place`, `Snap` u otro nodo consumidor, Jam coloca objetos aunque el campo
`asset` esté vacío y el pin no esté conectado a `Asset`, `Pick` ni a otro productor válido.

No es una compilación vieja. El ejecutor del Graph todavía hereda deliberadamente el comportamiento de
la Dash Bar:

```text
asset explícito/cableado vacío
→ asset activo de session
→ si tampoco existe, primer asset de library
→ ejecutar la tool
```

La UI actual presenta `asset` como un pin explícito, por lo que este fallback invisible contradice el
modelo visual del grafo.

## Causa técnica

- [`graph._resolver_asset()`](../Content/Python/jam/graph.py) usa `session.asset()` y luego el primer
  resultado de `library.buscar("", limit=1)` cuando no recibe nombre.
- `graph.ejecutar_detalle()` llama a ese resolver después de comprobar cables y campos, así que un
  consumidor desconectado siempre puede obtener un asset global.
- [`SJamGraphEditor::BuildJson()`](../Source/JamEditor/Private/SJamGraphEditor.cpp) serializa
  `"asset": null`; el fallback sucede después, en Python.
- `Run graph` entra directamente a ejecución. No existe una etapa pura de Compile/Preflight que
  valide todo el grafo antes de crear actores.
- `panel.ejecutar_grafo_json()` envuelve la ejecución en `_preview`, pero la ventana Graph no expone
  acciones propias para `Confirm/Bake` y `Discard`.

## Problema adicional: semántica Place → Snap

El cable principal del grafo de verbos transporta actualmente una ruta de asset, no el actor producido.
`Place` deja pasar esa ruta y `Snap` llama nuevamente a `place.colocar()`. Por tanto, incluso conectados,
`Place → Snap` puede crear otra instancia en lugar de ajustar la instancia creada por `Place`.

Hay que decidir y tipar explícitamente si una salida es:

- asset de contenido;
- actor/instancia del nivel;
- stream de puntos;
- spline;
- valor escalar o texto.

## Diseño recomendado

### 1. Compile/Preflight puro

Crear una etapa que no modifique Unreal y valide el grafo completo:

- ciclos;
- verbos desconocidos;
- aristas y nombres de pin válidos;
- compatibilidad de tipos;
- expresiones/variables resolubles;
- inputs obligatorios;
- asset requerido presente por campo o cable.

Si existe cualquier error, no debe ejecutarse ningún nodo. Cada error se devuelve por `node id` para
pintar el nodo rojo y mostrar el motivo en su tooltip/output.

### 2. Resolución estricta de assets en Graph

Para un consumidor, aceptar únicamente:

1. cable al pin `asset`;
2. valor escrito en el campo `asset`;
3. cable principal desde un productor compatible.

Un nodo `Asset` vacío debe fallar. `Pick` debe ser una fuente explícita que consulta la selección del
Content Browser. El fallback a `session.asset()`/biblioteca puede continuar en Dash Bar, pero no debe
ocurrir silenciosamente dentro del Graph.

### 3. Ciclo de ejecución visible

Separar las acciones del Graph:

```text
Compile/Validate → Run Preview → Confirm/Bake
                              ↘ Discard
```

- `Compile/Validate`: sólo diagnóstico.
- `Run Preview`: ejecuta únicamente un grafo válido y etiqueta los actores como `jam:preview`.
- `Confirm/Bake`: quita la etiqueta y fija el resultado.
- `Discard`: elimina el preview completo.

### 4. Semántica de actores

Definir si `Snap`, `Drop`, transformaciones y herramientas similares consumen un asset o un actor. Si
`Place → Snap` debe operar sobre la misma instancia, `Place` tiene que producir un actor y `Snap`
consumir/modificar ese actor, sin llamar de nuevo a `place.colocar()`.

## Criterios de aceptación

- Un `Place` aislado con `asset` vacío no crea actores y queda rojo con un error claro.
- Un `Place` con texto válido en `asset` puede ejecutar Preview.
- `Asset/Pick → Place` puede ejecutar Preview.
- Dos consumidores desconectados no heredan el asset activo ni el primero de la biblioteca.
- Un error en cualquier nodo impide efectos parciales en toda la escena.
- Repetir `Run Preview` descarta o reemplaza limpiamente el preview anterior.
- `Confirm/Bake` fija el resultado; `Discard` lo elimina.
- La Dash Bar conserva su comportamiento cómodo de asset activo.
- Se agregan pruebas Python para la validación estricta sin requerir Unreal cuando sea posible.
- Se documenta y prueba la semántica final de `Place → Snap`.

## Archivos que probablemente intervengan

- [`Content/Python/jam/graph.py`](../Content/Python/jam/graph.py)
- [`Content/Python/jam/panel.py`](../Content/Python/jam/panel.py)
- [`Content/Python/jam/api.py`](../Content/Python/jam/api.py)
- [`Content/Python/jam/tools.py`](../Content/Python/jam/tools.py)
- [`Source/JamEditor/Private/SJamGraphEditor.cpp`](../Source/JamEditor/Private/SJamGraphEditor.cpp)
- [`Source/JamEditor/Private/JamEditorModule.cpp`](../Source/JamEditor/Private/JamEditorModule.cpp)

## Estado de esta nota

Preflight, resolución estricta de assets y ciclo visible Run/Bake/Discard: implementados. Actores
nuevos y el asset `PCGGraph` ya tienen rollback/promoción; otros efectos sobre Content, mutaciones
existentes y semántica de actores continúan abiertos, por eso la tarea general permanece
`en-progreso`.

## Relacionado

- [[Auditoria proactiva de Jam - 2026-07-25]]
- [[Tarea - tipado y cardinalidad de conexiones Graph]]
- [[Tarea - contrato unificado de Graph Flow Presets y Web]]
- [[Tarea - Preview transaccional y efectos de PCG]]
