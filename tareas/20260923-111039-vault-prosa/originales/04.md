---
title: "Infraestructura de pruebas de Jam y Oráculo"
tipo: PLAN
version: "1.0"
date: 2026-07-25
updated: 2026-07-25
status: pendiente
priority: media
area: 04-Ejecucion-y-pruebas
tags:
  - jam
  - testing
  - ci
  - oraculo
  - technical-debt
---

# Tarea: infraestructura de pruebas de Jam y Oráculo

## Estado observado

- Al comenzar la auditoría no había tests específicos para `Content/Python/jam`.
- No hay `pyproject.toml`, `pytest.ini`, `setup.cfg` ni archivo equivalente que establezca dependencias,
  paths y comando de prueba del repositorio.
- La sintaxis de los 90 archivos Python bajo `Content/Python/jam` y `oraculo` compiló correctamente.
- `python3 -m unittest discover -s oraculo/tests -v` descubrió 13 módulos, pero ninguno llegó a correr:
  la mayoría importa `src.mazes`/`src.foundry`, aunque en este checkout existen `oraculo/mazes` y
  `oraculo/foundry`; otros requieren `pytest` o un módulo externo `core` no disponible en ese path.

Esto no prueba que el Oráculo esté roto dentro de su entorno histórico, pero sí que el repositorio no
ofrece hoy una forma reproducible de verificarlo desde su raíz.

## Avance 2026-07-25

Se agregó `Content/Python/tests/test_flow_validation.py`: 8 tests puros que cubren entradas faltantes o
excedentes, cables incompatibles, conexión `Number → parámetro numérico`, aridad variádica, operaciones
desconocidas, metadata de `Info` y variables duplicadas. Se ejecutan con:

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=Content/Python \
python3 -m unittest discover -s Content/Python/tests -v
```

La infraestructura global y la suite histórica de Oráculo siguen pendientes.

## Avance 2026-07-26

Se agregó `Content/Python/tests/test_graph_preflight.py` con 12 pruebas puras para la compilación del
grafo de tools: asset explícito, ausencia de fallback global, `Asset/Pick`, resolución fallida,
compatibilidad de tipos, parámetros cableados, cardinalidad, verbos desconocidos y ciclos. La suite de
Jam queda en 20 tests correctos (8 Flow + 12 Graph) con el mismo comando anterior.

Además se realizó un smoke separado dentro de `UnrealEditor-Cmd` para comprobar el contrato contra el
Asset Registry real sin crear actores. La configuración única de tests/CI y la suite histórica de
Oráculo continúan pendientes.

La capa de Preview transaccional suma 8 pruebas con adaptadores falsos de actores y assets: reemplazo
por owner, rollback de spawns/assets parciales, recuperación desde tags, aislamiento, promoción de
assets sin overwrite y conservación recuperable ante fallos de Bake/Discard. La suite Jam suma ahora
31 tests puros. Incluyen la regresión `Run → Bake → Run → Discard` para PCG y Fracture, además de
verificar que el runner entregue al consumidor la ruta temporal realmente producida por un
transformador, en lugar de la ruta final predicha por Compile. El intento de automatizar spawning real con
`UnrealEditor-Cmd -nullrhi` encontró un `SIGFPE` interno de Unreal 5.7 en hit proxies/viewport, por lo
que esa cobertura necesita una prueba interactiva o Unreal Automation con un entorno renderizable.

## Propuesta

- Definir una única configuración de test y dependencias de desarrollo.
- Corregir/normalizar el package layout o documentar el `PYTHONPATH` requerido.
- Separar tests puros de tests que exigen Unreal Editor.
- Crear una suite pura para:
  - parse/serialize de `.jamgraph`;
  - topología, aridad y tipos;
  - expresiones y variables;
  - dispatcher Graph/Flow;
  - presets y migraciones;
  - transiciones de estado de Preview usando fakes.
- Crear smoke tests de Unreal para load asset, spawn, Preview/Discard y PCG.
- Añadir un comando único local/CI que informe claramente qué suite se omitió y por qué.

## Criterios de aceptación

- Un checkout limpio puede instalar dependencias de desarrollo y ejecutar un comando documentado.
- Los tests puros no importan `unreal` ni requieren Editor.
- Las regresiones reproducidas en [[2026-07-25-INFORME-Auditoria-Proactiva-Jam-v1.0|Auditoría proactiva de Jam]] tienen un test rojo antes
  de su corrección y verde después.
- La suite no depende de imports `src.*` inexistentes ni de paths locales implícitos.

## Relacionado

- [[2026-07-25-INFORME-Auditoria-Proactiva-Jam-v1.0|Auditoría proactiva de Jam]]
