---
title: "Comentarios y grupos en el Graph"
tipo: INFORME
version: "1.0"
date: 2026-08-04
updated: 2026-08-04
status: implementado
area: 01-Graph
tags:
  - jam
  - graph-editor
  - slate
  - comentarios
  - grupos
  - ux
  - accesibilidad
aliases:
  - Cajas de comentario del Graph
  - Fase 7.1
  - Comment box
---

# Comentarios y grupos en el Graph

`C` sobre una selección encierra esos nodos en una caja con título editable y color propio.
Arrastrar el cuerpo mueve la caja **y lo que contiene**; la esquina inferior derecha la
redimensiona. Es la Fase 7.1 del [[2026-07-29-ROADMAP-Accesibilidad-Graph-v1.0|roadmap de
accesibilidad]].

Sobrevive deshacer/rehacer, copiar/cortar/pegar/duplicar, guardar/abrir y colapsar a función.

## La decisión que ordena todo: la caja no es dueña de nada

`FGComment` **no tiene lista de nodos miembro**. Qué contiene se recalcula por contención espacial
cada vez que empieza un arrastre, y nunca se persiste:

```cpp
void SJamGraphEditor::BeginCommentDrag(const FString& Id)
{
    CommentDragNodeIds.Reset();
    if (const FGComment* C = FindComment(Id))
    {
        CommentDragNodeIds = NodeIdsTouchingRect(C->Pos, C->Pos + C->Size);
    }
}
```

De ahí salen tres propiedades gratis, que con una lista de membresía habría que sostener a mano:

- **Borrar la caja no borra lo que encierra.** Es organizativa, no estructural.
- **Meter un nodo adentro es arrastrarlo adentro.** No hay «agregar al grupo».
- **Nada se puede desincronizar**, porque no hay un segundo lugar donde esté escrito qué contiene.

## La contención existe una sola vez

El marquee ya tenía esta misma fórmula (cruce con desigualdad **estricta**, la regla de
`jam.layout.en_marco`). Copiarla para el arrastre de la caja habría dejado dos copias divergibles —
y peor: el test que ata la regla al `.cpp` (`ReglaDelMarqueeEnElCppTests`) hace una búsqueda **no
anclada**, así que sólo habría mirado la primera y la segunda podría pudrirse en silencio.

Se extrajo `NodeIdsTouchingRect()` y el marquee pasó a **llamarla** en vez de tener la condición
inline. El test nuevo `ReglaDeContencionCompartidaEnElCppTests` exige que la condición aparezca
**exactamente una vez** en el archivo y que el helper se invoque al menos tres veces (definición +
marquee + `BeginCommentDrag`).

## El bug que costó cuatro intentos: el relleno no sale del brush

Durante varias iteraciones la caja pintaba **el borde del color elegido y el fondo blanco**. No era
el compositor ni Wayland: es cómo funciona `MakeBox`.

| | de dónde sale |
|---|---|
| **Borde** | del brush: `Element.SetOutline(InBrush->OutlineSettings.Color...)` |
| **Relleno** | del **parámetro** `InTint` de `MakeBox`, que por defecto es `FLinearColor::White` |

`FSlateBoxPayload::SetBrush()` copia margen, UV, tiling y recurso — y **nunca lee
`InBrush->TintColor`**. Entonces `MakeBox(..., &BodyBrush)` sin tint pintaba blanco opaco y
descartaba color y alfa juntos.

```cpp
// mal: el relleno queda blanco, el borde sí toma el color
FSlateDrawElement::MakeBox(OutDrawElements, Layer, PG, &BodyBrush);

// bien
FSlateDrawElement::MakeBox(OutDrawElements, Layer, PG, &BodyBrush,
    ESlateDrawEffect::None, BodyBrush.TintColor.GetSpecifiedColor());
```

Lo que hizo el diagnóstico lento fue que el síntoma («no se ve el color») se parece a un problema de
opacidad, y subir el alfa era un **no-op**: el alfa viajaba en el mismo tint descartado. Tres
ajustes seguidos no cambiaron un pixel, lo que parecía confirmar la hipótesis equivocada.

> [!warning] Mismo bug latente en `SJamGraphNode`
> Sus cuatro `MakeBox` (`SJamGraphNode.cpp:533, 541, 548, 580`) omiten el tint igual. Hoy no se nota
> porque sus colores son casi blancos, pero significa que **la sombra (`ShadowBrush`, negro al 0.26)
> y el relleno lavanda del halo de selección nunca se dibujaron**. Arreglarlo cambia el aspecto de
> todos los nodos, así que quedó pendiente de decisión.

## El orden de capas del canvas, y por qué

Llegar al orden correcto tomó tres pasadas, cada una rompiendo lo anterior:

```text
SJamGridLayer      fondo gris + grilla        (HitTestInvisible)
CommentCanvas      cajas de comentario
SJamWireLayer      cables + cable-fantasma    (HitTestInvisible)
Canvas             nodos
SJamMarqueeLayer   cuadro de selección        (HitTestInvisible)
SearchPopup        buscador
```

Dos hechos que hay que tener juntos para que cierre:

1. **`SJamWireLayer` pintaba también el fondo y la grilla.** Poner la caja «más atrás de todo» la
   dejó tapada por ese fondo opaco. Por eso el fondo se separó a `SJamGridLayer`: la caja necesita
   quedar **encima de la grilla** (para teñirla) y **debajo de los cables** (para no atenuarlos).
2. **Una capa que llena el canvas se roba los clics.** Al subir los cables por encima de las cajas,
   la caja dejó de recibir clics: el hit-test de Slate elige el hermano de más arriba y **no sigue
   bajando**. `SetVisibility(EVisibility::HitTestInvisible)` en grilla y cables lo resuelve — el
   precedente ya estaba en `SJamMarqueeLayer`.

## Un solo ciclo de mouse para arrastrar y redimensionar

El handle de resize **no es un widget**: es una región de 14×14 en la esquina, hit-testeada a mano
en el propio `OnMouseButtonDown`. Anidar un segundo widget con su propia captura dentro de un
`SCompoundWidget` que ya captura la suya es la clase de cosa que funciona hasta que el mouse sale de
la ventana a mitad de gesto.

`OnMouseButtonDown` decide `bResizing` vs `bDragging` por geometría, y de ahí los dos comparten
captura, `OnMouseMove` y `OnMouseButtonUp`.

Se respeta la regla de historial que ya regía el arrastre de nodos: **mutar en vivo en `OnMouseMove`,
un solo `Marcar()` en `OnMouseButtonUp`**, y sólo si algo se movió de verdad. Marcarlo por frame
llenaría el historial con las posiciones intermedias de un gesto único.

## Colapsar a función necesitó un parche explícito

`Ctrl+G` es el único camino que sale a Python: `jam/funcion.py` reconstruye el grafo padre **desde
cero** (`padre = JamGraph()`), copiando sólo `nodes` y `edges`. Python no sabe de comentarios, así
que sin intervención **cada `Ctrl+G` los borraba en silencio**.

La solución no toca Python: se saca una foto de `Comments` antes de `LoadGraphJson` y se reinyecta
después, todo bajo el mismo `TGuardValue` para que siga siendo **un** paso de undo.

No hace falta filtrar cajas que encerraban nodos ahora colapsados: la caja es organizativa, sigue
existiendo, y ahora contiene (o no) la instancia de función nueva.

## Serialización

`"comments"` es un campo **opcional** de nivel superior, con la misma forma que `"nodes"`:

```json
"comments": { "c1": { "title": "…", "x": 0, "y": 0, "w": 240, "h": 160,
                      "color": [0.39, 0.44, 0.82] } }
```

Un `.jamgraph` viejo sin la clave, o una caja mal formada, **no rompen la carga** — se ignoran, el
mismo trato que el `"debug"` ausente de un nodo. `JamGraph.from_json` ya ignora claves de nivel
superior desconocidas (probado con `schema_version`), así que Python no necesitó cambios.

Al pegar, a diferencia de una arista, **no hay referencia cruzada que remapear**: la contención se
recalcula sola en el primer arrastre.

## Cerrar el panel pregunta antes

`SDockTab::SetCanCloseTab` es el único hook que puede **vetar** el cierre; `SetOnTabClosed` llega
tarde (el tab se va igual). El estado sucio sale de comparar el `BuildJson()` vivo contra
`GuardadoEn`, una foto del último Guardar/Abrir.

A propósito **ni `LoadGraphJson` ni `NewGraph` tocan `GuardadoEn`**: por ahí pasan deshacer/rehacer
y `Ctrl+G`, y marcar «guardado» ahí afirmaría que el disco tiene algo que nunca se escribió. Como
efecto secundario feliz, **deshacer hasta el estado guardado vuelve a leer limpio**.

Diálogo de tres vías. Si elige guardar y cancela el diálogo de archivo (o la escritura falla), **el
cierre se aborta**: cerrar igual sería tirar justo lo que pidió conservar. Por eso `SaveDiagram`
ahora devuelve `bool`.

> [!note] Alcance
> Cubre cerrar el **tab Graph**. Cerrar Unreal entero no consulta `CanCloseTab`. Además el canvas ya
> sobrevivía al cierre del tab vía `EstadoDelCanvas`, así que decir «No» descarta hacia disco, no
> hacia la sesión.

## Fuera de alcance en v1 (decisión, no olvido)

- El marquee **no** selecciona cajas; sólo el clic directo.
- `Ctrl+A` y alinear/distribuir siguen operando sólo sobre nodos.
- No hay «traer al frente» entre cajas superpuestas.

## Archivos

| Archivo | Qué |
|---|---|
| `Source/JamEditor/Public/SJamGraphComment.h` · `Private/SJamGraphComment.cpp` | el widget (nuevo) |
| `Source/JamEditor/Public/SJamGraphEditor.h` · `Private/SJamGraphEditor.cpp` | `FGComment`, capas, serialización, `Ctrl+G`, cierre |
| `Source/JamEditor/Private/JamEditorModule.cpp` | `SetCanCloseTab` |
| `Source/JamEditor/JamEditor.Build.cs` | `AppFramework` (para `OpenColorPicker`) |
| `Content/Python/tests/test_layout.py` | `ReglaDeContencionCompartidaEnElCppTests` |

## Verificado

- Compila limpio contra UE 5.8.1 (`-NoUBA`, por el symlink `Plugins/Jam`).
- 601 tests de Python en verde, incluidos los dos nuevos.
- **Gestos probados a mano por Brian**: crear con `C`, arrastrar, redimensionar, color por picker,
  render detrás de los nodos con los cables visibles, y el diálogo de guardado al cerrar el panel.
  El resto de Slate no tiene camino headless — es el mismo límite ya documentado para
  Nanite/Simplify/Weld.
