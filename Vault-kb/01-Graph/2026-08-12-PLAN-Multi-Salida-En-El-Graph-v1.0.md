---
title: "Multi-salida en el Graph: el patrón Deconstruct"
tipo: PLAN
version: "1.0"
date: 2026-08-12
updated: 2026-08-12
status: propuesto
area: 01-Graph
tags:
  - jam
  - graph
  - arquitectura
  - grasshopper
---

# Multi-salida en el Graph: el patrón Deconstruct

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
