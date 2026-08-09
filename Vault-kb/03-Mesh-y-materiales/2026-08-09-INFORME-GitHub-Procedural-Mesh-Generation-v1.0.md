---
title: "GitHub como corpus de verbos de malla procedural"
tipo: INFORME
version: "1.0"
date: 2026-08-09
updated: 2026-08-09
status: en-implementacion
area: 03-Mesh-y-materiales
tags:
  - procedural-mesh
  - github
  - pcgex
  - geometry-script
  - ejemplos
aliases:
  - Corpus GitHub de PMG
  - Verbos PMG en GitHub
---

# GitHub como corpus de verbos de malla procedural

## Decisión

Los repositorios externos se usan como **corpus de capacidades y ejemplos**, no como dependencias de
Jam. La mejor dirección encontrada es la familia `Paths` de PCGEx: operaciones pequeñas, observables y
componibles sobre datos intermedios. Es la misma forma que necesita Jam para que el oráculo mida cada
transformación y no solamente el resultado final de un generador monolítico.

El primer verbo que salió de esta revisión es `curve_smooth`, **Suavizar curva**, implementado desde
cero como S → S. Hace pasadas Laplacianas simultáneas, permite conservar los extremos y no cambia la
cantidad de puntos ni la metadata jerárquica. Sigue siendo responsabilidad separada de
`curve_resample` elegir la densidad por longitud.

No se copió código de ninguno de los repositorios estudiados.

## Matriz de fuentes

| Repositorio | Versión/licencia observada | Qué enseña | Decisión para Jam |
|---|---|---|---|
| [PCGExtendedToolkit](https://github.com/PCGEx/PCGExtendedToolkit) | UE 5.8 en el plugin actual; MIT | Más de 200 primitivas: paths, grafos, filtros, sampling, topología y atributos | **Corpus principal de verbos**, sin volverlo dependencia |
| [PCGEx Example Project](https://github.com/PCGEx/PCGExExampleProject) | Proyecto UE 5.8; MIT | Categorías atómicas y ejemplos compuestos: contornos, cuartos, parcelas, ciudades y flood-fill | Corpus de grafos/tutoriales cuando Jam tenga datos de puntos y aristas |
| [ProceduralMeshDemos](https://github.com/TriAxis-Games/ProceduralMeshDemos) | UE 4.25; MIT | Secuencia pedagógica de primitivas, strips, heightfields y fractales | Ya alimenta los primeros ejemplos; no copiar su renderer histórico |
| [UnrealMeshProcessingTools](https://github.com/gradientspace/UnrealMeshProcessingTools) | Muestras UE 4.24/4.26; MIT | Separación entre herramienta interactiva, operador geométrico y procesamiento por comando | Referencia arquitectónica antigua, no código para integrar directo |
| [Modular Road Tool](https://github.com/coquigames/Modular_Road_Tool) | UE 4.18+; MIT | Spline de carretera, carriles, conectores, soportes, decoración y materiales | Ejemplo futuro para `offset`, frames, repeat y colocación por curva |
| [Procedural Cities](https://github.com/TriAxis-Games/Procedural-Cities) | Proyecto académico antiguo; MIT | Descomposición de ciudad completa con interiores continuos | Corpus de problemas; demasiado monolítico para ser un verbo |
| [UE5 Marching Cubes](https://github.com/Russell-Newton/UE5-Marching-Cubes) | UE5/RDG; MIT | Isosuperficie en compute shader y costo del readback GPU | Rama experimental posterior; contrato y determinismo son distintos |
| [monolith](https://github.com/tumourlove/monolith) | UE 5.7/5.8; MIT | Superficie amplia de acciones, namespaces y descubrimiento/validación | Estudiar despacho; Jam conserva un vocabulario menor, compuesto y medible |
| [ProceduralDungeon](https://github.com/BenPyton/ProceduralDungeon) | UE4/5; CeCILL-C en GitHub | Salas escritas a mano, seed y ensamblaje topológico | Corpus de Flow, no PMG de malla; licencia requiere tratamiento separado |

RealtimeMeshComponent también apareció en la búsqueda, pero resuelve representación/render de
malla runtime, no autoría geométrica. No conviene convertir una infraestructura de renderer en el
vocabulario de Jam.

## El vocabulario que sí se transfiere

PCGEx declara explícitamente `smooth`, `simplify`, `subdivide`, `cut`, `fuse`, `offset` y `bevel`
como operaciones de paths. Al inspeccionar el source actual también aparecen variantes para
resample, reduce, shift, shrink, slide, solidify y stitch. El valor para Jam no es reproducir el
catálogo entero, sino extraer fronteras que sigan siendo claras en un cable:

1. `curve_smooth` S → S: ya implementado; reduce aspereza, conserva cardinalidad y opcionalmente
   extremos.
2. `curve_fuse_collinear` S → S: **implementado**; elimina puntos redundantes con umbral angular y
   tolerancia espacial e informa cuántos puntos quitó.
3. `curve_subdivide` S → S: **implementado**; inserta puntos por distancia o cantidad, sin
   confundirse con remuestreo global.
4. `curve_offset` S → S: base de caminos, muros y contornos; necesita plano, lado, joins y límite de
   miter visibles.
5. `curve_solidify` o ribbon S → M: convierte el contorno procesado en geometría, con ancho y UV
   mensurables.
6. Delaunay, Voronoi y MST: esperan un tipo explícito de conjunto de puntos/grafo; forzarlos hoy
   dentro de `S` escondería topología.

El primer corte, **Fuse Collinear + Subdivide**, ya quedó cerrado con el tutorial `Preparar una
curva`. Sigue Offset y un tutorial de carretera o muro. La base ya distingue quitar, insertar,
redistribuir y suavizar puntos antes de abordar repeat recursivo o generación urbana.

## Ejemplo incorporado

`Cylinder Strip continuo` ahora enseña una cadena más completa:

```text
X/Y/Z N[] → Polyline S → Smooth S → Resample S → Pipe M
```

La curva quebrada se suaviza antes de uniformar la distancia entre muestras. El ejemplo sigue
produciendo un solo sweep cerrado y conectado; no es una hilera de cilindros independientes.

## Licencias y procedencia

- MIT permite estudiar y reutilizar con sus condiciones, pero una incorporación sustancial debe
  conservar el aviso correspondiente; esta entrega no incorporó código externo.
- CeCILL-C no se mezcla por inercia con el corpus MIT: ProceduralDungeon queda como referencia de
  diseño hasta hacer una revisión legal concreta.
- Un gist o fragmento sin licencia explícita no se copia aunque su algoritmo parezca conveniente.
- Los repos cambian: versión, licencia y compatibilidad se vuelven a comprobar antes de importar
  cualquier cosa.

## Lo que NO ve

- No se compilaron los repositorios externos dentro de BotOO ni se ejecutaron sus mapas de ejemplo.
- La inspección de source prueba que las capacidades existen, no que su comportamiento sea equivalente
  al contrato propio de Jam.
- No se comparó rendimiento ni calidad visual entre `curve_smooth` y PCGEx.
- La investigación no garantiza estabilidad de API, licencia o compatibilidad futura de cada repo.
- Marching Cubes en GPU exigiría medidas de readback, topología y reproducibilidad que todavía no
  existen; por eso no es el próximo verbo.

## Relacionado

- [[2026-08-09-INFORME-Biblioteca-Ejemplos-Malla-Procedural-v1.0|Biblioteca de ejemplos de malla procedural]]
- [[2026-08-02-ROADMAP-Nodos-Unreal-Engine-5-8-1-v1.0|Roadmap de nodos UE 5.8.1]]
- [[2026-08-09-ROADMAP-Verbos-Y-Ejemplos-PMG-v1.0|Roadmap de verbos y ejemplos PMG]]
- [[2026-07-27-INFORME-TreeGen-Auditoria-Blueprints-Flow-Real-v1.0|TreeGen: auditoría de Blueprints y flow real]]
