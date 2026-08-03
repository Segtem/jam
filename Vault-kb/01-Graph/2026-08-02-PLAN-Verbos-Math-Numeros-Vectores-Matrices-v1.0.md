---
title: "Verbos Math: números, vectores y matrices"
tipo: PLAN
version: "1.0"
date: 2026-08-02
updated: 2026-08-02
status: en-progreso
area: 01-Graph
tags:
  - jam
  - graph
  - math
  - numeros
  - vectores
  - matrices
  - tipos
aliases:
  - Nodos matemáticos
  - Matemática del Graph
  - Operaciones numéricas
---

# Verbos Math: números, vectores y matrices

Jam tiene hoy `number`, que produce un número, y `math`, que evalúa una expresión escrita como texto.
Eso permite hacer cuentas, pero no permite descubrirlas ni leer el flujo de un vistazo: sumar dos
valores exige escribir una fórmula y conocer previamente los nombres de sus variables. El objetivo
es sumar nodos explícitos como **Sumar**, **Restar** y **Multiplicar**, sin quitar el nodo de expresión
para los casos avanzados.

El orden importa. Primero se cierra el contrato de valores escalares; después se incorporan vectores
y recién entonces matrices. Implementar los tres como un comodín sobrecargado produciría pines
ambiguos y errores difíciles de explicar.

## Estado actual y deuda que hay que retirar

- `jam.flow.OPS_META` publica `number`, `math` y `text`, pero sus evaluaciones no viven en `OPS`.
- `jam.flow` y `jam.graph` repiten `VALOR_KINDS`, tipos, defaults y resolución de esos tres casos.
- `jam.ribbon` sólo ofrece `Maths/Operar → math`.
- el resultado matemático sí puede viajar por un cable `N` a cualquier parámetro numérico;
  por lo tanto el sustrato necesario ya existe.
- `geometry.Vec3` sirve a geometría interna, pero no es todavía un tipo de valor público del Graph.
  No conviene reutilizarlo como contrato serializado sin definir primero dimensión y representación.

Antes de agregar verbos se extraerá un registro de valores compartido por Flow, Graph y el spec. Una
operación nueva debe declararse una vez con verbo, etiqueta, pines, tipos, defaults, función pura y
documentación; los dos evaluadores consumen ese dato y dejan de crecer mediante listas especiales.

## Vocabulario de tipos

Los códigos siguen siendo protocolo interno y la UI siempre muestra el nombre completo:

| Código | Nombre visible | Representación pura inicial |
|---|---|---|
| `N` | Número | `float` finito |
| `B` | Booleano | `bool` |
| `V2` | Vector 2D | tupla inmutable de 2 números |
| `V3` | Vector 3D | tupla inmutable de 3 números |
| `V4` | Vector 4D | tupla inmutable de 4 números |
| `MX3` | Matriz 3×3 | 9 números, filas en orden |
| `MX4` | Matriz 4×4 | 16 números, filas en orden |

`M` ya significa **Malla dinámica** y `MT`, **Material**; una matriz no puede apropiarse de ninguno.
Los enteros no nacen como tipo aparte: los campos que necesitan cantidad siguen coaccionando al tipo
de su default. Cuaterniones, rotadores y transforms quedan fuera de este primer plan; podrán apoyarse
en `V3`, `V4` y `MX4` cuando haya un caso de uso concreto.

No habrá promoción silenciosa entre dimensiones ni difusión automática de un escalar sobre un vector
o una matriz. Esas conversiones serán nodos explícitos. La regla evita que `A × B` cambie de significado
según cables que el usuario no está mirando.

## Convención de nombres y pines

Los verbos internos son estables y en inglés técnico; las etiquetas y documentación son españolas:

```text
math_add       → Sumar
math_subtract  → Restar
math_multiply  → Multiplicar
math_divide    → Dividir
```

Cada pin muestra `nombre (Tipo)`: `a (Número)`, `b (Número)`, `resultado (Número)`. El nombre corto
del tipo queda además en tooltip y JSON. En operaciones no conmutativas los nombres deben explicar
el orden: `dividendo/divisor`, `base/exponente`, `valor/mínimo/máximo`; no se usarán `x` e `y` cuando
eso esconda la semántica.

## Fase 1 — aritmética escalar mínima

Es la entrega inicial y debe ser usable por sí sola:

| Grupo | Verbos | Firma |
|---|---|---|
| Básica | Sumar, Restar, Multiplicar, Dividir | `N, N → N` |
| Signo | Negar, Absoluto | `N → N` |
| Resto y potencia | Módulo, Potencia, Raíz cuadrada | `N, N → N` o `N → N` |
| Rango | Mínimo, Máximo, Limitar, Saturar | `N… → N` |
| Mezcla | Interpolar, Remapear | entradas escalares nombradas → `N` |
| Redondeo | Piso, Techo, Redondear | `N → N` |
| Ángulos | Grados a radianes, Radianes a grados, Seno, Coseno, Tangente | `N → N` |
| Comparación | Menor, Menor o igual, Mayor, Mayor o igual, Igual aproximado | `N, N → B` |

Dividir por cero, raíz de negativo, logaritmo fuera de dominio y resultados no finitos son errores de
Compile con el nodo y el pin responsables; nunca se convierten a cero ni a `None` silenciosamente.
`Igual aproximado` recibe una tolerancia explícita. Para flotantes, un `Igual` exacto invita a errores.

El nodo `math` existente pasa a llamarse visualmente **Expresión** y permanece al final del grupo
**Avanzado**. No se migran ni reescriben grafos existentes.

## Fase 2 — series numéricas

`N[]` ya existe como dato rico y `graph_curve` produce una `ScalarSeries`; esta fase lo incorpora al
registro general de valores y agrega Sumar serie, Producto, Promedio, Mediana, Mínimo, Máximo,
Longitud y Desviación estándar. No se simula una serie mediante texto CSV.
Los agregadores vacíos deben declarar su conducta por verbo: error para promedio/mediana, identidad
para suma y producto sólo si esa decisión queda visible en la documentación.

## Fase 3 — vectores

- construir y descomponer `V2`, `V3` y `V4`;
- sumar/restar vectores y escalar por `N` con verbos distintos;
- largo, largo al cuadrado, distancia y normalizar;
- producto punto para dimensiones iguales;
- producto cruz únicamente `V3 × V3 → V3`;
- interpolar vectores y limitar largo;
- conversiones explícitas entre dimensiones, indicando qué componente se descarta o agrega.

Normalizar el vector cero es error, no un vector cero fingido. El producto componente a componente se
llama **Multiplicar componentes** y no comparte verbo con escalar ni con producto punto.

## Fase 4 — matrices

La representación serializada es una lista plana en orden de filas y la documentación fija la
convención de composición antes de conectar con Unreal. El adaptador `ue.py` será el único lugar que
convierta entre el valor puro de Jam y tipos del motor.

- Identidad 3×3 e Identidad 4×4.
- Construir por filas/columnas y descomponer filas/columnas.
- Transponer, determinante e inversa.
- Multiplicar matrices del mismo tamaño.
- Transformar vector: `MX3 × V3 → V3` y `MX4 × V4 → V4`.
- Construir 4×4 desde traslación, rotación y escala sólo después de fijar orden, handedness y unidades.
- Descomponer una 4×4 con fallo explícito ante matrices no descomponibles.

**Multiplicar matrices** y **Multiplicar componentes** son nodos distintos. Invertir una matriz singular
es error con diagnóstico; no devuelve identidad.

## Arquitectura propuesta

1. Crear `jam/math_core.py`, puro y sin `import unreal`, con tipos de valor, validación finita y
   operaciones. No usa `eval`.
2. Crear un registro declarativo común de nodos de valor. De él salen spec, tipos de pines, defaults,
   evaluación y etiquetas del ribbon.
3. Hacer que `jam.flow` y `jam.graph` resuelvan el mismo DAG de valores. El cable manda sobre el
   default del campo, como hoy.
4. Extender el contrato de tool con pines de valor nombrados y tipo de salida. Slate sólo dibuja lo
   que publica el spec.
5. Agregar grupos al ribbon: **Aritmética**, **Rango**, **Trigonometría**, **Comparación** y
   **Avanzado**; Vectores y Matrices aparecen cuando sus fases estén implementadas.
6. Mantener `math`/Expresión como compatibilidad avanzada, pero sacar sus listas y defaults duplicados
   de ambos evaluadores.

Esto preserva la regla “cerebro puro, adaptador fino”: toda cuenta se prueba sin motor. `ue.py` sólo
traduce valores cuando una herramienta de Unreal realmente los consume.

## Verificación y criterio de entrega

- tablas de verdad y casos de borde por verbo;
- propiedades con bucles deterministas: conmutatividad donde corresponde, `a-a=0`, identidades,
  distributividad dentro de tolerancia y `M × I = M`;
- pruebas específicas de no conmutatividad para resta, división y matrices;
- errores de dominio, división por cero, overflow/no finito y matriz singular;
- round-trip JSON de vectores y matrices;
- paridad: el mismo grafo de valores produce el mismo resultado en Flow y Graph;
- test de contrato que lee Slate para atar etiquetas y tipos publicados;
- mutación deliberada de al menos una operación y de una regla de tipos para demostrar que las
  pruebas se ponen rojas;
- prueba real en BotOO: construir `Número → Sumar → parámetro` desde el Graph, guardar, reabrir,
  ejecutar y comprobar en el inspector el valor resuelto.

La Fase 1 se considera completa sólo con ese camino real. Las fases 2–4 no bloquean su entrega.

## Avance 2026-08-02 — base escalar implementada

Ya están implementados **Sumar**, **Restar**, **Multiplicar** y **Dividir** como primera entrega de
la Fase 1. El registro común vive en `jam/math_core.py`: Flow y Graph consumen las mismas firmas,
defaults, reglas de tipos, evaluación y diagnósticos. Los verbos explícitos no usan `eval`; el único
caso que conserva el evaluador de expresiones es el nodo compatible **Expresión**.

Slate recibe por spec el nombre visible de cada pin y lo dibuja sin cambiar el protocolo interno:
por ejemplo `dividendo (Número)`, `divisor (Número)` y `resultado (Número)` siguen serializando pines
`dividendo`, `divisor` y salida `N`. Los cuatro nodos aparecen en **Maths/Aritmética**, con iconos
propios. Sus resultados escalares quedan en la caché de ejecución y se pueden abrir en el inspector.

La base pasó 547 tests y compiló con UE 5.8.1. La sonda
`tools/experiments/verifica_math_graph.py` pasó además por el intérprete embebido y el contrato
público de Slate: spec, Compile, Run, Inspector=`40.000` y división por cero rechazada. El commandlet
termina con código 1 por nueve paquetes ilegibles preexistentes de BotOO; el marcador
`JAM_MATH_GRAPH_TEST TODO VERDE` en `BotOO.log` separa esa deuda del veredicto de Jam.

Las pruebas se hicieron fallar deliberadamente al
mutar `a + b` por `a - b` y al declarar un pin numérico como texto; ambas mutaciones fueron detectadas.
También están cubiertos paridad Flow/Graph, orden no conmutativo, división por cero, no finitos,
overflow, cable incompatible y el contrato de etiquetas de Slate.

La revisión del primer gesto manual encontró dos contratos que no estaban separados. Aunque un
grafo compuesto sólo por valores no puede modificar la escena, `api.run_graph_json` lo clasificaba
como Flow y `panel.ejecutar_flow_json` abría igualmente un Preview vacío. Además de agregar
`ok: true` y `preview: false` al envelope, la ruta pública ahora ejecuta esos grafos directamente y
termina con `RUN ✓ — … valores, sin efectos en la escena`; por lo tanto no crea ni descarta el
Preview anterior. Un grafo que contiene geometría conserva el camino transaccional de Preview.

La salida clásica también tenía tres conceptos mezclados. Quedan separados de forma explícita:

| Concepto | Ejemplo Math | Uso |
|---|---|---|
| Identidad estable del pin | `out` | cables y callbacks |
| Código de tipo | `N` | protocolo, compatibilidad y color |
| Rótulo humano | `resultado (Número)` | presentación en Slate |

Slate ya no pinta el código `N` como si fuera un segundo nombre de salida. El tooltip del grip sigue
exponiendo `out` y `N` para diagnóstico, mientras el cuerpo del nodo muestra una sola vez el rótulo
humano. Un test que lee el C++ ata esta división al spec de Python. La sonda en Unreal fue decisiva:
una primera prueba de la función interna pasó, pero la API real siguió abriendo Preview; al mover el
test al borde público reprodujo el rojo y luego validó la corrección.

## Verificación manual de la primera entrega — 2026-08-02

Brian confirmó el camino real completo en Slate: creó la función de suma con dos entradas, guardó y
volvió al grafo llamador, insertó su instancia desde Biblioteca, conectó valores, ejecutó y obtuvo el
resultado correcto en Inspector sin abrir un Preview vacío. Guardar, cerrar y reabrir conservó el
grafo. También confirmó Renombrar y Eliminar en el ABM.

Con esto queda cerrada la **primera entrega** de la base escalar —Sumar, Restar, Multiplicar y
Dividir— en tests, sonda embebida y gesto humano. La Fase 1 completa todavía requiere los grupos
Signo, Resto/Potencia, Rango, Mezcla, Redondeo, Ángulos y Comparación enumerados arriba; no se avanza
a vectores ni matrices antes de completar esa superficie escalar.

## Oracle y frontera

La exactitud aritmética pertenece primero a tests deterministas del cerebro; no hace falta inventar
una medida Oracle para reemplazarlos. Cuando un verbo matemático gobierne una salida geométrica,
Oracle seguirá midiendo el resultado observable después de la expansión normal del grafo. No se toca
`vendor/oracle/` para implementar este plan.

Relacionado: [[2026-07-25-PLAN-Tipado-Cardinalidad-Conexiones-Graph-v1.0|tipado y cardinalidad del
Graph]] y [[2026-07-29-INFORME-Funciones-Graph-Firma-v1.0|funciones con firma explícita]].
