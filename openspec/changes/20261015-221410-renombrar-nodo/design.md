# Design

- `web/renombrar.js` exporta `renombrar(nodo, nuevo, usados)`: devuelve `{ok, error, cambios}` sin
  tocar el DOM ni LiteGraph. `cambios` dice qué propiedades cambian (`nombre`, y `name` del valor si
  hace falta). Se carga en `editor.html` antes de `editor.js` y en `node` con `require`.
- El editor escucha `keydown` en el canvas: F2 con un solo nodo seleccionado abre el diálogo.
- Un nodo es de valor si su verbo está en `VALOR_KINDS` del spec del editor (`spec_editor`).
- `tools/emitir_hechos_pruebas.py --cambio ID --casos modulo.Clase.test_x ... --salida RUTA` corre
  los casos con `unittest` (con el `PYTHONPATH` de `Content/Python`) y escribe
  `{"prueba_caso": [{"requisito", "caso", "codigo"}], "prueba_corrida": [{"completa", "casos"}]}`.
