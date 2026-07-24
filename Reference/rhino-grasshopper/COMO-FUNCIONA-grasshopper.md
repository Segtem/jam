# Cómo funciona Rhino / Grasshopper — referencia para Jam

Investigación 2026-07-23. El norte de funcionamiento de Jam es Houdini/Grasshopper; este doc captura
**cómo funciona Grasshopper de verdad** (su modelo de datos y su modelo de componentes) y lo **mapea a
lo que Jam ya tiene y lo que le falta**.

Capturas de la sesión de Rhino 7 del usuario: `rhino7-ui.png` (los 4 viewports + toolbars) y
`rhino7-help-grasshopper.png` (panel de ayuda de GH). El canvas de GH no estaba al frente al capturar.

Fuentes: developer.rhino3d.com (guías de GH), The Grasshopper Primer 3ª ed., ShapeDiver, ETH DDM.

---

## 1. El modelo: dataflow visual

Grasshopper es un **editor de algoritmos visual** integrado en Rhino. Componés un programa colocando
**componentes** (nodos) en un lienzo y conectándolos con **cables** (wires). Por el cable **fluyen
datos**, y cada componente los lee, los transforma y los pasa. No hay bucles explícitos ni variables:
la estructura del grafo ES el programa. (Idéntico modelo a Houdini SOPs.)

Un componente NO procesa un valor: procesa **toda una estructura de datos** de una. Ahí está el corazón
de GH y lo que lo hace potente (y a veces confuso).

## 2. La estructura única: el DATA TREE

> "En Grasshopper hay una sola estructura para guardar datos, y es el data tree."

Todo — un número suelto, una lista, una malla de datos anidada — es un **data tree**. Jerarquía:

- **Item**: un dato suelto (la unidad).
- **List**: colección ordenada de items (mantiene índice).
- **Branch**: una lista guardada bajo una **path** (dirección).
- **Tree**: colección de branches, cada una en su path.

Un item suelto es un tree simplificado (una branch con un item); una lista es una branch con varios.

### Path notation

`{branch_path}[element_index]`. La path son enteros separados por `;` entre llaves; el índice entre
corchetes. Ej: `{0;1}[3]` = branch «0;1», item 3. Ejemplo canónico: dividir **7 curvas** en **24
segmentos** da un tree de **7 branches** (una por curva) × **24 items** (los puntos). La jerarquía
guarda "de qué curva vino cada punto" sin copiar el script.

### Por qué existen los trees

Para hacer **operaciones uno-a-muchos y bucles anidados SIN duplicar el grafo**. Un componente Circle
con **1 plano** y **N radios** produce N círculos: el plano se **difunde** (broadcast) sobre todos los
radios. Sin trees harías un loop por dataset.

## 3. DATA MATCHING (lo más importante para copiar)

Cuando un componente recibe entradas de distinto largo/estructura, las empareja con el **principio de
la lista más larga** (longest-list), repitiendo el último elemento:

- **Item → tree**: un valor solo se difunde a toda la estructura.
- **Lista corta → larga**: la corta repite su ÚLTIMO elemento hasta igualar.
- **Tree → tree**: se alinean replicando la última branch y estirando largos.
- Emparejamiento por índice: 1º con 1º, 2º con 2º…

⇒ **los MISMOS números producen resultados distintos según su estructura de árbol.** La estructura es
información, no sólo contenido.

## 4. Operaciones de árbol (las que todo GH usa)

- **Graft**: cada item pasa a su propia branch. Una branch de 24 puntos → 24 branches de 1. Habilita
  matching diagonal / producto cruzado.
- **Flatten**: fusiona todas las branches en UNA lista; tira la jerarquía.
- **Simplify**: borra los índices de path que no aportan (limpieza tras varias ops).
- **Flip**: intercambia niveles — 7 branches × 24 → 24 branches × 7 (para wireframes perpendiculares).
- **Path Mapper**: remapea paths con constantes (`item_count`, `path_count`, `path_index`).

Se acceden con clic derecho en cualquier salida de cualquier componente (graft/flatten/simplify están
a un clic).

## 5. Modelo de COMPONENTE (SDK) — nuestros nodos SON esto

Desde el SDK (RhinoCommon / GH_Component), un componente:

1. **Hereda de `GH_Component`** — que resuelve conversión de datos, GUI, menús, I/O, errores.
2. **Constructor** (1 vez): nombre, abreviatura (lo que se ve en el nodo), descripción, categoría.
3. **`RegisterInputParams` / `RegisterOutputParams`**: declara los pines con `pManager`.
4. **`SolveInstance(DA)`**: se ejecuta cada vez que hay que recalcular. Lee con
   `DA.GetData/GetDataList(i, ref x)` y escribe con `DA.SetData(i, v)`.
5. **`GH_ParamAccess`**: `item` (SolveInstance corre 1 vez por item — GH itera por vos) · `list` (te dan
   la lista entera) · `tree` (el árbol entero, vos manejás la jerarquía).
6. **`ComponentGuid`**: GUID único por tipo, para serializar en el `.gh/.ghx`. Nunca reusar ni editar.

La clave: con `access = item`, **GH hace el bucle y el data-matching por vos**; el autor sólo escribe la
operación sobre 1 item. Con `tree`, el autor maneja la jerarquía.

## 6. UX del lienzo (convenciones)

- **Doble clic** en el lienzo → **buscador** de componentes (tipear el nombre).
- **Barra espaciadora / clic medio** → **menú radial**.
- **ZUI (Zoomable UI)**: al hacer zoom sobre un componente aparecen +/- para agregar/quitar
  entradas/salidas.
- **Wires**: finos (item), guión-doble (lista), doble (tree) — "fancy wires" muestra la estructura.
- **Estados por color**: normal (gris) · seleccionado (verde) · **warning (naranja)** · **error
  (rojo)**. El color viene de la validez del DATO, no de una acción.
- Preview de geometría on/off; en el viewport: azul=bajo el mouse, verde=componente seleccionado,
  rojo=no seleccionado.

---

## 7. MAPEO A JAM — qué tenemos, qué falta

Jam ya tiene el modelo de dataflow (`jam/flow.py`): por el cable viaja un stream de puntos (`Sample`),
nodos fuente/máscara/instance, orden topológico. Comparado con GH:

| Concepto GH | Jam hoy | Nota |
|---|---|---|
| Dataflow por cables, orden topológico | ✅ `flow.Flow` | igual |
| Nodo = op sobre el stream | ✅ `OPS` (source/mask/merge/instance) | = componentes |
| Estados por color del nodo | ✅ ok/warn/error en el canvas | pero por el ORÁCULO, no por validez de dato — **mejor para nosotros** |
| Buscador al doble clic, ZUI, pan | ✅ (doble clic, zoom, pan) | falta menú radial |
| Fuentes sin pin de entrada | ✅ (`source` en el spec) | igual |
| **DATA TREES (jerarquía + paths)** | ❌ **stream PLANO (`list[Sample]`)** | **la brecha grande** |
| **Data matching (longest-list, broadcast)** | ❌ | derivado de lo anterior |
| Graft / Flatten / Simplify / Flip | ❌ | ops de árbol |
| Access modes (item/list/tree) | parcial: cada op recibe la lista entera (≈ `list`) | no hay `item` con matching automático |

### La conclusión útil

**Jam trabaja con listas planas; Grasshopper con árboles jerárquicos + data matching.** Para el scatter
1D/2D/spline que hacemos hoy, una lista plana ALCANZA — no necesitamos la maquinaria de trees todavía.

Pero la brecha marca el techo: cuando queramos **operaciones anidadas** (p.ej. "por cada edificio, una
tira de ventanas; por cada ventana, sus tornillos") sin duplicar el grafo, vamos a necesitar algo como
los data trees. El camino incremental sería:

1. Darle al `Sample` un **path** (tupla de enteros) además de su seed — hoy es plano `()`.
2. Un nodo **graft** (cada sample a su branch) y **flatten** (todo a una branch).
3. Data matching por índice/branch en los nodos que combinan streams (hoy `merge` sólo concatena).

No hace falta ahora. Se anota como el **norte del modelo de datos** cuando el flow crezca a estructuras
anidadas. Lo que SÍ conviene mantener: nuestro diferencial es que el color del nodo sale del
**oráculo** (¿la creación está bien parada/sin clavarse?), no de la validez del dato — eso GH no lo
tiene.
