# Jam fuera del motor: núcleo y adaptadores

- ESTADO: ABIERTA
- PRIORIDAD: 94
- ETIQUETAS: arquitectura, decision, commander

- Adjunto: [2026-09-27-JAM-FUERA-DEL-MOTOR.md](2026-09-27-JAM-FUERA-DEL-MOTOR.md)

## Por qué

2026-09-27, Brian: ¿Jam tiene que vivir dentro de Unreal, o puede ser un núcleo fuera del motor
(grafo, DSL, registro neutro de verbos, cálculo puro) con un adaptador por motor —Unreal, Godot,
Unity— que ejecuta lo que ese motor puede y declara sus capacidades? La propuesta, con la medición
del código, está en el adjunto. El acople de verdad está en `tools.py`, que mezcla la descripción
de cada verbo con su ejecución en el motor.

## Qué hacer

Nada hasta que Brian decida. Si va por este camino, las etapas y su criterio de hecho están en el
adjunto: 1) partir `tools.py` (registro neutro al núcleo, implementaciones a `adapter_unreal`; la
más barata y no rompe nada), 2) contrato JSON y adaptador de Unreal, 3) UI web, 4) adaptador de
Godot.

Una corrección a la medición del adjunto (2026-09-27, Claude): `tools.py` tiene 118 líneas con
`"fn":` escritas a mano, pero `tools.REGISTRO` carga **171** verbos: el resto se genera al importar.
Las 171 apuntan a funciones de `jam.tools`, así que la etapa 1 las abarca a todas, no a 116.

Relación con otras tareas: `dsl-grafos` suma a su pedido de diseño el criterio de esta nota (el
grafo y el DSL fuera del motor, sin `unreal`, sobre un registro neutro con capacidades); `jam-mcp`
queda más limpio afuera. La etapa 1 puede ir apenas termine `dsl-grafos`, o antes si se quiere que
su diseño nazca sobre el registro neutro.

### Nota (2026-09-28 02:53:25 UTC)

2026-09-27, DECISIÓN de Brian: se va por fuera del motor. Orden: la etapa 1 (partir tools.py: registro neutro en el núcleo, implementaciones en el adaptador de Unreal) va ANTES de implementar dsl-grafos, porque el diseño elegido (Claude v2) se apoya en ese registro (registro.py con motores y no_disponible).

### Nota (2026-09-28 02:57:56 UTC)

2026-09-27, Claude: ETAPA 1 hecha. tools.py partido con un script sobre el AST: jam/registro.py (núcleo, ~1140 líneas) tiene el literal REGISTRO sin las 116 fn, SIN_SPAWN, CATEGORIAS, GRAPH_*, NODOS_MATERIAL, las descripciones de las ops de Flow y los nodos de material, la derivación de source/aridad/in_name/…, PARAMS_ANGULARES, PARAMS_MUDADOS, necesita_instanciar y spec_json. tools.py (adaptador de Unreal) se queda con las t_*, las envolturas de ops de Flow y de material, e IMPLEMENTA = {verbo: fn} (171), que enchufa fn en el MISMO dict: tools.REGISTRO is registro.REGISTRO y reexporta los nombres, así que ningún consumidor cambia. dsl, graph (PARAMS_MUDADOS) y funcion leen de registro. Verificación: (1) volcado del registro entero (con el nombre de cada fn), las constantes y spec_json en HEAD y después: IDÉNTICOS byte a byte (274871 bytes); (2) test_nucleo_sin_motor.py: registro, registro_core, dsl, graph, flow, math_core, funcion, letras, shader, layout, display_core y cache_core importan en un proceso con sys.modules['unreal']=None, el registro trae 171 verbos y ninguno con fn; cada verbo tiene implementación en Unreal. Contra HEAD falla, y también con sólo dsl.py revertido; (3) suite 1263 OK; oracle test VERDE (28/4/3, 1099, 448/448); (4) editor, tools/experiments/verifica_registro_neutro_58.py: JamPlayground VERDE (171 con fn, Cylinder-Strip corre con sus 10 nodos en ok) y BotOO VERDE con el mismo spec_all (sha eefa1306…); la sonda de params y fuente roja sigue VERDE. Sin C++ tocado. Queda para las etapas siguientes: compilar(registro=None) y ejecutar_detalle todavía piden el adaptador por import (tools, library); el campo motores/no_disponible del registro llega con dsl-grafos, que lo necesita.

### Nota (2026-09-28 14:30:06 UTC)

2026-09-28, Claude: en qué motor corre cada verbo, con la decisión de Brian: lo que el motor conectado no tiene se muestra DESHABILITADO, no se esconde. registro: cada verbo declara motores, DERIVADO (op de Flow = pura, «*»; t_* = «unreal») y porque para lo que nunca sale de Unreal (Nanite, Chaos, PCG, Mass, materiales); registro.disponible(verbo, motor, implementados) — si el adaptador anunció lo que implementa, manda eso. tools.motor_activo() = («unreal», lo que tiene fn ahora); JAM_MOTOR_SIMULADO=godot juzga por lo declarado, para ver la ruta de otro motor antes de tenerlo. Compile: un verbo no disponible es error con su porqué. spec_json trae disponible/porque/motores; el C++ deshabilita la ficha del ribbon y el resultado del buscador (tooltip con el porqué; Enter no agrega uno deshabilitado); la ayuda (jam_help) lo marca. Tests: test_motores.py, 13. Compilado (al día); editor: verifica_registro_neutro y verifica_texto siguen VERDE. Suite 1349 OK; oracle test VERDE. Medido: del registro, 29 verbos son puros (puntos, máscaras, weights, sets, transform de puntos) + 69 nodos de valor puros = 98 nodos que ya corren en cualquier motor; 97 son de Unreal hoy (79 de Mesh) y 45 no van a salir de Unreal.

## Próximo paso

Brian propuso (2026-09-28) guardar lo hecho con Unreal y arrancar por nodos simples que anden en los tres motores, para sacar la base común antes de diversificar. Propuesta escrita en la conversación del 2026-09-28: el contrato mínimo del adaptador (malla desde datos, colocar, raycast, assets) y un primer conjunto común. Espera su decisión.

### Nota (2026-09-28 15:36:45 UTC)

2026-09-28, Claude: ETAPA 3, el editor de nodos WEB (pedido de Brian: abrir desde el motor una ventana con los nodos y grafos como el Graph de JamPlayground). Un solo editor, Content/Python/jam/web/editor.html + editor.js, con LiteGraph.js 0.7.18 (MIT, el de ComfyUI; en web/vendor con su licencia): nodos desde el spec del motor (los no disponibles, deshabilitados con su porqué), pines de datos y controles de parámetros, variádicos con entradas «in» que crecen, renombrar, bypass, cablear un parámetro; Compile en vivo pinta cada nodo; Run muestra el estado y el texto de cada nodo; panel ✎ Texto sincronizado (Aplicar, errores por línea); Abrir/Guardar .jamgraph. Protocolo único POST /api/<función>: en Unreal lo sirve jam.web (puerta 8790, ahora «/» = editor, la barra vieja en /consola; nuevas en jam.api con los mismos nombres: estado, spec_editor, compilar_grafo, correr_grafo, texto_de_grafo, grafo_de_texto, preview); en Godot/Unity lo sirve jam/servidor.py (núcleo afuera, puertos 8795/8796) hablándole al plugin. registro.spec_canvas es el spec puro que usan los dos. Menús: Unreal «Jam: editor de nodos (web)» (C++, compilado), Godot «Jam: editor de nodos» (Proyecto ▸ Herramientas), Unity «Jam/Editor de nodos (web)» (C#, compila); abren una ventana en modo aplicación de Chromium (jam.servidor.abrir_ventana). Verificado en el navegador (Chrome) contra los TRES motores de verdad: Godot (grafo con merge → Godot muestra 108 triángulos), Unity (Cylinder-Strip escrito como texto → nodos → Run → 740 triángulos en Unity; mesh_torus marcado no disponible con su línea) y Unreal (el mismo Cylinder-Strip → 740 triángulos con Geometry Script). Tests: test_editor_web.py (las funciones que llama editor.js existen con ese nombre en las dos puertas y en las dos listas blancas; el núcleo del editor contra un Godot falso). Falta: los clics en los menús de cada motor los tiene que ver Brian (el comando que disparan sí se probó); el layout de nodos que llegan del texto es básico (layout.auto + separar encimados).
