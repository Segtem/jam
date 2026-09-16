---
title: "El DSL (Domain-Specific Language) de Jam"
tipo: GUIA
version: "1.0"
date: 2026-09-10
updated: 2026-09-10
status: vigente
area: 04-Ejecucion-y-pruebas
tags:
  - jam
  - dsl
  - consola
  - dash-bar
  - comandos
  - sintaxis
aliases:
  - "El DSL de Jam"
  - "DSL de Jam"
  - "Consola y DSL de Jam"
---

# El DSL (Domain-Specific Language) de Jam

### 1. ¿Cómo está el lenguaje que usa Jam hoy?
 El DSL vive en dsl.py y se ejecuta a través de panel.py:824:

 1. Cerebro puro sin unreal:
 dsl.py:25 y dsl.py:49 son funciones puras en Python que no importan el motor, lo que permite testearlas al instante.
 2. Derivado dinámicamente de tools.REGISTRO:
 No hay una lista estática de comandos hardcodeados en el parser. Jam consulta el registro de herramientas en tools.py.
 3. Filtro de superficies (Consola vs Graph):
 De los 171 verbos registrados en Jam:
     • 83 verbos corren en la consola (registro_core.py:71): son aquellos que no requieren obligatoriamente entradas complejas de cables (mallas dinámicas M, frames F, etc.).
     • 88 verbos viven exclusivamente en Jam ▸ Graph: requieren datos generados por otros nodos. Si intentas correrlos en la consola, el sistema te avisa amablemente qué cable le
     falta.
 4. Composición automática en consola:
 En el Graph de nodos, scatter sólo genera puntos (P) y un nodo instance los coloca. En la consola, si escribes scatter SM_Rock, panel.py:824 compone automáticamente el cálculo
 de puntos con place, colocando los actores de inmediato.
 5. Ciclo interactivo con Oráculo y Preview:
 Cualquier comando que cree actores en el nivel no los fija a ciegas:
     • Genera una previsualización transaccional (preview).
     • El oráculo determinista evalúa la colocación (raycast al suelo, penetración con vecinos, pendientes, cobertura).
     • Puedes confirmar con confirm o descartar con discard.

 ──────
 ### 2. Sintaxis y reglas

 La sintaxis básica es:

   <verbo> [nombre_asset] [param=valor ...]

 • Verbo: Insensible a mayúsculas/minúsculas (place, PLACE, scatter, etc.).
 • Asset: Puede ir suelto (place SM_Rock) o como parámetro explícito (asset=SM_Rock o a=SM_Rock). Si no se indica, toma el asset activo en el picker o biblioteca.
 • Aliases de tipeo rápido:
     • n → count
     • s → seed
     • h → height
     • t → thickness
 • Valores booleanos aceptados: true, 1, si, sí, yes, on (y sus contrapartes para false).
 ──────
 ### 3. Ejemplos para probar

 Puedes introducir estos comandos en el campo de texto de la Dash Bar o mediante api.run_command("<comando>"):

 #### A. Colocación unitaria (place)

 Ubica un prop en la escena teniendo en cuenta el entorno físico:

   place SM_Rock view=true surface=true anchor=base

 │ Qué hace: Coloca SM_Rock en el punto exacto donde apunta la cámara del viewport (view=true), proyectado sobre el suelo (surface=true) y apoyado por su base (anchor=base). El
 │ oráculo informa si quedó bien asentado o si penetra con geometría vecina.

 Variación con rotación y escala:

   place SM_Crate view=true yaw=45 scale=1.2 sink=5

 │ Qué hace: Aplica una rotación de 45°, escala de 1.2x y lo hunde 5 cm en el suelo para evitar que parezca flotando.
 ──────
 #### B. Reparto y dispersión (scatter)

 Distribuye múltiples instancias sobre una superficie:

   scatter SM_Rock count=30 area=800 pattern=poisson scale_min=0.8 scale_max=1.4 seed=42

 │ Qué hace: Reparte 30 rocas en un radio de 800 cm usando distribución Poisson-disc (evita solapamientos midiendo la huella real), variando la escala entre 0.8 y 1.4 y usando
 una  semilla determinista.

 Uso con aliases rápidos:

   scatter SM_Pebble n=50 area=500 s=123
 ──────
 #### C. Soltar con física (drop)

 Coloca objetos dejándolos caer para que se asienten o apilen:

   drop SM_Barrel height=400 view=true

 │ Qué hace: Suelta un barril desde 400 cm de altura sobre el punto de mira y corre la simulación determinista de física hasta que asiente sobre el terreno u otros props.
 ──────
 #### D. Trazado modular a lo largo de curvas (spline)

 Para muros, caminos o cercas:

   spline SM_Wall_3m axis=x anchor=base surface=true

 │ Qué hace: Toma el spline seleccionado en el nivel y distribuye tramos de SM_Wall_3m a lo largo del recorrido respetando su longitud real y comprobando que no queden huecos ni
 │ solapes.
 ──────
 #### E. Diagnóstico y normalización de pivotes (pivot / normalize)

 Antes de instanciar un asset que viene con el pivote desalineado o en una esquina:

   pivot SM_Tree

 │ Diagnostica la caja del asset, informa dónde cae su pivote local y avisa si es apto para repetir en cuadrícula o requiere anclaje.

   normalize SM_Tree anchor=base

 │ Normaliza el agarre del asset en el kit a base, reajustando automáticamente las piezas que ya estén en el nivel sin alterar la malla del disco.
 ──────
 #### F. Primitivas de blockout procedural (mesh_*)

 Generación rápida de geometrías de prueba:

   mesh_box size_x=200 size_y=200 size_z=100

   mesh_stairs steps=12 step_width=160 step_height=18 step_depth=30
 ──────
 #### G. Comandos de control del flujo de trabajo

 Una vez ejecutado cualquier comando de spawn, puedes controlar el resultado:

 • confirm (o ok): Consolida el preview activo en el nivel.
 • discard (o cancel): Descarta y borra el preview si no te gusta el resultado.
 • verify (o oracle): Corre la suite de verificación espacial sobre todo el nivel.
 • search roca (o buscar muro): Busca assets en el Content Browser del proyecto.
 • pick: Toma el asset seleccionado en el Content Browser de Unreal y lo marca como activo.
 • preset list / preset "Muro de piedra 3m": Aplica presets configurados en presets.
 • help (o ayuda): Imprime en consola todos los verbos disponibles y sus parámetros vigentes.
