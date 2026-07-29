---
title: "Guía: el relevo entre Claude Code y Codex"
tipo: GUIA
version: "1.0"
date: 2026-07-29
updated: 2026-07-29
status: vigente
area: Proceso
tags:
  - proceso
  - relevo
  - agentes
  - verificacion
aliases:
  - Relevo de turno
  - Trabajar por turnos con dos agentes
  - Protocolo de handoff
---

# Guía: el relevo entre Claude Code y Codex

Jam lo trabajan **dos agentes por turnos de 3-4 días**. No es una preferencia de diseño: es que los
límites semanales de cada uno obligan a alternar. Trabajan a la par sobre el mismo repo, nunca al
mismo tiempo.

El problema no es repartir tareas — para eso ya está el roadmap. El problema es que **ninguno de los
dos recuerda el turno del otro**. Cada uno arranca en frío, sobre un repo que cambió tres días sin
él.

## Las cuatro cosas que se pierden en un relevo

Ordenadas por lo que cuestan:

**1. El conocimiento tácito.** Que `-nullrhi` tira SIGFPE en 5.7.x. Que escribir la pila de Material
Layers sin los arrays *editor-only* paralelos voltea el editor. Cada una de esas costó horas de
descubrir y **cabe en una línea**. Si vive en la memoria de un agente, el otro la vuelve a pagar
entera.

**2. Construir sobre lo no verificado.** Es el más caro y el menos visible. Al cerrar este primer
turno había **cuatro tandas seguidas de C++ que nadie había ejercido con las manos**. Si eso se
suelta como «hecho», el que entra construye tres días encima, y si el marquee estaba roto, se cae
todo junto.

**3. El estado sucio.** Trabajo sin commitear, binarios a medio compilar, un `.jamgraph` en el
medio. El que entra clona; no adivina.

**4. La ambigüedad del «qué sigue».** «Hacer el visor 2D» no es una tarea, es un título.

## La respuesta: el protocolo es un comando

Un protocolo escrito en prosa se degrada en dos turnos, exactamente igual que un test que no
discrimina. Así que el relevo se verifica solo:

```bash
python tools/relevo.py            # LLEGADA — ¿está verde lo que recibo?
python tools/relevo.py --cerrar   # SALIDA — el ritual de soltar el testigo
```

`--cerrar` **se niega a bendecir un relevo rojo**: comprueba el testigo, los tests, el vault, que el
árbol esté limpio y empujado, y —la que importa— que la **verificación con motor siga vigente**.
Recién entonces marca el turno con un tag.

### El chequeo que justifica todo el aparato

`RELEVO.md` declara en qué commit corrió la verificación con motor. El verificador comprueba que ese
commit exista, sea antecesor de `HEAD`, y que **desde ahí no se haya tocado `Source/` ni
`Content/Python/`**.

Un «corrió verde» es una foto con fecha. Si después se tocó el C++ o el cerebro, la foto es de otro
código y afirmarla es mentir. Mira **qué** cambió y no **cuánto**, así que commits de documentación
no la invalidan — que es lo que la hace usable en vez de molesta.

Es la aplicación directa de la regla de la casa: *verificar por el camino real, no por el atajo*.

## Dónde vive cada cosa

| Archivo | Qué es | Vigencia |
|---|---|---|
| `AGENTS.md` (raíz) | Recetas, reglas y trampas medidas. Codex lo lee solo al arrancar. | Permanente |
| `CLAUDE.md` (raíz) | Tres líneas que apuntan a `AGENTS.md`, para que los dos lean lo mismo | Permanente |
| `RELEVO.md` (raíz) | **El testigo.** El turno actual. | Se reescribe cada turno |
| `Vault-kb/` | La doctrina y los informes de lo que pasó | Histórico |
| Tags `relevo/AAAA-MM-DD-agente` | Dónde terminó cada turno | Histórico |

Dos decisiones que parecen menores y no lo son:

**El testigo está en la raíz, no en el vault, y no lleva fecha en el nombre.** Es estado operativo:
tiene que haber **exactamente uno** y tiene que estar siempre vigente. Un `RELEVO.md` fechado se
convierte en cuatro archivos y en la duda de cuál rige. El vault guarda historia; la raíz, el ahora.

**Lo durable va al repo, no a la memoria del agente.** Claude Code tiene memoria persistente entre
sesiones; Codex no ve nada de eso. Cualquier hecho que valga para mañana se escribe en `AGENTS.md` o
en el vault, y la memoria queda como puntero. Si no, el repo y lo que «sabe» un agente se separan en
silencio, que es la falla número 1 de arriba.

## Los tags: ver el turno ajeno en vez de leerlo

Cada cierre deja `relevo/2026-07-29-claude-code`. El que entra hace:

```bash
git log relevo/2026-07-29-claude-code..HEAD --oneline
git diff relevo/2026-07-29-claude-code..HEAD -- Source/
```

y **ve** el turno ajeno en vez de creerle a un resumen. Un diff no se puede exagerar; una prosa sí.

## Qué lleva el testigo

Seis secciones fijas — el verificador exige que estén. Corto a propósito: un testigo que no se lee
de una sentada no se lee.

1. **Verde al soltar** — los comandos con su resultado. El que entra los corre *antes* de tocar
   nada. Si llega rojo, eso es el turno, no el roadmap.
2. **Frontera de verificación** — qué quedó **sin** probar y quién puede probarlo. Es la sección que
   evita la falla número 2.
3. **Para las manos de Brian** — máximo seis gestos concretos, quince minutos. Sólo Brian puede
   verificar Slate; hay que hacerle barato ese trabajo o no ocurre.
4. **Lo próximo** — dos o tres tareas, ordenadas, cada una con **definición de terminado que es una
   comprobación**, no una opinión.
5. **No toques esto** — las trampas que cuestan un día. Las permanentes están en `AGENTS.md`; acá
   van las del código que se acaba de tocar.
6. **Lo que aprendí este turno** — los hallazgos nuevos, que ya deben estar en `AGENTS.md` o el
   vault. Acá queda el porqué.

## Cómo elegir qué dejarle al otro

Dos criterios que salieron de este primer relevo:

**Preferí dejar trabajo cuyo «terminado» lo decide una máquina.** Un agente solo, sin nadie que abra
el editor, rinde mucho más en el cerebro puro (`Content/Python/jam/`, tests en 0.3 s) que en gestos
de Slate, que escribe a ciegas y nadie sabe si andan. Por eso al primer relevo le tocan las
**funciones con firma** —que son casi todo cerebro— y **no** el visor 2D ni el gizmo de alineación,
que se guardan para un turno con Brian delante.

**El último día del turno es para cerrar, no para abrir frente nuevo.** No se empieza algo que no
se pueda terminar *y verificar* antes de soltar. Un turno que termina a mitad de una refactorización
de C++ le regala al otro el peor arranque posible.

## El ciclo completo

**Al entrar:** `python tools/relevo.py` → leer `RELEVO.md` entero → `git log <tag anterior>..HEAD` →
arreglar lo que Brian haya encontrado → recién ahí, el roadmap.

**Al salir:** cerrar lo abierto → correr la verificación con motor y anotar el commit en
`verde_editor` → reescribir `RELEVO.md` → volcar los hallazgos a `AGENTS.md` o al vault →
`python tools/relevo.py --cerrar` → `git push origin <tag>`.

## Relacionado

- [[2026-07-29-GUIA-Convencion-Documentacion-Vault-v1.0|Convención de documentación del vault]] — la
  otra regla que se verifica sola, con `tools/vault.py`
- [[2026-07-29-ROADMAP-Accesibilidad-Graph-v1.0|Roadmap de accesibilidad del Graph]] — de donde sale
  «lo próximo» del primer testigo
- [[2026-07-29-INFORME-Docking-Paneles-Nomad-Tabs-v1.0|Docking: los paneles son nomad tabs]] — el
  último trabajo del turno que cierra
