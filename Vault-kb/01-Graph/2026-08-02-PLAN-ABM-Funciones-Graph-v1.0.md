---
title: "ABM de funciones del Graph: identidad, firma y cuerpo"
tipo: PLAN
version: "1.0"
date: 2026-08-02
updated: 2026-08-02
status: en-progreso
area: 01-Graph
tags:
  - jam
  - graph
  - funciones
  - abm
  - ux
  - blueprint
aliases:
  - Biblioteca de funciones
  - Editor de firmas
  - ABM de funciones
---

# ABM de funciones del Graph: identidad, firma y cuerpo

El prototipo demostró la expansión de subgrafos, pero todavía confunde tres cosas distintas: el
identificador de una definición, su nombre visible y el nombre del archivo que la guarda. Por eso
una función nace como `Fn: Función 072657-271`, no se puede renombrar con seguridad y la biblioteca
no ofrece editar ni borrar.

Este plan convierte `Funciones/Biblioteca` en un administrador de definiciones, sin volver opaca la
expansión que mide Oracle.

## Estado del arte que se adopta

Blueprint separa la lista de funciones, el grafo que edita su cuerpo y el panel de detalles que
administra nombre, categoría, descripción y pines. Al colapsar una selección permite renombrar,
abrir la función con doble clic, agregar entradas y salidas y también volver a expandir la llamada.

- [Collapsing Graphs — Unreal Engine](https://dev.epicgames.com/documentation/unreal-engine/collapsing-graphs-in-unreal-engine)
- [Functions — Unreal Engine](https://dev.epicgames.com/documentation/unreal-engine/functions-in-unreal-engine?lang=en-US)

Los grupos de nodos de Blender usan una lista explícita de sockets con alta, baja, reordenamiento,
nombre, tipo y descripción. Las Material Functions de Unreal siguen el mismo contrato: los nodos de
entrada y salida forman los pines de la llamada, y cada entrada tiene nombre, tipo y descripción.

- [Node Groups — Blender](https://docs.blender.org/manual/en/latest/interface/controls/nodes/groups.html)
- [Material Function Expressions — Unreal Engine](https://dev.epicgames.com/documentation/en-us/unreal-engine/material-function-expressions-in-unreal-engine)

Houdini aporta la decisión que Jam necesita para no romper grafos guardados: un HDA tiene un nombre
interno estable y una etiqueta humana separada. El primero identifica el tipo; la segunda se puede
cambiar. Su editor de propiedades concentra etiqueta, versión, entradas, salidas e interfaz.

- [Create New Digital Asset — Houdini](https://www.sidefx.com/docs/houdini/ref/windows/createtype.html)
- [Type Properties — Houdini](https://www.sidefx.com/docs/houdini/ref/windows/optype)

## Contrato de una definición

Una función nueva guarda estos conceptos por separado:

```json
{
  "kind": "funcion",
  "funcion_id": "f_4b3f…",
  "nombre": "Fracturar roca preparada",
  "descripcion": "…",
  "graph": { "nodes": {}, "edges": [] }
}
```

- `funcion_id` es estable, no visible y no reutilizable. La instancia usa `fn:<funcion_id>`.
- `nombre` es la etiqueta humana. Renombrarla no altera las llamadas existentes.
- el archivo puede conservar un slug legible, pero deja de ser la identidad.
- las definiciones antiguas sin `funcion_id` siguen resolviendo `fn:<nombre>`; se migran al
  guardarlas, no mediante una reescritura destructiva de toda la biblioteca.
- el cuerpo sigue siendo un grafo normal con nodos `input` y `output`; `expandir()` continúa
  eliminando la abstracción antes del compilador y del oráculo.

## Superficie ABM

`Funciones/Biblioteca` tendrá una fila por definición con nombre humano, firma resumida y acciones:

- **Nueva** pide un nombre antes de crear; no inventa marcas horarias como interfaz final.
- **Editar** abre el cuerpo en el Graph y deja visible que se está editando una definición.
- **Guardar cambios** actualiza cuerpo, descripción y firma sin cambiar `funcion_id`.
- **Renombrar** cambia sólo la etiqueta.
- **Eliminar** exige confirmación y se niega si el grafo abierto contiene llamadas a esa función.
  La búsqueda de referencias en todos los presets queda como frontera explícita hasta tener un
  índice de dependencias.
- el doble clic sobre una función equivale a **Editar**.

Colapsar selección abre primero el diálogo de nombre y después crea la definición. Una función no
debe volver a aparecer como `Fn: Función XXXXX-XXXX`: el prefijo `fn:` pertenece al protocolo
interno, no al título del nodo.

## Firma y nombres de pines

La firma sigue saliendo de los bordes del cuerpo para que haya una sola fuente de verdad. Al editar
una función, los nodos `Entrada` y `Salida` permiten definir nombre y tipo con opciones válidas del
vocabulario de Jam. El orden visual de esos nodos continúa siendo el orden de la firma.

La regla de presentación es:

```text
nombre particular (Tipo)
```

Si no hay nombre particular, se muestra sólo `Tipo`. Ejemplos: `roca (Mesh)`, `densidad (Float)`,
`Mesh`. El tooltip conserva además el código corto (`M`, `F`, etc.). La regla se implementa en el
cerebro y se ata a Slate con un test que lee el `.cpp`, porque es una de las duplicaciones visuales
inevitables del proyecto.

## Compatibilidad y fallos visibles

- renombrar nunca cambia el verbo de una instancia nueva;
- eliminar devuelve un error legible, no un `ok` parcial;
- una firma cambiada vuelve inválida una llamada incompatible de forma explícita al compilar;
- una referencia a una definición ausente nombra el id y la última etiqueta conocida si existe;
- las funciones recursivas siguen fallando con el camino completo;
- un archivo legado conserva su comportamiento hasta que el usuario decide guardarlo.

## Orden de entrega

1. Separar id y etiqueta en Python, con lectura compatible de la biblioteca vieja.
2. Mostrar etiqueta humana y `nombre (Tipo)` en Slate.
3. Pedir nombre al colapsar y agregar Nueva/Editar/Guardar/Renombrar/Eliminar.
4. Cubrir el contrato puro, el contrato C++ leído desde tests y el camino real en el editor.
5. Agregar índice de dependencias entre presets antes de permitir borrado global sin advertencia.

## Frontera de verificación

Los tests puros pueden demostrar identidad estable, migración, firma y expansión. No demuestran que
los diálogos, el doble clic ni la persistencia del panel funcionen: eso requiere compilar 5.8.1 y
ejecutar el camino real dentro de BotOO. La entrega no se declara terminada hasta esa prueba.

## Checkpoint implementado — 2026-08-02

Los puntos 1 a 3 están implementados: id estable con compatibilidad legada, etiqueta humana, tipos
de pin cerrados, presentación `nombre (Tipo)`, nombre obligatorio al colapsar y ABM
Nueva/Editar/Guardar/Renombrar/Eliminar. La baja se bloquea ante usos en el canvas abierto y advierte
que todavía no existe índice global de dependencias.

La compilación C++ contra 5.8.1 quedó verde y `verifica_funcion_graph.py` demostró en el motor el
guardado, la publicación de la firma, dos expansiones y el Compile. Sigue pendiente ejercer con las
manos los diálogos y botones Slate; por eso el plan conserva `status: en-progreso`.

## Incidente del primer gesto manual: captura nula en el modal

Al pulsar **+ Nueva función**, escribir un nombre y aceptar, el editor caía en
`TSharedPtr::IsValid()` dentro de `JamPedirNombre`. El cuerpo vacío no intervenía: el stack no
llegaba a Python ni a `function_manage`.

`Dialogo` y `Campo` se declaraban antes de `SAssignNew`, pero sus callbacks se construían dentro de
esa misma expresión y los capturaban **por valor**. En ese instante ambos `TSharedPtr` todavía eran
`nullptr`; asignarlos después no modifica la copia congelada en la lambda. Aceptar dereferenciaba el
diálogo nulo y Cancelar compartía el mismo defecto.

Como el diálogo es modal, `JamPedirNombre` no retorna mientras esos callbacks pueden ejecutarse. La
corrección segura es capturar por referencia los dos locales (`&Campo`, `&Dialogo`). Un test de
contrato lee el `.cpp` y se probó rojo contra las capturas por valor antes de restaurar el código.

Después de recompilar 5.8.1, Brian repitió el camino real y creó **Sumar dos números**. El log mostró
el preset estable, `JAMFUNCTION {"ok": true}` y el cuerpo `entrada → salida`, sin otra aserción ni
señal. Queda pendiente completar los demás gestos del ABM.

## Incidente al cerrar Graph con un selector abierto

Durante la verificación de los nombres completos, cerrar el tab Graph dejó el editor visible pero sin
aceptar clics. `OnGraphClosed` guardaba el canvas y soltaba sus referencias sin cerrar antes los menús
emergentes ni liberar una posible captura global de puntero. Un popup/captor cuyo widget dueño ya no
existe puede seguir recibiendo los eventos de Slate y bloquear el resto de Unreal.

La primera corrección —`DismissAllMenus()` y `ReleaseAllPointerCapture()` mientras el canvas todavía
vivía— no alcanzó en el gesto real. `ReleaseAllPointerCapture` no restablece el lock del cursor ni el
foco, y `OnTabClosed` corre dentro del mismo reply que todavía tiene que destruir la ventana flotante.
Ese reply puede volver a alterar la entrada después de retornar del callback.

La corrección definitiva llama `ResetToDefaultInputSettings()` inmediatamente, guarda y suelta el
Graph, y agenda una segunda pasada con `FTSTicker` para el tick siguiente. Esa pasada actúa sobre el
estado final, ya sin el `SWindow` de docking, y devuelve al frente la ventana regular. El contrato exige
las dos fases y se probó rojo sustituyendo el reset completo por la antigua liberación parcial.

El gesto real del 2026-08-02 cerró Graph con `captor=sí menu=no modal=no`; la fase inmediata lo liberó
y la diferida registró `captor=no menu=no modal=no`. Brian volvió a usar los botones y cerró BotOO
normalmente. Antes hubo dos falsos intentos: el reloj del sandbox dejó el `.cpp` dos horas detrás del
`.so`, UBT informó `Target is up to date` y el editor cargó el binario viejo. La verificación válida
forzó la fecha del fuente y comprobó los marcadores dentro del módulo con `strings -el`.

## Incidente al abrir maximizado en UE 5.8.1 + Wayland

El bloqueo de clics reapareció sin cerrar Graph: BotOO arrancaba maximizado, la ventana se dibujaba,
pero ni el menú principal ni los botones aceptaban puntero. Restaurar la ventana y volver a
maximizarla manualmente lo corregía. El origen no era otro captor huérfano: el backend Linux de UE
5.8 advierte que, bajo Wayland, una posición cacheada de `SWindow` distinta de la asignada finalmente
por el compositor hace que `IsScreenspaceMouseWithin` rechace todos los eventos.

Jam ahora agenda una resincronización de la ventana raíz después de restaurar el layout. Separa en
ticks la restauración, un `ReshapeWindow` —aunque el rectángulo aparente no cambie— y la vuelta al
estado maximizado; al final invalida Slate y restablece entrada/foco. No abre paneles, no borra el
layout y conserva los ids persistentes `JamDashBar`, `JamGraph` y `JamContent`.

La apertura de Graph también se garantiza en las dos rutas reales. El comando de Jam pasa por
`OpenGraph`, pero el layout persistido y `Window → Tools` invocan directamente `SpawnGraphTab`; este
último agenda su propia recuperación cuando el TabManager ya adjuntó el tab a un `SWindow`. Si la
ventana flotante quedó fuera de pantalla, minimizada o con tamaño inválido, se restaura y centra en
el área de trabajo del monitor activo.

La prueba real del 2026-08-02 registró la ventana principal resincronizada en `1920,0 1920×1048`, el
Graph creado por el **spawner** en `1920,0 1427×827` y, siete segundos después, una acción del Graph
que construyó y validó su Preview. Es evidencia de apertura, foco y recepción de clics. El contrato
de C++ pasó primero con la corrección, se puso rojo al reemplazar deliberadamente `ReshapeWindow` y
volvió a verde al restaurarlo; la suite completa quedó en 547 tests.

## Edición del cuerpo y regreso al grafo llamador

Abrir **Editar** reemplaza temporalmente el canvas por la definición. Antes no había una salida
explícita y pulsar Compile/Run sobre ese cuerpo enviaba `input` y `output` al compilador de tools como
si fueran verbos ejecutables. Ahora una barra persistente identifica la función y ofrece **Guardar y
volver al grafo** o **Volver sin guardar**; el canvas llamador se serializa y se recupera incluso si
Graph se cierra y vuelve a abrir durante la edición.

Compile reconoce una definición, valida su firma y convierte sólo durante el análisis los bordes en
fuentes/sumideros sintéticos tipados. Así reutiliza las reglas normales de DAG, pines, cardinalidad y
tipos sin inventar que una función tenga valores concretos. Run explica que la definición no se
ejecuta sola: hay que guardar, insertar su ficha de Biblioteca y conectar valores. El cuerpo real
`Num1: N, Num2: N → Sumar → salida: N` dio `COMPILE ✓` con cuatro nodos.
