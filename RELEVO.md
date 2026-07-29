---
turno: 2026-07-29 · claude-code → codex
saliente: claude-code
entrante: codex
desde: 2026-07-29
verde_editor: 19d2593
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
| Cerebro | `cd Content/Python/tests && PYTHONPATH=$PWD/.. python -m unittest discover -s . -p "test_*.py" -q` | **477 OK**, 0.3 s |
| Vault | `python tools/vault.py` | **47 docs** en 5 carpetas, en regla |
| Motor | `tools/experiments/verifica_ejemplos.py` headless | **8/8 tutoriales · TODO VERDE** |
| Editor | arranque + carga del módulo | los 3 spawners registran, **sin warnings de tab** |

La verificación con motor es del commit `15c4cae`; desde ahí no se tocó `Source/` ni
`Content/Python/`, así que sigue hablando del código que hay. `relevo.py` lo comprueba solo.

## Frontera de verificación

Lo de abajo **está escrito y compila, pero nadie lo ejerció con las manos**. No conviene construir
encima sin probarlo antes.

| Cosa | Quién puede verificarla | Estado |
|---|---|---|
| Marquee, `Shift`/`Ctrl`+clic, arrastre en grupo | Brian (Slate) | ⏳ sin probar |
| `Ctrl+Z` / `Ctrl+Shift+Z` (50 pasos) | Brian | ⏳ sin probar |
| `Ctrl+C`/`X`/`V`/`D` contra el portapapeles del sistema | Brian | ⏳ sin probar |
| `F` / `Inicio` (encuadre) | Brian | ⏳ sin probar |
| Acoplar un panel, sidebar, y que vuelva al reabrir el editor | Brian | ⏳ sin probar |
| Alinear/distribuir (8 acciones del menú Edit) | ✅ cerebro con tests; el menú, Brian | parcial |

Son **cuatro tandas seguidas de C++ sin que nadie abriera el editor**. Es la deuda más cara del
proyecto ahora mismo.

## Para las manos de Brian

Quince minutos, en este orden — si algo falla acá, arrastra a todo lo demás:

1. Abrir `Window ▸ Tools ▸ Jam — Graph`, **arrastrarlo a un borde** hasta que se acople. Cerrar el
   editor, abrirlo: ¿volvió donde estaba?
2. En el Graph: marquee sobre varios nodos, arrastrarlos juntos, `Ctrl+Z`.
3. `Ctrl+C` en unos nodos, `Ctrl+V`. Pegar en un editor de texto: tiene que salir JSON legible.
4. Seleccionar 3 nodos desparejos → `Edit ▸ Acomodar ▸ Alinear a la izquierda`.
5. `F` con selección, `Inicio` sin selección.
6. Cerrar el tab del Graph con un diagrama puesto y volver a abrirlo: **el diagrama tiene que estar**.

## Lo próximo

**0. Lo que Brian haya encontrado** en la lista de arriba. Bloqueante: es código de este turno.

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
