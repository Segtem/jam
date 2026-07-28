# Investigación — materiales avanzados: Layers, Substrate, Material Functions y Substance

**Fecha:** 2026-07-28 · **Motor:** UE 5.7.4 · **Proyecto de prueba:** BotOO

Todo lo que dice «medido» se corrió en el editor real (commandlet `pythonscript`, con
`-AllowCommandletRendering` donde hacía falta el costo). Lo que sale de documentación o foros está
marcado como tal, porque no es lo mismo.

---

## 1. Material Layers — **se pueden, enteros, hoy**

### Lo que está expuesto (medido)

| Pieza | Estado |
|---|---|
| Assets `MaterialFunctionMaterialLayer` / `...LayerBlend` + sus factories | ✅ se crean |
| Editar la función por dentro (`create_material_expression_in_function`, `connect_material_expressions`, `update_material_function`, `layout_material_function_expressions`) | ✅ |
| Nodo de salida `MaterialExpressionMaterialLayerOutput` (entrada `"None"`) | ✅ |
| Nodo `MaterialAttributeLayers` en un material + su `default_layers` | ✅ |
| Conectar a `MaterialProperty.MP_MATERIAL_ATTRIBUTES` (con `use_material_attributes=True`) | ✅ |
| `MaterialLayersFunctions` y `MaterialLayersFunctionsEditorOnlyData` construibles y escribibles | ✅ |
| **Pila por INSTANCIA** (cambiar capas sin recompilar) | ❌ **no expuesta** |

`MaterialInstanceConstant` no tiene `layer_parameters` ni `static_parameters` como editor property,
y `MaterialEditingLibrary` no tiene **ningún** método con «layer» en el nombre (se listaron los 81).
O sea: Jam puede autorar el material con su pila por defecto, pero no manejar la pila de una
instancia.

### ⚠️ El campo minado: escribir la pila mal **voltea el editor**

No es una excepción de Python. Es assertion + SIGSEGV:

```
Assertion failed: Runtime.Layers.Num() == EditorOnly.LayerStates.Num()
[MaterialExpressions.cpp:15406]
```

`FMaterialLayersFunctions` mantiene **arrays paralelos** que hay que sincronizar a mano. Poner sólo
`layers` y `blends` —que es lo obvio y lo que hice la primera vez— mata el proceso.

La contabilidad exacta, leída de `AddDefaultBackgroundLayer` y `AppendBlendedLayer`
(`MaterialExpressions.cpp:14983-15012`), para **N capas = 1 fondo + K mezcladas**:

| array | largo |
|---|---|
| `layers` | N |
| `blends` | **K = N−1** |
| `editor_only.layer_states` | N |
| `editor_only.layer_names` | N |
| `editor_only.restrict_to_layer_relatives` | N |
| `editor_only.restrict_to_blend_relatives` | **K** ← el único que va a K |
| `editor_only.layer_guids` | N |
| `editor_only.layer_link_states` | N |

* El fondo lleva un **GUID FIJO `(2,0,0,0)`** — el motor lo usa para reconocerlo.
* `layer_link_states` = `MaterialLayerLinkState.NOT_FROM_PARENT` para capas nuevas.
* `layer_names` acepta `str` de Python (convierte a FText solo).
* Gotcha menor: `unreal.Guid()` **no toma kwargs**; los campos a/b/c/d se escriben después.

**Consecuencia para Jam:** si esto se implementa, la construcción de la pila tiene que ser UNA
función con un test que verifique los ocho largos ANTES de escribir. Un verbo que deje pasar una
pila inconsistente no da error: cierra el editor de Brian con trabajo sin guardar.

### Verificado además

Con una pila consistente (2 capas + 1 blend) el nodo la aceptó, se conectó a la salida de atributos
y el material se guardó. El costo dio PS=0 porque **las capas estaban vacías**: un material con
capas sin contenido no compila, y el oráculo de costo lo reporta como «no medido».

---

## 2. Material Functions — **la pieza más valiosa, y ya funciona**

Medido: se crea la `MaterialFunction`, se le agregan `FunctionInput` / `FunctionOutput`, se les
ponen `input_name` / `input_type` / `output_name`, se cablean, y `update_material_function` cierra.

Y lo importante: **`MaterialFunctionCall` DESCUBRE las entradas por nombre**. Apuntándolo a la
función, `get_material_expression_input_names` devolvió `['Entrada']` — el nombre que le puse.

Es el **mismo patrón** que ya usa Jam para las 408 expresiones: la firma se deriva, no se
hardcodea. O sea que una biblioteca de funciones de material propias entra en el sistema de verbos
existente **sin código nuevo de descubrimiento**: `material_node` puede instanciar un
`MaterialFunctionCall` y el verificador puro sabría sus entradas si se vuelcan igual que
`shader_firmas.py`.

Esto es, con diferencia, el mejor retorno por esfuerzo de todo lo investigado.

---

## 3. Substrate — **presente, apagado, y con una puerta de una sola dirección**

### Medido en este proyecto

```
r.Substrate = 0                     ← BotOO va por el camino NO-Substrate
nodos Substrate expuestos: 24       (+22 con el nombre viejo «Strata»)
MaterialProperty.MP_FRONT_MATERIAL  existe
SubstrateSlabBSDF → MP_FRONT_MATERIAL: conecta ✅
material resultante: PS=285 VS=196
```

Ese PS=285 es **el piso** (un material opaco que no hace nada mide 287). O sea: con el flag
apagado, el grafo Substrate se conecta sin protestar y **no aporta nada**. Es exactamente el tipo de
falla silenciosa contra la que existe el oráculo de Jam — se ve «bien» en la UI y no hace nada.

### De la documentación y los foros

* **Beta** en 5.8, con el aviso literal de Epic: «use caution when shipping with it».
* **En 5.7+, Substrate viene ENCENDIDO por defecto en proyectos NUEVOS.** Los proyectos que vienen
  de antes —como BotOO— siguen por el camino no-Substrate salvo que se opte explícitamente
  (Project Settings → Rendering).
* Abrir un material legacy en un proyecto Substrate **ya no lo altera**; sigue siendo compatible.
* **Convertir un material a Substrate es PERMANENTE y no se puede revertir.**
* Reportado por la comunidad y **sin respuesta de Epic** (hilo de 5.7 bumpeado en marzo 2026):
  normales en tangent space «no del todo soportadas», SSS en screen space no soportado, y nodos como
  `vertex interpolator` y `pre skinned normal` incompatibles con la GUI de Material Layer.

### Qué significa para Jam

La pregunta de fondo: **¿el IR de materiales de Jam nace viejo si sólo sabe de
BaseColor/Roughness?** La respuesta honesta es *todavía no, pero se ve venir*.

A favor de no tocarlo ahora: BotOO ya existe y no está en Substrate; la conversión no se revierte;
está en Beta; y la combinación Substrate + Material Layers es justamente la que la comunidad reporta
como incompleta.

A favor de prepararse: los proyectos nuevos de 5.7 ya nacen en Substrate, así que es hacia donde va
el motor. Y el IR de Jam **no tendría que cambiar de forma** para soportarlo: `SALIDAS` gana
`MP_FRONT_MATERIAL`, los 24 nodos ya están en la tabla de firmas, y `verificar` funciona igual. El
trabajo real sería el compilador de Weight y el material de viento, que hoy escriben a BaseColor.

**Recomendación:** no encender Substrate en BotOO. Sí dejar el IR agnóstico —que ya lo es— y, si en
algún momento se quiere probar, hacerlo en un proyecto de sonda aparte, nunca en BotOO.

---

## 4. Substance — qué hay en esta máquina (medido)

| Herramienta | Estado |
|---|---|
| Substance 3D **Designer** 2026 (16.0.4) | ✅ por Steam, con MCP `dcc-mcp-substancedesigner` y skill propia |
| `sbscooker` / `sbsrender` (headless, el camino verificable) | ✅ en el dir de instalación de SD |
| Substance 3D **Painter** 2022 | ✅ por Steam (`steam://rungameid/1775390`) |
| **Plugin Substance en UE** | ❌ **no está** — ni en el motor ni en BotOO |
| Bitmap2Material 3 (B2M3) | ❌ no encontrado en esta máquina |
| Biblioteca `.sbsar` | ✅ KB3D workzone, hearthandstone, + estudios |
| Fuentes `.sbs` propias | ✅ `~/Dev/creative/substance/` (cerámica, concreto, galvanizado, madera, piedra…) |

**La consecuencia práctica:** sin el plugin de Substance en UE, un `.sbsar` **no se puede evaluar en
vivo dentro del motor**. El flujo que ya está montado es el correcto y el único disponible: cocinar
con `sbsrender` headless → PNG → importar como texturas. Eso además es lo que lo hace verificable,
que es como Jam quiere las cosas.

Sobre **B2M3**: es producto discontinuado (lo sucedió Substance Sampler) y no está instalado. Si el
objetivo es «de una foto a un material PBR», hoy el camino es Sampler o un grafo de Designer.

Sobre **Painter**: tiene API de Python **adentro de la app** (y scripting remoto), no un CLI
headless de verdad. Automatizarlo es posible pero es otra clase de integración que Designer —vale la
pena sólo si el pipeline lo pide.

---

## 5. Lo que yo haría, en orden

1. **Biblioteca de Material Functions** (bajo riesgo, alto retorno, ya funciona). Volcar las firmas
   de las funciones igual que `shader_firmas.py` y dejar que `material_node` las instancie. Convierte
   a Jam en algo que acumula vocabulario propio en vez de sólo usar el del motor.
2. **Vía de atributos** (`MakeMaterialAttributes` + `BlendMaterialAttributes` +
   `use_material_attributes`): consigue el apilado de capas **dentro de un material**, sin assets
   frágiles ni la pila que crashea. Los tres nodos ya están en la tabla de 408 firmas: **se puede
   hacer hoy con `material_node`, sin escribir una línea de código nuevo.**
3. **Material Layers de verdad** sólo si hace falta el reuso entre materiales. Y con la construcción
   de la pila encapsulada y testeada, por lo del crash.
4. **Substrate**: no ahora. Revisar cuando salga de Beta o cuando un proyecto nuevo lo imponga.
