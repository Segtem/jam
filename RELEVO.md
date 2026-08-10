---
turno: 2026-08-01 · codex → claude-code
saliente: codex
entrante: claude-code
desde: 2026-08-01
verde_editor: c1fc6e7
verde_editor_fecha: 2026-08-09
---

# Testigo

Entra **claude-code**. Corré `python tools/relevo.py` antes de leer esto; si sale rojo, eso es el turno.

**Actualización Codex 2026-08-09 — Oracle cubre scatter en sombra.** Cuatro medidas declarativas
reproducen cantidad, contención, interpenetración y cobertura sobre 100 mundos diferenciales. El
runtime conserva la referencia histórica como autoridad y ejecuta `Motor` en sombra; además corrigió
el falso conteo que usaba los actores ya creados como cantidad pedida. UE 5.8.1 confirmó dos
coincidencias reales —reparto sano y saturado— y el marcador final
`placement=True snap=True scatter=True`; el shutdown repitió el SIGSEGV histórico posterior al
veredicto. Son **808 tests**, **519 acuerdos / 2958 veredictos** y **189/189 mutantes muertos**.
`contra_la_escena` continúa como aviso manual, no como medida binaria. Los próximos dominios de la
migración son pared, physics, reemplazo y espacio.

**Actualización Codex 2026-08-09 — primera vertical MassEntity.** Mass entró como familia propia de
Distribución, no como PMG. El módulo runtime `JamMass` depende sólo de `MassCore`/`MassEntity`; el
verbo diagnóstico `mass_probe` F → F crea una entidad real por frame con `FTransformFragment`, mide
cantidad/arquetipo/posición, las destruye y deja pasar el mismo dato. El tutorial **Primera población
MassEntity** ejecutó Spec → Compile → Run dentro de UE 5.8.1: **37 válidas, un arquetipo, transforms
conservados y 0/37 handles vivos al terminar**. Son 803 tests; mutar el juicio de limpieza lo puso
rojo. No es todavía una población persistente ni activa el plugin experimental MassGameplay: el
roadmap está en [[2026-08-09-ROADMAP-MassEntity-En-Jam-v1.0]]. `tools/build.py` ahora comprueba por
separado `JamEditor` y `JamMass`; el módulo nuevo quedó compilado y al día.

**Actualización Codex 2026-08-09 — frente PMG.** El roadmap de verbos procedurales avanzó hasta
`mesh_ribbon` S → M. El núcleo puro arma pares izquierda/derecha, triángulos, normales y UV0
longitudinal; el adaptador Geometry Script asigna Material ID. **Borde de camino** dejó de fingir la
superficie con un Pipe: ahora es `Bezier → Resample → Offset → Ribbon → Normals → Static`.
La sonda pública UE 5.8.1 dio 25 pares, 48 tris/50 verts, ancho 360 cm sin error en extremos, UV0
`0..5.91`, Material ID 3, abierta y una pieza. Son **790 tests**, mutación de winding discriminada y
13/13 tutoriales compilados en el motor. Límite declarado: ribbon sólo acepta recorridos abiertos;
la costura UV cerrada, espesor/solidify, auto-intersección, carretera modular y muro siguen.

**Actualización Codex 2026-08-09 — muro y extrusión.** La receta decidió el contrato: no nació un
`curve_solidify` monolítico sino `mesh_extrude` M → M para superficies abiertas. **Muro sobre
spline** compone `Bezier → Resample → Ribbon (30 cm) → Extrude (300 cm Z)`. UE 5.8.1 midió
`48→196` tris, `50→100` verts, 300.00 cm, UV0 completo, Material ID 3, sólido cerrado y una pieza.
Son **795 tests**, mutación cm/UV discriminada y **14/14 tutoriales** compilados. Una M cerrada se
rechaza: la API nativa la convierte en shell y esa semántica no se mezcló en el mismo verbo.

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

El 2026-08-03 comenzó el catálogo matemático ampliado: **Negar, Absoluto, Módulo, Potencia y Raíz
cuadrada** ya están implementados con errores de dominio, iconos propios y paridad Graph/Flow. El
ribbon principal dejó de ser una tira de veinte categorías: ahora son seis familias más Aprender,
con una segunda fila de categorías. Son **552 tests**, build 5.8.1 y sonda embebida verdes; falta el
juicio visual de la nueva organización y los cinco nodos.

Después se abrió el roadmap de nodos nativos de UE 5.8.1. La primera entrega agrega
**Nanite Analyze** y **Nanite Validate** como lecturas A → A: conteos públicos de triángulos,
vértices, UV y LOD, juicio puro sin `unreal`, iconos propios y Run sin Preview. La sonda real
discriminó una Sphere sin Nanite y `CasaKit/casa_kit` con 416.179 triángulos y 1.202.673 vértices.
También encontró que `StaticMeshEditorSubsystem` es `None` en commandlet: leer usa ahora el asset;
transformar conserva el subsistema. El plan completo vive en
[[2026-08-02-ROADMAP-Nodos-Unreal-Engine-5-8-1-v1.0]].

La segunda entrega de ese roadmap agrega **Simplificar por triángulos, por tolerancia y por arista**
como operadores M → M no destructivos en Mesh → Optimizar. El contrato puro fija el cambio sutil de
5.8: `attributes` usa `ATTRIBUTE_AWARE_V2`; el enum histórico sin V2 ahora sólo considera normales.
La sonda pública Compile/Run/Inspector redujo una esfera de 1.922 vértices a 202, 201 y 332,
respectivamente. Uniform Remesh repitió el mismo hash en 16 corridas y dos procesos, pero no se
registró como estable porque Epic declara su resultado potencialmente no determinista.

La tercera entrega agrega **Reasignar IDs de material** y **Limpiar IDs de material** como M → M.
El primer nodo sólo fusiona sections existentes; el segundo compacta IDs y la lista paralela de
slots que llega a `Mesh to Static`. La sonda real midió `Merge {0,1}/2 slots → Remap {0}/2 slots →
Clean {0}/1 slot`. También separa el grupo Mesh → Materiales del grupo de Acabado.

La cuarta entrega agrega **Validar malla** como sensor M → M en Mesh → Hornear. Mide vacío, huecos
de IDs, bordes ambiguos, cierre, componentes, UV y Material IDs/slots; los requisitos incumplidos
quedan naranjas con su causa pero dejan pasar la misma M. La sonda pública dio esfera cerrada verde,
grilla abierta naranja e identidad de entrada/salida. Son **581 tests** y el inventario 5.8.1 sigue
verde con 102 símbolos y 81 métodos.

La quinta entrega agrega **Copiar Static Mesh** y **Copiar Skeletal Mesh** como A → M, con selección
de LOD y opciones de Build Settings. Ambas conservan la lista de materiales que corresponde a los
IDs de la copia; `mesh_from_asset` queda como alias visible de compatibilidad. La sonda real midió
Sphere 266 vértices/1 material y Quinn 43.761/2. Son **586 tests** y 103 símbolos/84 métodos reales.

**Leé primero** `Vault-kb/00-Proceso/2026-07-30-INFORME-Oracle-Metalenguaje-De-Medidas-v1.0.md`: son
diez minutos y sin eso la mitad de los archivos nuevos no se entienden.

## Verde al soltar

| Qué | Comando | Resultado |
|---|---|---|
| Cerebro de Jam | `cd Content/Python/tests && PYTHONPATH=$PWD/.. python -m unittest discover -s . -p "test_*.py" -q` | **586 OK**, 0.3 s |
| Cerebro de Jam, corte PMG actual | mismo comando | **790 OK**, 0.47 s; winding mutado → rojo |
| Cerebro de Jam, corte MassEntity | mismo comando | **803 OK**, 0.48 s; limpieza mutada → rojo |
| Cerebro de Jam, corte Oracle scatter | mismo comando | **808 OK**, 0.48 s; conteo solicitado y sombra fijados |
| Ribbon S → M | `tools/experiments/verifica_mesh_ribbon_58.py` en `UnrealEditor-Cmd` | **25 pares · 48 tris/50 verts · ancho 360 · UV0 0..5.91 · Material ID 3 · TODO VERDE** |
| Tutoriales actuales | `tools/experiments/verifica_ejemplos.py` en `UnrealEditor-Cmd` | **13/13 compilan · TODO VERDE** |
| Extrude M → M / Muro | `tools/experiments/verifica_mesh_extrude_58.py` en `UnrealEditor-Cmd` | **48→196 tris · 50→100 verts · 300 cm · UV0/Material ID · cerrado · TODO VERDE** |
| Tutoriales tras muro | `tools/experiments/verifica_ejemplos.py` en `UnrealEditor-Cmd` | **14/14 compilan · TODO VERDE** |
| MassEntity core F → F | `tools/experiments/verifica_mass_entity_58.py` en `UnrealEditor-Cmd` | **37 válidas · 1 arquetipo `FTransformFragment` · transforms conservados · 37/37 destruidas · TODO VERDE** |
| Tutoriales con MassEntity | `tools/experiments/verifica_ejemplos.py` en `UnrealEditor-Cmd` | **15/15 compilan · TODO VERDE** |
| Math en UE 5.8.1 | `tools/experiments/verifica_math_graph.py` en `UnrealEditor-Cmd` | **9 verbos · Run sin Preview · Inspector=40/2 · dominios rechazados · TODO VERDE** |
| Nanite Analyze/Validate | `tools/experiments/verifica_nanite_diagnostics_58.py` en `UnrealEditor-Cmd` | **apagado rechazado + 416.179 tris/1.202.673 verts validados · Run sin Preview · TODO VERDE** |
| Simplify M → M | `tools/experiments/verifica_mesh_simplify_58.py` en `UnrealEditor-Cmd` | **Count 1922→202 · Tolerance 1922→201 · Edge 1922→332 vértices · TODO VERDE** |
| Material IDs M → M | `tools/experiments/verifica_mesh_material_ids_58.py` en `UnrealEditor-Cmd` | **Merge {0,1}/2 slots → Remap {0}/2 → Clean {0}/1 · TODO VERDE** |
| Validar malla M → M | `tools/experiments/verifica_mesh_validate_58.py` en `UnrealEditor-Cmd` | **esfera cerrada verde · grilla abierta naranja · identidad M · TODO VERDE** |
| Copiar Static/Skeletal A → M | `tools/experiments/verifica_mesh_copy_58.py` en `UnrealEditor-Cmd` | **Sphere 266 verts/1 material · Quinn 43.761/2 · alias compatible · TODO VERDE** |
| Uniform Remesh | `tools/experiments/investiga_remesh_determinismo_58.py` × 2 procesos | **16/16 mismo hash · 486 verts/968 tris; sigue experimental por contrato de Epic** |
| Vault (modo sombra) | `python tools/vault.py` | **58 docs · las dos implementaciones coinciden** |
| Motor | sonda headless + gestos reales de función/ventana | **ABM + Compile de cuerpo + ventana Wayland interactiva · TODO VERDE** |
| Nanite→Fracture | `tools/experiments/verifica_nanite_fracture_58.py` en editor GUI | **2/2 materiales distintos + GC Nanite · TODO VERDE; cierre 139** |
| UE 5.8.1 | APIs + ejemplos + material/UV + PCG real | **103 símbolos + 84 métodos · 8/8 ejemplos · material/UV verde · 287 HISM** |
| Oracle en UE 5.8.1 | `tools/experiments/verifica_oracle_shadow.py` con editor completo | **placement + snap + scatter funcional verde; cierre 139** |
| oracle sobre sí mismo | `cd vendor/oracle && python tools/aceptacion.py` | **27 rojos · 12 verdes · 0 huecos** |
| oracle sobre Jam | `python vendor/oracle/tools/diferencial.py --proyecto medidas --confiar-escalares` | **519 acuerdos · 2958 veredictos estables** |
| » mutación de medidas | `python vendor/oracle/tools/mutar.py --proyecto medidas --confiar-escalares` | **189/189 mutantes muertos** |
| » tests de oracle | `cd vendor/oracle && python -m unittest discover -s tests -t . -q` | **339 OK** |

El campo `verde_editor` apunta al checkpoint `c1fc6e7`, verificado en UE 5.8.1 con la sombra de
placement, snap y scatter sobre actores reales. Las verificaciones previas de Graph interactivo y
ribbon jerárquico siguen documentadas en sus respectivos cortes. `VIVO` distingue la
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
| Maths: Negar/Absoluto/Módulo/Potencia/Raíz | Brian | ⏳ tests/sonda/build verdes; falta gesto en Datos → Maths |
| Nanite Analyze/Validate, cable A → A y Run sin Preview | Brian | ⏳ tests + commandlet 5.8.1 verdes; falta gesto en Create → Nanite |
| Simplify Count/Tolerance/Edge, cables M → M | Brian | ⏳ 586 tests + Compile/Run/Inspector 5.8.1 verdes; falta gesto en Mesh → Optimizar |
| Reasignar/Limpiar Material IDs, cables M → M | Brian | ⏳ 586 tests + Graph 5.8.1 verde; falta gesto en Mesh → Materiales |
| Validar malla, requisitos y cable M → M | Brian | ⏳ 586 tests + Graph 5.8.1 verde; falta gesto en Mesh → Hornear |
| Copiar Static/Skeletal, LOD y cables A → M | Brian | ⏳ 586 tests + Graph 5.8.1 verde; falta gesto en Mesh → Hornear |
| Cinta de curva S → M y aspecto de Borde de camino | Brian | ⏳ 790 tests + Graph real 5.8.1 verde; falta verlo y juzgar miter/UV/material en viewport |
| Extruir superficie M → M y aspecto de Muro sobre spline | Brian | ⏳ 795 tests + Graph real 5.8.1 verde; falta juzgar espesor, remates y UV lateral en viewport |
| Mass → Probar MassEntity, cable F → F y resultado | Brian | ⏳ 803 tests + Graph real 5.8.1 verde; falta abrir el tutorial y confirmar ficha/cable/informe en Slate |
| Ribbon jerárquico por familias | Brian | ⏳ abrió/cerró sin crash; falta juzgar orden, densidad y navegación |
| Resto del ABM, `Ctrl+G` + dibujo/cableado de pines múltiples | Brian | ◐ Nueva/Editar/Guardar/Renombrar/Eliminar verdes; faltan `Ctrl+G` y firmas no numéricas |
| Aspecto de una GC Nanite fracturada y rotura en PIE | Brian | ⏳ metadata/materiales verdes; falta viewport y simulación |
| `drop`: la tanda se apila (era `place physics`) | Brian | ◐ 745 tests + sonda 5.8.1 con actores reales verdes; falta el gesto en el Graph |
| `asset_set → drop`: variantes por punto | Brian | ◐ compila y reparte 2/2 en 5.8.1; **colocar no se puede verificar headless** (ver trampas), falta verlo colocar |
| El corte `place` reparte / `drop` apila | Brian | ✅ visto en el nivel: montón sobre el terreno, 24/24 |
| El Preview anterior ya no es piso (barril flotando) | **nadie** | ⏳ 753 tests + guardián; **la sonda 5.8.1 NO se pudo correr** (editor abierto) |
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

**Prioridad nueva: Fase 1 de
[[2026-08-09-ROADMAP-MassEntity-En-Jam-v1.0|MassEntity en Jam]].** La prueba atómica core está
cerrada. Lo siguiente es diseñar `MS` (receta durable) y `MH` (población efímera), con
`mass_spawn`/`mass_inspect`/`mass_clear` y destrucción obligatoria en Discard, cambio de mundo y
cierre de PIE. No activar MassGameplay ni crear `AMassSpawner` hasta cerrar ese ciclo de vida.

**Después: cerrar la Fase 2 del
[[2026-08-09-ROADMAP-Verbos-Y-Ejemplos-PMG-v1.0|roadmap PMG]] con Carretera modular.** Offset,
Ribbon y Extrude ya están cerrados por el camino real. El próximo ejemplo debe decidir el dato de
módulos, medir cantidad, orientación, separación/seams y estabilidad por seed; no basta duplicar
una calzada ni agregar `curve_close/open/reverse` sin una necesidad demostrada.

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
