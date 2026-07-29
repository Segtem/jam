---
title: "TreeGen: curvas, Pipe y árbol ramificado"
tipo: INFORME
version: "1.0"
date: 2026-07-26
updated: 2026-07-26
status: implementado-historico
superseded_by: "[[2026-07-26-INFORME-TreeGen-Replica-Jerarquica-Branch-Leaf-v1.0|TreeGen: réplica jerárquica de Branch y Leaf]]"
area: 02-TreeGen
tags:
  - jam
  - graph
  - treegen
  - spline
  - sweep
  - procedural-mesh
---

# TreeGen: curvas, Pipe y árbol ramificado

> [!info] Evolución posterior
> `CurvePath`, `Pipe` y `Curve Child` siguen vigentes, pero el diagrama de 3 ramas y 288 planes ya no
> es el ejemplo actual. Jam ahora transporta listas por `S` y replica `Trunk → Branch → Leaf` con
> `Curve Branches` y `Mesh Leaf`. Ver [[2026-07-26-INFORME-TreeGen-Replica-Jerarquica-Branch-Leaf-v1.0|TreeGen: réplica jerárquica de Branch y Leaf]].

## Resultado

Jam ya puede construir un árbol coloreado con tronco y ramas curvas reales, no sólo aproximarlo
apilando conos.
La implementación sigue siendo general: se agregaron verbos de curva y barrido que también sirven para
cables, raíces, tuberías, cuernos, caminos volumétricos y piezas arquitectónicas.

Ejemplo incluido:

```text
Resources/Examples/TreeGen-Branched-Tree.jamgraph
```

Acceso desde la interfaz:

```text
Jam Graph → File → Abrir ejemplo: árbol ramificado TreeGen
```

## Qué hace TreeGen internamente

La inspección de los Blueprints `Trunk.uasset` y `Branch.uasset` muestra esta tubería:

1. Obtiene el largo de una spline.
2. La recorre mediante `Length Segments` y consulta un transform a cada distancia.
3. Para cada muestra recorre `Radius Segments` y calcula los vértices del anillo.
4. Reduce `Current Radius` a lo largo de la rama usando escala/curva.
5. Conecta anillos mediante triángulos.
6. Construye UV, vertex colors y datos de Pivot Paint.
7. Calcula normales y tangentes.
8. Las ramas hijas toman un transform de su padre usando distancia normalizada.

El equivalente inicial de Jam cubre los pasos 1–5 y 7 mediante Geometry Script, más un primer contrato
de Vertex Color del paso 6. UV controlados, hojas, materiales de producción y viento quedan para las
siguientes fases.

## Nuevos verbos

### Curve Bezier

```text
— → Curve Bezier → S
```

Genera una curva Bézier cuadrática transitoria mediante inicio, final y un desplazamiento `bend` desde
el punto medio. `segments` controla la resolución. No crea actor ni asset y por el cable viaja un
`CurvePath` liviano.

También se corrigió `Create Spline` para publicar su actor como dato runtime `S`. Por eso esta variante
editable también es válida:

```text
Create Spline (actor editable) → Mesh Pipe
```

### Mesh Pipe

```text
S → Mesh Pipe → M
```

Barre un círculo sobre cualquier curva `S` mediante
`GeometryScript_Primitives.append_simple_swept_polygon`.

Parámetros principales:

- `radius_start` y `radius_end`: taper lineal de base a punta;
- `sides`: resolución radial;
- `samples`: muestreo cuando la entrada es un `SplineComponent` real;
- `capped`: tapas de los extremos;
- `profile_rotation`: orientación inicial del perfil;
- `miter_limit`: límite de corrección en giros cerrados.

El perfil se genera antihorario y Geometry Script crea topología, UV básicos y frames a lo largo del
recorrido.

### Curve Child

```text
S padre → Curve Child → S hija
```

Evalúa posición, tangente y eje exterior a una distancia normalizada `at` de la curva padre. `angle`
abre la rama desde la tangente, `azimuth` la gira alrededor del padre y `bend` curva su control Bézier
en el frame local. La salida puede alimentar otro Child, Pipe o Along Curve sin depender de
coordenadas mundiales.

### Mesh Sphere

```text
— → Mesh Sphere → M
```

Esfera latitude/longitude con resolución configurable. Se usó como volumen de copa en la primera
versión del ejemplo, pero fue retirada al incorporar follaje procedural variable.

### Mesh Color

```text
M → Mesh Color → M
```

Clona la entrada y asigna un Vertex Color constante en formato `#RRGGBB` o `#RRGGBBAA`. El valor se
interpreta como sRGB y se convierte a lineal antes de escribir el overlay de Geometry Script. `Merge`,
`Transform` y `Normals` conservan el atributo, por lo que distintas ramas de entrada pueden mantener
colores diferentes dentro de un único `StaticMesh`.

`Mesh to Static` detecta el overlay y, con `show_vertex_colors=True`, asigna automáticamente el material
lit `/Engine/EngineDebugMaterials/VertexColorMaterial`. Sin un material que lea `Vertex Color`, el dato
existiría pero Unreal seguiría mostrando la superficie gris.

### Mesh From Asset

```text
A → Mesh From Asset → M
```

Extrae el mejor LOD disponible de un `StaticMesh` mediante Geometry Script y lo convierte en geometría
transitoria. Es el puente para usar hojas, piedras, módulos o piezas modeladas dentro de operaciones de
malla sin crear actores intermedios. En este MVP copia geometría y atributos, no su lista de materiales.

### Mesh Along Curve

```text
          Asset A ─┐
Curve S ───────────┴→ Mesh Along Curve → M
```

Muestrea posiciones equidistantes y frames estables sobre `S`, orienta el eje X del asset a la tangente
y su Z hacia el exterior, y agrega todas las copias a una única malla `M`. `radial_offset`, `turns` y
`angle_offset` permiten una distribución helicoidal; `start/end` recortan la zona y
`scale_start/scale_end` producen taper de las copias. `scale_x/y/z`, orientation, jitter y seed agregan
proporción y variación reproducible; `crossed` y `double_sided` permiten tarjetas de follaje visibles
desde cualquier dirección.

El frame evita la singularidad de una tangente vertical y funciona tanto con `CurvePath` como con un
`SplineComponent` editable.

## Diagrama ramificado

```text
Curve Bezier ┬→ Pipe tronco ─────────────────→ Merge madera → Color marrón ─┐
             ├→ 3 × (Curve Child → Pipe) ────┘                              ├→ Merge → Normals → To Static → Place
             └→ 4 × (Curve + Plane A → Along Curve) → Color verde ─────────┘
```

- 21 nodos y 30 conexiones.
- Un tronco y tres curvas hijas `S` dependientes de su frame.
- Cuatro pipes con taper.
- 72 frames con 288 tarjetas de hoja orientadas, cruzadas y doble cara.
- Sin copas elipsoidales provisionales.
- Dos subensambles coloreados que se combinan en el `Mesh Merge` final.
- Asset final: `/Game/Jam/Meshes/SM_TreeGen_Branched_Test`.
- Tamaño real aproximado: 500 × 468 × 660 cm.

## Cómo probarlo

1. Reiniciar Unreal.
2. Abrir **Jam: Graph**.
3. Elegir **File → Abrir ejemplo: árbol ramificado TreeGen**.
4. Ejecutar **Compile / Validate**.
5. Ejecutar **Run graph**.
6. Seleccionar el actor `prev_...` y pulsar `F` en el viewport.
7. Cambiar puntos finales, `bend`, radios o resolución y volver a ejecutar.
8. Usar Bake para conservar `/Game/Jam/Meshes/SM_TreeGen_Branched_Test`.

Un segundo Run después de Bake coloca otra copia en el mismo origen y Place informa warning por
superposición. Cambiar `x/y` del nodo final si se quieren conservar ambas instancias.

## Validación

- Suite Python headless: **57/57 tests OK**.
- Prueba real en Unreal Engine 5.7.4: **20 nodos `ok`, 1 warning informativo y 0 errores**. El warning
  pertenece al nodo Asset porque el Plane de Engine tiene pivote central; no se coloca como actor y no
  afecta las copias de malla.
- Geometry Script creó correctamente los cuatro barridos con taper.
- Los tres nodos `Curve Child` resolvieron sus anclajes desde el tronco y terminaron `ok`.
- `Mesh Along Curve` convirtió y agregó 288 tarjetas sobre 72 frames sin actores intermedios.
- Los colores marrón y verde sobrevivieron composición y normales; el StaticMesh baked quedó enlazado
  al material lit lector de Vertex Color.
- Se creó el `StaticMesh` temporal y un actor Preview.
- Bake promovió el asset y el `StaticMeshComponent` quedó enlazado a la ruta final.
- Otro Run + Discard conservó el asset y actor baked.
- Los actores y assets de prueba se limpiaron al finalizar.
- `BuildPlugin` Linux: **BUILD SUCCESSFUL**.
- El paquete contiene `curve.py`, el diagrama ramificado y el módulo C++ recompilado.

## Diferencias pendientes frente a TreeGen

El ejemplo demuestra el núcleo geométrico, pero todavía no es un reemplazo completo:

- las ramas ya dependen del frame del padre, pero todavía se componen explícitamente con un nodo por
  hija y no existe generación múltiple/recursiva por regla;
- `Mesh Merge` agrega shells, pero no suelda ni hace boolean union en las uniones;
- el taper es lineal y no acepta aún una curva de escala arbitraria;
- faltan proyección UV controlada, material slots y un material Jam de producción; el MVP usa Vertex
  Color y el material de diagnóstico incluido en Engine;
- las hojas ya tienen variación por seed, pero todavía usan una única malla de prueba; faltan selección
  ponderada y material de hoja real;
- falta Pivot Painter o una alternativa para animación de viento;
- faltan niveles de rama automáticos y variación de la propia estructura.

La siguiente vertical slice recomendada es representar conjuntos de curvas/frames y generar varias
hijas con rango, variación y seed. Para combinar libremente `P + M` también conviene ampliar el Graph
a múltiples entradas ricas tipadas; hoy `Mesh Along Curve` recibe `S` como entrada principal y `A` por
su pin Asset, una combinación ya soportada y validada.

## Archivos principales

- `Content/Python/jam/curve.py`: `CurvePath`, Bézier, remuestreo y frames orientados.
- `Content/Python/jam/mesh.py`: Sphere, Pipe, From Asset, Along Curve, Vertex Color y StaticMesh.
- `Content/Python/jam/tools.py`: contratos `S→M`, runtime y specs.
- `Resources/Examples/TreeGen-Branched-Tree.jamgraph`: ejemplo editable.
- `SJamGraphEditor.cpp`: acceso al ejemplo desde File.
- `Content/Python/tests/test_mesh.py`: regresiones de curva, taper y compilación del ejemplo.

## Relacionado

- [[2026-07-26-INFORME-Graph-Tab-Mesh-Verbos-Malla-v1.0|Tab Mesh y verbos de malla]]
- [[2026-07-26-GUIA-Ejemplo-Graph-Pino-Procedural-v1.0|Ejemplo Graph: pino procedural]]
- [[2026-07-26-INFORME-Nodo-Convert-To-Nanite-v1.0|Nodo: Convert to Nanite]]
- [[2026-07-26-INFORME-Nodo-Mesh-Color-Vertex-Color-v1.0|Nodo: Mesh Color y Vertex Color]]
- [[2026-07-26-INFORME-TreeGen-Mesh-From-Asset-Along-Curve-v1.0|TreeGen: Mesh From Asset y Mesh Along Curve]]
- [[2026-07-26-INFORME-TreeGen-Curve-Child-Ramas-Jerarquicas-v1.0|TreeGen: Curve Child]]
- [[2026-07-26-INFORME-TreeGen-Follaje-Procedural-Variacion-v1.0|TreeGen: follaje procedural]]
