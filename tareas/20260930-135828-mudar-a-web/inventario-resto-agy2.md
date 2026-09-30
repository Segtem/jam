# Inventario del resto de la interfaz de C++ (agy2, 2026-09-30)
---

He completado el inventario exhaustivo de todo lo que compone la interfaz C++ (Slate) fuera del Graph en [`Source/JamEditor/Private/JamEditorModule.cpp`] y [`Source/JamEditor/Public/JamEditorModule.h`].

El informe técnico detallado fue guardado en:
📁 [inventario_cxx_sin_graph.md]

---

### Resumen de Componentes Auditados (C++ fuera del Graph)

1. **Dash Bar (`JamTabs::Dash`)**: Barra flotante/acoplable estilo PolygonFlow Dash con ribbon de categorías, fichas de verbos con iconos, formulario dinámico de parámetros adaptado por tipos, composición automática de DSL, visualizador de miniatura de asset activo (48x48), y conmutadores de fantasma lila y gizmo cian.
2. **Línea de Comandos (CLI) y Log**: Prompt interactivo estilo Rhino (`Command:`), navegación histórica con flechas arriba/abajo (`EKeys::Up`/`Down`), y log acumulativo de salidas con autoscroll.
3. **Ventana de Content (`JamTabs::Content`)**: Navegador de assets independiente con árbol de carpetas con conteo real de mallas por carpeta, buscador por subcadena, contador de cobertura total vs. mostrados, grilla de miniaturas 88x88 renderizadas mediante [`FAssetThumbnailPool`], paginación dinámica `+200`, y liberación preventiva en `OnEditorPreExit` para evitar asserts de UObjects al cerrar el editor.
4. **Interacción con Viewport y Modo Vivo**: Raycast de visibilidad a 20 Hz (50 ms) trazando 1 km desde la cámara activa del editor de Unreal ([`ComputeAimPoint`]), bloqueo en vivo de spinners `x/y/z` reflejando la mira, congelación de coordenadas absolutas al salir del modo vivo, y precarga de mira para nuevos nodos.
5. **Selección del Motor**: Botón "◧ Selección de UE" ([`PickFromUnrealSelection`]) para capturar la StaticMesh marcada en el Content Browser nativo, lectura de actores seleccionados en el nivel (`pivot`, `brush`), y auto-selección en el viewport tras confirmar.
6. **Presets e Importación**: Menú desplegable de presets de comandos, guardado de comandos como presets, y diálogo nativo de archivos del SO para importar paquetes `.jamtool`.
7. **Nomad Tabs y Menús de Slate**: Spawners nómades en `FGlobalTabmanager`, persistencia de layout en `.ini`, sincronización de geometría y hit-test para Wayland/KWin en Linux, entradas en `Window ▸ Tools ▸ Jam`, comando de consola `Jam.AbrirGraph` y lanzador `OpenWebUI`.

---

### Tabla de Inventario de Capacidades

| ID | Capacidad | Qué hace | Cómo se dispara | Qué llama en Python (archivo:línea) | Depende de Viewport o Selección | Pedido al motor necesario desde la Web | Estado en Web actual |
|---|---|---|---|---|---|---|---|
| **1** | Ribbon Categorías | Fila de tabs por categoría con badges coloreados | Clic en tab | `api.spec()` ([`JamEditorModule.cpp:806`]) | NO | Ninguno | **PARCIAL** (paleta vertical) |
| **2** | Fichas de Verbos | Tarjetas de herramientas con badge e iconografía | Clic en ficha | Estado interno C++ (`SelectTool`) | NO | Ninguno | **PARCIAL** (botones de texto) |
| **3** | Find Tools | Búsqueda rápida por nombre de verbo o doc | Input + Enter | Búsqueda local en lista de herramientas | NO | Ninguno | **SÍ** (`#buscar`) |
| **4** | Panel de Parámetros | Formulario dinámico por tipos (bool, spin, combo, txt) | Al elegir verbo | C++ Slate ([`JamEditorModule.cpp:1895`]) | Indirecto (`x/y/z` en modo vivo) | Ninguno | **PARCIAL** (dentro de nodos) |
| **5** | Composición DSL | Auto-genera comando `verbo p=v asset=...` | Cambio en controles | `api.ghost_target()` ([`JamEditorModule.cpp:1380`]) | Sí (omite `x/y/z` en modo vivo) | Ninguno | **NO** |
| **6** | Miniatura Asset Activo | Cuadro 48x48 con miniatura y nombre en Dash Bar | Selección de asset | Consulta C++ a `AssetRegistry` | Sí (asset activo) | `GET /api/asset_thumbnail?path=...` | **NO** |
| **7** | Botón 👻 Fantasma | Toggle de previsualización translúcida en nivel | Clic en botón Fantasma | `api.run("ghost on=...")` ([`JamEditorModule.cpp:1139`]) | **SÍ (VIEWPORT)** | `POST /api/run` + `POST /api/ghost_target` | **NO** |
| **8** | Botón ◎ Gizmo | Toggle de punto de mira y huella de colocación | Clic en botón Gizmo | `api.run("gizmo on=...")` ([`JamEditorModule.cpp:1160`]) | **SÍ (VIEWPORT)** | `POST /api/run` (`gizmo on=...`) | **NO** |
| **9** | Confirmar / Colocar | Fija preview o ejecuta y coloca comando directo | Clic en ✓ Confirmar | `api.commit(cmd)` ([`JamEditorModule.cpp:2137`]) | Sí (resuelve punto de mira) | `POST /api/commit` con `{cmd}` | **PARCIAL** (`#b-fijar` sólo bakea grafo) |
| **10** | Descartar | Elimina la previsualización activa del nivel | Clic en ✗ Descartar | `api.run("discard")` ([`JamEditorModule.cpp:2149`]) | NO | `POST /api/preview` ("discard") | **PARCIAL** (`#b-descartar`) |
| **11** | Prompt CLI ("Command:") | Entrada textual interactiva de comandos DSL | Escribir + Enter | `api.run(cmd)` ([`JamEditorModule.cpp:2256`]) | NO directo | `POST /api/run` con `{cmd}` | **NO** |
| **12** | Historial CLI (↑/↓) | Navegación histórica de comandos tipeados | Teclas Up / Down | Memoria local C++ (`History`) | NO | Ninguno (gestión local en cliente JS) | **NO** |
| **13** | Log Acumulativo | Historial multilínea estilo Rhino (`> cmd` + resp) | Ejecución de comandos | Acumula salidas en Slate | NO | Ninguno (gestión local en cliente JS) | **PARCIAL** (`#reporte` es monomensaje) |
| **14** | Tab JamContent | Pestaña nómade desacoplable para assets | Botón Content / Menú | `api.assets()` ([`JamEditorModule.cpp:1712`]) | NO | `POST /api/assets` | **NO** |
| **15** | Árbol de Carpetas | Lista lateral con conteo real de mallas por carpeta | Clic en carpeta | `api.assets(q, limit, folder)` | NO | `POST /api/assets` | **NO** |
| **16** | Buscador de Mallas | Filtro de assets por subcadena | Escribir + Enter | `api.assets(q, limit, folder)` | NO | `POST /api/assets` | **NO** |
| **17** | Conteo de Cobertura | Rótulo "X de Y · Z mallas en proyecto" | Al poblar content | Lee `total` y `all` de `api.assets()` | NO | Ninguno (incluido en JSON de assets) | **NO** |
| **18** | Grilla de Miniaturas | Baldosas 88x88 con render de Slate | Al poblar content | Render nativo C++ (`AssetRegistry`) | Sí (renderizado de miniaturas) | `GET /api/asset_thumbnail?path=...` | **NO** |
| **19** | Paginación (+200) | Botón "mostrar más (+200)" sin perder filtro | Clic en botón | `api.assets()` con nuevo límite | NO | `POST /api/assets` | **NO** |
| **20** | Selección de Asset | Fija asset en `jam.session` y actualiza comando | Clic en baldosa | `api.select_asset(path)` ([`JamEditorModule.cpp:1881`]) | NO | `POST /api/select_asset` | **NO** |
| **21** | Limpieza Miniaturas | Previene assert `Index >= 0` en `OnEditorPreExit` | Cierre del editor | C++ Slate (`ReleaseThumbnailResources`) | NO (específico Slate) | No aplica al navegador web | **NO APLICA** |
| **22** | Raycast Cámara 20Hz | Traza línea de 1 km desde cámara para calcular mira | Timer activo Slate | C++ `LineTraceSingleByChannel` | **SÍ (VIEWPORT)** | `GET /api/aim` (llama a `jam.api.aim()`) | **NO** |
| **23** | Modo Vivo x/y/z | Spinners bloqueados mostrando `LiveAim` en vivo | Timer activo Slate | C++ Slate | **SÍ (VIEWPORT)** | Polling o WebSocket a `/api/aim` | **NO** |
| **24** | Congelar Mira | Vuelca mira a valores absolutos al salir de vivo | Flanco descendente vivo | C++ Slate | **SÍ (VIEWPORT)** | Guardar localmente última mira recibida | **NO** |
| **25** | Mira Nodos Nuevos | Precarga coordenadas de mira en nodos de colocado | Al instanciar nodo | `api.params_de_nodo_nuevo()` ([`JamEditorModule.cpp:2205`]) | **SÍ (VIEWPORT)** | `POST /api/params_de_nodo_nuevo` | **NO** (usa defaults) |
| **26** | Pick Selección UE | Captura la StaticMesh marcada en Content Browser UE | Clic en "◧ Selección UE" | `api.run("pick")` ([`JamEditorModule.cpp:1667`]) | **SÍ (CONTENT BROWSER UE)** | `POST /api/run` con `"pick"` | **NO** |
| **27** | Actores del Nivel | Lee actores seleccionados en el nivel | Verbos `pivot`, `brush` | `get_selected_level_actors()` ([`tools.py:236`]) | **SÍ (ACTORES VIEWPORT)** | `GET /api/actores_seleccionados` | **PARCIAL** (corre en backend) |
| **28** | Auto-selección Actores | Selecciona en Unreal los actores recién colocados | Al confirmar colocación | `ue.seleccionar()` ([`ue.py:175`]) | **SÍ (ACTORES VIEWPORT)** | Ejecutado automáticamente por el motor | **SÍ** |
| **29** | Menú Presets | Desplegable de presets reutilizables | Clic en "★ Presets" | `api.presets()` ([`JamEditorModule.cpp:1611`]) | NO | `POST /api/presets` | **NO** |
| **30** | Guardar Preset | Guarda el comando de la CLI como preset | Clic en "★ Guardar" | `api.preset_save_command()` ([`JamEditorModule.cpp:1656`]) | NO | `POST /api/preset_save_command` | **NO** |
| **31** | Importar .jamtool | Selector de archivo del SO para importar paquete | Clic en "↓ Importar..." | `api.tool_import()` ([`JamEditorModule.cpp:675`]) | NO | `<input type="file">` + `POST /api/tool_import` | **NO** |
| **32** | Nomad Tabs Docking | Acople y flotación en el docking de Slate | Al iniciar módulo | C++ Slate (`RegisterNomadTabSpawner`) | NO | No aplica a web (o librería JS Dockview) | **NO APLICA** |
| **33** | Layout Persistido | Guarda posiciones en `.ini` de Unreal | Al guardar layout UE | C++ Slate | NO | Guardar layout en `localStorage` | **NO** |
| **34** | Fixes Wayland/Linux | Sincroniza geometría de ventana y hit-test KWin | Apertura de ventanas | C++ Slate ([`JamEditorModule.cpp:109`]) | NO | No aplica a navegador web | **NO APLICA** |
| **35** | Restablecer Entrada | Limpia punteros huérfanos y modales al cerrar tabs | Cierre de tab | C++ Slate ([`JamEditorModule.cpp:68`]) | NO | No aplica a navegador web | **NO APLICA** |
| **36** | Menús Window▸Tools | Accesos directos a Dash, Content, Graph, Web | Barra menú de Unreal | C++ `UToolMenus` ([`JamEditorModule.cpp:416`]) | NO | Reducir a un solo botón "Jam Web" en UE | **NO** |
| **37** | Comando Consola | `Jam.AbrirGraph` para scripts y sondas | Consola `~` / `-ExecCmds` | C++ `IConsoleManager` | NO | Crear `Jam.AbrirWeb` en C++ o Python | **NO** |
| **38** | OpenWebUI | Inicia HTTP y abre browser/app en puerto 8790 | Menú Tools | `jam.web.iniciar()` ([`JamEditorModule.cpp:457`]) | NO | Ninguno | **SÍ** |
| **39** | Puente API Tipado | Ejecución de comandos con marcadores de respuesta | Llamadas de C++ | `IPythonScriptPlugin` ([`JamEditorModule.cpp:2185`]) | NO | Reemplazado por `fetch('/api/<fn>')` | **SÍ** |

---

### Totales

- **Capacidades totales auditadas (fuera del Graph):** **39**
- **Dependientes de VIEWPORT o SELECCIÓN del motor:** **7**
  1. Raycast de cámara a 20 Hz (`ComputeAimPoint`)
  2. Modo vivo en campos numéricos `x/y/z` (`IsLiveAim`)
  3. Congelación de mira en parámetros (`FreezeAimIntoParams`)
  4. Precarga de mira en nuevos nodos (`ParamsDeNodoNuevo`)
  5. Captura de malla de Unreal (`PickFromUnrealSelection`)
  6. Lectura de actores seleccionados en el nivel (`tools.t_pivot`, `tools.t_brush_source`)
  7. Auto-selección en Unreal de actores colocados (`ue.seleccionar`)
- **Estado de paridad en el editor web (`editor.html` / `editor.js`):**
  - **SÍ:** **5** (12,8%) — Búsqueda de herramientas, auto-selección de actores tras confirmación, lanzador `OpenWebUI`, y la infraestructura HTTP de llamadas a `POST /api/<fn>`.
  - **PARCIAL:** **7** (17,9%) — Categorías y fichas (existen como lista vertical sin iconografía), parámetros (existen dentro de nodos pero no desacoplados en panel inspector), bake y discard (sólo para grafos, no para comandos de colocación directa), reporte (sólo último veredicto), y soporte backend para actores de nivel.
  - **NO (o No Aplica a web):** **27** (69,2%) — La CLI interactiva completa con historial, composición automática de DSL, ventana de Content Browser completa (con miniaturas y árbol de carpetas con conteo), conmutadores de Gizmo y Fantasma, raycast continuo a 20 Hz, presets de comando, importador de herramientas `.jamtool`, docking de Slate y menús de Unreal.
