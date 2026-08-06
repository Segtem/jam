---
title: "Roadmap: accesibilidad y velocidad del Graph"
tipo: ROADMAP
version: "1.0"
date: 2026-07-29
updated: 2026-07-29
status: propuesta
area: 01-Graph
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
| Seleccionar | ✅ **Fase 0 hecha** — marquee, `Shift`/`Ctrl`+clic, `Ctrl+A`, `Esc` | `SelectedNodeIds` |
| Mover / borrar en grupo | ✅ **Fase 0 hecha** | `MoveSelection` / `DeleteSelection` |
| Alinear y distribuir | ✅ **hecho** — 8 acciones en el menú Edit | `jam/layout.py` (puro) |
| Borrar | ✅ `Supr` sobre la selección, o la `×` por nodo | `SJamGraphNode::OnKeyDown` |
| Borrar cable | ✅ `Alt` + clic | ver [[2026-07-25-INFORME-Graph-Eliminar-Conexiones-Alt-Click-v1.0\|Eliminar conexiones con Alt+click]] |
| Guardar / abrir | ✅ JSON en disco, ida y vuelta | `BuildJson()` / `SaveDiagram` / `OpenDiagram` |
| Flag de debug por nodo | ✅ el Display de Houdini | `SJamGraphNode::bDebugEnabled` |
| Deshacer / rehacer | ✅ **Fase 1** — `Ctrl+Z` / `Ctrl+Shift+Z`, 50 pasos | `Marcar` / `Deshacer` |
| Copiar / cortar / pegar | ✅ **Fase 1** — al portapapeles del SISTEMA, es el mismo JSON | `Copiar` / `PegarJson` |
| Duplicar | ✅ `Ctrl+D`, sin tocar el portapapeles | `Duplicar` |
| Foco (`F`) / encuadre (`Inicio`) | ✅ **Fase 2, parte** | `Encuadrar` |
| **Captura del grafo entero** | ❌ | — |
| **Comentarios / grupos** | ✅ **Fase 7.1** — `C` sobre la selección, arrastre, resize, color por caja | `SJamGraphComment` |
| **Funciones (subgrafo con firma)** | ✅ **Fase 5 completa** — `input`/`output`, `fn:<nombre>`, expansión inline, ribbon y `Ctrl+G` | `jam/funcion.py` + Slate |
| Docking del panel | ✅ **Fase 3** — los tres paneles son nomad tabs | `RegisterTabs` |

Dos hallazgos que valen más que la tabla:

**`BuildJson()` ya existe y el grafo hace ida y vuelta a JSON.** Eso convierte tres features caras en
una barata: el portapapeles es un JSON, el Deshacer es una pila de JSON, y duplicar es pegar lo que
acabás de copiar. No hay que inventar un modelo de comandos.

**La selección era el foco de teclado.** No era un estado del editor, y todo lo demás —mover en
grupo, borrar en grupo, alinear, copiar— estaba bloqueado detrás de convertirla en uno. Era la Fase 0
y no se podía saltear: **se hizo el 2026-07-29**, ver
[[2026-07-29-INFORME-Seleccion-Multiple-Alineacion-Nodos-v2.0\|Selección múltiple y alineación]].

---

## 2. Las dos preguntas abiertas de la sesión

### 2.1 El preview 2D de texturas: existe el motor, falta el visor

**Medido hoy.** El backend está hecho y probado:

- `jam/preview2d.py` (205 líneas, **puro**, sin `import unreal`): escritor de PNG por `zlib`,
  `campo()`, `islas_uv()`, `mascara_de_grafo()`, la rampa de color y `texto_de_ayuda()`.
- `jam.api.preview_2d(node_id, ancho, alto, canal)` arma el PNG y devuelve
  `{ok, ruta, tipo, ayuda}`.
- `tests/test_preview2d.py` corre dentro de los **435 tests** de la suite, en verde.

**HECHO el 2026-08-05.** Faltaba el consumidor —grep en `Source/` daba **cero** referencias a
`preview_2d`: Jam sabía dibujar y **nadie lo mostraba**—. Ahora el visor vive al lado del Inspector
de datos y **comparte su selector de nodo**: un solo control de «qué nodo», dos vistas, la numérica
y la visual. Se refresca desde `RefreshInspector()`, así que corre después de cada Run sin
disparadores propios.

> [!warning] La trampa que decidió el diseño
> Slate cachea las texturas dinámicas **por nombre de archivo**
> (`FSlateRHIResourceManager::GetDynamicTextureResourceByName`), y `api.preview_2d` escribe siempre
> la MISMA ruta por nodo —a propósito, para poder abrir el PNG por fuera—. Sin soltar el recurso
> antes de recrear el brush, **el segundo Run del mismo nodo mostraría la imagen del primero para
> siempre**: el visor parecería andar en la demo y mentiría en el uso real. Lo resuelve
> `SoltarPreview2D()` con `FSlateRenderer::ReleaseDynamicResource`.

**Miniatura en el nodo, estilo Substance Designer (2026-08-05).** Además del panel, cada nodo
dibujable muestra en el canvas lo que produjo: la miniatura **reemplaza al icono del verbo** en la
zona libre del centro, sin tocar la geometría del nodo. Aparece después de **Run**, no de Compile —
Compile valida, no produce datos, y las miniaturas salen de `graph.ultima_corrida()`.

Dos decisiones de costo:

- `api.preview_2d_todos()` las devuelve **todas en un viaje**. Una llamada por nodo desde Slate
  serían N `ExecPythonCapture` por Run; con 30 nodos, 30 procesos de ida y vuelta.
- Van a **64 px**. Para una máscara de material cada píxel es una evaluación del IR en CPU: a 320
  serían 102.400 por nodo, a 64 son 4.096.

**Doble clic en la miniatura abre el visor a 768 px** en una ventana emergente **no modal**, para
dejarla al lado mientras se sigue tocando el grafo. Doble clic y no clic simple: el centro del nodo
es zona de agarre y un clic simple le robaría el arrastre.

Los tres dibujos del mismo nodo conviven en la misma carpeta con sufijos distintos —`{id}.png` el
panel, `{id}_thumb.png` la miniatura, `{id}_full.png` el popup— porque Slate cachea la textura por
nombre de archivo: con el mismo nombre, uno mostraría al otro. Hay un test que exige que las tres
rutas sean distintas.

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
`OnTabClosed`— y desregistrar los spawners en `ShutdownModule`.

**HECHO el 2026-07-29**; el detalle está en
[[2026-07-29-INFORME-Docking-Paneles-Nomad-Tabs-v1.0\|Docking: los paneles son nomad tabs]]. De
regalo, cerrar el panel de Graph ya no tira el diagrama: el módulo guarda el estado (grafo + vista +
archivo actual) al cerrar el tab y lo repone al abrirlo.

---

## 3. Fases

### Fase 0 — La selección es un estado (`SelectedNodeIds`) — ✅ HECHA 2026-07-29

Todo lo de esta fase está implementado; el detalle está en
[[2026-07-29-INFORME-Seleccion-Multiple-Alineacion-Nodos-v2.0\|Selección múltiple y alineación]].
Junto con ella salió **alinear y distribuir** (que era Fase 7) porque es su primer pago concreto.

Una corrección al plan original, que decía que el hit-test del marquee saldría a Python como función
pura: **queda en C++**. Mandar la selección al cerebro en cada mouse-up mete un viaje a Python en el
medio de un gesto, y es aritmética de rectángulos. Pero entonces la regla queda escrita dos veces, así
que se ata como ya se ata la paleta de colores: `test_layout.py` **lee el `.cpp`** y exige que la
condición siga siendo cruce con desigualdad estricta. Las cuentas que sí valen un viaje —alinear y
distribuir, que son una acción y no un gesto— viven en `jam/layout.py`, puro y testeado.

### Fase 1 — El portapapeles y el historial son JSON

Lo caro ya está hecho: el grafo serializa.

**Copiar / cortar / pegar** (`Ctrl+C` / `Ctrl+X` / `Ctrl+V`) — ✅ HECHO 2026-07-29

- Copiar = `BuildJson()` **del subconjunto seleccionado**, más las aristas con LAS DOS puntas adentro
  (un cable a medias no es un grafo). Al portapapeles del sistema, así se pega entre dos ventanas de
  Graph y el fragmento se puede pegar en un chat o en el vault: es el mismo JSON de un `.jamgraph`.
- Pegar = deserializar, **ids nuevos**, corrimiento fijo de 26 u, y lo pegado queda elegido. Cada
  cable pegado pasa por `CanConnect`, **la misma compuerta que conectar a mano**: un cable pegado no
  puede entrar por una puerta que un cable dibujado no podría cruzar.
- Cortar = copiar + borrar la selección. Un solo paso del historial.
- Lo ilegible se saltea en silencio: el portapapeles del sistema puede tener cualquier cosa, y eso no
  es un error del usuario.

**Duplicar** (`Ctrl+D`) — ✅ HECHO. Sin tocar el portapapeles: duplicar no puede pisar lo copiado.
Falta `Alt`+arrastre, como en Houdini.

**Deshacer / rehacer** (`Ctrl+Z` / `Ctrl+Shift+Z`) — ✅ HECHO 2026-07-29

Dos pilas de snapshots de `BuildJson()`, tope 50. Detalle y las decisiones en
[[2026-07-29-INFORME-Historial-Deshacer-Rehacer-v1.0\|Historial: deshacer y rehacer]].

Dos correcciones al plan original:

- **No se fotografía «antes» de la mutación, sino después, apilando la foto anterior.** Sale igual
  para lo estructural y arregla lo otro: `BuildJson` lee los valores VIVOS de los widgets, así que
  una foto tomada «antes» de borrar un nodo ya se llevaba puesto lo que acababas de tipear.
- **Faltaban dos avisos que el editor no recibía.** Los valores de los params viven en los widgets y
  nadie notificaba al editor cuando cambiaban; el arrastre tampoco avisaba cuándo terminaba. Sin
  esos dos, editar un parámetro no era un paso y mover un nodo eran cientos.

### Fase 2 — Navegación

| Atajo | Qué hace | De dónde sale |
|---|---|---|
| `F` ✅ | encuadra la selección (o todo, si no hay selección) | Blueprint, Houdini, Maya |
| `Inicio` ✅ | encuadra el grafo entero | Blueprint / Houdini |
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

### Fase 5 — Funciones: el Compound con firma — ✅ COMPLETA 2026-07-30

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
- ✅ **El color nunca es el único canal.** Se cumple en los pines (cada uno dice su nombre, ver
  `DataName`) y, desde el **2026-08-05**, en el **estado del oráculo**: cada veredicto trae su
  símbolo en el canvas — `✓` ok · `⚠` aviso · `✗` REVISAR · `!` reventó — con el nombre del estado
  en palabras en el tooltip. Lo ata `VeredictoDelOraculoTests`, que lee `StateGlyph` del `.cpp` y
  exige que los cuatro estados tengan símbolo y que no haya dos iguales.
  Hasta entonces el veredicto vivía **sólo** en el color del cuerpo y en un tooltip que había que
  hoverear — y peor: por el bug del tint de `MakeBox` ese color del cuerpo ni siquiera se dibujaba,
  así que el veredicto se comunicaba por un borde de 1.4 px.
- ✅ **Contraste.** Auditado contra WCAG AA (4.5:1) el **2026-08-05**. El campo deshabilitado por
  cable —el que se sospechaba— pasa (5.04). Los que fallaban eran otros, y peores: **los dos estados
  que avisan de un problema eran los MENOS legibles del nodo**, REVISAR con 4.44 y ERROR con 2.62.
  Un rojo saturado no llega a AA con NINGUNA tinta (2.62 con la oscura, 2.66 con blanca), así que
  hubo que aclararlo; el significado no se pierde porque lo llevan además el borde y el símbolo `!`.
  Lo ata `ContrasteDelNodoTests`, que LEE los rellenos del `.cpp` y exige 4.5:1 contra `JamInk`.
- **Tamaño.** El zoom llega a 2.5×; el ribbon y el panel no escalan con él. Respetar el
  *Application Scale* del editor.
- **Tooltips como texto.** Ya está: el ribbon no muestra nombre bajo el icono, y el tooltip trae
  nombre + firma + doc (cubierto por `test_paleta.py`).

> **Verificable:** el contraste es aritmética sobre los colores del C++ — el mismo truco que ya usa
> `test_paleta.py`, que **lee `DataColor` del `.cpp`** para no copiar la paleta a mano. El test de
> contraste se escribe igual y no se puede desincronizar.

### Fase 7 — Comodidades del canvas

Ordenadas por lo que rinden, no por lo que cuestan:

1. ✅ **Comentarios / grupos** (`C` sobre la selección) — la caja de comentario de Blueprint, el
   *network box* de Houdini, el *scribble* de Grasshopper. En un grafo de 30 nodos es la diferencia
   entre leerlo y descifrarlo. Mover la caja mueve lo que contiene.
   **Hecho el 2026-08-04** — ver `2026-08-04-INFORME-Comentarios-Y-Grupos-Graph-v1.0`.
2. ✅ **Bypass / disable por nodo** (`D`) — apagar un nodo sin borrarlo; el stream lo atraviesa. Es el
   *bypass flag* de Houdini y vale oro para aislar un problema. Encaja con el flag de debug que ya
   existe.
   **Hecho el 2026-08-05**, con una restricción que no estaba en este plan: sólo se puede apagar un
   verbo que **recibe y produce el mismo tipo** (93 de los 140 del catálogo). Apagar un `M → A`
   sacaría una M por un pin que promete A y rompería todo lo cableado abajo; antes que re-propagar
   tipos en Compile —y tener que explicar por qué apagar un nodo rompió otro tres cables más
   allá— se prohíbe el caso. La regla vive en `jam.graph.puede_bypass` y en `JamPuedeBypass` del
   `.cpp`, atadas por un test que lee el `.cpp` y las compara verbo por verbo sobre el catálogo real.
3. **Alinear y distribuir** — `Q`/`W`/`E`/`R` como en Blueprint. Detalle en
   [[2026-07-29-INFORME-Seleccion-Multiple-Alineacion-Nodos-v2.0\|Selección múltiple y alineación]].
4. **Reroute** — doble clic sobre un cable inserta un punto de paso. Grafo largo = cables que cruzan
   todo.
5. ✅ **Auto-layout** (`L`) — ordenar el grafo por capas topológicas. `graph.topo_order()` ya existe: el
   layout es *puro*, se calcula en Python y el C++ sólo aplica posiciones.
   **Hecho el 2026-08-05** como `jam.layout.auto`. Reusa entero el puente que ya tenían alinear y
   distribuir (`OnLayout` → `api.acomodar` → aplicar posiciones); lo único nuevo es que `auto`
   necesita las ARISTAS además de los rectángulos, así que su payload es
   `{"nodos": [...], "edges": [...]}` en vez de la lista pelada. La capa sale del camino MÁS LARGO
   desde una fuente —con el más corto un nodo puede quedar a la izquierda de algo que lo alimenta,
   que es justo el cable para atrás que se quiere eliminar— y el orden dentro de la capa por
   baricentro, dos pasadas. Sin selección acomoda el grafo entero.
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
| `L` | acomodar el grafo (auto-layout) | 7 |
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

- [[2026-07-29-INFORME-Seleccion-Multiple-Alineacion-Nodos-v2.0|Selección múltiple y alineación]] — el detalle de la Fase 0
- [[2026-07-25-ROADMAP-Vision-Producto-Jam-v1.0|Visión y roadmap de producto]] — dónde encaja
- [[2026-07-25-CONCEPTO-Estetica-Nodos-Grasshopper-v1.0|Estética de nodos Grasshopper]] — el lenguaje visual
- [[2026-07-27-INFORME-Nodos-De-Debug-Ver-El-Stream-v1.0|Nodos de debug: ver el stream]] — el visor 2D es su continuación
- [[2026-07-25-PLAN-Persistencia-Segura-Diagramas-Graph-v1.0|Persistencia segura de diagramas]] — de acá sale el portapapeles
- [[2026-07-25-INFORME-Graph-Eliminar-Conexiones-Alt-Click-v1.0|Eliminar conexiones con Alt+click]]
- [[2026-07-29-GUIA-Convencion-Documentacion-Vault-v1.0|Convención de documentación del vault]]
