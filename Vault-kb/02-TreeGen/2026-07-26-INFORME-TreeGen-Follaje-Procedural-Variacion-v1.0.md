---
title: "TreeGen: follaje procedural con variación"
tipo: INFORME
version: "1.0"
date: 2026-07-26
updated: 2026-07-26
status: historico-superado
superseded_by: "[[2026-07-26-INFORME-TreeGen-Replica-Jerarquica-Branch-Leaf-v1.0|TreeGen: réplica jerárquica de Branch y Leaf]]"
area: 02-TreeGen
tags:
  - jam
  - graph
  - treegen
  - foliage
  - variation
  - seed
---

# TreeGen: follaje procedural con variación

> [!warning] Implementación histórica
> Este documento describe el experimento con `Plane + Mesh Along Curve` que produjo los listones de
> `ScreenShot00007.png`. El ejemplo incluido ya fue reemplazado por `Curve Branches + Mesh Leaf`.
> Consultar [[2026-07-26-INFORME-TreeGen-Replica-Jerarquica-Branch-Leaf-v1.0|TreeGen: réplica jerárquica de Branch y Leaf]] para el estado vigente.

## Resultado

`Mesh Along Curve` dejó de producir únicamente copias uniformes. Ahora puede construir follaje
alargado, orientado y variable de manera determinista, sin crear actores por hoja.

El ejemplo `TreeGen-Branched-Tree` eliminó las cuatro copas-esfera provisionales observadas en la
captura de prueba. El follaje visible proviene completamente de las curvas del tronco y las ramas.

```text
Plane A ─────────────────────────────┐
                                    ├→ Mesh Along Curve → follaje M
Trunk/Curve Child S ─────────────────┘
```

## Parámetros añadidos

| Parámetro | Función |
|---|---|
| `scale_x/y/z` | proporción local independiente además del taper start/end |
| `orientation` | `outward`, `world_up` o `random` |
| `rotation_jitter` | variación angular máxima alrededor de la tangente |
| `scale_jitter` | variación proporcional de escala, entre 0 y menos de 1 |
| `offset_jitter` | desplazamiento aleatorio perpendicular a la curva, en cm |
| `seed` | hace repetible la distribución aleatoria |
| `crossed` | agrega una segunda tarjeta rotada 90° en el mismo frame |
| `double_sided` | agrega geometría con winding inverso para verla desde ambos lados |

El eje X local del asset continúa siguiendo la tangente. Con el Plane de Engine, `scale_x=1.6` y
`scale_y=0.42` convierten el cuadrado original en una hoja estrecha. `random` gira su normal alrededor
de la rama; la semilla garantiza que dos Run consecutivos produzcan exactamente el mismo árbol.

`crossed + double_sided` genera cuatro copias por frame: dos tarjetas perpendiculares y el reverso de
cada una. Esto evita que el follaje desaparezca al observarlo de perfil o desde atrás, aun usando el
material provisional de Vertex Color.

## Ejemplo actualizado

- 21 nodos y 30 cables.
- 20 + 18 + 18 + 16 = **72 frames** de follaje.
- Cuatro copias por frame = **288 tarjetas** combinadas en una sola DynamicMesh.
- Cuatro seeds distintas para tronco y ramas.
- Escala no uniforme, jitter de rotación/escala/posición y orientación random.
- Sin copas `Mesh Sphere` ni transforms mundiales para simular volumen.
- Tamaño generado aproximado: 500 × 468 × 660 cm.

El Plane continúa siendo un placeholder. Sustituir el nodo Asset por una hoja modelada mantiene toda
la distribución, pero puede requerir ajustar sus ejes locales y `scale_x/y/z`.

## Validación

- Suite Python: **57/57 OK**.
- Regresión de seed: dos ejecuciones generan transforms idénticos.
- Regresión de tarjetas crossed + double-sided: ocho copias para dos frames.
- Validación de orientation y límites de jitter.
- Unreal Engine 5.7.4: 21 nodos evaluados, 20 `ok`, un warning informativo y cero errores.
- Los cuatro nodos Along Curve terminaron `ok`.
- Preview, Bake y Run + Discard conservaron correctamente el asset horneado.
- Vertex Colors y `/Engine/EngineDebugMaterials/VertexColorMaterial` permanecieron asignados.
- `BuildPlugin` Linux: **BUILD SUCCESSFUL**.
- Paquete: `/tmp/jam-plugin-treegen-foliage-20260726`.

## Pendiente visual

- usar una malla de hoja real con forma/UV en lugar del Plane;
- material de follaje Masked, Two Sided y con textura;
- variación o selección ponderada entre varias especies de hoja;
- ramificación múltiple para aumentar la densidad en los extremos;
- Pivot Painter o alternativa para viento.

## Archivos

- `Content/Python/jam/mesh.py`: transforms, orientación, jitter y duplicación de tarjetas.
- `Content/Python/jam/tools.py`: parámetros, dropdown de orientación y defaults.
- `Resources/Examples/TreeGen-Branched-Tree.jamgraph`: configuración de 72 frames.
- `Content/Python/tests/test_mesh.py`: seed, proporción, crossed y double-sided.

## Relacionado

- [[2026-07-26-INFORME-TreeGen-Curve-Child-Ramas-Jerarquicas-v1.0|TreeGen: Curve Child]]
- [[2026-07-26-INFORME-TreeGen-Mesh-From-Asset-Along-Curve-v1.0|TreeGen: Mesh From Asset y Mesh Along Curve]]
- [[2026-07-26-INFORME-TreeGen-Curvas-Pipe-Arbol-Ramificado-v1.0|TreeGen: curvas, Pipe y árbol]]
