---
title: "Estética de nodos Grasshopper para Jam"
tipo: CONCEPTO
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
  - grasshopper
  - ui
aliases:
  - Lenguaje visual de nodos Jam
  - Componentes Grasshopper en Jam
---

# Estética de nodos Grasshopper para Jam

## Referencias analizadas

- [Controles y componentes especiales](../Reference/input_reference.png)
- [Componentes de importación](../Reference/input_reference_2.png)
- [Componente seleccionado](../Reference/node_example.png)
- [Componentes compactos](../Reference/node_example_2.png)

## Qué define el lenguaje visual

Las referencias no usan una tarjeta de aplicación con una barra de título convencional. Cada elemento
se lee como un **componente físico pequeño sobre el canvas**:

1. El nombre vive en una cartela flotante clara, con un pequeño pico apuntando al componente.
2. El cuerpo tiene esquinas suaves, contorno oscuro, luz superior y sombra inferior corta.
3. Los grips son círculos pequeños colocados a caballo sobre los bordes izquierdo y derecho.
4. Las entradas se nombran junto al borde izquierdo; la salida se identifica junto al derecho.
5. El centro queda reservado para un pictograma que permite reconocer el componente antes de leerlo.
6. No hay pines de ejecución: la estructura visual expresa dataflow.
7. Los colores fuertes comunican estado. En Grasshopper el naranja es warning, el rojo es error y el
   lavanda exterior indica selección; no son meramente colores de categoría.

Los ejemplos grandes de calendario, rueda de color, imagen y sliders son **controles especializados**.
Su silueta forma parte del mismo lenguaje, pero su comportamiento no se puede obtener sólo cambiando la
piel del nodo genérico.

## Adaptación implementada en Jam

| Elemento de referencia | Implementación Jam |
|---|---|
| Cartela superior | Nombre del verbo, con `_` convertido a espacio y primera letra en mayúscula |
| Cuerpo normal | Gris frío con una influencia muy sutil del color de categoría |
| Warning | Cuerpo naranja fuerte, alimentado por el resultado del oráculo |
| Error | Cuerpo rojo coral, alimentado por el resultado del oráculo |
| OK | Cuerpo neutro con contorno verde |
| Selección | Halo lavanda durante hover o arrastre |
| Centro del componente | Icono Lucide gris oscuro; nombre vertical como fallback si falta el SVG |
| Grips | Centro claro y aro del mismo color semántico que el cable compatible |
| Relieve | Sombra inferior, highlight superior y degradado vertical suave |
| Inputs editables | Campos, spinboxes y cajas booleanas blancos y compactos; dropdown simple |
| Cerrar nodo | `×` independiente en la esquina superior derecha, fuera de las filas de parámetros |
| Borrar con teclado | Clic en el cuerpo selecciona el nodo; `Supr/Delete` ejecuta el mismo borrado que la `×` |
| Dataflow | Se conservan pines por parámetro, salida tipada y cables detrás del componente |

Esta separación permite que el estado siga siendo semántico y que la categoría permanezca reconocible
sin convertir todo el cuerpo en una paleta multicolor.

El booleano conserva el glyph y la interacción nativos de `SCheckBox`, pero ya no hereda el fondo negro
del tema del editor de Unreal. Su caja normal es blanca con borde gris; en hover y al pulsarla, el borde
toma el color de categoría del nodo, igual que el foco de los campos de número y texto.

La selección del nodo usa el foco de Slate. Un clic en el cuerpo mantiene visible el halo lavanda y la
tecla `Supr/Delete` invoca el mismo callback que la `×`, por lo que elimina también los cables asociados
y actualiza los pines que quedaron libres. Un clic en el fondo mueve el foco al canvas y deselecciona el
nodo. Si el foco está dentro de un campo de texto, `Supr` conserva su función de edición y no elimina el
componente.

## Iconografía Lucide

Se descargó un set curado de 45 SVG desde el repositorio oficial de Lucide, fijado al commit
`d29db5e98e194c05469dd6dba855aef4c48b8048`. Vive en
[`Resources/Icons/Lucide`](../Resources/Icons/Lucide/README.md), incluye la licencia original y un
`icon-map.json` que cubre todos los verbos actuales de `jam.tools` y `jam.flow` reutilizando pictogramas
cuando el concepto es equivalente.

Para hacerlo compatible con el flujo visual de Slate, se normalizó únicamente
`stroke="currentColor"` a blanco explícito. Cada `FSlateVectorImageBrush` aplica luego una tinta gris
casi negra sin modificar la geometría del icono. La tinta neutra mejora el contraste sobre el cuerpo
claro y evita que el pictograma compita con los colores semánticos de pines, cables y estados.

`SJamGraphEditor::IconPathForVerb()` carga el mapping una vez, resuelve la ruta absoluta dentro del
plugin y verifica que el archivo exista. Los nodos pintan el SVG a 24 px en su zona central y los
ribbons reutilizan el mismo asset sobre el badge de categoría. Si falla el JSON, el mapping o el SVG,
la UI mantiene el nombre vertical y el código corto anteriores como fallback.

Hay una diferencia importante entre las dos rutas de pintura: `SImage` aplica el `TintColor` del brush
automáticamente, pero `FSlateDrawElement::MakeBox` no. Como el nodo dibuja su icono manualmente en
`OnPaint`, debe pasar explícitamente
`IconBrush->GetTint(InWidgetStyle) * InWidgetStyle.GetColorAndOpacityTint()`; de lo contrario el SVG
queda blanco aunque el brush haya sido construido con tinta gris oscura.

Para cambiar un icono manualmente basta con agregar el SVG blanco a `Resources/Icons/Lucide`, editar
la pareja `"verbo": "archivo-sin-extension"` en `icon-map.json`, validar el JSON y reiniciar Unreal.
No hace falta recompilar cuando sólo cambian esos recursos. El procedimiento completo está en el
[README del set](../Resources/Icons/Lucide/README.md).

## Tipado visual de grips y cables

`SJamGraphEditor::DataColor()` es la única fuente de verdad para ambos elementos. El aro exterior del
grip indica qué dato entrega o espera; el centro permanece claro para conservar contraste.

| Código | Dato | Color |
|---|---|---|
| `P` | Stream de puntos | Azul |
| `N` | Número (`int` o `float`) | Ámbar |
| `T` | Texto y opciones | Violeta |
| `B` | Booleano | Rojo |
| `A` | Asset o actor | Verde |
| `S` | Spline | Dorado |
| `M` | Malla procedural transitoria (`DynamicMesh`) | Cyan |

El spec declara `in_name` para el pin principal: los verbos de herramientas tradicionales reciben `A`,
las operaciones no-fuente de flow reciben `P` y los operadores de malla reciben `M`. Los parámetros se
derivan de su tipo del spec; el pin especial `asset` siempre es `A`. El compilador usa los mismos tipos
para bloquear conexiones incompatibles antes de ejecutar el Graph.

## Archivos modificados

- [SJamGraphNode.cpp](../Source/JamEditor/Private/SJamGraphNode.cpp): pintura del componente, cartela,
  icono central con fallback, cierre superpuesto, grips, estados, relieve y estilos de los controles.
- [SJamGraphNode.h](../Source/JamEditor/Public/SJamGraphNode.h): métricas compartidas del layout y
  brushes persistentes de Slate.
- [SJamGraphEditor.cpp](../Source/JamEditor/Private/SJamGraphEditor.cpp): asignación de tipo/color para
  stream, salida y cada parámetro, carga del mapping Lucide y badges SVG.
- [JamEditorModule.cpp](../Source/JamEditor/Private/JamEditorModule.cpp): lectura de `in_name` desde el
  spec combinado.
- [tools.py](../Content/Python/jam/tools.py) y [flow.py](../Content/Python/jam/flow.py): metadata del tipo
  esperado por el pin principal.

Las métricas `TitleH`, `PadTop`, `HeaderH`, `RowH` y `PadBottom` son compartidas con el cálculo de los
anclajes. Cambiar una altura sólo en la pintura volvería a desalinear los cables; cualquier ajuste debe
mantener `PinLocalY()` y `NodeHeight()` como fuente única de verdad.

## Alcance

Se cambió la presentación genérica de todos los verbos. No se modificaron:

- serialización del grafo;
- ejecución topológica;
- valores ni tipos del spec;
- conexiones y colores de cables;
- comportamiento de los controles existentes.

No se implementaron todavía nodos funcionales específicos como `Colour Wheel`, `Calendar`,
`Image Sampler`, `MD Slider` o previews de archivos. Si Jam incorpora esos tipos, conviene crear
presentadores Slate por clase de dato y mantener este componente como marco común.

La selección actual sigue siendo individual y basada en foco. El marquee, el movimiento/eliminación
de grupos y Align/Distribute se registraron en [[2026-07-29-INFORME-Seleccion-Multiple-Alineacion-Nodos-v2.0|Selección múltiple y alineación]].

## Verificación

- `git diff --check`: correcto.
- Compilación `BotOOEditor Linux Development` con UE 5.7.4: correcta.
- UnrealBuildTool compiló `Module.JamEditor.cpp` y enlazó `libUnrealEditor-JamEditor.so`.
- Specs verificados: fuentes sin entrada, herramientas con entrada `A` y operaciones de flow con `P`.
- Mapping Lucide verificado contra los 50 verbos actuales: sin claves faltantes ni sobrantes.
- Los 45 SVG pasan validación XML y cada valor del mapping apunta a un archivo existente.

## Prueba visual recomendada

1. Reiniciar Unreal para cargar el `.so` nuevo.
2. Abrir **Tools → Jam: Graph (Grasshopper)**.
3. Usar **Display → Insertar todos los nodos** para revisar la familia completa.
4. Confirmar cartelas, nombres verticales, botón de cierre y grips en componentes bajos y altos.
5. Pasar el cursor y arrastrar un nodo para comprobar el halo lavanda.
6. Ejecutar un grafo que produzca `ok`, `warn` y `error` y verificar que los colores mantengan su
   significado.
7. Crear cables hacia el pin de stream y hacia parámetros; deben coincidir con el centro de cada grip.
8. Confirmar que el color del cable coincide con el aro del pin compatible en ambos extremos.
9. Hacer clic en el cuerpo de un nodo, comprobar que el halo queda visible y pulsar `Supr`; el nodo y
   sus cables deben desaparecer. Repetir dentro de un campo de texto: sólo debe editarse el texto.
