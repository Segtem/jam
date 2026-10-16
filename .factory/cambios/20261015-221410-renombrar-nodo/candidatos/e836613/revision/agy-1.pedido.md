Sos un revisor independiente del cambio 20261015-221410-renombrar-nodo de un proyecto que usa Oracle Factory: «F2 renombra un nodo y la variable de un valor conserva su nombre». No escribiste este código.
NO edites el checkout, no hagas commits ni decidas nada por la persona: tu trabajo es encontrar defectos y contarlos con evidencia.

Qué tiene que hacer el cambio:
- Propuesta: /home/workstation/Dev/jam-renombrar-nodo/openspec/changes/20261015-221410-renombrar-nodo/proposal.md
- Spec (lo que se promete, con sus escenarios): /home/workstation/Dev/jam-renombrar-nodo/openspec/changes/20261015-221410-renombrar-nodo/specs/editor/spec.md

Qué revisar:
- Checkout del candidato e836613 (sólo lectura): /home/workstation/Dev/jam-renombrar-nodo/.factory/local/revisiones/e836613
- Paquete de Oracle Clue con el diff y el contexto: /home/workstation/Dev/jam-renombrar-nodo/.factory/cambios/20261015-221410-renombrar-nodo/candidatos/e836613/clue/paquete-agy-1.json

Fuera del paquete, porque no son producto (.factory, tareas): 4 archivos de registros y evidencia de Factory; no los revises.

Cómo trabajar: leé la spec y el diff; contrastá cada promesa con el código y con las pruebas; buscá casos que fallen, afirmaciones que el
código no cumple y pruebas que no prueban lo que dicen. Si podés, hacé mutaciones a mano sobre copias en tu carpeta y decí cuáles sobreviven.
Mandá la salida larga a archivos de tu carpeta y leé sólo el resumen.

Entregable: un informe JSON en /home/workstation/Dev/jam-renombrar-nodo/.factory/local/revisores/e836613-agy-1/informe.json con este formato (schema oracle-clue.review/v1):
- schema_version "oracle-clue.review/v1"; repo, base, head, diff_sha256 y context_sha256 copiados del paquete;
- provider {"name": "agy", "model": "gemini-3.8-flash-high"};
- findings: lista de hallazgos, cada uno con id, kind, severity (alta|media|baja|informativa), confidence (0 a 1), title, explanation,
  location {file, start_line, end_line, side: "head"} DENTRO de los rangos del diff del paquete, trigger, evidence, related_requirement,
  status "pendiente" y verification;
- review_status ("completo" o "incompleto") y limitations (qué corriste y qué no).
Sin hallazgos: findings vacía, explicado en limitations. Validalo antes de terminar con:
  oracle-clue validar /home/workstation/Dev/jam-renombrar-nodo/.factory/local/revisores/e836613-agy-1/informe.json --paquete /home/workstation/Dev/jam-renombrar-nodo/.factory/cambios/20261015-221410-renombrar-nodo/candidatos/e836613/clue/paquete-agy-1.json --repo /home/workstation/Dev/jam-renombrar-nodo/.factory/local/revisiones/e836613
y terminá con un resumen corto en español.

Indicaciones de quien pide la revisión:
Vuelta 1. Revisá la implementación (Content/Python/jam/web/renombrar.js, el renombrar y el manejador de F2 de Content/Python/jam/web/editor.js, el script en editor.html, la marca valor de registro.spec_canvas) contra los 2 requisitos de la spec, y si Content/Python/tests/test_renombrar_nodo.py prueba de verdad cada escenario; revisá también tools/emitir_hechos_pruebas.py, las relaciones medidas/relaciones/prueba_*.relacion, las medidas medidas/catalogos/editor y pruebas, y los casos medidas/corpus/editor. Mirá especialmente: un renombre que deje un cable o una variable rota, nombres inválidos o repetidos que pasen, F2 que se dispare escribiendo en un campo, nodos de valor con y sin name, y si el emisor puede dar verde con un caso que no corrió. Jam tiene el Graph de C++ congelado: esto va sólo en el editor web. Para correr las pruebas usá exactamente, en primer plano: cd /home/workstation/Dev/jam-renombrar-nodo/Content/Python && PYTHONPATH=. python3 -m unittest tests.test_renombrar_nodo tests.test_editor_web </dev/null . No corras oracle test, la suite completa ni el editor de Unreal. Nombrá archivos con rutas relativas.
