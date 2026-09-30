# Jam — instrucciones para el agente de turno

**Hablá y escribí en español.** Commits, documentos, comentarios de código y respuestas.

Este proyecto lo trabajan **dos agentes por turnos de 3-4 días**: Claude Code y Codex. Ninguno
recuerda el turno del otro, así que **todo lo que valga para mañana vive en el repo**, no en la
memoria de nadie.


> **2026-09-30 — una sola interfaz: la web** (decisión de Brian, tarea `mudar-a-web`). El Graph de
> C++ (`Source/JamEditor/`) está **congelado**: ninguna función nueva, sólo arreglos que bloqueen.
> Todo lo nuevo de interfaz va al editor web (`Content/Python/jam/web/`), que es uno solo para
> Unreal, Godot y Unity.

## Protocolo de tareas y relevo

- Para retomar: `tasks list` y `tasks show <id>`. `tasks` es el tracker, paquete aparte de Oracle
  desde 0.34.0: `uv tool install trackertast==0.1.0` (los verbos en español siguen como alias).
- La tarea es la fuente de verdad del pedido, los avances, la evidencia y los bloqueos.
- Anotá el relevo con `tasks note <id> "…"`; nunca en otro `.md` suelto.
- Todo pendiente nuevo va a `tasks new "<problema>" --sufijo <corto>`.
- Al dejar el trabajo, reemplazá la única sección `## Próximo paso` al final de la tarea.
- Si hay un bloqueo, escribí su causa y la acción concreta para destrabarlo.
- Commits: `<ID>: resumen`; cierre: `<ID>: done`, con la tarea CERRADA.
- `RELEVO.md` conserva evidencia histórica y las restricciones «No toques esto».
- `python tools/relevo.py` sigue comprobando la vigencia del editor; un rojo se anota en la tarea.
- Los gestos para Brian se siguen con `tasks list --etiqueta gestos`.
- «Para las manos de Brian» se conserva aunque esté vacía; sus avances se anotan en las tareas.
- El vault es documentación: se enlaza como evidencia, no se usa como lista de pendientes.

## Qué es Jam

Plugin de Unreal Engine 5.8.1: un asistente in-editor tipo Dash (PolygonFlow) para crear cosas
dentro del motor, **con una diferencia — todo lo que produce lo verifica un oráculo determinista**.
Crear libre con la mejor herramienta, medir desde afuera. El juego que lo empuja es BotOO
(`Brianholl/BotOO`), un Hunt: Showdown lovecrafteano de 1920.

## `oracle`: el verificador es un lenguaje aparte

Oracle es un metalenguaje de medidas para construir herramientas con un LLM. Jam es su primer
**proyecto** — sus medidas, sensores y fixtures viven en `medidas/`. **Desde el 2026-09-01 se consume
desde PyPI, ya no por subtree**: `vendor/oracle/` no existe más.

Jam lo usa por **dos caminos a la vez**, y hacen falta los dos:

```bash
# 1. los COMANDOS, para vos y para relevo.py
uv tool install oracle-metalenguaje          # deja los 10 ejecutables en el PATH
oracle --version                             # tiene que decir 0.38.0

oracle-corpus      --proyecto medidas
oracle-aceptacion  --proyecto medidas --confiar-escalares
oracle-diferencial --proyecto medidas --confiar-escalares
oracle-mutar       --proyecto medidas --confiar-escalares
oracle-estudio     --proyecto medidas --confiar-escalares
oracle test        --proyecto medidas --confiar-escalares   # la secuencia entera
oracle cobertura   --proyecto medidas --confiar-escalares   # qué promesas de Jam se miden
```

Los **requisitos** (`medidas/requisitos/*.requisito`) dicen qué promete Jam, qué medidas lo
defienden y qué queda sin medir; `oracle cobertura` los lista. Jam no tiene CI, así que
`.githooks/pre-push` corre `oracle cambios` en cada push y lo bloquea si el catálogo se afloja sin
reescribir su `porque` (un umbral subido, un `requiere` quitado). Se activa una vez por clon con
`git config core.hooksPath .githooks`. Las dos cosas necesitan Oracle 0.36.1 o posterior.

```bash
# 2. el PAQUETE, para el intérprete embebido de Unreal
python3 -m pip install --target vendor/oracle-pkg --no-deps "oracle-metalenguaje==0.38.0"
rm -rf vendor/oracle-pkg/bin        # scripts con shebang de esta máquina; no van al repo
```

⚠️ **`uv tool install` NO alcanza y borrar `vendor/oracle-pkg/` no rompe ningún verificador: rompe
el editor.** `bridge.py` pone ese directorio en el `sys.path` del intérprete de Unreal, que es el
suyo — no ve el entorno de `uv`, ni el del sistema, ni un venv del proyecto. Por eso sigue habiendo
un directorio en el repo, y por eso **igual es mejor que el subtree**: es un artefacto con versión
fijada (2,3 MB · 173 archivos, contra 3,5 MB · 284 del subtree), no una copia de un repositorio que
hay que acordarse de traer y que se puede editar a mano sin que nadie se entere.

**No edites `vendor/oracle-pkg/` a mano.** Una edición local desaparece en la próxima reinstalación
sin dejar rastro. Actualizar Oracle es cambiar el número en tres lugares —el `pip install` de arriba,
`ORACLE_VERSION` en `Content/Python/tests/test_oracle_embedding.py` y el `uv tool install`— y
reinstalar. **Fijá con `==`, nunca con `>=`**: un consumidor que se actualiza solo se pone rojo un
martes por algo que no cambió de su lado.

⚠️ **`oracle` es un SEGUNDO REPOSITORIO y se commitea aparte.** Vive en `~/Dev/oracle`
(`git@github.com:Segtem/oracle.git`) y se publica en PyPI como `oracle-metalenguaje`. El flujo ahora
es: cambiar arriba, commitear y empujar, **publicar una versión**, y recién ahí subir el número acá.
Al terminar el turno, **los dos repos tienen que quedar empujados** — `relevo.py --cerrar` sólo mira
Jam.

### Las tres sombras declaradas el 2026-09-01

Oracle 0.3.3 trae medidas que el subtree no tenía, y encontraron cosas reales que no se arreglan en
el commit de la migración. Están en `medidas/oracle.json` **en sombra**: se evalúan, se informan con
`[EN SOMBRA]` y no tumban la corrida. Apagarlas sería volver a un verde que no significa nada.

| medida | infracciones | cómo se cierra |
|---|---|---|
| `meta.toda_cantidad_comparada_tiene_unidad_derivable` | 54 | declarar los campos en `relaciones/`, por relación |
| `meta.todo_umbral_declara_de_donde_sale` | 41 | poner el `segun` de cada umbral, sin adivinar el número |
| `meta.la_medida_no_se_fija_solo_con_evidencia_fabricada` | 9 | transcribir corridas reales de las sondas; necesita el editor abierto |

**Una sombra no es una excepción permanente**, y las tres tienen fecha para poder envejecerlas.

### Tres deudas viejas que ya no están (medido el 2026-09-01)

El `id` desalineado de `004-coberturas-distintas`, `snap.al_ras`/`snap.comparte_cara`/
`scatter.cobertura` sin `donde` ni `agrupar`, y el `vault.json` vencido: las tres estaban cerradas al
medir. `oracle-corpus` sale **0 · 23 casos**. Y el corpus **sí tiene las dos polaridades**: la
aceptación informa **3 verdes correctos**, así que la deuda de «cero casos `verde_correcto`» tampoco
sigue en pie.

Lo que hay que saber antes de tocarlo, en una frase: **una medida es un dato**, y declara
obligatoriamente **la defensa de su umbral** y **qué NO ve**. El informe verde termina enumerando sus
puntos ciegos. Todo lo demás está en
`Vault-kb/00-Proceso/2026-07-30-INFORME-Oracle-Metalenguaje-De-Medidas-v1.0.md`.

## La arquitectura, en una regla

**El cerebro es puro y el adaptador es fino.**

- `Content/Python/jam/*.py` — cerebro. **Cero `import unreal`.** Por eso se puede testear sin motor,
  y por eso los **1237 tests corren en 0.7 s**.
- `Content/Python/jam/registro.py` — la **descripción** de cada verbo (params, tipos, opciones,
  pines, doc), sin `"fn"`. Es núcleo: se importa con `sys.modules["unreal"] = None`, y
  `test_nucleo_sin_motor.py` lo exige para él, `dsl`, `graph`, `flow`, `funcion` y el resto del
  núcleo. Un verbo nuevo se DESCRIBE acá y se IMPLEMENTA en el adaptador.
- `Content/Python/jam/tools.py` — el adaptador de Unreal de los verbos: las `t_*` y
  `IMPLEMENTA = {verbo: fn}`, que al importarse enchufa `"fn"` en el mismo diccionario
  (`tools.REGISTRO is registro.REGISTRO`). Tarea `fuera-del-motor`: el núcleo sale del motor y cada
  motor tiene su adaptador.
- `Content/Python/jam/ue.py` — **el único** adaptador al motor.
- `Source/JamEditor/` — C++ de Slate (paneles, Graph). La lógica sigue en Python; el C++ la llama
  con `ExecPythonCommandEx`.

Cuando una regla queda forzosamente duplicada en C++ (un hit-test, un color), **se ata con un test
que lee el `.cpp`** — el patrón de `test_paleta.py` y `test_layout.py`. Es la única forma de que el
cerebro y Slate no se separen en silencio.

## Recetas

Motor: `~/Dev/engines/UnrealEngine_5.8` (5.8.1).

**Proyecto host: `~/Dev/games/JamPlayground`** desde el 2026-08-15. Es un proyecto UE **mínimo**
creado para esto: arranca en **~15 s** y compila los tres módulos en **~38 s**, contra los 18 GB de
BotOO que había que cargar en cada iteración.

**BotOO (`~/Dev/games/BotOO`) sigue siendo la PRUEBA DE INTEGRACIÓN**, no el banco de trabajo. Antes
de dar por bueno un cambio grande, abrirlo también ahí: el plugin tiene que andar sobre un proyecto
real con arte y PCG, no sólo sobre un template vacío. Las trampas de logs de BotOO que están más
abajo siguen valiendo para esa pasada.

```bash
# tests del cerebro (rápido, sin motor) — el que se corre siempre
cd Content/Python/tests && PYTHONPATH=$PWD/.. python -m unittest discover -s . -p "test_*.py" -q

# vault de documentación (nombres, frontmatter, wikilinks)
python tools/vault.py            #  --indice reescribe Vault-kb/README.md

# compilar el C++ del editor Y COMPROBAR que el binario quedó al día
./BUILD-JAM.sh                   # --solo-ver para verificar sin compilar
# (BUILD-JAM.sh es sólo el lanzador; la lógica vive en tools/build.py)

# lo mismo a mano (~16-19 s incremental)
# -NoUBA: Unreal Build Accelerator se confunde con el symlink Plugins/Jam -> ~/Dev/jam
# (ASSERT: cross-process rename-while-open). Sin esa flag el build falla siempre.
ENG=~/Dev/engines/UnrealEngine_5.8
$ENG/Engine/Build/BatchFiles/Linux/Build.sh JamPlaygroundEditor Linux Development \
  -Project="$HOME/Dev/games/JamPlayground/JamPlayground.uproject" -WaitMutex -FromMsBuild -NoUBA

# correr algo dentro del editor, sin ventana
$ENG/Engine/Binaries/Linux/UnrealEditor-Cmd \
  $HOME/Dev/games/JamPlayground/JamPlayground.uproject \
  -run=pythonscript -script=/ruta/absoluta/al/script.py \
  -RenderOffScreen -unattended -nosplash -stdout

# la MISMA sonda contra BotOO, para la pasada de integración
$ENG/Engine/Binaries/Linux/UnrealEditor \
  $HOME/Dev/games/BotOO/BotOO.uproject -RenderOffScreen -unattended -nosplash \
  -ExecCmds="py /ruta/absoluta/al/script.py,QUIT_EDITOR"
```

**Una sonda que necesita el Graph de Slate abierto** (el canvas, no sólo el cerebro):
`-ExecCmds="Jam.AbrirGraph,py <sonda>.py"` sin `QUIT_EDITOR`, y la sonda avanza con
`unreal.register_slate_post_tick_callback` y sale sola con `unreal.SystemLibrary.quit_editor()`.
El modelo es `tools/experiments/verifica_texto_canvas_58.py`.

**Godot (base común, tarea `base-comun`).** El núcleo corre FUERA de Godot, en un Python común, y le
habla al plugin de editor `Godot/addons/jam/` (TCP 127.0.0.1:8792, una línea de JSON por pedido).
Banco de trabajo: `~/Dev/games/JamGodot` (el plugin entra por symlink). Godot headless:
`godot --headless --editor --path ~/Dev/games/JamGodot`. La prueba cruzada Unreal ↔ Godot/Unity es
`python tools/experiments/verifica_base_comun.py --motor godot|unity` (antes, `verifica_caja_comun_58.py`
en Unreal): corre todo el fixture común y compara triángulos, posiciones, caja, área y volumen con
signo. **Unity**: `Unity/Assets/Jam/Editor/` (C#, TCP 8793), banco `~/Dev/games/JamUnity` (symlink),
editor `~/Dev/engines/unity/6000.3.24f1` (la 6000.6.1f1 necesita `libxml2-legacy`); en batchmode
atiende con `-executeMethod Jam.JamServidor.Lote` hasta «salir». El contrato habla en el marco del núcleo —cm, Z arriba—; el plugin traduce, e INVIERTE cada
triángulo porque la traducción es una reflexión (medido con el `BoxMesh` de Godot). Cerrar Godot por
PID: `pkill -f` con el path del proyecto mata también al shell que lo lanzó.

⚠️ **La salida NO llega fiablemente a stdout.** El veredicto está en el `.log` más reciente de
`Saved/Logs/` del proyecto que se corrió — `JamPlayground*.log` o `BotOO*.log` según el caso. Si el
editor GUI está abierto, el commandlet paralelo escribe por ejemplo `BotOO_2.log`, no `BotOO.log`.

## Reglas que no se negocian

**Verificar por el camino REAL, no por el atajo.** Llamar la función directo, o con `unreal`
mockeado, **no es verificar**: una vez dieron verde cuatro bugs en una sola sesión. Si el camino
real pasa por el editor, se corre el editor.

**Probá que el test discrimina.** Rompé el código a propósito y mirá que el test se ponga rojo. Un
test que pasa con el código roto no es un test.

**Rutas absolutas en cualquier comando destructivo.** El *cwd* de bash persiste entre llamadas y ya
mordió.

**Licencias.** Los assets comerciales se pueden usar, modificar y shipear; **nunca** relicenciar ni
redistribuir, nunca relicenciar CC0. Los repos van privados.

**No se suelta el turno en rojo.** `python tools/relevo.py --cerrar` antes de soltar.

## Trampas medidas (cada una costó tiempo)

| Trampa | Qué pasa |
|---|---|
| `-nullrhi` en UE 5.7.x | **SIGFPE**. Usar `-RenderOffScreen`. |
| Leer siempre `BotOO.log` | Con el editor GUI abierto, el commandlet paralelo escribe `BotOO_2.log` (o el siguiente sufijo) y `BotOO.log` sigue perteneciendo a la GUI. Buscar el `BotOO*.log` más reciente. |
| Renombrar un id de nomad tab | Es la **clave persistente del layout**: le borra al usuario el acomodo de los paneles. |
| Pila de Material Layers sin los arrays *editor-only* paralelos | **Voltea el editor** (assert + SIGSEGV). |
| `Target.cs` desparejos | En UE 5.8.1, ambos con `BuildSettingsVersion.V7` + `EngineIncludeOrderVersion.Unreal5_8` o no comparte el entorno del motor. |
| Tocar C++ y no recompilar | El editor sigue corriendo el binario viejo y «no anduvo» miente. |
| Relojes distintos entre sandbox y host | UBT puede decir `Target is up to date` aunque cambió el `.cpp`, si el `.so` tiene una fecha futura. Comparar `stat`; tocar el fuente desde el host y comprobar un marcador con `strings -el` antes de abrir. |
| `Constant3Vector` | La propiedad es `constant`, no `r/g/b`. |
| Enums de UE | **No son subscriptables** — `getattr(Enum, nombre)`. |
| `get_statistics` de materiales | Da **cero** headless; el costo sólo se mide con GUI. |
| El AABB de un **landscape** como piso | Su caja llega hasta la loma más alta de TODO el mapa (medido: 121 m de ancho, `top`=3 m). Usarla para asentar deja cada pieza a esa cota, flotando sobre el terreno real. Del terreno habla `ue.raycast`, uno por pieza; el AABB sirve para cajas, no para superficies. |
| `add_dataflow_node` / `FieldSystem` headless | **Cuelgan**. Ese camino es sólo con editor GUI. |
| `spawn_actor_from_object` en commandlet | **Devuelve None** y sólo avisa con `LogUtils: SpawnActorFromObject. No actor was spawned.` Pasa con un mapa real cargado y un mundo válido (`spawn_actor_from_class` sí anda en la misma corrida). O sea: **`place.colocar` y todo lo que instancia no se pueden verificar headless**; la sonda verifica hasta la resolución de mallas y el acto de colocar queda para el editor GUI. |
| `add_edge` de PCG | **No lanza** al fallar: hay que verificar el grafo después. |
| Destructor explícito de un `TGuardValue` de pila | Doble destrucción. Usar un bloque con *scope*. |
| `grep --include=*.cpp` en fish | fish expande el glob: va **entre comillas**. |
| Mutar código y restaurar en el mismo segundo | CPython invalida el `.pyc` por (mtime, tamaño): `max` y `min` ocupan lo mismo, así que sigue corriendo el **bytecode mutado**. Limpiar `__pycache__` entre mutantes. |
| Matar un proceso que escribe sobre fuentes | **`SIGTERM` no ejecuta el `finally`**. Una corrida cortada dejó un archivo mutado en el árbol; hace falta `atexit` + manejadores de señal, y mirar `git status` después. |
| El trabajador aislado de `escalares.py` no importa `oracle_metalenguaje` | **Era un bug de Oracle 0.3.1 con el paquete vendorizado, y se arregló en 0.3.2.** `nucleo/aislamiento/escalares.py` lanzaba el trabajador con `env` REEMPLAZADO y `PYTHONPATH = RAIZ_ORACLE`, que en el wheel es el directorio del propio paquete — así que `medidas/escalares.py`, que hace `from oracle_metalenguaje import escalar`, moría con `ModuleNotFoundError`. Con el subtree andaba de casualidad, y desde un venv tampoco se veía porque ahí `site.py` agrega `site-packages` solo. Si vuelve a aparecer, el paquete vendorizado es anterior a 0.3.2: revendorizalo. Ver `DECISION-010` de Oracle. |
| Editar `vendor/oracle-pkg/` a mano | Es el wheel de PyPI, no un subtree: la edición desaparece en la próxima reinstalación sin dejar rastro. Se cambia arriba, se publica, y acá se sube el número. |
| Dar por compilado un cambio porque el build dijo `Result: Succeeded` | **`Succeeded` también lo imprime un build que no hizo nada.** Pasó: se reportó un fix de UI sobre un binario 35 minutos más viejo que la fuente, y el usuario vio el comportamiento anterior. Usar `python tools/build.py`, que compila y **verifica el timestamp** del binario base contra los fuentes. También detecta el caso del editor abierto, donde UBT linkea un `…-0001.so` de hot reload y el base queda viejo. Un build que sí trabajó imprime `[n/m] Compile …` y `[n/m] Link …`; filtrar la salida sólo por `error:|Result:` esconde justamente eso. |
| Medir una malla por sus `normals` | **Las normales de sombreado NO deciden qué lado se ve.** El backface culling mira el ORDEN DE LOS ÍNDICES. Una cinta puede declarar normales impecables hacia arriba y ser invisible desde arriba: pasó con `mesh_ribbon`, 790 tests en verde y el tutorial transparente en el viewport. Para juzgar la cara visible, `GeometryScript_MeshQueries.get_triangle_face_normal`, y con una malla nativa al lado como control. |
| `ls BotOO*.log` para leer el veredicto | El glob matchea **`BotOO-CRC.log`**, que no lleva salida de Python y suele ser el más reciente: la sonda parece muda aunque haya escrito su marcador. Filtrar: `ls -t …/BotOO*.log \| grep -v CRC \| head -1`. |
| Afinar el código hasta que la medida se ponga verde | Es Goodhart con pasos extra: la medida deja de ser un juez independiente y pasa a ser el objetivo. Si un arreglo no cubre todo, se declara el límite y se deja el caso medido en rojo — vale más que un número lindo. |
| `EditorAssetLibrary` sobre el content de un PLUGIN en commandlet | `does_asset_exist` devuelve **False** y `load_asset` **None** para un asset que existe en disco y que AssetTools sí ve —se niega a crearlo «porque ya existe»—. Medido con `/Jam/Mass/MC_JamAmbientPatrol`. Usar `unreal.load_object(None, "/Ruta/Asset.Asset")`, que sí lo carga. |
| Una sonda con `register_slate_post_tick_callback` en `-run=pythonscript` | **No corre nunca**: en commandlet no hay bucle de Slate, el callback no dispara y el editor sale en milisegundos informando «Python script executed successfully». Las sondas que necesitan PIE o ticks van en editor completo. |
| Crear una población Mass y leerla en el MISMO tick | Los fragments salen con su valor por defecto: el processor todavía no corrió sobre ella. Hay que devolverle el control al motor unos ticks entre crear y leer, y sin PIE los processors no tickean en absoluto. |
| Un lambda de Slate que captura `[this]` para leer un miembro | **Use-after-free** si el widget muere mientras su padre todavía se dibuja. Si el valor se usa como ÍNDICE, el editor cae con `Array index out of bounds` dentro de `DrawPrepass`. El número delata la causa: con optimización, `bMiembro ? 1 : 0` sobre un `bool` compila como **carga directa del byte** —el compilador sabe que un bool es 0 o 1—, así que la basura entra tal cual (medido: **254** en un `SWidgetSwitcher` de 2 slots). Capturar `TWeakPtr` y acotar el índice. Quedan 17 lambdas `[this]` más sólo en `SJamGraphNode.cpp`. |
| Un test que lee el `.cpp` buscando un patrón | **Los comentarios cuentan.** Un comentario que EXPLICA el bug suele nombrar el patrón prohibido, y el test se atrapa a sí mismo. Filtrar las líneas `//` antes de juzgar. |
| `SLATE_ARGUMENT(bool, X)` sin lista de inicialización en `SLATE_BEGIN_ARGS` | **Nace con basura de la pila.** Es un miembro POD crudo: quien no pasa `.X(...)` se lleva lo que hubiera ahí. Costó tres diagnósticos equivocados: el nodo salía en tamaño normal con el contenido compacto, y un `bool` basura de 254 volteaba el editor porque `X ? 1 : 0` compila como carga directa del byte. Inicializar SIEMPRE en `SLATE_BEGIN_ARGS(S) : _X(false)`. |
| Un `SWidgetSwitcher` cuyo índice sale de un lambda | Si el lambda lee memoria de un widget muerto, el índice es basura y el editor cae en `DrawPrepass` con `Array index out of bounds`. **Preferir dos hijos con `Visibility` en un `SOverlay`**: sin entero no hay índice fuera de rango. Costó tres intentos; los dos que atacaron el índice fallaron. |
| Cambiar `Visibility` por ATRIBUTO y esperar que `Invalidate` la reevalúe | No alcanza: Slate la cachea y el widget queda con el contenido de un modo y el TAMAÑO del otro, sin volver atrás. Guardar los widgets y llamar `SetVisibility` a mano. |
| Perseguir un crash que no podés reproducir leyendo el stack | Falló dos veces seguidas acá. Cuando el gesto necesita manos y no las tenés, **no adivines mejor: partí el problema**. Un cambio cuyo resultado sea informativo en las DOS direcciones —desaparece el crash o queda demostrado que la causa está afuera— vale más que un arreglo plausible. |
| Restaurar una mutación con `git checkout` | **Borra el trabajo no commiteado que estás probando.** Se muta el fuente para ver si el test discrimina, se hace `git checkout` para restaurar… y vuelve a HEAD, o sea sin el arreglo recién escrito. Las mutaciones siguientes «pasan» porque miden un archivo sin fix. Copiar el archivo a un `.bak` antes y restaurar desde ahí. El síntoma que lo delata: el caso SIN mutar también falla. |
| `re.findall("Foo")` para contar apariciones | Matchea también el prefijo de `FooBar`, así que la mutación que renombra `Foo`→`FooXX` no cambia la cuenta y el test pasa con el código roto. Anclar con lo que sigue (`Foo\(`). |
| Cronometrar UNA corrida, y encima la primera | El arranque frío del proceso —cargar clases, inicializar subsistemas— cae entero sobre el primer caso medido. Medido: una cadena que en régimen cuesta 2,6 ms cuesta **271 ms** en la vuelta 0. Calentar y descartar, y tomar la MEDIANA de varias vueltas. |
| Alternar A/B cuando cada corrida limpia lo que dejó la anterior | El costo aparece en la corrida equivocada. Medido: `mesh_preview` «costaba» 156 ms que en realidad eran el borrado del asset que había dejado `mesh_to_static` en la corrida previa. Cada variante en su TANDA, y descartar el estado heredado entre tandas. **Y muerde igual —o peor— cuando la alternancia se agrega como CONTROL**: se intercaló una serie de «mirar» para controlar la deriva del proceso y quedó en 250 ms por vuelta, contra 1,3 medida sola. **Un control que toca el estado compartido no controla nada**: para la deriva, repetir la MISMA tanda al final. |
| Medir crecimiento o deriva sobre una serie que ALTERNA | «Las primeras cinco contra las últimas cinco» mide qué ranuras cayeron adentro de cada ventana, no el tiempo. Medido: una serie que alterna 90 ms y 9 ms según la ranura daba «×1,28 hay deriva» y «×0,60 baja», dos veredictos opuestos sobre los mismos datos sanos. Separar por la variable que alterna ANTES de resumir, y si no se sabe cuál es, anotar la condición de cada vuelta en vez de deducirla por la paridad. |
| Medir headless algo que espera al RENDER THREAD | Un commandlet `-run=pythonscript` no tickea nunca, así que cualquier fence de render se paga con un plazo que no tiene nada que ver con el del editor de verdad. Medido: pisar un `StaticMesh` cargado espera en `StaticAllocateObject` a `IsReadyForFinishDestroy()` y cuesta ~85 ms headless — **y dormir 400 ms entre vueltas no lo baja**, porque no espera tiempo sino que le bombeen el render thread. Para esos costos, editor completo: `UnrealEditor … -RenderOffScreen -unattended -nosplash -ExecCmds="py <script>,QUIT_EDITOR"` (sin `-run=`), que tickea y no abre ventana. ⚠️ **`-ExecCmds` separa por COMAS, no por `;`**: con punto y coma el `; QUIT_EDITOR` entra como parte de la línea de Python y sale `SyntaxError: invalid decimal literal`. Esta misma celda tuvo el `;` mal durante un turno entero. |
| Correr un verificador sobre el conjunto VACÍO y leer el verde | Toda medida que cuenta defectos da cero sobre cero entidades, así que **un verificador que no encontró nada que mirar sale verde y es indistinguible de uno que miró todo y estaba bien**. Medido: `tools/vault.py` le pasaba `VAULT` a un `hechos()` que adentro hace `raiz / "Vault-kb"`, o sea `Vault-kb/Vault-kb`, que no existe. La sombra del oráculo evaluó **0 documentos y 0 enlaces** e imprimió «las dos implementaciones coinciden» sobre 70 documentos que nunca vio; lo destapó un enlace roto de verdad que el verificador a mano encontró y la sombra no. **Todo verificador tiene que publicar CUÁNTAS entidades midió, y negarse si son cero.** |
| Enseñarle algo nuevo a UNA ruta de cables y darlo por hecho | **Hay CUATRO lugares que reparten lo que viaja por un cable**, y no se parecen entre sí: `math_core.resolver` (valor→valor), `graph.ejecutar_detalle` (el ejecutor), `graph.compilar` (params de las tools) y `flow._param_wires` (el preflight paralelo). Medido: multi-salida se enseñó a dos, y un cable de `domain_construct.desde` a `pts_line.count` le entregaba al verbo el dominio ENTERO `(10.0, 90.0)`; `dsl.coaccionar` no reconocía la tupla, **descartaba el parámetro en silencio** y la línea corría con su default. Compile en verde, Run en verde, número equivocado. Un cambio en el reparto se prueba en las cuatro, y el único que las cruza es `_valor_del_pin`. |
| Elegir el texto que muestra un nodo por el TIPO de Python del valor | La pregunta es si RESOLVIÓ, no de qué tipo es. Medido: el panel formateaba número y texto y mandaba **todo lo demás** al saco de «(sin resolver)», así que un vector, un dominio o una matriz resueltos perfectos se dibujaban como si no hubieran resuelto — con el estado del nodo en «ok» al mismo tiempo. Es el silencio más caro de esta casa: *lo hizo* leído como *no hizo nada*. El tipo sólo puede decidir CUÁNTO se escribe. |
| Comparar contra el número exacto lo que se leyó de un DISPLAY | El nodo escribe con `.6g`: 37.416574 se dibuja «37.4166». Un `< 1e-6` contra el valor exacto da rojo con el código impecable. La tolerancia tiene que ser la del display, y sigue discriminando de sobra — un pin que entregara la parte de otro se equivoca en el primer decimal, no en el cuarto. |
| Leer `ok` del envelope de un Run | **`ejecutar_flow_json` no devuelve esa clave**, así que un grafo de puras ops de Flow —cualquiera que empiece con `pts_*`— sale con `ok = None` y un Run perfecto se lee como fallado. El veredicto que existe en las dos rutas es el estado POR NODO. |
| Verificar un efecto de escena CONTANDO actores | Dos cosas distintas dan la misma cuenta. Medido: marcar un nodo con el display flag dejaba 1 actor igual que sin marcarlo, y el assert «hay menos actores» daba rojo aunque el recorte funcionaba — era OTRO actor (`JamDebug_viz` en vez de `JamPreviewSolo`). Preguntar por IDENTIDAD (etiqueta, ruta, clase), no por cantidad. |
| Confiar en `cProfile` para ubicar costo del MOTOR | Sólo ve marcos de Python: el tiempo adentro de una llamada del binding queda sumado al `tottime` de la función que la hizo, sin desglose. Medido: el perfil decía «`to_static` 49,8 ms» y adentro eran 44 de `create_new_static_mesh_asset_from_mesh`. Sirve para saber QUÉ función, no QUÉ llamada. Y envolver el binding para cronometrarlo tampoco se puede: `TypeError: cannot set attribute of immutable type 'EditorAssetLibrary'`. Queda instrumentar el `.py` propio, con `.bak` y revirtiendo después. |
| Cronometrar los tramos que uno sospecha | Sólo encuentra lo que ya sospechabas. Medido: los cuatro tramos elegidos a mano explicaban **0,7 ms de 156**. Un perfilador no elige: `cProfile` alrededor del camino real puso la causa en una línea. Si la suma de los tramos no cierra con el total, la causa está afuera de lo que mediste. |
| Un `TSharedPtr` a algo que retiene UObjects (`FAssetThumbnailPool`, `FAssetThumbnail`) como miembro del módulo | Assert al cerrar el editor: `Index >= 0` en `UObjectArray.h`. **`ShutdownModule()` NO alcanza** — se intentó y el crash volvió igual: `FEngineLoop::Exit()` corre `GEngine->PreExit()` (que destruye los subsistemas de `GEditor`) **antes** de `FModuleManager::UnloadModulesAtShutdown()`, así que destructor y `ShutdownModule()` son igual de tarde. Hay que soltarlos en `FEditorDelegates::OnEditorPreExit`, que dispara antes de `PreExit()`; dejar la liberación también en `ShutdownModule()`, idempotente, cubre hot-reload y deshabilitar el plugin, donde `OnEditorPreExit` nunca dispara. |
| Dibujar el ID de un pin donde va su ETIQUETA | Un pin tiene dos nombres: el del **protocolo** (`out`, `eje_x`, `D`, `MX`), que viaja en las aristas y en los presets, y el **visible** (`dominio`, `eje X`, `rango`, `matriz`). Cada vez que la presentación toma el primero, la persona lee un identificador. Ya pasó **dos veces con el mismo nodo**: los pines de tipo mostraban la letra cruda (`05272b9`), y las filas de salida de un nodo multi-salida muestran el ID (`out (rango)` en vez de `dominio`) porque `out_label` sólo alimenta el nub del header, que se apaga cuando hay filas. La regla: si una struct de presentación tiene un solo campo de nombre, ese campo es el **ID**, y falta el otro. |
| Pasarle a Unreal una matriz de Jam tal cual | **Las convenciones son OPUESTAS y una matriz mal leída no falla: transforma mal.** Jam almacena por FILAS con vectores COLUMNA y la traslación en la última COLUMNA, así que `a × b` aplica primero `b`; Unreal usa vectores FILA con la traslación en la última FILA. La traducción es una transposición y va **en `ue.py`**, que es el único adaptador — no en el cerebro, que tiene la convención escrita en un solo lugar (arriba de `_matriz`, en `math_core.py`). Hoy no hay ningún consumidor en `ue.py`: el primero que lo escriba es el que paga esta trampa. |
| Encadenar el commit después de filtrar la suite con `grep` | `… unittest … \| grep -E "^OK\|FAIL" && git commit` commitea con la suite ROJA: el `grep` encuentra la línea `FAILED` y sale 0. Pasó el 2026-09-28 (un commit empujado en rojo). Decidir por el **código de salida de la suite**, no por su texto. |
| Devolver un valor «razonable» cuando la cuenta no tiene respuesta | La inversa de una matriz singular no es la identidad, y una que espeja no se descompone en escalas positivas. Devolver algo plausible deja todo andando y todo transformando mal — el defecto más caro es el que no se nota. Se levanta `ValorError` con el motivo adentro; el nodo lo muestra y el Compile queda rojo. |

## Dónde está escrito lo demás

- **`RELEVO.md`** — el turno actual. Siempre vigente, siempre uno solo.
- **`Vault-kb/`** — 70 documentos en 5 carpetas (`00-Proceso`, `01-Graph`, `02-TreeGen`,
  `03-Mesh-y-materiales`, `04-Ejecucion-y-pruebas`). Nomenclatura `AAAA-MM-DD-TIPO-Nombre-vX.X.md`,
  y **el `area:` de cada doc tiene que ser su carpeta** — lo verifica `tools/vault.py`. Empezá por
  `Vault-kb/README.md`, que es el índice generado (no se edita a mano).
- El protocolo de relevo, explicado:
  `Vault-kb/00-Proceso/2026-07-29-GUIA-Relevo-Claude-Codex-v1.0.md`.
