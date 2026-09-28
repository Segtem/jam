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
