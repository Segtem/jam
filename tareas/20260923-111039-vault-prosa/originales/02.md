---
title: "Oracle: un metalenguaje de medidas para construir herramientas con un LLM"
tipo: INFORME
version: "1.0"
date: 2026-07-30
updated: 2026-07-30
status: implementado
area: 00-Proceso
tags:
  - oracle
  - proceso
  - goodhart
  - verificacion
  - metalenguaje
aliases:
  - Oracle
  - El metalenguaje de medidas
  - Por qué debería creerte
---

# Oracle: un metalenguaje de medidas para construir herramientas con un LLM

`Segtem/oracle`, vendorizado en Jam como `vendor/oracle/`. Jam es su primer **proyecto**: sus medidas,
sus sensores y sus fixtures viven en `medidas/`.

## La esencia

Debajo de todos los mecanismos hay una sola frase:

> **Ninguna afirmación vale por sí sola. Tampoco la que dice «esto está verificado».**

Cada pieza es una respuesta a *«¿por qué debería creerte?»* sobre una clase distinta de afirmación:

| La afirmación | Qué se le exige |
|---|---|
| «está bien» | contra qué medida, con qué umbral, y **qué no miró** |
| «el test lo cubre» | ¿qué mutante lo mata? |
| «corrió verde» | en qué commit, y ¿cambió el código desde entonces? |
| «esta medida sirve» | ¿qué caso la pone roja? ¿y qué caso la pone verde? |
| «el marco funciona» | ¿qué medida lo dice? |

**Su naturaleza es negarse.** En 1593 líneas de núcleo hay siete tipos de error declarados y 39
negativas. No calcula calidad: declina dejar pasar lo que no se puede sostener. Y lo que produce no es
confianza sino **confianza acotada** — el veredicto no es el producto, el punto ciego lo es.

## Por qué existe

El problema tiene nombre: **Goodhart**. Cuando el que construye la herramienta es el mismo que escribe
su verificador, el verificador tiende a preguntar lo que la herramienta ya contesta bien. Con un LLM el
efecto es estructural por dos razones: escribe la herramienta y su test **con la misma mano**, y **no
tiene memoria entre sesiones** — así que una regla escrita como consejo se lee y se olvida. Tiene que
**negarse**.

La medición que lo justifica, tomada de una sola sesión de trabajo sobre Jam: **de 16 defectos reales,
14 fueron falsos verdes**, y **ninguno lo atrapó un verificador propio en el momento** (8 la mutación,
5 Brian, 4 la casualidad, 1 una herramienta ajena) — con 489 tests en verde y dos verificadores
corriendo.

## Qué es, mecánicamente

Una **medida** es un dato, no código:

```json
["ninguno", "proceso.test_con_mutante_que_lo_mata",
  "mutante", "m",
  ["==", ["campo", "m", "murio"], false],
  "un mutante que sobrevive es un test que no discrimina",
  "cuenta mutantes DECLARADOS. NO ve los que nadie escribió"]
```

Cinco piezas, y dos son obligatorias por una razón: **`porque`** (un número que nadie puede discutir es
una métrica esperando a volverse objetivo) y **`alcance`** (un verde que no dice lo que no miró se lee
como «está bien»).

Tres influencias, y las tres hacen falta: **SQL** da el álgebra con clausura; **GPSS**, la segunda
fuente de evidencia (correr el sistema y medir lo que emerge); **LISP**, que la medida *sea un dato* —
sin eso el lenguaje tiene dueño, y el dueño sería el LLM.

## Cómo se relaciona con Jam

**Jam no depende de oracle en tiempo de ejecución.** El patrón es el mismo que ya usaba el oráculo del
plugin: el **sensor** vive con el productor y produce hechos; el **juez** vive en oracle y no mira el
mundo.

```
tools/emitir_hechos_vault.py     el sensor del vault      → medidas/diferencial/vault.json
tools/emitir_hechos_relevo.py    el sensor del relevo     → medidas/diferencial/relevo.json
tools/emitir_diferencial.py      el sensor de geometría   → medidas/diferencial/geometria.json

python vendor/oracle/tools/diferencial.py --proyecto medidas
```

`tools/vault.py` corre en **modo sombra**: calcula el veredicto por los dos caminos —el escrito a mano
y las diez medidas— y **sale con código 2 si difieren**. El informe que imprime es el del oráculo,
porque enumera lo que no mira. Los verificadores escritos a mano **siguen siendo la referencia** hasta
que el diferencial lleve tiempo en verde.

## Las decisiones que costaron algo

- **La ausencia sin nulos.** «Módulos que nadie usa de verdad» parecía pedir un `LEFT JOIN`, que
  habría traído el concepto de nulo. Se resolvió agrupando sobre el producto **sin filtrar** y sumando
  un predicado: los booleanos suman 0 y 1, así que un grupo donde nada casó da cero y sigue existiendo.
- **La recursión queda fuera del álgebra.** «Alcanzable desde» es un **hecho** que produce el sensor,
  no una consulta. Un operador `cierre` habría sido recursión con un solo usuario.
- **El orden es un campo del hecho.** No puede ser una propiedad de la relación: una relación es un
  conjunto y los conjuntos no tienen orden.
- **La igualdad exacta entre flotantes está prohibida.** `0.1 + 0.2` no es `0.3`. Sobre lo que se mide
  hace falta una tolerancia; sobre lo que se cuenta o se nombra, la igualdad sigue valiendo.

De las cuatro preguntas abiertas de la especificación, **tres se cerraron sin agregar un operador**. Es
la única prueba de que el juego chico alcanzaba.

## El costo, dicho

**1593 líneas de lenguaje** contra las medidas escritas en él: diez a uno con el catálogo base, cinco a
uno contando Jam. Ésa es la apuesta y ésa es la métrica — que el segundo número crezca y el primero no.
Es lo único que no se puede sastrear escribiendo más medidas, porque escribir más medidas es
exactamente lo que la mejora.

## Para estudiarlo

`python vendor/oracle/tools/estudio.py --proyecto medidas` vuelca todo a diez documentos de Markdown
plano y autocontenido, aptos para subir a NotebookLM. El más revelador es el diario de commits: leído
en orden muestra el proceso y no el resultado, y cerca de la mitad de los títulos son la corrección de
algo que el propio autor había afirmado.

## Relacionado

- [[2026-07-29-GUIA-Relevo-Claude-Codex-v1.0|El relevo entre Claude Code y Codex]] — `relevo.py` es
  uno de los tres dominios re-expresados como medidas
- [[2026-07-29-GUIA-Convencion-Documentacion-Vault-v1.0|Convención de documentación del vault]] —
  `vault.py` es otro, y corre en modo sombra
