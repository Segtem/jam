---
title: "Ribbon jerárquico del Graph por familias"
tipo: INFORME
version: "1.0"
date: 2026-08-03
updated: 2026-08-03
status: en-progreso
area: 01-Graph
tags:
  - jam
  - graph
  - slate
  - ribbon
  - ux
aliases:
  - Familias del ribbon
  - Navegación compacta del Graph
---

# Ribbon jerárquico del Graph por familias

El Graph llegó a unas veinte categorías en una sola fila horizontal. El scroll evitaba perder
herramientas, pero no permitía comprender el catálogo ni escalar a la biblioteca matemática
planeada. Agregar más verbos iba a empeorar una deuda que ya era visible.

## Decisión

La navegación tiene ahora dos niveles:

| Familia principal | Categorías existentes |
|---|---|
| Inicio | Content, Place, Create, Edit, Display |
| Geometría | Mesh, Vector, Transform, Sets, Combine |
| Distribución | Scatter, Mask, Weight, Source, Output |
| Datos | Params, Maths, Debug |
| Materiales | Shader |
| Funciones | Funciones |

**Aprender** permanece primero como acceso independiente. La fila superior baja así de unas veinte
fichas a siete destinos estables; la segunda fila muestra sólo las categorías de la familia activa.
El tercer nivel existente —los paneles de cada categoría— sigue agrupando los verbos.

## Compatibilidad

`cat` no cambió: sigue determinando contrato, color, orden y compatibilidad. `seccion` es un dato de
presentación producido por `jam/ribbon.py`; no entra en el JSON de un grafo ni en los presets. Los
ids persistentes `JamDashBar`, `JamGraph` y `JamContent` tampoco cambian, por lo que no se borra el
layout del usuario.

Las funciones dinámicas publican `seccion: Funciones`; el parser C++ conserva un fallback a `cat`
para specs viejos. Un test puro exige que toda categoría pertenezca exactamente a una familia, que
la fila principal no supere siete entradas y que el C++ mantenga filas separadas para familia y
categoría. La mutación deliberada de `seccion` en el parser puso rojo ese contrato.

## Verificación

- 552 tests puros verdes.
- C++ compilado y enlazado contra UE 5.8.1.
- El editor real cargó el módulo y Graph abrió/cerró sin crash; el cierre liberó captor `sí → no`.
- Falta la evaluación humana de densidad, nombres y orden de las seis familias.

No se declara terminado hasta confirmar con gestos: cambiar entre familias, entrar a
**Datos → Maths**, crear un nodo y volver a otra categoría sin perder el grafo.
