---
title: "TreeGen: auditoría de Blueprints, funciones y flow real"
tipo: INFORME
version: "1.0"
aliases:
  - "TreeGen flow real"
  - "Análisis de código TreeGen"
tags:
  - jam
  - graph
  - treegen
  - blueprint
  - flow
  - procedural-mesh
status: en-implementacion
date: 2026-07-26
updated: 2026-07-27
---

# TreeGen: auditoría de Blueprints, funciones y flow real

## Resultado

Se pudo reconstruir el código y el flujo de TreeGen sin depender de capturas de pantalla. TreeGen es
un plugin content-only de Unreal 4.24: no contiene C++, pero sus `.uasset` conservan los grafos
editoriales de Blueprint.

Para inspeccionarlos se montó el contenido original de sólo lectura en Unreal Engine 5.7 y se compiló
un inspector temporal en `/tmp`. El inspector recorrió directamente `UBlueprint`, `UEdGraph`, nodos,
pins y enlaces. No se guardó ni convirtió ningún asset de TreeGen y no se modificó Jam durante la
extracción.

Se recuperaron **1.769 nodos Blueprint**:

| Blueprint | Grafos | Nodos |
|---|---:|---:|
| `Trunk` | 13 | 362 |
| `Branch` | 11 | 387 |
| `Leaf` | 7 | 296 |
| `TreeParent` | 5 | 65 |
| `Macros` | 3 | 120 |
| `Root` | 15 | 363 |
| `BakeMaster` | 6 | 176 |

## Arquitectura real

TreeGen no pasa sólo una spline de un actor a otro. Cada componente publica un paquete jerárquico de
geometría y metadatos que los hijos vuelven a consumir:

```text
Root
  └─ Components[]
       └─ Trunk
            ├─ Branch
            │    ├─ Branch
            │    │    └─ Leaf
            │    └─ Leaf
            └─ Leaf

cada componente publica:
  ProcMesh + Material
  Ts[] (listas de transforms por objeto padre)
  ParentRadius / PRadius[]
  Pivots[] / Pivot indices / Pivot Paint UV

Root:
  Collate → Group by Material → Offset Triangles → Mesh Sections
          → Pivot Painter textures → ProceduralMesh final
```

`TreeParent.UpdateChildren` recorre `ChildRefs`, asigna `Root`, adjunta el hijo al padre, detecta si es
`Trunk`, `Branch` o `Leaf` y llama a su `Draw`. La evaluación es recursiva y jerárquica, no una lista
plana de actores independientes.

## Contrato común: `TreeParent`

Campos recuperados:

- `Parent`, `Root` y `ChildRefs` para formar la jerarquía;
- `Material` y `ProcMesh` para que `Root` pueda componer el resultado;
- `RandomSeed` compartido;
- `Ts`: arrays de transforms que describen todos los objetos producidos;
- `ParentRadius` y `PRadius` para anclar hijos sobre la superficie y heredar grosor;
- `Pivots`, `PIndex`, `PPIndex`, `PPUVs` y `TotalPivots` para Pivot Painter.

El dato equivalente en Jam no debería ser sólo `CurveSet`. Hace falta un stream de frames con
atributos, por ejemplo:

```text
Frame {
  transform, t, radius, scale,
  parent_index, local_index,
  seed, pivot_index
}
```

## Flujo de `Trunk`

Funciones principales:

| Función | Responsabilidad |
|---|---|
| `Draw` | prepara displacement, resuelve un posible trunk padre, construye datos y actualiza hijos |
| `CreateBaseSegments` | divide la spline uniformemente, obtiene transforms y crea los frames para hijos |
| `DrawRadius` | genera cada anillo radial, vértices, UV, vertex color y triángulos |
| `CreateMeshQuad` | conecta dos anillos mediante dos triángulos por segmento |
| `DrawMesh` | calcula normales/tangentes y crea o actualiza la sección procedural |
| `ClearMeshData` | distingue cambio topológico de simple actualización y reutiliza la sección cuando puede |
| `SetPosition` | interpola una posición normalizada sobre otro trunk padre |
| `Add Branch Child` / `Add Leaf Child` | crea, adjunta, registra y dibuja hijos |

Detalles importantes que Jam todavía no replica:

- `Displace` y `Displace Strength`: TreeGen dibuja una textura a un render target y la samplea por UV
  durante `DrawRadius` para deformar el radio;
- `UV Scale` y `D UV Scale` independientes;
- actualización incremental de la sección si no cambia la cantidad de segmentos;
- `SnapToParentLength`: un trunk también puede ser hijo de otro trunk;
- frames orientados y swizzleados específicamente para que las ramas consuman una base estable.

## Flujo de `Branch`

El orden exacto de `Draw` es:

```text
ClearData
  → Make Branch Data
  → Create Mesh
  → UpdateChildren
```

`Make Branch Data`:

1. Si existe padre, recorre **cada lista de transforms y cada objeto** producido por el padre.
2. Convierte `Parent Range` a posiciones normalizadas.
3. Para cada índice calcula posición, rotación y escala con `RandomStream`.
4. Compone el transform de origen usando el frame del padre, su radio y `Parent Offset`.
5. Registra índices y pivots para mantener la jerarquía.
6. Llama a `AddBranch` para crear la geometría de cada rama.

`AddBranch`:

- elige una longitud entre `Length Min Max` con seed determinista;
- recorre `Length Segments`;
- evalúa `BranchScaleCurve`, no un taper obligatoriamente lineal;
- aplica `Curl` y la macro de rotación `BRotator`;
- genera el transform de cada punto y lo publica en `Ts` para la siguiente generación;
- llama a `DrawRadius` para construir anillos y malla.

Parámetros que forman parte del contrato real:

- `Location`, `Rotation`, `Scale` como valor base más rango de variación vectorial (`VWVar`);
- `Parent Range`, `Parent Offset`, `Spawn Count`;
- `Length Min Max`, `Length Segments`, `Radius Segments`;
- `Rotation Per Index` y `Rotation Along Parent`;
- `Scale/ParentLength`;
- `BranchScaleCurve` y `Curl`;
- `UV Scale`.

`Curve Branches` de Jam ya aproxima distribución, giro, longitud y seed, pero hoy encapsula demasiadas
operaciones y pierde parte del contrato: stream de frames, curva de taper, curl por segmento,
variación vectorial general, UV y metadatos jerárquicos.

## Flujo de `Leaf`

El Blueprint tiene dos rutas de salida distintas:

```text
Meshes[] → 1: ReadMesh
              ↓
parent frames → 2: MakeMeshes
                  ├─ RenderInstances=true  → HISM AddInstance
                  └─ false                 → 2-5: AddMeshToProc → ProceduralMesh
```

### `1: ReadMesh`

Recorre todo `Meshes[]`, usa `GetSectionFromStaticMesh`, guarda vértices, triángulos, UV, normales y
tangentes, y calcula bounds/radio por variante.

### `2: MakeMeshes`

- recorre cada objeto producido por el padre;
- distribuye `Spawn Count` dentro de `Parent Range`;
- compone `Location`, `Rotation` y `Scale` con variación determinista;
- aplica `Rotate Per Index` y un rango `Rotate Along Parent`;
- usa el frame, radio, índice local y escala del padre;
- puede aplicar `Inherit Scale`;
- decide entre una instancia HISM y una copia incorporada a la malla.

### `2-5: AddMeshToProc`

- elige aleatoriamente una variante de `Meshes[]` mediante el `RandomStream`;
- transforma sus vértices al frame calculado;
- corrige los índices de triángulos con el offset acumulado;
- concatena UV, normales, tangentes y vertex colors;
- almacena distancia al padre y datos de Pivot Painter.

Hallazgo decisivo: `Mesh Leaf` de Jam ya acepta una StaticMesh opcional, pero para igualar TreeGen
debe aceptar **varias mallas**, elegir por seed y conservar atributos/materiales. También hace falta un
modo HISM separado del modo de malla horneada.

## Flujo de `Root`

`Root` no es sólo un contenedor. Es el compositor final.

### `Collate and Build`

```text
clear old sections/materials
  → collect unique materials from Components[]
  → Optimise
  → MakeMesh
```

### `Optimise`

- detecta si la cantidad de materiales coincide con las secciones existentes;
- agrupa componentes que comparten material;
- concatena datos por grupo;
- aplica offsets a los triángulos;
- produce una sección por material.

### `MakeMesh`

Calcula tangentes, crea cada `ProceduralMeshSection` y asigna su material correspondiente.

### `Update Pivot Painter`

- cuenta y reindexa pivots de todos los componentes;
- agrega un offset por componente a los índices locales;
- calcula dimensiones de textura elevadas a potencia de dos;
- actualiza el canal UV usado como índice;
- genera render targets de World Position, Forward Vector y corte/índice de componente;
- escribe un píxel por pivot y permite exportar las texturas.

Esto descubre dos ausencias estructurales de Jam: `Mesh Merge` hoy combina geometría, pero no expresa
secciones/material slots; y `Mesh to Static` todavía no tiene un pipeline de atributos jerárquicos para
viento.

## `BakeMaster` no equivale al Bake de Jam

El `BakeMaster` de TreeGen es principalmente un **baker de texturas/impostor**, no la promoción
transaccional Preview → asset definitivo implementada por Jam.

Su construction script:

- calcula bounds del conjunto de actores;
- configura captura ortográfica y spline de contorno;
- crea render targets de diffuse, normal y Roughness/Alpha/Height;
- ajusta profundidad/falloff mediante materiales dinámicos;
- ofrece `ExportTextures`.

Conviene mantener ambos conceptos separados en Jam:

- **Bake Graph**: promueve el resultado procedural a asset persistente;
- **Bake Maps / Impostor**: captura texturas de presentación/LOD.

## Ejemplos recuperados del mapa

El mapa confirma que el mismo sistema compone especies distintas:

```text
Pino:     Trunk → Branch(64) → Leaf(PineFrond), más Leaf sobre Trunk
Abedul:   Trunk → Branch(5) → Branch(5) → Leaf(TreeLeaves), más BirchPeel sobre Trunk
Bambú:    Branch → Leaf(BambooShoot) + Leaf(BambooLeaf variantes) + canopy
Palmera:  Trunk → Leaf(BarkPeel) + dos distribuciones Leaf(PalmFrond)
```

No hay un algoritmo especial por especie: la variedad surge al combinar niveles, rangos, curvas de
escala, transforms y sets de mallas. Este es precisamente el comportamiento que debería poder
expresar Jam Graph.

## Brecha arquitectónica actual de Jam

Jam ya posee un buen conjunto `Flow` para puntos `P` y otro conjunto Graph para `S`, `M` y `A`, pero
son evaluadores separados. `api.run_graph` decide si ejecuta un Flow puro o un JamGraph; hoy no se
puede componer libremente:

```text
Flow P → frames sobre spline S → malla M
```

Además:

- `N` representa escalares, no listas/rangos numéricos;
- `S` puede ocultar un `CurveSet`, pero no expone sus frames/atributos;
- no existe un tipo explícito de frame/transform jerárquico;
- el pin lateral `A` acepta una sola fuente;
- no existe `A[]` para sets de variantes;
- `M` no preserva todavía un contrato completo de material sections/slots.

Agregar más nodos monolíticos sin resolver estos tipos volvería a esconder el flow dentro de cada
verbo. Primero conviene crear el sustrato compartido.

## Nodos propuestos, en prioridad

### P0 — hacer expresable el flow de TreeGen

1. **Curve Frames** `S → F`: samplea transform, `t`, tangent/up, radius e índices.
2. **Range** `N,N,N → N[]`: lista normalizada o en dominio configurable.
3. **Remap / Graph Curve** `N[] → N[]`: falloff editable para taper y distribución.
4. **Distribute Frames** `F → F`: count, parent range, rotate per index y seed.
5. **Transform Frames** `F → F`: location/rotation/scale base más rangos de variación.
6. **Branch From Frames** `F → S`: length range, curl, segments y seed.
7. **Asset Set** `A… → A[]`: entrada variádica de StaticMeshes.
8. **Choose Asset** `A[] + F → A[]/selection`: selección determinista por frame/seed.
9. **Copy Mesh to Frames** `A/A[] + F → M`: modo baked y preservación de atributos.
10. **Pipe with Radius Curve** `S + N[]/curve → M`: reemplaza el taper exclusivamente lineal.

Avance: **Curve Frames**, **Distribute Frames**, **Transform Frames**, **Branch From Frames**,
**Copy Mesh to Frames**, **Asset Set**, **Choose Asset**, **Copy Variants**, **Graph Curve** y
**Pipe with Profile** se implementaron el 2026-07-27 como cortes verticales de los tipos `F`, `A[]`,
`AF` y `N[]`. Véanse
[[2026-07-27-INFORME-TreeGen-Curve-Frames-FrameStream-v1.0|TreeGen: Curve Frames y FrameStream]], [[2026-07-27-INFORME-TreeGen-Distribute-Frames-v1.0|TreeGen: Distribute Frames]] y
[[2026-07-27-INFORME-TreeGen-Transform-Frames-v1.0|TreeGen: Transform Frames]], [[2026-07-27-INFORME-TreeGen-Branch-From-Frames-v1.0|TreeGen: Branch From Frames]] y
[[2026-07-27-INFORME-TreeGen-Copy-Mesh-To-Frames-v1.0|TreeGen: Copy Mesh to Frames]], además de
[[2026-07-27-INFORME-TreeGen-Asset-Set-Choose-Copy-Variants-v1.0|TreeGen: Asset Set, Choose Asset y Copy Variants]] y
[[2026-07-27-INFORME-TreeGen-Curve-N-Array-Pipe-With-Profile-v1.0|TreeGen: Curve N[] y Pipe with Profile]].

`Graph Curve` es la primera versión compacta del bloque `Range/Remap/Graph Curve`: produce una serie
normalizada y editable directamente. `Range` y `Remap` separados siguen siendo útiles como verbos
generales, pero ya no bloquean el taper de TreeGen.

`Curve Branches` y `Mesh Leaf` pueden conservarse como **compounds convenientes** construidos encima
de esos verbos, no como la única forma de generar ramas y follaje.

### P1 — fidelidad de producción

1. **Assign Material / Material Slot**.
2. **Merge by Material / Mesh Sections**.
3. **UV Along Curve** y **UV Scale**.
4. **HISM Output** como alternativa a combinar geometría.
5. **Repeat Branch Level** o compound recursivo para niveles de rama.
6. **Displace by Texture/Field** sobre radio o superficie.
7. **Set/Read Attributes** para `radius`, `parent_index`, `pivot_index`, `weight`, etc.

### P2 — viento, optimización y presentación

1. **Pivot Hierarchy / Pivot Painter Encode**.
2. **Pivot Painter Texture Output**.
3. **Bake Maps**: diffuse, normal, roughness/alpha/height.
4. **Debug Frames**, **Debug Bounds** e **Info Attributes**.
5. LOD/impostor y controles de colisión/Nanite apropiados al resultado.

## Sobre las capturas

No son necesarias para comprender la topología ni las funciones principales: ya se recuperaron los
pins y enlaces. Sí serían útiles como validación visual de intención, especialmente si se quiere copiar
la organización exacta de comentarios y grupos del autor.

Si se toman capturas, las de mayor valor son, en este orden:

1. `Branch → Make Branch Data` completa;
2. `Branch → AddBranch`;
3. `Leaf → 2: MakeMeshes`;
4. `Root → Collate and Build` y `Optimise`;
5. `Root → Update Pivot Painter` sólo cuando se implemente viento.

## Relacionado

- [[2026-07-27-INFORME-TreeGen-Curve-Frames-FrameStream-v1.0|TreeGen: Curve Frames y FrameStream]]
- [[2026-07-27-INFORME-TreeGen-Distribute-Frames-v1.0|TreeGen: Distribute Frames]]
- [[2026-07-27-INFORME-TreeGen-Transform-Frames-v1.0|TreeGen: Transform Frames]]
- [[2026-07-27-INFORME-TreeGen-Branch-From-Frames-v1.0|TreeGen: Branch From Frames]]
- [[2026-07-27-INFORME-TreeGen-Copy-Mesh-To-Frames-v1.0|TreeGen: Copy Mesh to Frames]]
- [[2026-07-27-INFORME-TreeGen-Asset-Set-Choose-Copy-Variants-v1.0|TreeGen: Asset Set, Choose Asset y Copy Variants]]
- [[2026-07-27-INFORME-TreeGen-Curve-N-Array-Pipe-With-Profile-v1.0|TreeGen: Curve N[] y Pipe with Profile]]
- [[2026-07-26-INFORME-TreeGen-Replica-Jerarquica-Branch-Leaf-v1.0|TreeGen: réplica jerárquica de Branch y Leaf]]
- [[2026-07-26-INFORME-TreeGen-Mesh-Leaf-StaticMesh-Opcional-v1.0|TreeGen: Mesh Leaf]]
- [[2026-07-26-INFORME-TreeGen-Curvas-Pipe-Arbol-Ramificado-v1.0|TreeGen: curvas, Pipe y árbol]]
- [[2026-07-26-INFORME-Graph-Tab-Mesh-Verbos-Malla-v1.0|Tab Mesh y verbos de malla]]
- [[2026-07-27-INFORME-Oraculo-De-Forma-Malla-Referencia-v1.0|Oráculo de forma]]
