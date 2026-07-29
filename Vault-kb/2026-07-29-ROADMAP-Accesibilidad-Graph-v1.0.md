---
title: "Roadmap: accesibilidad y velocidad del Graph"
tipo: ROADMAP
version: "1.0"
date: 2026-07-29
updated: 2026-07-29
status: propuesta
area: JamEditor/Graph
tags:
  - jam
  - graph-editor
  - slate
  - accesibilidad
  - ux
  - velocidad
  - undo
  - clipboard
  - docking
  - funciones
aliases:
  - Accesibilidad del Graph
  - Atajos del Graph
  - Roadmap de velocidad del Graph
---

# Roadmap: accesibilidad y velocidad del Graph

## 0. Por qué esto es un roadmap y no una lista de caprichos

El cuello de botella de Jam ya no es el motor. Las tres tools son production-grade, el oráculo mide,
el compilador de materiales anda. Lo que frena es **el costo de tocar un grafo**: hoy no se pueden
mover dos nodos juntos, no se puede copiar una rama probada a otro diagrama, no hay Deshacer, y para
mostrarle un grafo a alguien hay que sacar una foto de pantalla que corta el diagrama al borde de la
ventana.

Cada una de esas cosas cuesta segundos, muchas veces por sesión. Es el impuesto que se paga en cada
iteración, y a diferencia de un bug no aparece en ningún test.

«Accesibilidad» acá quiere decir **las dos cosas**, y las dos importan:

1. **Accesibilidad de trabajo** — que la herramienta no me pelee. Atajos, selección, portapapeles,
   foco, deshacer.
2. **Accesibilidad real** — que se pueda usar sin memorizar una paleta de colores, sin mouse fino, y
   con un monitor cualquiera. Ya es una regla del proyecto: *«no pueden haber pines que se
   identifiquen sólo por el color, no es accesible para trabajar»*. Un color acompaña; el que
   identifica es el **nombre**.

La regla que ordena todo el documento: **cada ítem tiene un criterio de aceptación verificable**. Si
no se puede escribir el test, el ítem está mal planteado, no incompleto.

---

## 1. Estado actual (leído del código, 2026-07-29)

`SJamGraphEditor.cpp` — 2379 líneas; el modelo son `TArray<FGNode> Nodes` + `TArray<FGEdge> Edges`.

| Gesto | Hoy | Dónde vive |
|---|---|---|
| Pan del canvas | ✅ botón derecho / medio arrastrando | `OnMouseButtonDown` / `bPanning` |
| Zoom | ✅ rueda, clamp 0.35–2.5, anclado al cursor | `OnMouseWheel` / `ApplyZoom` |
| Crear nodo | ✅ doble clic (buscador) · clic en la ficha (va al centro) · arrastre (va donde soltás) | `SJamVerbTile` / `AddNodeAlCentro` |
| Mover un nodo | ✅ arrastrar el cuerpo | `SJamGraphNode::OnMouseMove` |
| Seleccionar | ⚠️ **uno solo**, y es el foco de teclado, no un estado | `SupportsKeyboardFocus` |
| Borrar | ✅ `Supr` sobre el nodo enfocado, o la `×` | `SJamGraphNode::OnKeyDown` |
| Borrar cable | ✅ `Alt` + clic | ver [[2026-07-25-INFORME-Graph-Eliminar-Conexiones-Alt-Click-v1.0\|Eliminar conexiones con Alt+click]] |
| Guardar / abrir | ✅ JSON en disco, ida y vuelta | `BuildJson()` / `SaveDiagram` / `OpenDiagram` |
| Flag de debug por nodo | ✅ el Display de Houdini | `SJamGraphNode::bDebugEnabled` |
| **Selección múltiple** | ❌ | — |
| **Copiar / cortar / pegar** | ❌ | — |
| **Duplicar** | ❌ | — |
| **Deshacer / rehacer** | ❌ | — |
| **Foco (`F`) / encuadre** | ❌ | — |
| **Captura del grafo entero** | ❌ | — |
| **Comentarios / grupos** | ❌ | — |
| **Funciones (subgrafo con firma)** | ❌ (hay Compounds, sin entradas/salidas declaradas) | `jam/preset.py` |
| **Docking del panel** | ❌ es una `SWindow` suelta | `JamEditorModule.cpp:126` |

Dos hallazgos que valen más que la tabla:

**`BuildJson()` ya existe y el grafo hace ida y vuelta a JSON.** Eso convierte tres features caras en
una barata: el portapapeles es un JSON, el Deshacer es una pila de JSON, y duplicar es pegar lo que
acabás de copiar. No hay que inventar un modelo de comandos.

**La selección hoy es el foco de teclado.** No es un estado del editor. Todo lo demás —mover en
grupo, borrar en grupo, alinear, copiar— está bloqueado detrás de convertirla en uno. Es la Fase 0 y
no se puede saltear.

---

## 2. Las dos preguntas abiertas de la sesión

### 2.1 El preview 2D de texturas: existe el motor, falta el visor

**Medido hoy.** El backend está hecho y probado:

- `jam/preview2d.py` (205 líneas, **puro**, sin `import unreal`): escritor de PNG por `zlib`,
  `campo()`, `islas_uv()`, `mascara_de_grafo()`, la rampa de color y `texto_de_ayuda()`.
- `jam.api.preview_2d(node_id, ancho, alto, canal)` arma el PNG y devuelve
  `{ok, ruta, tipo, ayuda}`.
- `tests/test_preview2d.py` corre dentro de los **435 tests** de la suite, en verde.

**Lo que falta es el consumidor.** Grep en `Source/`: **cero** referencias a `preview_2d`. O sea: Jam
sabe dibujar la máscara y el desplegado de UVs, escribe el PNG en disco, y **nadie lo muestra**. Hoy
el visor sólo es accesible llamando a la API a mano.

Falta un panel en el Graph que:
1. tome el nodo con el flag de debug prendido,
2. llame a `preview_2d`,
3. cargue el PNG en un `FSlateDynamicImageBrush` y lo dibuje,
4. y cuando no hay nada que dibujar, muestre `texto_de_ayuda()` — que es información — en vez de un
   cuadro vacío.

Es media jornada de Slate, no un sistema nuevo. Encaja con
[[2026-07-27-INFORME-Nodos-De-Debug-Ver-El-Stream-v1.0\|Nodos de debug: ver el stream]].

**Y el 3D no hace falta.** El viewport de Unreal ya es el visor 3D, y el Preview transaccional ya
cubre «verlo sin comprometerme». Un segundo visor 3D adentro del panel sería un viewport peor al
lado de uno bueno. Lo que sí falta del lado 3D es **acumulativo**, no un widget: que el Run dibuje la
cadena hasta el nodo marcado, como el Display flag de Houdini.

### 2.2 Docking del panel: se puede, y es la forma estándar

**Verificado en el código del motor (UE 5.7.4).** Hoy las tres ventanas de Jam —Dash, Graph,
Content— se crean con `SNew(SWindow)` + `FSlateApplication::Get().AddWindow(...)`
(`JamEditorModule.cpp:126, 205, 861`). Una `SWindow` suelta **no puede acoplarse**: el sistema de
docking de Unreal sólo conoce *tabs*.

La conversión es mecánica y es lo que hace todo el editor:

```cpp
FGlobalTabmanager::Get()
    ->RegisterNomadTabSpawner(JamTabs::Graph, FOnSpawnTab::CreateRaw(this, &FJamEditorModule::SpawnGraphTab))
    .SetDisplayName(LOCTEXT("JamGraphTab", "Jam — Graph"))
    .SetGroup(WorkspaceMenu::GetMenuStructure().GetToolsCategory())
    .SetIcon(FSlateIcon(...));
```

y para abrirlo, `FGlobalTabmanager::Get()->TryInvokeTab(JamTabs::Graph)`.

Confirmado en `Engine/Source/Editor/`: `ContentBrowserSingleton.cpp:115`, `ClassViewerModule.cpp:49`,
`ConfigEditorModule.cpp:36`, `CSVtoSVGModule.cpp:50` — todos usan exactamente ese patrón.

Lo que gana un **nomad tab**:

- se acopla a cualquier lado del editor, o al costado como *sidebar*;
- **la posición queda guardada en el layout del editor** y vuelve sola al reabrir — eso es el
  «siempre visible» que pedís;
- aparece en `Window ▸ Tools` como cualquier panel del motor;
- se puede seguir arrancando flotante si querés (es lo que significa *nomad*).

Costo: bajo. Hay que cambiar el ciclo de vida —de `SWindow` + `OnWindowClosed` a `SDockTab` +
`OnTabClosed`— y desregistrar los spawners en `ShutdownModule`. **Riesgo conocido:** el tab se
destruye y se recrea al acoplar, así que el estado del Graph (nodos, aristas, pan, zoom) no puede
vivir sólo en el widget o se pierde al mover el panel. Ya hay `BuildJson()`/`OpenDiagram`: el módulo
guarda el JSON al cerrar el tab y lo restaura al abrirlo.

**Recomendación: hacerlo temprano**, en la Fase 3, antes de invertir más en el canvas. Es más barato
migrar tres ventanas ahora que seis después.

---

## 3. Fases

### Fase 0 — La selección es un estado (`SelectedNodeIds`)

Habilita casi todo lo demás. Ya está especificada en detalle en
[[2026-07-26-PLAN-Seleccion-Multiple-Alineacion-Nodos-v1.0\|Selección múltiple y alineación]]; acá va
lo mínimo:

- `TSet<FString> SelectedNodeIds` en el editor; el nodo recibe `IsSelected` como atributo y pinta el
  halo lavanda de forma declarativa.
- **Marquee**: arrastrar el izquierdo sobre el fondo dibuja el rectángulo; al soltar entra lo que
  interseca. Clic en el fondo limpia.
- `Shift`+clic agrega, `Ctrl`+clic alterna.
- `Ctrl+A` selecciona todo; `Esc` limpia.
- Arrastrar un nodo seleccionado mueve **todo el grupo** con el mismo delta.
- `Supr` borra el grupo entero, con sus cables, en **una** operación.

> **Verificable:** el hit-test del marquee es geometría pura —rectángulos contra rectángulos en
> coordenadas de modelo— así que sale a Python como función pura y se testea sin editor: rectángulo
> que toca 3 de 5 nodos ⇒ los 3 esperados, con cualquier pan y cualquier zoom.

### Fase 1 — El portapapeles y el historial son JSON

Lo caro ya está hecho: el grafo serializa.

**Copiar / cortar / pegar** (`Ctrl+C` / `Ctrl+X` / `Ctrl+V`)

- Copiar = `BuildJson()` **del subconjunto seleccionado**, más las aristas cuyos dos extremos están
  adentro. Al portapapeles del sistema (`FPlatformApplicationMisc::ClipboardCopy`) — así se pega
  entre dos ventanas de Graph, y se puede pegar el JSON en un chat o en el vault.
- Pegar = deserializar, **reasignar ids**, desplazar un delta fijo (o pegar en el cursor) y dejar lo
  pegado seleccionado.
- Cortar = copiar + borrar la selección.

**Duplicar** (`Ctrl+D`, y `Alt`+arrastre como en Houdini) = copiar + pegar sin tocar el portapapeles.

**Deshacer / rehacer** (`Ctrl+Z` / `Ctrl+Shift+Z`)

Anillo de snapshots de `BuildJson()`, ~50 pasos. Un grafo típico es de kilobytes: el costo es
irrelevante y la implementación no puede desincronizarse del modelo, porque *es* el modelo.

Se toma snapshot **antes** de cada operación que muta: crear, borrar, mover (al soltar, no por
frame), conectar, desconectar, pegar, alinear, cambiar un parámetro (con *coalescing* mientras se
tipea en el mismo campo).

> **Verificable, y esta es la parte linda:** el JSON es la unidad. `estado → operación → deshacer`
> tiene que devolver **exactamente el mismo JSON**. Un test recorre todas las operaciones y compara
> strings. Y para pegar: el JSON pegado tiene que compilar con `graph.validar` — si copiar rompe un
> grafo válido, el oráculo lo dice antes que el usuario.

### Fase 2 — Navegación

| Atajo | Qué hace | De dónde sale |
|---|---|---|
| `F` | encuadra la selección (o todo, si no hay selección) | Blueprint, Houdini, Maya |
| `Home` / `A` | encuadra el grafo entero | Blueprint / Houdini |
| `Ctrl+F` | buscar nodo por verbo o por parámetro, y saltar a él | «Find in Blueprints» |
| `Ctrl+1..9` | guardar la vista actual | *quickmarks* de Houdini |
| `1..9` | volver a esa vista | idem |
| `Ctrl+0` | zoom 1:1 | — |

Las *quickmarks* de Houdini son la que más rinde y casi nadie copia: en un grafo grande, saltar entre
«la parte de scatter» y «la parte de material» con una tecla vale más que cualquier minimapa.

`F` y `Home` son aritmética sobre el AABB de los nodos: función pura, se testea sin Slate.

### Fase 3 — Docking (§2.2)

Las tres ventanas pasan a nomad tabs. Se hace **entera**, no sólo el Graph: dejar Dash flotante y
Graph acoplado sería peor que hoy.

### Fase 4 — El retrato del grafo (captura 1:1)

El pedido: una imagen del grafo **completo**, a calidad 1:1, sin que la corte el borde de la ventana
ni la degrade el zoom.

**Verificado que las APIs existen en 5.7.4** (todavía sin correr la cadena entera):

- `FWidgetRenderer::DrawWidget(Widget, FVector2D DrawSize)` →
  `Engine/Source/Runtime/UMG/Public/Slate/WidgetRenderer.h:51`. Dibuja un widget a un
  `UTextureRenderTarget2D` **del tamaño que le pidas**, sin depender de la ventana. Es el camino.
- `FSlateApplication::TakeScreenshot(Widget, OutColorData, OutSize)` →
  `SlateApplication.h:1038`. Más simple, pero captura **lo que está en pantalla**: no sirve para un
  grafo más grande que la ventana.

Receta:

1. AABB de todos los nodos en coordenadas de modelo, + margen.
2. Una copia del canvas en un `SVirtualWindow` de ese tamaño, con `Zoom = 1`.
3. `DrawWidget` a un render target de ese tamaño exacto.
4. Volcar a PNG.

**La vuelta de tuerca de Jam.** Como el grafo *es* JSON y Jam ya tiene un escritor de PNG puro
(`preview2d.png`), hay una **segunda** ruta: un renderer en Python que dibuja el diagrama desde el
JSON, sin Slate y sin editor. Más pobre visualmente, pero:

- corre **headless** ⇒ un grafo guardado se ilustra desde un script, para el vault o para un tutorial;
- es **determinista** ⇒ el mismo JSON da el mismo PNG byte a byte;
- y por eso mismo **es un oráculo**: dos grafos que deberían ser iguales se comparan por imagen, y el
  diff señala *dónde*.

Van las dos: `DrawWidget` para «mostrale esto a alguien», el renderer puro para «documentá y
verificá esto». La segunda es la que sólo Jam puede tener.

### Fase 5 — Funciones: el Compound con firma

Hoy un `preset kind=flow` guarda un grafo entero y lo aplica (`jam/preset.py`). Es el Cluster de
Grasshopper, el HDA de Houdini, el «Collapse to Function» de Blueprint. Lo que le falta es lo mismo
en los tres: **una firma**.

Las piezas:

1. **Dos verbos nuevos**: `input` y `output`. Adentro de un compound, marcan qué entra y qué sale, con
   nombre y tipo del vocabulario que ya existe (`A`, `P`, `F`, `M`, `N`, `MT`, …).
2. **Instanciación**: un compound guardado aparece en el ribbon como **un nodo**, con los pines que
   declararon sus `input`/`output`. Se cablea como cualquier verbo.
3. **Compilación por inline**: `graph.compilar` expande el subgrafo en el padre y renumera ids. Nada
   nuevo en tiempo de ejecución — el grafo expandido es un grafo normal, así que **el oráculo sigue
   midiendo lo mismo**.
4. **Guarda contra recursión**: un compound no se puede contener; el ciclo se detecta al compilar y es
   un error, no un cuelgue.
5. **«Collapse to function»**: seleccionás nodos (Fase 0), y Jam arma el compound solo — los cables
   que cruzan el borde de la selección se vuelven `input`/`output` automáticamente. Es exactamente lo
   que hace Blueprint, y es donde la Fase 0 se paga sola.

**Este es el ítem de mayor palanca del roadmap.** Es lo que convierte «hice un grafo que anda» en
«tengo una herramienta»: es el paso `Graph editable → Compound reusable` de
[[2026-07-25-ROADMAP-Vision-Producto-Jam-v1.0\|Visión y roadmap de producto]], que hoy está a medias.

> **Verificable:** un compound expandido tiene que dar **el mismo resultado** que el grafo plano
> equivalente. Se compara el plan compilado, no la imagen — mismo orden topológico, mismos
> parámetros resueltos. Y el ciclo tiene que dar error de compilación, con test.

### Fase 6 — Accesibilidad real

No es un extra: es la regla que ya rige el proyecto, extendida al resto del canvas.

- **Teclado puro.** `Tab` recorre los nodos en orden topológico; las flechas mueven el seleccionado;
  `Enter` entra a editar el primer parámetro. Hoy, sin mouse, el Graph no se usa.
- **El color nunca es el único canal.** Ya se cumple en los pines (cada uno dice su nombre, ver
  `DataName`). Falta cerrarlo en el **estado del oráculo**: verde/naranja/rojo tienen que venir con
  su símbolo — `✓` / `⚠` / `✗`, que `jam.graph` ya emite. Un test que recorra los estados y exija
  que ninguno se distinga sólo por color.
- **Contraste.** El cuerpo del nodo es `0.80,0.80,0.78` con texto oscuro: está bien. Auditar el resto
  contra WCAG AA (4.5:1) — sobre todo el gris de un campo **deshabilitado por cable**, que es
  justamente el que hay que poder leer para saber qué valor está llegando.
- **Tamaño.** El zoom llega a 2.5×; el ribbon y el panel no escalan con él. Respetar el
  *Application Scale* del editor.
- **Tooltips como texto.** Ya está: el ribbon no muestra nombre bajo el icono, y el tooltip trae
  nombre + firma + doc (cubierto por `test_paleta.py`).

> **Verificable:** el contraste es aritmética sobre los colores del C++ — el mismo truco que ya usa
> `test_paleta.py`, que **lee `DataColor` del `.cpp`** para no copiar la paleta a mano. El test de
> contraste se escribe igual y no se puede desincronizar.

### Fase 7 — Comodidades del canvas

Ordenadas por lo que rinden, no por lo que cuestan:

1. **Comentarios / grupos** (`C` sobre la selección) — la caja de comentario de Blueprint, el
   *network box* de Houdini, el *scribble* de Grasshopper. En un grafo de 30 nodos es la diferencia
   entre leerlo y descifrarlo. Mover la caja mueve lo que contiene.
2. **Bypass / disable por nodo** (`D`) — apagar un nodo sin borrarlo; el stream lo atraviesa. Es el
   *bypass flag* de Houdini y vale oro para aislar un problema. Encaja con el flag de debug que ya
   existe.
3. **Alinear y distribuir** — `Q`/`W`/`E`/`R` como en Blueprint. Detalle en
   [[2026-07-26-PLAN-Seleccion-Multiple-Alineacion-Nodos-v1.0\|Selección múltiple y alineación]].
4. **Reroute** — doble clic sobre un cable inserta un punto de paso. Grafo largo = cables que cruzan
   todo.
5. **Auto-layout** — ordenar el grafo por capas topológicas. `graph.topo_order()` ya existe: el layout
   es *puro*, se calcula en Python y el C++ sólo aplica posiciones.
6. **Snap a la grilla** — la grilla ya se dibuja (paso 24); falta que los nodos la usen.

---

## 4. Tabla de atajos propuesta

Elegidos para no pelearse con lo que Brian ya tiene en el dedo de Blueprint y de Houdini.

| Tecla | Acción | Fase |
|---|---|---|
| `Ctrl+A` | seleccionar todo | 0 |
| `Esc` | limpiar selección | 0 |
| `Supr` | borrar selección | 0 |
| `Ctrl+C` / `X` / `V` | copiar / cortar / pegar | 1 |
| `Ctrl+D` · `Alt`+arrastre | duplicar | 1 |
| `Ctrl+Z` / `Ctrl+Shift+Z` | deshacer / rehacer | 1 |
| `F` | encuadrar selección | 2 |
| `Home` | encuadrar todo | 2 |
| `Ctrl+F` | buscar nodo | 2 |
| `Ctrl+1..9` / `1..9` | guardar / recuperar vista | 2 |
| `Ctrl+0` | zoom 1:1 | 2 |
| `Ctrl+Shift+P` | captura del grafo entero | 4 |
| `Ctrl+G` | colapsar selección a función | 5 |
| `Tab` | siguiente nodo (orden topológico) | 6 |
| `C` | comentario sobre la selección | 7 |
| `D` | bypass del nodo | 7 |
| `Q`/`W`/`E`/`R` | alinear | 7 |

**Conflicto conocido:** `Supr` y `Ctrl+A` mientras un campo de texto tiene el foco pertenecen al
campo. La regla: los atajos del canvas sólo corren si el foco **no** está en un widget de edición —
lo mismo que ya se resolvió para el `Supr` del nodo.

---

## 5. Orden recomendado

```text
Fase 0  selección          ← desbloquea 1, 5, 7. Empezar acá, sí o sí.
Fase 1  JSON: copiar/deshacer  ← barata porque BuildJson() ya existe
Fase 3  docking            ← antes de crecer más el canvas
Fase 2  navegación         ← F y Home primero; quickmarks después
        visor 2D (§2.1)    ← media jornada, y ya está todo el motor hecho
Fase 5  funciones          ← la de mayor palanca; necesita 0
Fase 7  comentarios, bypass, alinear
Fase 4  captura 1:1        ← la ruta pura vale doble (documentar + verificar)
Fase 6  accesibilidad real ← los tests de contraste y símbolo, apenas haya estados nuevos
```

Fases 0 y 1 juntas son **un día**, y son las que más se notan por hora invertida.

---

## 6. Lo que NO vamos a hacer, y por qué

- **Un viewport 3D adentro del panel.** El de Unreal ya está y es mejor. Ver §2.1.
- **Minimapa.** Con `F`, `Home` y quickmarks no hace falta, y come canvas permanentemente.
- **Data trees estilo Grasshopper.** Es una brecha real y conocida
  ([[2026-07-25-CONCEPTO-Estetica-Nodos-Grasshopper-v1.0\|Estética de nodos]]), pero es un cambio del
  *modelo de datos*, no de accesibilidad. Va en su propio documento.
- **Un motor de undo por comandos.** El anillo de JSON da lo mismo con una fracción del código y sin
  poder desincronizarse del modelo.

---

## 7. Relacionado

- [[2026-07-26-PLAN-Seleccion-Multiple-Alineacion-Nodos-v1.0|Selección múltiple y alineación]] — el detalle de la Fase 0
- [[2026-07-25-ROADMAP-Vision-Producto-Jam-v1.0|Visión y roadmap de producto]] — dónde encaja
- [[2026-07-25-CONCEPTO-Estetica-Nodos-Grasshopper-v1.0|Estética de nodos Grasshopper]] — el lenguaje visual
- [[2026-07-27-INFORME-Nodos-De-Debug-Ver-El-Stream-v1.0|Nodos de debug: ver el stream]] — el visor 2D es su continuación
- [[2026-07-25-PLAN-Persistencia-Segura-Diagramas-Graph-v1.0|Persistencia segura de diagramas]] — de acá sale el portapapeles
- [[2026-07-25-INFORME-Graph-Eliminar-Conexiones-Alt-Click-v1.0|Eliminar conexiones con Alt+click]]
- [[2026-07-29-GUIA-Convencion-Documentacion-Vault-v1.0|Convención de documentación del vault]]
