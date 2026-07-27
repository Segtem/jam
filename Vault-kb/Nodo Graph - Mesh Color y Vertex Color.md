---
title: "Nodo Graph: Mesh Color y Vertex Color"
date: 2026-07-26
status: implementado-mvp
area: Jam/Graph/GeometryScript
tags:
  - jam
  - graph
  - mesh
  - vertex-color
  - material
---

# Nodo Graph: Mesh Color y Vertex Color

## Resultado

Se agregó `Mesh Color`, un operador no destructivo `M → M` que permite distinguir partes de una malla
procedural antes de combinarlas. El ejemplo TreeGen usa marrón `#70452A` para tronco/ramas y verde
`#3F7D3B` para las copas.

```text
Pipes ──→ Merge madera ──→ Mesh Color #70452A ──┐
                                                   ├─→ Merge final → Normals → To Static
Copas ──→ Merge follaje ─→ Mesh Color #3F7D3B ──┘
```

## Contrato

- Entrada y salida: `M` (`unreal.DynamicMesh`).
- Formatos aceptados: `#RRGGBB` y `#RRGGBBAA`.
- El texto hexadecimal representa sRGB; Jam lo convierte a lineal.
- Se clona la entrada antes de escribir, para no colorear otras ramas que compartan el mismo origen.
- Geometry Script almacena el dato en el overlay primario de Vertex Color.
- `Transform`, `Merge` y `Normals` preservan el overlay.
- Un valor inválido detiene ese nodo con un error claro de formato.

## Por qué también cambió Mesh to Static

El Vertex Color es sólo un atributo. El material gris por defecto no lo consulta, así que escribir el
overlay sin cambiar material no produce un cambio visible.

`Mesh to Static` ahora:

1. consulta si la malla tiene un conjunto de colores válido;
2. convierte la malla a `StaticMesh` como antes;
3. si `show_vertex_colors=True`, asigna el material lit de Engine
   `/Engine/EngineDebugMaterials/VertexColorMaterial`;
4. guarda el asset dentro de la misma transacción Preview/Bake/Discard.

Las mallas sin Vertex Color conservan su comportamiento anterior. `show_vertex_colors=False` permite
evitar la asignación automática si se piensa aplicar otro material manualmente.

## Validación

- Suite Python: **50/50 OK**.
- Caso unitario: clonación, parseo de hex, conversión sRGB→lineal y asignación de material.
- Ejemplo TreeGen: **24/24 nodos `ok`** en Unreal Engine 5.7.4.
- El StaticMesh baked reportó como material:
  `/Engine/EngineDebugMaterials/VertexColorMaterial.VertexColorMaterial`.
- Un segundo Run seguido de Discard conservó actor y asset baked.

El editor emitió el fallo de memoria ya conocido al cerrarse, después de imprimir resultados, limpiar
la prueba y ejecutar `QUIT_EDITOR`; no ocurrió durante la evaluación del Graph.

## Alcance y siguiente mejora

Este material de Engine sirve para el MVP y es lit, pero continúa siendo un recurso de diagnóstico. La
siguiente versión debería incluir un material maestro propio de Jam, cookable y parametrizable
(roughness, especular y quizá tint), además de un selector visual de color en el nodo. Para corteza y
hojas reales también hacen falta UV y material slots; Vertex Color puede quedar como máscara, tint o
datos de viento.

## Archivos

- `Content/Python/jam/mesh.py`: parseo, escritura del overlay y material de visualización.
- `Content/Python/jam/tools.py`: nodo, spec y tipado `M→M`.
- `Resources/Examples/TreeGen-Branched-Tree.jamgraph`: madera/follaje coloreados.
- `Resources/Icons/Lucide/icon-map.json`: icono `palette`.
- `Content/Python/tests/test_mesh.py`: regresiones.

## Relacionado

- [[TreeGen - curvas Pipe y arbol ramificado]]
- [[Graph - tab Mesh y verbos de malla procedural]]
