---
turno: 2026-07-30 · claude-code → codex
saliente: claude-code
entrante: codex
desde: 2026-07-30
verde_editor: 80373ea
verde_editor_fecha: 2026-07-29
---

# Testigo

Entra **codex**. Corré `python tools/relevo.py` antes de leer esto; si sale rojo, eso es el turno.

El turno que cierra hizo dos cosas grandes. En **Jam**: el roadmap de accesibilidad del Graph (fases 0
a 3) y las funciones con firma (fase 5, cerebro). Y después nació **`oracle`** —repo aparte,
`Segtem/oracle`— que es un metalenguaje de medidas para construir herramientas con un LLM. Jam pasó a
ser su primer proyecto.

**Leé primero** `Vault-kb/00-Proceso/2026-07-30-INFORME-Oracle-Metalenguaje-De-Medidas-v1.0.md`: son
diez minutos y sin eso la mitad de los archivos nuevos no se entienden.

## Verde al soltar

| Qué | Comando | Resultado |
|---|---|---|
| Cerebro de Jam | `cd Content/Python/tests && PYTHONPATH=$PWD/.. python -m unittest discover -s . -p "test_*.py" -q` | **489 OK**, 0.3 s |
| Vault (modo sombra) | `python tools/vault.py` | **48 docs · las dos implementaciones coinciden** |
| Motor | `tools/experiments/verifica_ejemplos.py` headless | **8/8 tutoriales · TODO VERDE** |
| oracle sobre sí mismo | `cd ~/Dev/oracle && python tools/aceptacion.py` | **15 rojos · 11 verdes · 3 huecos** |
| oracle sobre Jam | `python vendor/oracle/tools/diferencial.py --proyecto medidas` | **269 veredictos, 0 desacuerdos** |
| » mutación de medidas | `python vendor/oracle/tools/mutar.py --proyecto medidas` | **80/80 mutantes muertos** |
| » tests de oracle | `cd ~/Dev/oracle && python -m unittest discover -s tests -t . -q` | **111 OK** |

La verificación con motor es del commit `80373ea`; desde ahí no se tocó `Source/`, `Content/Python/`
ni `oraculo/`. `relevo.py` lo comprueba solo.

**Un rojo conocido y deliberado:** `cd ~/Dev/oracle && python tools/mutar_codigo.py` deja **31
mutantes vivos** de 242. Es código del núcleo que ningún test fija, y el número está a la vista a
propósito. **No los declares equivalentes en masa para pintar verde** — sería exactamente el Goodhart
que el repo persigue. Bajan escribiendo tests, o declarando equivalentes **de a uno con su razón
escrita** en `equivalentes.json`. Tarda varios minutos: corré con timeout largo.

## Frontera de verificación

Lo de Slate quedó **cerrado** el 2026-07-29: Brian probó el editor y confirmó que todo funciona
—marquee, historial, portapapeles, docking, alinear—. Desde entonces no se escribió nada de Slate, así
que esa frontera sigue en pie.

Lo que **nadie ejerció con las manos** de este turno:

| Cosa | Quién puede verificarla | Estado |
|---|---|---|
| El paquete de estudio subido a NotebookLM | Brian | ⏳ generado, sin abrir |
| Que el informe del modo sombra de `vault.py` se lea bien | Brian | ⏳ |
| Todo lo demás de `oracle` | ✅ sus propias herramientas, el diferencial y la mutación | verificado |

## Para las manos de Brian

**Una sola cosa, y no es urgente:** subir `~/Dev/oracle/estudio/` a NotebookLM y estudiarlo. Son 10
documentos planos, 212 KB, generados por `python vendor/oracle/tools/estudio.py --proyecto medidas`.
Empezá por `00-esencia.md` y `08-los-numeros.md` —diez minutos— y después `07-el-diario.md`, que es el
más revelador porque muestra el proceso y no el resultado.

Nada en el editor está esperando manos. Si Codex escribe Slate este turno, **tiene que volver a
listarlo acá**: máximo seis gestos, quince minutos. Es el mecanismo que funcionó — cuatro tandas
pidiendo «probá cuando puedas» no habían movido nada.

*(Esta sección es obligatoria y no se borra cuando está vacía: si se pudiera omitir, un turno dejaría
de pedir manos sin que nadie lo note.)*

## Lo próximo

**1. Fase 5 — la capa de Slate de las funciones del Graph.** El cerebro está hecho y cableado
(`jam/funcion.py`, 18 tests, expansión inline verificada contra el grafo plano equivalente; el informe
está en `Vault-kb/01-Graph/`). Falta lo de arriba, que es gesto:

- **instanciar desde el ribbon**: `funcion.firma()` ya devuelve los pines en el orden en que se ven;
- **`Ctrl+G`, colapsar la selección a función**: los cables que cruzan el borde se vuelven
  `input`/`output`. Acá la Fase 0 se paga sola, porque la selección ya es un estado.

*Terminado* = guardar una selección como función, instanciarla dos veces, y que el Compile del canvas
dé verde con los nodos `f1__…` en el reporte.

**2. Fase 7 del Graph — bypass (`D`) y comentarios (`C`).** El bypass es cerebro y por lo tanto
verificable; el comentario es Slate.

**3. Los 31 mutantes de código vivos de `oracle`**, de a uno.

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
