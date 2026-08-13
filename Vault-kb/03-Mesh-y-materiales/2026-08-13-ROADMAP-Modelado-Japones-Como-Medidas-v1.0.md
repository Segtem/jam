---
title: "El modelado japonés como medidas, no como gestos"
tipo: ROADMAP
version: "1.0"
date: 2026-08-13
updated: 2026-08-13
status: propuesto
area: 03-Mesh-y-materiales
tags:
  - jam
  - malla
  - normales
  - silueta
  - oraculo
  - roadmap
---

# El modelado japonés como medidas, no como gestos

## De dónde sale y qué NO se leyó

Brian trajo el video **"I Studied Japan's 3D Modeling Philosophy for 30 Days"**, del canal **Noggi**
(subido el 2026-08-12), y preguntó si algo de eso se puede aplicar a Jam.

⚠️ **El video no se pudo ver**: YouTube no entrega el contenido a las herramientas de este entorno.
Lo único que se leyó es la ficha y la descripción, que nombra las fuentes. Todo lo que sigue está
razonado **desde esas fuentes**, que sí están documentadas públicamente:

- el **Polygonomicon** de Junya Motomura,
- los modelos de **Guilty Gear** de Arc System Works (las charlas de Xrd sobre normales de vértice),
- el modelado por silueta de **Martin Krol**.

**Si Noggi llegó en sus 30 días a una conclusión distinta, este documento no la tiene.** Queda
pendiente que Brian lo mire y corrija; él dijo que se va a informar más sobre el tema.

## La tesis del documento

La escuela japonesa de poly modeling se resume en algo que encaja sorprendentemente bien con Jam:
**el modelo no se esculpe y se retopologiza — se construye ya en su topología final, y el sombreado
se AUTORA en vez de derivarse de la geometría.**

De ahí sale el corte que propone este roadmap, y es la decisión de diseño entera:

> **Jam absorbe los CRITERIOS —qué hace buena a una topología— como MEDIDAS.
> Jam no absorbe los GESTOS —cómo mueve los vértices un modelador.**

Ese corte no es estilístico. Un apartado "modelado japonés" entendido como gestos se convierte en una
herramienta de modelar a mano, que es exactamente lo contrario de la tesis de Jam: **el mapa emerge
de la cadena, no lo escribe la mano.** Y entendido como medidas respeta el
anti-Goodhart de siempre: no se le enseña a `mesh_loft` a "ser japonés", se mide desde afuera y las
herramientas se bancan el juicio.

---

## 1 · Normales de vértice como canal autorado

**El más barato, el que tiene consumidor real, y el primero que haría.**

Es el corazón de la técnica de Guilty Gear Xrd: transferir las normales desde un **proxy primitivo**
—una esfera, un cilindro— para que la superficie se lea limpia sin importar cómo esté triangulada.
La geometría resuelve la silueta; las normales resuelven el sombreado. Son dos problemas separados y
la escuela japonesa los separa a propósito.

**Jam ya está parado justo ahí y no lo sabe:**

- `ribbon_core._normals` ya calcula normales a mano — es el único verbo que arma buffers propios.
- **`malla.cara_visible` ya juzga la cara que el motor dibuja contra la normal de sombreado de sus
  propios vértices.** Es la medida que encontró el winding invertido de `mesh_ribbon` con 790 tests
  en verde, así que hay evidencia de que este eje detecta defectos reales.

**Lo que falta:**

| pieza | forma | nota |
|---|---|---|
| `mesh_normals_from` | M + M → M | transferir normales desde un proxy. Cerebro puro, cero `unreal` |
| `malla.sombreado_continuo` | medida | sin discontinuidad de normal a través de una arista declarada suave |

**Consumidor inmediato**: las juntas del kit Victorian de BotOO (los 365 StaticMesh de KitBash3D +
VictorianAlley). Piezas modulares distintas que se tocan y muestran la costura porque
cada una calculó sus normales sin mirar a la vecina — es literalmente el problema que la técnica
resuelve.

⚠️ **Antes de escribir el verbo, medir el defecto.** La regla de esta casa es que una capacidad sin
consumidor no se construye: primero correr `malla.sombreado_continuo` sobre las juntas reales del kit
y ver si hay rojo. Si no lo hay, el verbo espera.

## 2 · La silueta como presupuesto medible

"Gastá polígonos donde se ve el contorno" suena a doctrina hasta que se **cuenta**. Para N
direcciones de cámara, se puede preguntar qué fracción de triángulos aparece **alguna vez** en la
silueta y cuál no aparece nunca.

- **Medida**: `malla.poligonos_en_la_silueta` — fracción de triángulos que contribuyen al contorno
  sobre un conjunto declarado de vistas.
- **Y sobre todo, un criterio de decimación**: hoy `mesh_simplify` tira triángulos por conteo,
  tolerancia o arista, **sin saber desde dónde se va a mirar la pieza**. Simplificar preservando la
  silueta desde el rango de vistas real es mejor herramienta, no sólo mejor número.

⚠️ **El rango de vistas es un DATO que hay que declarar**, y ahí está el riesgo: una medida que elige
las vistas sola inventa un criterio y lo presenta como veredicto. La declaración es del usuario.

## 3 · Modelar para una distancia declarada

El corolario del punto 2. La escuela japonesa modela a resolución final para una distancia de cámara
conocida — no hay subdivisión ni "se arregla después".

- **Medida**: `malla.densidad_en_pantalla` — triángulos por píxel a una distancia declarada.
- Hoy **Nanite Analyze** da el conteo crudo (416.179 triángulos en `CasaKit/casa_kit`) sin decir si
  sobra o falta **para el uso**. En un Hunt la misma pieza se ve a 3 m y a 80 m, y ése es justamente
  el juicio que hoy nadie hace.

---

## Lo que NO se trae, y por qué

**El resto de la filosofía es gesto manual**: colocar vértices a mano, dirigir los loops con el
criterio de una persona, decidir dónde cae cada arista. Eso no entra en Jam. No porque esté mal
—es excelente— sino porque Jam es un orquestador con oráculo, y esa capacidad pertenece a una
herramienta de modelado. Es el lema de siempre: **la creación se delega a la best-in-class y se
compite en el verificador.**

Brian mencionó la posibilidad de **una tool complementaria** para esa mitad. Este documento no la
diseña; sólo deja anotado que el corte entre las dos cae exactamente acá.

## El límite honesto: quads

Buena parte del vocabulario de edge flow —loops continuos, dirección de los quads, poles— es sobre
**cuadriláteros**, y Jam produce mallas **trianguladas** de Geometry Script. La continuidad de loops
**no es representable hoy**, así que las medidas de edge flow no se pueden escribir aunque se sepa
cuáles son.

Es el mismo tipo de caveat que ya está anotado para NURBS en
[[2026-08-12-ROADMAP-Escalera-Grasshopper-Basics-v1.0|la escalera de Grasshopper]]: el tutorial
aporta el vocabulario y el orden, no la representación.

## Prioridad

**Esto no destraba nada y no va antes que multi-salida.** El orden sugerido, si algún día entra:

1. Medir `malla.sombreado_continuo` sobre las juntas del Victorian — es una medida sobre assets que
   ya existen, no necesita verbos nuevos y responde si el punto 1 tiene consumidor.
2. Si hay rojo: `mesh_normals_from`.
3. Los puntos 2 y 3 comparten maquinaria (proyección a un conjunto de vistas) y convendría hacerlos
   juntos o ninguno.

Los tres son **cerebro puro** —geometría y proyección, cero `unreal`—, así que ninguno depende del
motor para escribirse ni para probarse. El adaptador sólo entrega la malla.
