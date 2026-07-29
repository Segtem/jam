---
title: "Docking: los tres paneles de Jam son nomad tabs"
tipo: INFORME
version: "1.0"
date: 2026-07-29
updated: 2026-07-29
status: implementado
area: JamEditor
tags:
  - jam
  - slate
  - docking
  - nomad-tab
  - ue5-7
  - ux
aliases:
  - Acoplar los paneles de Jam
  - Nomad tabs de Jam
  - Jam siempre visible
---

# Docking: los tres paneles de Jam son nomad tabs

Dash Bar, Graph y Content dejaron de ser ventanas flotantes sueltas. Ahora se acoplan a cualquier
lado del editor, se pueden mandar al costado como *sidebar*, aparecen en **`Window ▸ Tools`** junto
al resto de los paneles del motor, y —lo que importaba— **su posición queda guardada en el layout**
y vuelven solos al reabrir el editor. Eso es el «siempre visible».

## Por qué no se podía antes

Las tres se creaban con `SNew(SWindow)` + `FSlateApplication::Get().AddWindow(...)`. Una `SWindow` es
una ventana del sistema operativo: **el docking de Unreal no la conoce**. El sistema de acople sólo
maneja *tabs*, así que no había nada que arreglar en la ventana — había que dejar de usar ventanas.

## Qué es un nomad tab

Un tab que **no pertenece a un editor de asset**. El Content Browser, el Class Viewer, el Output Log
son todos nomad tabs, y por eso se pueden poner donde uno quiera. El patrón es el mismo en todos:

```cpp
FGlobalTabmanager::Get()->RegisterNomadTabSpawner(JamTabs::Graph,
    FOnSpawnTab::CreateRaw(this, &FJamEditorModule::SpawnGraphTab))
    .SetDisplayName(LOCTEXT("GraphTabTitle", "Jam — Graph"))
    .SetGroup(WorkspaceMenu::GetMenuStructure().GetToolsCategory());
```

y para abrirlo, `FGlobalTabmanager::Get()->TryInvokeTab(JamTabs::Graph)`. Verificado contra el
código del motor 5.7.4: `ContentBrowserSingleton.cpp:115`, `ClassViewerModule.cpp:49`,
`ConfigEditorModule.cpp:36`, `CSVtoSVGModule.cpp:50`.

Las entradas de `Tools ▸ Jam` siguen estando: ahora invocan el tab en vez de crear una ventana.

## Detalles que no son obvios

**Los ids de tab son una clave persistente.** El editor guarda la posición de cada panel usando el
`FName` con el que se registró. Cambiarlo más adelante no es un rename inocuo: le borra al usuario el
acomodo que tenía y los paneles vuelven a aparecer flotando.

**Los punteros a los tabs son débiles.** El dueño es el tab manager. Guardarlos fuertes haría que
cerrar un panel no liberara nada y que «¿está abierto?» contestara que sí para siempre.

**El timer de la Dash Bar se mudó al contenido.** El punto de mira se refresca a 20 Hz con un
`RegisterActiveTimer` que estaba sobre la `SWindow`. **Un tab acoplado no tiene ventana propia**, así
que el timer ahora vive en el widget de contenido, que es lo que existe en los dos casos.

**Hay que desregistrar los spawners en `ShutdownModule`.** Si no, recargar el plugin en caliente deja
spawners apuntando a un módulo que ya no está.

## De regalo: cerrar el Graph ya no tira el trabajo

`SJamGraphEditor` ganó `EstadoDelCanvas()` / `RestaurarCanvas()`. El módulo guarda ese estado cuando
se cierra el tab y lo repone cuando se vuelve a abrir. Viaja:

- el **grafo** (el mismo JSON de un `.jamgraph`, guardado como objeto y no como string escapado, así
  el estado entero se sigue pudiendo leer y diffear);
- la **vista** (pan y zoom) — volver a un grafo que quedó en otro zoom y en otro lado se siente como
  que no volvió;
- el **archivo actual**, porque `LoadGraphJson` pasa por `NewGraph` y ése limpia `CurrentPath`: sin
  reponerlo, el próximo «Guardar» pediría nombre en vez de sobrescribir el `.jamgraph` en el que
  venías.

El historial **no** viaja: reabrir el panel arranca de cero con el grafo puesto. Deshacer hasta
antes de haber cerrado el panel sería más confuso que útil.

Esto era una mejora aparte —antes cerrar la ventana perdía el diagrama sin preguntar— y además
cubre el caso de que acoplar un tab recreara el widget: no depende de que Slate conserve el
contenido al moverlo.

## Verificación

El editor arranca, el módulo carga y **los tres spawners se registran sin una sola queja** en el log
(se buscaron errores y warnings de `TabSpawner` / `RegisterNomadTab` / los tres ids: ninguno). Los 8
tutoriales siguen cargando y compilando: `VEREDICTO: TODO VERDE`.

**Lo que no se puede verificar headless es el acople en sí**: arrastrar el panel, soltarlo en un
borde, mandarlo al sidebar, cerrar el editor y ver si vuelve donde estaba. Eso hay que hacerlo a
mano, y es lo primero que conviene probar.

## Relacionado

- [[2026-07-29-ROADMAP-Accesibilidad-Graph-v1.0|Roadmap de accesibilidad del Graph]] — era la Fase 3
- [[2026-07-29-INFORME-Historial-Deshacer-Rehacer-v1.0|Historial: deshacer y rehacer]]
- [[2026-07-25-PLAN-Persistencia-Segura-Diagramas-Graph-v1.0|Persistencia segura de diagramas]]
