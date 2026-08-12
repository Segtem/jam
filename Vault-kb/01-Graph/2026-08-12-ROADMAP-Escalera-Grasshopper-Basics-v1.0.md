---
title: "La escalera de Grasshopper Basics como paso de los verbos"
tipo: ROADMAP
version: "1.0"
date: 2026-08-12
updated: 2026-08-12
status: en-progreso
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

| peldaño | componente del tutorial | en Jam |
|---|---|---|
| Puntos | Number Slider | ✅ `number` |
| | Panel | ✅ el Inspector |
| | **Construct Point** (x,y,z → punto) | ❌ **falta** |
| | Point / Boolean Toggle (Params) | ⚠️ `boolean` **recién hecho**; falta el contenedor Point |
| Líneas | **Line** (dos puntos) | ⚠️ `pts_line` reparte N puntos sobre el segmento, no lo produce como curva |
| | **Line SDL** (origen + dirección + largo) | ❌ **falta** (y necesita vectores) |
| | **Unit X / Unit Z** | ❌ **falta el TIPO vector** |
| | Move | ⚠️ `move` para puntos, `mesh_transform` para mallas; no para curvas |
| Polilíneas | Polyline | ✅ `curve_polyline` |
| | cerrar con Boolean → polígono | ⚠️ `curve_polyline` **no tiene** parámetro de cierre |
| Curvas | **Interpolate** (curva por puntos de control) | ❌ **falta** — `curve_bezier` es otra cosa |
| | Range | ✅ `series_range` |
| | Sine | ✅ `math_sin` (Fase 1 de Math, 2026-08-12) |
| Superficies | Plane Surface | ≈ `mesh_grid` |
| | Box 2Pt / Center Box | ≈ `mesh_box` (por tamaño, no por dos puntos) |
| | **Boundary Surfaces** | ❌ **falta** |
| | **Ruled Surface** | ❌ **falta** |
| | **Loft** | ❌ **falta** |
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

**2. Construir punto y línea.** `point` (x,y,z → `P` de un punto) y `curve_line` (dos puntos → `S`).
Hoy `pts_line` reparte puntos SOBRE un segmento, que es otra cosa: no se puede cablear el segmento
a nada que espere una curva.

**3. Cerrar la polilínea.** Un parámetro de cierre en `curve_polyline`, cableado desde el
interruptor del peldaño 0 — que es exactamente el gesto del tutorial para hacer un polígono.

**4. Line SDL y Move sobre curvas.** Ya con `V`.

**5. Interpolate.** Curva suave que PASA por los puntos, contra `curve_bezier` que los usa de
control. Son dos cosas distintas y el tutorial enseña la primera; hoy sólo tenemos la segunda.

**6. Superficies regladas: Ruled Surface y Loft.** Dos curvas → malla. Es el paso donde la escalera
se junta con lo que Jam ya hace bien (`mesh_ribbon` es un caso particular de esto), y donde va a
volver a aparecer el moño del bevel de `ribbon_core` si no se resolvió antes.

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
Transpose, Swap Columns, Swap Rows. ❌ Pendiente, y depende del peldaño 1 (el tipo `V`): una matriz
es el paso siguiente al vector, no anterior.

**Lo que se ve en `Maths/Domain.png`** (16 componentes): Construct/Deconstruct Domain, Bounds,
Divide Domain, Includes, Remap Numbers, y las versiones 2D. ❌ Pendiente. Jam tiene `math_remap` y
`series_remap` sueltos; GH los tiene apoyados sobre un TIPO dominio, y por eso puede preguntar
«¿este número está adentro?» o «partime este rango en 8». Es el modelo más limpio y vale copiarlo.

## ⚠️ Dos límites del grafo que las capturas dejaron a la vista

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
