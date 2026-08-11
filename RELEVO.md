---
turno: 2026-08-01 · codex → claude-code
saliente: codex
entrante: claude-code
desde: 2026-08-01
verde_editor: 0162647
verde_editor_fecha: 2026-08-10
---

# Testigo

Entra **claude-code**. Corré `python tools/relevo.py` antes de leer esto; si sale rojo, eso es el turno.

**Actualización Claude Code 2026-08-11 — la deuda de gestos se cobró dos falsos verdes.** Brian abrió
los tutoriales acumulados en ⏳ y **«Borde de camino» era invisible desde arriba**: sólo el contorno de
selección, con el piso a través. `mesh_ribbon` le entregaba a Unreal el winding invertido. Los 790
tests miraban el array `normals` —que estaba bien, `(0,0,1)`— y el backface culling **ignora ese array
y mira el orden de los índices**; el test incluso había congelado el orden defectuoso
(`assertEqual(triangles, ((0,1,2),(1,3,2)))`), fijando lo observado como si fuera lo correcto. La
sonda `investiga_winding_ribbon_58.py` lo midió con control y tratamiento en UE 5.8.1: un `mesh_box`
nativo daba su tapa a +Z mientras los **48/48 triángulos** del tutorial daban -Z; tras el arreglo,
**48/48 a +Z**. El fix tiene dos mitades que van juntas —invertir el winding e invertir el cross de
`_normals`—, porque sólo la primera dejaría la cinta visible pero iluminada por detrás. Brian
confirmó las dos con los ojos: la calzada se ve y el muro quedó del lado correcto (se extruye sobre
la misma superficie, así que se corrigió solo). Es el ÚNICO verbo que arma buffers a mano: censado.

**Y oracle no lo veía, aunque lo había avisado.** Los puntos ciegos declarados de `spline.cobertura`
(«NO ve … visibilidad») y `spline.sin_solape` («NO ve … triángulos») nombraban exactamente este
hueco. Nació el dominio **`malla`** con dos medidas: `malla.cara_visible` —la cara que dibuja el motor
contra la normal de sombreado de sus propios vértices, cero como único corte defendible— y
`malla.superficie_sin_vueltas`. En su PRIMER uso la medida encontró un defecto que nadie había visto:
**`ribbon_core` pliega caras cuando el recorrido dobla más cerrado que el ancho de la cinta** (4 de 20
mundos «limpios» salían rotos). No se escondió bajando el generador: quedó como el defecto nombrado
`curva_mas_cerrada_que_el_ancho`, con 12 rojos / 8 verdes. El estado final de ese pliegue está
en el párrafo siguiente, que es el único que hay que leer sobre el tema.

**ESTADO DEL PLIEGUE — resuelto en el rango realista, con un residuo que es otro defecto.**
`_sin_pliegues` angosta la cinta donde el recorrido dobla más cerrado que su media anchura, con el
mismo factor en los dos bordes para no descentrarla, y lo publica en `angostados`: el mismo patrón con
que `miter_limit` cae a bevel en vez de estirar la esquina en silencio. Trabaja contra el eje REAL de
cada muestra, porque `offset_points` ahora publica `origins` —de qué vértice nació cada punto emitido,
dos con el mismo índice en un bevel—; el punto medio entre bordes, que se usó primero, deja de
representar al eje cuando un miter empuja un borde lejísimos.

| recorrido | antes | con punto medio | con eje real |
|---|---|---|---|
| giros ≤22° por muestra (realista) | 4/20 plegadas | **0/20** | **0/20** |
| giros de 140°, cinta más ancha que el paso | 20/20 | 11/20 | **7/20** |

**Los 7 que quedan NO son el mismo defecto**, y por eso no se siguió afinando: ahí el borde interior
**no retrocede, avanza muy poco**. Medido en el mundo 1 del corpus, el izquierdo avanza 1,4 cm contra
~460 del derecho, y como cada muestra lleva su propia Z el triángulo casi sin base queda casi vertical
(`nz = -0,048`). Es una degeneración por avance despreciable; pide criterio y defensa de umbral
propios —avance mínimo proporcional al del eje, o fusionar muestras casi coincidentes— y es el próximo
corte. `malla.cara_visible` los marca en rojo mientras tanto: **no se afinó el algoritmo contra la
medida a propósito.** En UE 5.8.1: `JAM_MESH_RIBBON_58 TODO VERDE` con los mismos 25 pares / 48 tris /
UV0 0..5.91 de siempre, `mesh_extrude` y `curve_offset` —que comparte el núcleo tocado— verdes, cara
de la cinta 48/48 a +Z y **19/19 tutoriales compilan**.

**`malla` se extendió a los SÓLIDOS: extrude y primitivas.** Una superficie abierta se juzga por el
lado que muestra; un sólido, por si sus caras miran hacia AFUERA —invertidas, la pieza se ve como si
uno estuviera adentro—. `malla.solido_hacia_afuera` usa el volumen con signo, no el producto punto
contra el centroide, porque ese atajo falla en cualquier forma cóncava y las piezas de un kit lo son;
`malla.solido_esta_cerrado` es su guarda, porque sobre una malla abierta el volumen daría un número
con apariencia de veredicto. El signo NO se razonó: `verifica_malla_solidos_58.py` lo fija contra
primitivas nativas, y un `mesh_box` de 200×140×90 dio **volumen_orientado = 2.520.000 exacto**, con la
misma caja invertida en el negativo exacto. El muro real —cinta extruida— salió cerrado y positivo.

El corpus se escribió dos veces porque oracle rechazó las dos primeras versiones, y las dos veces
tenía razón: primero **mis propios prismas no cerraban** (la base recorría el polígono en el mismo
sentido que los laterales) y después **no eran convexos** (un radio suelto por vértice los volvía
estrellados, y sobre un cóncavo no valen ni el abanico ni la referencia). Son **1099 acuerdos / 4298
veredictos**, **303/303 mutantes** y 11 dominios.

⚠️ **EL CRASH DEL ARRASTRE SIGUE ABIERTO — tres intentos, y el tercero es un EXPERIMENTO, no un
arreglo.** Brian lo reproduce arrastrando una ficha del ribbon al lienzo. Siempre cae igual:
`TOneDynamicChildBase<…, TSlateAttribute<int>>::GetChildRefAt` dentro de `DrawPrepass`, con
«Array index out of bounds: **254** into an array of size **2**» y, la última vez, además
`SIGSEGV … write at 0x3`.

Lo intentado y DESCARTADO, para que nadie lo repita:
1. **Diferir la creación del nodo un frame** (`OnDrop` guarda y un `RegisterActiveTimer` crea). No
   era la causa; se conserva porque mutar la jerarquía dentro del evento igual está mal.
2. **Puntero débil + clamp en el `WidgetIndex_Lambda`** del `SWidgetSwitcher` de la ficha, que
   capturaba `this` crudo. Tampoco: el crash volvió con el binario nuevo — verificado por
   timestamps, el crash de las 11:25:28 es posterior al `.so` de las 11:23:33.

3. **Lo que está ahora es un experimento que DISCRIMINA, y hay que leerlo como tal.** Se eliminó el
   único `SWidgetSwitcher` de todo Jam: la columna de la ficha usa dos hijos con `Visibility` en un
   `SOverlay`, que hace lo mismo sin ningún índice. **Sin índice no puede haber índice fuera de
   rango.** Por eso el resultado es informativo en las dos direcciones:
   · si el crash **desaparece**, era nuestro y quedó cerrado;
   · si el crash **sigue**, el `TOneDynamicChildBase` culpable **no es de Jam** —era el único que
     había— y hay que buscarlo en el editor: candidatos son los switchers propios de Slate en la
     ventana del decorador de drag-drop o en el tab, y ahí ya no alcanza con leer el stack.

Un test recorre `Source/` y falla si vuelve a aparecer `SNew(SWidgetSwitcher)`. **870 tests.**
⚠️ **Quedan 17 lambdas `[this]` más en `SJamGraphNode.cpp`** con el mismo riesgo latente.

**Lo que se aprendió del método**: deducir la causa desde un stack sin poder reproducir el gesto
falló dos veces seguidas. El tercer paso no pretende acertar sino PARTIR EL PROBLEMA EN DOS.

**(histórico del intento 2)** El crash del arrastre parecía un USE-AFTER-FREE. El primer arreglo
—diferir la creación del nodo un frame— no era la causa; se conserva porque mutar la jerarquía dentro
del evento igual está mal, pero el editor siguió rompiéndose. El stack completo que trajo Brian tenía
el dato que faltaba: `Array index out of bounds: **254** into an array of size **2**`, en un
`TOneDynamicChildBase` con `TSlateAttribute<int>` — o sea un `SWidgetSwitcher`. El de
`SJamGraphNode.cpp` elegía su columna con `.WidgetIndex_Lambda([this]() { return bCompacto ? 1 : 0; })`,
capturando `this` CRUDO: con el nodo destruido y el switcher todavía dibujándose, leía `bCompacto`
sobre memoria liberada.

**El 254 era la firma del bug**, no ruido: con optimización el compilador sabe que un `bool` sólo vale
0 o 1, así que `bCompacto ? 1 : 0` compila como una carga directa del byte, sin rama; la basura entra
tal cual como índice de slot. Ahora el lambda captura `TWeakPtr<SJamGraphNode>` y acota con
`FMath::Clamp`. Tres tests leen el `.cpp` y las dos mutaciones —volver a `[this]`, quitar el clamp—
lo ponen rojo. Son **870 tests**. ⚠️ **Quedan 17 lambdas `[this]` más sólo en ese archivo**, con el
mismo riesgo latente; sólo ésta reventaba porque su valor se usa como índice.

**El gesto de arrastre en sí ya existía** Brian lo
reportó como intermitente («de vez en cuando»). El gesto YA existía —`SJamVerbTile::OnDragDetected`
más `SJamGraphEditor::OnDrop`—, así que no había que incorporarlo sino entender por qué reventaba. El
stack de los asserts lo ubica: `SWidget::Prepass_Internal` → `ForEachWidget` → `GetChildRefAt` con
índice fuera de rango. `OnDrop` llamaba a `AddNode`, que agrega slots al canvas, **en medio del
recorrido que Slate hacía sobre esos mismos hijos**; que fuera intermitente es coherente con que el
drop caiga o no dentro de ese recorrido. Ahora `OnDrop` sólo guarda verbo y posición y
`RegisterActiveTimer` crea el nodo en el frame siguiente. Tres tests leen el `.cpp` y dos mutaciones
—devolver `AddNode` a `OnDrop`, y limpiar el pendiente después de crear en vez de antes— lo ponen
rojo. **Compila y son 867 tests, pero el gesto no se pudo ejercer**: necesita mouse real en el editor
GUI. Que el crash desapareció lo confirma Brian, no yo.

⚠️ **MassEntity Fase 4b — variación por entidad: IMPLEMENTADA Y COMPILADA, SIN VERIFICAR EN PIE.**
La patrulla anterior movía a toda la población al unísono: `Distance = 0`, `Direction = 1` y la misma
velocidad para todas, así que salían juntas, tocaban el extremo en el mismo frame y volvían juntas.
Cada individuo estaba bien y el conjunto se veía como una coreografía.

Ahora `FJamMassPatrolFragment` lleva `Phase` y `SpeedScale` por entidad, y `FJamMassPatrolParameters`
un `Variation` en 0..1 (el asset quedó en **0.70**). La variación se deriva del **ORIGEN de spawn**,
cuantizado a centímetros, y NO del índice de la entidad: el orden en que Mass crea y ordena entidades
es un detalle interno, y atarse a él haría que una escena no se viera igual dos veces sin que nada
avisara. Cada canal (fase, velocidad, sentido) sale de un hash distinto — si fase y velocidad salieran
del mismo número, las más adelantadas serían siempre las más rápidas y la formación volvería ordenada
de otra manera. `mass_config require_variation=true` es un requisito APARTE de `require_patrol`,
porque una población en fase es una patrulla válida; mezclarlos habría puesto en rojo la Fase 4
anterior. `inspect_population` publica ahora `patrol_phases` y `patrol_speed_scales` crudas —no un
promedio, que escondería justamente el caso de todas iguales— y `mass_core.judge_variation` las juzga.

**Lo que falta es la sonda, y no es un detalle.** `verifica_mass_variacion_58.py` está escrita y mide
lo que corresponde —dispersión y determinismo entre dos poblaciones sobre los mismos transforms— pero
NO se logró ejecutar: en commandlet (`-run=pythonscript`) no hay bucle de Slate, así que el callback
por tick nunca dispara y el editor sale en 4 ms; con `-ExecCmds="py …"` en editor completo tampoco
escribió su marcador. La receta de invocación de las sondas PIE quedó sin resolver, así que **la
variación no está verificada en el motor**: lo único medido es que compila, que los 864 tests del
cerebro pasan y que el asset conserva `variación 0.70`. Al retomar, lo primero es hacer correr esa
sonda —mirar cómo se invoca `verifica_mass_pie_58.py`, que sí funciona en editor completo—. Antes de
eso, dos ceros conocidos: crear y leer la población en el MISMO tick da seis fases en 0 porque el
processor todavía no corrió, y sin PIE tampoco tickea.

⚠️ **El fix de Wayland del Graph está compilado pero NO verificado.** Reabrir el Graph dejaba la
ventana sin recibir clics: `ReshapeWindow` pedía `(173, 97)` y Slate seguía informando `(0, 0)`, así
que el hit-test quedaba corrido y sólo se destrababa con un resize manual. `SincronizarGeometriaFlotante`
repite en dos ticks el gesto del resize (con un tamaño DISTINTO: al mismo tamaño el compositor puede
no emitir `configure`) y publica `ventana Graph resincronizada — alineada=sí/no`. Cuatro tests atan el
`.cpp` y las cuatro mutaciones discriminan. **Pero en la sesión de verificación el camino no se
ejecutó ni una vez** (`reubicada=no` en las tres reaperturas, porque el rect ya era válido en el
segundo monitor): el editor anduvo por otra razón. No lo cuentes como verde.

**Actualización Codex 2026-08-10 — MassEntity Fase 4, primera patrulla autónoma.** Jam distribuye
`/Jam/Mass/MC_JamAmbientPatrol`: ISM dinámica y vaivén a 800 cm/s en radio 25 cm sobre el eje de
cada frame. Trait, fragment, parámetros compartidos y processor son C++ tipado;
`mass_config require_patrol=true` mide fragment, parámetros y movilidad antes de publicar MC. PIE
real dio **4/4 inicializadas, movidas y revertidas, cero fuera de radio, ISM dinámica 4/4 y limpieza
completa**. Neutralizar sólo la escritura del transform dejó el estado interno avanzando pero las
entidades inmóviles (`transform_mismatches=0`) y puso roja la sonda; restaurar volvió a verde. Son
854 tests. No evita obstáculos, no sigue terreno y no tiene señales/StateTree/ZoneGraph. Próximo
corte: variación determinista por entidad o señal ambiental medible, no navegación todavía.

**Actualización Codex 2026-08-10 — MassEntity Fase 3 cerrada con presupuesto LOD.** Jam distribuye
`/Jam/Mass/MC_JamAmbientBudget`, con topes independientes High/Medium/Low=1 y Off ilimitado.
`mass_config require_lod_budget=true` inspecciona los cuatro `LODMaxCount` antes de publicar MC; el
tutorial `Poblacion-Mass-LOD-Presupuestado` deja visible MC→MS→MH. En PIE real, cuatro entidades
dentro del rango High dieron **High=4** con el control ilimitado y **High/Medium/Low/Off=1/1/1/1,
ISM/None=3/1** con el presupuesto. Mutar High a ilimitado dejó 4/0/0/0 y puso roja la misma sonda;
código y asset fueron restaurados. Son 849 tests y ambos módulos están al día. El shutdown sigue
abortando después del marcador; una apertura/cierre mínima lo reprodujo incluso con
`-DisablePlugins=Jam`, así que queda delimitado como rojo del host/editor, no como verde de Jam.
Lo próximo es Fase 4: un comportamiento ambiental mínimo y medible, sin ZoneGraph hasta que un caso
de BotOO exija navegación.

**Actualización Codex 2026-08-10 — MassEntity Fase 3, representación ambiental cerrada.** Jam
distribuye `/Jam/Mass/MC_JamAmbientISM`: Stationary, Sphere, ISM en High/Medium/Low y None en Off.
`mass_config require_ism=true` mide fragments, descriptor, movilidad, perfil y umbrales antes de
publicar MC. Tres procesadores Jam habilitan las bases dinámicas de Epic y quedan aislados con
`FJamMassAmbientTag`; el mismo tag enlaza `LODParams.FilterTag`, cuya ausencia mandaba todo a Off.
La sonda de editor completo, con PIE jugable/viewer/ticks reales, midió **High/Medium/Low/Off =
1/1/1/1, ISM/None = 3/1, cuatro descriptores válidos y limpieza completa**. Simulate primero
discriminó que sin viewer todo queda Off; el test de paridad C++ pasó a rojo al quitar el enlace del
tag. Son 845 tests. Límite: no hay saturación por presupuesto, actores high/low, navegación ni
comportamiento. El `double free` histórico vuelve sólo al apagar el editor, después del marcador.

**Actualización Codex 2026-08-10 — MassEntity Fase 2, primera vertical MassGameplay cerrada.**
`mass_config` valida un `UMassEntityConfigAsset` y publica MC sólo si su template tiene
`FTransformFragment`; MC entra por pin de dato a `mass_spec`. El camino configurado crea mediante
`AJamMassSpawner` + un generador determinista de frames, y Jam distribuye el config portable
`/Jam/Mass/MC_JamSpatial`. La sonda pública MC→MS→MH midió **37/37 vivas, ruta y spawner
trazables, cero transforms distintos y cero vivas tras Discard**. Quitar el fragment del trait,
recompilar y repetir puso el Run rojo; restaurar volvió a `JAM_MASS_GAMEPLAY_58 TODO VERDE`. Límite:
todavía no hay representación/LOD, navegación ni comportamiento. El mutante también mostró que un
nodo fuente rojo no cancela dependientes aunque el Run global sí queda rojo y revierte Preview.

**Actualización Codex 2026-08-10 — MassEntity Fase 1 cerrada con PIE real.** La nueva sonda mantiene
simultáneamente tres entidades del editor y tres del `UWorld` PIE. Al terminar PIE, las del editor
siguen vivas y el MH de PIE queda «inexistente o ya liberada». Neutralizar `OnWorldCleanup`,
recompilar y repetir dejó el MH atado al mundo destruido y puso la sonda roja; restaurar el callback
y recompilar devolvió `JAM_MASS_PIE_58 TODO VERDE`. El `double free` histórico ocurre después del
marcador durante el desmontaje completo. La Fase 1 queda cerrada; el próximo corte es Fase 2:
`MassGameplay`, MC/traits y un caso ambiental acotado de BotOO.

**Actualización Codex 2026-08-10 — MassEntity Fase 1, primera vertical MS/MH.** `mass_spec` convierte
F en una receta pura MS con seed/presupuesto; `mass_spawn`, `mass_inspect` y `mass_clear` gobiernan
una población MH viva desde `JamMass`. Preview ahora admite efectos runtime sin Actor: Run×2 libera
la población anterior, un Run fallido revierte la nueva y Discard la destruye. Bake conserva MH sólo
durante la vida del mundo; Clear es idempotente. UE 5.8.1 verificó 37 entidades en cada etapa y acabó
con cero vivas; mutar deliberadamente el juicio de `valid_after` puso rojo el test. Son **837 tests**
y ambos módulos están compilados/al día. Abrir un mapa vacío retiró además la población confirmada
del mundo anterior mediante `OnWorldCleanup`; falta ejercer cierre de PIE antes de declarar cerrada
la Fase 1. MassGameplay
sigue apagado; `config_path` reserva MC pero todavía no cambia el arquetipo.

**Actualización Codex 2026-08-10 — Oracle cubre espacio y completa los oráculos vivos.** Tres
medidas declaran inicio único, meta única y extracción alcanzable sobre el subconjunto que
`nivel.py` produce hoy: nodos, llaves y puertas. El sensor puro hace su propio BFS `(nodo, llaves)`;
100 mundos diferenciales cubren cuatro defectos y la mutación deliberada del alcance produjo 60
desacuerdos. UE 5.8.1 creó cinco actores, reconstruyó el grafo desde tags `jam:*`, pasó el mapa sano
y detectó el roto al desconectar la llave. Cuatro sombras coincidieron y el marcador terminó en
`espacio=True`; después volvió el `invalid pointer`/señal 6 de shutdown. Switches, hazards, flags,
recursos, tareas, canales y subgrafos sin aplanar se rechazan visiblemente, no se certifican por
accidente. Quedan **829 tests**, **919 acuerdos / 3938 veredictos** y **279/279 mutantes**. Ya no
queda ningún oráculo del runtime vivo sin sensor, catálogo y diferencial.

**Actualización Codex 2026-08-10 — Oracle cubre reemplazo.** Tres medidas declarativas separan
centro XY, base y footprint del blockout. Ochenta mundos cubren las tres roturas; aflojar
deliberadamente la planta de 2 a 20 cm produjo veinte falsos verdes. En UE 5.8.1, un reemplazo
ajustado preservó todo, el asset nativo rompió la planta `(-98,5, -107,0)` cm y otro desplazado 10 cm
rompió centro/base conservando la planta. Las tres sombras coincidieron y el marcador terminó en
`reemplazo=True`; el shutdown posterior repitió señal 6. Quedan **825 tests**, **819 acuerdos / 3638
veredictos** y **260/260 mutantes**. El único oráculo vivo todavía sin migrar es `espacio`.

**Actualización Codex 2026-08-10 — Oracle cubre physics paint por lotes.** Dos medidas nuevas exigen
que todas las piezas encuentren soporte y que sus AABB finales no interpenetren. El audit encontró
un falso verde: `resumen()` decía `ASENTAR ✓` si una pieza aterrizaba aunque otra quedara sin piso;
ahora el resultado parcial lleva `✗`. Son 80 mundos nuevos, con bordes mutacionales de 0,5 cm y dos
profundidades distintas. UE 5.8.1 apiló actores reales en bases 0/100/200 cm, ignoró el Preview
anterior y midió cuatro alturas de Landscape por raycast; las tres sombras coincidieron y
`JAM_PHYSICS_PAINT_58 TODO VERDE`. Quedan **821 tests**, **739 acuerdos / 3398 veredictos** y
**234/234 mutantes**. El commandlet salió 1 sólo por los nueve paquetes inválidos conocidos de
BotOO. La cantidad apilada sigue siendo diagnóstico, no umbral universal; falta únicamente mirar el
gesto de `drop(points)` en Slate.

**Actualización Codex 2026-08-10 — Oracle cubre el apoyo físico unitario.** El camino vivo
`t_drop → physics.soltar → ue.physics_texto` ejecuta ahora dos medidas en sombra:
`physics.tiene_suelo` y `physics.apoyado`. El sensor puro elige el soporte AABB válido más alto y el
diferencial cubre 80 mundos: apoyado, sin suelo, flotando y hundido. Invertir deliberadamente el
comparador produjo desacuerdos antes de restaurarlo. UE 5.8.1 midió con dimensiones reales 200 cm
de aire, apoyo a 0 cm y 20 cm de hundimiento; las tres sombras coincidieron y el marcador terminó en
`placement=True snap=True scatter=True spline=True physics=True`. Quedan **816 tests**, **659
acuerdos / 3238 veredictos** y **219/219 mutantes**. El shutdown posterior cayó con señal 139. Esto
no certifica `drop` por puntos: esa tanda usa raycasts y `physics_core.asentar_tanda` y queda como
frontera separada.

**Actualización Codex 2026-08-09 — Oracle cubre el spline modular real.** El pendiente llamado
“pared” apuntaba a `oracle_pared`, pero esa R7 que estiraba segmentos sólo conserva un selftest: el
Graph usa `t_spline → spline.construir → spline_core`. La sombra entró ahí con medidas de cobertura
≥90% y solape longitudinal ≤1 cm sobre 60 mundos. También corrigió un falso verde: ahora se juzgan
los módulos que Unreal realmente creó, no el plan previo al spawn. UE 5.8.1 midió cinco sanos con
cobertura 1.0 y cinco solapados con cuatro juntas; marcador
`placement=True snap=True scatter=True spline=True`. Quedan **812 tests**, **579 acuerdos / 3078
veredictos** y **201/201 mutantes**. El shutdown posterior abortó con `invalid pointer`/señal 6.

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
| Cerebro de Jam, corte Oracle spline | mismo comando | **812 OK**, 0.48 s; spawn real y sombra fijados |
| Cerebro de Jam, corte Oracle physics | mismo comando | **816 OK**, 0.48 s; cuatro estados y selftest AABB fijados |
| Cerebro de Jam, corte physics paint | mismo comando | **821 OK**, 0.49 s; parcial rojo y sombra de tanda fijados |
| Cerebro de Jam, corte reemplazo | mismo comando | **825 OK**, 0.5 s; centro, base y planta fijados |
| Cerebro de Jam, corte espacio | mismo comando | **829 OK**, 0.49 s; BFS independiente y frontera avanzada fijados |
| Cerebro de Jam, corte Mass MS/MH + PIE | mismo comando | **838 OK**; callback PIE mutado → rojo real |
| Cerebro de Jam, corte MassGameplay MC→MS→MH | mismo comando | **841 OK**; trait sin `FTransformFragment` → rojo real |
| Cerebro de Jam, corte winding + Wayland | mismo comando | **861 OK**, 0.54 s; winding revertido → 4 rojos, normales desincronizadas → 3 rojos |
| Cara visible de la cinta | `tools/experiments/investiga_winding_ribbon_58.py` en `UnrealEditor-Cmd` | **control caja +Z=2/-Z=2 · cinta 48/48 a +Z · VEREDICTO VERDE** (antes del fix: 48/48 a -Z) |
| » y con los ojos | Brian, en el viewport | **la calzada se ve · el muro del lado correcto** |
| Ribbon S → M | `tools/experiments/verifica_mesh_ribbon_58.py` en `UnrealEditor-Cmd` | **25 pares · 48 tris/50 verts · ancho 360 · UV0 0..5.91 · Material ID 3 · TODO VERDE** |
| Tutoriales actuales | `tools/experiments/verifica_ejemplos.py` en `UnrealEditor-Cmd` | **13/13 compilan · TODO VERDE** |
| Extrude M → M / Muro | `tools/experiments/verifica_mesh_extrude_58.py` en `UnrealEditor-Cmd` | **48→196 tris · 50→100 verts · 300 cm · UV0/Material ID · cerrado · TODO VERDE** |
| Tutoriales tras muro | `tools/experiments/verifica_ejemplos.py` en `UnrealEditor-Cmd` | **14/14 compilan · TODO VERDE** |
| MassEntity core F → F | `tools/experiments/verifica_mass_entity_58.py` en `UnrealEditor-Cmd` | **37 válidas · 1 arquetipo `FTransformFragment` · transforms conservados · 37/37 destruidas · TODO VERDE** |
| MassEntity MS → MH | mismo script | **Run×2 reemplaza · Discard destruye · Bake conserva · Clear×2 y cambio de mapa dejan 0 · TODO VERDE** |
| MassEntity fin de PIE | `tools/experiments/verifica_mass_pie_58.py` en editor completo | **editor 3 vivas · PIE 3 vivas · cierre libera sólo PIE · mutante real rojo · TODO VERDE** |
| Tutoriales con MassEntity | `tools/experiments/verifica_ejemplos.py` en `UnrealEditor-Cmd` | **16/16 compilan · TODO VERDE** |
| Tutoriales con MassGameplay | mismo script | **17/17 compilan · config `/Jam/Mass/MC_JamSpatial` resuelve · TODO VERDE** |
| MassGameplay MC → MS → MH | `tools/experiments/verifica_mass_gameplay_58.py` en `UnrealEditor-Cmd` | **37/37 · `AJamMassSpawner` · transforms exactos · tutorial portable · Discard 0 vivas · TODO VERDE** |
| MassRepresentation ambiental | `tools/experiments/verifica_mass_representation_58.py` en editor completo | **High/Medium/Low/Off 1/1/1/1 · ISM/None 3/1 · 4 descriptores · Clear 0 · TODO VERDE** |
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
| Oracle en UE 5.8.1 | `tools/experiments/verifica_oracle_shadow.py` con editor completo | **placement + snap + scatter + spline + physics + reemplazo + espacio funcional verde; shutdown histórico rojo** |
| Physics paint en UE 5.8.1 | `tools/experiments/verifica_physics_paint_58.py` | **pila 0/100/200 · Preview ignorado · Landscape por pieza · 3 sombras coinciden** |
| oracle sobre sí mismo | `cd vendor/oracle && python tools/aceptacion.py` | **27 rojos · 12 verdes · 0 huecos** |
| oracle sobre Jam | `python vendor/oracle/tools/diferencial.py --proyecto medidas --confiar-escalares` | **1099 acuerdos · 4298 veredictos estables** (11 dominios: `malla` y `malla_solidos`) |
| » mutación de medidas | `python vendor/oracle/tools/mutar.py --proyecto medidas --confiar-escalares` | **303/303 mutantes muertos** |
| Sólidos en UE 5.8.1 | `tools/experiments/verifica_malla_solidos_58.py` | **caja 2.520.000 exacto · esfera y muro cerrados y positivos · caja invertida negativa · TODO VERDE** |
| » tests de oracle | `cd vendor/oracle && python -m unittest discover -s tests -t . -q` | **339 OK** |

El campo `verde_editor` apunta al checkpoint `4eaf0c7`, verificado en UE 5.8.1 con MS/MH,
Preview/Discard/Bake/Clear, cambio real de mapa y cierre PIE verde/discriminado. También conserva la evidencia previa de placement,
snap, scatter, spline, physics, reemplazo y espacio sobre actores reales. Las verificaciones previas de Graph interactivo y
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
| Apertura/cierre de Graph y entrada global | Brian | ◐ anduvo, pero el camino del fix nuevo (`reubicada=sí`) NO se ejecutó: sin verificar |
| El pliegue de `ribbon_core` en curvas cerradas | **nadie** | ⏳ medido y acotado por `malla`; **sin arreglar** |
| Selector de tipos completo | Brian | ⏳ falta desplegar la lista y confirmar la presentación real |
| Maths: Sumar/Restar/Multiplicar/Dividir, pines y resultado | Brian | ✅ función/instancia + Run + Inspector + persistencia; sin Preview vacío |
| Maths: Negar/Absoluto/Módulo/Potencia/Raíz | Brian | ⏳ tests/sonda/build verdes; falta gesto en Datos → Maths |
| Nanite Analyze/Validate, cable A → A y Run sin Preview | Brian | ⏳ tests + commandlet 5.8.1 verdes; falta gesto en Create → Nanite |
| Simplify Count/Tolerance/Edge, cables M → M | Brian | ⏳ 586 tests + Compile/Run/Inspector 5.8.1 verdes; falta gesto en Mesh → Optimizar |
| Reasignar/Limpiar Material IDs, cables M → M | Brian | ⏳ 586 tests + Graph 5.8.1 verde; falta gesto en Mesh → Materiales |
| Validar malla, requisitos y cable M → M | Brian | ⏳ 586 tests + Graph 5.8.1 verde; falta gesto en Mesh → Hornear |
| Copiar Static/Skeletal, LOD y cables A → M | Brian | ⏳ 586 tests + Graph 5.8.1 verde; falta gesto en Mesh → Hornear |
| Cinta de curva S → M y aspecto de Borde de camino | Brian | ✅ 2026-08-11: **estaba ROTO** (invisible por winding). Arreglado, medido y visto |
| Extruir superficie M → M y aspecto de Muro sobre spline | Brian | ✅ 2026-08-11: heredaba la vuelta de la cinta; corregido en la base y visto |
| Mass → Probar MassEntity, cable F → F y resultado | Brian | ✅ 2026-08-11: ficha, cable e informe correctos en Slate |
| Mass → MS/MH, cuatro fichas y ciclo Preview | Brian | ✅ 2026-08-11: las cinco fichas y sus cables se ven bien |
| Ribbon jerárquico por familias | Brian | ⏳ abrió/cerró sin crash; falta juzgar orden, densidad y navegación |
| Resto del ABM, `Ctrl+G` + dibujo/cableado de pines múltiples | Brian | ◐ Nueva/Editar/Guardar/Renombrar/Eliminar verdes; faltan `Ctrl+G` y firmas no numéricas |
| Aspecto de una GC Nanite fracturada y rotura en PIE | Brian | ⏳ metadata/materiales verdes; falta viewport y simulación |
| `drop`: la tanda se apila (era `place physics`) | Brian | ◐ 821 tests + sonda 5.8.1 real y sombra declarativa verdes; falta el gesto en el Graph |
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

**0. Cerrar el residuo de la cinta: muestras con avance despreciable.** El pliegue por cruce ya está
resuelto en el rango realista (ver «ESTADO DEL PLIEGUE» arriba). Quedan 7 de 20 en giros de 140°, y
son otra cosa: el borde no retrocede, avanza casi nada —1,4 cm contra ~460 del otro lado— y con Z
propia por muestra el triángulo casi sin base queda casi vertical. Pide su propio criterio y su
defensa de umbral: exigir avance mínimo proporcional al del eje, o fusionar muestras casi
coincidentes. `malla.cara_visible` ya lo juzga, así que el corte llega con oráculo puesto.

**Siguiente corte de la Fase 4 de
[[2026-08-09-ROADMAP-MassEntity-En-Jam-v1.0|MassEntity en Jam]]: variación o señal ambiental.** La
patrulla acotada ya demuestra un processor autónomo y representación dinámica. Agregar variación
determinista por entidad o una señal simple que cambie un estado medible; no agregar ZoneGraph ni
StateTree hasta que navegación o estados complejos sean una necesidad demostrada.

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

**5. Re-expresar los oráculos vivos restantes del plugin** como medidas. Ya están `placement`,
`snap`, `scatter`, la pared viva como `spline`, `physics` unitario/por lotes, `reemplazo` y
`espacio`. La migración en sombra del runtime vivo quedó completa; el paso siguiente es dejarla
madurar antes de decidir qué referencias históricas pueden retirarse.

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
