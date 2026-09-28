# La base común de nodos corre igual en Unreal, Godot y Unity

- ESTADO: ABIERTA
- PRIORIDAD: 93
- ETIQUETAS: arquitectura, godot, commander


## Por qué

2026-09-28, Brian: guardar lo hecho con Unreal y arrancar por nodos simples que funcionen en los tres
motores, para sacar la base común antes de diversificar. Decidido en la conversación:

- La base común es un **contrato mínimo** que cada motor implementa —malla desde datos, colocar y
  borrar con Preview, raycast, resolver un asset— y todo lo demás se calcula en el núcleo, igual
  en los tres.
- **Mismo nombre en los tres**: cuando un verbo pasa a la base común (p. ej. `mesh_box`), Unreal
  también lo calcula en el núcleo; si corriera otro código, la base no sería común.
- **Godot primero**, Unity después.
- Lo de antes queda en el tag `unreal-base-2026-09-28`; los verbos propios de Unreal siguen siendo
  su diversificación.

## Criterio de hecho

El mismo grafo corre en los tres motores y produce los mismos hechos (vértices, transformaciones),
que Oracle juzga igual.

### Nota (2026-09-28 14:45:14 UTC)

2026-09-28, Claude: paso 1 — el primer verbo común. Lo de antes quedó en el tag unreal-base-2026-09-28 (empujado). jam/malla_core.py (puro): la Malla de la base común en el formato de buffers que ya usaban ribbon_core y loft_core (vértices partidos por cara, triángulos, normal y UV0 por vértice), la caja con el winding de Unreal comprobado triángulo por triángulo, y los HECHOS que se comparan entre motores (triángulos, posiciones distintas, caja envolvente, área; no la cuenta de vértices, que cada motor parte distinto). jam/comun.py: IMPLEMENTA de la base común (hoy mesh_box, mismo nombre y misma firma que en Unreal). registro.COMUNES → motores «*». Adaptador de Unreal: mesh.desde_malla (append_buffers_to_mesh + weld_mesh_edges) es su primitiva «malla desde datos», y t_mesh_box ya calcula en el núcleo. Medido con el motor (tools/experiments/verifica_caja_comun_58.py): en tres cajas —con y sin subdivisiones— la del núcleo es IDÉNTICA a la de Geometry Script en triángulos, vértices, caja envolvente, área, volumen y orientación de caras. La primera versión dio distinto con subdivisiones: steps en Geometry Script son VÉRTICES por arista (segmentos = max(steps,2)-1), no cortes; corregido con lo medido. La salida del nodo es la misma de antes. Tests: test_base_comun.py (los números del motor como referencia). Suite 1358 OK; oracle test VERDE; verifica_texto sigue VERDE.

### Nota (2026-09-28 14:51:21 UTC)

2026-09-28, Claude: paso 2 — Godot. El núcleo corre FUERA de Godot (Python común, sin unreal) y le habla al plugin de editor Godot/addons/jam (GDScript, TCP 127.0.0.1:8792, una línea de JSON por pedido; operaciones cerradas: hola, mostrar_malla, descartar, fijar, hechos; sin evaluación de código). Banco de trabajo: ~/Dev/games/JamGodot (git local, plugin por symlink). Contrato en el marco del núcleo (cm, Z arriba); el plugin traduce (swap Y/Z, /100) e INVIERTE cada triángulo: la traducción es una reflexión, y el winding de Godot se MIDIÓ en su propio BoxMesh ((c-a)×(b-a) afuera en 12 de 12). graph.ejecutar_detalle recibe el adaptador (por defecto jam.tools, así Unreal no cambia); jam/adaptador_godot.py trae Cliente, AdaptadorGodot (base común y ops de Flow en el núcleo, mesh_preview por el contrato) y correr_texto (Compile contra lo que Godot implementa). registro.PRIMITIVAS = {mesh_preview} → motores «*». Verificación: tools/experiments/verifica_base_comun_godot.py — lo que Unreal midió sobre la caja del núcleo contra lo que Godot mide sobre la malla que guardó: triángulos, vértices y caja envolvente IGUALES en los tres casos, área dentro de 1e-6 relativo (Godot guarda float32: 59999,998 contra 60000), todas las caras frontales hacia afuera. VERDE; y ROJO con el mutante que no invierte el orden. test_adaptador_godot.py, 6 (contra un Godot falso, incluido el grafo corriendo en un proceso con unreal bloqueado). Unreal sin cambios: verifica_registro_neutro, verifica_texto y verifica_params_y_fuente_roja VERDE. Suite 1364 OK; oracle test VERDE. EL CRITERIO DE HECHO SE CUMPLE PARA mesh_box.

## Próximo paso

1. Crecer la base común, verbo por verbo con la misma prueba cruzada: primitivas (plano, cilindro, esfera, cono), transformar y juntar mallas, curvas, tubo sobre curva.
2. Las primitivas que faltan del contrato: colocar un asset con transformación, raycast y resolver un asset (para colocar y dispersar).
3. `jam-mcp` con Godot: que el MCP pueda hablarle al núcleo con Godot del otro lado (hoy sólo habla con el editor de Unreal).
4. Unity, cuando Godot tenga el primer conjunto.

### Nota (2026-09-28 15:02:02 UTC)

2026-09-28, Claude: las curvas y series pasan a la base común (11 verbos: graph_curve, series_range, series_remap, curve_bezier/polyline/interpolate/line/line_sdl/move/resample/smooth). Sus cuerpos se mudaron TAL CUAL de tools.py a jam/comun.py (misma firma, mismo texto de salida); cada función común devuelve (dato, texto) y tools.py las envuelve con _envolver_comun, así Unreal y Godot corren el mismo código. curve.py importa unreal sólo dentro de la única función que lee un spline real del nivel. Verificación: suite 1364 OK (el test de firmas ahora mira sólo los parámetros por nombre); Unreal, Cylinder-Strip sigue con sus 10 nodos en ok (verifica_registro_neutro, verifica_texto VERDE); Godot, la misma cadena de curvas de Cylinder-Strip corre en el núcleo y mesh_pipe dice que no está disponible en godot, con su línea. En paralelo: agy1 (quad, grid, disc, transform, merge), agy2 (cilindro, cono, esfera) y Codex (adaptador de Unity) trabajan en worktrees contra el fixture de Unreal (tests/fixtures/primitivas_unreal.json, 30 casos) y el juez tests/fixtures_primitivas.py. La vitrina de Unreal (tools/experiments/vitrina_unreal_58.py) guarda /Game/Jam/Vitrina y sobrevive a reabrir el nivel.

### Nota (2026-09-28 15:06:09 UTC)

2026-09-28, Claude: integrado agy1 (Docker, worktree propio, gemini-3.8-flash-high): malla_plana.py (quad, grid, disc) y malla_ops.py (transformar, juntar), con sus tests contra el fixture — revisado: recorren TODOS los casos con el juez, sin unreal, sin tocar archivos existentes. Hallazgos suyos, medidos contra el fixture: en un disco ABIERTO sides cuenta vértices del arco (sides-1 segmentos), en uno cerrado sectores; la rotación de Unreal es Rz(yaw)·Ry(-pitch)·Rx(-roll); con escala de determinante negativo Geometry Script invierte el winding. DECISIÓN al integrar: los GENERADORES comunes (box, quad, grid, disc) se calculan en el núcleo en todos los motores; los OPERADORES comunes (transform, merge) en Unreal siguen con Geometry Script porque también reciben mallas de verbos propios de Unreal con materiales/colores/UV que la malla del núcleo no lleva; en Godot y Unity corre el núcleo; la igualdad la garantiza el fixture (el código del núcleo pasa el juez contra Geometry Script). Verificación: Unreal, tools/experiments/verifica_comunes_58.py — los 8 casos de quad/grid/disc por el camino real del Graph (núcleo → desde_malla) dan lo mismo que Geometry Script; verifica_texto VERDE. Godot, verifica_base_comun_godot.py generalizado a todo el fixture común: 18 casos (3 cajas, 8 generadores planos, 6 transformaciones incl. escala negativa, 1 merge) VERDE en triángulos, vértices, caja, área y VOLUMEN CON SIGNO (métrica nueva del plugin: coincide con Unreal sólo si Godot dibuja las mismas caras; la de «caras hacia afuera» contra el centro no sirve para un merge de dos piezas); el mutante sin inversión da ROJO en los 10 casos cerrados. Suite 1375 OK; oracle test VERDE.

### Nota (2026-09-28 15:09:46 UTC)

2026-09-28, Claude: integrado agy2 (Docker, cuenta 2): malla_revolucion.py (cilindro, cono, esfera) + tests contra el fixture. agy2 encontró un error MÍO en el fixture/juez: «vertices» era la cuenta CRUDA de la DynamicMesh y el juez la comparaba con posiciones distintas; con top_radius=0 Geometry Script deja un vértice por lado en el ápice (98 crudos, 82 posiciones). Arreglo en la fuente: el volcador guarda también «posiciones» (re-volcado: geometría idéntica), y el juez, verifica_comunes y la cruzada de Godot comparan posiciones; el juez además no juzga la orientación de triángulos DEGENERADOS (el ápice). La excepción que agy2 había puesto en su test se reemplazó por el juez común. Otro error mío, en el plugin de Godot: la clave de posiciones con «%.3f» partía en dos los vértices del eje (-0.000 vs 0.000); corregido. La cruzada compara el volumen sólo en mallas CERRADAS (decidido con los triángulos que volcó Unreal: cada arista en dos triángulos); el de una abierta depende del origen. Verificación: Unreal, verifica_comunes 17 casos de generadores (box, quad, grid, disc, cylinder, cone, sphere) por el camino real = Geometry Script; verifica_caja_comun y verifica_texto VERDE. Godot, cruzada con TODO el fixture común: 27 casos VERDE. Suite 1384 OK; oracle test VERDE. En curso: agy1 con mesh_pipe (fixture pipe_unreal.json), Codex con el adaptador de Unity.
