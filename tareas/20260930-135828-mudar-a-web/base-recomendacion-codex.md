# Decisión propuesta para la base web

**Seguir con el LiteGraph vendorizado y encapsularlo.** La inversión urgente es completar documento/API/historial; cambiar el renderer no resuelve esas tres cosas. Para este requisito de archivos estáticos servidos por Python, el bundle actual ya entrega pines, canvas, grupos, controles básicos y navegación. No recomiendo esperar a la migración de biblioteca para mudar Slate.

Costos relativos estimados por alcance de código, no cronograma medido ni promesa de días. Las tareas comunes —API, documento, funciones, assets, inspector y verificación real— se pagan en todos los caminos.

| Camino | Sin npm/build en Jam | Costo adicional y compromiso | Decisión |
|---|---|---|---|
| LiteGraph actual, fijado y envuelto | Sí, ya funciona así. | **Bajo de transición, medio de extensiones**: conservar integración; implementar historial/IDs, vías, compacto con multipines, perilla embebida, tooltips. Ser dueños de los fixes aislados y de la validación del vendor. | Recomendado para la mudanza. |
| Otro snapshot de jagenjo/comfyanonymous con build precompilado | Sí si el archivo de distribución está publicado y se vende con versión/hash/licencia. | **Medio**: comparar API/eventos/serialización y repetir gestos; no asumir que otro snapshot resuelve historial, funciones Jam o compacto. Sólo cambiar ante un beneficio concreto demostrado en una prueba pequeña. | Alternativa puntual, no cambio estratégico por el nombre Comfy. |
| Comfy-Org/litegraph independiente | Un artefacto histórico compilado puede servirse estático. | **Alto**: upstream lo declara ampliamente incompatible y archivado; elegirlo como biblioteca mantenida sería una premisa errónea. Congelar otro fork no elimina mantenimiento. | Descartar como apuesta de mantenimiento. |
| LiteGraph actual integrado en ComfyUI_frontend | No se puede copiar sus fuentes TypeScript como scripts de este servidor. | **Muy alto / incompatible con el alcance**: extraer, desacoplar imports internos y Vue/stores, producir una distribución o mantener otra cadena de build fuera de Jam. Mucho más que reemplazar un JS. | Descartar bajo la restricción actual. |
| Rete 2 con distribuciones UMD vendorizadas | **Sí es viable sin build en Jam**; la documentación publica carga por script. Hace falta renderer y dependencias pares también fijadas. | **Alto de transición**: rehacer nodos, sockets, conversión, selección y eventos; ensamblar plugins. Beneficio: plugins de historial, vías, comentarios y minimapa, UI DOM más cómoda para controles ricos. Sigue faltando política Jam de nombres, funciones y transacciones de parámetros. | Reserva si se decide que Canvas2D limita edición/accesibilidad/control DOM. No lo elegiría para acelerar esta mudanza. |

El fork [comfyanonymous/litegraph.js](https://github.com/comfyanonymous/litegraph.js) conserva el modo de consumo con `build/litegraph.js` y CSS. Eso demuestra viabilidad sin npm, **no mantenimiento actual ni que sea el bundle de Jam**. La página consultada no alcanza para certificar actividad reciente.

[Comfy-Org/litegraph.js](https://github.com/Comfy-Org/litegraph.js/) declara archivado su paquete e integración al frontend desde agosto de 2025. El [LGraph.ts actual del frontend](https://github.com/Comfy-Org/ComfyUI_frontend/blob/main/src/lib/litegraph/src/LGraph.ts) importa Vue y módulos internos; inferencia: extraerlo para una página estática exige trabajo de desacoplamiento/compilación. No confundir el fork antiguo de comfyanonymous, el paquete archivado de Comfy-Org y ese código integrado.

[Rete: inicio y carga por CDN](https://retejs.org/docs/getting-started/) publica formatos ES/CommonJS/UMD y ejemplos de scripts: npm no es obligatorio para consumir el runtime. Para Jam, descargar versiones exactas a vendor y servirlas localmente, sin CDN en ejecución. Su [FAQ](https://retejs.org/docs/faq/) aclara que no ofrece renderer vanilla JS; habría que usar uno publicado con sus dependencias (p. ej. React/Vue/Lit según la distribución elegida) o escribirlo. Sus plugins de [historial](https://retejs.org/docs/guides/undo-redo/), [reroute](https://retejs.org/docs/guides/reroute/) y [minimapa](https://retejs.org/docs/guides/minimap/) existen, pero requieren ensamblaje. El historial documenta acciones personalizadas para cambios que el preset no cubre.

Fuentes oficiales consultadas durante esta revisión. No se instaló ni probó otra biblioteca; la compatibilidad específica de una combinación de versiones Rete necesitaría una prueba en navegador antes de adoptarla.

## Organización sin build

Usar módulos ES nativos `.js` con imports relativos y extensiones explícitas. Mantener LiteGraph como script clásico antes del punto de entrada: convertir su UMD/IIFE a module sin adaptación puede cambiar su global `this`. Los servidores ya entregan `.js` con MIME JavaScript (web.py:76; servidor.py:179). Elegir `.js`, no `.mjs`, para aprovechar exactamente las rutas actuales. editor.html:94–95 pasa a cargar el vendor clásico y luego editor.js con `type="module"`.

Estructura propuesta dentro de `Content/Python/jam/web/` (no creada):

| Módulo | Responsabilidad |
|---|---|
| `editor.js` | Arranque, montaje y conexión de dependencias; sin lógica de grafo. |
| `api/cliente.js` | POST, decodificación uniforme, errores, capacidades del motor, revisión de peticiones. |
| `documento/modelo.js` | Documento Jam completo, validación, flags, IDs, comentarios/vías y campos preservados. |
| `documento/acciones.js` | Única entrada para agregar/borrar, pegar, renombrar, aplicar texto, editar parámetros y funciones. |
| `documento/historial.js` | Snapshot/transacción por gesto, undo/redo, estado dirty y restauración sin ejecutar efectos. |
| `canvas/litegraph.js` | Encapsular LGraph/LGraphCanvas y acceso a `_nodes`, links, slots. Adaptación ida/vuelta sin pérdida. |
| `canvas/nodos.js` | Tipos desde spec; name/label/tipo/letra separados; desconocidos conservados. |
| `canvas/widgets.js` | Widgets por descriptor: unidades, expresiones, rango, combo, perilla, tirador. |
| `canvas/interaccion.js` | Atajos/foco, selección, hit-test, vías, compacto y tooltips. |
| `paneles/paleta.js`, `texto.js`, `inspector.js`, `biblioteca.js`, `assets.js` | Paneles DOM: presentan datos y disparan acciones; no duplican reglas Python. |
| `ejecucion.js` | Compile, Run, Live view, revisión de resultados, exclusión de ejecuciones y preview. |
| `sesion.js` | Documento actual, vista/persistencia, publicar/consumir cambios del agente y recuperación. |

Inyectar estado/API/acciones a los paneles; evitar globals compartidos y ciclos de imports. `window.LiteGraph` queda dentro del adaptador. Mantener el vendor sin editar y poner extensiones en el adaptador; si una corrección exige parchearlo, guardar un parche mínimo rastreable con versión, procedencia y hash, para no terminar con un fork invisible.

La fuente de verdad debe ser el documento JSON de Jam con sus metadatos; no reconstruirlo sólo desde la clase JamGraph, cuyo from_json descarta comentarios/vías/compact (graph.py:130). LiteGraph refleja el estado y emite gestos. El núcleo Python decide compilación, expansión de funciones, nombres/defaults dependientes de motor, layout y ejecución. Ningún nodo JavaScript debe reimplementar el evaluador de Jam.

## Orden de trabajo propuesto

1. **Documento sin pérdida y nombres únicos.** Corregir round-trip, abrir atómicamente, conservar desconocidos, soportar edges de 2/4 elementos, debug/compact/comments/reroutes y expresiones numéricas. Distinguir estado de vista de estado que afecta Run. Los índices de reroutes deben remapearse al reordenar aristas; JS hoy las ordena por destino/slot (editor.js:180).
2. **Contrato común Python.** Extraer servicios puros de funciones/biblioteca/layout/variables; exponer capacidades de motor. Mantener alias actuales mientras se completa el inventario. Normalizar tipos y resultados; adaptar archivos/imágenes al navegador. El inventario de 29 funciones es el mínimo de paridad Python, no todo lo que Slate hace nativamente.
3. **Historial y agente.** Un gesto = una transacción. Pegar/duplicar/apply-text deben ser atómicos. Publicar documento y sondear buzón con revisiones; evitar sobrescribir una edición local con una respuesta vieja. Compile asíncrono debe descartar resultados de revisiones anteriores; Run/confirm/discard no se cancelan como si fueran lecturas inocuas.
4. **Paridad de canvas.** Etiquetas de pines primero (LG ya lo soporta), grupos, modo compacto multipin, vías, atajos, controles y tooltips. Funciones Jam se editan como documentos con vuelta al padre; no depender del To Subgraph incompleto.
5. **Paneles y gestos restantes.** Biblioteca/presets, inspector, imágenes, Content/selección y colocación por adaptador. Verificar el mismo recorrido visual en los motores disponibles y con Brian antes de retirar Slate. Minimapa es mejora opcional, no requisito encontrado de paridad.

## Qué tendría que discriminar la futura verificación

No se ejecutaron pruebas ni mutaciones en este trabajo de sólo lectura. Al implementar:

- Abrir un .jamgraph real con comentarios, vías, multipines, debug/compact, variádico y expresión; guardar/reabrir conserva todo. Introducir pérdida deliberada de un campo debe fallar.
- Copiar/pegar y duplicar crean identidades nuevas sin pisar nodos; cortar/pegar conserva estructura; deshacer deja exactamente el documento previo.
- Un arrastre de slider/perilla produce una sola entrada de historial; editar texto conserva su undo nativo.
- Crear/colapsar/renombrar/editar una función mantiene su identidad y sus llamadas en los tres motores; catálogo disponible no promete un backend ausente.
- Descendente=false por HTTP ordena ascendente; los errores de preview/Run se muestran, sin asumir `ok` donde no existe; imágenes cargan por URL.
- Un cambio de agente aparece en el editor web y leer_canvas devuelve lo que está visible; Compile retrasado de una revisión anterior no pinta la nueva.
- Verificación final en navegador y camino real del motor, no sólo unit tests con motor falso. Actualizar test_editor_web.py:32 cuando las llamadas se repartan por módulos, porque hoy sólo busca editor.js.
