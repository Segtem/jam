---
title: "Nanite a Fracture en UE 5.8: Geometry Collection sin perder materiales"
tipo: INFORME
version: "1.0"
date: 2026-08-02
updated: 2026-08-02
status: implementado
area: 03-Mesh-y-materiales
tags:
  - jam
  - nanite
  - fracture
  - dataflow
  - geometry-collection
  - ue-5-8
aliases:
  - Bug Nanite Fracture
  - Materiales de Geometry Collection
---

# Nanite a Fracture en UE 5.8: Geometry Collection sin perder materiales

## Síntoma

El flujo `StaticMesh → Nanite → Fracture` terminaba visualmente como una malla común sin texturas.
Había dos efectos mezclados: Fracture **debe** cambiar el tipo de asset a Geometry Collection, pero
no debe apagar Nanite ni descartar los materiales de la Static Mesh que recibe.

## Causa

`fracture.py` todavía creaba `FStaticMeshToCollectionDataflowNode` y
`FGeometryCollectionTerminalDataflowNode`, deprecados desde 5.6. Sólo conectaba `Collection`; luego
intentaba reparar el aspecto con:

```python
gc.set_editor_property("materials", [m0, m0])
```

Eso conservaba únicamente el primer slot y lo duplicaba. Una malla con varios materiales perdía
todos los demás.

En 5.8 el nodo `FStaticMeshToCollectionDataflowNode_v2` publica `Collection`, `Materials`,
`InstancedMeshes` y `RootProxyMeshes`. El terminal v2 consume esos canales y llama `ResetFrom` con
el array completo de `UMaterialInterface`. Jam estaba omitiendo justamente el canal que el motor
agregó para resolver este contrato.

La segunda omisión era `GeometryCollection.EnableNanite`. Fracture Mode nativo copia ese valor si
alguna Static Mesh fuente usa Nanite; el camino Dataflow de Jam creaba una GC vacía y nunca hacía
esa herencia.

Epic documenta ambas reglas: las Geometry Collections soportan Nanite y éste puede habilitarse en
su editor; además, una GC creada desde una fuente Nanite lo adopta automáticamente. La guía de
Geometry Collections muestra también que los ids de material de la fuente se conservan y se
duplican cuando hacen falta superficies interiores.

- [Nanite Virtualized Geometry — Unreal Engine 5.8](https://dev.epicgames.com/documentation/en-us/unreal-engine/nanite-virtualized-geometry-in-unreal-engine)
- [Chaos Destruction Optimization](https://dev.epicgames.com/documentation/unreal-engine/chaos-destruction-optimization)
- [Geometry Collections User Guide](https://dev.epicgames.com/documentation/en-us/unreal-engine/geometry-collections-user-guide)
- [Unreal Engine 5.8 Release Notes](https://dev.epicgames.com/documentation/unreal-engine/unreal-engine-5-8-release-notes)

## Corrección

- las fuentes sólida y hueca usan `FStaticMeshToCollectionDataflowNode_v2`;
- el terminal es `FGeometryCollectionTerminalDataflowNode_v2`;
- `Materials` llega por cable al terminal, sin asignación manual posterior;
- el camino sólido lleva además `InstancedMeshes` y `RootProxyMeshes`;
- el camino hueco usa un conversor v2 paralelo sólo para recuperar metadata de materiales;
- antes de regenerar, la GC fija `enable_nanite` según los settings de la Static Mesh recibida.

La salida sigue siendo correctamente una **Geometry Collection Nanite**, no una Static Mesh. El
nodo Graph debería comunicar ese cambio de tipo con claridad; convertirla de vuelta a Mesh sería
perder la semántica destructible.

## Verificación

`test_fracture_58.py` ata los dos nodos v2, el cable de materiales y la herencia Nanite. Se probó
que discrimina: al devolver sólo la fuente sólida al nodo deprecado falló `1 != 2`; restaurada la
migración volvió a verde.

`verifica_nanite_fracture_58.py` corrió dentro del editor gráfico 5.8.1. Eligió
`/Engine/EditorMeshes/EditorShaderBall` con tres slots y dos materiales distintos, creó la copia
Nanite, regeneró la GC mediante Dataflow y comprobó:

```text
JAM_NANITE_FRACTURE_TEST TODO VERDE
materiales fuente distintos = 2
materiales GC distintos = 2
enable_nanite de la GC = true
```

Los assets efímeros bajo `/Game/JamVerification/NaniteFracture58` se eliminaron en el `finally`.

## Frontera

La sonda verifica autoría, regeneración, materiales y el flag Nanite; no verifica todavía la imagen
en viewport, la rotura en PIE ni que todos los materiales particulares de BotOO sean compatibles con
Nanite. Después del marcador verde y del cleanup, `quit_editor()` terminó con señal 11 durante el
apagado. Es un rojo de ciclo de vida separado —similar al ya medido en la sonda de Oracle— y no
ocurrió dentro de la conversión o de Dataflow.
