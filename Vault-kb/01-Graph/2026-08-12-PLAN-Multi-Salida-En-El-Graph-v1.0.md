---
title: "Multi-salida en el Graph: el patrón Deconstruct"
tipo: PLAN
version: "1.0"
date: 2026-08-12
updated: 2026-08-12
status: implementado
area: 01-Graph
tags:
  - jam
  - graph
  - arquitectura
  - grasshopper
---

# Multi-salida en el Graph: el patrón Deconstruct

> ✅ **El CEREBRO está hecho** (2026-08-13, commit `0adae42`): declaración, Compile, ejecutor, los
> dos preflight y el spec. `domain_construct` estrena la capacidad con sus dos extremos. 1173 tests,
> 8/8 mutantes muertos, `JAM_MULTISALIDA_58 TODO VERDE` y 19/19 tutoriales.
> ✅ **Y Slate también** (2026-08-13, commit `83cd6bf`): la ficha dibuja **un nub por salida**.
> ✅ **Y el consumidor por el que se hizo todo esto** (2026-08-14, commit `d207caf`): las matrices
> 4×4, con `matrix_decompose` publicando **cinco** salidas. Ver el `## Avance 2026-08-14` al final:
> ahí está el falso verde que destapó, que es lo más importante que dejó este plan.
>
> **Dos correcciones al plan, medidas al implementarlo:**
> · El radio de explosión era MENOR: de los 79 `out_name` del cerebro, **64 son declaraciones** en la
>   tabla de `math_core` y sólo ~15 son consumidores. El corte aditivo no tocó ninguno.
> · Y había un lugar que el plan NO contaba: **`flow.py` valida por su cuenta**, con un preflight
>   paralelo al de `graph.compilar` y su propio `_tipo_salida`. Un grafo de puros nodos de valor
>   entra por ahí. Enseñarle multi-salida a un solo lado dejó el Compile rojo con todos los tests
>   puros en verde, y lo encontró la sonda del camino real.

**Ningún verbo de Jam puede tener más de una salida.** Los 200 declaran un solo `out_name`, y el
compilador rechaza cualquier arista cuyo pin de origen no sea `"out"`. Eso deja afuera todo el patrón
**Deconstruct** de Grasshopper —Deconstruct Date, Matrix, Domain, Point, Vector—, que es un nodo con
varias salidas.

No es un verbo que falta: es una capacidad del grafo. Se chocó **cuatro veces en un solo día**
(2026-08-12) y cada vez se pagó con verbos de más:

| lo que se quería | lo que hubo que escribir |
|---|---|
| Deconstruct Time | `time_horas`, `time_minutos`, `time_segundos` |
| Deconstruct Vector | `vector_x`, `vector_y`, `vector_z` |
| Deconstruct Domain | `domain_min`, `domain_max` |
| Deconstruct Matrix | **bloqueado** — nadie va a querer nueve verbos para nueve celdas |

Ocho verbos existen sólo por esto, y el noveno caso ni siquiera es viable. **Ahí es donde deja de
escalar**: con tres componentes la solución de un verbo por salida es fea pero pasable; con una
matriz es absurda.

## El radio de explosión, medido

No estimado: contado sobre el árbol el 2026-08-12.

| supuesto de «una salida por nodo» | usos |
|---|---|
| `out_name` en el cerebro | **79** |
| `OutName` en el C++ | **33** |
| `runtime_outputs[nid]` | 13 (4 asignaciones) |
| `PIN_OUT` | 11 |
| `_tipo_salida` | 9 |

Cambiar los 79 + 33 de una vez es reescribir el ejecutor del que depende todo lo demás. **No se hace
así.**

## Lo que YA está a favor

**Las aristas ya llevan el pin de origen.** El formato es `(origen, origen_pin, destino,
destino_pin)` y los `.jamgraph` lo guardan; lo único que pasa es que `compilar` rechaza cualquier
`origen_pin` que no sea `"out"`:

    if (origen_pin != PIN_OUT):
        error(origen, f"pin de salida desconocido: «{origen_pin}»")

**O sea que no hay migración de formato.** Un diagrama viejo sigue siendo válido y uno nuevo con
salidas extra se puede guardar y abrir con el mismo esquema. Eso saca del camino el riesgo más caro.

## El corte propuesto: ADITIVO, con salida principal

Un verbo declara **salidas extra** además de la suya:

    "outs": (("min", "N", "desde"), ("max", "N", "hasta"))

· Un verbo **sin** `outs` se comporta EXACTAMENTE como hoy. Esa es la propiedad que hace seguro el
cambio: los 79 usos de `out_name` no se tocan, y ningún grafo existente cambia de comportamiento.
· `_tipo_salida(verbo, registro)` pasa a tomar el **pin**; hoy lo ignora porque siempre es uno.
· La validación de aristas acepta un `origen_pin` que esté en `outs`.
· En Run, el nodo se ejecuta UNA vez y las salidas extra son **rebanadas de su resultado**, no
cómputos aparte: un dominio ya es `(desde, hasta)`, un vector ya es `(x, y, z)`. Eso evita que un
Deconstruct ejecute el nodo tres veces.

**Por qué aditivo y no N salidas iguales, como Grasshopper.** Porque los 79 usos de `out_name`
preguntan «¿de qué tipo es este nodo?» para cosas que no son cablear: el color del nodo, la letra del
modo compacto, el caché, el spec, las funciones. Sacarles la respuesta obligaría a decidir, en 79
lugares, cuál de las salidas es «la del nodo». Con salida principal esa pregunta sigue teniendo la
misma respuesta que hoy.

## Lo que hay que decidir antes de escribir

1. **El caché.** `cache_core` guarda un resultado por huella de nodo. Con salidas extra que son
   rebanadas del mismo resultado, guardar el resultado completo alcanza — pero hay que confirmarlo
   con una medida, no suponerlo.
2. **El dibujo del nodo.** `SJamGraphNode` dibuja UN nub de salida. Con tres hay que decidir dónde
   van (apilados a la derecha, como Grasshopper) y cómo se golpean con el mouse; `OnOutputClicked`
   ya recibe el nombre del pin, así que el borde existe.
3. **El modo compacto.** Un nodo colapsado muestra una letra por pin (`letras.py`). Tres salidas
   necesitan tres letras únicas, y la regla de unicidad hoy es por nodo: hay que confirmar que
   alcanza.
4. **Qué se colapsa después.** Los ocho verbos de la tabla de arriba son candidatos a desaparecer,
   pero **borrarlos rompe diagramas guardados**. La decisión de compatibilidad va aparte de la
   capacidad, y probablemente sea: la capacidad primero, la limpieza cuando haya con qué migrar.

## Cómo se verifica

· Un test puro que un verbo **sin** `outs` compila y corre idéntico a hoy — la propiedad que hace
seguro todo lo demás.
· Un verbo de prueba con dos salidas: cablear cada una a un destino distinto y comprobar que llegan
valores distintos.
· Que el Compile **rechace** un pin de salida que no existe, con el nombre del pin adentro.
· Por el camino real, en UE: un `domain_construct` con sus dos salidas cableadas a dos nodos, y el
Inspector mostrando los dos valores.
· Y la regresión que más importa: los 19 tutoriales siguen compilando.

Relacionado: [[2026-08-12-ROADMAP-Escalera-Grasshopper-Basics-v1.0|la escalera de Grasshopper
Basics]], que es donde se nombró el límite por primera vez.

## Avance 2026-08-14 — cerrado, y con un falso verde adentro

La capacidad quedó completa: cerebro (`0adae42`), Slate (`83cd6bf`) y su primer consumidor real, las
matrices 4×4 (`d207caf`). `matrix_decompose` publica **cinco** salidas de una sola cuenta, que es lo
que demuestra que el mecanismo no estaba atado al dos de `domain_construct`.

### La corrección más cara: el plan contaba DOS rutas y son CUATRO

Arriba ya quedó anotado que el plan no había contado el preflight paralelo de `flow.py`. Faltaba una
más, y ésta salía **verde con el número equivocado**:

| ruta | quién la usa | ¿rebanaba? |
|---|---|---|
| `math_core.resolver` | cable de nodo de valor a nodo de valor | sí |
| `graph.ejecutar_detalle` | el ejecutor, en Run | sí |
| `graph.compilar` → `param_sources` | **params de las tools** | ❌ tiraba el pin de origen |
| `flow._param_wires` | el preflight paralelo de Flow | ❌ lo mismo |

Un cable de `domain_construct.desde` a `pts_line.count` le entregaba al verbo el dominio **entero**,
`(10.0, 90.0)` en vez de `10.0`. Y no fallaba: `dsl.coaccionar` hace `str()` de los params, no
reconoce `«(3.0, 90.0)»` como número y **descarta el parámetro en silencio**, así que la línea corría
con su default de 10. Compile verde, Run verde, número equivocado.

Las cuatro pasan ahora por **`graph._valor_del_pin`**, la única definición de «qué sale por este
pin», con un gemelo en `flow` porque `graph` importa `flow` y al revés sería círculo. La lección
—que una capacidad no se le enseña a una ruta sino a todas las que hacen lo mismo— quedó en
`AGENTS.md` con las cuatro nombradas.

### La pieza de diseño que faltaba: `corte_principal`

`matrix_decompose` es el primer verbo cuyo **valor guardado no lo muestra ningún pin, ni siquiera el
principal**: calcula los cinco vectores juntos y `out` se sirve la traslación. Sin eso, o el pin
principal declaraba «vector» y entregaba cinco, o cada pin recalculaba la descomposición entera.

⚠️ Y la validación por pin va **adentro de `evaluar`**, no en el corte: `_rebanar` corre FUERA del
`try` de `resolver`, así que un corte que levante allá no pone rojo al nodo culpable — voltea la
resolución del grafo entero.

### Las cuatro decisiones que el plan dejaba abiertas, contestadas

1. **El caché.** Guardar el resultado completo alcanza: el nodo corre UNA vez y cada pin rebana. Se
   confirmó con la sonda del camino real, no por suposición.
2. **El dibujo del nodo.** Los nubs se apilan a la derecha y `OnOutputClicked` ya recibía el nombre
   del pin. **Con cinco todavía no lo miró nadie** — es el gesto `3-ter` de `RELEVO.md`, y es donde
   la pregunta «¿se quedan donde están o suben como en Grasshopper?» importa de verdad.
3. **El modo compacto.** Sigue sin ejercerse con un nodo de cinco letras.
4. **Qué se colapsa después.** Nada: `domain_min`/`domain_max` y los `vector_x/y/z` **no se tocaron**,
   porque borrarlos rompe diagramas guardados. La capacidad primero, la limpieza cuando haya con qué
   migrar.

### El defecto de al lado, anterior a todo esto

Buscando cómo mostrar una matriz en el cuerpo del nodo apareció que el panel elegía el texto por el
**tipo de Python** del valor —número, texto, y todo lo demás al saco de `(sin resolver)`—. Cualquier
vector, dominio o matriz resuelto se dibujaba como si no hubiera resuelto, con el estado del nodo en
«ok» al mismo tiempo. Existía desde antes de multi-salida y lo veía cualquiera con un
`domain_construct` en pantalla. Ahora hay `math_core.texto_de_valor`, una sola definición para Graph
y Flow, que pregunta si RESOLVIÓ y deja al tipo decidir sólo **cuánto** se escribe.
