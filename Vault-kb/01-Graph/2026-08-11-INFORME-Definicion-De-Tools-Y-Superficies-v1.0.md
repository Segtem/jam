---
title: "Cómo se define una tool y cómo llega a la Dash Bar"
tipo: INFORME
version: "1.0"
date: 2026-08-11
updated: 2026-08-11
status: relevamiento
area: 01-Graph
tags:
  - graph
  - dash-bar
  - arquitectura
  - estado-del-arte
---

# Cómo se define una tool y cómo llega a la Dash Bar

Relevamiento pedido por Brian: hoy las tools se exponen a la Dash Bar de una forma que funciona pero
que nadie decidió del todo. Esto mide qué hay, dice qué está flojo y compara contra cómo lo resuelven
las herramientas que Jam toma como norte.

## 1. Qué hay hoy, medido

Una tool se declara en `REGISTRO`, en `Content/Python/jam/tools.py`. Son **113 entradas**. Cada una
trae cuatro campos y el resto se completa desde afuera:

| campo | lo declaran | qué es |
|---|---|---|
| `fn`, `cat`, `params`, `doc` | 113 · 113 · 113 · 112 | lo único obligatorio de facto |
| `graph_only` | 93 | **opt-out**: no aparece en la Dash Bar |
| `label` | 29 | nombre visible; los otros 84 muestran el nombre técnico |
| `opciones`, `etiquetas_params`, `data_params` | 25 · 23 · 10 | dominio y presentación de los params |
| `read_only`, `in_accepts` | 8 · 3 | contrato de ejecución y de tipos |

Y hay **9 tablas paralelas indexadas por nombre** que completan el resto: `GRAPH_SOURCES`,
`GRAPH_ARITY`, `GRAPH_MIN_INPUTS`, `GRAPH_IN_NAMES`, `GRAPH_NO_ASSET`, más `OPS_FLOW_EN_GRAPH` y
`NODOS_MATERIAL_EN_GRAPH`. Un bucle al final del módulo las cruza y deriva `source`, `aridad`,
`min_inputs`, `in_name`, `asset_required`, `asset_pin` y `asset_row`.

A eso se suman dos módulos más que también indexan por nombre de verbo: `ribbon.py` decide **en qué
familia, tab y subgrupo** cae cada uno, y `letras.py` calcula la letra de cada pin en modo compacto.

**Definir una tool, entonces, es escribir en hasta cuatro lugares distintos.** Ninguno obliga a los
otros.

### Cómo llega a la Dash Bar

`api.spec_all()` arma el spec para el Graph con `include_graph_only=True`; la Dash Bar consume el
mismo `spec_json` **sin** ese flag. O sea: la superficie se decide por **ausencia** — una tool
aparece en la barra si nadie le puso `graph_only`. Con 93 de 113 marcadas, **el default está al
revés de lo que pasa en la práctica**.

## 2. Qué está flojo

1. **La superficie se declara en negativo.** `graph_only` dice dónde NO va. Una tool nueva aparece en
   la Dash Bar por olvido, no por decisión. La pregunta «¿dónde tiene que verse esto?» no tiene un
   campo que la conteste.
2. **La definición está repartida.** Firma, presentación, ubicación y letra viven en cuatro archivos.
   Nada garantiza que un verbo nuevo aparezca en `ribbon.py`; si falta, cae en un bloque sin etiqueta.
3. **`label` es opcional y falta en 84 de 113.** El ribbon mezcla `Simplificar por triángulos` con
   `mesh_weld` crudo en el mismo subgrupo. Eso no es un olvido puntual: es lo que pasa cuando el
   campo no es obligatorio.
4. **No hay un oráculo del registro.** Todo lo demás en Jam se mide; esto no. Un verbo sin categoría
   conocida, con una letra repetida o con un `data_type` que nadie reconoce no rompe ningún test.

Lo que **sí está bien** y no hay que tocar: `fn` apunta al adaptador y la lógica vive en el cerebro
puro; el spec viaja a Slate como dato y el C++ no conoce verbos por nombre. Esa parte es correcta y
cualquier cambio tiene que preservarla.

## 3. Estado del arte

### Houdini — HDA / Operator Type Definition
Un nodo es **un artefacto** (`.hda`). Su *Type Properties* define en un solo lugar: nombre interno,
label, categoría del Tab menu, mínimo y máximo de inputs, nombres de cada input/output, y la
*Parameter Interface* completa — cada parm con tipo, rango, default, ayuda y expresiones de
`disable when` / `hide when`. **La firma y la interfaz son parte del tipo**, no metadata lateral.

### Grasshopper — `GH_Component`
Una clase por componente. El constructor lleva `(Name, Nickname, Description, Category,
SubCategory)`; `RegisterInputParams` y `RegisterOutputParams` declaran cada pin con nombre,
apodo, descripción, **tipo y acceso** (item/list/tree); `SolveInstance` ejecuta. La ubicación en el
ribbon sale de `Category`/`SubCategory` — el mismo dato que describe el componente. Y la identidad
es un **GUID estable**, separado del nombre visible, así que renombrar no rompe los archivos que ya
lo usan.

### Substance Designer
Nodos con puertos tipados; los parámetros se *exponen* explícitamente, con grupos, orden y
visibilidad condicional. Lo expuesto es una decisión declarada, no un residuo.

### Blender — `bpy.types.Operator`
`bl_idname`, `bl_label`, `bl_options` y las propiedades como anotaciones tipadas. El operador se
autodescribe; el panel que lo muestra es otra cosa, pero **el operador no depende de una tabla
externa para saber cómo se llama ni qué recibe**.

### Unreal — PCG y Blueprint
`UPCGSettings` declara sus pines con `InputPinProperties()`/`OutputPinProperties()` y sus parámetros
como `UPROPERTY` con meta. En Blueprint, `UFUNCTION(BlueprintCallable, Category="…", meta=(DisplayName="…"))`:
**la categoría y el nombre visible son meta del propio símbolo**.

### El patrón, en una frase
En las cinco, **una tool se declara en UN lugar, junto con su firma tipada, su nombre visible y su
ubicación**. Ninguna usa tablas laterales indexadas por nombre. Jam es la excepción.

## 4. Hacia dónde ir

La propuesta no es reescribir: es **mudar la verdad a un solo descriptor** y derivar lo demás.

**a. Un descriptor por verbo, completo.** Identidad estable, `label` **obligatorio**, categoría y
subgrupo, doc, firma (tipos de entrada/salida, aridad, mínimo de entradas), params con su tipo,
dominio, etiqueta y letra, y `fn`. `ribbon.py`, `letras.py` y `spec_json` pasan a **leer** de ahí en
vez de aportar su parte.

**b. La superficie, en positivo.** Reemplazar `graph_only` por algo como
`superficies={"graph"}` / `{"dash", "graph"}`. Contesta la pregunta de Brian de frente: una tool
aparece en la Dash Bar **porque alguien lo decidió**, y el default es no aparecer. La migración es
mecánica: los 93 `graph_only` son `{"graph"}` y los otros 20, ambas.

**c. Un oráculo del registro.** Es lo que falta y es barato: medidas sobre el catálogo mismo —todo
verbo tiene label; su categoría existe en el ribbon; sus letras no se repiten dentro del nodo; su
`data_type` está en el vocabulario; declara al menos una superficie—. Hoy nada de eso se mide, y es
exactamente el tipo de defecto silencioso que el proyecto persigue en todo lo demás.

**d. Migración incremental, no big-bang.** El descriptor puede convivir con el dict actual: se
agrega, se hace que las 113 entradas lo satisfagan de a poco, y un test exige que **toda tool nueva**
lo use. Sin ventana de rotura.

## 5. Lo que este informe NO dice

No mide si la Dash Bar muestra las tools **correctas** —cuáles conviene tener a mano es una decisión
de producto, no de arquitectura—. No propone cambiar la separación cerebro/adaptador, que está bien.
No toca el protocolo del spec hacia Slate, que ya viaja como dato. Y no evalúa el costo real de la
migración: son 113 entradas y hasta que no se escriba el descriptor de las primeras diez no hay una
estimación honesta.

Ver también: [[2026-07-29-GUIA-Relevo-Claude-Codex-v1.0]].
