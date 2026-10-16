# F2 renombra un nodo y la variable de un valor conserva su nombre

- ESTADO: ABIERTA
- PRIORIDAD: 50
- ETIQUETAS: 

### Nota (2026-10-15 22:14:10 UTC)

OpenSpec: openspec/changes/20261015-221410-renombrar-nodo. Modo de trabajo: confirmacion. Estado de factory: espera aceptación de proposal.md y spec.md.

### Nota (2026-10-15 22:15:15 UTC)

Brian Hollweg (persona, decidio, modo confirmacion) aceptó propuesta y spec openspec/changes/20261015-221410-renombrar-nodo/specs/editor/spec.md; se reiniciaron las validaciones dependientes.

### Nota (2026-10-15 22:15:26 UTC)

Requisitos importados: editor_c257ef91da6aae526.f2_renombra_el_nodo_seleccionado (funcional), editor_c257ef91da6aae526.la_variable_de_un_valor_conserva_su_nombre_al_renombrar_el_nodo (funcional). Los nuevos nacen SIN MEDIR; verificá cobertura antes del juicio.

### Nota (2026-10-15 22:22:20 UTC)

Medidas de editor_c257ef91da6aae526.f2_renombra_el_nodo_seleccionado: editor.f2_renombra_el_nodo_seleccionado, pruebas.corrida_completa; propuestas por claude-code (agente, propuso, modo confirmacion). SIN MEDIR: sin límite adicional declarado. Revisión y juicio anteriores invalidados; no se declara cumplimiento ni aprobación de pertinencia.

### Nota (2026-10-15 22:22:21 UTC)

Medidas de editor_c257ef91da6aae526.la_variable_de_un_valor_conserva_su_nombre_al_renombrar_el_nodo: editor.la_variable_de_un_valor_conserva_su_nombre_al_renombrar_el_nodo, pruebas.corrida_completa; propuestas por claude-code (agente, propuso, modo confirmacion). SIN MEDIR: sin límite adicional declarado. Revisión y juicio anteriores invalidados; no se declara cumplimiento ni aprobación de pertinencia.

### Nota (2026-10-15 22:26:36 UTC)

Medidas de editor_c257ef91da6aae526.f2_renombra_el_nodo_seleccionado: Brian Hollweg (persona, confirmo, modo confirmacion).

### Nota (2026-10-15 22:26:36 UTC)

Medidas de editor_c257ef91da6aae526.la_variable_de_un_valor_conserva_su_nombre_al_renombrar_el_nodo: Brian Hollweg (persona, confirmo, modo confirmacion).

### Nota (2026-10-15 23:47:03 UTC)

Brian Hollweg (persona, decidio, modo confirmacion) aceptó propuesta y spec openspec/changes/20261015-221410-renombrar-nodo/specs/editor/spec.md; se reiniciaron las validaciones dependientes.

### Nota (2026-10-15 23:47:44 UTC)

Requisitos importados: editor_c74fa6931d9c5585a.f2_renombra_el_nodo_seleccionado (funcional), editor_c74fa6931d9c5585a.la_variable_de_un_valor_conserva_su_nombre_al_renombrar_el_nodo (funcional). Los nuevos nacen SIN MEDIR; verificá cobertura antes del juicio.

### Nota (2026-10-15 23:52:36 UTC)

Medidas de editor_c74fa6931d9c5585a.f2_renombra_el_nodo_seleccionado: editor.f2_renombra_el_nodo_seleccionado, pruebas.corrida_completa; propuestas por claude-code (agente, propuso, modo confirmacion). SIN MEDIR: sin límite adicional declarado. Revisión y juicio anteriores invalidados; no se declara cumplimiento ni aprobación de pertinencia.

### Nota (2026-10-15 23:52:37 UTC)

Medidas de editor_c74fa6931d9c5585a.la_variable_de_un_valor_conserva_su_nombre_al_renombrar_el_nodo: editor.la_variable_de_un_valor_conserva_su_nombre_al_renombrar_el_nodo, pruebas.corrida_completa; propuestas por claude-code (agente, propuso, modo confirmacion). SIN MEDIR: sin límite adicional declarado. Revisión y juicio anteriores invalidados; no se declara cumplimiento ni aprobación de pertinencia.

### Nota (2026-10-15 23:53:09 UTC)

Medidas de editor_c74fa6931d9c5585a.f2_renombra_el_nodo_seleccionado: Brian Hollweg (persona, confirmo, modo confirmacion).

### Nota (2026-10-15 23:53:09 UTC)

Medidas de editor_c74fa6931d9c5585a.la_variable_de_un_valor_conserva_su_nombre_al_renombrar_el_nodo: Brian Hollweg (persona, confirmo, modo confirmacion).

### Nota (2026-10-16 00:32:15 UTC)

Juicio Factory: verde; salida Oracle 0; informe .factory/cambios/20261015-221410-renombrar-nodo/oracle-veredicto.txt.

### Nota (2026-10-16 01:16:58 UTC)

Revisión guiada Brian Hollweg: aprobar; registrada por Brian Hollweg (persona, confirmo, modo confirmacion; motivo: seis vueltas de codex y agy, a la vez. La 1 encontró que el editor creaba y cargaba los valores con el name por defecto, que las math_* usadas se rompían, que el emisor no sabía qué casos faltaban y que la prueba no ejercitaba el editor; con decisiones de Brian se corrigió todo y el editor real se prueba en node con LiteGraph y el núcleo. La 2: una expresión rota en plural. La 3: un name vacío al cargar y un escenario que el contrato podía omitir. La 4 y la 5 quedaron incompletas de lado de codex porque su sandbox no abría sockets: el arnés pasó a hablar con el núcleo por stdio, y la 5 trajo además un requisito de la spec que el emisor podía omitir. La 6, completa en los dos, no encontró nada. Cada arreglo con una mutación que lo hace fallar; tests de Jam y oracle test VERDE sin subir cotas.); 0 abiertos derivados; commit bd38361d4f8ff73377b1f883daa95bc638420a27; informe tareas/20261015-221410-renombrar-nodo/revisiones/registro-zd5__e11/informe.json; decisiones tareas/20261015-221410-renombrar-nodo/revisiones/registro-zd5__e11/decisiones.json.

### Nota (2026-10-16 01:18:40 UTC)

Juicio Factory: verde; salida Oracle 0; informe .factory/cambios/20261015-221410-renombrar-nodo/oracle-veredicto.txt.
