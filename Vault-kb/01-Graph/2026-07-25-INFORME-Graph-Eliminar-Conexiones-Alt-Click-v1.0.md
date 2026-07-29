---
title: "Graph: eliminar conexiones con Alt-click"
tipo: INFORME
version: "1.0"
date: 2026-07-25
updated: 2026-07-25
status: implementado
area: 01-Graph
tags:
  - jam
  - unreal-engine
  - slate
  - graph-editor
  - interaction
aliases:
  - Desconectar cables de nodos
  - Borrar wires del graph
---

# Graph: eliminar conexiones con Alt-click

## Interacción

`Alt + clic izquierdo` sobre un pin elimina sus conexiones, siguiendo la convención habitual de los
editores nodales:

- En un pin de entrada elimina todo cable que llegue a ese pin concreto.
- En un pin de salida elimina todos los cables que parten de esa salida.
- Si había un cable fantasma en curso, también se cancela.
- Un pin de parámetro vuelve a habilitar su control local al quedar sin cable.

Todos los grips anuncian esta acción en su tooltip: `Alt+clic: eliminar conexiones del pin`.

## Implementación

`SJamGraphEditor::OnPinClicked()` consulta
`FSlateApplication::Get().GetModifierKeys().IsAltDown()` antes de ejecutar la conexión normal. Elimina
las aristas que coinciden por nodo y nombre de pin, vacía `PendingSource`, llama a
`RefreshCabledPins()` e invalida la pintura de `WireLayer`.

No fue necesario ampliar los delegates de `SJamGraphNode`: la consulta del modificador sucede durante
el callback sincrónico del botón del grip, mientras `Alt` todavía está presionado.

## Verificación

- `git diff --check`: correcto.
- Compilación `BotOOEditor Linux Development` con UE 5.7.4: correcta.
- UnrealBuildTool compiló `Module.JamEditor.cpp` y enlazó `libUnrealEditor-JamEditor.so`.
- La prueba interactiva debe realizarse tras reiniciar Unreal para cargar el módulo nuevo.

## Prueba manual

1. Conectar una salida a un parámetro y confirmar que el campo se deshabilita.
2. Mantener `Alt` y hacer clic sobre ese pin de entrada.
3. Confirmar que desaparece el cable y que el campo vuelve a habilitarse.
4. Conectar una salida a dos o más nodos.
5. Hacer `Alt+clic` sobre la salida y confirmar que desaparecen todos sus cables.
6. Iniciar un cable fantasma y hacer `Alt+clic` sobre cualquier pin; debe cancelarse.
