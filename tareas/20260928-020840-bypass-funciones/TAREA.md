# Un grafo con una función pierde todos sus bypass al expandirse

- ESTADO: CERRADA
- PRIORIDAD: 80
- ETIQUETAS: graph


## Por qué

Lo encontró el agente Claude del diseño de `dsl-grafos` (2026-09-27) y se verificó leyendo el código:
`funcion._copiar` copiaba `verb`, `params`, `asset`, `x`, `y` y `debug`, pero no `bypass`. Cuando el
grafo tiene al menos una instancia `fn:`, `expandir_json` reconstruye TODOS los nodos con `_copiar`
(los de afuera y los del cuerpo), así que cada nodo apagado volvía a correr en Compile y Run. Sin
instancias, `expandir_json` devuelve el JSON tal cual y no pasaba. `colapsar` usa la misma función.

### Nota (2026-09-28 02:08:40 UTC)

2026-09-27, Claude: hecho. _copiar lleva bypass. Test test_expandir_conserva_el_bypass_afuera_y_adentro_del_cuerpo en test_funcion.py: rojo sin el arreglo («el bypass de afuera se perdió»), verde con él. Suite 1259 OK; oracle test VERDE (28/4/3, 1099, 448/448). Es cerebro puro: api → funcion.expandir_json → graph, sin motor en el medio.

## Próximo paso

Ninguno.
