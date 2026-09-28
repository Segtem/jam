# Jam fuera del motor: un núcleo y un adaptador por motor

**Estado:** propuesta, para decidir antes de elegir el diseño de `dsl-grafos`.
**Fecha:** 2026-09-27. **Pregunta de:** Brian. **Medición:** Claude, sobre `~/Dev/jam` en `513d653`.

## La pregunta

Hoy Jam es un plugin de Unreal y usa la UI de Unreal (Slate) para los nodos y los cables. ¿Hace
falta que sea así, o Jam puede vivir fuera del motor —por ejemplo un servidor con una interfaz
HTML/CSS/JS— y conectarse a Unreal, Godot y Unity con un adaptador por motor, donde cada uno hace lo
que puede?

## La respuesta corta

Puede, y el código ya está más cerca de eso de lo que parece. El modelo del grafo, el DSL y casi la
mitad del Python no dependen de Unreal, y la UI de Slate **ya habla con la lógica por JSON**. El
acople de verdad está en un solo archivo, `tools.py`, que mezcla la **descripción** de cada verbo con
su **ejecución** en el motor.

## Lo que se midió

| capa | estado | cifras |
|---|---|---|
| Modelo del grafo y DSL (`graph.py`, `dsl.py`) | no importan `unreal`; lo alcanzan sólo al EJECUTAR un verbo, por imports dentro de funciones (`tools`, `library`) | 959 + 111 líneas |
| Cálculo puro (`*_core.py`, `flow`, `math_core`, `fields`, `layout`, `geometry`, `display_core`) | 57 módulos sin `unreal`, ni directo ni indirecto | ~10 000 de ~25 400 líneas de Python |
| Hechos para Oracle (`oracle_*_facts.py`) | ya partidos en sensor puro y adaptador | 7 módulos |
| UI de nodos (`Source/JamEditor`, Slate) | cliente JSON de la lógica: `jam.api.run_graph_json`, `compile_graph_json`, `preset_save_graph`, `collapse_function`, `function_manage` | ~9 600 líneas de C++ |
| Registro de verbos (`tools.py`) | **el acople**: importa `unreal` en la línea 10; `REGISTRO` declara 116 verbos y cada entrada apunta con `"fn"` a su implementación en el motor | 3 117 líneas |
| Geometría nativa (Geometry Script / DynamicMesh) | la usan 6 archivos: `api`, `compare`, `mesh`, `mesh_material_ids_core`, `mesh_noise_core`, `tools` | 157 líneas |
| Mass (`Source/JamMass`) | sólo Unreal | ~1 600 líneas de C++ |
| Servidor dentro de Unreal | UE 5.8 trae **Remote Control** (HTTP/WebSocket, con interfaz web propia): `Engine/Plugins/VirtualProduction/RemoteControl` | — |

Verbos por categoría (`"cat"` de `REGISTRO`), y qué haría cada adaptador:

| categoría | verbos | portabilidad |
|---|---|---|
| Mesh (curvas, marcos, ramas, reroute, extrusión, ruido…) | 55 | casi todo es cálculo; la malla final la construye cada motor con lo suyo (Godot: `ArrayMesh`/`SurfaceTool`) |
| Shader | 8 | propio de cada motor: materiales de UE ≠ shaders de Godot ≠ Unity |
| Create (`replace`, `create_spline`, `fracture`, `nanite*`) | 6 | Nanite y fractura (Chaos) son sólo de Unreal |
| Edit (`pivot`, `normalize`, `pivot_set`, `gizmo`, `ghost`) | 5 | pivotes sí; `gizmo` y `ghost` son herramientas del viewport de cada motor |
| Scatter (`scatter`, `spline`, `brush`, `pcg`) | 4 | sí, salvo `pcg` (sólo Unreal) |
| Place (`place`, `drop`, `snap`) | 3 | sí |
| Content (`asset`, `pick`) | 2 | sí, con el navegador de assets de cada motor |
| Debug | 1 | sí |

## La propuesta

```
            clientes                       núcleo (fuera del motor)                adaptadores
  ┌──────────────────────────┐     ┌────────────────────────────────┐     ┌──────────────────────┐
  │ UI web (HTML/CSS/JS)     │     │ grafo · DSL · registro neutro  │     │ adapter-unreal       │
  │ UI Slate (la de hoy)     │ ──▶ │ evaluación del grafo           │ ──▶ │ adapter-godot        │
  │ jam-mcp (agentes)        │JSON │ cálculo puro (*_core)          │JSON │ adapter-unity        │
  │ consola / DSL            │     │ capacidades por adaptador      │     │ (cada uno: los verbos│
  └──────────────────────────┘     └────────────────────────────────┘     │  que puede, nativos) │
                                                                          └──────────────────────┘
```

- **Núcleo**, un paquete de Python sin `unreal`: el grafo, el DSL con ida y vuelta al canvas, el
  **registro neutro** de verbos (nombre, parámetros, tipos, opciones, superficies, documentación:
  lo que hoy declara `REGISTRO` sin el campo `"fn"`), la evaluación del grafo y el cálculo puro.
- **Adaptador por motor**: implementa los verbos que ese motor puede ejecutar, con lo nativo, y
  **declara sus capacidades**. Un verbo que el motor no tiene se ve en la UI y en el DSL como «no
  disponible en este motor», con el porqué; no falla en silencio.
- **Contrato** entre núcleo y adaptador, en JSON: ejecutar un verbo con sus parámetros y entradas,
  y devolver sus salidas. Lo que cruza son parámetros, puntos y referencias a assets o actores, **no
  mallas enteras**.
- **Clientes**: la UI web, la UI de Slate (que puede seguir, como un cliente más, hasta que la web la
  iguale), `jam-mcp` para agentes y la consola.

## Límites, dichos de entrada

1. **La vista 3D no sale del motor.** La web muestra los nodos; el resultado se ve en la ventana del
   motor. `gizmo` y `ghost` (vista previa en el viewport) siguen siendo del adaptador. Se trabaja con
   dos ventanas, como con Houdini Engine.
2. **Cada motor necesita un servidor chico adentro.** En Unreal ya existe (Remote Control, o el
   Python del editor como hoy). En Godot y en Unity, un plugin de editor que escuche por WebSocket.
3. **Lo pesado se ejecuta en el motor.** Calcular mallas grandes afuera en Python puro y pasarlas por
   el cable sería lento. El núcleo decide y ordena; el adaptador ejecuta cada verbo con lo nativo.
4. **La latencia de ida y vuelta** importa en lo interactivo (perillas, scrub). Por eso el núcleo
   evalúa lo que es cálculo sin cruzar al motor, y sólo cruza para lo que toca el mundo.

## Cómo encaja con las tareas abiertas

- `dsl-parametros` y `fuente-roja`: no cambian; son del núcleo y valen igual.
- **`dsl-grafos`**: el pedido de diseño a los tres modelos (`513d653`) debería agregar un criterio:
  el grafo y el DSL **viven fuera del motor** y no pueden importar `unreal` (ya casi es así; que el
  diseño no lo vuelva a acoplar), y un verbo se describe en el registro neutro con sus capacidades.
- **`jam-mcp`**: más limpio afuera. El agente habla con el núcleo y el núcleo con el adaptador; no
  hace falta el Python embebido del editor para hablarle a un agente.
- **commander** (`godot-mcp`, `corte-1`): esto es lo que necesita para trabajar en más de un motor.

## Etapas, cada una con su criterio de hecho

1. **Partir `tools.py`.** El registro neutro (sin `"fn"`) pasa al núcleo; las implementaciones de
   Unreal, a `adapter_unreal`, unidas por el nombre del verbo. *Hecho cuando:* un test importa el
   núcleo entero con `unreal` bloqueado (por ejemplo `sys.modules["unreal"] = None`) y pasa; la UI de
   Slate y la suite siguen iguales; `oracle test --proyecto medidas` sigue en VERDE con los mismos
   números.
2. **El contrato y el adaptador de Unreal.** Un protocolo JSON versionado (ejecutar verbo, listar
   capacidades) y el adaptador sobre el Python del editor o Remote Control. *Hecho cuando:* un grafo
   de ejemplo corre desde un proceso de Python fuera del editor y deja el mismo resultado que desde
   la UI de Slate (medido con las sondas de JamPlayground).
3. **La UI web.** FastAPI (o la biblioteca estándar) con HTML/CSS/JS, como segundo cliente del mismo
   contrato. *Hecho cuando:* se arma, se guarda y se corre un grafo desde el navegador, y la ida y
   vuelta DSL ↔ canvas da el mismo grafo que en Slate.
4. **El adaptador de Godot**, con el subconjunto que puede (place, scatter, snap, curvas, mallas por
   `ArrayMesh`). *Hecho cuando:* un grafo de colocación corre en Godot 4.7.2 y las medidas de
   colocación de Oracle lo juzgan igual que en Unreal; los verbos que Godot no tiene aparecen como
   no disponibles.

## Lo que NO se hace ahora

- No se reescribe la UI de Slate ni se la apaga: sigue siendo el cliente de Unreal hasta que la web
  la iguale.
- No se porta nada a Unity todavía: Godot primero, porque ya está instalado y commander lo necesita.
- No se mueve el cálculo de mallas pesadas fuera del motor.

## Riesgos

- **Dos UIs a la vez** durante la transición: duplicación de trabajo en cada cambio visual. Se acota
  con el contrato: las dos consumen el mismo JSON.
- **Un protocolo que se congela temprano.** Versionarlo desde el primer día, como la sintaxis de
  Oracle.
- **Capacidades que se declaran mal** (un adaptador dice que puede y no puede). Se cubre con Oracle:
  las medidas se corren por adaptador.
