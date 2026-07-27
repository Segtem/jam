---
title: "Graph: tab Mesh y verbos de malla procedural"
date: 2026-07-26
status: implementado-mvp
area: Jam/Graph/GeometryScript
tags:
  - jam
  - graph
  - geometry-script
  - dynamic-mesh
  - static-mesh
  - procedural
---

# Graph: tab Mesh y verbos de malla procedural

## Objetivo

Se incorporó al Graph una primera familia de verbos para construir geometría procedural y convertirla
en assets de Unreal. El objetivo es habilitar los mecanismos generales que hacen posible un generador
como TreeGen, no copiar el árbol ni limitar Jam a ese caso de uso.

Flujo mínimo:

```text
Mesh Cylinder (M) → Mesh Normals (M) → Mesh to Static (A) → Nanite (A) → Place
```

Flujo con composición:

```text
Mesh Cylinder ───────────────┐
                            ├→ Mesh Merge → Mesh Normals → Mesh to Static
Mesh Cone → Mesh Transform ─┘
```

## Qué se extrajo de TreeGen

`/home/workstation/Dev/games/unreal/TreeGen` es un plugin content-only para UE 4.24 basado en
`ProceduralMeshComponent`. Sus Blueprints mantienen buffers de vértices, triángulos, UV y colores,
calculan tangentes y crean secciones de malla. La generación del tronco y las ramas se apoya en splines.

La lección reutilizable es la tubería **primitiva/curva → modificación → combinación → normales/tangentes
→ asset**, no el algoritmo específico del árbol. Para Jam se eligió `DynamicMesh` + Geometry Script de
UE 5.7 porque ofrece operaciones de malla de mayor nivel, evita administrar arrays crudos en cada nodo y
permite convertir el resultado directamente en `StaticMesh`.

No se copiaron Blueprints ni assets de TreeGen.

## Nuevo contrato de dato `M`

Los cables `M` transportan un `unreal.DynamicMesh` transitorio durante un Run. Una malla `M`:

- no es un asset de Content;
- no se serializa dentro del archivo del Graph;
- sólo vive durante la evaluación topológica;
- se clona antes de cada modificación para que dos ramas no se muten entre sí;
- no es compatible con un pin `A` hasta pasar por `Mesh to Static`.

El grip y el cable `M` son cyan. El compilador rechaza conexiones `A ↔ M`, entradas `M` desconectadas y
un `Mesh Merge` con menos de dos fuentes.

## Tab Mesh

Los verbos están en una categoría nueva, **Mesh**, y sólo aparecen en la interfaz Graph. Se ocultaron del
Dash tradicional porque allí se ejecutarían aislados, sin poder encadenar el dato transitorio `M`.

| Verbo | Entrada | Salida | Función |
|---|---:|---:|---|
| `Mesh Triangle` | — | `M` | Triángulo equilátero en XY |
| `Mesh Quad` | — | `M` | Plano rectangular mínimo |
| `Mesh Grid` | — | `M` | Plano subdividido por filas y columnas de vértices |
| `Mesh Cylinder` | — | `M` | Cilindro parametrizable y opcionalmente cerrado |
| `Mesh Cone` | — | `M` | Cono o tronco de cono parametrizable |
| `Curve Bezier` | — | `S` | Curva cuadrática transitoria mediante inicio, final y bend |
| `Curve Child` | `S` | `S` | Curva hija anclada y orientada por el frame local del padre |
| `Mesh Sphere` | — | `M` | Esfera latitude/longitude con resolución configurable |
| `Mesh From Asset` | `A` | `M` | Extrae la geometría del mejor LOD de un StaticMesh |
| `Mesh Pipe` | `S` | `M` | Barrido circular sobre curva con taper de radio |
| `Mesh Along Curve` | `S` + Asset `A` | `M` | Copias con orientación, escala, jitter y seed sobre una curva |
| `Mesh Transform` | `M` | `M` | Traslación, rotación y escala no destructivas |
| `Mesh Color` | `M` | `M` | Escribe un Vertex Color hexadecimal preservable por Merge |
| `Mesh Merge` | `M × N` | `M` | Combina dos o más ramas de malla |
| `Mesh Normals` | `M` | `M` | Recalcula normales con pesos por ángulo y/o área |
| `Mesh to Static` | `M` | `A` | Crea un `StaticMesh`, colisión/tangentes y material de Vertex Color |

Cada verbo tiene un icono Lucide y la categoría Mesh usa una identidad teal. `Mesh Merge` es el primer
nodo del Graph con entrada principal variádica real.

## Frontera M → A y ciclo Preview/Bake

Sólo `Mesh to Static` escribe Content. Su ruta final por defecto es:

```text
/Game/Jam/Meshes/SM_<name>
```

Durante `Run graph`, el asset se crea bajo `/Game/JamPreview/graph/PV_<run-id>_...` y se registra en la
misma transacción usada por el resto de Jam:

- `Discard` elimina el `StaticMesh` temporal;
- `Bake` lo promueve a la ruta final;
- un Run posterior crea otro temporal;
- Discard de ese segundo Run conserva el asset ya horneado.

De esta forma los nodos `Nanite`, `Place`, `Scatter` y PCG pueden consumir el resultado como cualquier
otro asset `A`. Una ejecución directa fuera de Preview se niega a sobrescribir un asset final existente.

## Implementación

- `Content/Python/jam/mesh.py`: primitivas, operadores y conversión a `StaticMesh`.
- `Content/Python/jam/tools.py`: registro del tab, ejecución y almacenamiento transitorio de `M`.
- `Content/Python/jam/graph.py`: compilación tipada y propagación de objetos ricos/entradas variádicas.
- `Content/Python/jam/api.py`: el Graph pide el spec completo; el Dash conserva sólo verbos ejecutables
  de forma aislada.
- `Jam.uplugin`: habilita `GeometryScripting`.
- `SJamGraphEditor.cpp`: colores de categoría y dato `M`.
- `Resources/Icons/Lucide/icon-map.json`: iconografía de los verbos.

## Verificación

- Suite Python headless actual: **57/57 tests OK**.
- Validación real con Unreal Engine **5.7.4**:
  - creó un cilindro y un cono;
  - transformó el cono;
  - combinó ambas mallas;
  - recalculó normales;
  - creó y guardó el `StaticMesh` temporal;
  - promovió el asset con Bake;
  - ejecutó otra vez y confirmó que Discard eliminó sólo el nuevo preview;
  - verificó que `/Game/Jam/Meshes/SM_MeshGraphE2E` continuaba existiendo.
- Los assets de la prueba real se eliminaron al finalizar.
- `BuildPlugin` para Linux con Unreal Engine **5.7.4**: **BUILD SUCCESSFUL**; el paquete contiene
  `mesh.py`, el mapa de iconos y `libUnrealEditor-JamEditor.so`.

La instalación local de UE 5.7 emitió su fallo conocido `double free or corruption` durante el cierre,
después de imprimir todos los resultados exitosos y limpiar los assets. El mismo fallo de shutdown ya se
había observado en pruebas independientes del plugin.

## Próximos verbos sugeridos

Esta primera entrega valida el cable `M`, la composición y la creación segura de assets. Para acercarse
a generadores orgánicos/arquitectónicos como los que posibilita TreeGen, la siguiente tanda útil es:

1. Exponer conjuntos de `Curve Frames` y generación múltiple de hijas con variación/seed.
2. Soportar varias entradas ricas tipadas (`P + M`, `S + M`) por nodo.
3. `Taper` y `Bend` como deformadores generales.
4. `Append / Bridge / Weld` con políticas topológicas explícitas.
5. `UV Project` y material slots de producción.
6. `Set Material` antes o después de la conversión a asset.

`Sweep / Pipe`, `Curve Child`, `Set Vertex Color`, `Mesh From Asset` y `Mesh Along Curve` ya forman
parte del MVP. La siguiente combinación de mayor impacto es transportar conjuntos de frames/curvas y
consumirlos sin encapsular todo en un generador monolítico.

## Relacionado

- [[TreeGen - curvas Pipe y arbol ramificado]]
- [[Ejemplo Graph - pino procedural TreeGen]]
- [[Nodo Graph - Convert to Nanite]]
- [[Nodo Graph - Mesh Color y Vertex Color]]
- [[TreeGen - Mesh From Asset y Mesh Along Curve]]
- [[TreeGen - Curve Child y ramas jerarquicas]]
- [[TreeGen - follaje procedural con variacion]]
- [[Tarea - tipado y cardinalidad de conexiones Graph]]
- [[Tarea - Preview transaccional y efectos de PCG]]
- [[Vision y roadmap de producto para Jam]]
