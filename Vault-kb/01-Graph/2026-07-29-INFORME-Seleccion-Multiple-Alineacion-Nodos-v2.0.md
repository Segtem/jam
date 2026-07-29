---
title: "Selección múltiple y alineación de nodos Graph"
tipo: INFORME
version: "2.0"
date: 2026-07-26
updated: 2026-07-29
status: implementado
priority: media
area: 01-Graph
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

# Selección múltiple y alineación de nodos Graph

> **v2.0 — implementado el 2026-07-29.** Este documento nació como plan (v1.0, 2026-07-26). Lo de
> abajo es lo que se construyó; el plan original queda como la sección «Lo que se especificó».

## Lo que quedó hecho

**La selección es un estado.** `TSet<FString> SelectedNodeIds` en `SJamGraphEditor`. El nodo la lee
por atributo (`IsSelected`) y pinta el mismo halo lavanda que ya usaba para hover y foco, así que no
hubo que inventar un segundo lenguaje visual.

| Gesto | Qué hace |
|---|---|
| arrastrar sobre el fondo | cuadro de selección; entra lo que el cuadro TOCA |
| `Shift`/`Ctrl` + arrastrar | el cuadro SUMA a lo que ya estaba elegido |
| clic en un nodo | lo elige |
| `Shift` + clic | lo agrega |
| `Ctrl` + clic | lo alterna |
| clic en el fondo | limpia |
| `Ctrl+A` / `Esc` | todo / nada |
| arrastrar un nodo elegido | mueve **el grupo entero**, conservando distancias |
| `Supr` | borra el grupo con sus cables, en una operación |
| la `×` del nodo | borra **ese** nodo, siempre — es lo que dice el botón |

**Alinear y distribuir** (menú `Edit`): izquierda, derecha, arriba, abajo, centrar en columna,
centrar en fila, distribuir en horizontal y en vertical. Requieren 2+ nodos elegidos; con menos, la
entrada del menú aparece deshabilitada en vez de no hacer nada en silencio.

## Las tres decisiones que importan

**Se alinea al borde del cuadro que envuelve la selección, no «al último que seleccionaste».** Es lo
que hace Grasshopper y tiene una ventaja concreta: el resultado depende sólo de lo que se ve, así que
alinear dos veces seguidas da lo mismo —es idempotente— y no hay que acordarse en qué orden se hizo
clic. Hay un test que lo fija.

**Se alinean BORDES, no coordenadas.** «Alinear abajo» iguala `y + alto`, no `y`. En Jam los nodos
tienen alturas distintas —un verbo con 6 params es mucho más alto que uno sin params— así que la
diferencia se ve. Lo mismo «distribuir»: iguala los HUECOS, no los centros; con tamaños distintos,
centros parejos dan huecos visiblemente disparejos aunque los números cierren.

**Clic sin modificadores sobre un nodo que YA estaba elegido no rompe el grupo.** Sin esa excepción,
agarrar un grupo por cualquiera de sus nodos lo desarmaba en el mismo gesto con el que se lo quería
mover.

## Dónde vive cada cosa, y por qué

Las cuentas de alinear y distribuir están en **`jam/layout.py`, puro** (cero `import unreal`): son
las mismas con cualquier pan, cualquier zoom y cualquier DPI, y así se verifican sin abrir el editor.
El C++ manda rectángulos en coordenadas de modelo y aplica las posiciones que vuelven.

El hit-test del **marquee, en cambio, quedó en C++**: mandar la selección al cerebro en cada mouse-up
metería un viaje a Python en el medio de un gesto. El precio es que la regla queda escrita dos veces,
y se paga como ya se paga la paleta de colores: `test_layout.py` **lee el `.cpp`** y exige que la
condición siga siendo cruce con desigualdad estricta, que compare los cuatro bordes y que use la
altura propia de cada nodo. Tres mutaciones del C++ lo confirman.

## Verificación

- **24 tests nuevos** en `tests/test_layout.py` (suite total: 459, en verde).
- **7 mutaciones, las 7 en rojo**: alinear a la derecha por `x` en vez del borde; el marquee contando
  el roce; alinear en un eje tocando el otro; distribuir igualando centros; y las tres del `.cpp`.
- `tools/experiments/verifica_acomodar.py` corre **dentro del editor** y comprueba el camino real —
  que `jam.api.acomodar` exista, que el JSON con comillas sobreviva el viaje por `ToPyStr`, y que la
  respuesta traiga las claves que el C++ parsea. `VEREDICTO: TODO VERDE`.

## Lo que queda

- **El gizmo flotante de Grasshopper** (`Reference/align.png`): el cuadro punteado con manijas de
  alinear sobre cada lado de la selección. Hoy las mismas acciones están en el menú `Edit`; falta la
  versión al alcance del mouse.
- **Atajos de teclado** `Q`/`W`/`E`/`R` para alinear, como Blueprint.
- **Snap a la grilla** y separación numérica configurable.
- **Atomicidad para Undo**: mover/borrar/alinear en grupo ya son una sola operación del modelo, que
  es lo que la Fase 1 necesita para tomar un snapshot por acción.

---

## Lo que se especificó (v1.0, 2026-07-26)

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

- [[2026-07-25-CONCEPTO-Estetica-Nodos-Grasshopper-v1.0|Estética de nodos Grasshopper]]
- [[2026-07-25-INFORME-Graph-Eliminar-Conexiones-Alt-Click-v1.0|Eliminar conexiones con Alt+click]]
- [[2026-07-25-PLAN-Persistencia-Segura-Diagramas-Graph-v1.0|Persistencia segura de diagramas]]
- [[2026-07-25-ROADMAP-Vision-Producto-Jam-v1.0|Visión y roadmap de producto]]

