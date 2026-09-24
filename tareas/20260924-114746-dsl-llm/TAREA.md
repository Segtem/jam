# Un LLM no puede hacer por el DSL todo lo que Jam hace, y lo que escribe no siempre se puede seguir y corregir como nodos

- ESTADO: ABIERTA
- PRIORIDAD: 96
- ETIQUETAS: dsl, graph, llm, commander


## Por qué

2026-09-24, Brian: commander (`~/Dev/commander`, tarea `vision`) usa Jam como superficie de creación:
**un LLM crea por el DSL, y un humano puede seguir, observar y corregir esa creación en la interfaz de
nodos, porque todo queda expuesto.** Para eso Jam tiene que estar completo y ser compatible con el DSL
en los dos sentidos:

- **Cobertura:** todo lo que se puede hacer en Jam desde la interfaz (Slate, gestos, jamtool) se
  puede hacer también por el DSL. Un verbo que sólo existe detrás de un gesto es una pared para el LLM.
- **Ida y vuelta:** lo que el LLM escribe en el DSL aparece como grafo de nodos legible (con nombres y
  pines, no ids), y lo que el humano cambia en los nodos se puede leer de vuelta como DSL, sin perder
  nada. El LLM y el humano trabajan sobre el mismo grafo.
- **Errores legibles para un modelo:** cuando el DSL rechaza algo, el mensaje dice qué y cómo seguir,
  como el de Oracle. Nada se descarta en silencio (ver AGENTS.md, `dsl.coaccionar` descartaba un
  parámetro sin avisar).

## Qué hacer primero

Una **auditoría**, sin cambiar código: la lista de verbos y operaciones de Jam y, para cada uno, si
se alcanza por el DSL, si hace la ida y vuelta DSL ↔ nodos, y qué lo impide, con la cita del código.
Incluir las tareas abiertas que ya son parte de esto (`etiquetas-pines`, `labels-tools`,
`jamtool-ui`, `colocar-cli`, `fuente-roja`). Ordenar lo que falta por cuánto le cierra el paso a un LLM.

## Avance

2026-09-24: Auditoría completada y documentada en [AUDITORIA.md](../../tareas/20260924-114746-dsl-llm/AUDITORIA.md) (sin cambios de código, sin ejecuciones de shell):
- Relevamiento de 186 tools registradas: ~80 corren por consola y 86 quedan excluidas del DSL (`registro_core.cable_que_falta`).
- Análisis de la falta de ida y vuelta: `JamGraph` solo serializa a JSON crudo; no hay compilador DSL → Grafo ni descompilador Grafo → DSL.
- Diagnóstico de coerción ciega y descarte silencioso en `dsl.coaccionar` (`_desc` ignorado en `graph.py:825`).
- Diagnóstico del bug `fuente-roja` en `graph.ejecutar_detalle` (excepciones secundarias en cascada por `entrada=None`).
- Relevamiento del estado de las 5 tareas abiertas vinculadas (`etiquetas-pines`, `labels-tools`, `jamtool-ui`, `colocar-cli`, `fuente-roja`).
- Jerarquía priorizada de 7 niveles de bloqueos para el LLM.

## Próximo paso

Diseñar la especificación técnica de la sintaxis DSL para grafos y composición (tuberías/pipes, asignación de identificadores semánticos y conexión de pines) que resuelva la P1 de la auditoría y defina el contrato de ida y vuelta formal DSL ↔ JamGraph.

