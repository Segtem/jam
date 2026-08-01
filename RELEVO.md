---
turno: 2026-08-01 · codex → claude-code
saliente: codex
entrante: claude-code
desde: 2026-08-01
verde_editor: b7b886e
verde_editor_fecha: 2026-08-01
---

# Testigo

Entra **codex**. Corré `python tools/relevo.py` antes de leer esto; si sale rojo, eso es el turno.

El turno que cierra hizo dos cosas grandes. En **Jam**: el roadmap de accesibilidad del Graph (fases 0
a 3) y las funciones con firma (fase 5, cerebro). Y después nació **`oracle`** —repo aparte,
`Segtem/oracle`— que es un metalenguaje de medidas para construir herramientas con un LLM. Jam pasó a
ser su primer proyecto.

Codex completó arriba de eso la **capa Slate de la Fase 5**: funciones dinámicas en el ribbon con
pines múltiples nombrados y `Ctrl+G` para colapsar una selección. El borde y el colapso viven en
Python puro; C++ sólo dibuja y transmite el gesto.

**Leé primero** `Vault-kb/00-Proceso/2026-07-30-INFORME-Oracle-Metalenguaje-De-Medidas-v1.0.md`: son
diez minutos y sin eso la mitad de los archivos nuevos no se entienden.

## Verde al soltar

| Qué | Comando | Resultado |
|---|---|---|
| Cerebro de Jam | `cd Content/Python/tests && PYTHONPATH=$PWD/.. python -m unittest discover -s . -p "test_*.py" -q` | **496 OK**, 0.3 s |
| Vault (modo sombra) | `python tools/vault.py` | **48 docs · las dos implementaciones coinciden** |
| Motor | `tools/experiments/verifica_funcion_graph.py` headless | **guardar + firma en ribbon + 2 instancias + Compile · TODO VERDE** |
| oracle sobre sí mismo | `cd ~/Dev/oracle && python tools/aceptacion.py` | **15 rojos · 11 verdes · 3 huecos** |
| oracle sobre Jam | `python vendor/oracle/tools/diferencial.py --proyecto medidas` | **269 veredictos, 0 desacuerdos** |
| » mutación de medidas | `python vendor/oracle/tools/mutar.py --proyecto medidas` | **80/80 mutantes muertos** |
| » tests de oracle | `cd ~/Dev/oracle && python -m unittest discover -s tests -t . -q` | **111 OK** |

El campo `verde_editor` todavía apunta al último commit cerrado (`80373ea`). El worktree actual sí se
compiló y pasó `verifica_funcion_graph.py`, pero **antes de cerrar** hay que commitearlo, actualizar
ese campo al commit verificado y volver a correr `relevo.py --cerrar`; mientras tanto el rojo del
relevo por código vivo modificado es correcto.

**Un rojo conocido y deliberado:** `cd ~/Dev/oracle && python tools/mutar_codigo.py` deja **31
mutantes vivos** de 242. Es código del núcleo que ningún test fija, y el número está a la vista a
propósito. **No los declares equivalentes en masa para pintar verde** — sería exactamente el Goodhart
que el repo persigue. Bajan escribiendo tests, o declarando equivalentes **de a uno con su razón
escrita** en `equivalentes.json`. Tarda varios minutos: corré con timeout largo.

## Frontera de verificación

Lo anterior de Slate quedó **cerrado** el 2026-07-29: Brian confirmó marquee, historial,
portapapeles, docking y alinear. La Fase 5 nueva compiló y pasó por Unreal headless, pero nadie ejerció
todavía su gesto ni miró sus pines en el panel; ésa es la nueva frontera.

Lo que **nadie ejerció con las manos** de este turno:

| Cosa | Quién puede verificarla | Estado |
|---|---|---|
| `Ctrl+G` + dibujo/cableado de pines múltiples de función | Brian | ⏳ compilado y headless verde; falta gesto |
| El paquete de estudio subido a NotebookLM | Brian | ⏳ generado, sin abrir |
| Que el informe del modo sombra de `vault.py` se lea bien | Brian | ⏳ |
| Todo lo demás de `oracle` | ✅ sus propias herramientas, el diferencial y la mutación | verificado |

## Para las manos de Brian

**Funciones del Graph — cinco gestos, diez minutos:**

1. Abrí Jam ▸ Graph y armá una cadena de cuatro nodos Mesh.
2. Seleccioná los dos del medio y apretá `Ctrl+G`: deben quedar reemplazados por una función cableada.
3. Abrí el tab **Funciones**: la ficha nueva debe instanciar un nodo con `in` y `salida` legibles.
4. Agregá una segunda instancia en serie y tendé sus dos cables por esos pines.
5. Compile: tiene que dar verde y listar nodos `f1__…`/`f2__…` (el nombre exacto del primer id puede variar).

En el primer intento manual, `Ctrl+G` sí guardó el preset pero Slate mostró «respuesta ilegible»:
`preset.guardar` había escrito un log antes del JSON y `ExecPythonCapture` los concatenó. El borde C++
ahora imprime `JAMCOLLAPSE:` y recorta desde la última aparición antes de deserializar; el contrato
está atado en `test_funcion.py`, discriminó al mutarlo y el plugin recompiló. Falta repetir el gesto
con el binario nuevo. Quedó como artefacto válido de ese intento el preset local
`funcion-072657-271.json`; no se borró automáticamente.

Después, sin urgencia: subir `~/Dev/oracle/estudio/` a NotebookLM. Empezá por `00-esencia.md`,
`08-los-numeros.md` y `07-el-diario.md`.

*(Esta sección es obligatoria y no se borra cuando está vacía: si se pudiera omitir, un turno dejaría
de pedir manos sin que nadie lo note.)*

## Lo próximo

**1. Fase 7 del Graph — bypass (`D`) y comentarios (`C`).** El bypass es cerebro y por lo tanto
verificable; el comentario es Slate.

**2. Los 31 mutantes de código vivos de `oracle`**, de a uno.

**3. Reemplazar de verdad los verificadores escritos a mano** de Jam (`vault.py`, `relevo.py`). Están
re-expresados como medidas y verificados por diferencial, y **siguen en uso los originales**. El
reemplazo va cuando el diferencial lleve tiempo en verde, no el mismo día en que se escribió.

**4. Re-expresar los otros cinco oráculos vivos del plugin** como medidas: `scatter`, `pared`,
`physics`, `reemplazo`, `espacio`. Ya están `placement` y `snap`. Cada uno con su sensor y su
diferencial, siguiendo el patrón de `tools/emitir_diferencial.py`.

⚠️ **La trampa del paso 4**: `jam/oracle_*.py` los llama el **editor**, así que el vendor tendría que
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
