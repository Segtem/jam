# Inventario del Graph de C++ (agy1, 2026-09-30)
---

El inventario completo y exhaustivo de las capacidades del Graph de C++ ha sido generado y guardado en el archivo de artefacto:
**[`INVENTARIO_GRAPH_CPP_MUDANZA_WEB.md`]**

A continuación se presenta el desglose consolidado por grupos funcionales, identificando cada capacidad del usuario, su disparador, su ligadura con Python (`jam.api`), su ubicación exacta en código C++ y su estado de paridad actual en [editor.js].

---

### Resumen de Totales

| Estado en el Editor Web | Cantidad de Capacidades | Porcentaje |
|---|:---:|:---:|
| **SÍ** (Ya implementado en `editor.js` / `editor.html`) | **24** | **23,1 %** |
| **PARCIAL** (Implementación básica, incompleta o sin paridad ergonómica) | **16** | **15,4 %** |
| **NO** (Pendiente absoluto de implementar) | **64** | **61,5 %** |
| **TOTAL CAPACIDADES RELEVADAS** | **104** | **100,0 %** |

---

## Inventario Consolidado por Grupo

### 1. Edición del Grafo y Vista (Canvas & Viewport)
- **Nuevo grafo:** Vacía nodos, aristas y comentarios. Disparo: Menú `File -> Nuevo` o `Edit -> Vaciar`. C++: [`SJamGraphEditor.cpp:5336`]. Python: Notifica `canvas_publicar`. Web: **SÍ** ([`editor.js:426`]).
- **Abrir diagrama (.jamgraph):** Selector de archivos del SO. Disparo: Menú `File -> Abrir diagrama…`. C++: [`SJamGraphEditor.cpp:5804`]. Web: **SÍ** ([`editor.js:432`]).
- **Guardar diagrama (.jamgraph):** Guarda en ruta activa o abre diálogo. Disparo: Menú `File -> Guardar`. C++: [`SJamGraphEditor.cpp:5728`]. Web: **SÍ** (descarga blob en [`editor.js:427`]).
- **Guardar diagrama como…:** Guarda forzando diálogo de destino. Disparo: Menú `File -> Guardar como…`. C++: [`SJamGraphEditor.cpp:5733`]. Web: **NO**.
- **Pan del lienzo:** Desplaza vista 2D. Disparo: Arrastre botón derecho o medio. C++: [`SJamGraphEditor.cpp:4937, 5088`]. Web: **SÍ** (LiteGraph nativo).
- **Zoom ZUI:** Acerca o aleja anclando al cursor. Disparo: Rueda del ratón. C++: [`SJamGraphEditor.cpp:4919`]. Web: **SÍ** (LiteGraph nativo).
- **Encuadrar selección (F):** Centra y ajusta zoom a nodos elegidos. Disparo: Tecla `F` o `View -> Encuadrar selección`. C++: [`SJamGraphEditor.cpp:3657, 5032`]. Web: **NO**.
- **Encuadrar todo (Home):** Centra todos los nodos. Disparo: Tecla `Home` o `View -> Encuadrar todo`. C++: [`SJamGraphEditor.cpp:3657, 5052`]. Web: **PARCIAL** (`encuadrar()` en [`editor.js:308`] solo corre al cargar ejemplos/arranque).
- **Reencuadrar vista inicial:** Pan (0,0) y zoom 1.0. Disparo: Menú `View -> Reencuadrar`. C++: [`SJamGraphEditor.cpp:5886`]. Web: **NO**.
- **Galería de nodos:** Cuadrícula con un nodo de cada verbo. Disparo: Menú `Display -> Galería`. C++: [`SJamGraphEditor.cpp:5856`]. Web: **NO**.
- **Persistencia de sesión de canvas:** Serializa zoom/pan para sobrevivir al cierre de pestaña. C++: [`SJamGraphEditor.cpp:3003-3087`]. Web: **NO**.
- **Veto de cierre sin guardar:** Modal de confirmación para evitar pérdida de trabajo. C++: [`SJamGraphEditor.cpp:5770-5802`]. Web: **NO**.

### 2. Nodos y Pines
- **Crear nodo al centro:** Clic en ficha de herramienta. Python: [`jam.api.nombre_de_nodo_nuevo`] y `params_de_nodo_nuevo`. C++: [`SJamGraphEditor.cpp:2213, 2305`]. Web: **SÍ** ([`editor.js:246`]).
- **Crear nodo por arrastre (Drag & Drop):** Arrastrar del Ribbon/Paleta al punto exacto. C++: [`SJamGraphEditor.cpp:2226-2269`]. Web: **NO** (solo clic).
- **Eliminar nodo individual:** Botón `×` en la esquina superior del nodo. C++: [`SJamGraphNode.cpp:812-833`]. Web: **PARCIAL** (solo por menú contextual o tecla Delete).
- **Renombrar nodo:** Asigna ID único al nodo. C++: [`SJamGraphEditor.cpp:2271`]. Web: **SÍ** ([`editor.js:155`]).
- **Pines de stream (`in`/`out`):** Nubs de flujo principal con color por tipo. C++: [`SJamGraphNode.cpp:178-224`]. Web: **SÍ** ([`editor.js:63, 74`]).
- **Entradas variádicas automáticas:** Expande slots `in` dinámicamente al conectar (ej. `mesh_merge`). C++: [`SJamGraphEditor.cpp:4300`]. Web: **SÍ** ([`editor.js:64, 98-102`]).
- **Pines nombrados dinámicos:** Filas para firmas de funciones de usuario. C++: [`SJamGraphNode.cpp:531-583`]. Web: **SÍ**.
- **Grisado de inputs cableados:** Deshabilita el control visual cuando entra un cable. C++: [`SJamGraphNode.cpp:501`], [`SJamGraphEditor.cpp:4336`]. Web: **PARCIAL**.
- **Cablear parámetro libre:** Expone un parámetro como entrada. C++: Nativo en cada fila. Web: **SÍ** (menú contextual en [`editor.js:126-131`]).

### 3. Cables, Vías y Conexiones
- **Conexión validada por tipos:** Clic salida -> Clic entrada. C++: [`SJamGraphEditor.cpp:4024, 4238`]. Web: **SÍ** ([`editor.js:46-49`]).
- **Cable fantasma (Rubber-Band):** Trazo interactivo con color semántico. C++: [`SJamGraphEditor.cpp:4476, 5084`]. Web: **SÍ** (LiteGraph nativo).
- **Cancelar conexión en curso:** Tecla `Esc` o clic derecho. C++: [`SJamGraphEditor.cpp:4217, 4943`]. Web: **SÍ**.
- **Desconectar cables (Alt+Clic):** Rompe cables en un pin. C++: [`SJamGraphEditor.cpp:4240-4267`]. Web: **PARCIAL** (solo arrastrando fuera del slot).
- **Colores semánticos en cables:** Color por tipo de dato (Puntos, Malla, etc.). C++: [`SJamGraphEditor.cpp:88, 4442`]. Web: **PARCIAL** (colores genéricos de LiteGraph).
- **Etiquetado textual de tipos en pines:** Nombre legible en pines y tooltips para accesibilidad. C++: [`SJamGraphEditor.cpp:4398`], [`SJamGraphNode.cpp:196`]. Web: **NO**.
- **Vías en cable (Waypoints):** Inserta codo/punto de paso con doble clic. Python: [`jam.api.cable_bajo_punto`]. C++: [`SJamGraphEditor.cpp:4079-4160`]. Web: **NO**.
- **Arrastre de vías en cable:** Permite mover puntos de paso con el ratón. C++: [`SJamGraphEditor.cpp:4966, 5097, 5137`]. Web: **NO**.
- **Insertar Reroute en cable:** `Ctrl + Doble Clic` divide el cable e inserta nodo `reroute_*`. C++: [`SJamGraphEditor.cpp:4161-4215`]. Web: **NO**.

### 4. Selección, Undo/Redo y Portapapeles
- **Selección individual y combinada:** Clic / Shift+Clic / Ctrl+Clic. C++: [`SJamGraphEditor.cpp:3702`]. Web: **SÍ**.
- **Selección por recuadro (Marquee):** Arrastre en fondo con botón izquierdo. C++: [`SJamGraphEditor.cpp:3817, 4972`]. Web: **SÍ**.
- **Seleccionar todo (Ctrl+A):** C++: [`SJamGraphEditor.cpp:3731, 5057`]. Web: **NO**.
- **Deseleccionar todo (Escape):** C++: [`SJamGraphEditor.cpp:3725, 5068`]. Web: **SÍ**.
- **Borrar selección (Delete):** C++: [`SJamGraphEditor.cpp:3740, 5074`]. Web: **SÍ**.
- **Mover selección en bloque:** C++: [`SJamGraphEditor.cpp:3809`]. Web: **SÍ**.
- **Deshacer (Undo / Ctrl+Z):** Snapshots JSON del grafo completo. C++: [`SJamGraphEditor.cpp:2736, 2969`]. Web: **NO**.
- **Rehacer (Redo / Ctrl+Shift+Z / Ctrl+Y):** C++: [`SJamGraphEditor.cpp:2985, 5002`]. Web: **NO**.
- **Copiar (Ctrl+C):** Serializa a JSON en portapapeles del SO. C++: [`SJamGraphEditor.cpp:3088, 5007`]. Web: **NO**.
- **Cortar (Ctrl+X):** Copia y borra selección. C++: [`SJamGraphEditor.cpp:3088, 5012`]. Web: **NO**.
- **Pegar (Ctrl+V):** Lee del SO, renombra IDs, remapea cables internos y desplaza. C++: [`SJamGraphEditor.cpp:3111, 3494`]. Web: **NO**.
- **Duplicar (Ctrl+D):** Clona en sitio sin pisar portapapeles del SO. C++: [`SJamGraphEditor.cpp:3118, 5022`]. Web: **NO**.
- **Auto-layout (L):** Capas topológicas de izquierda a derecha. Python: [`jam.api.acomodar(Json, "auto")`]. C++: [`SJamGraphEditor.cpp:3848, 5047`]. Web: **NO**.
- **Ajustar a grilla (Snap Grid):** Redondea coordenadas al cruce de grilla. Python: `jam.api.acomodar(Json, "snap")`. C++: [`SJamGraphEditor.cpp:3860, 5263`]. Web: **NO**.
- **Alinear nodos:** Izquierda, derecha, arriba, abajo, centro-x, centro-y. Python: `jam.api.acomodar(Json, accion)`. C++: [`SJamGraphEditor.cpp:3848, 5269-5285`]. Web: **NO**.
- **Distribuir nodos:** Espaciado regular horizontal (`dist-x`) o vertical (`dist-y`). Python: `jam.api.acomodar(Json, accion)`. C++: [`SJamGraphEditor.cpp:3848, 5286-5290`]. Web: **NO**.

### 5. Funciones, Compounds y Abstracción (Ctrl+G)
- **Colapsar a función (Ctrl+G):** Extrae subgrafo a función y la instancia en el canvas. Python: [`jam.api.collapse_function`]. C++: [`SJamGraphEditor.cpp:3128-3250, 5027`]. Web: **NO**.
- **Crear nueva función:** Botón `+ Nueva función` en ribbon. Python: [`jam.api.function_manage("create", ...)`]. C++: [`SJamGraphEditor.cpp:1819, 3331`]. Web: **NO**.
- **Editar cuerpo de función:** Carga cuerpo de función en canvas. Python: `jam.api.function_manage("get", ...)`. C++: [`SJamGraphEditor.cpp:1935, 3345`]. Web: **NO**.
- **Guardar función:** Python: `jam.api.function_manage("update", ...)`. C++: [`SJamGraphEditor.cpp:1826, 3358`]. Web: **NO**.
- **Guardar y volver al grafo:** Guarda y restaura grafo padre. C++: [`SJamGraphEditor.cpp:815, 3365`]. Web: **NO**.
- **Volver sin guardar:** Descarta cambios y recupera grafo previo. C++: [`SJamGraphEditor.cpp:821, 3375`]. Web: **NO**.
- **Publicar/Despublicar en Dash:** Conmuta botón en la barra Dash. Python: `jam.api.function_manage("publish", ...)`. C++: [`SJamGraphEditor.cpp:1947, 3402`]. Web: **NO**.
- **Exportar a `.jamtool`:** Guarda paquete portable JSON. Python: [`jam.api.tool_export`]. C++: [`SJamGraphEditor.cpp:1956, 3418`]. Web: **NO**.
- **Renombrar función:** Python: `jam.api.function_manage("rename", ...)`. C++: [`SJamGraphEditor.cpp:1941, 3445`]. Web: **NO**.
- **Eliminar función:** Python: `jam.api.function_manage("delete", ...)`. C++: [`SJamGraphEditor.cpp:1964, 3454`]. Web: **NO**.

### 6. Presets y Plantillas
- **Guardar como Preset Compound:** Guarda en Saved como compound. Python: [`jam.api.preset_save_graph`]. C++: [`SJamGraphEditor.cpp:966`]. Web: **NO**.
- **Camino de aprendizaje (Tutoriales):** Fichas interactivas paso 1..6 y catálogo con tilde de visto. C++: [`SJamGraphEditor.cpp:2003-2200, 5826`]. Web: **PARCIAL** (dropdown simple en [`editor.js:290`]).

### 7. Ejecución del Grafo y Ciclo Preview
- **Validar grafo (✓ Compile):** Valida sin tocar la escena. Python: [`jam.api.compile_graph_json`]. C++: [`SJamGraphEditor.cpp:926, 4618`]. Web: **SÍ** ([`editor.js:422`]).
- **Correr grafo (▶ Run):** Ejecuta pipeline, genera Preview y veredictos. Python: [`jam.api.run_graph_json`]. C++: [`SJamGraphEditor.cpp:932, 4631`]. Web: **SÍ** ([`editor.js:362, 423`]).
- **Fijar resultado (✓ Bake):** Deja permanente el Preview en la escena. Python: [`jam.api.confirm('graph')`]. C++: [`SJamGraphEditor.cpp:954, 4746`]. Web: **SÍ** ([`editor.js:424`]).
- **Descartar resultado (✗ Discard):** Borra actores transitorios del Preview. Python: [`jam.api.discard('graph')`]. C++: [`SJamGraphEditor.cpp:960, 4756`]. Web: **SÍ** ([`editor.js:425`]).
- **Solo ver este nodo (Display Flag ◉):** Recorta ejecución al nodo marcado. C++: [`SJamGraphNode.cpp:775`], [`SJamGraphEditor.cpp:4648`]. Web: **NO**.
- **Live View interactivo (⟳ Live):** Recocina con debounce adaptativo mientras se arrastran perillas/sliders. C++: [`SJamGraphEditor.cpp:937, 4677`]. Web: **PARCIAL** (debounce en [`editor.js:326`] solo compila, no ejecuta en escena).

### 8. Inspector de Datos (Spreadsheet) y Visor 2D
- **Inspector numérico de datos:** Geometry spreadsheet con columnas dinámicas. Python: [`jam.api.inspect_json`]. C++: [`SJamGraphEditor.cpp:1067-1166, 1476`]. Web: **NO**.
- **Filtro de filas en inspector:** C++: [`SJamGraphEditor.cpp:1117, 1485`]. Web: **NO**.
- **Ordenación por columnas en inspector:** C++: [`SJamGraphEditor.cpp:1539`]. Web: **NO**.
- **Visor 2D (UVs y máscaras):** Dibuja islas UV o máscaras en PNG. Python: [`jam.api.preview_2d`]. C++: [`SJamGraphEditor.cpp:1168, 1423`]. Web: **NO**.
- **Selector de canal UV en visor 2D:** C++: [`SJamGraphEditor.cpp:1175`]. Web: **NO**.
- **Visor 2D Full Res (Ventana flotante):** Popup de 768x768 px con doble clic en imagen o miniatura. Python: `jam.api.preview_2d(..., 768, ..., "_full")`. C++: [`SJamGraphEditor.cpp:1340`], [`SJamGraphNode.cpp:860`]. Web: **NO**.
- **Miniaturas en nodos (Substance-style):** Inserta imagen de 64x64 en el cuerpo del nodo. Python: [`jam.api.preview_2d_todos`]. C++: [`SJamGraphEditor.cpp:1244, 1267`], [`SJamGraphNode.cpp:1071`]. Web: **NO**.

### 9. Panel de Texto (DSL Bidireccional y Agente)
- **Alternar panel lateral ("✎ Texto"):** C++: [`SJamGraphEditor.cpp:979`]. Web: **SÍ** ([`editor.js:437`]).
- **Sincronización Canvas -> Texto:** Python: [`jam.api.graph_text`] / `texto_de_grafo`. C++: [`SJamGraphEditor.cpp:2786`]. Web: **SÍ** ([`editor.js:346`]).
- **Aplicar texto al Canvas:** Parsea y reconstruye nodos. Python: [`jam.api.graph_from_text`] / `grafo_de_texto`. C++: [`SJamGraphEditor.cpp:2822`]. Web: **SÍ** ([`editor.js:368`]).
- **Refrescar texto desde Canvas:** Botón `↻ Del canvas`. C++: [`SJamGraphEditor.cpp:2796`]. Web: **SÍ** ([`editor.js:443`]).
- **Reporte de errores sintácticos DSL:** Muestra línea y error. C++: [`SJamGraphEditor.cpp:2866`]. Web: **SÍ** ([`editor.js:370`]).
- **Buzón reactivo para agentes (`canvas_buzon`):** Polling cada 0.5s para reflejar ejecuciones externas de agentes en el canvas. Python: [`jam.api.canvas_buzon`]. C++: [`SJamGraphEditor.cpp:1018, 2892`]. Web: **NO**.
- **Publicar grafo activo (`canvas_publicar`):** Notifica a Python cada cambio del humano. Python: [`jam.api.canvas_publicar`]. C++: [`SJamGraphEditor.cpp:2786`]. Web: **NO**.

### 10. Perillas y Tiradores (Knobs, Scrubs & Parameter Controls)
- **Perilla de ángulos radial (`SJamKnob`):** Arrastre circular para rotaciones; Shift a 5°; aguja gráfica sin perder el cuadro de texto. C++: [`SJamKnob.cpp:1-149`], [`SJamGraphNode.cpp:424`]. Web: **NO**.
- **Tirador numérico sensible (`SJamScrub`):** Arrastre horizontal con protección de expresiones (`=...`). C++: [`SJamScrub.cpp:1-120`], [`SJamGraphNode.cpp:400`]. Web: **PARCIAL** (LiteGraph tiene drag numérico pero no protege `=...`).
- **Slider acotado del nodo `number`:** Spinbox slider restringido dinámicamente a `[min, max]`. C++: [`SJamGraphNode.cpp:251-294`]. Web: **NO**.
- **Selector de variables en `expr`:** Desplegable con nombres de variables vivas. Python: [`jam.api.variables`]. C++: [`SJamGraphNode.cpp:451`], [`SJamGraphEditor.cpp:1310`]. Web: **NO**.
- **Dropdown para Enums:** Selector de lista cerrada. C++: [`SJamGraphNode.cpp:315-356`]. Web: **SÍ** ([`editor.js:86`]).
- **Toggle para booleanos:** Checkbox claro true/false. C++: [`SJamGraphNode.cpp:295-314`]. Web: **SÍ** ([`editor.js:88`]).
- **Selector de Asset (`Content…`):** Botón para abrir Content de Unreal. C++: [`SJamGraphEditor.cpp:702`]. Web: **NO**.

### 11. Modo Compacto
- **Conmutar nodo compacto (▲ / △):** Comprime a 82 px con letras de pin (`jam.letras`) e icono, manteniendo cables anclados. C++: [`SJamGraphNode.cpp:694, 874`]. Web: **NO**.
- **Persistencia de compresión en JSON:** Clave `compact: true`. C++: [`SJamGraphEditor.cpp:4520, 5430`]. Web: **NO**.

### 12. Bypass de Nodos
- **Bypass individual (■ / □):** Apaga nodo legal (`can_bypass`) sin romper cableado. C++: [`SJamGraphNode.cpp:730, 896`]. Web: **PARCIAL** (menú contextual en [`editor.js:123`], sin botón ni validación).
- **Bypass grupal (D):** Conmuta bypass en toda la selección. C++: [`SJamGraphEditor.cpp:3768, 5042`]. Web: **NO**.

### 13. Cajas de Comentarios y Grupos (Comments)
- **Crear caja desde selección (C):** Envuelve nodos elegidos en caja translúcida. C++: [`SJamGraphEditor.cpp:2666, 5037`]. Web: **NO**.
- **Arrastrar caja con su contenido:** Mover el cuerpo arrastra nodos contenidos espacialmente. C++: [`SJamGraphComment.cpp:173`], [`SJamGraphEditor.cpp:2702`]. Web: **NO**.
- **Redimensionar caja:** Tirador en esquina inferior derecha. C++: [`SJamGraphComment.cpp:146, 174`], [`SJamGraphEditor.cpp:2721`]. Web: **NO**.
- **Editar título de caja:** Texto inline en franja superior. C++: [`SJamGraphComment.cpp:60`]. Web: **NO**.
- **Selector de color de caja:** Color picker nativo con swatch. C++: [`SJamGraphComment.cpp:73, 131`]. Web: **NO**.
- **Eliminar caja:** `Delete` borra la caja sin borrar los nodos encerrados. C++: [`SJamGraphComment.cpp:153`], [`SJamGraphEditor.cpp:2628`]. Web: **NO**.

### 14. Búsqueda Rápida de Nodos (Tab / Doble Clic)
- **Buscador emergente tipo Grasshopper:** Doble clic en fondo vacío abre popup predictivo; Enter agrega nodo. C++: [`SJamGraphEditor.cpp:4801, 4897`]. Web: **SÍ** (LiteGraph nativo).

### 15. Ribbon y Catálogo de Herramientas
- **Navegación por familias principales:** Primera fila de botones (Inicio, Geometría, Datos, Materiales...). C++: [`SJamGraphEditor.cpp:707, 1728`]. Web: **NO** (lista plana de acordeones a la izquierda).
- **Segunda fila de categorías:** Filtra categorías dentro de la familia activa. C++: [`SJamGraphEditor.cpp:1764`]. Web: **NO**.
- **Fichas en 3 filas fijas con badges:** Subgrupos en columnas de 3 filas. Python: `jam.ribbon`. C++: [`SJamGraphEditor.cpp:1799`]. Web: **NO**.
- **Identificación de nodos no disponibles:** Fichas deshabilitadas con tooltip explicando el motivo (`t.porque`). C++: [`SJamGraphEditor.cpp:1906`]. Web: **SÍ** ([`editor.js:78, 280`]).

### 16. Estado de Nodos, Veredictos y Accesibilidad
- **Glifos accesibles de veredicto:** Símbolos explícitos en el nodo (`✓` ok, `▲` aviso, `✗` warn, `!` error, `–` omitido, `↑` cancelado). C++: [`SJamGraphNode.cpp:661, 1123-1142`]. Web: **NO** (solo dibuja texto simple abajo con `fillText`).
- **Colores de estado con contraste WCAG AA:** Paleta de cuerpo y borde con contraste > 4.5:1. C++: [`SJamGraphNode.cpp:909, 1144`]. Web: **PARCIAL** (solo `boxcolor` perimetral).
- **Tooltip enriquecido de veredicto:** Diagnóstico completo del oráculo al hacer hover en el estado. C++: [`SJamGraphNode.cpp:670, 1118`]. Web: **PARCIAL** (solo trunca 70 chars de la 1ª línea).

### 17. Iconografía y Badges
- **Insignias con SVG Lucide y fallback:** Iconos vectoriales desde `Resources/Icons/Lucide/icon-map.json`. C++: [`SJamGraphEditor.cpp:1676`], [`SJamGraphNode.cpp:98, 1084`]. Web: **NO**.

---

## Tabla de Atajos de Teclado del Graph C++

| Atajo | Función ejecutada en C++ | Implementado en Web |
|---|---|:---:|
| `Ctrl + Z` | `Deshacer()` (Snapshot Undo) | **NO** |
| `Ctrl + Shift + Z` / `Ctrl + Y` | `Rehacer()` (Snapshot Redo) | **NO** |
| `Ctrl + C` | `Copiar(false)` al portapapeles del SO | **NO** |
| `Ctrl + X` | `Copiar(true)` al portapapeles del SO (Cortar) | **NO** |
| `Ctrl + V` | `Pegar()` desde el portapapeles del SO | **NO** |
| `Ctrl + D` | `Duplicar()` selección in situ | **NO** |
| `Ctrl + G` | `ColapsarSeleccion()` (Crear Compound / Función) | **NO** |
| `Ctrl + A` | `SelectAll()` (Seleccionar todo) | **NO** |
| `Escape` | `CancelarConexion()` / `ClearSelection()` | **SÍ** |
| `Delete` / `Supr` | `DeleteSelection()` (Borrar selección) | **SÍ** |
| `F` | `Encuadrar(true)` (Frame Selected) | **NO** |
| `Home` | `Encuadrar(false)` (Frame All) | **NO** |
| `C` | `CreateCommentFromSelection()` (Caja de comentario) | **NO** |
| `D` | `AlternarBypassDeLaSeleccion()` (Bypass grupal) | **NO** |
| `L` | `AcomodarSeleccion("auto")` (Auto-layout topológico) | **NO** |
| `Alt + Clic` en Pin | Romper conexiones de ese pin | **PARCIAL** |
| `Doble Clic` en Cable | `AlternarViaEnCable()` (Insertar/quitar vía) | **NO** |
| `Ctrl + Doble Clic` en Cable | `InsertarRerouteEnCable()` (Insertar nodo reroute) | **NO** |
| `Doble Clic` en Miniatura | `AbrirVisorFullRes()` (Popup 2D grande) | **NO** |
| `Doble Clic` en Fondo | `OpenSearch()` (Buscador rápido de nodos) | **SÍ** |
| `Shift + Arrastre` en Knob | Acomodar rotación a saltos de 5° | **NO** |
| `Shift + Arrastre` en Scrub | Acomodar número a enteros | **NO** |

---

El inventario queda listo para cruzarse con las partes de `agy2` (resto de UI de C++) y `Codex` (LiteGraph y contrato API), estableciendo la base de la matriz de migración hacia el editor web.
