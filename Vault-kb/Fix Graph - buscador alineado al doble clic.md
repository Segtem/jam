---
title: "Fix Graph: buscador alineado al doble clic"
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
  - Bug del doble clic y menú de nodos
---

# Fix Graph: buscador alineado al doble clic

## Resultado

El buscador de nodos ahora aparece en el punto exacto del doble clic dentro del canvas. Antes se abría
unos 50 px por debajo, aproximadamente la altura conjunta del menú y del ribbon.

## Causa raíz

`SJamGraphEditor::OnMouseButtonDoubleClick` convertía la posición de pantalla con
`MyGeometry.AbsoluteToLocal(...)`. Esa geometría pertenece al editor completo, mientras `SearchPopup`
es hijo del `SOverlay` que ocupa sólo el canvas. La coordenada local conservaba por tanto el offset de
la cabecera y luego se reutilizaba como si ya perteneciera al lienzo.

Es la misma causa estructural documentada en
[[Fix Graph - cable fantasma alineado al cursor]]: mezclar coordenadas locales de dos widgets con
orígenes distintos.

## Cambio

El doble clic se transforma ahora contra `WireLayer->GetCachedGeometry()`. La capa de wires y el popup
son hermanos que llenan el mismo overlay, así que comparten origen, tamaño y escala de layout:

```cpp
const FVector2D AtCanvas = WireLayer.IsValid()
    ? WireLayer->GetCachedGeometry().AbsoluteToLocal(MouseEvent.GetScreenSpacePosition())
    : MyGeometry.AbsoluteToLocal(MouseEvent.GetScreenSpacePosition());
OpenSearch(AtCanvas);
```

No se resta una constante: la corrección sigue siendo válida si cambia la altura del ribbon, el DPI o
el layout de la ventana. `SearchAt` queda además en el espacio correcto para `LocalToModel()` cuando el
usuario elige el nodo que quiere insertar.

## Verificación

- `git diff --check`: correcto.
- Compilación `BotOOEditor Linux Development` con UE 5.7.4: correcta.
- UnrealBuildTool recompiló `Module.JamEditor.cpp` y enlazó `libUnrealEditor-JamEditor.so`.
- La comprobación visual interactiva queda para Unreal; requiere reiniciar el proceso para cargar el
  módulo recién enlazado.

## Prueba manual

1. Reiniciar Unreal después de compilar el módulo.
2. Abrir **Tools → Jam: Graph (Grasshopper)**.
3. Hacer doble clic cerca de la parte superior, media e inferior del canvas.
4. Confirmar que la esquina superior izquierda del buscador nace en el punto pulsado.
5. Elegir un resultado y comprobar que el nodo se crea en esa misma posición visual.
6. Repetir con zoom distinto de `1.0` y con el ribbon mostrando categorías diferentes.
