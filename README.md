# Jam

**Toolbox privado de gamedev para Unreal, con oráculo.**

Jam es un plugin de Unreal Engine — un asistente in-editor al estilo de
[Dash (PolygonFlow)](https://polygonflow.io) para incorporar y crear cosas dentro del motor —
pero con una diferencia: **todo lo que produce lo verifica un oráculo determinista**. Crear libre
con la mejor herramienta, medir desde afuera (anti-Goodhart).

No es un producto para terceros: es la herramienta con la que construyo mi juego.

## El juego: BotOO — *Bounty of the Old Ones*

Un **Hunt: Showdown** lovecrafteano de **época 1920**, con la fidelidad visual de **The Order: 1886**.
Extracción **PvPvE**: rastrear pistas → jefe (horror cósmico) → **extraer**. 12 jugadores, equipos
de 1-2-3. Vive en su propio repo: `Brianholl/BotOO`.

## Motor

UE **5.7.4** hoy (el que anda); migración a **5.8.1** cuando funcione en esta máquina.

## Estructura

```
oraculo/    Verificadores engine-agnósticos (lo único rescatado del viejo monorepo).
            - mazes/       grafo del espacio, BFS, canales, jerarquía, PCG
            - qa/          winnability (¿es ganable?)
            - foundry/     obj_oracle (topología de malla)
            - shape_dsl/   oráculo de Shape
```

## Historia

Jam nace el 2026-07-20 de una limpieza: el monorepo `jamprotocol` (DSL + receptores Godot/Babylon +
pipeline Houdini/Substance) se archivó entero en `Segtem/jamprotocol` y se retiró. De él sobrevive
**sólo el oráculo**, como semilla. Todo lo demás se rehace fresco, ahora Unreal-only y como plugin.
