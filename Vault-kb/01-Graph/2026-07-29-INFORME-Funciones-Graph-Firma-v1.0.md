---
title: "Funciones del Graph: un subgrafo con firma"
tipo: INFORME
version: "1.0"
date: 2026-07-29
updated: 2026-07-29
status: implementado-cerebro
area: 01-Graph
tags:
  - jam
  - graph
  - funciones
  - compilador
  - oraculo
aliases:
  - Funciones con firma
  - Compound con entradas y salidas
  - fn:nombre
---

# Funciones del Graph: un subgrafo con firma

Es la Fase 5 del [[2026-07-29-ROADMAP-Accesibilidad-Graph-v1.0|roadmap de accesibilidad]], y la de
mayor palanca: es lo que convierte «hice un grafo que anda» en «tengo una herramienta».

Hasta acá un preset de grafo guardaba un diagrama entero y lo aplicaba. Es el Cluster de
Grasshopper, el HDA de Houdini, el «Collapse to Function» de Blueprint. A los tres les falta lo
mismo cuando no lo tienen: **una firma**.

## Las piezas

**Dos verbos de borde, `input` y `output`.** Adentro del cuerpo marcan qué entra y qué sale, con
nombre y tipo del vocabulario que ya existe (`A`, `P`, `F`, `M`, `MT`, …). Una función no es un
formato nuevo: es un `.jamgraph` que además declara pines.

**Una instancia es un nodo con verbo `fn:<nombre>`**, y sus pines *son* la firma del cuerpo.
`funcion.firma()` los devuelve en el orden en que se ven —de arriba a abajo—, no en el orden en que
se crearon: es el orden que espera quien mira el nodo.

**`expandir()`** reemplaza cada instancia por una copia del cuerpo y recablea el borde.

## La decisión que importa: expandir es anterior al compilador

La expansión es una transformación **grafo → grafo pura**, no algo adentro de `compilar`.

Después de expandir, lo que queda es un grafo normal. `compilar` no se entera de que hubo funciones,
y **el oráculo sigue midiendo exactamente lo mismo**. Una función opaca le taparía el interior al
oráculo — que es lo único que este proyecto no puede permitirse. Como efecto secundario, todo esto
se testea sin motor y sin compilador.

Los ids expandidos son `<instancia>__<id en el cuerpo>`: se lee de qué instancia salió cada nodo en
el diagnóstico, y no hay choques por construcción.

Anidar funciones está permitido. Que una se contenga a sí misma, no: se detecta con una pila de
nombres y es un **error de compilación con el camino** (`a → b → a`), no un cuelgue.

## Cableado hasta el borde

El motor sin consumidores no sirve —es exactamente lo que le pasa al preview 2D, que está entero y
no lo usa nadie—, así que esto llega hasta la puerta por la que entra Slate:

- `api.compile_graph_json` y `api.run_graph_json` **expanden antes que nada**. Una función recursiva
  sale como `COMPILE ✗` con su motivo, no como excepción cruda contra el editor.
- El `kind` de un preset **sale del contenido**, como ya era: si el grafo declara pines, es
  `funcion`. No hay un botón «guardar como función».
- Una función **no se aplica sola** —sería ejecutar `input`/`output` como si fueran verbos—: se
  rechaza con el motivo y se sugiere instanciarla con `fn:<nombre>`.

## Verificación

18 tests nuevos, 477 en total. El que manda es el del roadmap: **un grafo que usa la función dos
veces compila al mismo plan que el grafo plano equivalente**. Se compara el plan —orden topológico y
parámetros resueltos—, no la imagen: los ids cambian a propósito y **no son parte del contrato**,
porque si lo fueran, renombrar un nodo adentro del cuerpo rompería a todos los usuarios de la
función.

Probado por mutación con 6 mutantes: ids sin prefijo de instancia, sin guarda de recursión, firma
ordenada por id, sin copiar params, sin pasamanos, y sin cablear las entradas.

**Uno sobrevivió.** «Firma ordenada por id» pasaba en verde porque en el test el id `a` caía justo
en el pin de arriba y los dos órdenes coincidían: el test no discriminaba nada. Ahora los ids van a
propósito al revés que la posición. Es el argumento entero de la prueba por mutación — sin romper el
código a propósito, ese test se quedaba en la suite dando una seguridad falsa.

## Lo que falta (capa de Slate)

- **Instanciar desde el ribbon**: `firma()` ya devuelve los pines ordenados; falta dibujarlos.
- **`Ctrl+G`, colapsar la selección a función**: los cables que cruzan el borde de la selección se
  vuelven `input`/`output`. Es donde la Fase 0 se paga sola, porque la selección ya es un estado.

## Relacionado

- [[2026-07-29-ROADMAP-Accesibilidad-Graph-v1.0|Roadmap de accesibilidad del Graph]] — Fase 5
- [[2026-07-29-INFORME-Seleccion-Multiple-Alineacion-Nodos-v2.0|Selección múltiple]] — de lo que
  depende «colapsar a función»
- [[2026-07-25-ROADMAP-Vision-Producto-Jam-v1.0|Visión y roadmap de producto]] — el paso
  «Graph editable → Compound reusable»
