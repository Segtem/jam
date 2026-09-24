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

## Próximo paso

El pedido del diseño para los tres modelos.
