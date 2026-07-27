---
title: "Oráculo de forma: comparar contra la malla de referencia"
aliases:
  - "Compare to Reference"
  - "Oráculo de forma"
  - "Perfil de masa por altura"
tags:
  - jam
  - oraculo
  - graph
  - treegen
  - verificacion
status: implementado
date: 2026-07-27
---

# Oráculo de forma: comparar contra la malla de referencia

## De dónde sale

Brian: «funciona, pero no genera el árbol que está en TreeGen. ¿Cómo verificamos dónde está el
error?». Mirar y opinar no escala. Hacía falta medir.

El hallazgo que lo hizo posible: **TreeGen distribuye sus árboles YA horneados** como StaticMesh en
`/TreeGen/Examples/` (`Pine`, `Birch`, `Bamboo`, `BirchBig`, `PalmTree_*`). No hay que reconstruir el
Blueprint para tener una verdad de referencia: viene en la caja.

```text
Pine       tris=25268   verts=18424   secciones=2   alto=3574cm
Birch      tris=20360   verts=13482   secciones=3   alto=1372cm
Bamboo     tris=26798   verts=17630   secciones=2   alto=1235cm
BirchBig   tris=181824  verts=121239  secciones=3   alto=1306cm
```

Y los slots de material dicen qué son esas secciones:

```text
Pine   slot 0: M_Pine     slot 1: M_PineFrond
Birch  slot 0: M_Birch    slot 1: M_BirchPeel   slot 2: M_Leaves
```

**El follaje de TreeGen está horneado DENTRO de la malla del árbol**, como una sección de material
más. Esa fue la primera divergencia estructural encontrada, y explicaba buena parte del «no se
parece».

## El verbo `Compare to Reference` `M + A → M`

Tab **Mesh**. Consume la malla, exige un StaticMesh de referencia por el pin lateral `asset`, y
**deja pasar la malla intacta**: es un oráculo, no un transformador. Se intercala antes de
`Mesh to Static` para que el mismo Run que construye el árbol diga cuánto se parece al de referencia.

Mide seis cosas y las ordena por gravedad, de modo que lo primero que se lee es lo que más separa a
las dos mallas:

| Métrica | Tolerancia por defecto | Por qué |
|---|---|---|
| `alto` | ±30% | tamaño general |
| `ancho` | ±35% | la copa abre más o menos |
| `vertices` | ±50% | densidad de geometría |
| `triangulos` | ±50% | idem |
| `secciones` | **exacta** | una sección menos = falta un material entero |
| `perfil` | distancia ≤ 0.15 | **la que más discrimina** |

`secciones` no admite tolerancia a propósito: en un árbol, una sección de menos suele significar que
falta todo el follaje.

### El perfil de masa es lo que localiza el error

El conteo de vértices dice *cuánta* geometría hay; el perfil dice **dónde**. Se reparte la malla en
franjas de altura y se mide qué fracción de los vértices cae en cada una. Está normalizado por altura
relativa, así que compara FORMA y no tamaño: dos árboles de escalas distintas con la misma silueta dan
el mismo perfil.

La distancia entre perfiles es la variación total (0 = misma silueta, 1 = disjuntos).

## Arquitectura

Fiel al desacople del cerebro:

- `Content/Python/jam/compare.py` — **puro**, cero Unreal. Recibe posiciones de vértices y conteos,
  produce una `Medida` y el diff. Es lo que se prueba headless.
- `Content/Python/jam/mesh.py` — el adaptador: `medir()` y `comparar()`. Lee una `DynamicMesh` del
  grafo o una `StaticMesh` de Content **con la misma regla**, copiando el asset a una DynamicMesh
  antes de medir. Eso garantiza que la comparación sea manzana con manzana.
- `Content/Python/jam/tools.py` — el verbo `mesh_compare`.

Gotchas de la API de Geometry Script, encontrados con [[TreeGen - UV materiales sections y salida HISM|el verificador de nombres]]:

- `get_all_vertex_positions(mesh, skip_gaps)` toma **2** argumentos y devuelve
  `(mesh, position_list, has_gaps)`;
- `position_list` es un `GeometryScriptVectorList` que **no es iterable**: hay que pedirle
  `convert_vector_list_to_array()`.

## El lazo cerrado, con números

Primera medición del árbol de dos niveles contra el Pine:

```text
✗ alto              690 vs     3574  (0.19×)
✗ ancho             668 vs     1329  (0.50×)
✗ perfil        distancia 0.301 (límite 0.15)
✓ vertices         9234 vs    18424  (0.50×)
✓ triangulos      13946 vs    25268  (0.55×)
✓ secciones           2 vs        2  (1.00×)

masa por franja (base → copa):
  generada       0%    0%    2%   16%   22%   25%   29%    6%
  referencia     7%   10%   16%   16%   16%   17%   18%    1%
```

El perfil dijo exactamente dónde: **cero masa en las tres franjas de abajo**. El tronco aportaba 228
vértices de 9234 y las ramas arrancaban al 18% de su altura, así que todo el árbol vivía arriba.

Ajustes guiados por esa lectura: tronco 5× más alto, más grueso y con más resolución de barrido; ramas
arrancando al 8% en vez del 18%; 26 ramas madre en vez de 12; ramas y ramitas más largas.

```text
✓ ancho             966 vs     1329  (0.73×)
✓ perfil        distancia 0.123 (límite 0.15)
✓ vertices        16473 vs    18424  (0.89×)
✓ alto             3313 vs     3574  (0.93×)
✓ triangulos      25055 vs    25268  (0.99×)
✓ secciones           2 vs        2  (1.00×)

masa por franja (base → copa):
  generada       0%    6%   17%   20%   16%   16%   17%    7%
  referencia     7%   10%   16%   16%   16%   17%   18%    1%
```

Las seis métricas dentro de tolerancia. **Ese es el lazo que faltaba**: de «no se parece» a un número
por eje, y del número al parámetro que hay que mover.

### Lo que el perfil todavía marca

- Franja 0: **0% vs 7%**. TreeGen le cuelga `Leaf` al **tronco** directamente, no sólo a las ramas
  (`Pino: Trunk → Branch(64) → Leaf(PineFrond), más Leaf sobre Trunk`). Jam todavía no lo hace.
- Franja 7: 7% vs 1%. La copa de Jam es más pesada; TreeGen afina más hacia la punta.

Ninguna de las dos rompe la tolerancia, pero son las siguientes dos cosas a cerrar si se busca
parecido fino. Falta además `Displace` (TreeGen deforma el radio del tronco sampleando un render
target por UV) y Pivot Painter para viento.

## El ejemplo hace la unión

El ejemplo de dos niveles ahora **hornea el follaje en la malla** como segunda sección, igual que el
Pine original:

```text
trunk_pipe ─┐
branch_pipe ─┼→ merge → color → uv → material(madera) ─┐
twig_pipe   ─┘                                          ├→ tree_merge → normals → Static → Place
Choose Asset → Copy Variants → color → material(fronda)┘
```

Los dos materiales son distintos a propósito (`VertexColorMaterial` para la madera, `M_PineFrond` para
el follaje), que es lo que produce las dos sections reales.

Las **dos** salidas de follaje quedan demostradas y probadas, una en cada ejemplo:

| Ejemplo | Follaje | Equivale a |
|---|---|---|
| dos niveles | horneado en la malla (`Copy Variants → M`) | `Leaf` con `RenderInstances=false` |
| un nivel | actor instanciado (`HISM Output → H`) | `Leaf` con `RenderInstances=true` |

TreeGen tiene ese mismo toggle por cada `Leaf`; Jam lo expresa como dos verbos.

## Cómo correrlo contra TreeGen

TreeGen es contenido de 4.24 y no está montado en BotOO. Para medir se armó un proyecto desechable con
una **copia** del plugin (subiéndole `EngineVersion` a 5.7 en la copia; el original quedó intacto) más
Jam, y ahí se corre el grafo y la comparación. No se importó ni se modificó ningún asset de TreeGen.

## Verificación

- Suite Python headless: **116/116** (`test_compare.py` es nuevo con 11).
- El núcleo puro se prueba solo: invariancia de escala del perfil, mallas planas y vacías, ancho por el
  eje más ancho, sección faltante sin tolerancia, orden por gravedad, perfil que detecta masa ausente
  abajo, tolerancias configurables y simetría de la distancia.
- `tools/check_unreal_api.py`: **50 llamadas, todas existen** en UE 5.7.4.
- Corrida real en Unreal 5.7.4 con TreeGen montado: 30 nodos, 0 en error, y el diff de arriba.

## Archivos principales

- `Content/Python/jam/compare.py`: núcleo puro del oráculo.
- `Content/Python/jam/mesh.py`: `medir()`, `comparar()`, `_posiciones()`, `_secciones()`.
- `Content/Python/jam/tools.py`: verbo `mesh_compare`.
- `Resources/Examples/TreeGen-Two-Level.jamgraph`: la unión + parámetros ajustados por el oráculo.
- `Content/Python/tests/test_compare.py`: regresiones puras.

## Relacionado

- [[TreeGen - ejemplo de dos niveles y presets de Graph]]
- [[TreeGen - UV materiales sections y salida HISM]]
- [[TreeGen - auditoria de Blueprints funciones y flow real]]
- [[TreeGen - Asset Set Choose Asset y Copy Variants]]
