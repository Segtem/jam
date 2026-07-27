---
title: "Tarea: contratos defensivos de tools y assets"
date: 2026-07-25
status: pendiente
priority: media
area: Jam/Tools
tags:
  - jam
  - tools
  - validation
  - error-handling
  - technical-debt
---

# Tarea: contratos defensivos de tools y assets

## Riesgos encontrados

Los resolvers consideran que todo string con `/` o `.` ya es un ObjectPath y lo devuelven sin comprobar
existencia ni clase. Varias tools delegan el load/spawn y luego siguen operando bajo la suposición de
que recibieron un objeto/actor válido.

Ejemplos a revisar dentro de `tools.py` y módulos llamados:

- `Drop`: si `place.colocar()` devuelve `None`, la fase de física recibe un actor inválido.
- `Replace`: una creación fallida puede dejar `blockout=None` y luego intentar etiquetarlo.
- `Snap`: una colocación fallida puede continuar hacia el cálculo/ajuste.
- Cualquier ObjectPath de clase incompatible puede fallar tarde, después de otros efectos.

El grafo legacy captura excepciones por nodo, pero la Dash Bar llama estas tools dentro de `_preview()`
sin un contrato de error estructurado. El usuario puede recibir un traceback o, peor, efectos parciales.

## Propuesta

- Resolver asset como resultado tipado: ruta canónica, objeto cargado, clase y diagnóstico.
- Cada tool declara inputs obligatorios y clase aceptada.
- Nunca continuar con `None`; devolver un `ToolResult` estructurado antes de producir efectos.
- Separar `validate/plan` de `apply` para que Compile pueda comprobar sin tocar Unreal.
- Normalizar errores esperables (`asset_missing`, `wrong_class`, `spawn_failed`, `no_hit`) y conservar
  excepciones inesperadas para logging técnico.
- Añadir pruebas con adaptadores falsos para load/spawn/raycast, sin necesitar Unreal.

## Criterios de aceptación

- Una ruta inexistente o clase incorrecta no crea actores y produce un diagnóstico por nodo/campo.
- Fallos de spawn no se convierten en `AttributeError` posteriores.
- Dash, Graph, presets y Web reciben el mismo resultado estructurado.
- Las tools con efectos declaran qué crean/modifican para que Preview pueda revertirlo.

## Relacionado

- [[Tarea - compilacion estricta y ciclo Preview Bake del Graph]]
- [[Tarea - Preview transaccional y efectos de PCG]]
- [[Auditoria proactiva de Jam - 2026-07-25]]

