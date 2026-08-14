---
title: "La escalera de Grasshopper Basics como paso de los verbos"
tipo: ROADMAP
version: "1.0"
date: 2026-08-12
updated: 2026-08-12
status: completo
area: 01-Graph
tags:
  - jam
  - graph
  - verbos
  - roadmap
  - grasshopper
---

# La escalera de Grasshopper Basics como paso de los verbos

Brian trajo [An Introduction to Grasshopper](https://baharmon.github.io/basics) (Brendan Harmon, LSU)
y pidió ponerla **en paso para los verbos**, como la Fase 1 de
[[2026-08-02-PLAN-Verbos-Math-Numeros-Vectores-Matrices-v1.0|Math]] fue la escalera de los escalares.

Sirve para eso mejor que el catálogo de los 11 tabs que ya teníamos en
`Reference/rhino-grasshopper/`. Ese cataloga **todo el vocabulario**, que es un mapa; esto es un
**camino**: el orden exacto en que una persona que nunca vio un grafo llega a modelar una superficie.
Un catálogo dice qué falta; una escalera dice **en qué orden importa**, y ese orden no es el nuestro
sino el de alguien que enseña esto hace años.

La escalera es: **punto → línea → polilínea → curva → superficie**. Cada peldaño usa lo del anterior.

## La auditoría, medida contra el registro real

No de memoria: los 200 verbos de `tools.REGISTRO` + `flow.OPS_META` + `math_core.VALORES`.

Esta tabla se mantiene **al día**: es la que se mira para saber qué falta, y una fila desactualizada
manda a construir algo que ya existe.

| peldaño | componente del tutorial | en Jam |
|---|---|---|
| Puntos | Number Slider | ✅ `number` |
| | Panel | ✅ el Inspector |
| | **Construct Point** (x,y,z → punto) | ✅ **es `vector_construct`** — en Jam una posición es un `V` |
| | Boolean Toggle | ✅ `boolean` (peldaño 0) |
| Líneas | **Line** (dos puntos) | ✅ `curve_line` (peldaño 2) |
| | **Line SDL** (origen + dirección + largo) | ✅ `curve_line_sdl` (peldaño 4) |
| | **Unit X / Unit Z** | ✅ `vector_unit_x/y/z` (peldaño 1) |
| | Move | ✅ `curve_move` — ya estaban `move` (puntos) y `mesh_transform` (mallas) |
| Polilíneas | Polyline | ✅ `curve_polyline` |
| | cerrar con Boolean → polígono | ✅ `closed`, cableable desde el interruptor (peldaño 3) |
| Curvas | **Interpolate** (curva que PASA por los puntos) | ✅ `curve_interpolate` (peldaño 5) |
| | Range | ✅ `series_range` |
| | Sine | ✅ `math_sin` (Fase 1 de Math) |
| Superficies | Plane Surface | ≈ `mesh_grid` |
| | Box 2Pt / Center Box | ≈ `mesh_box` (por tamaño, no por dos puntos) |
| | **Boundary Surfaces** | ❌ falta (superficie desde un contorno cerrado) |
| | **Ruled Surface** | ✅ `mesh_loft` con dos curvas (peldaño 6) |
| | **Loft** | ✅ `mesh_loft` con tres o más (peldaño 6) |
| | Extrude | ✅ `mesh_extrude` |

## Lo que la escalera enseña sobre nuestro hueco

Los tres faltantes grandes —Unit X/Z, Line SDL, Loft— **no son verbos sueltos: son un tipo que no
tenemos.** Jam maneja `N` (número), `T` (texto), `B` (booleano), `P` (puntos), `S` (curva), `F`
(frames), `M` (malla), `A` (asset)… y **ningún vector**. Sin `V` no hay dirección que cablear, y sin
dirección no hay Line SDL, ni Move con vector, ni normales manipulables.

Eso coincide exactamente con la **Fase 2 del plan de Math** (vectores y matrices), que quedó
desbloqueada al cerrar la Fase 1. La escalera de Harmon confirma el orden desde afuera: el vector no
es un lujo matemático, es lo que hace falta para dibujar la segunda figura del tutorial.

## Los peldaños, en orden

**0. Interruptor booleano.** ✅ HECHO 2026-08-12. El hueco medido: **43 verbos con 70 parámetros
booleanos y CERO nodos capaces de producir un booleano**. Las comparaciones producían `B` pero no
había de dónde sacar un «sí» constante, así que esos 70 parámetros sólo se tocaban a mano en cada
ficha y nunca se manejaban desde el lienzo. Gotcha que quedó fijado en test: `bool("false")` en
Python es **True** —toda cadena no vacía lo es— y los params viajan como TEXTO, así que un
interruptor apagado se habría leído prendido al abrir un `.jamgraph`, con el nodo dibujándose bien.

**1. El tipo vector `V` y sus constructores.** ✅ HECHO 2026-08-12. Trece verbos: Construir,
Unitario X/Y/Z, Componente X/Y/Z, Sumar, Escalar, Largo, Normalizar, Producto punto y Producto cruz.

**Se decidió TIPO PROPIO y no un `N[]` de tres**, y la razón dejó de ser una opinión al mirar el
código: la compatibilidad del Graph es por **letra exacta** (`graph.py`), así que un tipo propio
**regala la guarda sin escribir nada** — un número o una serie de siete no entran en un pin de
dirección, y el Compile lo dice. Con `N[]` ese error se vería recién en la geometría, a diez nodos
de la causa. Verificado por el camino real: `Compile aceptó un número donde va un vector` es un
rechazo, no un pase.

Lo que hubo que enseñarle al cerebro: `math_core.evaluar` pasaba **todos** los params por `_numero`,
lo cual alcanzaba mientras el único tipo fuera `N`; un vector así se aplasta a float y pierde dos
componentes sin avisar. Ahora cada pin se coacciona según el tipo que **ya declaraba** en `tipos` —
la tabla existía y no se estaba consultando—. El mismo mecanismo va a servir para matrices.

Dos decisiones que quedaron en test: **un número suelto NO es un vector** (`(n,n,n)` y `(n,0,0)` son
las dos lecturas posibles y elegir una en silencio haría que la mitad de las veces apunte a otro
lado) y **el vector cero no tiene dirección que normalizar** (devolver `(0,0,0)` propagaría «para
ningún lado» y la pieza quedaría con su rotación anterior).

El pin tiene color propio en `DataColor`: **índigo**, lejos del azul de `P` — un vector y un stream
de puntos son las dos cosas que más se van a cablear cerca, y distinguirlas por un pelo de tono no
es distinguirlas.

**2. Construir punto y línea.** ✅ HECHO 2026-08-12, y **el peldaño se achicó solo al llegar**. El
tutorial arma la línea con dos «Construct Point»; en Jam **una posición ya es un `V`**, porque el
tipo `P` no es un punto geométrico sino un stream de muestras de colocación —con semilla, escala y
normal por muestra—. Así que el constructor de puntos ya existía con otro nombre
(`vector_construct`) y lo único que faltaba era `curve_line`. Un segmento de largo cero es error y
no una curva degenerada: todo lo que consume `S` —barrer, extruir, distribuir— necesita una
dirección que ahí no existe.

**3. Cerrar la polilínea.** ✅ HECHO. `curve_polyline` tiene `closed`, cableable desde el interruptor
del peldaño 0. **Se repite el primer punto al final en vez de marcar una bandera**: todo lo que
consume `S` recorre la lista de puntos, así que una bandera obligaría a que cada consumidor se
acuerde de cerrar, y el que se olvide deja un polígono abierto por un lado sin que nada lo diga.
Medido por el camino real: 4 puntos / 519,6 cm abierta → 5 puntos / 1039,2 cm cerrada.

**4. Line SDL.** ✅ HECHO. **La dirección se NORMALIZA antes de escalar**, así que el largo pedido es
el largo que sale; sin eso una dirección `(0,0,2)` daría el doble de lo que dice el parámetro y el
error sería invisible —la línea se ve bien, sólo que mide otra cosa—. Queda pendiente `Move` sobre
curvas.

⚠️ **Y estos tres peldaños destaparon un defecto del GRAFO que los 1053 tests puros no veían.** Un
pin de dato OPCIONAL sin cable recibía `None`, y el valor **escrito en la ficha se perdía**: alguien
tipea «0,0,500» en el extremo de una línea, ve el número en el nodo, y el verbo recibe nada. Es el
peor tipo de silencio, porque la interfaz muestra un valor que no se está usando. Ahora un pin
opcional sin cable **usa lo escrito** — que es además cómo funciona Grasshopper: toda entrada se
puede tipear O cablear. Lo encontró la sonda del camino real, no los tests.

**5. Interpolate.** ✅ HECHO 2026-08-12. Curva suave que PASA por los puntos, contra `curve_bezier`
que los usa de control. Quien dibuja el recorrido de un camino quiere lo primero: puso el punto donde
quiere que pase el camino.

**Parametrización centrípeta (`alpha = 0,5`), y la razón está MEDIDA, no citada.** La uniforme —la
versión que aparece primero en cualquier búsqueda— se pasa de largo y hace rulos cuando los puntos
están desparejos, que es exactamente el caso de alguien marcando esquinas a ojo. Comparadas las dos
sobre el caso clásico (dos puntos muy juntos y después un salto largo), con la MISMA rutina y
cambiando una sola variable:

| parametrización | se sale de la caja | retrocesos (rulo) |
|---|---|---|
| uniforme (`alpha=0`) | **2,89 cm** | **11** |
| centrípeta (`alpha=0,5`) | **0,00 cm** | **0** |

Los extremos usan puntos fantasma **reflejados** y no repetidos: repetir da tangente cero y la curva
arranca y termina con una planchada visible. Toma la MISMA entrada que `curve_polyline` a propósito,
para poder cambiar un nodo por el otro sin recablear y ver la diferencia. Medido por el camino real:
las mismas 4 muestras dan `POLYLINE 4 puntos` contra `INTERPOLATE 25 puntos por 4 de control`.

**6. Superficies regladas: Ruled Surface y Loft.** ✅ HECHO 2026-08-12, en **un solo verbo**:
`mesh_loft`, «Tender entre curvas». Grasshopper los separa porque el reglado entre dos curvas es más
barato de resolver en NURBS; en una malla la diferencia desaparece —son las mismas filas de
cuadriláteros— y dos nodos que hacen lo mismo obligan a elegir entre ellos sin ningún criterio. Con
dos curvas es el reglado, con más es el loft. Recibe N cables en el mismo pin (`GRAPH_ARITY = -1`,
como `mesh_merge`), que es la forma en que GH recibe su lista de curvas.

**El winding se IMPORTA de `ribbon_core`, no se reescribe.** Es el código que ya costó un tutorial
invisible y una sesión entera de diagnóstico: si el loft se dibujara con su propia regla podría
quedar dado vuelta sin que nada lo relacione con la cinta. Un test compara las dos superficies cara
por cara sobre la misma geometría.

⚠️ Pero ese test compara **dos buffers nuestros entre sí**: si los dos estuvieran dados vuelta,
seguiría verde. Por eso `verifica_loft_58.py` construye la malla de verdad y se la da a
**`malla.cara_visible`** —la medida que en su primer uso encontró que `mesh_ribbon` entregaba el
winding invertido con 790 tests en verde—. Resultado: **14 caras, acuerdo mínimo +1,000, cero en
rojo**, y la cadena entera de la escalera corriendo de punta a punta (vector → línea → dos curvas →
superficie).

**Dos decisiones más, ambas del patrón «degradar explícito e informar»:**
· Una curva recorrida al REVÉS se endereza sola y se avisa en el reporte (`N curva(s) dadas vuelta`).
Dos curvas trazadas en direcciones distintas son un caso normal, no un error, y pedirle al usuario
que las redibuje sería cobrarle un problema que la herramienta ve sola. Se decide MIDIENDO —si
invertir la segunda acorta los travesaños, van en sentidos opuestos—, no suponiendo.
· **Dos curvas superpuestas son un error**, no una superficie de área cero: cada cuadrilátero sería
un triángulo degenerado y sus normales las decidiría el redondeo. Es el mismo problema que el moño
del bevel, atajado antes de emitirlo.

Y las curvas se remuestrean **por longitud de arco**, no por índice: una de 3 puntos y otra de 40
tienden parejo en vez de amontonar la superficie donde la segunda tenía más detalle.

**El moño del bevel no reapareció acá** porque el loft no hace offset: recibe las curvas ya
trazadas. Sigue esperando en `offset_points`, que es de donde sale.

**7. `Move` sobre curvas.** ✅ HECHO 2026-08-12, y con eso **la escalera está completa**. Jam ya
tenía `move` para puntos y `mesh_transform` para mallas; las curvas quedaban sin forma de correrse
de lugar, así que armar dos rieles paralelos para un loft obligaba a escribir dos veces las mismas
coordenadas con un offset a mano. Conserva la METADATA de cada recorrido —semilla, escala, índices
de TreeGen—: una curva movida sigue siendo la misma curva en otro lado, y perder su semilla haría
que la rama que cuelga de ella salga distinta después de moverla, que es de los efectos más
desconcertantes posibles porque mover no debería cambiar la forma de nada.

## La escalera, corriendo entera

`verifica_loft_58.py` la recorre de punta a punta en un solo grafo, cada peldaño usando el anterior:

    Unitario X → Línea por dirección → Mover curva (con Unitario Z) → Tender entre curvas

Cinco nodos, `MOVE S ✓ — movida 200.0 cm` y `LOFT M ✓ — 14 triángulos · 2 curvas × 8 muestras`. Eso
es exactamente lo que el tutorial de Harmon enseña a hacer en Rhino, hecho con nodos de Jam sobre
mallas de Geometry Script.

## El otro eje: el tab Maths completo, mirando las capturas

Brian pidió además **horas/minutos/segundos, ángulos y matrices**, y mandó a mirar las capturas de
`~/Dev/studies/rhino/`. Mirarlas cambió el plan en dos puntos que el catálogo de texto no mostraba.

**Lo que se ve en `Maths/Trig.png`** (18 componentes): Seno, Coseno, Tangente, sus tres INVERSAS,
las tres recíprocas (Secante, Cosecante, Cotangente), Sinc, Grados, Radianes, y un bloque de
geometría de triángulos (Right/Triangle Trigonometry, Centroide, Circuncentro, Incentro,
Ortocentro). ✅ Hecho 2026-08-12: las tres inversas más **`atan2`**, que es la que de verdad sirve
para apuntar —`atan(y/x)` pierde el cuadrante y explota mirando en vertical—. **Las recíprocas se
saltearon a propósito**: son `1/cos`, `1/sen` y `1/tan`, el grafo ya las escribe con Dividir, y
triplicarían el grupo sin capacidad nueva. El bloque de triángulos es geometría, no aritmética, y va
con los verbos de curva.

**Lo que se ve en `Maths/Time.png`** (8 componentes): Construct Date, Construct Time, Deconstruct
Date, Combine Date & Time, Date Range, Interpolate Date… ✅ Hecho: Armar tiempo + Horas/Minutos/
Segundos de. **Decisión: un tiempo es SEGUNDOS, un `N` común, y no un tipo propio.** Grasshopper
tiene tipo fecha/hora porque modela calendarios —salida del sol, estaciones—; acá lo que se necesita
son DURACIONES (cuánto dura una extracción, cada cuánto rota una patrulla). Un tipo nuevo obligaría a
duplicar sumar, restar, interpolar y comparar; en segundos todo eso ya funciona.

**Lo que se ve en `Maths/Matrix.png`** (7 componentes): Construct, Deconstruct, Display, Invert,
Transpose, Swap Columns, Swap Rows. ✅ **Hecho el 2026-08-14** (once verbos, tipo `MX` propio) — ver
el `## Avance 2026-08-14` al final. Dependía del peldaño 1 (el tipo `V`) y de multi-salida, y las dos
dependencias eran reales: una matriz es el paso siguiente al vector, no anterior.

**Lo que se ve en `Maths/Domain.png`** (16 componentes): Construct/Deconstruct Domain, Bounds,
Divide Domain, Includes, Remap Numbers, y las versiones 2D. ✅ **Hecho el 2026-08-12**: el tipo `D`
con Armar dominio / Desde / Hasta / Largo / ¿Está adentro?, y `math_remap` reescrito para tomar dos
DOMINIOS en vez de cuatro números sueltos (de 5 pines a 3). Jam tenía `math_remap` y
`series_remap` sueltos; GH los tiene apoyados sobre un TIPO dominio, y por eso puede preguntar
«¿este número está adentro?» o «partime este rango en 8». Es el modelo más limpio y vale copiarlo.

## ⚠️ Dos límites del grafo que las capturas dejaron a la vista

> **Los dos cayeron. El 1 entero, el 2 a medias** — ver el `## Avance 2026-08-14` al final. Se dejan
> escritos como estaban porque son el mejor ejemplo de para qué sirve mirar las capturas: los dos
> límites los encontró la comparación con una herramienta ajena, no el uso de la propia.

**1. Ningún verbo de Jam tiene más de una salida.** Medido: los 200 verbos declaran un solo
`out_name`. Todo el patrón **Deconstruct** de Grasshopper —Deconstruct Date, Matrix, Domain, Point,
Vector— es un nodo con VARIAS salidas, y hoy no se puede expresar. Por eso el tiempo se
descompone con tres verbos (`Horas de`, `Minutos de`, `Segundos de`) en vez de uno: es honesto, pero
no escala a matrices, donde nadie va a querer nueve verbos para sacar nueve celdas. **Multi-salida es
una capacidad del grafo, no un verbo que falta**, y bloquea de verdad el peldaño de matrices.

**2. Los nodos de valor no admiten parámetros que no sean números.** `math_core.evaluar` pasa todos
los params por `_numero`, así que un desplegable —«¿qué parte del tiempo querés?»— no se puede
declarar en un nodo de Maths. Es la otra razón por la que el tiempo son tres verbos.

## El eje «vistoso»: el cuerpo del nodo como widget

`Params/Input.png` es la captura que explica el pedido de «nodos más accesibles vistosos». Grasshopper
tiene 25 parámetros de entrada donde **el cuerpo del nodo ES el control**: Number Slider, **Control
Knob** (una perilla), **MD Slider** (un pad 2D), **Digit Scroller**, **Value List**, **Calendar**,
**Clock** (un reloj que se arrastra), Colour Picker/Swatch/Wheel, **Gradient**, **Graph Mapper** (una
curva que se agarra con el mouse), Image Sampler.

Jam hoy dibuja tres controles: spinbox, checkbox y desplegable. Todo lo demás es una fila de texto.
**Esa es la brecha de accesibilidad, y no es de vocabulario sino de Slate**: un nodo «Armar tiempo»
con tres spinboxes dice lo mismo que un reloj arrastrable, pero no se lee de un vistazo.

Y lo mismo vale para el ICONO. Los de Grasshopper son diagramas de la operación —el de Seno es una
onda seno, el de Transponer es la grilla dada vuelta, el de Construct Time es un reloj—, no símbolos
arbitrarios. Los 24 iconos nuevos de este turno siguen esa regla: las inversas dibujan la curva
REFLEJADA, y los cuatro de tiempo son relojes con la manecilla que corresponde.

Orden propuesto para este eje, de más barato a más caro: **Value List** (desplegable con opciones
visibles) → **Digit Scroller** → **Control Knob** → **Gradient** → **MD Slider** → **Graph Mapper**
(Jam ya tiene `graph_curve` como dato; le falta el widget).

## Lo que NO se toma del tutorial

Es de **NURBS**, y Jam produce mallas dinámicas de Geometry Script. Loft y Boundary Surface se van a
implementar como triangulación, no como superficie paramétrica: la escalera aporta el ORDEN y el
vocabulario, no la representación. Anotarlo importa porque «Loft» va a significar algo distinto acá
que en Rhino, y quien venga de Rhino va a esperar lo otro.

Relacionado: [[2026-08-02-PLAN-Verbos-Math-Numeros-Vectores-Matrices-v1.0|verbos de Math]] ·
[[2026-08-03-ROADMAP-Catalogo-Matematico-Ampliado-v1.0|catálogo matemático ampliado]].

## Avance 2026-08-14 — cayeron los dos límites y se cerró el peldaño de matrices

Dos días después de escribir esta escalera, los dos peldaños que quedaban en ❌ están hechos y los
dos límites que las capturas habían dejado a la vista se cerraron —uno entero, el otro a medias—.

**El límite 1 (una sola salida por verbo) cayó entero.** Un verbo puede declarar `outs` además de su
salida principal, y el corte es **aditivo**: un verbo sin `outs` se comporta exactamente como antes.
El detalle vive en [[2026-08-12-PLAN-Multi-Salida-En-El-Graph-v1.0|el plan de multi-salida]], que
además documenta el falso verde que destapó — había **cuatro** rutas que reparten lo que viaja por un
cable y la capacidad se le había enseñado a dos.

**El límite 2 cayó a medias, y la mitad que queda es la que importa menos.** Los nodos de valor **ya
aceptan params que no son números**: `math_core` tiene una tabla `COACCION` y un param puede
declararse `B`, `V`, `D` o `MX`, con coerción desde texto (`"10,20,30"` es un vector válido). Lo que
sigue sin poder declararse en un nodo de valor es un **desplegable** (`opciones`), que las tools sí
tienen. Y esa mitad no se construyó a propósito: sería una capacidad **sin consumidor** — ningún
verbo de Maths necesita hoy un modo. Queda anotado y no construido, que es la regla de esta casa.

**El peldaño de matrices, entonces.** Once verbos en `Maths ▸ Matriz`, tipo `MX` propio y
`matrix_decompose` con cinco salidas. Comparado contra las 7 componentes de `Maths/Matrix.png`:

| Grasshopper | Jam | nota |
|---|---|---|
| Construct Matrix | `matrix_identity` · `matrix_translation` · `matrix_scale_matrix` · `matrix_rotation` | GH arma por celdas; acá se arma por lo que la matriz **significa** |
| Deconstruct Matrix | `matrix_decompose` | cinco salidas: traslación, escala y los tres ejes |
| Invert Matrix | `matrix_inverse` | **se niega** ante una singular, con el motivo adentro |
| Transpose Matrix | `matrix_transpose` | |
| — | `matrix_multiply` · `matrix_determinant` · `matrix_transform_point` · `matrix_transform_direction` | no están en la captura y son los que de verdad se usan |
| Display Matrix | ❌ | es un visor, no aritmética: va con el eje vistoso |
| Swap Columns / Swap Rows | ❌ **a propósito** | son edición por celdas de una matriz vista como grilla; acá una matriz es una transformación |

**Dos desvíos del plan, medidos al implementarlo:**
· **Sólo 4×4, no 3×3.** Un `V` de Jam es 3D, así que una 3×3 sería «la 4×4 sin traslación»: cada
  verbo duplicado sin capacidad nueva. Lo que de verdad da una 3×3 —transformar una dirección
  ignorando la traslación— ya lo da `matrix_transform_direction`.
· **Descomponer da EJES, no ángulos de Euler.** Un trío de ángulos exige fijar un orden de aplicación
  y elegirlo en silencio hace que la mitad de las cadenas oriente para otro lado.

⚠️ **La convención está fijada en un solo lugar** (arriba de `_matriz`, en `math_core.py`):
almacenamiento por FILAS, vectores COLUMNA, traslación en la última COLUMNA, y por lo tanto `a × b`
aplica primero `b`. **Unreal usa la opuesta**, así que la transposición va en `ue.py` — donde todavía
no hay ningún consumidor: las matrices son hoy puro cerebro.

**Del eje vistoso ya cayó el Control Knob** (la perilla de ángulos, con captura del mouse, Shift a 5°
y un solo `Ctrl+Z` por arrastre). Quedan Gradient, MD Slider y Graph Mapper.
