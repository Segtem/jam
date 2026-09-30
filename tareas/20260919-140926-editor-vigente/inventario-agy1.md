# Inventario de agy1 (2026-09-29): los 43 archivos de VIVO desde d207caf y la sonda que los ejerce

### Inventario de cobertura con motor (`d207caf..HEAD`)

Entre el commit de `verde_editor` (`d207caf`, 2026-08-14) y `HEAD` se modificaron **43 archivos de código vivo** (`VIVO`: `Source`, `Content/Python/init_unreal.py`, `Content/Python/jam`, `oraculo`). A continuación se detalla para cada archivo el subsistema que abarca, los commits involucrados en el rango y las sondas existentes en `tools/experiments/` que lo ejercitan con el motor (diferenciando las que corren dentro de Unreal Editor de aquellas que interactúan con motores externos como Godot o Unity).

---

### Tabla: Archivo → Subsistema → Commits → Sondas de verificación

| # | Archivo | Subsistema que toca | Commits (`d207caf..HEAD`) | Sonda(s) en `tools/experiments/` |
|---|---|---|---|---|
| 01 | [`Content/Python/init_unreal.py`] | **Arranque del editor / MCP**: levanta el servidor HTTP local en segundo plano (`jam.web`, puerto 8790) al iniciar el plugin Python en Unreal. | `7cf56df` | **NINGUNA** *(dudoso pasivo: Unreal lo ejecuta al inicio de cualquier corrida, pero ninguna sonda verifica que `jam.web` escuche en 8790 ni hace peticiones HTTP)* |
| 02 | [`Content/Python/jam/adaptador_godot.py`] | **Base común / Godot**: cliente TCP (puerto 8792) que envía el contrato de la base común al plugin de editor de Godot. | `6cafc87`<br>`41e8092`<br>`8a0b543` | [`verifica_base_comun.py`], [`verifica_colocar.py`] *(con motor Godot headless; **NINGUNA** en Unreal)* |
| 03 | [`Content/Python/jam/adaptador_unity.py`] | **Base común / Unity**: cliente TCP (puerto 8793) que envía el contrato al plugin C# de Unity. | `ef6caed` | [`verifica_base_comun_unity.py`], [`verifica_base_comun.py`] `--motor unity`, [`verifica_colocar.py`] `--motor unity` *(con Unity batchmode; **NINGUNA** en Unreal)* |
| 04 | [`Content/Python/jam/api.py`] | **API pública y puente**: `api.run` para texto y documentos, buzón canvas Slate (`canvas_publicar`, `canvas_pendiente`), filtrado de motores en `spec`/`spec_all`. | `d46aefe`<br>`9dc3002`<br>`ef5bac7`<br>`7cf56df`<br>`b929ffe`<br>`e30bf6b` | [`verifica_texto_58.py`], [`verifica_texto_canvas_58.py`], [`verifica_params_y_fuente_roja_58.py`], [`verifica_registro_neutro_58.py`], [`vitrina_unreal_58.py`], [`verifica_colocar_58.py`] |
| 05 | [`Content/Python/jam/bridge.py`] | **Integración Oracle / paths**: inyección de `vendor/oracle-pkg` en `sys.path` del intérprete Python embebido de Unreal. | `1abd3db` | [`verifica_oracle_shadow.py`] *(ejecuta `menu.selftest_*()` que usa `bridge.ensure_oraculo_on_path()` en editor completo)* |
| 06 | [`Content/Python/jam/colocacion.py`] | **Base común / Colocación**: planificación pura sin motor de `place` (`colocacion.planear`, AABB, reparto y raycast). | `6cafc87` | [`verifica_colocar.py`] *(vía Godot y Unity; **NINGUNA** en Unreal, pues Unreal ejecuta `place.colocar` nativo)* |
| 07 | [`Content/Python/jam/comun.py`] | **Base común / Geometría pura**: registro e implementación en el núcleo de generadores, operadores y curvas comunes. | `e1df64a`<br>`e3bfdb8`<br>`239fe2c`<br>`7996d41`<br>`aad01b6`<br>`41e8092`<br>`47826ae` | [`verifica_caja_comun_58.py`], [`verifica_comunes_58.py`], [`volcar_pipe_58.py`], [`vitrina_unreal_58.py`] |
| 08 | [`Content/Python/jam/curve.py`] | **Cálculo de curvas**: import condicional/diferido de `unreal` para permitir ejecución en núcleo puro. | `41e8092` | [`volcar_pipe_58.py`], [`verifica_pivote.py`], [`verifica_curve_sampling_58.py`] |
| 09 | [`Content/Python/jam/dsl.py`] | **Consola / DSL**: validación estricta de parámetros y opciones con sugerencias difusas (`registro_core`) y uso de `registro.py`. | `dd1c98f`<br>`9ad34c0` | [`verifica_params_y_fuente_roja_58.py`] *(ejecuta líneas de comando por `api.run` rechazando typos)* |
| 10 | [`Content/Python/jam/ejemplos.py`] | **Editor web / Catálogo**: listar y servir ejemplos `.jamgraph` / `.jam` al editor web fuera del motor. | `d46aefe` | **NINGUNA** *(sólo se prueba en tests unitarios `test_editor_web.py`; `verifica_ejemplos.py` lee directamente `examples.json` en disco)* |
| 11 | [`Content/Python/jam/flow.py`] | **Pipeline Flow**: validación de parámetros y opciones inválidas en nodos de pipeline con sugerencias de `registro_core`. | `9ad34c0` | **Dudoso** *(importado pasivamente en casos exitosos por [`verifica_material_mascara.py`], pero **NINGUNA** sonda en motor prueba el rechazo de parámetros o sugerencias en Flow)* |
| 12 | [`Content/Python/jam/funcion.py`] | **Funciones de usuario**: registro neutro (`_registro.REGISTRO`) y preservación del flag `bypass` al expandir subgrafos. | `dd1c98f`<br>`2db55d5` | [`verifica_funcion_graph.py`], [`verifica_perillas_funcion_58.py`] *(el módulo se ejerce en motor; pero la regresión de bypass dentro de funciones sólo se cubre en `test_funcion.py`)* |
| 13 | [`Content/Python/jam/graph.py`] | **Motor de grafos**: `fuente-roja` (cancelación de dependientes nombrando la causa), filtro de motores (`motor: str`), validación de params. | `6cafc87`<br>`8a0b543`<br>`ef5bac7`<br>`dd1c98f`<br>`807459a`<br>`9ad34c0` | [`verifica_params_y_fuente_roja_58.py`], [`verifica_registro_neutro_58.py`], [`verifica_texto_canvas_58.py`], [`verifica_matrices_58.py`] |
| 14 | [`Content/Python/jam/hechos_escena.py`] | **Aura / Hechos L0**: extracción de hechos L0 de actores colocados para juicio determinista con Oracle. | `7717827` | [`sonda_colocacion_aura.py`] *(vía `ue.hechos_escena` en UE 5.8)* |
| 15 | [`Content/Python/jam/malla_core.py`] | **Base común / Malla núcleo**: estructura `Malla`, `Triangulo`, `mesh_box`, soldadura geométrica y cálculo de cajas/áreas/volúmenes. | `47826ae` | [`verifica_caja_comun_58.py`], [`verifica_comunes_58.py`] |
| 16 | [`Content/Python/jam/malla_formas.py`] | **Base común / Primitivas complejas**: generadores puros de triángulo, cápsula, toro, rectángulo redondeado, escaleras y esfera cúbica. | `e1df64a` | [`verifica_comunes_58.py`] *(ejecuta y mide los 7 generadores en UE 5.8)* |
| 17 | [`Content/Python/jam/malla_ops.py`] | **Base común / Operadores**: `transformar` (`mesh_transform`) y `juntar` (`mesh_merge`) calculados en el núcleo puro. | `aad01b6` | [`verifica_comunes_58.py`] |
| 18 | [`Content/Python/jam/malla_plana.py`] | **Base común / Primitivas 2D**: generadores puros de plano/quad, grilla y disco. | `aad01b6` | [`verifica_comunes_58.py`] |
| 19 | [`Content/Python/jam/malla_revolucion.py`] | **Base común / Primitivas revolución**: generadores puros de cilindro, cono y esfera. | `7996d41` | [`verifica_comunes_58.py`] |
| 20 | [`Content/Python/jam/malla_tubo.py`] | **Base común / Tubo**: cálculo puro de tubo sobre curva (`tubo`). | `239fe2c` | [`verifica_base_comun.py`] *(en Godot/Unity; en Unreal **NINGUNA**, ya que en UE `mesh_pipe` sigue usando Geometry Script nativo y no `malla_tubo.py`)* |
| 21 | [`Content/Python/jam/math_core.py`] | **Nodos matemáticos y valores**: resolución de variables y nombres de nodos de valor (`valor-sin-nombre`). | `87a1d36` | [`verifica_math_graph.py`], [`verifica_matrices_58.py`], [`verifica_multi_salida_58.py`] |
| 22 | [`Content/Python/jam/mesh.py`] | **Adaptador Geometry Script**: función `mesh.desde_malla` (materialización de `malla_core.Malla` a `DynamicMesh` en Unreal). | `47826ae` | [`verifica_caja_comun_58.py`], [`verifica_comunes_58.py`] |
| 23 | [`Content/Python/jam/oracle_physics_facts.py`] | **Oráculos de física**: soporte explícito para valores no medibles (`apoyado_medible`, booleano sin nulls). | `b5caad6` | [`verifica_physics_paint_58.py`], [`verifica_oracle_shadow.py`], [`sonda_colocacion_aura.py`] |
| 24 | [`Content/Python/jam/oracle_physics_tanda_facts.py`] | **Oráculos de física por tanda**: `soporte_medible` y `apoyada_medible` en hechos de asentamiento por tanda. | `b5caad6` | [`verifica_physics_paint_58.py`] *(vía `physics.asentar_actores` → `ue.physics_tanda` → `comparar_physics_tanda`)* |
| 25 | [`Content/Python/jam/panel.py`] | **Consola / UI**: función `_no_corrio(verbo, errores)` para frenar la ejecución silenciosa de comandos ante parámetros mal escritos. | `9ad34c0` | [`verifica_params_y_fuente_roja_58.py`] |
| 26 | [`Content/Python/jam/registro.py`] | **Catálogo neutro de verbos**: extracción del registro fuera de `tools.py`, motores soportados por verbo (`motores`), metadata pura. | 12 commits | [`verifica_registro_neutro_58.py`], [`verifica_comunes_58.py`], [`volcar_primitivas_58.py`] |
| 27 | [`Content/Python/jam/registro_core.py`] | **Sugerencias de parámetros**: coincidencia difusa (`difflib`) ante nombres de parámetros u opciones mal escritos. | `9ad34c0` | [`verifica_params_y_fuente_roja_58.py`] |
| 28 | [`Content/Python/jam/servidor.py`] | **Editor web fuera del motor**: servidor HTTP/API local para comunicar el editor web con motores externos. | `f9b1d77`<br>`6cafc87`<br>`d46aefe`<br>`9dc3002` | **NINGUNA** *(sólo se prueba en tests unitarios `test_editor_web.py`)* |
| 29 | [`Content/Python/jam/texto.py`] | **Texto de grafos (`dsl-grafos`)**: conversión bidireccional texto ↔ grafo, nombres e IDs legibles, ejecución por `api.run`. | `7cf56df`<br>`b929ffe`<br>`e30bf6b`<br>`707c910` | [`verifica_texto_58.py`], [`verifica_texto_canvas_58.py`], [`vitrina_unreal_58.py`], [`verifica_colocar_58.py`] |
| 30 | [`Content/Python/jam/tools.py`] | **Adaptador Unreal de verbos**: reexportación de `registro.py`, integración de generadores comunes con `mesh.desde_malla`. | 10 commits | [`verifica_registro_neutro_58.py`], [`verifica_comunes_58.py`], [`volcar_primitivas_58.py`] |
| 31 | [`Content/Python/jam/ue.py`] | **Adaptador de motor**: función `ue.hechos_escena(tanda)` para consultar actores y filtrar componentes de nivel. | `7717827` | [`sonda_colocacion_aura.py`] *(ejercita directamente `hechos_escena`)*, [`verifica_physics_paint_58.py`] |
| 32 | [`Content/Python/jam/web.py`] | **Puerta web / MCP**: servidor HTTP en 127.0.0.1:8790 con lista blanca `POST /api/<función>` y entrega de archivos estáticos. | `d46aefe`<br>`9dc3002`<br>`7cf56df` | **NINGUNA** *(sólo se prueba en unit tests `test_editor_web.py` y `test_mcp.py`; ninguna sonda de motor hace requests HTTP)* |
| 33 | [`Content/Python/jam/web/editor.html`] | **Editor web**: HTML del editor de nodos web. | `d46aefe`<br>`9dc3002` | **NINGUNA** *(asset web estático)* |
| 34 | [`Content/Python/jam/web/editor.js`] | **Editor web**: lógica JS sobre LiteGraph para comunicarse con la API. | `d46aefe`<br>`9dc3002` | **NINGUNA** *(asset web estático)* |
| 35 | [`Content/Python/jam/web/vendor/LICENSE-litegraph`] | **Vendor / Licencia**: texto de licencia MIT de LiteGraph. | `9dc3002` | **NINGUNA** *(documentación/licencia)* |
| 36 | [`Content/Python/jam/web/vendor/litegraph.css`] | **Vendor / Estilos**: CSS de LiteGraph. | `9dc3002` | **NINGUNA** *(asset web estático)* |
| 37 | [`Content/Python/jam/web/vendor/litegraph.js`] | **Vendor / Librería**: biblioteca JS LiteGraph empaquetada. | `9dc3002` | **NINGUNA** *(librería JS externa)* |
| 38 | [`Source/JamEditor/Private/JamEditorModule.cpp`] | **C++ Slate / Editor**: comando `Jam.AbrirGraph`, puente `LlamarApi` para sincronizar con Python, y menú para editor web. | `9dc3002`<br>`ef5bac7`<br>`b929ffe` | [`verifica_texto_canvas_58.py`] *(invoca `Jam.AbrirGraph` y ejercita `LlamarApi`)* |
| 39 | [`Source/JamEditor/Private/SJamGraphEditor.cpp`] | **C++ Slate / Canvas**: panel ✎ Texto (`ConstruirPanelTexto`), `AlCambiarGrafo`, creación de nodos con nombres legibles (`NombreDeNodoNuevo`). | `ef5bac7`<br>`b929ffe` | [`verifica_texto_canvas_58.py`] *(abre el widget en Slate, interactúa con el bucle y verifica la sincronización)* |
| 40 | [`Source/JamEditor/Private/SJamGraphNode.cpp`] | **C++ Slate / Nodo**: visualización de `NodeName` legible en la ficha y tooltip de estado cancelado por `fuente-roja`. | `b929ffe`<br>`807459a` | [`verifica_texto_canvas_58.py`] *(instancia nodos en Slate con `NodeName`)* |
| 41 | [`Source/JamEditor/Public/JamEditorModule.h`] | **C++ Header**: declaraciones de `ComandoAbrirGraph`, `LlamarApi` y `bDisponible`. | `ef5bac7`<br>`b929ffe` | [`verifica_texto_canvas_58.py`] |
| 42 | [`Source/JamEditor/Public/SJamGraphEditor.h`] | **C++ Header**: declaraciones de `NombreDeNodoNuevo`, `AlCambiarGrafo`, `ConstruirPanelTexto`. | `b929ffe` | [`verifica_texto_canvas_58.py`] |
| 43 | [`Source/JamEditor/Public/SJamGraphNode.h`] | **C++ Header**: argumento Slate `NodeName` (`SLATE_ARGUMENT(FString, NodeName)`). | `b929ffe` | [`verifica_texto_canvas_58.py`] |

---

### Lista mínima de sondas que cubre los archivos cubribles

Para ejercitar la totalidad de los cambios con cobertura con motor real, el conjunto mínimo de sondas es:

1. **[`tools/experiments/verifica_texto_canvas_58.py`]** (requiere Slate en editor completo):
   Cubre todo el C++ de Slate (`JamEditorModule.cpp/.h`, `SJamGraphEditor.cpp/.h`, `SJamGraphNode.cpp/.h`), el comando `Jam.AbrirGraph`, el panel lateral de texto y la sincronización bidireccional con [`jam/texto.py`], [`jam/api.py`] y [`jam/graph.py`].
2. **[`tools/experiments/verifica_params_y_fuente_roja_58.py`]**:
   Cubre [`jam/registro_core.py`] (sugerencias difusas de parámetros), [`jam/panel.py`] (freno ante error), [`jam/dsl.py`] (validación de consola) y la lógica de cancelación en cascada de `fuente-roja` en [`jam/graph.py`].
3. **[`tools/experiments/verifica_comunes_58.py`]**:
   Cubre toda la base común geométrica materializada en Unreal: [`jam/malla_formas.py`], [`jam/malla_ops.py`], [`jam/malla_plana.py`], [`jam/malla_revolucion.py`], [`jam/malla_core.py`], [`jam/comun.py`] y [`jam/mesh.py`] (`desde_malla`), además de [`jam/tools.py`] y [`jam/registro.py`].
4. **[`tools/experiments/verifica_registro_neutro_58.py`]**:
   Cubre la separación de catálogo entre [`jam/registro.py`] y [`jam/tools.py`], validando la paridad de `spec()` y `spec_all()` en Unreal.
5. **[`tools/experiments/sonda_colocacion_aura.py`]**:
   Cubre [`jam/hechos_escena.py`], [`jam/ue.py`] (`ue.hechos_escena`) y [`jam/oracle_physics_facts.py`].
6. **[`tools/experiments/verifica_physics_paint_58.py`]**:
   Cubre [`jam/oracle_physics_tanda_facts.py`] y [`jam/oracle_physics_facts.py`] (vía `physics.asentar_actores` → `ue.physics_tanda` en escena real).
7. **[`tools/experiments/verifica_oracle_shadow.py`]**:
   Cubre [`jam/bridge.py`] garantizando que `vendor/oracle-pkg` esté activo y operativo dentro de Unreal Editor completo.
8. **[`tools/experiments/verifica_math_graph.py`]**:
   Cubre [`jam/math_core.py`] evaluando el catálogo de nodos matemáticos y variables en el intérprete del motor.
9. **[`tools/experiments/volcar_pipe_58.py`]** (o [`verifica_pivote.py`]):
   Cubre [`jam/curve.py`] en Unreal.
10. **[`tools/experiments/verifica_funcion_graph.py`]**:
    Cubre [`jam/funcion.py`] en Unreal.

*(Para los motores alternativos fuera de Unreal: [`verifica_base_comun.py`] cubre `adaptador_godot`, `adaptador_unity` y `malla_tubo`; [`verifica_colocar.py`] cubre `colocacion.py`).*

---

### Archivos que NO cubre ninguna sonda (o cobertura dudosa)

De los 43 archivos, **12 archivos no tienen ninguna cobertura mediante sondas de motor**, y **2 tienen cobertura dudosa/incompleta**:

#### 1. Archivos sin ninguna sonda de motor (12)
1. **[`Content/Python/init_unreal.py`]**:
   *Por qué:* Aunque el archivo se interpreta automáticamente al arrancar Python en Unreal, el cambio (`7cf56df`) consiste en inicializar el hilo de `jam.web.iniciar()` en el puerto 8790. Ninguna sonda existente en `tools/experiments/` realiza peticiones HTTP para comprobar que el socket esté abierto ni valida que el servidor esté vivo.
2. **[`Content/Python/jam/web.py`]**:
   *Por qué:* Es el servidor HTTP local para agentes MCP y el editor web. No existe ninguna sonda en `tools/experiments/` que lo importe ni lo pruebe en ejecución (sólo está cubierto por tests de Python sin motor: `test_mcp.py` y `test_editor_web.py`).
3. **[`Content/Python/jam/servidor.py`]**:
   *Por qué:* Es el servidor local de Jam para comunicar el editor web con motores externos (Godot/Unity). Ninguna sonda de `tools/experiments/` lo importa ni lo levanta; sólo se testea en `test_editor_web.py`.
4. **[`Content/Python/jam/ejemplos.py`]**:
   *Por qué:* Creado específicamente para el endpoint del editor web. Las sondas existentes de Unreal como `verifica_ejemplos.py` leen `examples.json` de manera independiente y directa sin importar este módulo.
5. **[`Content/Python/jam/web/editor.html`]**:
   *Por qué:* Archivo estático HTML para el navegador. Ninguna sonda de motor lo renderiza.
6. **[`Content/Python/jam/web/editor.js`]**:
   *Por qué:* Lógica JavaScript del navegador web.
7. **[`Content/Python/jam/web/vendor/LICENSE-litegraph`]**:
   *Por qué:* Texto de licencia estático.
8. **[`Content/Python/jam/web/vendor/litegraph.css`]**:
   *Por qué:* Hoja de estilos estática.
9. **[`Content/Python/jam/web/vendor/litegraph.js`]**:
   *Por qué:* Biblioteca JavaScript vendorizada.
10. **[`Content/Python/jam/colocacion.py`]** *(sin cobertura en Unreal)*:
    *Por qué:* Contiene la lógica pura de colocación para otros motores. En Unreal Editor, el verbo `place` sigue ejecutando el adaptador nativo `place.colocar` / `scatter_core` y jamás pasa por `colocacion.py`. Sólo se ejercita fuera de Unreal a través de Godot y Unity en `verifica_colocar.py`.
11. **[`Content/Python/jam/malla_tubo.py`]** *(sin cobertura en Unreal)*:
    *Por qué:* `malla_tubo.py` implementa el cálculo puro de tubos sobre curvas. En Unreal, el verbo `mesh_pipe` sigue usando Geometry Script nativo (`mesh.pipe` / `AppendSimpleSweptPolygon` en `tools.py`) para conservar el soporte de Pivot Painter (`pivot_uvs`). `malla_tubo.py` sólo es consumido por `comun.py` cuando se invoca desde Godot o Unity (`verifica_base_comun.py`).
12. **[`Content/Python/jam/adaptador_godot.py`]** y **[`Content/Python/jam/adaptador_unity.py`]** *(sin cobertura en Unreal)*:
    *Por qué:* Son adaptadores cliente exclusivos para los motores externos Godot y Unity; no forman parte del runtime de Unreal ni son importados en ninguna ejecución de Unreal Editor.

#### 2. Archivos con cobertura dudosa o incompleta (2)
1. **[`Content/Python/jam/flow.py`]**:
   *Por qué:* El commit `9ad34c0` agregó validación y sugerencias ante parámetros y opciones inválidas en los nodos de pipeline (`from .registro_core import opcion_invalida, param_desconocido`). Aunque `verifica_material_mascara.py` importa `flow`, sólo corre un caso válido exitoso; ninguna sonda en el motor ejerce el rechazo de errores ni las sugerencias en `flow.py`.
2. **[`Content/Python/jam/funcion.py`]**:
   *Por qué:* El commit `2db55d5` implementó que al expandir una función se preserve el flag `bypass` de los nodos internos. Las sondas existentes de funciones en el motor (`verifica_funcion_graph.py`, `verifica_perillas_funcion_58.py`) prueban funciones estándar sin nodos en bypass; y la sonda `verifica_bypass_58.py` prueba bypass en grafos planos sin funciones. Por ende, la regresión específica de funciones con bypass sólo queda cubierta por tests unitarios sin motor (`test_funcion.py`).
