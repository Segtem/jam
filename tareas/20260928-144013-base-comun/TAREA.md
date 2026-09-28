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

1. Integrar `mesh_pipe` (agy1, en curso) y sumarlo a la cruzada.
2. La vitrina en los tres motores: el mismo texto guardado en `/Game/Jam/Vitrina` (Unreal), `main.tscn` (Godot) y `JamBaseComun.unity` (Unity), para que Brian los abra.
3. Las primitivas del contrato que faltan (colocar un asset, raycast, resolver un asset) y `jam-mcp` con Godot y Unity.

### Nota (2026-09-28 15:14:22 UTC)

2026-09-28, Claude: LA VITRINA. tools/vitrina/vitrina.py corre el MISMO texto (tools/vitrina/base_comun.jam: caja, esfera, cilindro, cono, disco con agujero, piso de grilla y una torre girada, todo con mesh_transform) en los tres motores y lo guarda: Unreal en JamPlayground /Game/Jam/Vitrina (vitrina_unreal_58.py: carga el nivel si existe y limpia la corrida anterior —con new_level sobre uno existente no había qué guardar—; reabierto en otra sesión: las 7 piezas), Godot en ~/Dev/games/JamGodot/main.tscn (commit en su git local), Unity en ~/Dev/games/JamUnity Assets/Scenes/JamBaseComun.unity. Los tres dan las mismas 7 piezas con los mismos triángulos (12, 320, 144, 288, 64, 66, 28). Pendiente menor: Unity acumula en Assets/JamGenerado las mallas de corridas viejas.

### Nota (2026-09-28 15:16:46 UTC)

2026-09-28, Claude: contaminación del fixture, encontrada y corregida. El volcador corría cada verbo por el camino del Graph; con cone/sphere ya comunes, el re-volcado midió la implementación del NÚCLEO en vez de la de Geometry Script (se vio porque la cuenta cruda de vértices del cono cambió de 98 a 114): la referencia empezaba a compararse contra sí misma. Ahora los generadores comunes se vuelcan llamando directo a la función de Geometry Script de mesh.py (REFERENCIA_GEOMETRY_SCRIPT), y el volcador se NIEGA a volcar un generador común sin su referencia declarada. Re-volcado: los generadores coinciden con la medición anterior de Geometry Script; transform/merge sólo cambiaron el ORDEN de la lista de triángulos (como conjunto idénticos: la caja del núcleo es igual a la de Geometry Script también en las diagonales). El fixture suma 18 casos: triangle, capsule, torus, round_rect, stairs, stairs_curved, sphere_box (con casos inválidos).

### Nota (2026-09-28 15:18:27 UTC)

2026-09-28, Claude: integrado el TUBO (agy1, segunda tanda): malla_tubo.py (tubo sobre CurvePath: marco por tramo, ingleteado con bisectriz y tope miter_limit en el plano de flexión, tapas en abanico desde el índice 1) + test_malla_tubo.py — pasa los 15 casos de pipe_unreal.json con el juez corregido (su worktree tenía el anterior), incluida la esquina de 90°. mesh_pipe es común como OPERADOR: en Unreal sigue con Geometry Script (que además arma los UV de Pivot Painter, pivot_uvs, que la malla del núcleo no lleva); en Godot y Unity, el núcleo. radius_from_parent y pivot_uvs quedaron SIN medir (el fixture no los ejerce). La cruzada suma los tubos sobre recta y bezier: 35 casos VERDE en Godot y en Unity. En curso: agy2 con siete generadores más (triangle, capsule, torus, round_rect, stairs, stairs_curved, sphere_box), Codex con jam-mcp multi-motor.

### Nota (2026-09-28 15:21:06 UTC)

2026-09-28, Claude: frames y ramas a la base común (10 verbos: curve_frames, distribute_frames, transform_frames, points_to_frames, branch_from_frames, curve_child, curve_branches, curve_fuse_collinear, curve_subdivide, curve_offset): la misma mudanza tal cual de tools.py a comun.py que las curvas (todos importaban sólo curve.py, puro); curve_noise no sigue el patrón y queda. Los tests que llamaban tools.t_* directo pasan por tools.implementacion(verbo), el mismo camino del Graph. Verificación: suite 1395 OK; BotOO (tiene el asset PineFrond): los cuatro TreeGen —que ejercen estos verbos— corren en verde por api.run_graph_json (en JamPlayground tres fallan en el Compile por el asset, antes y después).

### Nota (2026-09-28 15:58:50 UTC)

e1df64a: las 7 formas de agy2 (malla_formas.py) en la base común. Juez 18/18; verifica_comunes_58 en JamPlayground VERDE (21 generadores, 31 casos); verifica_base_comun godot y unity VERDE (49 casos). Ya no queda ningún generador de malla sólo-Unreal salvo mesh_revolve/ribbon/extrude/loft (necesitan curva o malla).

### Nota (2026-09-28 16:19:22 UTC)

6cafc87: COLOCAR en los tres motores. Contrato (docs/contrato-motor.md) + guardar_malla, resolver_asset, colocar, raycast; asset/mesh_to_static/place corren sobre ellas y jam.colocacion decide dónde. verifica_colocar_58 (Unreal, nivel vacío /Game/Jam/Pruebas/Colocar) es la referencia; verifica_colocar --motor godot|unity VERDE en 6 casos (puntos con reparto, rejilla por la esquina con sink, girada y escalada, piso del mismo Run, piso del Run anterior, piso fijado); mutante del yaw al revés ROJO en los dos (11 diferencias). Descubierto en Unreal: el raycast ignora el Preview del Run ANTERIOR pero ve lo que el Run en curso ya colocó; mesh_to_static nombra SM_<name> y al fijar nunca pisa (_2, _3). Fuera del motor cada Run empieza descartando el anterior (no transaccional: ponytail) y descartar ya no borra lo fijado. Raycast en 64 bits en Godot y Unity (float32 perdía 0,2 mm a ±10 km: el piso en -5 daba -4,98). Falta en la base común: align (orientar a la normal) y view (sin viewport en el contrato) — se rechazan con su porqué; drop/scatter/source_surface siguen sólo en Unreal. Unity: las cuatro ops de Codex (su sandbox no pudo abrir TCP: la prueba contra el motor se hizo acá). verifica_base_comun ahora mide después de cada caso; 49 VERDE en los dos.
