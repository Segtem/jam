---
title: "TreeGen: Mesh From Asset y Mesh Along Curve"
tipo: INFORME
version: "1.0"
date: 2026-07-26
updated: 2026-07-26
status: implementado-historico
superseded_by: "[[2026-07-26-INFORME-TreeGen-Replica-Jerarquica-Branch-Leaf-v1.0|TreeGen: réplica jerárquica de Branch y Leaf]]"
area: 02-TreeGen
tags:
  - jam
  - graph
  - treegen
  - curve-frames
  - leaves
  - dynamic-mesh
---

# TreeGen: Mesh From Asset y Mesh Along Curve

> [!info] Evolución posterior
> `Mesh From Asset` y `Mesh Along Curve` siguen disponibles, pero el ejemplo ya no usa el Plane como
> hoja. Fue reemplazado por la jerarquía documentada en
> [[2026-07-26-INFORME-TreeGen-Replica-Jerarquica-Branch-Leaf-v1.0|TreeGen: réplica jerárquica de Branch y Leaf]].

## Resultado

Jam puede recuperar la geometría de un `StaticMesh` y repetirla como una sola `DynamicMesh` orientada
sobre cualquier curva. El ejemplo ramificado usa el Plane incluido en Engine como hoja provisional y
genera 288 tarjetas distribuidas sobre 72 frames entre tronco y ramas.

```text
Asset A ───────────────────────────┐
                                  ├→ Mesh Along Curve → M
Curve Bezier S ────────────────────┘

Asset A → Mesh From Asset → M
```

## Mesh From Asset

- Contrato: `A → M`.
- Acepta ruta o `unreal.StaticMesh` ya cargado.
- Usa `GeometryScript_AssetUtils.copy_mesh_from_static_mesh`.
- Lee el mejor LOD fuente disponible y aplica sus Build Settings.
- No crea paquete, actor ni copia persistente.
- El MVP preserva geometría/atributos de malla, pero no transporta la lista de materiales del asset.

Esto permite llevar una pieza modelada al dominio procedural y continuar con Transform, Merge, Color,
Normals y To Static.

## Mesh Along Curve

El nodo tiene dos entradas de naturaleza distinta que el Graph ya puede representar:

- pin principal `S`: la curva;
- pin lateral `asset` de tipo `A`: el StaticMesh que se repite;
- salida `M`: una única malla combinada.

Parámetros:

| Parámetro | Función |
|---|---|
| `count` | cantidad de copias, 1–512 |
| `start`, `end` | intervalo normalizado sobre la longitud, 0–1 |
| `radial_offset` | distancia desde el eje de la curva |
| `turns` | vueltas completas alrededor de la curva |
| `angle_offset` | fase inicial en grados |
| `scale_start`, `scale_end` | escala interpolada de inicio a fin |
| `scale_x/y/z` | proporción independiente en los ejes locales del asset |
| `orientation` | normal `outward`, `world_up` o `random` |
| `rotation/scale/offset_jitter` | variaciones reproducibles por frame |
| `seed` | semilla de toda la variación |
| `crossed`, `double_sided` | tarjetas cruzadas y reverso geométrico |
| `samples` | resolución al leer un SplineComponent |

Los puntos se remuestrean por distancia acumulada, no por índice de la polilínea. Cada frame construye
una base ortonormal estable: X sigue la tangente y Z mira radialmente hacia afuera. En tangentes casi
verticales cambia el vector de referencia para evitar un producto cruzado nulo. Toda la aleatoriedad
usa un generador local con seed: no depende del orden global de Python ni cambia entre Runs.

## Hallazgo de arquitectura

El Graph actual admite una entrada principal rica y un pin Asset lateral, pero todavía no permite un
nodo arbitrario con dos streams ricos, por ejemplo `P + M → M`. Por eso no se expuso todavía el diseño
ideal `Curve Frames → P` + `Copy Mesh to Points(P, M)`.

`Mesh Along Curve(S, A)` no es un parche TreeGen: es un verbo general válido para hojas, escamas,
remaches, aisladores, baldosas, luces o módulos sobre una guía. El runner se amplió explícitamente para
mantener el stream principal `S` mientras inyecta el asset lateral, sin confundir ambos valores.

## Ejemplo TreeGen

`TreeGen-Branched-Tree.jamgraph` ahora contiene:

- 21 nodos y 30 cables;
- tres ramas `Curve Child` dependientes del tronco;
- cuatro ramas Pipe;
- cuatro operadores Along Curve;
- 72 frames y 288 tarjetas de hoja cruzadas/doble cara;
- sin copas-esfera provisionales: el volumen depende de las curvas;
- Vertex Color marrón/verde;
- ciclo Preview/Bake/Discard.

El nodo Asset informa un warning de pivote porque `/Engine/BasicShapes/Plane` tiene pivote central. Es
un diagnóstico correcto para Place, pero aquí el Plane se copia como geometría y el warning no afecta
la orientación ni el resultado.

## Validación

- Suite Python: **57/57 OK**.
- Pruebas puras de remuestreo, frame vertical, taper y giro helicoidal.
- Prueba del runner con stream rico principal + asset lateral.
- Unreal Engine 5.7.4: Compile correcto, 21 nodos evaluados, 0 errores.
- Los cuatro nodos Along Curve terminaron `ok`.
- Bake promovió el StaticMesh y Run + Discard posterior preservó lo horneado.
- El material lector de Vertex Color permaneció asignado.

## Siguiente paso TreeGen

`Curve Child` ya origina una hija desde un frame normalizado del padre. El paso siguiente es exponer
conjuntos de frames/curvas y habilitar entradas ricas múltiples para expresar generación repetida y
`Curve Frames(P) + Mesh From Asset(M) → Copy to Points(M)` sin fusionar responsabilidades.

## Archivos

- `Content/Python/jam/curve.py`: `CurveFrame`, remuestreo y frames.
- `Content/Python/jam/mesh.py`: conversión A→M y copias sobre S.
- `Content/Python/jam/graph.py`: asset lateral junto a entrada rica.
- `Content/Python/jam/tools.py`: registro y contratos de los nodos.
- `Resources/Examples/TreeGen-Branched-Tree.jamgraph`: ejemplo con hojas.
- `Content/Python/tests/test_mesh.py`: geometría y frames.
- `Content/Python/tests/test_graph_preflight.py`: transporte runtime de ambas entradas.

## Relacionado

- [[2026-07-26-INFORME-TreeGen-Curvas-Pipe-Arbol-Ramificado-v1.0|TreeGen: curvas, Pipe y árbol]]
- [[2026-07-26-INFORME-Nodo-Mesh-Color-Vertex-Color-v1.0|Nodo: Mesh Color y Vertex Color]]
- [[2026-07-26-INFORME-Graph-Tab-Mesh-Verbos-Malla-v1.0|Tab Mesh y verbos de malla]]
- [[2026-07-26-INFORME-TreeGen-Curve-Child-Ramas-Jerarquicas-v1.0|TreeGen: Curve Child]]
- [[2026-07-26-INFORME-TreeGen-Follaje-Procedural-Variacion-v1.0|TreeGen: follaje procedural]]
