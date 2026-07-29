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

Plugin de Unreal Engine 5.7.4: un asistente in-editor tipo Dash (PolygonFlow) para crear cosas
dentro del motor, **con una diferencia — todo lo que produce lo verifica un oráculo determinista**.
Crear libre con la mejor herramienta, medir desde afuera. El juego que lo empuja es BotOO
(`Brianholl/BotOO`), un Hunt: Showdown lovecrafteano de 1920.

## La arquitectura, en una regla

**El cerebro es puro y el adaptador es fino.**

- `Content/Python/jam/*.py` — cerebro. **Cero `import unreal`.** Por eso se puede testear sin motor,
  y por eso los 459 tests corren en 0.3 s.
- `Content/Python/jam/ue.py` — **el único** adaptador al motor.
- `Source/JamEditor/` — C++ de Slate (paneles, Graph). La lógica sigue en Python; el C++ la llama
  con `ExecPythonCommandEx`.

Cuando una regla queda forzosamente duplicada en C++ (un hit-test, un color), **se ata con un test
que lee el `.cpp`** — el patrón de `test_paleta.py` y `test_layout.py`. Es la única forma de que el
cerebro y Slate no se separen en silencio.

## Recetas

Motor: `~/Dev/engines/UnrealEngine_5.7` · proyecto host: `/home/workstation/Dev/games/BotOO`.

```bash
# tests del cerebro (rápido, sin motor) — el que se corre siempre
cd Content/Python/tests && PYTHONPATH=$PWD/.. python -m unittest discover -s . -p "test_*.py" -q

# vault de documentación (nombres, frontmatter, wikilinks)
python tools/vault.py            #  --indice reescribe Vault-kb/README.md

# compilar el C++ del editor  (~16-19 s incremental)
ENG=~/Dev/engines/UnrealEngine_5.7
$ENG/Engine/Build/BatchFiles/Linux/Build.sh BotOOEditor Linux Development \
  -Project="/home/workstation/Dev/games/BotOO/BotOO.uproject" -WaitMutex -FromMsBuild

# correr algo dentro del editor, sin ventana
$ENG/Engine/Binaries/Linux/UnrealEditor-Cmd \
  /home/workstation/Dev/games/BotOO/BotOO.uproject \
  -run=pythonscript -script=/ruta/absoluta/al/script.py \
  -RenderOffScreen -unattended -nosplash -stdout
```

⚠️ **La salida NO llega fiablemente a stdout.** El veredicto está en
`/home/workstation/Dev/games/BotOO/Saved/Logs/BotOO.log`.

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
| Renombrar un id de nomad tab | Es la **clave persistente del layout**: le borra al usuario el acomodo de los paneles. |
| Pila de Material Layers sin los arrays *editor-only* paralelos | **Voltea el editor** (assert + SIGSEGV). |
| `Target.cs` desparejos | Ambos con `BuildSettingsVersion.V6` + `EngineIncludeOrderVersion.Unreal5_7` o no compila. |
| Tocar C++ y no recompilar | El editor sigue corriendo el binario viejo y «no anduvo» miente. |
| `Constant3Vector` | La propiedad es `constant`, no `r/g/b`. |
| Enums de UE | **No son subscriptables** — `getattr(Enum, nombre)`. |
| `get_statistics` de materiales | Da **cero** headless; el costo sólo se mide con GUI. |
| `add_dataflow_node` / `FieldSystem` headless | **Cuelgan**. Ese camino es sólo con editor GUI. |
| `add_edge` de PCG | **No lanza** al fallar: hay que verificar el grafo después. |
| Destructor explícito de un `TGuardValue` de pila | Doble destrucción. Usar un bloque con *scope*. |
| `grep --include=*.cpp` en fish | fish expande el glob: va **entre comillas**. |

## Dónde está escrito lo demás

- **`RELEVO.md`** — el turno actual. Siempre vigente, siempre uno solo.
- **`Vault-kb/`** — 46 documentos en 5 carpetas (`00-Proceso`, `01-Graph`, `02-TreeGen`,
  `03-Mesh-y-materiales`, `04-Ejecucion-y-pruebas`). Nomenclatura `AAAA-MM-DD-TIPO-Nombre-vX.X.md`,
  y **el `area:` de cada doc tiene que ser su carpeta** — lo verifica `tools/vault.py`. Empezá por
  `Vault-kb/README.md`, que es el índice generado (no se edita a mano).
- El protocolo de relevo, explicado:
  `Vault-kb/00-Proceso/2026-07-29-GUIA-Relevo-Claude-Codex-v1.0.md`.
