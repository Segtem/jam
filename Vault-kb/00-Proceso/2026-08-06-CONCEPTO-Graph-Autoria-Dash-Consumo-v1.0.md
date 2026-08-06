---
title: "Graph autor, Dash consumidor: qué es un proyecto y qué es una herramienta"
tipo: CONCEPTO
version: "1.0"
date: 2026-08-06
updated: 2026-08-06
status: propuesta
area: 00-Proceso
tags:
  - jam
  - graph
  - dash
  - funciones
  - presets
  - arquitectura
aliases:
  - Graph como motor de herramientas
  - HDA de Jam
  - jamgraph vs herramienta
---

# Graph autor, Dash consumidor

**La idea:** el Graph es donde se *construyen* herramientas; la Dash Bar es donde se *usan*. Como
Houdini (red → HDA) o Substance Designer (`.sbs` → `.sbsar`).

**El hallazgo:** Jam ya tiene casi toda la maquinaria. Lo que falta es un puente chico y un nombre.

## Lo que ya existe

| Substance | Houdini | Jam **hoy** |
|---|---|---|
| `.sbs` — el proyecto editable | la red | **`.jamgraph`** |
| promover parámetros | *promote parms* | `input`/`output` con nombre y tipo (`funcion.firma`) |
| `.sbsar` — la herramienta | el HDA | **preset `kind=funcion`**, que publica el verbo `fn:<nombre>` |
| el artista usa el `.sbsar` | usa el HDA | ⚠️ **falta** — ver abajo |

`jam/funcion.py` ya implementa el concepto entero: un subgrafo con firma, instanciable como un nodo
cuyos pines *son* esa firma. Su propio docstring lo dice: «el Cluster de Grasshopper, el HDA de
Houdini».

## La decisión que ya está tomada, y que conviene no revertir

**La analogía correcta es HDA, no SBSAR — y la diferencia no es el empaquetado, es la OPACIDAD.**

Un `.sbsar` es *compilado y cerrado*: sólo se ven los parámetros expuestos. Un HDA es abierto: se
puede entrar y mirar adentro.

Jam **no puede** tener un artefacto opaco, y la razón está escrita en `funcion.py`:

> Una función opaca le taparía el interior al oráculo — que es lo único que este proyecto no puede
> permitirse.

Por eso una función **se expande inline antes de compilar**: después de expandir queda un grafo
normal y el oráculo mide exactamente lo mismo que mediría sin funciones. Un `.jamar` compilado al
estilo `.sbsar` rompería la premisa del producto.

> [!important] Regla
> Una herramienta de Jam es **transparente por obligación**. Se puede empaquetar, versionar y
> compartir; no se puede cerrar.

## Los tres huecos reales

### 1. La Dash no ve lo que el Graph produce ← *el corazón de la idea*

El Graph carga `api.spec_all()` (verbos + ops de flow + **funciones**). La Dash carga `api.spec()`,
que es sólo `tools.REGISTRO`. Una definición creada en el Graph **no aparece en la Dash**.

Es el cambio más chico de los tres y el que más se parece a lo que se pidió.

**Pregunta abierta:** ¿*todas* las funciones aparecen en la Dash, o sólo las marcadas como
«publicadas»? Un Graph de trabajo genera funciones intermedias que serían ruido en una barra de
herramientas.

### 2. Una herramienta no es un archivo que se pueda pasar

Hoy una definición vive en `presets/*.json` del plugin (global, versionado) o en
`<proyecto>/Saved/JamPresets/` (local). No hay «tomá este archivo e importalo».

Un artefacto portable **sí** tiene sentido y no rompe nada, siempre que sea transparente: JSON con
cuerpo + firma + metadata. Es empaquetado, no compilación.

### 3. Una herramienta expone PINES, no PARÁMETROS

Éste es el hueco conceptual, y el que la analogía con Substance ilumina mejor.

Un `.sbsar` expone **parámetros** (sliders, enums) que el artista toca sin entender el grafo. Un HDA
promueve parámetros escalares al nivel del asset. La firma de una función de Jam, en cambio, son
**pines**: cosas que se cablean.

Para que la Dash sea usable como barra de herramientas hace falta lo otro: poder marcar un parámetro
interno (`count`, `seed`, `radius`) como **expuesto**, y que aparezca como control en la ficha.
Hoy no existe.

Sin esto, una función en la Dash sería un botón sin perillas.

## Vocabulario propuesto

- **Proyecto** — `.jamgraph`. El diagrama editable. *(existe)*
- **Definición** — un `.jamgraph` con `input`/`output`; el cuerpo de una herramienta. *(existe)*
- **Herramienta publicada** — una definición con firma **más parámetros expuestos**, visible en la
  Dash. *(falta el «publicada» y los parámetros)*

Deliberadamente **no** se propone una extensión nueva tipo `.jamar`: sugeriría un artefacto
compilado, que es justo lo que no puede ser.

## Orden sugerido

1. **Parámetros expuestos** en la firma de una función. Es el que falta de verdad; sin él lo demás
   no rinde.
2. **Publicar/despublicar** una definición, y que la Dash muestre las publicadas.
3. **Exportar/importar** una definición como archivo suelto.

El 1 es puro cerebro (`funcion.py` + `preset.py`), testeable sin motor. El 2 es un cambio de una
línea en qué spec carga la Dash, más el flag. El 3 es E/S de archivos.

## Relacionado

- [[2026-07-29-INFORME-Funciones-Graph-Firma-v1.0]]
- [[2026-08-02-PLAN-ABM-Funciones-Graph-v1.0]]
