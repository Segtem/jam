# El DSL no puede describir un grafo: no hay cables ni nodos con nombre, y no hay ida y vuelta con el canvas

- ESTADO: ABIERTA
- PRIORIDAD: 95
- ETIQUETAS: dsl, graph, llm, commander


## Por qué

Auditoría de [`dsl-llm`](../20260924-114746-dsl-llm/AUDITORIA.md), §1–3 y nivel 1: `dsl.parsear` lee
una línea por vez (`verbo [asset] [clave=valor]`), sin forma de conectar la salida de un verbo con la
entrada de otro. Eso deja 86 verbos fuera del alcance de un LLM: mallas, curvas, frames, materiales,
Mass y todo el flujo de puntos. Además, lo que corre por `api.run` no aparece en el canvas, y nada
convierte un `JamGraph` en DSL: el LLM y el humano trabajan sobre cosas distintas.

## Qué hacer

1. **Diseño primero, sin código**, con tres modelos a ciegas (Codex, agy, Claude), como se decidió en
   Oracle `repo-limpio`. El DSL de grafos tiene que ser una **superficie legible del mismo
   `JamGraph`**: nodos con nombre (no `n1`), cables por nombre de pin, parámetros tipados (vectores,
   dominios, matrices). Tiene que existir una conversión exacta en los dos sentidos (DSL → grafo →
   DSL da el mismo texto; grafo → DSL → grafo da el mismo grafo). Antecedente: la superficie infija
   de Oracle, que se lee tal cual como la forma canónica, con ida y vuelta verificada.
2. Después, implementar: `dsl → JamGraph` (lo que escribe el LLM aparece como nodos) y
   `JamGraph → dsl` (lo que edita el humano se lee como texto), con la ida y vuelta como test.
3. La consola de una línea sigue funcionando como caso particular.

### Nota (2026-09-28 01:45:28 UTC)

2026-09-27, Claude: pedido de diseño escrito en investigacion/pedido.txt: el mismo texto para los tres, a ciegas entre sí, con diez criterios escritos para elegir (ida y vuelta exacta y qué es «el mismo grafo», cobertura del modelo entero, escribible por un LLM, legible en el canvas, diffs limpios, la consola de una línea como caso particular, dónde vive el layout, literales ricos coherentes con texto_de_valor, cerebro puro, una sola forma canónica) y entregables comparables: gramática, Cylinder-Strip y TreeGen-Curve-Frames transcritos enteros, un ejemplo propio con multi-salida, valor cableado, expresión, función y bypass, reglas del impresor, errores con línea, integración con api.run/canvas/MCP y la alternativa descartada. Lanzados: agy (gemini-3.8-flash-high) en contenedor agy-naval sobre una copia git archive de HEAD, y un agente Claude nuevo sin el contexto de esta sesión. Codex (gpt-6-sol) vuelve el 2026-09-30.

## Próximo paso

Juntar las tres respuestas en investigacion/ (agy.md, claude.md, codex.md; Codex el 2026-09-30), armar la tabla por criterio y proponérsela a Brian, que elige.
