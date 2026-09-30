# Verificar con Brian: los verbos no disponibles se ven deshabilitados con su porqué (ribbon y búsqueda)

- ESTADO: CERRADA
- PRIORIDAD: 58
- ETIQUETAS: gestos


## Por qué

`fuera-del-motor` (ef5bac7) dejó los verbos que el motor no tiene VISIBLES pero deshabilitados, con
su porqué, en vez de esconderlos (decisión de Brian). En C++: `FJamTool::bDisponible`, las fichas del
ribbon con `IsEnabled(false)` y tooltip `NO DISPONIBLE en este motor: <porqué>`, y lo mismo en la
búsqueda (Tab), donde Enter salta al primer resultado disponible. El binario compiló y
`verifica_registro_neutro_58` mide el spec, pero nadie lo vio dibujado. Salió al revisar
`verde_editor` (tarea `editor-vigente`, inventario de agy2).

## Qué hacer

En Unreal todo está disponible, así que hay que simular otro motor: abrir JamPlayground con
`JAM_MOTOR_SIMULADO=godot` en el entorno, abrir el Graph y:
1. Recorrer las pestañas del ribbon: las fichas de verbos sólo de Unreal (p. ej. Nanite, Mass) se
   ven atenuadas; el tooltip empieza con `NO DISPONIBLE en este motor:` y el porqué.
2. Hacer clic en una: no agrega nodo ni da error.
3. En el canvas, Tab y tipear un verbo no disponible: aparece en gris con el mismo tooltip; Enter
   no lo inserta (salta al primero disponible, si hay).

## Próximo paso

El gesto de Brian.

### Nota (2026-09-30 14:11:42 UTC)

2026-09-30: reemplazado por la decisión de Brian de una sola interfaz (tarea mudar-a-web). Este gesto revisaba la interfaz de C++, que queda congelada y se reemplaza; lo que verificaba se revisa UNA vez en el editor web, cuando esa capacidad llegue ahí (el inventario de mudar-a-web la incluye).
