---
title: "Errores y resultados observables de Flow"
tipo: PLAN
version: "1.0"
date: 2026-07-25
updated: 2026-07-25
status: pendiente
priority: alta
area: 04-Ejecucion-y-pruebas
tags:
  - jam
  - flow
  - diagnostics
  - bug
  - testing
---

# Tarea: errores y resultados observables de Flow

## Fallos confirmados

### Entradas obligatorias sin validar

`mask_slope`, `move` e `info` aislados lanzan `IndexError: list index out of range`, porque sus
funciones acceden a `e[0]`. `panel.ejecutar_flow_json()` captura `ValueError` sólo para ciclos, por lo
que la excepción puede salir del contrato JSON esperado por C++.

### Operaciones desconocidas silenciosas

Si `tabla_fn` no contiene un `kind`, `Flow.evaluar()` asigna `[]` y continúa. Esto oculta archivos
viejos, typos, plugins ausentes y presets guardados con el runner incorrecto.

### Metadata escrita en un diccionario temporal

`_resolver_params()` devuelve un nuevo `dict`. `_info()` escribe `p['_stats']` y `_op_instance()`
escribe `p['_out']` en esa copia. Después, `panel.ejecutar_flow_json()` busca ambas claves en
`nodo['params']`, donde nunca quedaron.

Prueba reproducida: `pts_line(count=3) → info` produjo un stream de 3 puntos, pero
`persisted_stats=None`; el reporte termina mostrando `0 puntos`.

### Nodo Text mal informado

`text` pertenece a `VALOR_KINDS` y recibe `_val`, pero el reporte especial sólo contempla `number` y
`math`. Un nodo texto cae en el caso genérico de streams y aparece como `0 puntos`/warning.

### Expresiones y nombres ambiguos no producen diagnóstico

Una expresión explícita `=expr` que no puede resolverse cae a `0.0`; una expresión implícita inválida
puede conservar el literal y terminar coaccionada al default. En ambos casos el resultado parece un
valor real aunque haya un error de variable, sintaxis o división. Además, dos nodos de valor con el
mismo `name` escriben la misma entrada de la tabla y gana el orden de inserción sin advertencia.

## Diseño recomendado

Separar datos persistidos de resultados de ejecución. Por ejemplo:

```python
EvaluationResult(
    streams={node_id: [...]},
    values={node_id: value},
    metadata={node_id: {...}},
    diagnostics={node_id: [...]},
)
```

Las funciones de op no deberían mutar `params` para comunicarse con la UI. El evaluador debe validar
aridad antes de llamar a cada op y convertir toda falla esperable en un diagnóstico por nodo. Las
excepciones inesperadas deben conservar tipo/contexto, cancelar la transacción y devolver JSON válido.

## Criterios de aceptación

- Todo nodo con entrada obligatoria desconectada queda rojo sin traceback ni efectos parciales.
- Una op desconocida bloquea Compile/Run con `node id` y nombre de op.
- `Info` muestra cantidad y bbox reales.
- `Instance` informa colocados, rechazados y assets reales.
- `Text` muestra `nombre = valor` y estado correcto.
- Una expresión inválida o variable ausente queda roja; nunca se sustituye silenciosamente por cero.
- Los nombres de variable duplicados se rechazan o aplican una regla visible y determinista.
- Los resultados de ejecución no contaminan el JSON persistente del grafo.
- Hay tests puros para aridad 0/1/N, op desconocida, metadata y serialización del resultado.

## Relacionado

- [[2026-07-25-PLAN-Tipado-Cardinalidad-Conexiones-Graph-v1.0|Tipado y cardinalidad de conexiones]]
- [[2026-07-26-PLAN-Preview-Transaccional-Efectos-PCG-v1.0|Preview transaccional y efectos de PCG]]
- [[2026-07-25-INFORME-Auditoria-Proactiva-Jam-v1.0|Auditoría proactiva de Jam]]
