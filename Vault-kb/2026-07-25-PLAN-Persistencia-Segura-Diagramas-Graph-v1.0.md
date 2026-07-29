---
title: "Persistencia segura de diagramas Graph"
tipo: PLAN
version: "1.0"
date: 2026-07-25
updated: 2026-07-25
status: en-progreso
priority: alta
area: JamEditor/Graph
tags:
  - jam
  - graph-editor
  - persistence
  - data-loss
  - schema
---

# Tarea: persistencia segura de diagramas Graph

## Riesgos confirmados

### New conserva la ruta anterior

`SJamGraphEditor::NewGraph()` limpia nodos y aristas, pero no vacía `CurrentPath`. Secuencia de riesgo:

```text
abrir/guardar A.jamgraph → File/New → crear otro grafo → Save
                                           ↓
                                  sobrescribe A.jamgraph
```

### Load modifica antes de validar todo

`LoadGraphJson()` sólo valida que el root sea JSON y luego llama inmediatamente a `NewGraph()`. Los
campos de nodos se leen con `GetStringField()`/`GetNumberField()`, que pueden fallar si el esquema es
incompleto. Un JSON sintácticamente válido pero estructuralmente inválido puede borrar el canvas
actual antes de terminar la carga.

`OpenDiagram()` asigna `CurrentPath = Files[0]` después de llamar a una función `LoadGraphJson()` que no
devuelve éxito/fallo. Por tanto puede dejar como ruta actual un archivo que no cargó correctamente.

### Pérdida silenciosa de tipos

Al cargar parámetros, C++ sólo conserva valores que `TryGetString()` acepta. El editor guarda strings,
pero un JSON generado a mano o por LLM con números/booleanos JSON reales puede perder valores sin
advertencia.

### No existe estado dirty ni versión de esquema

New, Open y cierre de ventana no piden confirmar cambios sin guardar. Tampoco hay `schema_version` ni
migraciones para evolucionar pines, nombres de ops o tipos.

## Implementado — 2026-07-26

### New ya no puede sobrescribir el diagrama anterior

`NewGraph()` y, por extensión, la galería de todos los nodos, vacían `CurrentPath`. El próximo
`Guardar` abre el diálogo y exige elegir un destino nuevo.

### Open es transaccional

`LoadGraphJson()` ahora devuelve éxito/fallo y valida el documento completo en memoria antes de
reemplazar el canvas:

- versión de esquema soportada;
- colección de nodos, verbos conocidos, posiciones y parámetros;
- parámetros string, number y bool, convertidos sin descartarlos silenciosamente;
- endpoints existentes, nombres de pin, compatibilidad de tipos, duplicados y cardinalidad de cada
  entrada.

Si algo falla, conserva los nodos, wires, ruta, zoom y pan que el usuario ya tenía. `OpenDiagram()`
sólo cambia `CurrentPath` después de una carga exitosa.

### Save protege el archivo anterior

El JSON se escribe primero a un archivo `.tmp` junto al destino y sólo después se promueve al nombre
definitivo. Si escribir o promover falla, se muestra un error y el `.jamgraph` anterior queda intacto.

### Esquema inicial

Los documentos nuevos incluyen `"schema_version": 1`. La carga sigue aceptando documentos antiguos
sin el campo como versión 1 y rechaza una versión futura que todavía no conoce.

## Verificación

- `BuildPlugin` del plugin completo contra la misma instalación usada por BotOO:
  Unreal Engine **5.7.4**, Linux Development — `BUILD SUCCESSFUL`.
- Suite Python headless: **31/31 tests OK**.
- `git diff --check`: sin errores de whitespace.

## Pendiente para cerrar la tarea

- Añadir estado `dirty` y diálogo Guardar/Descartar/Cancelar antes de New, Open y cerrar la pestaña.
- Agregar migraciones cuando exista `schema_version: 2`.
- Automatizar round-trips y fallos de carga desde un test Slate/editor; la compilación actual cubre la
  integración C++, pero no puede manejar los file dialogs de forma headless.

## Propuesta

- [x] Construir un modelo temporal validado antes de tocar `Nodes`, `Edges` o `CurrentPath`.
- [x] Hacer `LoadGraphJson()` transaccional y devolver `bool` más diagnósticos.
- [x] `NewGraph()` limpia `CurrentPath`; `InsertAllNodes()` crea explícitamente un documento nuevo.
- Mantener `bDirty` y ofrecer Guardar/Descartar/Cancelar al reemplazar o cerrar un grafo modificado.
- [x] Guardar de forma atómica: archivo temporal en el mismo directorio y rename sólo tras éxito.
- [x] Introducir `schema_version` y validación de pines/verbos. Las migraciones quedan para v2.
- [x] Aceptar strings, numbers y booleans; rechazar objetos, arrays y null con diagnóstico.

## Criterios de aceptación

- New + Save abre diálogo y nunca pisa el archivo anterior implícitamente.
- Un archivo inválido no cambia canvas, ruta, zoom ni selección actuales.
- Cancelar New/Open/Close preserva el trabajo no guardado.
- Los parámetros numéricos y booleanos sobreviven un round-trip aunque el JSON use tipos nativos.
- Una versión futura o no soportada falla sin pérdida de datos.
- Hay tests de carga fallida y round-trip para nodos, posición, params, assets, aristas y versión.

## Relacionado

- [[2026-07-25-PLAN-Contrato-Unificado-Graph-Flow-Presets-Web-v1.0|Contrato unificado de ejecución]]
- [[2026-07-25-INFORME-Auditoria-Proactiva-Jam-v1.0|Auditoría proactiva de Jam]]
