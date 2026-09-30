# La verificación del editor quedó vencida

- ESTADO: CERRADA
- PRIORIDAD: 95
- ETIQUETAS: verificacion


## Qué se sabe

La llegada del 2026-09-19 sale 1: verde_editor d207caf quedó viejo por dos archivos runtime, incluido bridge.py. No equivale a un bug confirmado del editor.

## Evidencia

tools/relevo.py; RELEVO.md, frontmatter y Verde al soltar. Inventario del 2026-09-19; las cifras históricas no son mediciones nuevas.

## Próximo paso

Repetir las sondas afectadas en JamPlayground y la integración que corresponda en BotOO; guardar marcadores y actualizar verde_editor sólo con evidencia real.

### Nota (2026-09-29 23:46:35 UTC)

2026-09-29, Claude: se retoma con el prompt de Brian, corregido: la foto venció por 43 archivos de VIVO (36 Content/Python/jam, 6 Source/JamEditor, init_unreal.py; los tests NO cuentan). Sondas mínimas: las cuatro de d207caf (matrices, multi-salida, funciones, ejemplos) + las de lo que cambió. Delegado en lectura: agy1 inventario archivo→sonda, agy2 gestos de UI, Codex vigencia de las sondas viejas.

### Nota (2026-09-29 23:52:23 UTC)

2026-09-29, Claude, sobre 758cfc6 (binarios al día: BUILD-JAM.sh → Target is up to date). JamPlayground: verifica_matrices_58 JAM_MATRICES_58 TODO VERDE · verifica_multi_salida_58 JAM_MULTISALIDA_58 TODO VERDE · verifica_funcion_graph JAM_FUNCION_TEST TODO VERDE · verifica_ejemplos 16/19 con 3 FALLAS (TreeGen-Branched-Tree, TreeGen-Curve-Frames, TreeGen-Two-Level: «asset no encontrado: PineFrond», el asset existe sólo en BotOO; JamPlayground nació el 2026-08-15, después de d207caf, así que aquel 19/19 fue en BotOO) · BotOO verifica_ejemplos 19/19 TODO VERDE. Lo que cambió desde d207caf, en JamPlayground: verifica_texto_58 VERDE · verifica_texto_canvas_58 VERDE (lanzada con Jam.AbrirGraph y sin QUIT_EDITOR: la primera vez la corté con QUIT_EDITOR y no dejó marca) · verifica_registro_neutro_58 VERDE · verifica_params_y_fuente_roja_58 VERDE · verifica_caja_comun_58 VERDE · verifica_comunes_58 VERDE · verifica_colocar_58 OK. Integración en BotOO: matrices TODO VERDE · funcion_graph TODO VERDE · texto VERDE · params_y_fuente_roja VERDE · registro_neutro VERDE.

### Nota (2026-09-29 23:59:46 UTC)

2026-09-29, Claude, sobre 758cfc6 — cierre de la re-medición. Además de las 11 anotadas: verifica_web_58 (NUEVA: jam.web por HTTP dentro de Unreal, el hueco más grande del inventario de agy1) VERDE — estado unreal/conectado, 245 verbos habilitados, 22 ejemplos, base_comun corre 20/20 nodos ok, discard borra 7; su mutante JAM_WEB=0 da ROJO (Connection refused) · verifica_physics_paint_58 TODO VERDE · verifica_math_graph TODO VERDE · verifica_perillas_funcion_58 TODO VERDE · verifica_curve_sampling_58 ROJO por la SONDA (esperaba que curve_polyline tuviera sólo pines x/y/z; el parámetro closed existe desde el 2026-08-12, antes de d207caf, así que ya estaba roja en aquella foto y no la certificaba): corregida para mirar sólo pines → TODO VERDE · verifica_oracle_shadow ROJO REAL: dentro de Unreal ningún dominio evalúa (EscalaresInvalidas), porque Oracle lanza su trabajador de escalares con sys.executable = UnrealEditor → tarea oracle-escalares-embebido. Fuera de Unreal: verifica_colocar y verifica_base_comun (49) VERDE en Godot y en Unity. Inventario completo de agy1 en inventario-agy1.md; revisión de Codex (las 4 sondas viejas siguen válidas, con agujeros previos) en la tarea sondas-discriminan; gestos de UI (agy2): existen gesto-cancelado, gesto-texto, gesto-596 (el selector que RELEVO exige) y se abrieron gesto-deshabilitados y gesto-menu-web. VEREDICTO: verde_editor NO se mueve — un rojo real (oracle-escalares-embebido) y cinco gestos de Brian pendientes.

### Nota (2026-09-30 10:10:33 UTC)

2026-09-30: los dos rojos que quedaban por sonda se cerraron — verifica_oracle_shadow TODO VERDE en JamPlayground y BotOO (Oracle 0.36.2 + ORACLE_PYTHON en bridge.py; selftest con el cubo del motor). Ya no hay sondas en rojo; verde_editor sólo espera los cinco gestos de Brian (gesto-596, gesto-texto, gesto-cancelado, gesto-deshabilitados, gesto-menu-web).

### Nota (2026-09-30 14:11:43 UTC)

2026-09-30: con la decisión de una sola interfaz (mudar-a-web), los cinco gestos sobre el C++ se cerraron como reemplazados. verde_editor ya no espera gestos del C++: todas las sondas están en VERDE, así que se puede mover (ver la nota de RELEVO.md).

### Nota (2026-09-30 14:15:49 UTC)

2026-09-30: CERRADA. verde_editor → 89eaa75 (2026-09-30): 18 sondas VERDE en JamPlayground sobre ese commit con binarios al día + ejemplos 19/19 en BotOO. Los gestos del C++ quedaron reemplazados por mudar-a-web. relevo.py: LLEGÓ VERDE.
