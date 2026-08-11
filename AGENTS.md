# Jam — instrucciones para el agente de turno

**Hablá y escribí en español.** Commits, documentos, comentarios de código y respuestas.

Este proyecto lo trabajan **dos agentes por turnos de 3-4 días**: Claude Code y Codex. Ninguno
recuerda el turno del otro, así que **todo lo que valga para mañana vive en el repo**, no en la
memoria de nadie.

## Lo primero, siempre

```bash
python tools/relevo.py          # ¿en qué turno estoy y llegó verde?
```

Después leé **`RELEVO.md`** entero. Es corto a propósito. La sección **«No toques esto»** te ahorra
un día; la de **«Frontera de verificación»** te dice qué está sin probar, o sea sobre qué **no**
conviene construir todavía.

## Qué es Jam

Plugin de Unreal Engine 5.8.1: un asistente in-editor tipo Dash (PolygonFlow) para crear cosas
dentro del motor, **con una diferencia — todo lo que produce lo verifica un oráculo determinista**.
Crear libre con la mejor herramienta, medir desde afuera. El juego que lo empuja es BotOO
(`Brianholl/BotOO`), un Hunt: Showdown lovecrafteano de 1920.

## `oracle`: el verificador es un lenguaje aparte

`vendor/oracle/` es un **subtree** de `Segtem/oracle`: un metalenguaje de medidas para construir
herramientas con un LLM. Jam es su primer **proyecto** — sus medidas, sensores y fixtures viven en
`medidas/`.

```bash
python vendor/oracle/tools/diferencial.py --proyecto medidas --confiar-escalares
python vendor/oracle/tools/mutar.py       --proyecto medidas --confiar-escalares
python vendor/oracle/tools/estudio.py     --proyecto medidas --confiar-escalares
```

⚠️ **`oracle` es un SEGUNDO REPOSITORIO y se commitea aparte.** Vive en `~/Dev/oracle`
(`git@github.com:Segtem/oracle.git`). El flujo es siempre el mismo:

```bash
cd ~/Dev/oracle && …cambiar… && git commit && git push        # 1. arriba
cd ~/Dev/jam && git subtree pull --prefix=vendor/oracle \
    git@github.com:Segtem/oracle.git main --squash            # 2. traer
git commit && git push                                        # 3. abajo
```

**No edites `vendor/oracle/` a mano**: es una copia vendorizada y editarla la separa del upstream en
silencio. Y al terminar el turno, **los dos repos tienen que quedar empujados** — `relevo.py --cerrar`
sólo mira Jam.

Lo que hay que saber antes de tocarlo, en una frase: **una medida es un dato**, y declara
obligatoriamente **la defensa de su umbral** y **qué NO ve**. El informe verde termina enumerando sus
puntos ciegos. Todo lo demás está en
`Vault-kb/00-Proceso/2026-07-30-INFORME-Oracle-Metalenguaje-De-Medidas-v1.0.md`.

## La arquitectura, en una regla

**El cerebro es puro y el adaptador es fino.**

- `Content/Python/jam/*.py` — cerebro. **Cero `import unreal`.** Por eso se puede testear sin motor,
  y por eso los 489 tests corren en 0.3 s.
- `Content/Python/jam/ue.py` — **el único** adaptador al motor.
- `Source/JamEditor/` — C++ de Slate (paneles, Graph). La lógica sigue en Python; el C++ la llama
  con `ExecPythonCommandEx`.

Cuando una regla queda forzosamente duplicada en C++ (un hit-test, un color), **se ata con un test
que lee el `.cpp`** — el patrón de `test_paleta.py` y `test_layout.py`. Es la única forma de que el
cerebro y Slate no se separen en silencio.

## Recetas

Motor: `~/Dev/engines/UnrealEngine_5.8` (5.8.1) · proyecto host: `/home/workstation/Dev/games/BotOO`.

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
$ENG/Engine/Build/BatchFiles/Linux/Build.sh BotOOEditor Linux Development \
  -Project="/home/workstation/Dev/games/BotOO/BotOO.uproject" -WaitMutex -FromMsBuild -NoUBA

# correr algo dentro del editor, sin ventana
$ENG/Engine/Binaries/Linux/UnrealEditor-Cmd \
  /home/workstation/Dev/games/BotOO/BotOO.uproject \
  -run=pythonscript -script=/ruta/absoluta/al/script.py \
  -RenderOffScreen -unattended -nosplash -stdout
```

⚠️ **La salida NO llega fiablemente a stdout.** El veredicto está en el `.log` más reciente de
`/home/workstation/Dev/games/BotOO/Saved/Logs/BotOO*.log`; si el editor GUI está abierto, el
commandlet paralelo escribe por ejemplo `BotOO_2.log`, no `BotOO.log`.

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
| Editar `vendor/oracle/` a mano | Es un subtree: se separa del upstream en silencio. Se cambia arriba y se trae con `git subtree pull`. |
| Dar por compilado un cambio porque el build dijo `Result: Succeeded` | **`Succeeded` también lo imprime un build que no hizo nada.** Pasó: se reportó un fix de UI sobre un binario 35 minutos más viejo que la fuente, y el usuario vio el comportamiento anterior. Usar `python tools/build.py`, que compila y **verifica el timestamp** del binario base contra los fuentes. También detecta el caso del editor abierto, donde UBT linkea un `…-0001.so` de hot reload y el base queda viejo. Un build que sí trabajó imprime `[n/m] Compile …` y `[n/m] Link …`; filtrar la salida sólo por `error:|Result:` esconde justamente eso. |
| Medir una malla por sus `normals` | **Las normales de sombreado NO deciden qué lado se ve.** El backface culling mira el ORDEN DE LOS ÍNDICES. Una cinta puede declarar normales impecables hacia arriba y ser invisible desde arriba: pasó con `mesh_ribbon`, 790 tests en verde y el tutorial transparente en el viewport. Para juzgar la cara visible, `GeometryScript_MeshQueries.get_triangle_face_normal`, y con una malla nativa al lado como control. |
| `ls BotOO*.log` para leer el veredicto | El glob matchea **`BotOO-CRC.log`**, que no lleva salida de Python y suele ser el más reciente: la sonda parece muda aunque haya escrito su marcador. Filtrar: `ls -t …/BotOO*.log \| grep -v CRC \| head -1`. |
| Afinar el código hasta que la medida se ponga verde | Es Goodhart con pasos extra: la medida deja de ser un juez independiente y pasa a ser el objetivo. Si un arreglo no cubre todo, se declara el límite y se deja el caso medido en rojo — vale más que un número lindo. |
| `EditorAssetLibrary` sobre el content de un PLUGIN en commandlet | `does_asset_exist` devuelve **False** y `load_asset` **None** para un asset que existe en disco y que AssetTools sí ve —se niega a crearlo «porque ya existe»—. Medido con `/Jam/Mass/MC_JamAmbientPatrol`. Usar `unreal.load_object(None, "/Ruta/Asset.Asset")`, que sí lo carga. |
| Una sonda con `register_slate_post_tick_callback` en `-run=pythonscript` | **No corre nunca**: en commandlet no hay bucle de Slate, el callback no dispara y el editor sale en milisegundos informando «Python script executed successfully». Las sondas que necesitan PIE o ticks van en editor completo. |
| Crear una población Mass y leerla en el MISMO tick | Los fragments salen con su valor por defecto: el processor todavía no corrió sobre ella. Hay que devolverle el control al motor unos ticks entre crear y leer, y sin PIE los processors no tickean en absoluto. |
| Un lambda de Slate que captura `[this]` para leer un miembro | **Use-after-free** si el widget muere mientras su padre todavía se dibuja. Si el valor se usa como ÍNDICE, el editor cae con `Array index out of bounds` dentro de `DrawPrepass`. El número delata la causa: con optimización, `bMiembro ? 1 : 0` sobre un `bool` compila como **carga directa del byte** —el compilador sabe que un bool es 0 o 1—, así que la basura entra tal cual (medido: **254** en un `SWidgetSwitcher` de 2 slots). Capturar `TWeakPtr` y acotar el índice. Quedan 17 lambdas `[this]` más sólo en `SJamGraphNode.cpp`. |
| Un test que lee el `.cpp` buscando un patrón | **Los comentarios cuentan.** Un comentario que EXPLICA el bug suele nombrar el patrón prohibido, y el test se atrapa a sí mismo. Filtrar las líneas `//` antes de juzgar. |
| Un `SWidgetSwitcher` cuyo índice sale de un lambda | Si el lambda lee memoria de un widget muerto, el índice es basura y el editor cae en `DrawPrepass` con `Array index out of bounds`. **Preferir dos hijos con `Visibility` en un `SOverlay`**: sin entero no hay índice fuera de rango. Costó tres intentos; los dos que atacaron el índice fallaron. |
| Cambiar `Visibility` por ATRIBUTO y esperar que `Invalidate` la reevalúe | No alcanza: Slate la cachea y el widget queda con el contenido de un modo y el TAMAÑO del otro, sin volver atrás. Guardar los widgets y llamar `SetVisibility` a mano. |
| Perseguir un crash que no podés reproducir leyendo el stack | Falló dos veces seguidas acá. Cuando el gesto necesita manos y no las tenés, **no adivines mejor: partí el problema**. Un cambio cuyo resultado sea informativo en las DOS direcciones —desaparece el crash o queda demostrado que la causa está afuera— vale más que un arreglo plausible. |
| Restaurar una mutación con `git checkout` | **Borra el trabajo no commiteado que estás probando.** Se muta el fuente para ver si el test discrimina, se hace `git checkout` para restaurar… y vuelve a HEAD, o sea sin el arreglo recién escrito. Las mutaciones siguientes «pasan» porque miden un archivo sin fix. Copiar el archivo a un `.bak` antes y restaurar desde ahí. El síntoma que lo delata: el caso SIN mutar también falla. |
| `re.findall("Foo")` para contar apariciones | Matchea también el prefijo de `FooBar`, así que la mutación que renombra `Foo`→`FooXX` no cambia la cuenta y el test pasa con el código roto. Anclar con lo que sigue (`Foo\(`). |
| Un `TSharedPtr` a algo que retiene UObjects (`FAssetThumbnailPool`, `FAssetThumbnail`) como miembro del módulo | Assert al cerrar el editor: `Index >= 0` en `UObjectArray.h`. **`ShutdownModule()` NO alcanza** — se intentó y el crash volvió igual: `FEngineLoop::Exit()` corre `GEngine->PreExit()` (que destruye los subsistemas de `GEditor`) **antes** de `FModuleManager::UnloadModulesAtShutdown()`, así que destructor y `ShutdownModule()` son igual de tarde. Hay que soltarlos en `FEditorDelegates::OnEditorPreExit`, que dispara antes de `PreExit()`; dejar la liberación también en `ShutdownModule()`, idempotente, cubre hot-reload y deshabilitar el plugin, donde `OnEditorPreExit` nunca dispara. |

## Dónde está escrito lo demás

- **`RELEVO.md`** — el turno actual. Siempre vigente, siempre uno solo.
- **`Vault-kb/`** — 48 documentos en 5 carpetas (`00-Proceso`, `01-Graph`, `02-TreeGen`,
  `03-Mesh-y-materiales`, `04-Ejecucion-y-pruebas`). Nomenclatura `AAAA-MM-DD-TIPO-Nombre-vX.X.md`,
  y **el `area:` de cada doc tiene que ser su carpeta** — lo verifica `tools/vault.py`. Empezá por
  `Vault-kb/README.md`, que es el índice generado (no se edita a mano).
- El protocolo de relevo, explicado:
  `Vault-kb/00-Proceso/2026-07-29-GUIA-Relevo-Claude-Codex-v1.0.md`.
