---
title: "Fix Graph: cable fantasma alineado al cursor"
date: 2026-07-25
status: implementado
area: JamEditor/Graph
tags:
  - jam
  - unreal-engine
  - slate
  - graph-editor
  - bugfix
aliases:
  - Bug del cursor y la flecha
---

# Fix Graph: cable fantasma alineado al cursor

## Resultado

Al crear una conexión en **Jam — Graph (Grasshopper)**, el extremo libre del cable fantasma ahora usa
la posición real del cursor dentro del lienzo. Antes aparecía desplazado hacia abajo aproximadamente la
altura conjunta del menú y del ribbon.

Captura original: [Bug del cursor y la flecha.png](../Reference/Bug%20del%20cursor%20y%20la%20flecha.png)

## Causa raíz

La interfaz tiene dos espacios locales distintos:

- `SJamGraphEditor` contiene toda la ventana: menú, ribbon, canvas y barra inferior.
- `SJamWireLayer` ocupa solamente el área interna del canvas y allí dibuja las splines.

`SJamGraphEditor::OnMouseMove` calculaba `LastMousePos` con
`MyGeometry.AbsoluteToLocal(...)`. En ese callback, `MyGeometry` corresponde al editor completo, pero
`SJamWireLayer::OnPaint` interpreta el punto como local a la capa del canvas. Por eso la coordenada Y
tenía incorporada la altura de la cabecera y el cable terminaba debajo del cursor.

## Cambio realizado

Archivo: [SJamGraphEditor.cpp](../Source/JamEditor/Private/SJamGraphEditor.cpp)

La posición de pantalla ahora se transforma usando la geometría cacheada del widget que realmente pinta
el cable:

```cpp
LastMousePos = WireLayer->GetCachedGeometry().AbsoluteToLocal(
    MouseEvent.GetScreenSpacePosition());
```

También se corrigió la descripción de `LastMousePos` en
[SJamGraphEditor.h](../Source/JamEditor/Public/SJamGraphEditor.h) para dejar explícito que sus coordenadas
son locales a `SJamWireLayer`.

Este enfoque evita restar a mano una altura fija y sigue funcionando si cambia el ribbon, el layout de la
ventana o la escala DPI de Slate.

## Verificación

- `git diff --check`: correcto, sin errores de whitespace.
- La API usada existe en Slate: `SWidget::GetCachedGeometry() const` y
  `FGeometry::AbsoluteToLocal(FVector2D)`.
- Compilación de `BotOOEditor` con UE 5.7.4: correcta. Se compilaron `Module.JamEditor.cpp` y
  `libUnrealEditor-JamEditor.so`.
- El engine correcto está en `/home/workstation/Dev/engines/UnrealEngine_5.7`. La ruta
  `/home/workstation/UnrealEngine` corresponde a UE 4.27.2 y no sirve para compilar este host.
- La primera prueba visual posterior al cambio usó un binario anterior: el fuente tenía una fecha más
  reciente que `Binaries/Linux/libUnrealEditor-JamEditor.so`. Después de detectar esto se recompiló el
  plugin con UE 5.7.4. Es necesario reiniciar Unreal para que el proceso cargue el `.so` nuevo.
- La suite Python no cubre esta interfaz Slate y tampoco pudo usarse como regresión general: `pytest`
  no está instalado; el fallback con `unittest` encuentra además imports históricos desde `src.*` que
  no existen en la estructura actual `oraculo/`.

## Prueba manual recomendada en UE 5.7.4

1. Abrir **Tools → Jam: Graph (Grasshopper)**.
2. Crear dos nodos separados.
3. Hacer clic en el pin de salida del primero.
4. Mover el cursor por la parte alta, central y baja del canvas, y confirmar que el extremo del cable
   queda debajo del cursor sin desplazamiento vertical.
5. Repetir con zoom distinto de `1.0` y, si es posible, con otra escala DPI.
6. Hacer clic en un pin de entrada y confirmar que la conexión fija conserva sus anclajes.

## Alcance para el siguiente agente

La corrección funcional está limitada a la conversión de coordenadas del cable temporal. El worktree ya
contenía otros cambios sin commit en `SJamGraphEditor`, `SJamGraphNode` y módulos Python; se preservaron y
no forman parte de este fix.
