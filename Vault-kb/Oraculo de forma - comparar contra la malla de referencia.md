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

Mide ocho cosas y las ordena por gravedad, de modo que lo primero que se lee es lo que más separa a
las dos mallas:

| Métrica | Tolerancia por defecto | Por qué |
|---|---|---|
| `alto` | ±30% | tamaño general |
| `ancho` | ±35% | la copa abre más o menos |
| `esbeltez` | ±20% | la **proporción** alto/ancho |
| `vertices` | ±50% | densidad de geometría |
| `triangulos` | ±50% | idem |
| `secciones` | **exacta** | una sección menos = falta un material entero |
| `perfil` | distancia ≤ 0.15 | dónde está la masa a lo alto |
| `silueta` | distancia ≤ 0.18 | el contorno: cono contra cilindro |

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

Las seis métricas de entonces, dentro de tolerancia. **Ese es el lazo que faltaba**: de «no se parece»
a un número por eje, y del número al parámetro que hay que mover. Pero el árbol seguía estando mal —
ver la corrección más abajo, que agregó las dos métricas que faltaban.

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

- Suite Python headless: **128/128** (`test_compare.py` tiene 17).
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

## Corrección 2026-07-27 — el oráculo aprobó y el árbol estaba mal

Con las seis métricas en verde, Brian abrió el editor y miró: un **poste** de 33 metros con muñones
uniformes, no un pino. Un humano lo vio en un segundo; el oráculo no.

Dos agujeros estructurales:

**No había métrica de proporción.** `alto` 0.93× y `ancho` 0.73× pasaban cada uno su tolerancia, pero
la relación alto/ancho daba 3.43 contra 2.69 — 28% más esbelto. La proporción no era ninguna de las
seis, y es lo primero que lee el ojo.

**El perfil vertical no distingue un cono de un cilindro.** Los dos reparten la masa igual a lo largo
del eje. Hay un test que lo demuestra: `cono.perfil == cilindro.perfil`, distancia 0.0. Y esa es
exactamente la diferencia entre un pino y un poste con muñones.

### Las dos métricas nuevas

- **`esbeltez`** = alto/ancho, tolerancia ±20% (más estrecha que alto y ancho por separado).
- **`silueta`** = radio máximo de cada franja respecto del eje, normalizado al mayor. Distancia por
  diferencia media, no variación total: una silueta no es una distribución, no suma 1.

Sobre el mismo árbol que antes daba ✓:

```text
JAM vs TreeGen Pine — ok=False  peor=esbeltez
  ✗ esbeltez         3.43 vs     2.69  (1.28×)
  ✗ silueta       distancia 0.246 (límite 0.18)
  ✓ ancho             966 vs     1329  (0.73×)
  ✓ perfil        distancia 0.123 (límite 0.15)
  ✓ vertices        16473 vs    18424  (0.89×)
  ✓ alto             3313 vs     3574  (0.93×)
  ✓ triangulos      25055 vs    25268  (0.99×)
  ✓ secciones           2 vs        2  (1.00×)

silueta: radio de cada franja, normalizado al mayor:
  generada      41%   84%  100%   88%   91%   82%   86%   71%
  referencia    57%  100%   91%   70%   63%   56%   41%   32%
```

La línea de silueta es el diagnóstico entero: la referencia se angosta monótonamente desde la segunda
franja; la generada se queda ancha hasta arriba.

### La causa de fondo: parámetros absolutos en nodos agnósticos

Los nodos del grafo son agnósticos a propósito — `Branch From Frames` no sabe que hace un árbol. El
costo es que **ningún nodo sabe cómo se ve un árbol**: las relaciones entre niveles tienen que viajar
como datos por los cables.

`branch_from_frames` toma `length_min`/`length_max` en **centímetros absolutos**:

```python
inherited_scale = frame.scale if inherit_scale else 1.0
length = rng.uniform(length_min, length_max) * inherited_scale
```

`inherited_scale` es un factor (~0.82), no el largo del padre. Al subir el tronco 5× para igualar la
altura de la referencia, las ramas quedaron en 324–542cm: **10-16% del tronco, igual abajo que
arriba** (correlación altura↔largo r = −0.41, que es ruido del jitter). Un cilindro de muñones.

TreeGen no tiene el problema porque sus parámetros son **relativos**: `Scale/ParentLength` y
`BranchScaleCurve`. Jam ya tiene el mecanismo —`Graph Curve` produce esa serie `N[]` y
`Pipe with Profile` la consume para el radio— pero no está cableado al largo de las ramas.

**Pendiente**: que `branch_from_frames` acepte un `N[]` por pin lateral para modular el largo a lo
largo del padre, y/o un modo de largo relativo al padre.

### Lección

Esto fue Goodhart, y lo cometió quien escribió el oráculo: los parámetros se ajustaron *leyendo las
métricas*. Un verde no es una garantía, es la ausencia de una refutación — sólo dice que las métricas
que tenés no vieron nada.

El ciclo sano: el oráculo caza lo que ya sabemos mirar, el humano caza lo nuevo, y lo nuevo se
convierte en oráculo. Desarrollado en `docs/Oraculo de Jam - guia completa.md` §9.9.

## Cierre 2026-07-27 — largo relativo al padre y perfil de rama

El arreglo que la corrección anterior dejaba pendiente. `branch_from_frames` gana dos controles:

- **`relative_to_parent`**: interpreta `length_min/max` como FRACCIÓN del largo del padre en vez de
  centímetros. Requiere `CurveFrame.parent_length`, que ahora se propaga por las cuatro etapas
  (`curve_frames` lo siembra desde la curva, `distribute`, `transform` e interpolación lo conservan).
- **`profile` (`N[]`, pin lateral OPCIONAL)**: modula el largo según `frame.parameter`, o sea dónde
  nace el frame sobre el padre. Es el `BranchScaleCurve` de TreeGen y lo que produce la silueta
  cónica.

El Preflight ganó el concepto de **pin de datos opcional** (`optional_data_params`): hasta ahora todo
`data_params` declarado era obligatorio, que es correcto para el perfil de `Pipe with Profile` pero no
para éste, donde no conectar nada significa «sin modulación».

### El resultado, medido

| | antes (absoluto) | ahora (relativo + perfil) |
|---|---|---|
| esbeltez | 3.43 (1.28× ✗) | **2.65** (0.98× ✓) |
| silueta | 0.246 ✗ | **0.098** ✓ |
| ancho | 966 (0.71×) | 1250 (0.94×) |

```text
silueta: radio de cada franja, normalizado al mayor
  generada      30%   90%  100%   78%   70%   46%   47%   34%
  referencia    57%  100%   91%   70%   63%   56%   41%   32%
```

Las ocho métricas en verde.

### La prueba de que el arreglo es estructural

Que las métricas den verde no alcanza —esa fue justamente la lección anterior—, así que hay un test de
**invariancia de proporción**: se construye el mismo árbol con el tronco a 1650 y a 3300 cm y se
comprueba que cada rama se duplique con él, que la proporción media rama/tronco no cambie, y que el
perfil siga afinando de la base a la punta en los dos tamaños.

Con el largo absoluto ese test es imposible de pasar: duplicar el tronco dejaba las ramas donde
estaban. Es la diferencia entre un arreglo y un ajuste de números.

## Corrección 2026-07-27 — el tamaño lo decide el juego, no la referencia

Brian, mirando el árbol en el editor: «sigue siendo enorme». Y tenía razón: 33 metros. El error de
fondo fue **atar el tamaño a la referencia sin preguntar si esa referencia servía**. El Pine de
TreeGen mide 3574cm de verdad (escala 1:1 en su mapa, verificado), y el ajuste se hizo para igualarlo.

Pero las métricas de forma —`esbeltez`, `silueta`, `perfil`— son **invariantes a escala** a propósito.
Sólo `alto` y `ancho` comparan tamaño absoluto. Así que bajar el árbol a ~12 m no cuesta nada de lo
trabajado:

```text
                 33 m        12 m
esbeltez     2.65 ✓      2.45 ✓
silueta      0.098 ✓     0.129 ✓
perfil       0.135 ✓     0.133 ✓
alto/ancho   0.93/0.94   0.34/0.37   ← divergen a propósito
```

La forma sobrevivió intacta al cambio de tamaño. **Ese es el pago del `relative_to_parent`**: se
cambió la altura del tronco y las ramas la siguieron solas.

### `solo_forma`

El oráculo no podía expresar «esta forma, a MI tamaño»: cualquier árbol que no midiera lo mismo que la
referencia quedaba en ✗ para siempre. `mesh_compare` gana `solo_forma`: `alto` y `ancho` se siguen
midiendo y mostrando, pero no juzgan. La proporción y la silueta se siguen exigiendo, así que no es
un cheque en blanco — un árbol estirado sigue fallando aunque se lo mida en modo forma.

### Lo que todavía NO escala solo

El largo de las ramas es relativo al padre, pero **el radio de los pipes sigue en centímetros
absolutos**. Bajar el árbol de 33 a 12 m requirió tocar seis números (altura del tronco, curvatura y
cuatro radios) en vez de uno. El paso siguiente natural es un radio relativo al padre —`ParentRadius`
en TreeGen— o una escala global del grafo.

## Corrección 2026-07-27 — tres defectos que el oráculo no vio

Con el tamaño ya resuelto, las capturas del editor mostraron tres cosas que ninguna de las ocho
métricas marcaba:

1. **El tronco terminaba en un cilindro romo que sobresalía desnudo** por encima del follaje. Era lo
   que más rompía la lectura del árbol.
2. **Las ramas eran caños gruesos y lisos** que se veían atravesando el follaje.
3. **El follaje no llenaba el volumen** que definían las ramas: las puntas quedaban peladas.

### Por qué se le escaparon

El primero es el más interesante. La punta del tronco es **fina y de poca masa**, así que:

- el perfil de masa no la ve (aporta ~0% en su franja);
- la silueta tampoco, porque mide el radio MÁXIMO de la franja, y ahí arriba el máximo lo pone alguna
  rama, no el tronco pelado.

Es decir: un defecto que ocupa un cuarto de la altura del árbol y salta a la vista es invisible para
las dos métricas de forma, porque **es delgado**. Ninguna métrica pregunta «¿hay un tramo donde lo
único que existe es el tronco?».

Los otros dos son de grosor y densidad locales; las métricas actuales son todas globales o por franja.

### Los arreglos

| | antes | ahora |
|---|---|---|
| `trunk_profile.end_value` | 0.24 (romo) | **0.03** (afina a punta) |
| ramas hasta | 0.92 del tronco | **0.95**, y frames hasta 0.99 |
| `branch_pipe.radius` | 8cm | **5cm** |
| `twig_pipe.radius` | 2cm | **1.2cm** |
| follaje por ramita | 3 | **4**, desde 0.25 |

Resultado medido: silueta **0.129 → 0.101**, perfil 0.133 → 0.130, y la franja de la base pasó de 26%
a **71%** de radio (la referencia tiene 57%). El árbol dejó de ser un poste con un penacho.

Quedó en 31.571 triángulos (1.25× la referencia). Una pasada intermedia con follaje 5 se fue a 1.52×
y el oráculo lo marcó, que es exactamente para lo que sirve.

### Lección que se repite

Es el tercer defecto que encuentra el ojo y no las métricas. El patrón ya es claro y vale como
principio: **las métricas cazan lo que alguien ya se tomó el trabajo de formalizar; todo lo demás lo
sigue encontrando quien mira.** Por eso el ciclo no termina — cada hallazgo visual es candidato a
métrica nueva.

Candidata concreta que dejó este episodio: *fracción de la altura donde el radio cae por debajo de un
umbral del máximo* — cazaría el «poste pelado» y cualquier tramo donde sólo exista el eje.

## Relacionado

- [[TreeGen - ejemplo de dos niveles y presets de Graph]]
- [[TreeGen - UV materiales sections y salida HISM]]
- [[TreeGen - auditoria de Blueprints funciones y flow real]]
- [[TreeGen - Asset Set Choose Asset y Copy Variants]]
