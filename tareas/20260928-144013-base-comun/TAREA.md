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

## Próximo paso

Paso 2, Godot: el contrato JSON del adaptador (malla desde datos, colocar/borrar con Preview, raycast, asset) y un plugin de editor de Godot 4.7.2 que lo implemente; el núcleo corre FUERA de Godot (el runner de la etapa 2 de `fuera-del-motor`). Hecho cuando `caja = mesh_box …` → mostrar en escena da los mismos hechos en Godot que en Unreal.
