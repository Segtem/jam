---
title: "Historial del Graph: deshacer y rehacer"
tipo: INFORME
version: "1.0"
date: 2026-07-29
updated: 2026-07-29
status: implementado
area: JamEditor/Graph
tags:
  - jam
  - graph-editor
  - slate
  - undo
  - historial
  - ux
aliases:
  - Ctrl+Z del Graph
  - Deshacer y rehacer
---

# Historial del Graph: deshacer y rehacer

`Ctrl+Z` deshace, `Ctrl+Shift+Z` (y `Ctrl+Y`) rehace, y las dos están en el menú `Edit`, que las
muestra deshabilitadas cuando no hay nada que deshacer.

## Un paso deshacible es el grafo entero, en JSON

No hay motor de comandos. El grafo **ya sabía serializarse** (`BuildJson()` / `LoadGraphJson()`,
que es lo que usan Guardar y Abrir), así que un paso del historial es sencillamente el JSON del
grafo completo. Un diagrama pesa kilobytes: el costo es irrelevante, y a cambio el historial **no
puede desincronizarse del modelo, porque es el modelo**.

Dos pilas y una foto:

```text
Deshechos [ ... , estado_n-2, estado_n-1 ]   ← Ctrl+Z saca de acá
Anterior    estado_n                          ← la foto del estado actual
Rehechos  [ ... ]                             ← Ctrl+Shift+Z saca de acá
```

Tope de 50 pasos; al pasarse se cae el más viejo. Un paso nuevo **corta la rama de rehacer**, que es
la convención de todo editor.

## La decisión que importa: se marca DESPUÉS, apilando la foto anterior

El plan original decía «fotografiar antes de cada mutación». Está mal, y por una razón que sólo
aparece mirando el código: **`BuildJson` lee los valores VIVOS de los widgets**. Los parámetros de un
nodo no viven en el modelo, viven en el text box.

Entonces, si uno tipea `count = 24` y después borra un nodo, la foto tomada «antes de borrar» ya
incluye el `24`. Al deshacer el borrado, el `24` se iba con él: un solo `Ctrl+Z` deshacía dos cosas.

La versión que quedó es uniforme y no tiene ese problema:

```cpp
void Marcar()          // se llama DESPUÉS de la mutación
{
    Deshechos.Add(Anterior);   // apila el estado PREVIO, que ya estaba fotografiado
    Rehechos.Reset();
    Anterior = BuildJson();    // y refotografía el actual
}
```

Como `Anterior` se refresca en cada paso, siempre refleja lo que había —incluido lo tipeado— justo
antes de la mutación que se está registrando.

## Los dos avisos que no existían

Para que un paso sea un paso, el editor tiene que enterarse. Faltaban dos:

- **`OnParamChanged`** — los cinco tipos de control de parámetro (slider del `number`, sus `min`/`max`,
  toggle, dropdown y campo de texto) ahora avisan **al confirmar**: Enter, perder el foco, soltar el
  slider, elegir del menú. Al confirmar y no en cada tecla, o tipear «24» serían dos pasos y `Ctrl+Z`
  devolvería «2».
- **`OnDragEnd`** — un arrastre es UN paso, al soltar. Y sólo si el nodo se movió de verdad: un clic
  con el pulso no ensucia el historial.

## Lo que es un paso y lo que no

| Sí | No |
|---|---|
| crear un nodo · borrarlo · borrar la selección (uno solo, no doce) | seleccionar, deseleccionar |
| conectar · desconectar con `Alt`+clic (si había cable) | `Alt`+clic sobre un pin sin cables |
| mover (al soltar) | pan y zoom |
| alinear y distribuir | correr el grafo |
| cambiar un parámetro | tipear sin confirmar |
| vaciar el grafo · abrir un diagrama · la galería (uno, no 200) | el Preview |

Cargar un diagrama son N nodos + N wires en el modelo, pero **un** paso para el usuario: lo
resuelve una bandera de silencio (`bSinHistorial`) sobre el bloque de reconstrucción. Va con
`TGuardValue` y no con un bool a mano justamente porque adentro de ese bloque hay `return`s de
error: dejar la bandera prendida mataría el historial en silencio por el resto de la sesión.

Pan y zoom quedan afuera **a propósito**: no son el documento, y meterlos haría que `Ctrl+Z` a veces
mueva la cámara en vez de deshacer lo último que hiciste.

## Dos arreglos que cayeron de paso

**Los ids ya no se renumeran al cargar.** `LoadGraphJson` reconstruía el grafo con `AddNode`, que
emitía ids nuevos (`n1`, `n2`, …) en el orden de un `TMap` de JSON —que ni siquiera es estable—. Para
Guardar/Abrir era invisible; para deshacer no: cada `Ctrl+Z` habría reescrito los ids del grafo, y el
veredicto del oráculo y el inspector quedarían apuntando a nodos que cambiaron de nombre. Ahora
`AddNode` acepta un id preferido y el contador se corre para no repetirlo. De regalo, un `.jamgraph`
guardado dos veces produce el mismo archivo, así que su diff se puede leer.

**Deshacer ya no te cambia de documento.** `LoadGraphJson` pasa por `NewGraph`, que borra
`CurrentPath` (abrir uno vacío sí empieza un archivo nuevo). Sin cuidarlo, un `Ctrl+Z` hacía que el
próximo «Guardar» pidiera nombre en vez de sobrescribir el `.jamgraph` en el que venías trabajando.

## Verificación

Compila; los 8 tutoriales siguen cargando y compilando en el editor (`VEREDICTO: TODO VERDE`), que es
lo que ejercita el camino de `LoadGraphJson` con los ids preservados; y los 459 tests del cerebro
siguen en verde.

**Lo que no está verificado por test es el historial en sí**: es interacción de Slate y no hay forma
de manejarlo headless. Los puntos donde se marca un paso se auditaron uno por uno leyendo el código
—hay 9 llamadas a `Marcar()` y 4 bloques de silencio— pero eso es lectura, no medición. Que `Ctrl+Z`
haga lo correcto hay que probarlo a mano.

## El resto de la Fase 1, hecho el mismo día

Copiar / cortar / pegar / duplicar salieron enseguida y con el mismo mecanismo: `BuildJson()` ahora
acepta un filtro, así que un recorte es el mismo JSON con menos nodos. Va al portapapeles **del
sistema**, no a un buffer interno, y por eso se pega entre dos ventanas de Graph y el fragmento se
puede leer a ojo o pegar en el vault.

Dos detalles que valen: **un cable sólo viaja si sus DOS puntas están en el recorte** (uno a medias
no es un grafo, y pegarlo dejaría una entrada conectada a la nada); y cada cable pegado pasa por
`CanConnect`, **la misma compuerta que conectar a mano** — un cable pegado no puede entrar por una
puerta que un cable dibujado no podría cruzar.

Pegar N nodos con sus cables es UN paso. Como `PegarJson` tiene `return`s de error adentro, el
silencio va con `TGuardValue` y el `Marcar()` lo hace el que llama, según lo que devuelva.

## Relacionado

- [[2026-07-29-ROADMAP-Accesibilidad-Graph-v1.0|Roadmap de accesibilidad del Graph]]
- [[2026-07-29-INFORME-Seleccion-Multiple-Alineacion-Nodos-v2.0|Selección múltiple y alineación]] — la Fase 0
- [[2026-07-25-PLAN-Persistencia-Segura-Diagramas-Graph-v1.0|Persistencia segura de diagramas]] — de acá sale el snapshot
