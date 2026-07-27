---
title: "TreeGen: Copy Mesh to Frames A + F a M"
aliases:
  - "Copy Mesh to Frames"
tags:
  - jam
  - graph
  - treegen
  - frames
  - foliage
  - static-mesh
status: implementado
date: 2026-07-27
---

# TreeGen: Copy Mesh to Frames A + F a M

## Resultado

Se implementó **Copy Mesh to Frames `A + F → M`**. El nodo recibe una Static Mesh por el pin lateral
`asset`, un `FrameSet` por `in`, copia el asset una vez por frame y combina las copias en una
`DynamicMesh` transitoria.

```text
Asset A ───────────────┐
                      ▼
Frames F ───→ Copy Mesh to Frames ───→ Mesh M
```

Es el primer consumidor modular para follaje, frondas, corteza y piezas prefabricadas. A diferencia
de `Mesh Along Curve`, no vuelve a samplear una spline ni genera su propia variación: usa exactamente
los transforms preparados por `Curve Frames`, `Distribute Frames` y `Transform Frames`.

## Contrato de orientación

Por cada frame:

- el eje local `X` del asset se alinea con `frame.tangent`;
- el eje local `Z` se alinea con `frame.outward`;
- la posición se toma de `frame.position`;
- con `inherit_scale=true`, la escala uniforme incluye `frame.scale`.

La alineación usa `make_rot_from_xz`, la misma convención utilizada por los nodos de hojas existentes.

## Corrección propia del asset

Antes de copiar se puede corregir la malla fuente sin modificar el asset original:

- `asset_offset_x/y/z`: corrige un pivot inconveniente;
- `asset_pitch/yaw/roll`: adapta assets cuyo eje frontal no es `+X`;
- `asset_scale`: tamaño uniforme base;
- `scale_x/y/z`: corrección anisotrópica;
- `inherit_scale`: decide si se multiplica por `frame.scale`.

La corrección de offset y rotación se aplica una sola vez sobre la `DynamicMesh` plantilla. Después se
realizan las copias, evitando releer la Static Mesh por cada frame.

## Preflight y límites

- Entrada principal requerida: `F`.
- Entrada lateral requerida: `asset` de tipo `A`.
- Salida: `M`.
- Sin cable `A`, Compile detiene el graph con `requiere asset explícito`.
- Escalas cero, negativas o no finitas son rechazadas.
- Un frame con escala inválida también detiene el nodo.
- Máximo: 4096 copias por evaluación.

## Ejemplo actualizado

El ejemplo **File → Abrir ejemplo: frames de TreeGen** ahora posee 16 nodos y combina dos ramas de
geometría:

```text
Curve → F → Distribute → Transform ───────→ Branch From F → Branch Pipe ─┐
                         │                                                ├→ Wood Color ─┐
                         └─ PineFrond A → Copy Mesh to Frames → Green ────┘               │
Curve ────────────────────────────────────────────────→ Trunk Pipe ────────────────────────┤
                                                                                          ▼
                                                        Final Merge → Normals → Static → Place
```

Madera y follaje reciben Vertex Colors diferentes antes del merge final.

## Validación real en Unreal 5.7

El graph completo se ejecutó en `BotOOEditor`:

- Compile: **16 nodos correctos**.
- `PineFrond`: resuelto como `/Game/Examples/Meshes/PineFrond.PineFrond`.
- Copy Mesh to Frames: **18 copias y 1.098 vértices**.
- Ramas: 18 sweeps y 1.386 vértices.
- Árbol final: **2.688 vértices**.
- Static Mesh temporal y actor de preview creados correctamente.
- Discard eliminó 1 actor y 1 asset temporal.
- Se comprobó que el archivo temporal ya no existe después de cerrar Unreal.

Suite automatizada:

- **77/77 pruebas Python correctas**.
- Orientación, posición, escala heredada y corrección de asset cubiertas.
- Runtime `F + A → M`, spec de pines y falta de asset cubiertos.
- JSON, mapa de iconos y `git diff --check` correctos.

## Hallazgo sobre PineFrond

El oráculo detectó que `PineFrond` posee un pivot descentrado: aproximadamente `x 42%`, `y 96%` y
`83%` de la altura de su bounding box. La copia funciona, pero su apoyo visual puede requerir ajuste.

Opciones seguras:

1. ajustar `asset_offset_x/y/z` sólo en este nodo;
2. crear una copia normalizada del asset si se quiere corregirlo globalmente;
3. conservar el pivot original cuando éste haya sido diseñado para animación o Pivot Painter.

No se modificó `PineFrond` durante esta implementación.

## Continuación implementada

- La salida combina geometría en una `DynamicMesh`; todavía no existe el modo HISM.
- El nodo original conserva su contrato simple `A + F → M`.
- Para variantes ya existen `Asset Set A… → A[]`, `Choose Asset F + A[] → AF` y
  `Copy Variants AF → M`.
- La variación se prepara aguas arriba con `Transform Frames`; esto es intencional para no esconder
  nuevamente el flow dentro de un nodo monolítico.

## Próximo corte

El corte siguiente también quedó implementado como **Graph Curve `N[]`** y
**Pipe with Profile `S + N[] → M`**. Véase
[[TreeGen - Graph Curve N array y Pipe with Profile]]. La selección de variantes está cubierta en
[[TreeGen - Asset Set Choose Asset y Copy Variants]].

## Relacionado

- [[TreeGen - Curve Frames y contrato FrameStream F]]
- [[TreeGen - Transform Frames F]]
- [[TreeGen - Branch From Frames F a S]]
- [[TreeGen - Asset Set Choose Asset y Copy Variants]]
- [[TreeGen - Graph Curve N array y Pipe with Profile]]
- [[TreeGen - auditoria de Blueprints funciones y flow real]]
- [[TreeGen - Mesh Leaf con StaticMesh opcional]]
