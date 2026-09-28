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

## Dos de tres propuestas, versión 1 (2026-09-27, sin el criterio 11)

agy ([agy.md](investigacion/agy-v1.md), gemini-3.8-flash-high en contenedor) y un agente Claude sin
contexto ([claude.md](investigacion/claude-v1.md)). Codex vuelve el 2026-09-30. Lo verificado contra el
árbol está marcado; el resto es lo que cada uno afirma.

| criterio | agy | Claude |
|---|---|---|
| forma | un nodo por bloque: `nombre: verbo [flags]` y un atributo `pin = valor` por línea indentada | un nodo por línea: `nombre: verbo [asset] @entradas clave=valor +flags` |
| 1 · ida y vuelta | define «el mismo grafo»; pero imprime floats con `.6g` → **pierde precisión**, grafo→texto→grafo no es exacto | forma normal N(g) explícita (defaults llenados, tipos por pin, literal de pin cableado descartado, cables como conjunto salvo variádicos); `repr` sin pérdida |
| defaults | dice omitirlos, pero sus transcripciones los escriben (`start = 0.0` es el default de `series_range`, medido) | los omite; transcripciones calculadas contra REGISTRO (`view=true` en place: default False, medido) |
| 2 · cobertura | ejemplo propio con errores: `matrix_construct` **no existe**; `descomp.traslacion` no es una salida extra (lo es el principal); `mesh_simplify_count` no tiene `target_count` (medido) | ejemplo propio válido: todos los verbos y pines existen, incluidos `traslación`/`ángulo` Unicode y `@partes.eje_z` (medido); resuelve funciones por etiqueta con fallback a id |
| 3 · escribible por un LLM | verboso (un atributo por línea) | compacto; la ayuda se genera en la misma sintaxis (`firma(verbo)`) |
| 4 · nombres legibles | slug del verbo + sufijo | ídem, sin renombrar nunca lo existente; F2 para renombrar |
| 5 · diffs | el orden topológico se desempata **por posición x/y**: mover un nodo reordena el texto | postorden desde sumideros: un param o una inserción cambian sólo sus líneas; un recableado puede mover líneas (declarado) |
| 6 · consola | la línea vieja sigue por el camino histórico | ídem, y distingue comando (compone place) de nodo en documento |
| 7 · layout | en el texto (bloque `layout:` y `comment`): arrastrar ensucia el diff | fuera del texto, unido por nombre; reindexa `reroutes`; propone buzón C++ para escritor externo |
| 8 · literales ricos | `(x, y, z)`, `matrix(…16…)` | tuplas; tipo por pin, sin atajo de matriz |
| 9 · implementación | ~1055 líneas; propone `layout_core.py` nuevo aunque `layout.auto` ya existe (layout.py:137) | ~500 + 350 tests + 60 api + 250 C++; reusa `layout.auto` |
| 10 · forma única | sí | sí, con un superconjunto de entrada enumerado que el formateador normaliza (como Oracle) |
| hechos | varias citas imprecisas | cifras correctas: REGISTRO 171, VALORES 69, OPS 101, **88** verbos que exigen cable (la auditoría decía 86) — medido |

Encontrado de paso por Claude, a verificar: `compilar` nombra un nodo de valor `name or nid`
(graph.py:477) y `math_core.resolver` usa el default `"n"` (math_core.py:1399).

### Nota (2026-09-28 01:56:08 UTC)

2026-09-27, Claude: por pedido de Brian, el pedido suma el criterio 11 (núcleo fuera del motor: el grafo y el DSL no importan unreal, sobre un registro neutro con capacidades por motor; ver fuera-del-motor) y el entregable g lo cubre. Las dos respuestas de arriba son la versión 1, sin ese criterio: se relanzan agy y un Claude nuevo con el pedido actualizado, y Codex (2026-09-30) recibe el mismo.

## Próximo paso

Juntar agy.md y claude.md (con el criterio 11) y codex.md (2026-09-30), rehacer la tabla por criterio y proponérsela a Brian, que elige.
