# Verificar con Brian: el menú de Unreal abre el editor de nodos web en su propia ventana

- ESTADO: ABIERTA
- PRIORIDAD: 58
- ETIQUETAS: gestos


## Por qué

`fuera-del-motor` (9dc3002) cambió el ítem del menú de Unreal a «Jam: editor de nodos (web)»: llama
a `jam.servidor.abrir_ventana('http://127.0.0.1:8790/')`, una ventana en modo aplicación de
Chromium, el mismo editor que se abre desde Godot y Unity. El comando que dispara se probó; el clic
en el menú lo tiene que ver Brian (lo anotaba ya la tarea `fuera-del-motor`). En Godot y Unity Brian
ya lo abrió; en Unreal, no consta. Salió al revisar `verde_editor` (tarea `editor-vigente`).

## Qué hacer

En JamPlayground: menú de herramientas → «Jam: editor de nodos (web)».
- Se abre una ventana propia (sin barra de URL), no una pestaña del navegador.
- Carga el editor con la paleta a la izquierda y el grafo inicial; arriba dice el motor (unreal) y
  la conexión en verde.
- Un Run de un ejemplo (p. ej. «base_comun») deja el Preview en el nivel.

## Próximo paso

El gesto de Brian.
