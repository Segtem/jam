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

## Inventario (2026-09-30)

- `inventario-graph-agy1.md`: el Graph de C++, **104 capacidades** — en el web 24 sí, 16 parcial, 64 no.
- `inventario-resto-agy2.md`: Dash Bar, Content, CLI, presets, menús, viewport — **39 capacidades**, 5
  sí; 7 dependen del viewport o de la selección de Unreal (punto de mira, pick, gizmo, fantasma,
  actores seleccionados): el web las pide al motor por la API.
- `base-api-codex.md`: las **29 funciones de `jam.api`** que llama el C++; sólo 4 están con el mismo
  nombre en `web.API_PUBLICA` y 0 en `servidor.Nucleo.PUBLICAS`.
- `base-litegraph-codex.md` y `base-recomendacion-codex.md`: **se sigue con LiteGraph** (el vendorizado,
  envuelto), `editor.js` partido en módulos ES nativos sin build; Rete queda de reserva. Lo que falla
  de base: abrir/guardar pierde comentarios, compacto, debug y vías; no hay Deshacer; copiar/pegar
  puede pisar nodos.

## Fases

1. **Documento sin pérdida, módulos y Deshacer** (JS): el `.jamgraph` va y vuelve entero; editor.js en
   módulos; historial por gesto; copiar/pegar/duplicar con nombres nuevos.
2. **Contrato común** (Python): las 29 funciones del C++ en la API pública de `web.py` y
   `servidor.Nucleo` —las mismas en los tres motores cuando se pueda; las de Unreal, declaradas—.
3. **Content y pedidos al motor**: navegador de assets con miniaturas por URL, pick, punto de mira,
   selección de actores.
4. **Paridad del canvas**: etiquetas de pines, compacto multipin, vías, comentarios, atajos, perillas y
   tiradores, funciones (Ctrl+G, editar firma), presets, preview 2D, panel de ejecución.
5. **Dash/CLI y retiro**: línea de comandos con historial, fantasma y gizmo; Brian recorre el web;
   el menú de Unreal abre sólo el web y el C++ se borra en un commit propio.

## Próximo paso

Fases 1 (Codex) y 2 (agy1) en paralelo, y la parte Python de la 3 (agy2: assets y miniaturas).
