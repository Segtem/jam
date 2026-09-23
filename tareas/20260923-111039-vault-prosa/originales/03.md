---
title: "Ejemplo Graph: pino procedural TreeGen"
tipo: GUIA
version: "1.0"
date: 2026-07-26
updated: 2026-07-26
status: implementado
area: 02-TreeGen
tags:
  - jam
  - graph
  - treegen
  - dynamic-mesh
  - ejemplo
---

# Ejemplo Graph: pino procedural TreeGen

## Resultado

Se agregó un diagrama editable que construye un pino low-poly con los verbos genéricos del tab Mesh.
No replica el Blueprint de TreeGen: demuestra que Jam ya puede expresar la misma clase básica de tubería
procedural, componer piezas de geometría y producir un asset.

Archivo distribuido:

```text
Resources/Examples/TreeGen-Stylized-Pine.jamgraph
```

También puede abrirse directamente desde:

```text
Jam Graph → File → Abrir ejemplo: pino procedural
```

Se carga como una plantilla sin ruta activa. Si se elige Guardar, Jam pregunta dónde escribir una copia
y nunca modifica el ejemplo instalado dentro del plugin.

## Diagrama

```text
Mesh Cone (tronco) ────────────────────────────────┐
                                                   │
Mesh Cone (copa baja)  → Mesh Transform (Z 190) ──┤
                                                   ├→ Mesh Merge
Mesh Cone (copa media) → Mesh Transform (Z 360) ──┤       │
                                                   │       ▼
Mesh Cone (copa alta)  → Mesh Transform (Z 510) ──┘  Mesh Normals
                                                           │
                                                           ▼
                                                    Mesh to Static
                                                           │
                                                           ▼
                                                         Place
```

- 11 nodos.
- 10 conexiones tipadas.
- 4 entradas `M` en el nodo variádico `Mesh Merge`.
- Tronco troncocónico de 600 cm.
- Tres conos superpuestos para una copa de pino estilizada.
- Resultado aproximado: 460 × 460 × 750 cm.
- Asset final: `/Game/Jam/Meshes/SM_TreeGen_Pine_Test`.
- Instancia colocada en `(0, 0, 0)`.

## Cómo probarlo

1. Reiniciar Unreal para cargar la nueva compilación del plugin.
2. Abrir **Jam: Graph**.
3. Elegir **File → Abrir ejemplo: pino procedural**.
4. Ejecutar **Solution → Compile / Validate**.
5. Ejecutar **Solution → Run graph**.
6. Seleccionar el actor `prev_...` del Outliner y pulsar `F` para encuadrarlo.
7. Elegir **Bake / Confirm Preview** para conservar el árbol y el `StaticMesh`, o **Discard Preview**
   para eliminarlos.

Después de Bake, volver a ejecutar el mismo diagrama crea otro árbol en el mismo origen. El nodo Place
puede mostrar warning por superposición con el árbol baked; es el oráculo funcionando correctamente.
Para mantener ambos, cambiar `x` o `y` en el nodo Place antes del segundo Run.

## Hallazgo durante la validación

El ejemplo reveló que `Mesh Transform` construía `unreal.Rotator` con argumentos posicionales. La API de
Python usa un orden diferente al de los campos visuales `pitch/yaw/roll`, por lo que un valor de yaw
podía terminar inclinando la pieza. Se cambió a argumentos nombrados y se agregó una regresión unitaria.

Después de la corrección, las cotas reales del asset fueron:

```text
min Z = 0 cm
max Z = 750 cm
extent X/Y = 230 cm
```

## Verificación

- Suite Python headless: **46/46 tests OK**.
- Los 11 nodos terminaron en estado `ok` durante el primer Run real en UE 5.7.4.
- Se creó un actor Preview y un `StaticMesh` temporal.
- Bake promovió el asset y reasignó correctamente el `StaticMeshComponent` del actor a la ruta final.
- Un segundo Run + Discard conservó tanto el asset como el actor baked.
- Los assets y actores utilizados por la prueba se limpiaron al finalizar.
- `BuildPlugin` Linux: **BUILD SUCCESSFUL**.
- El paquete final contiene el `.jamgraph` dentro de `Resources/Examples`.

## Relacionado

- [[2026-07-26-INFORME-Graph-Tab-Mesh-Verbos-Malla-v1.0|Tab Mesh y verbos de malla]]
- [[2026-07-26-INFORME-Nodo-Convert-To-Nanite-v1.0|Nodo: Convert to Nanite]]
- [[2026-07-26-PLAN-Preview-Transaccional-Efectos-PCG-v1.0|Preview transaccional y efectos de PCG]]
