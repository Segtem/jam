# Las sondas que certifican verde_editor tienen agujeros de discriminación

- ESTADO: ABIERTA
- PRIORIDAD: 70
- ETIQUETAS: verificacion

## Qué se sabe

Codex revisó (2026-09-29, tarea `editor-vigente`) las cuatro sondas de la certificación de
`verde_editor`: siguen compatibles con el código de hoy —sus archivos no cambiaron desde `d207caf` y
las APIs conservan firma—, así que un verde significa lo mismo que en agosto. Pero ya entonces
podían dar falsos verdes:

- `verifica_matrices_58`: `corrio_limpio({"nodes": {}})` da True (también un resultado sólo con
  nodos `cancelado`); la sección 4 mide largos y no ve signo, orientación ni ejes cruzados; las
  secciones 6 y 7 van por Flow (`panel.ejecutar_flow_json`), no por el Graph.
- `verifica_multi_salida_58`: `"80" in reporte` acepta `-80`; promete Inspector y no lo llama.
- `verifica_funcion_graph`: nunca ejecuta la función, sólo ABM y Compile.
- `verifica_ejemplos`: un catálogo vacío da TODO VERDE; no recorre los `.jam` de `tools/vitrina/`
  (el editor web lista 22, «Aprender» 19).

El detalle y los diffs propuestos, en `codex-revision.md` (su respuesta entera).

## Qué hacer

Aplicar los refuerzos de a una sonda, cada uno con su mutante que antes pasaba y ahora no, y
correrlos en JamPlayground y BotOO.

## Próximo paso

Empezar por `corrio_limpio` (el de mayor alcance).
