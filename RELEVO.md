---
turno: 2026-08-01 · codex → claude-code
saliente: codex
entrante: claude-code
desde: 2026-08-01
verde_editor: 6905c8e
verde_editor_fecha: 2026-08-02
---

# Testigo

Entra **claude-code**. Corré `python tools/relevo.py` antes de leer esto; si sale rojo, eso es el turno.

El turno que cierra hizo dos cosas grandes. En **Jam**: el roadmap de accesibilidad del Graph (fases 0
a 3) y las funciones con firma (fase 5, cerebro). Y después nació **`oracle`** —repo aparte,
`Segtem/oracle`— que es un metalenguaje de medidas para construir herramientas con un LLM. Jam pasó a
ser su primer proyecto.

Codex completó arriba de eso la **capa Slate de la Fase 5**: funciones dinámicas en el ribbon con
pines múltiples nombrados y `Ctrl+G` para colapsar una selección. El borde y el colapso viven en
Python puro; C++ sólo dibuja y transmite el gesto.

El 2026-08-02 esa primera capa pasó a una biblioteca administrable: identidad estable separada del
nombre, ABM Nueva/Editar/Guardar/Renombrar/Eliminar, nombre obligatorio al colapsar y pines
`nombre (Tipo)`. También se corrigió el flujo Nanite→Fracture para UE 5.8: Dataflow v2 conserva
materiales y la Geometry Collection hereda Nanite.

El selector de tipos de la firma ya separa protocolo y presentación: los presets conservan `N`,
`M`, `A[]`, etc., mientras Slate recibe etiquetas como `Número (N)` y `Malla dinámica (M)`. El cambio
compiló en 5.8.1; queda pendiente el gesto visual en el editor abierto. El diseño de los futuros
verbos escalares, vectoriales y matriciales quedó en
[[2026-08-02-PLAN-Verbos-Math-Numeros-Vectores-Matrices-v1.0|el plan de Math]].

La primera base de ese plan ya está implementada: **Sumar, Restar, Multiplicar y Dividir** comparten
un registro y evaluador puro entre Flow y Graph, muestran pines `nombre (Tipo)`, detectan errores de
dominio en Compile y publican el resultado escalar al inspector. Compiló contra UE 5.8.1 y pasó 540
tests, incluidas dos mutaciones deliberadas. La sonda embebida dio
`JAM_MATH_GRAPH_TEST TODO VERDE` para spec + Compile + Run + Inspector=`40.000`; falta el gesto real
de guardar/reabrir/ejecutar. El commandlet retorna 1 sólo por nueve paquetes ilegibles de BotOO que
Asset Registry ya reporta al arrancar.

La revisión posterior del botón **Run** encontró que los grafos Math puros entraban por el adaptador
Flow y abrían un Preview vacío. La ruta pública ahora devuelve `preview: false`, no reemplaza el
Preview de escena y reporta explícitamente «sin efectos en la escena»; los grafos con geometría
siguen siendo transaccionales. La salida Slate separa además pin estable `out`, tipo protocolar `N` y
rótulo `resultado (Número)`, así que ya no pinta el código corto como un segundo nombre.

La edición de una función tiene ahora regreso explícito al grafo llamador y Compile entiende los
bordes `input/output` como firma, no como tools desconocidas. Finalmente se corrigió el bloqueo de
clics al arrancar maximizado en **UE 5.8.1 + Wayland**: Jam resincroniza la geometría de la ventana
raíz después del layout, y tanto `OpenGraph` como el spawner real de `Window → Tools` recuperan una
ventana flotante inválida. Son **547 tests OK**; build 5.8.1 verde. En el gesto real el menú abrió
Graph por el spawner y el panel recibió una acción que construyó Preview siete segundos después.

**Leé primero** `Vault-kb/00-Proceso/2026-07-30-INFORME-Oracle-Metalenguaje-De-Medidas-v1.0.md`: son
diez minutos y sin eso la mitad de los archivos nuevos no se entienden.

## Verde al soltar

| Qué | Comando | Resultado |
|---|---|---|
| Cerebro de Jam | `cd Content/Python/tests && PYTHONPATH=$PWD/.. python -m unittest discover -s . -p "test_*.py" -q` | **547 OK**, 0.3 s |
| Math en UE 5.8.1 | `tools/experiments/verifica_math_graph.py` en `UnrealEditor-Cmd` | **spec + Compile + Run sin Preview + Inspector=40.000 + cero rechazado · TODO VERDE** |
| Vault (modo sombra) | `python tools/vault.py` | **55 docs · las dos implementaciones coinciden** |
| Motor | sonda headless + gestos reales de función/ventana | **ABM + Compile de cuerpo + ventana Wayland interactiva · TODO VERDE** |
| Nanite→Fracture | `tools/experiments/verifica_nanite_fracture_58.py` en editor GUI | **2/2 materiales distintos + GC Nanite · TODO VERDE; cierre 139** |
| UE 5.8.1 | APIs + ejemplos + material/UV + PCG real | **98 símbolos + 75 métodos · 8/8 ejemplos · material/UV verde · 287 HISM** |
| Oracle en UE 5.8.1 | `tools/experiments/verifica_oracle_shadow.py` con editor completo | **placement + snap funcional verde; cierre 139** |
| oracle sobre sí mismo | `cd vendor/oracle && python tools/aceptacion.py` | **27 rojos · 12 verdes · 0 huecos** |
| oracle sobre Jam | `python vendor/oracle/tools/diferencial.py --proyecto medidas --confiar-escalares` | **419 acuerdos · 2558 veredictos estables** |
| » mutación de medidas | `python vendor/oracle/tools/mutar.py --proyecto medidas --confiar-escalares` | **163/163 mutantes muertos** |
| » tests de oracle | `cd vendor/oracle && python -m unittest discover -s tests -t . -q` | **339 OK** |

El campo `verde_editor` apunta al checkpoint `6905c8e`, compilado y verificado en UE 5.8.1 con las
sondas y los gestos reales de función, apertura del menú y Graph interactivo. `VIVO` distingue la
suite de `init_unreal.py` y `jam/`, por lo que cambiar sólo tests ya no invalida falsamente esa
evidencia.

El selector con nombres completos es posterior a ese checkpoint. Su C++ compiló contra 5.8.1, pero
`verde_editor` no se adelanta hasta que alguien despliegue la lista y confirme lo que realmente pinta.
Cerrar Graph dejó el editor sin clics: la liberación simple tampoco alcanzó. El cierre ahora hace un
reset completo de entrada inmediatamente y otro en el tick posterior a destruir la ventana. El gesto
real registró `captor=sí` antes, `captor=no` después, y Brian recuperó los botones. **Cuidado con UBT:**
dos intentos cargaron el `.so` viejo porque el reloj del sandbox fechó el fuente detrás del binario.

**Un rojo histórico y deliberado:** el relevo anterior midió 31 mutantes de código vivos de 242. El
denominador cambió desde entonces y ese número no se revalidó en esta revisión. **No declares
equivalentes en masa para pintar verde**: bajan escribiendo tests o justificando cada equivalencia.

## Frontera de verificación

Lo anterior de Slate quedó **cerrado** el 2026-07-29: Brian confirmó marquee, historial,
portapapeles, docking y alinear. La Fase 5 nueva compiló y pasó por Unreal headless, pero nadie ejerció
todavía su gesto ni miró sus pines en el panel; ésa es la nueva frontera.

Lo que **nadie ejerció con las manos** de este turno:

| Cosa | Quién puede verificarla | Estado |
|---|---|---|
| Apertura/cierre de Graph y entrada global | Brian | ✅ ventana raíz resincronizada; menú abre Graph; captor sí→no al cerrar |
| Selector de tipos completo | Brian | ⏳ falta desplegar la lista y confirmar la presentación real |
| Maths: Sumar/Restar/Multiplicar/Dividir, pines y resultado | Brian | ✅ función/instancia + Run + Inspector + persistencia; sin Preview vacío |
| Resto del ABM, `Ctrl+G` + dibujo/cableado de pines múltiples | Brian | ◐ Nueva/Editar/Guardar/Renombrar/Eliminar verdes; faltan `Ctrl+G` y firmas no numéricas |
| Aspecto de una GC Nanite fracturada y rotura en PIE | Brian | ⏳ metadata/materiales verdes; falta viewport y simulación |
| El paquete de estudio subido a NotebookLM | Brian | ⏳ generado, sin abrir |
| Que el informe del modo sombra de `vault.py` se lea bien | Brian | ⏳ |
| Todo lo demás de `oracle` | ✅ sus propias herramientas, el diferencial y la mutación | verificado |

## Para las manos de Brian

**Funciones del Graph — ocho gestos, quince minutos:**

1. Abrí Jam ▸ Graph y armá una cadena de cuatro nodos Mesh.
2. Seleccioná los dos del medio y apretá `Ctrl+G`: debe pedir un nombre antes de reemplazarlos.
3. Abrí **Funciones**: la ficha debe mostrar ese nombre, no `Fn: Función XXXXX-XXXX`.
4. Tocá **Editar**, renombrá los nodos de borde y elegí sus tipos; el selector debe decir
   `Número (N)`, `Malla dinámica (M)`, etc., no códigos sueltos. Guardá. La instancia debe mostrar
   `nombre (Tipo)` en entradas y salidas.
5. Tocá **Nombre** y renombrá la función: las llamadas existentes deben conservarse.
6. Agregá una segunda instancia en serie y tendé sus cables por los pines nombrados.
7. Intentá eliminarla mientras el canvas la usa: debe negarse. Quitá ambas llamadas y eliminála.
8. Repetí con una función conservada y Compile: tiene que dar verde y listar nodos
   `f1__…`/`f2__…` (el nombre exacto del primer id puede variar).

En el primer intento manual, `Ctrl+G` sí guardó el preset pero Slate mostró «respuesta ilegible»:
`preset.guardar` había escrito un log antes del JSON y `ExecPythonCapture` los concatenó. El borde C++
ahora imprime `JAMCOLLAPSE:` y recorta desde la última aparición antes de deserializar; el contrato
está atado en `test_funcion.py`, discriminó al mutarlo y el plugin recompiló. Falta repetir el gesto
con el binario nuevo. Quedó como artefacto válido de ese intento el preset local
`funcion-072657-271.json`; no se borró automáticamente.

El primer intento de **+ Nueva función** también reveló un crash distinto: las lambdas del modal
capturaban `Campo` y `Dialogo` por valor dentro del mismo `SAssignNew`, congelando dos punteros nulos.
El stack cayó antes de Python. Ahora se capturan por referencia durante la vida modal; el test
discriminó con el código roto, el plugin recompiló y Brian creó **Sumar dos números** por la UI real.

Después, sin urgencia: subir `~/Dev/oracle/estudio/` a NotebookLM. Empezá por `00-esencia.md`,
`08-los-numeros.md` y `07-el-diario.md`.

*(Esta sección es obligatoria y no se borra cuando está vacía: si se pudiera omitir, un turno dejaría
de pedir manos sin que nadie lo note.)*

## Lo próximo

**1. Continuar el
[[2026-08-02-PLAN-Revision-Jam-Oracle-UE-5-8-v1.0|plan de revisión integral]].** Las fases 0 y 1
recuperaron la puerta diferencial y certificaron el embedding/sombra; sigue la matriz completa de
UE 5.8.1. La primera matriz automatizable está en
[[2026-08-02-INFORME-Certificacion-Jam-UE-5-8-1-v1.0|la certificación 5.8.1]]; quedan las fronteras
manuales y GUI que enumera el informe.

**2. Completar los verbos escalares de la Fase 1 de
[[2026-08-02-PLAN-Verbos-Math-Numeros-Vectores-Matrices-v1.0|Math]].** La primera entrega
Sumar/Restar/Multiplicar/Dividir ya quedó verde también con gestos: función, Biblioteca, Run,
Inspector, persistencia y ABM. Siguen Signo, Resto/Potencia, Rango, Mezcla, Redondeo, Ángulos y
Comparación; vectores y matrices esperan esa base.

**3. Después de certificar la base, Fase 7 del Graph — bypass (`D`) y comentarios (`C`).**

**4. Reemplazar de verdad los verificadores escritos a mano** de Jam (`vault.py`, `relevo.py`). Están
re-expresados como medidas y verificados por diferencial, y **siguen en uso los originales**. El
reemplazo va cuando el diferencial lleve tiempo en verde, no el mismo día en que se escribió.

**5. Re-expresar los otros cinco oráculos vivos del plugin** como medidas: `scatter`, `pared`,
`physics`, `reemplazo`, `espacio`. Ya están `placement` y `snap`. Cada uno con su sensor y su
diferencial, siguiendo el patrón de `tools/emitir_diferencial.py`.

⚠️ **La trampa del paso 5**: `jam/oracle_*.py` los llama el **editor**, así que el vendor tendría que
estar en el path del intérprete embebido de UE — y hoy `vendor/oracle` es *hermano* de
`Content/Python/`, no está adentro. Hay que decidir si se mueve bajo `Content/Python/` o se inserta el
path, que es el olor de `bridge.py`. **Yo movería.**

**Para un turno con Brian delante, no para éste:** el visor 2D de texturas (el motor está entero en
`jam/preview2d.py` y no lo consume nadie en `Source/`) y el gizmo flotante de alineación de
`Reference/align.png`. Los dos son gesto puro.

## No toques esto

- **`vendor/oracle/` es un subtree: no lo edites a mano.** Se cambia en `Segtem/oracle` y se trae con
  `git subtree pull --prefix=vendor/oracle git@github.com:Segtem/oracle.git main --squash`. Editar la
  copia la separa del upstream en silencio.
- **No borres el verificador escrito a mano de `tools/vault.py`.** La sombra es el chequeo; sin él el
  reemplazo sería un acto de fe. Y si tocás `vault.py`, `relevo.py`, `oracle_placement` u
  `oracle_snap`, **regenerá el fixture** con el emisor correspondiente y el diferencial tiene que
  seguir en cero desacuerdos.
- **En `oracle`, no agregues un operador al álgebra hasta que una SEGUNDA medida lo necesite.** Van
  cinco de seis; `con` levanta un error que dice cuál sería su disparador. Tres de las cuatro preguntas
  abiertas se cerraron sin ampliar el lenguaje, y eso es lo único que prueba que el juego chico
  alcanzaba.
- **Los ids de los nomad tabs** (`JamDashBar` / `JamGraph` / `JamContent`): son la clave persistente
  del layout. Renombrarlos le borra a Brian el acomodo de los paneles.
- **`Marcar()` va DESPUÉS de mutar, no antes.** `BuildJson()` lee los widgets vivos, así que una foto
  tomada «antes» ya contiene lo que acabás de tipear y un `Ctrl+Z` deshace dos cosas.
- **Los ids de nodo no se renumeran al cargar.** Se rompió una vez: el oráculo y el inspector
  referencian nodos por id.
- El resto de las trampas permanentes, en `AGENTS.md`.

## Lo que aprendí este turno

Lo durable está en `AGENTS.md`, en el vault y en el corpus de `oracle`. Acá el resumen de por qué.

- **Un verificador que reporta roto lo que está bien es peor que ninguno**: enseña a ignorarlo. Es el
  caso `008` del corpus, y en un solo día lo cometí **tres veces** escribiendo medidas nuevas.
- **De 16 defectos reales, 14 fueron falsos verdes**, y ninguno lo atrapó un verificador propio en el
  momento: 8 la mutación, 5 Brian, 4 la casualidad, 1 un parser ajeno. Con 489 tests en verde.
- **El arnés de mutación mentía por bytecode viejo.** `max` y `min` ocupan lo mismo y CPython invalida
  el `.pyc` por (mtime, tamaño): hay que limpiar `__pycache__` entre mutantes o el resultado es al azar.
- **`SIGTERM` no ejecuta el `finally`.** Una corrida de `mutar_codigo.py` cortada por timeout dejó un
  archivo del núcleo **mutado en el árbol de trabajo**; lo salvó `git checkout`, no la herramienta. Y
  había un test que decía cubrir eso y sólo probaba el camino feliz.
- **Una medida necesita evidencia de las dos polaridades.** Un corpus de puros defectos deja la medida
  floja — es lo mismo que evaluar un clasificador sólo con positivos.
- **Los verificadores no se juzgan con `if`s.** El veredicto sobre el propio marco tenía que ser un
  dato, como todos los demás.
- **Dos veces afirmé una proporción de memoria y las dos estaban mal.** Ahora los números del README de
  `oracle` los mide `tools/estudio.py`.
- **El nombre visible no puede ser la identidad de una función.** Separar `funcion_id` de la etiqueta
  permite renombrar sin reescribir ni romper todas sus llamadas.
- **En Dataflow 5.8 los materiales son un cable, no un parche posterior.** Los nodos y terminales v2
  transportan el array completo; asignar `[m0, m0]` había borrado silenciosamente el resto.
- **Predeclarar un `TSharedPtr` no vuelve segura una captura por valor dentro de su `SAssignNew`.** La
  lambda se construye antes de la asignación y congela `nullptr`; en un modal, capturar el local por
  referencia es seguro porque la función no retorna mientras la ventana vive.
- **Una etiqueta de opción no es su valor.** Los tipos completos pertenecen a presentación; el código
  corto pertenece al protocolo. Guardar `Número` en lugar de `N` haría legible la UI rompiendo los
  presets, y mostrar sólo `N` preservaría los datos a costa de la persona. Slate necesita ambos.
