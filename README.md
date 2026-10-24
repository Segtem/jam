# Jam

**Toolbox privado de gamedev para Unreal, con oráculo.**

Jam es un plugin de Unreal Engine — un asistente in-editor al estilo de
[Dash (PolygonFlow)](https://polygonflow.io) para incorporar y crear cosas dentro del motor —
pero con una diferencia: **todo lo que produce lo verifica un oráculo determinista**. Crear libre
con la mejor herramienta, medir desde afuera (anti-Goodhart).

No es un producto para terceros: es la herramienta con la que construyo mi juego.

**En otra máquina:** ver [`INSTALAR.md`](INSTALAR.md) — `python tools/instalar.py <proyecto>` para Unreal, Godot o Unity.

## Cambios con Oracle Factory

Los cambios nuevos de Jam se llevan con [Oracle Factory](https://github.com/Segtem/oracle-factory):
propuesta y spec, requisitos, medidas, revisión, juicio de Oracle y cierre. El proyecto Oracle de
Jam está en `medidas/`; sus verificadores, sensores y requisitos anteriores siguen usando ese catálogo.
El flujo y las versiones usadas en este proyecto están en [AGENTS.md](AGENTS.md).

El agente trabaja con su nombre (`--agente codex` o `--agente claude-code`). En el modo
`confirmacion`, Brian confirma las propuestas y decide el cierre desde su terminal.
El [tablero de VS Code](https://github.com/Segtem/oracle-factory/blob/main/docs/tablero.md) permite
seguir pendientes, evidencia y responsables, y colaborar con Live Share.

Las guías actuales de Factory explican también el
[conocimiento del proyecto](https://github.com/Segtem/oracle-factory/blob/main/docs/conocimiento.md)
(base derivada del registro, notas humanas, consultas con citas y origen de decisiones) y el
[trabajo de agentes](https://github.com/Segtem/oracle-factory/blob/main/docs/agentes.md).
Las respuestas elaboradas requieren configurar un modelo por proyecto; el MCP de Factory ofrece
consultas de sólo lectura. Las capacidades disponibles corresponden a la versión de Factory instalada.

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
