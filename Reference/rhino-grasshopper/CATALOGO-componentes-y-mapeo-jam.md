# Catálogo de componentes de Grasshopper + mapeo a Jam

De la biblioteca de estudio del usuario en `~/Dev/studies/rhino/` (84 capturas: los 11 tabs de GH por
sub-panel + interacciones de mouse + 7 tutoriales de "Getting started"). Este doc **cataloga** el
vocabulario de GH y lo **mapea a las herramientas de Jam** — qué ya tenemos, y qué componentes
concretos conviene mirar para crecer. Complementa `COMO-FUNCIONA-grasshopper.md` (el modelo de datos).

Fuente = capturas reales de Grasshopper (Rhino 7) en `~/Dev/studies/rhino/<Tab>/<Panel>.png`.

---

## UX del lienzo (las 3 interacciones de mouse)

- **Botón IZQUIERDO doble clic** (`Left-mouse/Search.png`) → caja «Enter a search keyword…»: el
  buscador de componentes. **Jam ya lo tiene** (doble clic → buscador de nodos).
- **Botón MEDIO** (`Middle-Mouse/`) → **menú radial** con: Bake · Cluster · Enable/Disable ·
  Enable/Disable Preview · Enable/Disable Solver · Find · Group · Navigate · Preferences · Recompute ·
  Zoom. **Jam NO tiene menú radial** — candidato de UX.
- **Botón DERECHO** (`Right-mouse/menu.png`) → menú contextual: Preview On/Off · Enable/Disable ·
  Bake · Zoom · Group · Cluster · Recompute · Lock Solver · Preferences · Navigate · Find.

Acciones clave que Jam podría adoptar: **Group** (agrupar nodos), **Bake** (fijar el resultado del
preview → ≈ nuestro Confirmar), **Disable/Lock Solver** (pausar el recálculo), **Cluster** (colapsar
un subgrafo en un nodo = ≈ guardar un flow como preset/compound, que YA hicimos).

## Los 11 tabs de componentes (el vocabulario completo)

| Tab | Sub-paneles | Qué cubre |
|---|---|---|
| **Params** | Geometry, Primitive, Input, Util | contenedores de datos, sliders, paneles, **Relay** |
| **Maths** | Domain, Matrix, Operators, Polynomials, Script, Time, Trig, Util | aritmética, dominios (remap), **Script** (C#/Python) |
| **Sets** | List, Sequence, Sets, Text, **Tree** | estructuras de datos ← *la brecha de Jam* |
| **Vector** | Point, Vector, Plane, **Grid**, Field | puntos/planos, **grillas y Populate** ← *scatter* |
| **Curve** | Primitive, Spline, **Division**, Analysis, Util | curvas, **división y frames** ← *spline* |
| **Surface** | Primitive, Freeform, SubD, Analysis, Util | superficies |
| **Mesh** | Primitive, Triangulation, Analysis, Util | mallas |
| **Intersect** | Mathematical, Physical, Region, Shape | booleanas, **Region** (dentro/fuera) ← *máscara* |
| **Transform** | Euclidean, Affine, Array, Morph, Util | mover/rotar/escalar, **Array** |
| **Display** | Colour, Dimensions, Graphs, Preview, Vector | visualización |
| **Kangaroo2** | Main, Mesh, Goals-*, Utility | solver físico (relajación) |

## Mapeo directo: primitiva de GH → herramienta de Jam

### scatter ← `Vector/Grid`
`Grid.png` trae: Hexagonal · Radial · Rectangular · Square · Triangular · **Populate 2D** (N puntos
al azar en una región) · **Populate 3D** · **Populate Geometry** (puntos sobre una superficie).
→ **Jam ya cubre lo esencial**: `poisson` (≈ Populate 2D con separación mínima), `grid` (≈
Rectangular/Square), `radial` (≈ Radial). Falta **hexagonal/triangular** como patrones, y **Populate
Geometry** = sembrar sobre una superficie arbitraria (hoy raycasteamos vertical; sembrar sobre una
malla inclinada sería el equivalente).

### spline ← `Curve/Division`
`Division.png` trae: Divide Curve (N) · **Divide Distance** (un punto cada X — *edge-to-edge*) ·
Divide Length · Shatter · **Perp Frames / Horizontal Frames / Curve Frames** (planos orientados a lo
largo de la curva).
→ **Confirma nuestro enfoque**: spline = *Divide Distance* (piezas a su largo real) + *Perp Frames*
(orientar a la tangente). Lo que hicimos es exactamente esa combinación. GH separa "dividir" de
"orientar" en dos componentes; Jam lo hace en uno (`caminar`).

### máscaras ← `Cull` + `Intersect/Region`
En el tutorial `6.png` se ve **Cull** ("Remove exterior points") — filtrar puntos por una condición.
`Intersect/Region` da dentro/fuera de una región. → **Jam ya tiene** `mask_slope/height/noise/density/
circle`. GH las hace con Cull + un patrón booleano; el concepto es idéntico (stream → filtro → stream).

### variación ← `Graph Mapper` (Params) + `Maths/Domain`
En `6.png` el **Graph Mapper** remapea un valor a través de una curva editable (ease, S-curve…), y el
texto dice *"remap your numbers into a fixed domain"*. → Jam varía escala/yaw con RNG uniforme; un
**Graph Mapper** daría control artístico sobre la distribución (p.ej. más piezas chicas que grandes
según una curva). Candidato claro para la variación de scatter.

## La brecha de datos, con nombre y apellido: `Sets/Tree` y `Sets/List`

`Tree.png` (26 componentes): Clean/Graft/Simplify/Trim/Flatten/Prune/Unflatten/Explode **Tree** ·
Entwine · Flip Matrix · **Merge** · Match Tree · Path Mapper · Split Tree · **Stream Filter / Stream
Gate** (ruteo) · Relative Item(s) · Tree Branch/Item · Construct/Deconstruct Path · Replace Paths.

`List.png` (21): Insert/List Item/Partition/Reverse/Sort/Sub/Split List · **Dispatch** (partir por
patrón booleano) · Weave · **Cross Reference** (producto cruzado) · **Longest/Shortest List** (control
de data-matching) · Pick'n'Choose · Sift Pattern · Null handling.

→ **Jam usa listas PLANAS** (`list[Sample]`); todo esto es la maquinaria de **árboles jerárquicos +
data matching** que Jam no tiene (ver `COMO-FUNCIONA-grasshopper.md §7`). No hace falta para
scatter/spline de hoy. Cuando el flow crezca a **estructuras anidadas** (edificio → ventanas →
tornillos), los candidatos mínimos son: **Graft/Flatten**, **Merge** (con matching, hoy sólo
concatena), **Dispatch/Stream Gate** (ruteo condicional), **Longest List** (política de matching).

## Qué de acá vale la pena para Jam (orden de valor)

1. **Nada urgente** — las 3 tools + flow + presets cubren el caso de hoy; GH confirma el enfoque.
2. **UX barata**: menú radial (botón medio), **Group** de nodos, y **Bake** ya lo tenemos como Confirmar.
3. **Cuando haya estructuras anidadas**: `path` en el `Sample` + nodos Graft/Flatten/Merge-con-matching.
4. **Expresividad**: un nodo **Graph Mapper** para la variación (curva editable de escala/densidad).
5. **Populate Geometry** / patrones hex-triangular si el scatter necesita más variedad de siembra.

El diferencial de Jam sigue firme y GH no lo tiene: **el color/estado del nodo sale del ORÁCULO**
(¿la creación está bien parada, apoyada, sin clavarse?), no de la validez del dato.
