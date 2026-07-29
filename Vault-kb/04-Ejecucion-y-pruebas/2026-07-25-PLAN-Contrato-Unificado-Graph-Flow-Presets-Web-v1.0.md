---
title: "Contrato unificado de Graph, Flow, Presets y Web"
tipo: PLAN
version: "1.0"
date: 2026-07-25
updated: 2026-07-25
status: pendiente
priority: alta
area: 04-Ejecucion-y-pruebas
tags:
  - jam
  - graph-editor
  - flow
  - presets
  - api
  - architecture
---

# Tarea: contrato unificado de Graph, Flow, Presets y Web

## Inconsistencia principal

El canvas carga `api.spec_all()`, una paleta única con tools y operaciones Flow. Sin embargo,
`api.run_graph_json()` sólo distingue dos casos:

```text
todos los nodos pertenecen a OPS_META → panel.ejecutar_flow_json
cualquier otro caso                 → panel.ejecutar_grafo_json
```

Un grafo mixto cae completo al runner legacy de tools. Allí las operaciones Flow son verbos
desconocidos. La paleta ofrece una composición que el producto no puede ejecutar.

## Presets Compound

`SJamGraphEditor::SaveGraphAsPreset()` guarda cualquier canvas mediante `preset_save_graph()`.
`preset.desde_grafo()` marca siempre el resultado como `kind: flow`, aunque contenga `Place`, `Snap` u
otras tools. Al aplicarlo, `preset.aplicar()` lo fuerza a `panel.ejecutar_flow_json()`.

Además, `Flow.evaluar()` convierte operaciones desconocidas en `[]` sin error. El Compound puede
parecer válido mientras omite silenciosamente los nodos tool.

## API Web

El endpoint `POST /run_graph` llama a `api.run_graph()`, que siempre usa el runner legacy. El canvas
C++ llama a `run_graph_json()`, que intenta autodetectar. Un mismo JSON tiene semántica distinta según
el punto de entrada.

## Decisión necesaria

Elegir explícitamente una de estas direcciones:

1. **Grafo unificado:** un único compilador y runtime tipado que soporte tools, streams, valores,
   assets y actores en un mismo DAG.
2. **Dos modos claros:** `Tool Graph` y `Flow Graph`, con paletas, extensión/metadata de archivo,
   presets y runners separados; no permitir mezclar nodos entre modos.

La opción 1 es más potente, pero depende de definir la semántica de `AssetPath`, `ActorRef` y
`Stream<Point>`. La opción 2 permite estabilizar antes el producto con menos ambigüedad.

## Cambios mínimos independientemente de la decisión

- Agregar `graph_kind` y `schema_version` al JSON.
- Validar todos los verbos antes de ejecutar; ninguno puede convertirse silenciosamente en `[]`.
- Guardar el `kind` real en los presets y rechazar combinaciones no soportadas.
- Hacer que C++, Web y presets llamen al mismo punto de entrada público.
- Devolver siempre el mismo envelope de resultado: `ok`, `report`, `nodes`, `diagnostics`,
  `preview_id`.

## Criterios de aceptación

- Un JSON obtiene el mismo resultado desde canvas, preset y Web.
- Un grafo mixto funciona por diseño o falla en Compile con un diagnóstico explícito.
- Guardar/aplicar un Compound con tools nunca ejecuta el runner Flow por accidente.
- Una operación eliminada/renombrada bloquea la ejecución y señala su `node id`.
- Hay pruebas de round-trip `canvas JSON → preset → load → run` para cada clase soportada.

## Relacionado

- [[2026-07-25-PLAN-Tipado-Cardinalidad-Conexiones-Graph-v1.0|Tipado y cardinalidad de conexiones]]
- [[2026-07-25-PLAN-Compilacion-Estricta-Preview-Bake-v1.0|Compilación estricta y ciclo Preview/Bake]]
- [[2026-07-25-INFORME-Auditoria-Proactiva-Jam-v1.0|Auditoría proactiva de Jam]]

