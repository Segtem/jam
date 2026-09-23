---
title: "Soldar bordes (mesh_weld) y el diagnóstico de malla que mentía"
tipo: INFORME
version: "1.0"
date: 2026-08-04
updated: 2026-08-04
status: implementado
area: 03-Mesh-y-materiales
tags:
  - jam
  - mesh
  - geometry-script
  - simplify
  - weld
  - diagnostico
aliases:
  - mesh_weld
  - Por qué Simplify no bajaba
---

# Soldar bordes (`mesh_weld`) y el diagnóstico de malla que mentía

Salió de una sospecha concreta de Brian: correr Simplify sobre `casa_madera` con objetivos cada vez
más agresivos **no cambiaba el número que mostraba el Inspector**. Parecía Simplify roto. No lo
estaba: lo que estaba roto era **lo que se estaba mirando**.

## El diagnóstico mostraba vértices y se leía como triángulos

`_info()` devolvía la primera línea del volcado de `GetMeshInfoString` — una utilidad pensada para
depurar el motor, no para leerse en un Inspector. Esa primera línea trae **sólo vértices**.

Y los objetivos de Simplify se piden **en triángulos**. Es decir: se podía correr
`mesh_simplify_count` con objetivo 5000 y **no había forma de ver si se había cumplido**. El número
que se movía poco era otro número.

`GetTriangleCount` **no existe** en Geometry Script 5.8 — está comentado en el header del propio
motor. La alternativa limpia es `GetNumTriangleIDs`, que coincide con el conteo real en una malla
compacta (todo lo que produce Jam lo es: copia, simplify y merge dejan `auto_compact` o
`append_mesh` sin huecos).

`_info()` ahora usa cuatro consultas nombradas en vez de parsear un volcado:

```text
4820 triángulos · 2412 vértices · cerrada
9314 triángulos · 27942 vértices · abierta · 17932 piezas
```

**`piezas` (`GetNumConnectedComponents`) es el dato que faltaba**: cuando es más de una, un Simplify
puede quedarse muy por debajo del objetivo **sin que sea un error**.

## Simplify nunca estuvo roto: se probó contra una esfera

Antes de tocar nada se aisló el algoritmo. Una esfera generada (cerrada, una sola pieza) simplificada
a 20000 / 5000 / 1000 / 200 triángulos dio **el objetivo exacto las cuatro veces**.

El problema era el asset: `casa_madera` tiene **17932 piezas — una por triángulo, cero vértices
compartidos**. Un colapso de aristas **no toca un borde abierto**, y cada pieza aislada tiene su
propio piso mínimo. Con 17932 piezas sueltas no hay nada que colapsar.

> [!note] La pista falsa que costó tiempo
> `preserve_seams=True` (el default) era una hipótesis razonable, y apagarlo **mejoró algo**
> (268980 → 230184 vértices), lo bastante para parecer la explicación. No lo era: seguía a
> muchísima distancia del objetivo. Una mejora parcial que confirma una hipótesis equivocada es peor
> que ninguna mejora.

## `mesh_weld`: darle al simplificador algo que colapsar

De ahí sale el verbo. Suelda bordes abiertos coincidentes para fusionar piezas que están pegadas
pero no comparten vértices.

El default de Geometry Script (`1e-6`, prácticamente cero) no perdona el error de punto flotante
típico de piezas colocadas a mano. Jam usa **`0,01 cm` (0,1 mm)**: suelda lo casi-coincidente sin
tragarse detalle real.

Soldar **no garantiza** cerrar la malla: piezas genuinamente separadas por diseño quedan intactas, a
propósito. Lo que da es margen donde antes no había ninguno.

## Lo que el registro obligó a mantener sincronizado

Agregar un verbo tocó cinco lugares, y **tres los descubrieron los tests de completitud del propio
repo**, no yo:

| Lugar | Qué |
|---|---|
| `jam/mesh.py` | `weld()` |
| `jam/tools.py` | `t_mesh_weld`, `REGISTRO`, `GRAPH_NO_ASSET`, `GRAPH_IN_NAMES`, `GRAPH_OUT_NAMES` |
| `jam/ribbon.py` | subgrupo «Optimizar» |
| `Resources/Icons/Lucide/` | SVG + entrada en `icon-map.json` |
| `Content/Python/tests/` | `test_mesh_weld.py`, `InfoTests` en `test_mesh.py` |

Que un verbo nuevo sin ícono o sin subgrupo **rompa la suite** es exactamente lo que hace que el
catálogo no se pudra.

## Verificado

- `tools/experiments/verifica_mesh_weld_58.py` — spec, Compile y Run reales sobre `casa_madera` en
  UE 5.8.1, veredicto en `BotOO.log` con prefijo `JAM_MESH_WELD_58`.
- `tools/experiments/verifica_info_limpio_58.py` — que `_info()` reporta las cuatro magnitudes.
- La prueba de la esfera a cuatro objetivos, que es la que descarta el bug en Simplify.

El **gesto en Slate** (arrastrar el nodo desde el ribbon y cablearlo) no tiene camino headless — es
el límite ya documentado para Nanite/Simplify.
