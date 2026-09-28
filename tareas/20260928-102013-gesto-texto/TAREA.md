# Verificar con Brian: el texto del grafo en el canvas (nombres, panel ✎ Texto, Aplicar, buzón)

- ESTADO: ABIERTA
- PRIORIDAD: 70
- ETIQUETAS: gestos


## Por qué

`dsl-grafos`, tramo 3: el Graph muestra el texto del mismo grafo. Lo que se pudo verificar sin manos
está verificado (tests que atan el `.cpp`, y `verifica_texto_canvas_58.py`: lo que corre por
`api.run` aparece en el Graph abierto). Lo que se VE, no.

## Qué mirar (JamPlayground, Jam ▸ Graph)

1. **Nombres**: soltá un nodo (p. ej. «Soldar»): la cartela tiene que decir `mesh_weld · <etiqueta>`,
   y otro igual `mesh_weld_2`. En modo compacto, sólo el nombre. ¿Se lee? ¿Se corta?
2. **✎ Texto** (al lado de «★ Guardar como preset»): abre el panel a la derecha con el grafo escrito.
   Cambiá un parámetro en un nodo → la línea cambia sola.
3. **Aplicar**: escribí en el panel (p. ej. `x = mesh_box size_x=300`) y «Aplicar» → aparece el nodo;
   Ctrl+Z lo deshace en UN paso. Con un error (`@noexiste`), abajo dice la línea y el canvas no cambia.
4. **● sin aplicar**: tipeá sin aplicar y mové un nodo: lo tipeado no se pisa.
5. **Buzón**: con el Graph abierto, en la consola de Python del editor:
   `import jam.api as a; a.run("c = mesh_box\nn = mesh_normals @c")` → aparece en el canvas.

## Próximo paso

El gesto de Brian.
