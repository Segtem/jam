---
title: "Tarea: tipado y cardinalidad de conexiones Graph"
date: 2026-07-25
status: en-progreso
priority: alta
area: JamEditor/Graph
tags:
  - jam
  - graph-editor
  - type-system
  - validation
  - bug
---

# Tarea: tipado y cardinalidad de conexiones Graph

## Avance 2026-07-25 — Fase 1 implementada

Se implementó el primer contrato ejecutable, compartiendo los tipos visuales existentes
`P/N/T/B/A/S` y la aridad del spec.

### En Python/Flow

- `Flow.validar()` hace un Preflight puro de operaciones, endpoints, pines, tipos, cardinalidad,
  autoconexiones, ciclos, conexiones duplicadas y nombres de variable duplicados.
- `Flow.evaluar()` no llama ninguna op si el Preflight devuelve errores; lanza
  `FlowValidationError` con diagnósticos por `node id`.
- Una op desconocida o sin implementación ya no se convierte silenciosamente en `[]`.
- Los resultados efímeros viven en `Flow.resultados`, separados de los params persistentes.
- `Info` conserva sus stats, `Instance` su resumen y `Text` se reporta como valor, no como `0 puntos`.
- `panel.ejecutar_flow_json()` valida antes de entrar a Preview: un Flow inválido no descarta el
  preview anterior ni toca Unreal.

### En Slate/C++

- `FJamTool` conserva `Arity` desde el spec.
- `CanConnect()` compara el tipo de la salida con el tipo efectivo del pin destino.
- Un cable incompatible se rechaza y explica, por ejemplo: `entrega P; espera N`.
- Parámetros e inputs unarios reemplazan su cable anterior.
- Sólo los nodos con `aridad=-1` mantienen varios cables en `in`.
- Una autoconexión se rechaza explícitamente.
- Al cargar `.jamgraph`, los wires inválidos, duplicados o excedentes se ignoran y se informa el total.

### Verificación

- 8 tests puros de regresión: correctos.
- 42 archivos Python de Jam + tests: sintaxis correcta.
- Spec comprobado: `pts_line=0`, `move=1`, `merge=-1`, `weave=-1`.
- `git diff --check`: correcto.
- Compilación `BotOOEditor Linux Development` con Unreal 5.7: correcta.

### Pendiente para cerrar la tarea completa

- Resolver el contrato unificado o la separación explícita de grafos Flow/tools.
- Distinguir `AssetPath` de `ActorRef`, hoy ambos representados por `A`.
- Agregar automatización de Slate/carga además de los tests Python.
- Realizar la prueba interactiva después de reiniciar Unreal para cargar el módulo recompilado.

## Avance 2026-07-26 — Fase 2 implementada

- `jam.graph.compilar()` aplica en el runner de tools los mismos principios de Preflight: endpoints,
  pines, tipos, cardinalidad, ciclos, variables, expresiones, params y assets explícitos.
- `jam.api.compile_graph_json()` ofrece el contrato de Compile a Slate y a futuros clientes API/Web.
- `Run graph` compila antes de Preview y reutiliza el plan, evitando una segunda resolución divergente.
- La suite suma 12 casos específicos de Graph; junto con Flow son 20 tests puros correctos.
- Se verificó el resolver con el Asset Registry real y se recompiló `BotOOEditor` con Unreal 5.7.

## Problemas reproducidos

### Una operación unaria acepta varias entradas

La UI permite varios cables hacia todo pin principal llamado `in`. Eso es correcto para `Merge`,
`Weave` y otras ops variádicas, pero también sucede en `Move`, máscaras e `Info`, cuya aridad es 1.
El runtime construye las dos entradas y esas funciones leen sólo `e[0]`.

Prueba: dos fuentes de 2 y 5 puntos conectadas a `Move` dieron un resultado de 2 puntos. El segundo
cable queda visible aunque no participa.

### Los colores no hacen cumplir los tipos

Los pines muestran `A`, `P`, `N`, `T` y tienen borde/color de tipo, pero `OnPinClicked()` no comprueba
compatibilidad. Se puede conectar un stream `P` a `dx`, que requiere número. El campo queda
deshabilitado por estar cableado, pero `Flow._param_wires()` sólo acepta como escalar un nodo de valor;
por tanto el cable se ignora y el valor local sigue activo.

Prueba: `pts_circle.out → move.dx` dejó `dx=25.0` sin advertencia.

## Causa técnica

- El spec Python publica `aridad`, `in_name`, `out_name` y tipos de parámetros.
- `FJamTool` carga `in_name`/`out_name`, pero no conserva `aridad`.
- La interfaz usa los tipos para color y etiqueta, no para validar la conexión.
- El runtime tolera cables incompatibles o excedentes en lugar de rechazarlos.

## Propuesta

Definir un contrato común de pin:

```text
A = AssetPath o ActorRef (separarlos si ambos siguen existiendo)
P = Stream<Point>
N = Number
T = Text
S = Spline/Curve
```

- Incorporar `aridad` y tipos completos a `FJamTool`/`FGNode`.
- Validar al cerrar el cable y mostrar un mensaje claro si es incompatible.
- Cardinalidad 1: reemplazar el cable anterior también en `in`.
- Cardinalidad N: permitir varios cables únicamente en operaciones declaradas variádicas.
- Revalidar al cargar JSON, porque un archivo puede saltarse la interacción de UI.
- Repetir la validación en Compile/Preflight; la UI no debe ser la única barrera.
- Mantener el color como ayuda visual, pero acompañarlo con tooltip de tipo esperado/recibido.

## Criterios de aceptación

- `P → dx:N` no crea un wire y explica `se esperaba N, llegó P`.
- `N → dx:N` funciona y deshabilita el campo local.
- Una segunda entrada a `Move.in` reemplaza la anterior o se rechaza de forma explícita.
- `Merge.in` y `Weave.in` aceptan N entradas y consumen todas.
- Un `.jamgraph` con tipos o cardinalidad inválidos no ejecuta y marca ambos extremos relevantes.
- Las mismas reglas se prueban en Python sin Unreal y en automatización de Slate cuando sea viable.

## Relacionado

- [[Tarea - compilacion estricta y ciclo Preview Bake del Graph]]
- [[Tarea - contrato unificado de Graph Flow Presets y Web]]
- [[Auditoria proactiva de Jam - 2026-07-25]]
