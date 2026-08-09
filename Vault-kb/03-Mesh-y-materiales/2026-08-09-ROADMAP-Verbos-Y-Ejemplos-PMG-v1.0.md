---
title: "Roadmap de verbos y ejemplos de malla procedural"
tipo: ROADMAP
version: "1.0"
date: 2026-08-09
updated: 2026-08-09
status: en-implementacion
area: 03-Mesh-y-materiales
tags:
  - procedural-mesh
  - roadmap
  - curvas
  - flow
  - ejemplos
aliases:
  - Roadmap PMG
  - Roadmap de verbos procedurales
---

# Roadmap de verbos y ejemplos de malla procedural

## Norte

Jam necesita una biblioteca de **verbos pequeños, datos visibles y ejemplos componibles**. Un ejemplo
puede producir un árbol, una carretera o una parcela; un verbo no debe llamarse «Hacer árbol» ni
«Hacer ciudad» si el resultado puede expresarse como transformaciones medibles sobre `N[]`, `P`,
`S`, `F` y `M`.

Cada entrega termina solamente cuando cumple cuatro fronteras:

1. cerebro puro sin `unreal`, con límites de explosión y errores de dominio;
2. Graph público con pines y tipos correctos, no una llamada directa al helper;
3. sonda en UE 5.8.1 que compila y ejecuta por `api.compile_graph_json`/`run_graph_json`;
4. ejemplo editable que hace visible por qué el verbo existe y enumera lo que la medida no ve.

## Estado de la base

| Dato/operación | Estado | Ejemplo o evidencia |
|---|---|---|
| `Range` N[] y `Remap` N[] → N[] | ✅ | Rango y Remap |
| `Polyline` N[]³ → S | ✅ | Cylinder Strip continuo |
| `Smooth` S → S | ✅ | Reduce aspereza sin cambiar cardinalidad |
| `Resample` S → S | ✅ | Redistribuye por longitud |
| `Noise` M → M | ✅ | Terreno con ruido |
| `Offset` S → S y `Ribbon` S → M | ✅ | Borde de camino |
| `Extrude` M → M sobre superficie abierta | ✅ | Muro sobre spline |
| barridos S → M, frames S → F y ramas | ✅ | Cylinder Strip y ejemplos TreeGen |

## Fase 1 — editar la discretización de paths

**Objetivo:** distinguir quitar, insertar, redistribuir y suavizar puntos.

**Estado: ✅ implementada y verificada en UE 5.8.1 el 2026-08-09.**

- `curve_fuse_collinear` S → S: fusiona puntos colineales por umbral angular y puntos
  co-localizados por tolerancia espacial; preserva extremos y reporta cuántos quitó.
- `curve_subdivide` S → S: subdivide cada segmento por cantidad o por largo máximo; conserva todos
  los vértices originales y reporta cuántos insertó.
- Ejemplo **Preparar una curva**: Polyline → Fuse → Subdivide → Smooth → Resample → Debug.

**Medidas:** cardinalidad esperada, extremos y vértices originales conservados donde corresponde,
error angular residual, largo máximo de segmento y metadata TreeGen intacta.

La sonda pública midió la cadena `7→2→5→5→13`; dos mutaciones deliberadas demostraron que los
tests detectan tanto invertir el juicio angular de Fuse como interpretar `count` con una división
menos. El catálogo completo quedó en 14/14 ejemplos compilados dentro del motor.

## Fase 2 — contornos, caminos y muros

**Objetivo:** convertir un recorrido procesado en bordes y superficies utilizables.

**Estado: ◐ Offset, ribbon, extrusión y muro verificados; carretera modular pendiente.**

- `curve_offset` S → S con plano, lado, joins y `miter_limit` explícitos. ✅
- `curve_reverse`, `curve_close` y `curve_open` si una segunda receta demuestra que son necesarios.
- `mesh_ribbon` S → M con ancho, plano, joins, UV longitudinal y Material ID. ✅
- `mesh_extrude` M → M para dar altura/espesor en dirección fija a una superficie abierta. ✅
- `curve_solidify` no fue necesario: Ribbon define la planta y Extrude la vuelve sólido sin
  esconder dos operaciones bajo un solo nodo.
- Ejemplo **Borde de camino**: eje → Resample → Offset → Ribbon. ✅
- Ejemplo completo **Muro sobre spline**: curva → Ribbon → Extrude. ✅
- Ejemplo completo **Carretera modular**. ⏳

**Medidas:** distancia lateral, orientación, auto-intersecciones conocidas, cierre, componentes,
ancho, estiramiento UV y presupuesto de miter. Un offset no se declara correcto sólo porque dibuja.

La sonda pública de `mesh_ribbon` produjo 25 pares, 50 vértices y 48 triángulos en una sola pieza
abierta; midió ancho de extremos de 360 cm con error 0.0000, UV0 longitudinal `0..5.91` y Material ID
3 en los 48 triángulos. Invertir deliberadamente el winding puso rojo el test de normales. La
primera versión acepta recorridos abiertos: cerrar una cinta exige duplicar la costura UV y hoy se
rechaza en vez de soldarla con coordenadas ambiguas. Tampoco detecta todavía auto-intersecciones de
un camino cuyo ancho supera el radio local de sus curvas.

La receta de muro resolvió la frontera de espesor con un verbo general. `mesh_extrude` normaliza la
dirección antes de multiplicarla por la distancia —la API nativa no lo hace—, convierte centímetros
por UV a su factor inverso y rechaza mallas cerradas porque Geometry Script cambia allí la operación
a shell. La sonda real midió `48→196` triángulos, `50→100` vértices, altura 300.00 cm, UV0 completo,
Material ID 3 conservado, cierre y una pieza. Mutar `1/uv_scale` a `uv_scale` puso rojo el test.

## Fase 3 — atributos y selecciones observables

**Objetivo:** que TreeGen y las recetas PMG no dependan de sidecars invisibles.

- leer/escribir `radius`, `scale`, `weight`, `seed`, `parent_index`, `pivot_index` y Material ID;
- máscaras y filtros sobre puntos/frames/curvas con salida observable;
- blend y transferencia de atributos entre muestras antes de generar M.
- Ejemplos **Bambú** y **Palmera** construidos con los mismos verbos, no con uno por especie.

**Medidas:** procedencia, cardinalidad, rangos, estabilidad por seed y conservación a través de cada
operador.

## Fase 4 — repetición y funciones

**Objetivo:** expresar patrones recursivos/acumulativos sin copiar cadenas en el canvas.

- `Repeat Compound` sobre una función pura con firma explícita;
- límite duro de iteraciones y presupuesto de elementos/geometría;
- acumulación separada de feedback para que el ciclo sea legible y terminante.
- Ejemplos **Sierpinski Lines** y **Sierpinski Tetrahedron**.

**Medidas:** terminación, crecimiento esperado por nivel, identidad para cero iteraciones y rechazo
antes de exceder el presupuesto.

## Fase 5 — conjuntos de puntos y grafos topológicos

**Objetivo:** habilitar parcelas y redes sin esconder aristas dentro de `S`.

- decidir un dato explícito para conjunto de puntos + aristas;
- Delaunay, Voronoi, convex hull y MST;
- componentes, fronteras, flood-fill y pathfinding como operaciones de grafo;
- ejemplos de habitaciones conectadas, parcelas y layout urbano inspirados en PCGEx.

**Medidas:** planitud, aristas duplicadas/cruzadas, componentes, Euler, cobertura y estabilidad ante
permutar el orden de entrada.

## Fase 6 — superficies implícitas experimentales

**Objetivo:** evaluar Marching Cubes sin mezclarlo con la ruta determinista ya certificada.

- campo escalar 3D observable;
- extracción CPU como referencia y GPU/RDG como aceleración opcional;
- deduplicación, normales, cierre y presupuesto de readback.

Queda en categoría experimental hasta medir reproducibilidad entre procesos, hardware y versiones de
UE. No bloquea las fases de autoría sobre curvas.

## Orden inmediato

1. ~~cerrar Fase 1 completa~~ ✅;
2. ~~`curve_offset` + `mesh_ribbon` + `mesh_extrude` + muro~~ ✅; sigue carretera modular;
3. atributos explícitos + bambú o palmera;
4. Repeat Compound;
5. recién entonces definir el dato topológico y explorar generación urbana;
6. Marching Cubes queda como laboratorio independiente.

## Lo que NO ve el roadmap

- No estima todavía esfuerzo de Slate ni juicio visual de cada ficha.
- No promete que todos los verbos de PCGEx sean necesarios en Jam.
- No sustituye una verificación de licencia y versión al momento de incorporar código externo.
- No resuelve animación/runtime: este orden prioriza autoría determinista de assets y datos.
- No convierte una sonda headless verde en aprobación visual del viewport.

## Relacionado

- [[2026-08-09-INFORME-GitHub-Procedural-Mesh-Generation-v1.0|GitHub como corpus de verbos de malla procedural]]
- [[2026-08-09-INFORME-Biblioteca-Ejemplos-Malla-Procedural-v1.0|Biblioteca de ejemplos de malla procedural]]
- [[2026-07-27-INFORME-TreeGen-Auditoria-Blueprints-Flow-Real-v1.0|TreeGen: auditoría de Blueprints y flow real]]
- [[2026-08-02-ROADMAP-Nodos-Unreal-Engine-5-8-1-v1.0|Roadmap de nodos UE 5.8.1]]
