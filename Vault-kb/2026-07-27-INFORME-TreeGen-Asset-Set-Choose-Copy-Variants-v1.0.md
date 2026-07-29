---
title: "TreeGen: Asset Set, Choose Asset y Copy Variants"
tipo: INFORME
version: "1.0"
aliases:
  - "Asset Set y Choose Asset"
  - "Variantes de assets por frame"
tags:
  - jam
  - graph
  - treegen
  - variants
  - frames
  - static-mesh
status: implementado
date: 2026-07-27
updated: 2026-07-27
---

# TreeGen: Asset Set, Choose Asset y Copy Variants

## Resultado

Se incorporó un flow explícito para elegir distintas Static Meshes por frame:

```text
Asset A ─┐
Asset A ─┴→ Asset Set A[] ──┐
                            ├→ Choose Asset AF → Copy Variants M
Frames F ───────────────────┘
```

Los tres nodos viven en el tab **Mesh**:

- **Asset Set `A… → A[]`** reúne entre 2 y 64 assets. Es variádico y preserva repeticiones: conectar
  dos veces una variante aumenta deliberadamente su peso.
- **Choose Asset `F + A[] → AF`** asocia un asset a cada frame sin generar geometría todavía.
- **Copy Variants `AF → M`** carga cada Static Mesh única una sola vez, aplica su corrección de eje,
  pivot y escala, y combina las copias en una `DynamicMesh`.

## Tipos nuevos y compilación

- `A[]` representa un set ordenado de rutas de assets.
- `AF` representa frames con la variante ya resuelta para cada elemento.
- Slate muestra ambos como pines tipados y con colores propios.
- El compilador ahora admite parámetros laterales de datos tipados, no sólo valores de formulario.
- `Choose Asset` no compila si el pin lateral `assets` está desconectado o recibe otro tipo.
- `Asset Set` no compila con menos de dos entradas ni con cables incompatibles.

Esta infraestructura queda disponible para futuros verbos que necesiten datos auxiliares ricos sin
convertirlos en strings o números.

## Modos de selección

`Choose Asset` ofrece tres políticas:

- `random`: elección pseudoaleatoria reproducible a partir de `seed` y del seed del frame;
- `cycle`: recorre el set por índice local;
- `parent`: mantiene una variante estable por padre.

El mismo graph y el mismo seed siempre producen la misma selección. Cambiar el orden o repetir una
entrada de `Asset Set` cambia explícitamente la distribución.

## Ejemplo TreeGen actualizado

**File → Abrir ejemplo: frames de TreeGen** usa ahora 19 nodos y 20 conexiones. Su follaje combina:

- `/Game/Examples/Meshes/PineFrond.PineFrond`;
- `/Engine/BasicShapes/Plane.Plane`, sólo como segunda variante portable de prueba.

El Plane no pretende ser follaje final: se puede reemplazar por otra fronda sin cambiar el flow.
No se importó ni modificó ningún asset del proyecto TreeGen original.

## Validación real en Unreal 5.7

El ejemplo completo se compiló y ejecutó en `BotOOEditor`:

- Asset Set: **2 assets, 2 únicos**.
- Choose Asset: **18 frames, 2/2 variantes**, modo `random`, seed `3107`.
- Copy Variants: **18 copias**, 699 vértices.
- Ramas: 18 sweeps y 1.386 vértices.
- Árbol final: **2.289 vértices**.
- Static Mesh y actor de preview creados correctamente.
- `Discard` eliminó 1 actor y 1 asset temporal; el `.uasset` no quedó en disco.
- El módulo C++ `JamEditor` recompiló y enlazó correctamente.
- Suite Python: **80/80 pruebas correctas**.

Las pruebas cubren selección determinista, `cycle`, validación de sets, inyección real del pin `A[]`,
errores de conexión y caché de assets únicos durante el copiado.

## Archivos principales

- `Content/Python/jam/variants.py`: contratos `AssetSet` y `FrameAssetSelection`.
- `Content/Python/jam/graph.py`: compilación y runtime de parámetros laterales tipados.
- `Content/Python/jam/mesh.py`: copiado de una o varias plantillas.
- `Content/Python/jam/tools.py`: nodos, spec, pines e iconos.
- `Source/JamEditor/Private/SJamGraphEditor.cpp`: visualización y validación Slate.
- `Resources/Examples/TreeGen-Curve-Frames.jamgraph`: ejemplo editable.
- `Content/Python/tests/test_mesh.py`: regresiones del nuevo flow.

## Cuánto falta en esta etapa TreeGen

El taper no lineal se implementó después de esta nota mediante `Graph Curve N[]` y
`Pipe with Profile`; véase [[2026-07-27-INFORME-TreeGen-Curve-N-Array-Pipe-With-Profile-v1.0|TreeGen: Curve N[] y Pipe with Profile]]. Quedaban dos bloques
funcionales:

1. ~~**Fidelidad de materiales y rendimiento**: UV/material sections y salida HISM.~~ Hecho después de
   esta nota; véase [[2026-07-27-INFORME-TreeGen-UV-Materiales-Sections-HISM-v1.0|TreeGen: UV, materiales, sections y HISM]]. Ese corte también recableó el
   ejemplo: el follaje dejó de fusionarse en la malla y ahora sale por HISM, así que los 19 nodos y 20
   conexiones de arriba quedaron en 21 y 21.
2. ~~**Ejemplo final de dos niveles y presets**: cerrar una réplica editable, documentada y comparable
   con el flow original.~~ Hecho; véase [[2026-07-27-INFORME-TreeGen-Dos-Niveles-Presets-v1.0|TreeGen: ejemplo de dos niveles]].

**Los dos bloques están cerrados**: la etapa TreeGen terminó. Lo que sigue abierto es del Graph en
general, no de TreeGen.

## Relacionado

- [[2026-07-27-INFORME-TreeGen-Auditoria-Blueprints-Flow-Real-v1.0|TreeGen: auditoría de Blueprints y flow real]]
- [[2026-07-27-INFORME-TreeGen-Curve-Frames-FrameStream-v1.0|TreeGen: Curve Frames y FrameStream]]
- [[2026-07-27-INFORME-TreeGen-Transform-Frames-v1.0|TreeGen: Transform Frames]]
- [[2026-07-27-INFORME-TreeGen-Branch-From-Frames-v1.0|TreeGen: Branch From Frames]]
- [[2026-07-27-INFORME-TreeGen-Copy-Mesh-To-Frames-v1.0|TreeGen: Copy Mesh to Frames]]
- [[2026-07-26-INFORME-TreeGen-Replica-Jerarquica-Branch-Leaf-v1.0|TreeGen: réplica jerárquica de Branch y Leaf]]
- [[2026-07-27-INFORME-TreeGen-Curve-N-Array-Pipe-With-Profile-v1.0|TreeGen: Curve N[] y Pipe with Profile]]
- [[2026-07-27-INFORME-TreeGen-UV-Materiales-Sections-HISM-v1.0|TreeGen: UV, materiales, sections y HISM]]
- [[2026-07-27-INFORME-TreeGen-Dos-Niveles-Presets-v1.0|TreeGen: ejemplo de dos niveles]]
