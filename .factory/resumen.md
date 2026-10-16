<!-- oracle-factory resumen sha256:f7e3e1259e8ef3747a3da56253b12c16c125394380ded65b601c3ec33d306bc6 -->
# Estado actual

Generado por `oracle-factory resumen` a partir de los registros; no se edita a mano. `oracle-factory resumen --verificar` dice si quedó viejo.

1 capacidad · 2 requisitos vigentes · 0 cambios abiertos

## Lo vigente

El veredicto es el registrado al cerrar el cambio de origen, no una corrida nueva de Oracle sobre todo el sistema.

### editor

Spec completa: [openspec/specs/editor/spec.md](../openspec/specs/editor/spec.md)

| Requisito | Tipo | Requisito de Oracle | Medidas | Veredicto al cerrar | Cambio de origen |
|---|---|---|---|---|---|
| F2 renombra el nodo seleccionado | funcional | `editor_c74fa6931d9c5585a.f2_renombra_el_nodo_seleccionado` | editor.f2_renombra_el_nodo_seleccionado, pruebas.corrida_completa | verde al cerrar el 2026-10-16 | 20261015-221410-renombrar-nodo |
| la variable de un valor conserva su nombre al renombrar el nodo | funcional | `editor_c74fa6931d9c5585a.la_variable_de_un_valor_conserva_su_nombre_al_renombrar_el_nodo` | editor.la_variable_de_un_valor_conserva_su_nombre_al_renombrar_el_nodo, pruebas.corrida_completa | verde al cerrar el 2026-10-16 | 20261015-221410-renombrar-nodo |

## Cambios abiertos

Ninguno.

## Riesgos aceptados

Ninguno.

## Límites declarados

### De cambios con requisitos vigentes

- (20261015-221410-renombrar-nodo) agy (gemini-3.8-flash-high): Se ejecutaron exclusivamente las pruebas indicadas en primer plano: 'cd Content/Python && PYTHONPATH=. python3 -m unittest tests.test_renombrar_nodo </dev/null' (6 pruebas pasadas en ~0.7s), sin abrir sockets ni requerir dependencias no disponibles en el entorno.
- (20261015-221410-renombrar-nodo) agy (gemini-3.8-flash-high): Se verificó 'tools/emitir_hechos_pruebas.py' ejecutándolo con el cambio '20261015-221410-renombrar-nodo', comprobando que extrae escenarios de la spec, compara con los requisitos registrados en factory.json, valida el contrato y genera hechos completos ('completa': 1) sólo cuando no hay discrepancias ni omisiones.
- (20261015-221410-renombrar-nodo) agy (gemini-3.8-flash-high): Se verificó la corrección de la vuelta 5 (codex-1): cuando la spec contiene un requisito no importado por factory.json (o viceversa), emitir_hechos_pruebas.py marca problemas y emite 'completa': 0 impidiendo falsos verdes.
- (20261015-221410-renombrar-nodo) agy (gemini-3.8-flash-high): Se llevaron a cabo pruebas de mutación manuales en copias temporales aisladas dentro de la carpeta de trabajo del revisor (permitir dígitos iniciales en IDENT, omitir validación de nombres usados, disparar F2 sobre campos INPUT o con selecciones múltiples, omitir fallback a nombre viejo de parámetros name vacíos en renombrar.js o desdeJam, omitir asignación de name en onAdded y omitir bloqueo de operaciones math_* usadas por expresiones), comprobando que los tests fallan ante cada una de estas mutaciones.
- (20261015-221410-renombrar-nodo) agy (gemini-3.8-flash-high): No se corrieron 'oracle test', la suite completa de Jam ni el editor de Unreal Engine, respetando las instrucciones del usuario.
- (20261015-221410-renombrar-nodo) agy (gemini-3.8-flash-high): La verificación del editor web se realizó sobre Node.js con LiteGraph, renombrar.js, editor.js y el núcleo de Python vía stdio (puente_nucleo.py); no se probó sobre un navegador web gráfico interactivo.
- (20261015-221410-renombrar-nodo) codex (gpt-6-luna): Revisión estática de la propuesta, la spec y el diff del paquete; del editor.js, renombrar.js, editor.html, marca valor del registro.spec_canvas, editor_en_node.js y test_renombrar_nodo.py; y de tools/emitir_hechos_pruebas.py, contratos, relaciones, catálogos, casos de corpus y revisiones anteriores indicadas. No se editaron archivos del checkout candidato ni se revisaron los 45 archivos excluidos de .factory/tareas.
- (20261015-221410-renombrar-nodo) codex (gpt-6-luna): Se ejecutó exactamente: cd /home/workstation/Dev/jam-renombrar-nodo/Content/Python && PYTHONPATH=. python3 -m unittest tests.test_renombrar_nodo </dev/null. Resultado: 6 tests, OK.
- (20261015-221410-renombrar-nodo) codex (gpt-6-luna): El arnés carga LiteGraph, renombrar.js y editor.js reales y usa el núcleo por un puente de stdin/stdout; LGraphCanvas es un doble que conserva selección y no dibuja. La tecla F2 es un evento sintético. No se ejecutó navegador ni editor de Unreal, conforme al alcance indicado.
- (20261015-221410-renombrar-nodo) codex (gpt-6-luna): El contrato cubre los seis escenarios de ambos requisitos. El emisor compara requisitos de la spec con el registro Factory, exige cobertura de cada escenario, rechaza entradas extra y casos repetidos o no ejecutados exactamente una vez; esto se revisó por inspección, sin ejecutar el emisor. No se ejecutó oracle test, tests.test_editor_web ni la suite completa.
- (20261015-221410-renombrar-nodo) codex (gpt-6-luna): No hice mutaciones manuales. Las correcciones observadas de vueltas previas siguen presentes: fallback para name ausente/vacío, detección de expresiones que usan operaciones sin name (incluidos errores plurales) y detección de requisitos/escenarios faltantes en el emisor. No encontré defectos adicionales demostrables dentro del alcance.
