---
title: "Nodos de debug: ver el stream, no sólo medirlo"
aliases:
  - "Debug Frames"
  - "Debug Points"
  - "Ayudantes visuales del Graph"
tags:
  - jam
  - graph
  - debug
  - oraculo
status: implementado
date: 2026-07-27
---

# Nodos de debug: ver el stream, no sólo medirlo

## De dónde sale

Idea de Brian: *«¿podemos incorporar nodos debug? Assets como flecha, ejes, etc.»*

Llena un hueco real y complementario al oráculo. El oráculo **mide** el resultado final contra una
referencia; no deja **ver** lo que pasa a mitad de la cadena. Si los frames apuntan mal, o una máscara
mató los puntos equivocados, no hay forma de darse cuenta hasta que la malla final sale rara — y para
entonces ya no se sabe qué nodo tuvo la culpa.

Es exactamente el patrón que se viene repitiendo: **las métricas cazan lo que alguien formalizó, el
ojo caza lo demás**. Estos nodos le dan al ojo algo que mirar en el medio del grafo.

## Un solo verbo con pin comodín

La primera versión fueron dos verbos tipados (`debug_frames` `F → M` y `debug_points` `P → M`).
Brian, al mirarlo: *«no sé bien en qué nodos se conectan»*. Y tenía razón: el problema no era la
documentación, era el diseño. Un verbo por tipo obliga a saber de antemano cuál usar, y cuantos más
tipos hay peor se pone.

Ahora es **un solo nodo** `Debug` con pin de entrada `*`, un **comodín** que acepta cualquier cable.
Se arrastra y el nodo se da cuenta solo de qué llegó:

| Cable | Qué dibuja |
|---|---|
| `F` frames | ejes de colores: posición, orientación y escala |
| `P` puntos | un cubo por punto, con el peso de la máscara como tamaño |
| `S` curva | el recorrido de cada polilínea, con arranque y punta marcados |
| `N[]` serie | la serie como gráfico, para editar un taper viendo su forma |
| `M` malla | caja envolvente + espinas de normales (delata normales dadas vuelta) |
| `AF` variantes | los frames, coloreados por la variante que les tocó |

Los ejes usan la convención de siempre —la misma que `make_rot_from_xz` al orientar geometría, para
que **lo que se ve sea lo que se orienta**:

```text
X rojo   = tangent   — hacia dónde crece
Y verde  = lateral   — cross(tangent, outward)
Z azul   = outward   — hacia afuera
```

### El comodín en el sistema de tipos

`*` se agregó en los **dos** validadores, porque si no el cable se rechazaba antes de llegar:

- `graph.compilar()`: `if tipo_in != COMODIN and tipo_out != tipo_in`
- `SJamGraphEditor::CanConnect()`: `if (InType != TEXT("*") && OutType != InType)`

Y **no es una amnistía general**: hay un test que comprueba que un `P` conectado a `mesh_pipe` sigue
fallando con `esperaba S, recibió P`. El comodín es del pin de Debug, no del sistema.

Detalles que valen: `escalar_con_dato` hace que el largo de los ejes siga la escala del frame —así se
ve de un vistazo si cae en cascada entre niveles o si la maneja una máscara—, y en los puntos `minimo`
evita que un peso 0 los vuelva invisibles, para distinguir **«la máscara lo apagó»** de **«nunca
estuvo»**, que a ojo son lo mismo y significan cosas muy distintas.

## Cómo probarlo

**File → Abrir ejemplo: banco de pruebas de Debug** (`Debug-Playground.jamgraph`, 19 nodos). Tiene
una fuente de cada tipo, cada una con su nodo `Debug` al lado, y todos los resultados mergeados a una
StaticMesh que se coloca. `Run graph` y se ve todo en el viewport; `Discard` lo borra.

La primera versión los mergeaba directo y **todo se apilaba en el origen**: la serie `N[]` producía
sus 600 vértices y no se distinguía porque quedaba enterrada bajo la esfera y la curva. Cada debug
pasa ahora por un `mesh_transform` que lo corre a su propio carril, 5 m de separación en Y — 23 m de
extensión total. Es la diferencia entre «lo dibujó» y «lo puedo mirar».

Corrido en UE 5.7.4, 18 nodos, 0 errores:

```text
[ver_S·debug] DEBUG M ✓ — 640 verts · S · 16 trazos
[ver_N·debug] DEBUG M ✓ — 600 verts · N[] · 15 trazos
[ver_M·debug] DEBUG M ✓ — 1240 verts · M · 31 trazos
[ver_P·debug] DEBUG M ✓ — 128 verts · P · 16 puntos · peso 0.36→0.76
[ver_F·debug] DEBUG M ✓ — 1920 verts · F · 48 trazos
[juntar·mesh_merge] MERGE M ✓ — 4528 verts
```

El mismo verbo sirviendo cinco tipos en una sola corrida.

Verificado además que las espinas de `M` apuntan **para afuera**: sobre una esfera, las 74 se alejan
del centro. Una normal dada vuelta es justamente lo que este modo tiene que delatar, así que valía
comprobar que el propio ayudante no estuviera mintiendo.

## Rendimiento

`append_mesh_transformed` acepta la **lista entera** de transforms, así que se construye una flecha
unitaria una vez y se estampa N veces en una sola llamada por eje: tres llamadas para cualquier
cantidad de frames, no una por flecha. Tope de 4096 elementos por nodo.

## Arquitectura

- `Content/Python/jam/debug.py` — **puro**: convierte frames en tramos `(origen, dirección, largo,
  eje)` y puntos en marcadores. Es lo que se prueba, y permite afirmar que el eje X **es** la
  tangente sin levantar el motor.
- `Content/Python/jam/mesh.py` — `debug_ejes()` y `debug_puntos()`: estampan la plantilla y pintan
  cada eje con su color.

Un detalle que el núcleo puro resuelve: si `tangent` y `outward` quedan **paralelos**, el producto
cruzado da cero y los ejes serían basura. Se elige una perpendicular estable y hay un test que exige
que los tres sigan siendo ortogonales en ese caso.

## Verificación

Corrido en UE 5.7.4 sobre la cadena Flow → Mesh, 7 nodos, 0 errores:

```text
[peso·weight_noise]   WEIGHT NOISE P ✓ — 9 puntos
[verpts·debug_points] DEBUG P M ✓ — 72 verts · 9 puntos · peso 0.33→0.73
[verfr·debug_frames]  DEBUG F M ✓ — 1080 verts · 9 frames · ejes XYZ
[juntar·mesh_merge]   MERGE M ✓ — 1152 verts
[malla·mesh_to_static] STATIC MESH ✓
```

Suite headless: **166/166** (`test_debug.py` tiene 15).

## Fix — la regla de tipos estaba duplicada

Al abrir el ejemplo, Brian: *«me sale edge 1 tiene pines o tipos incompatibles»*.

El comodín se había agregado en `CanConnect` —el camino que valida un cable **tendido a mano**— pero
`LoadGraphJson`, el que valida al **abrir un archivo**, tenía la misma condición escrita aparte:

```cpp
if (OutType.IsEmpty() || InType.IsEmpty() || OutType != InType)   // sin comodín
```

Resultado: el nodo Debug se conectaba bien arrastrando, pero el ejemplo que lo usaba no se podía
abrir. La UI aceptaba algo que el cargador rechazaba.

El arreglo no fue agregar el comodín en el segundo lugar sino **eliminar la duplicación**:

```cpp
static bool JamTiposCompatibles(const FString& OutType, const FString& InType)
{
    if (OutType.IsEmpty() || InType.IsEmpty()) { return false; }
    return InType == TEXT("*") || OutType == InType;
}
```

Los dos caminos la llaman. Con la regla en un solo lugar el desfasaje no puede volver a pasar.

### El test que faltaba

Ninguna prueba abría los ejemplos: se verificaba que **compilaran** (Preflight de Python), no que se
pudieran **cargar** (validación de Slate). Son dos contratos distintos y sólo uno estaba cubierto.

`EjemplosCargablesTests` recorre los cinco `.jamgraph` distribuidos aplicando los mismos pasos que el
cargador. Verificado por mutación: sacándole el comodín reproduce el error exacto —
`edge 1 peso.out(P) → ver_P.in(*) sería rechazado al abrir`.

## Revisión 2026-07-27 — cómo lo hacen las herramientas de verdad

Brian, sobre el nodo comodín: *«me parece raro un solo nodo y que pueda mostrar para todas»*. Tenía
razón, y la investigación lo confirmó.

### El paradigma dominante: flag por nodo

| Herramienta | Cómo se depura |
|---|---|
| **Houdini** | **display flag** y **template flag** en cada nodo; el que tiene el display flag es el que se ve |
| **Grasshopper** | *preview toggle* por componente, encendido por defecto |
| **Unreal PCG** | flag de debug por nodo, e **Inspect** con la tecla `A` |
| **Substance Designer** | cada nodo muestra su propia salida |

La propiedad que comparten: **no se agrega un nodo para depurar, se prende el nodo que ya está**.
Cero contaminación del grafo, cero recableo.

### La otra mitad: el inspector numérico

Todas tienen un inspector de datos **separado** de la visualización 3D — el *Geometry Spreadsheet* de
Houdini (que sirve, textualmente, para «inspeccionar datos que no tienen visualización»), el
*Spreadsheet Editor* de Blender, el panel de Inspect de PCG.

Y el dato decisivo: el flujo documentado de PCG es **«recorrer desde la entrada hacia adelante y ver
dónde el conteo cae a cero»**. El acto de depurar más común no es mirar geometría, es mirar números.

### Dónde quedaba el nodo comodín

Blender **sí** tiene un Viewer node comodín, así que la idea no era inventada. Pero con dos
diferencias que la salvan: `Shift-Ctrl-click` sobre cualquier nodo lo reconecta al viewer activo —o
sea funciona como **sonda que se mueve**, no como nodo que se coloca y cablea— y viene con el
Spreadsheet al lado. Blender además agregó *Quick Inspection*, que muestra el valor evaluado junto al
socket sin viewer: están convergiendo hacia el flag.

La versión de Jam era la de Blender **sin** el atajo y **sin** el inspector: la peor combinación.

## Lo implementado

### 1. Flag de debug por nodo

Un toggle `○ / ◉` en la esquina de cada nodo, al lado de la ✕. Cuando está prendido, el Run:

- **vuelca los datos de ese nodo al reporte** (la tabla, abajo);
- **dibuja su salida** en la escena.

El flag viaja en el `.jamgraph` (`"debug": true`) y es **opcional**: un archivo viejo sin el campo
carga con el flag apagado.

Nada de esto necesita cables ni nodos extra. Es el display flag de Houdini.

### 2. Tabla de datos en el reporte

`debug.tabla()` —**pura**— vuelca el stream como columnas según su tipo:

```text
[peso·weight_noise] WEIGHT NOISE P ✓ — 9 puntos
    idx                    posición    peso  pendiente
      0  ( -250.0, -250.0,    0.0)   0.597        0.0°
      1  (    0.0, -250.0,    0.0)   0.349        0.0°
    …  y 1 más
```

`F` muestra posición, escala y tangente; `P` posición, peso y pendiente; `N[]` los valores; `S`
puntos, largo y escala; `AF` la variante que le tocó a cada frame. Recorta a 8 filas y dice cuántas
quedaron.

El conteo por nodo —el «dónde cae a cero» de PCG— **ya estaba** en el reporte de todo Run, marcado o
no. Eso no cambió.

### 3. El nodo `debug` se queda, con otro rol

Ya no es *la* forma de depurar, pero sirve para lo que el flag no puede: **componer** la
visualización dentro de una malla que se hornea, coloca o comparte. Un asset de referencia es un caso
real; simplemente no es el gesto de cada día.

## Una regla que salió de esto

**Un flag de debug nunca debe tumbar el Run.** Si el dibujo falla —o si no hay motor, como en la
suite headless— se informa y el grafo sigue:

```text
DEBUG ✗ — no se pudo dibujar: AttributeError: module 'unreal' has no attribute 'DynamicMesh'
```

Hay un test que lo fija. La tabla del reporte no depende del dibujo, así que sigue saliendo igual.

## Verificación

Corrido en UE 5.7.4 con cuatro nodos marcados y **ningún nodo de debug en el grafo**: las cuatro
tablas en el reporte, un solo actor de visualización en escena, 0 errores, y `Discard` se lo llevó.

El actor es un `DynamicMeshActor` —la visualización es transitoria por definición y no tiene por qué
ensuciar Content— y cae dentro del `_preview` que envuelve al Run, así que no hizo falta marcarlo:
la transacción ya captura por diferencia todo actor nuevo.

Suite headless: **174/174**.

## Lo que sigue faltando

- **Inspector por elemento como panel**, con filtro y orden, tipo Geometry Spreadsheet. Hoy la tabla
  vive en el reporte y se recorta a 8 filas.
- **La sonda que se mueve** de Blender (`Shift-Ctrl-click` para reconectar el viewer activo).
- **Selección bidireccional**: en Houdini, seleccionar en el viewport resalta la fila del spreadsheet.

## Relacionado

- [[Puente P a F - las ops de Flow como verbos del Graph]]
- [[Oraculo de forma - comparar contra la malla de referencia]]
