---
title: "Guía: convención de documentación del Vault-kb de Jam"
tipo: GUIA
version: "1.0"
date: 2026-07-29
updated: 2026-07-29
status: vigente
area: 00-Proceso
tags:
  - jam
  - vault
  - obsidian
  - convencion
  - nomenclatura
aliases:
  - Nomenclatura del vault
  - Cómo nombrar un doc de Jam
---

# Guía: convención de documentación del Vault-kb de Jam

Aplicada el 2026-07-29 a los 41 documentos que había. Es la misma convención que ya usa el vault de
JamProtocol, para que los dos se lean igual.

## El nombre de archivo

```text
AAAA-MM-DD-TIPO-Nombre-vX.X.md
```

Ejemplo real: `2026-07-27-INFORME-TreeGen-Distribute-Frames-v1.0.md`

| Parte | Regla |
|---|---|
| `AAAA-MM-DD` | fecha de **última actualización** (el campo `updated:`), no la de creación |
| `TIPO` | en MAYÚSCULAS, de la lista de abajo |
| `Nombre` | ASCII, palabras unidas con guiones, **sin acentos, sin ñ, sin espacios, sin `—`** |
| `vX.X` | versión; `v1.0` al crear. Un cambio de fondo sube a `v2.0`; una corrección, a `v1.1` |

Por qué ASCII: el nombre de archivo es también el destino de los wikilinks y viaja por git, por la
terminal y por scripts. Los acentos ahí no aportan y rompen cosas — la legibilidad se resuelve con el
**alias** del enlace, no con el nombre del archivo.

## Los TIPOs

| TIPO | Para qué | Cuántos hoy |
|---|---|---|
| `INFORME` | lo que se midió o se implementó, ya cerrado | 27 |
| `PLAN` | trabajo especificado, pendiente o en curso | 9 |
| `ROADMAP` | dirección de producto a varias fases | 2 |
| `CONCEPTO` | un principio de diseño, no una implementación | 1 |
| `GUIA` | cómo se usa algo (tutoriales, convenciones) | 2 |
| `ESTADO` | foto de situación en una fecha | 0 |
| `ADR` | decisión de arquitectura; conserva su número: `ADR-NNN-...` | 0 |

La diferencia que más se confunde: **`PLAN` describe lo que falta, `INFORME` describe lo que pasó.**
Cuando un `PLAN` se termina, se lo reescribe como `INFORME` y sube de versión.

## El frontmatter

```yaml
---
title: "TreeGen: Distribute Frames F"
tipo: INFORME
version: "1.0"
date: 2026-07-27          # creación
updated: 2026-07-27       # última actualización — manda sobre el nombre del archivo
status: implementado
area: 02-TreeGen           # obligatorio, y tiene que ser la carpeta donde vive
tags: [jam, treegen, frames]
aliases: [Distribute Frames]
---
```

`title` es lo que se lee: **ahí sí** van acentos, `ñ` y puntuación. `status` es texto libre corto
(`pendiente`, `en-progreso`, `implementado`, `historico-superado`, …).

## Los wikilinks van con alias

```markdown
[[2026-07-27-INFORME-TreeGen-Distribute-Frames-v1.0|Distribute Frames]]
```

El destino es el nombre del archivo (que es feo y estable); el alias es lo que se lee. Dentro de una
tabla de Markdown hay que escapar la barra: `\|`.

## Cómo se verifica

El renombrado del 2026-07-29 no se hizo a mano: un script mueve con `git mv`, reescribe el
frontmatter, reescribe los ~250 wikilinks, y al final **recorre cada `[[destino]]` y comprueba que
exista el archivo**. Si algo no resuelve, aborta.

Esa última parte es el punto: un vault sin verificación de enlaces se pudre en silencio, igual que
un test que no discrimina. Conviene volver a correr esa comprobación cada vez que se renombre algo.

## Lo que queda afuera

- `README.md` — es el índice, se llama así y punto.
- `.obsidian/` — configuración del vault.
- La documentación **del código** (`docs/`, `README.md` del plugin, docstrings) no es del vault y no
  usa esta convención.

## Las carpetas son la taxonomía

```
Vault-kb/
  README.md                 índice generado — no se edita a mano
  00-Proceso/               cómo se trabaja y hacia dónde va Jam
  01-Graph/                 el editor de nodos y sus paneles
  02-TreeGen/               el árbol procedural
  03-Mesh-y-materiales/
  04-Ejecucion-y-pruebas/
```

**Un documento vive en una carpeta y sólo una, y su `area:` dice cuál.** Eso lo verifica
`tools/vault.py`: `area` distinto de la carpeta es un error, igual que un `.md` suelto en la raíz o
una carpeta que no está en la lista.

Esta guía decía, el mismo día que se escribió, que con 43 notas el vault plano alcanzaba y que las
carpetas podían esperar a las ~80. Se hicieron con 46 y estuvo bien, por una razón que yo no había
pesado: **el índice se agrupaba con una heurística de palabras clave sobre el nombre de archivo**
(«si dice Mesh va en Mesh»), y el campo `area:` estaba podrido — 16 documentos no lo tenían y el
resto usaba 14 valores incompatibles (`Jam`, `JamEditor/Graph`, `Jam/Graph/GeometryScript` para
notas de TreeGen). La carpeta convierte esa adivinanza en un dato, y el dato se verifica. El
volumen era el argumento equivocado.

**El nombre del archivo sigue siendo único en todo el vault**, no sólo dentro de su carpeta: un
wikilink apunta por nombre y no por ruta, así que dos homónimos en carpetas distintas dejarían el
enlace a cara o cruz. El verificador también comprueba eso.

Mover un documento de carpeta es `git mv` + corregir su `area:`. **Los wikilinks no se tocan**:
Obsidian los resuelve por nombre.

## Relacionado

- [[2026-07-29-ROADMAP-Accesibilidad-Graph-v1.0|Roadmap de accesibilidad del Graph]]
- [[2026-07-25-ROADMAP-Vision-Producto-Jam-v1.0|Visión y roadmap de producto]]
