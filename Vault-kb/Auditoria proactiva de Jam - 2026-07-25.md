---
title: "Auditoría proactiva de Jam — 2026-07-25"
date: 2026-07-25
status: revision-completa
area: Jam
tags:
  - jam
  - audit
  - bugs
  - technical-debt
  - graph-editor
---

# Auditoría proactiva de Jam — 2026-07-25

## Alcance

Revisión estática y pruebas puras de la interfaz Graph en Slate/C++, el despacho de ejecución, `Flow`,
el grafo de tools, presets, Preview y la infraestructura de pruebas. Esta pasada **sólo documenta**:
no cambia todavía el comportamiento del producto.

## Resumen priorizado

| Prioridad | Hallazgo | Estado | Tarea |
|---|---|---|---|
| Alta | El Graph permite cables incompatibles y más entradas de las que una operación consume | Preflight Flow/tools implementado; falta automatización Slate | [[Tarea - tipado y cardinalidad de conexiones Graph]] |
| Alta | La paleta mezcla Flow y tools, pero el runner sólo admite un grafo completamente Flow o completamente tool | Confirmado por código y prueba pura | [[Tarea - contrato unificado de Graph Flow Presets y Web]] |
| Alta | Guardar un Compound siempre lo marca como `flow`; un preset con tools se ejecuta con el runner equivocado | Confirmado por código | [[Tarea - contrato unificado de Graph Flow Presets y Web]] |
| Alta | Un nodo Flow unario desconectado puede lanzar `IndexError` y una op desconocida se ignora | Reproducido | [[Tarea - errores y resultados observables de Flow]] |
| Alta | `Info` e `Instance` escriben resultados en una copia temporal y el canvas informa cero aunque el trabajo exista | Reproducido/confirmado | [[Tarea - errores y resultados observables de Flow]] |
| Alta | `File → New` conserva `CurrentPath`; el siguiente Save puede sobrescribir el archivo anterior | Corregido 2026-07-26 | [[Tarea - persistencia segura de diagramas Graph]] |
| Alta | Preview no es transaccional ante excepciones y no limpia huérfanos al reiniciar/recargar | Rollback de actores y recuperación por tags implementados; faltan mutaciones y otros assets | [[Tarea - Preview transaccional y efectos de PCG]] |
| Alta | `PCG` estaba en `SIN_SPAWN`, aunque crea volumen y asset | Corregido: volumen en Preview y PCGGraph temporal con Bake/Discard | [[Tarea - Preview transaccional y efectos de PCG]] |
| Alta | Repetir `Asset → Fracture → Place` borra la GC usada por el actor baked anterior | Corregido en Graph: DF/GC temporales por Run y propagación runtime a Place | [[Tarea - Preview transaccional y efectos de PCG]] |
| Alta | El Graph usa el asset de sesión/biblioteca aunque el pin `asset` esté vacío | Corregido por Preflight estricto; Preview/Bake sigue abierto | [[Tarea - compilacion estricta y ciclo Preview Bake del Graph]] |
| Media | Expresiones inválidas pueden convertirse en `0.0` y variables duplicadas se pisan sin diagnóstico | Confirmado por código | [[Tarea - errores y resultados observables de Flow]] |
| Media | Una carga JSON parcialmente inválida puede vaciar el canvas y luego dejar una ruta inválida como actual | Corregido 2026-07-26 | [[Tarea - persistencia segura de diagramas Graph]] |
| Media | Algunas tools continúan con `None` después de fallar el load/spawn y convierten un error de dominio en excepción | Riesgo confirmado por contrato | [[Tarea - contratos defensivos de tools y assets]] |
| Media | No hay pruebas específicas de Jam; la suite encontrada de `oraculo` no inicia desde este checkout | Verificado | [[Tarea - infraestructura de pruebas de Jam y Oraculo]] |

## Reproducciones puras

Se ejecutaron con `PYTHONPATH=Content/Python`, sin Unreal y sin escribir archivos:

```text
unconnected_mask_slope=IndexError: list index out of range
unconnected_move=IndexError: list index out of range
unconnected_info=IndexError: list index out of range
unary_multiple_inputs=sources:2,5 result:2
incompatible_param_wire_dx=25.0
info_stream=3 persisted_stats=None
unknown_op_output=[]
mixed_graph_solo_flow=False
```

Interpretación:

- `Move` recibió streams de 2 y 5 puntos, pero devolvió 2: el segundo cable se dibuja y se ignora.
- Un stream de puntos conectado al parámetro `dx` no aporta un escalar; el cable existe, el campo queda
  deshabilitado, pero el ejecutor conserva silenciosamente el valor local `25`.
- `Info` procesó 3 puntos, pero `_stats` no quedó disponible para el reporte del nodo.
- Una operación eliminada o renombrada produce `[]` en lugar de un error de compatibilidad.

## Verificaciones generales

- Sintaxis Python: **90 archivos analizados, 0 errores**.
- `git diff --check`: correcto al momento de la auditoría.
- Tests: `python3 -m unittest discover -s oraculo/tests -v` encontró 13 módulos y los 13 fallaron
  durante importación. Las causas visibles son imports obsoletos `src.*`/`core` y ausencia de
  `pytest`; no llegaron a ejecutarse casos de prueba.
- No se encontró una suite específica para `Content/Python/jam` ni configuración de proyecto para
  ejecutar pruebas de Jam de forma uniforme.

### Actualización posterior

La primera corrección priorizada agregó `Content/Python/tests/test_flow_validation.py` con 8 pruebas
puras de tipos, aridad, operaciones desconocidas, variables y metadata. La deuda general de packaging,
CI, tests de tools y automatización Unreal continúa abierta.

El 2026-07-26 se agregó el Preflight del grafo de tools y 12 pruebas puras adicionales. La suite Jam
suma 20 tests; también se hizo un smoke de resolución de assets en Unreal. Permanecen abiertos el
runner Graph/Flow unificado, Preview transaccional, semántica de actores y automatización de Slate.

## Orden sugerido

1. Definir si habrá un runner unificado o dos modos de canvas explícitos; corregir presets y Web con
   la misma decisión.
2. Hacer Preview transaccional antes de ampliar herramientas con efectos sobre el nivel o Content.
3. Corregir observabilidad/errores de Flow y persistencia segura del editor.
4. Ampliar las pruebas puras y agregar automatización Slate antes de tocar la semántica de actores.

## Archivos principales revisados

- [`Content/Python/jam/flow.py`](../Content/Python/jam/flow.py)
- [`Content/Python/jam/graph.py`](../Content/Python/jam/graph.py)
- [`Content/Python/jam/panel.py`](../Content/Python/jam/panel.py)
- [`Content/Python/jam/api.py`](../Content/Python/jam/api.py)
- [`Content/Python/jam/preset.py`](../Content/Python/jam/preset.py)
- [`Content/Python/jam/tools.py`](../Content/Python/jam/tools.py)
- [`Content/Python/jam/pcg.py`](../Content/Python/jam/pcg.py)
- [`Source/JamEditor/Private/SJamGraphEditor.cpp`](../Source/JamEditor/Private/SJamGraphEditor.cpp)
- [`Source/JamEditor/Private/JamEditorModule.cpp`](../Source/JamEditor/Private/JamEditorModule.cpp)
