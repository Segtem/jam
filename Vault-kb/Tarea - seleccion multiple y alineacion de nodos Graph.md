---
title: "Tarea: selección múltiple y alineación de nodos Graph"
date: 2026-07-26
status: pendiente
priority: media
area: JamEditor/Graph
tags:
  - jam
  - graph-editor
  - slate
  - selection
  - alignment
  - ux
aliases:
  - Marquee selection del Graph
  - Alinear nodos del Graph
  - Mover y eliminar múltiples nodos
---

# Tarea: selección múltiple y alineación de nodos Graph

## Estado actual

Jam permite seleccionar un nodo haciendo clic en su cuerpo, moverlo y eliminarlo con la `×` o con
`Supr/Delete`. Todavía no existe una selección persistente de varios nodos ni un rectángulo de
selección sobre el canvas.

## Funcionalidad pendiente

### Selección por cuadro de arrastre

- Arrastrar con el botón izquierdo sobre una zona vacía dibuja un rectángulo de selección visible.
- Al soltar, quedan seleccionados los nodos alcanzados por el rectángulo.
- Clic en el fondo sin arrastrar limpia la selección.
- `Shift` permite agregar nodos a la selección; `Ctrl` permite alternarlos individualmente.
- El halo lavanda debe permanecer visible en todos los nodos seleccionados.
- La selección no debe interferir con pan, conexión de pines, búsqueda por doble clic ni edición de
  parámetros.

Conviene definir una regla predecible para el marquee. Como primera versión, seleccionar cualquier
nodo cuyo rectángulo interseque el cuadro es la interacción más directa. Más adelante puede adoptarse
la convención de CAD: izquierda→derecha exige contención completa y derecha→izquierda acepta cruce.

### Operaciones sobre múltiples nodos

- Arrastrar cualquiera de los nodos seleccionados mueve el grupo completo conservando distancias.
- `Supr/Delete` elimina todos los nodos seleccionados y todas sus conexiones.
- Un clic sobre un nodo no seleccionado reemplaza la selección por ese nodo antes de moverlo.
- `Shift/Ctrl + clic` agrega o quita un nodo sin iniciar movimientos inesperados.
- La operación debe ser atómica para que un futuro Undo/Redo pueda restaurar el grupo completo.

### Herramientas de Align y Distribute

Agregar acciones al menú `Edit` o a una barra contextual:

- Align Left / Right.
- Align Top / Bottom.
- Align Horizontal Center / Vertical Center.
- Distribute Horizontally / Vertically con separación uniforme.
- Opcional posterior: Snap to Grid y separación numérica configurable.

Las acciones deben usar las posiciones del modelo, no coordenadas de pantalla, para funcionar igual
con cualquier pan, zoom o DPI. Para Align conviene mantener fijo un nodo de referencia —por ejemplo,
el último seleccionado— y mover los demás.

## Modelo técnico sugerido

- Reemplazar la selección implícita basada sólo en foco por un `TSet<FString> SelectedNodeIds` en
  `SJamGraphEditor`.
- Pasar a cada `SJamGraphNode` un atributo `IsSelected` para pintar el halo de forma declarativa.
- Guardar inicio/fin del marquee en coordenadas locales del canvas y convertir sus límites a modelo
  con `LocalToModel()` antes del hit-test.
- Centralizar `DeleteSelection()`, `MoveSelection()` y `AlignSelection()` en el editor para limpiar
  cables y refrescar pines una sola vez por operación.

## Criterios de aceptación

- El cuadro de arrastre selecciona visualmente dos o más nodos.
- Mover uno desplaza exactamente el mismo delta a todo el grupo.
- `Supr` elimina el grupo y ningún cable queda huérfano.
- Los campos de texto conservan el uso normal de `Supr` mientras tienen foco.
- Align y Distribute producen posiciones deterministas sin depender del zoom.
- Pan, doble clic, cables, `Alt+clic` y selección individual continúan funcionando.
- Guardar y cargar no necesita persistir la selección; abrir un grafo comienza sin nodos seleccionados.

## Relacionado

- [[Estetica de nodos Grasshopper para Jam]]
- [[Graph - eliminar conexiones con Alt-click]]
- [[Tarea - persistencia segura de diagramas Graph]]
- [[Vision y roadmap de producto para Jam]]

