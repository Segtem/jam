# Mudar al editor web todo lo construido en C++ (Slate): una sola interfaz

- ESTADO: ABIERTA
- PRIORIDAD: 97
- ETIQUETAS: arquitectura, web, graph, decision

## Por qué

2026-09-30, DECISIÓN de Brian: **una sola interfaz, la web**. Hasta hoy convivían el Graph de C++
(Slate, ~10.000 líneas en `Source/JamEditor/`, sólo Unreal) y el editor web (`Content/Python/jam/web/`,
LiteGraph, ~450 líneas, abierto desde Unreal, Godot y Unity). Mantener las dos es hacer cada cosa dos
veces —ya pasó: las etiquetas de `etiquetas-pines` quedaron arregladas sólo en C++— y revisar dos.
Con una sola, Brian revisa una sola cosa, y es la misma en los tres motores y la misma que usa un
agente.

## Reglas mientras dura la mudanza

- El C++ queda **congelado**: ninguna función nueva; sólo arreglos que bloqueen el uso de hoy.
- Todo lo nuevo de interfaz va al web.
- La lógica sigue en el núcleo Python (`jam.api`, `jam.registro`, `jam.graph`…): el web habla el mismo
  contrato que usaba el C++ (`LlamarApi` / `ExecPythonCommandEx` → `POST /api/<función>`).
- Cuando el web tenga lo que se usa del C++, se declara deprecado y se saca del menú (el código se
  borra en un commit propio, recuperable).

## Criterio de hecho

El inventario de lo que hace la interfaz de C++ (Graph, Dash Bar, Content, paneles, perillas,
tiradores, menús) está entero, cada fila tiene su equivalente en el web verificado por el camino real
(sonda con el web abierto y Brian mirando lo visual), y el menú de Unreal abre sólo el web.

## Próximo paso

Inventario en paralelo (agy1: el Graph; agy2: el resto del C++; Codex: LiteGraph y el contrato con
`jam.api`), y después el plan por fases.
