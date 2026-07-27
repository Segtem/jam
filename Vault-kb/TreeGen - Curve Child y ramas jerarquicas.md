---
title: "TreeGen: Curve Child y ramas jerárquicas"
date: 2026-07-26
status: implementado-historico
superseded_by: "[[TreeGen - replica jerarquica real de Branch y Leaf]]"
area: Jam/Graph/GeometryScript
tags:
  - jam
  - graph
  - treegen
  - curves
  - branches
  - hierarchy
---

# TreeGen: Curve Child y ramas jerárquicas

> [!info] Evolución posterior
> `Curve Child` sigue disponible para una hija explícita. El ejemplo TreeGen vigente usa
> `Curve Branches` para transportar 64 hijas en un solo cable `S`; ver
> [[TreeGen - replica jerarquica real de Branch y Leaf]].

## Resultado

Jam incorpora `Curve Child`, un verbo `S → S` que genera una curva hija desde el frame local de una
curva padre. Las ramas ya no necesitan coordenadas mundiales duplicadas: si cambia la forma, longitud
u orientación del tronco, su punto de nacimiento y su dirección se recalculan con él.

```text
Curve Bezier S ──┬→ Mesh Pipe → tronco M
                 ├→ Curve Child S → Mesh Pipe → rama M
                 ├→ Curve Child S → Mesh Pipe → rama M
                 └→ Curve Child S → Mesh Pipe → rama M
```

La salida sigue siendo un `CurvePath` liviano. Por eso una hija puede alimentar `Mesh Pipe`,
`Mesh Along Curve` u otro `Curve Child` sin crear actores, splines ni assets intermedios.

## Parámetros

| Parámetro | Función |
|---|---|
| `at` | posición normalizada 0–1 sobre la longitud acumulada del padre |
| `length` | largo recto objetivo de la hija en centímetros |
| `angle` | apertura desde la tangente: 0° continúa el padre, 90° sale perpendicular |
| `azimuth` | giro en grados alrededor de la tangente del padre |
| `bend` | desplazamiento del control Bézier sobre la dirección de crecimiento del padre |
| `radial_offset` | separa el origen desde el eje en la dirección exterior |
| `segments` | resolución de la curva Bézier hija, de 2 a 128 |
| `samples` | resolución usada si la entrada es un SplineComponent de Unreal |

`bend > 0` levanta el arco siguiendo el crecimiento del padre; un valor negativo genera caída. El
inicio se calcula por distancia acumulada, no por índice de punto, así que `at` es estable aunque
cambie la teselación de la curva.

## Implementación geométrica

1. Normaliza `CurvePath`, `SplineComponent` o Actor con spline a una polilínea.
2. Evalúa posición y tangente a distancia normalizada `at`.
3. Construye un frame ortonormal estable incluso cuando la tangente es vertical.
4. Rota el eje exterior mediante `azimuth`.
5. Mezcla tangente y exterior mediante `angle` para obtener la dirección de la hija.
6. Genera una Bézier cuadrática desde ese origen, con `bend` relativo al padre.

La operación valida curva vacía, longitud nula, números no finitos, rango de `at`, ángulo y cantidad
de segmentos antes de entregar datos al resto del Graph.

## Ejemplo TreeGen actualizado

`TreeGen-Branched-Tree.jamgraph` usa tres `Curve Child` conectados al tronco. Cada salida alimenta tanto
su Pipe con taper como su distribución de hojas. Tras reemplazar las copas provisionales por follaje
procedural, el diagrama quedó en 21 nodos y 30 conexiones.

Las copas low-poly fueron eliminadas: el volumen verde ahora se forma con 288 tarjetas sobre las
curvas. Ya no quedan transforms mundiales de copa que se desacoplen al editar el tronco.

## Validación

- Suite Python: **57/57 OK**.
- Pruebas de anclaje, orientación, offset radial y validación de parámetros.
- El ejemplo compila con contratos `S → S → M` y 30 cables.
- Unreal Engine 5.7.4 evaluó los 21 nodos sin errores; los tres `Curve Child` terminaron `ok`.
- Preview y Bake crearon `/Game/Jam/Meshes/SM_TreeGen_Branched_Test`.
- Otro Run seguido de Discard conservó el actor y el StaticMesh horneados.
- Los Vertex Colors y su material lector permanecieron asignados.
- El único warning es el diagnóstico conocido de pivote del Plane usado como hoja provisional.
- `BuildPlugin` Linux: **BUILD SUCCESSFUL**.
- Paquete verificado: `/tmp/jam-plugin-treegen-child-20260726`.

## Próximo bloque TreeGen

El siguiente salto no debería ser otro nodo singular, sino cardinalidad jerárquica:

1. representar un conjunto de curvas o frames como dato rico público;
2. generar varias hijas con count, rango de `at`, azimuth, variación y seed;
3. permitir que Pipe y Along Curve consuman esos conjuntos;
4. después incorporar taper mediante curva, uniones/soldado, UV y viento.

Esto permite pasar de un árbol dibujado con tres nodos Child a una regla procedural repetible sin
esconder toda la generación dentro de un nodo monolítico `Tree`.

## Archivos

- `Content/Python/jam/curve.py`: evaluación del frame y generación de la Bézier hija.
- `Content/Python/jam/tools.py`: tool, parámetros y contrato Graph `S → S`.
- `Resources/Examples/TreeGen-Branched-Tree.jamgraph`: ramas dependientes del tronco.
- `Resources/Icons/Lucide/icon-map.json`: icono Lucide `git-merge`.
- `Content/Python/tests/test_mesh.py`: regresiones geométricas y del ejemplo.

## Relacionado

- [[TreeGen - curvas Pipe y arbol ramificado]]
- [[TreeGen - Mesh From Asset y Mesh Along Curve]]
- [[Graph - tab Mesh y verbos de malla procedural]]
- [[TreeGen - follaje procedural con variacion]]
