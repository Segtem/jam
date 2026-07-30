---
turno: 2026-07-29 · claude-code → codex
saliente: claude-code
entrante: codex
desde: 2026-07-29
verde_editor: 80373ea
verde_editor_fecha: 2026-07-29
---

# Testigo

Entra **codex**. Corré `python tools/relevo.py` antes de leer esto; si sale rojo, eso es el turno.

El turno que cierra hizo el **roadmap de accesibilidad del Graph, fases 0 a 3**: la selección pasó a
ser un estado, y encima de eso vinieron alinear/distribuir, el historial, el portapapeles y el
docking de los tres paneles.

## Verde al soltar

| Qué | Comando | Resultado |
|---|---|---|
| Cerebro | `cd Content/Python/tests && PYTHONPATH=$PWD/.. python -m unittest discover -s . -p "test_*.py" -q` | **489 OK**, 0.3 s |
| Vault | `python tools/vault.py` | **47 docs** en 5 carpetas, en regla |
| Motor | `tools/experiments/verifica_ejemplos.py` headless | **8/8 tutoriales · TODO VERDE** |
| Editor | arranque + carga del módulo | los 3 spawners registran, **sin warnings de tab** |
| Oráculo (repo aparte, `~/Dev/oracle`) | `corpus.py` · `aceptacion.py` · `diferencial.py` · `mutar.py` · `unittest discover -s tests -t .` | **19 casos · aceptación ✓ · diferencial 1200/1200 · 44/44 mutantes · 53 tests** |

La verificación con motor es del commit `80373ea`; desde ahí no se tocó `Source/`, `Content/Python/`
ni `oraculo/`, así que sigue hablando del código que hay. `relevo.py` lo comprueba solo.

## Frontera de verificación — CERRADA el 2026-07-29

**Brian probó el editor y confirmó que todo funciona.** Con eso se cierra la deuda más cara que tenía
el proyecto: cinco tandas seguidas de C++ que nadie había ejercido con las manos.

| Cosa | Estado |
|---|---|
| Marquee, `Shift`/`Ctrl`+clic, arrastre en grupo | ✅ Brian, en el editor |
| `Ctrl+Z` / `Ctrl+Shift+Z` (50 pasos) | ✅ |
| `Ctrl+C`/`X`/`V`/`D` contra el portapapeles del sistema | ✅ |
| `F` / `Inicio` (encuadre) | ✅ |
| Acoplar un panel, sidebar, y que vuelva al reabrir el editor | ✅ |
| Alinear/distribuir (8 acciones del menú Edit) | ✅ cerebro con tests **y** el menú a mano |

**Precisión sobre el alcance de esta confirmación**, para que el registro no diga más de lo que
sabe: es un «todo funciona bien» **global**, no gesto por gesto. Alcanza para construir encima con
confianza; si algo aparece más adelante, no queda contradiciendo a este documento.

Lo que sigue valiendo: **lo que se escriba de Slate a partir de acá vuelve a nacer sin verificar** y
hay que volver a listarlo abajo. La frontera no se cierra de una vez, se cierra por turno.

## Para las manos de Brian

**Nada pendiente.** La lista de este turno eran seis gestos —acoplar el Graph y reabrir el editor,
marquee + arrastre en grupo + `Ctrl+Z`, `Ctrl+C`/`V`, alinear, `F`/`Inicio`, y cerrar/reabrir el tab
con un diagrama puesto— y Brian los probó el 2026-07-29 sin encontrar nada.

*(Esta sección es obligatoria y no se borra cuando está vacía: si se pudiera omitir, un turno dejaría
de pedir manos sin que nadie lo note. Vacía dice «no hace falta»; ausente no dice nada.)*

Al cerrar el próximo turno va acá lo nuevo de Slate: **máximo seis gestos, quince minutos**. Es el
mecanismo que funcionó — cuatro tandas pidiendo «probá cuando puedas» no habían movido nada.

## Lo próximo

**0. Nada bloqueante.** Brian ya probó el editor y no encontró nada. Se puede construir encima de las
fases 0 a 3 con confianza.

**1. Fase 5 — la capa de Slate de las funciones.** El **cerebro ya está hecho y cableado**
(`jam/funcion.py`, 18 tests, expansión inline verificada contra el grafo plano equivalente; ver
[el informe](Vault-kb/01-Graph/2026-07-29-INFORME-Funciones-Graph-Firma-v1.0.md)). Falta lo de
arriba, que es gesto y por lo tanto queda en la frontera:

- **instanciar desde el ribbon**: una función guardada aparece como un nodo, y `funcion.firma()` ya
  devuelve los pines en el orden en que se ven. Sólo hay que dibujarlos;
- **`Ctrl+G`, colapsar la selección a función**: los cables que cruzan el borde de la selección se
  vuelven `input`/`output`. Acá es donde la Fase 0 se paga sola — la selección ya es un estado.

*Terminado* = guardar una selección como función, instanciarla dos veces, y que el Compile del
canvas dé verde con los nodos `f1__…` en el reporte.

**2. Fase 7 — bypass (`D`) y comentarios (`C`).** El bypass es cerebro (compilar salteando el nodo,
pasando la entrada a la salida) y por lo tanto verificable; el comentario es Slate.

**3. `oracle` — repo nuevo, `Segtem/oracle` en `~/Dev/oracle`.** Decisión de Brian de esta sesión:
el oráculo se abstrae en un **modo de trabajar** —un metalenguaje de medidas— y su primer dominio es
**el proceso de construir con un LLM**, no la geometría. Va el paso 0 de 5: están el corpus (11 casos
donde la medición dijo bien y no estaba bien) y `ESPECIFICACION.md` (el álgebra: medida como dato,
seis operadores, clausura). **Todavía no hay evaluador, a propósito** — el corpus es el criterio de
aceptación de lo que venga.

**Pasos 1 y 2 también están hechos** (`988bcfe`): el evaluador (`nucleo/`), 8 medidas como archivos
de datos en `catalogos/`, y `tools/aceptacion.py` — donde **el corpus juzga al oráculo**: los 9 casos
con medida se ponen en rojo, los 2 con hueco declarado quedan verdes a propósito. Corre también el
nivel L2 (el catálogo servido como relación y medido por una medida, sin mecanismo nuevo).

**El paso 3 está hecho a medias, y a propósito** (`f6360d2`): el sensor muta las **medidas** —que son
datos, así que el caché frío es verdadero por construcción— y sus hechos los juzga una medida del
catálogo. 28 mutantes, 28 muertos. **Falta la otra mitad: mutar CÓDIGO Python**, que es la que atrapó
3 de los 11 casos del corpus. Ahí sí hace falta el arnés con caché frío — `max` y `min` ocupan lo
mismo y CPython invalida el `.pyc` por (mtime, tamaño), así que sin limpiar `__pycache__` entre
mutantes el resultado es al azar (caso `006`).

**El paso 4 está hecho** (`8a4d24b`): dos dominios —proceso y geometría— con **los mismos operadores
y sin adaptador**. `unir` entró al llegar su disparador; van 4 operadores de 6.

La verificación vive a caballo de los dos repos y conviene no romperla: **`jam/tools/emitir_diferencial.py`**
genera 300 mundos con los oráculos escritos a mano de Jam (implementación independiente) y escribe
`~/Dev/oracle/diferencial/geometria.json`. `oracle/tools/diferencial.py` los re-juzga: **1200
veredictos, cero desacuerdos**. Si se toca `jam/oracle_placement` o `jam/oracle_snap`, hay que
regenerar el fixture y el diferencial tiene que seguir en cero.

**Siguiente paso — la otra mitad del paso 3: mutar CÓDIGO Python.** Lo que hay muta *medidas*, que son
datos. Mutar el código es lo que atrapó 3 de los casos del corpus, y ahí sí hace falta el arnés con
caché frío. Después, paso 5: `relevo.py` y `vault.py` dejan de ser verificadores a mano y se
re-expresan como medidas.

Dos reglas del repo que hay que respetar y son fáciles de romper sin querer:

- **sólo 3 de los 6 operadores están implementados** (`de`, `donde`, `resumen`), a propósito: son los
  únicos con usuario. Los otros levantan un error con su disparador. No implementarlos «de paso».
- **el repo no tiene dependencias, ni de desarrollo.** Tests en `unittest` puro. El oráculo viejo de
  Jam tenía 13 archivos escritos para pytest sin pytest instalado: 0 tests corriendo por 8 días.

Lo que NO hay que hacer ahí: migrar `oraculo/` viejo (queda en Jam), transporte por red, parser de
sintaxis propia, y macros.

**Para un turno con Brian delante, no para éste:** el visor 2D de texturas (el motor está entero en
`jam/preview2d.py` y **no lo consume nadie** en `Source/`; falta el `FSlateDynamicImageBrush`) y el
gizmo flotante de alineación de `Reference/align.png`. Los dos son gesto puro: un agente los escribe
a ciegas y nadie sabe si andan.

## No toques esto

- **Los ids de los nomad tabs** (`JamDashBar` / `JamGraph` / `JamContent`): son la clave persistente
  del layout. Renombrarlos le borra a Brian el acomodo de los paneles.
- **`Marcar()` va DESPUÉS de mutar, no antes.** `BuildJson()` lee los widgets vivos, así que una
  foto tomada «antes» ya contiene lo que acabás de tipear y un `Ctrl+Z` deshace dos cosas.
- **Los ids de nodo no se renumeran al cargar.** Se rompió una vez: el oráculo y el inspector
  referencian nodos por id.
- El resto de las trampas permanentes, en `AGENTS.md`.

## Lo que aprendí este turno

Todo esto ya está en `AGENTS.md` o en el Vault; acá queda el resumen de por qué se agregó.

- Una `SWindow` **no se puede acoplar**: el docking de Unreal sólo conoce tabs. No había que
  arreglar la ventana, había que dejar de usar ventanas.
- **Un tab acoplado no tiene ventana propia** — el timer de 20 Hz del punto de mira tuvo que mudarse
  al widget de contenido. Habría sido un bug silencioso: los campos x/y/z dejaban de actualizarse
  justo al acoplar.
- Llamar al destructor de un `TGuardValue` de pila es doble destrucción. **Lo hice dos veces** en la
  misma sesión; la segunda la atajó el compilador de casualidad. Bloque con *scope*, siempre.
- **Un mutante sobrevivió** al probar las funciones: ordenar la firma por id en vez de por posición
  pasaba en verde, porque en el test el id `a` caía justo en el pin de arriba y los dos órdenes
  coincidían. El test no discriminaba. Si no se rompe el código a propósito, esto no se ve.
- **El verificador del relevo tenía el mismo agujero que persigue**: miraba sólo lo commiteado desde
  la foto de `verde_editor`, así que daba VERDE con el código vivo modificado en el árbol de
  trabajo. Corregido: ahora mira también lo que está sin commitear.
- Un verificador que reporta roto lo que está bien **es peor que no verificar**: enseña a ignorarlo.
  Salió de dos falsos positivos del verificador del vault (la barra escapada `\|` de las tablas y
  los `[[ejemplos]]` dentro de comillas invertidas). Se arregló el verificador, no los documentos.
- **El arnés de mutación mentía por bytecode viejo.** `max` y `min` ocupan lo mismo, y CPython
  invalida el `.pyc` por (mtime, tamaño): mutar y restaurar dentro del mismo segundo dejaba a Python
  corriendo el bytecode mutado. Hay que limpiar `__pycache__` entre mutantes o los resultados son al
  azar. Es el caso `006` del corpus.
- **De 11 defectos medidos hoy, ninguno lo atrapó un verificador propio por diseño**: 4 los vio
  Brian, 3 la mutación, 3 la casualidad, 1 un parser ajeno. Con 489 tests en verde y dos
  verificadores corriendo. Ése es el número que motivó el repo `oracle`.
- **La definición de «código vivo» del relevo estaba incompleta**: `oraculo/` no estaba en `VIVO`, y
  el plugin lo importa (`jam.nivel`, `jam.oracle_espacio`). Una edición ahí pasaba sin invalidar la
  verificación con motor. Corregido — mismo agujero que el caso `007`, en otra ropa.
