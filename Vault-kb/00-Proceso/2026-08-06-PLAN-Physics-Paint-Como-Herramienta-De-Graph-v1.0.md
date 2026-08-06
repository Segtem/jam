---
title: "Physics Paint como herramienta creada en Graph"
tipo: PLAN
version: "1.0"
date: 2026-08-06
updated: 2026-08-06
status: propuesta
area: 00-Proceso
tags:
  - jam
  - graph
  - dash
  - gizmo
  - physics
  - herramientas
aliases:
  - Physics Paint de Jam
  - Gizmo pincel
---

# Physics Paint como herramienta creada en Graph

**La meta:** construir desde el Graph una herramienta equivalente al *Physics Paint* de Dash —
pintar objetos que se asientan físicamente— y que después se use desde la Dash Bar. Es el caso de
prueba de [[2026-08-06-CONCEPTO-Graph-Autoria-Dash-Consumo-v1.0]].

## Qué hace falta, contra lo que ya hay

| Pieza de la herramienta | Estado |
|---|---|
| Lista de assets de entrada | ✅ `asset_set` produce `A[]`; `choose_asset` elige variante |
| Asentar con física | ✅ `place` tiene `physics` |
| Colisión, hundido, escala mín/máx | ✅ params de `place` (`surface`, `sink`, `scale_min/max`) |
| Cantidad y distribución | ✅ `scatter` produce `P` con patrón, área y máscaras |
| Parámetros expuestos en la ficha | ❌ una función expone PINES, no perillas |
| **El pincel** | ❌ — ver abajo |

O sea: **el «qué» y el «cómo» ya están**. Falta el «dónde» interactivo y las perillas.

## El corte que importa: declarativo vs. interactivo

Un grafo de Jam es **declarativo**: se configura y se corre. El Physics Paint de Dash es
**interactivo**: se arrastra un pincel por el viewport y va sembrando.

Jam hoy **lee** el viewport (`ue.punto_de_mira()` hace un raycast desde la cámara) pero **no lo
escucha**: no hay `FEdMode` ni captura de input en `Source/`. Un trazo de pincel no puede llegar.

La salida no es volver interactivo al grafo, sino **separar las responsabilidades**:

- el **grafo** decide QUÉ se coloca y CÓMO (assets, física, escala, colisión) — ya funciona;
- el **gizmo** decide DÓNDE — es un dispositivo de entrada que produce `P`.

Con eso el gizmo es sólo *otra fuente de puntos*, exactamente como `scatter`. El grafo no cambia de
naturaleza.

## Dos caminos para el pincel

### A. Gizmo-actor (barato, sin código de interacción)

El pincel es un **actor** en el nivel que se mueve con el gizmo de transformación de Unreal. Un
verbo `brush` lee su transform y su radio y produce `P` alrededor. Se posiciona, se corre, se
estampa; se mueve, se vuelve a correr.

- **No es pintar**: es estampar. Pero da el 80 % del valor sin una línea de código de input.
- Reusa todo: `scatter` para la distribución dentro del radio, `place` para la física.
- Encaja con el `gizmo` que ya existe (hoy sólo marca dónde está parado Jam).

### B. Modo de editor (`UEdMode`, el camino real)

Un modo propio con captura de clic, arrastre, hover y previsualización del pincel. Es lo que hace
Dash. Da el trazo continuo de verdad.

- Costo alto: es un subsistema nuevo en C++, y **nada de eso se puede verificar headless**.
- Sólo vale la pena si A demuestra que la herramienta rinde.

> [!important] Recomendación
> **Empezar por A.** Si estampar con un radio ya resuelve el trabajo, el modo de editor puede no
> hacer falta nunca. Y si hace falta, se llega con la herramienta ya definida y probada, que es la
> parte que no se puede saltear.

## Orden

1. **Parámetros expuestos** en la firma de una función (`funcion.py` + `preset.py`, puro cerebro).
   Sin esto la herramienta es un botón sin perillas, y hace falta igual para cualquier tool.
2. **Verbo `brush`**: fuente que produce `P` a partir de un actor-gizmo (radio, cantidad, semilla).
3. **Armar la herramienta en el Graph** y colapsarla: `brush → scatter → choose_asset → place`.
4. **Publicarla** y que la Dash la muestre con sus perillas.
5. *(sólo si hace falta)* modo de editor para trazo continuo.

Los pasos 1 y 2 son puro cerebro y se testean sin motor. El 3 es un grafo, no código.

## Relacionado

- [[2026-08-06-CONCEPTO-Graph-Autoria-Dash-Consumo-v1.0]]
- Referencia: `docs.polygonflow.io/how-it-works/physics-tools`
