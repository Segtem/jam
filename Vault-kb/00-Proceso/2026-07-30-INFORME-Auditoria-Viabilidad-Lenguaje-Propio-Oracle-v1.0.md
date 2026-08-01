---
title: "Auditoría de viabilidad: un lenguaje propio para Oracle"
tipo: INFORME
version: "1.0"
date: 2026-07-30
updated: 2026-07-30
status: dictamen-desaconsejado
area: 00-Proceso
tags:
  - oracle
  - metalenguaje
  - arquitectura
  - dsl
  - verificacion
  - viabilidad
aliases:
  - Viabilidad del lenguaje de Oracle
  - Auditoría del DSL de Oracle
---

# Auditoría de viabilidad: un lenguaje propio para Oracle

## Veredicto

**DESACONSEJADO construir un lenguaje completo para Oracle.**  
**Confianza: 92 %.**

Sí es razonable estudiar una sintaxis de autoría adicional, pero sólo de forma **condicional** y
conservando el DSL, el IR canónico y el intérprete actuales.

Las tres razones principales:

1. **Oracle ya tiene un DSL externo interpretado.** Las listas JSON son su sintaxis concreta,
   `Medida.de_datos()` construye y valida su representación y `desde()` / `_evaluar_expr()` recorren
   el árbol para ejecutarlo (`nucleo/medida.py:116`, `nucleo/algebra.py:188`, `:263`, `:517`).
2. **Los problemas observables no son de expresividad.** Son principalmente autoría verbosa, falta
   de esquema estático para relaciones y campos, y ausencia de ubicaciones de origen en errores
   semánticos. Todo eso puede resolverse sin VM, compilador ni lenguaje general.
3. **La economía es mala.** El historial Git muestra un solo contribuidor. Un frontend nuevo y digno
   de producción costaría aproximadamente 600–1.400 horas-persona; un lenguaje completo,
   2.200–5.600. Es una inversión comparable o superior al tamaño del producto que intenta servir.

La suite observada durante esta auditoría: **319 tests, todos pasan**.

## 1. Qué hay realmente en el repositorio

### Arquitectura encontrada

El flujo efectivo es:

```text
productor/sensor → relaciones de hechos → medida JSON → validación
                 → intérprete relacional → veredicto/testigos
```

- El núcleo está en `nucleo/`: álgebra, medidas, macros, mutación, proyectos, simulación y fixtures.
- Los comandos están en `tools/`.
- Las declaraciones viven en `catalogos/` y `perfiles/*/catalogos/`.
- La implementación requiere Python 3.11, no declara dependencias de runtime y se distribuye con
  setuptools (`pyproject.toml:5-31`).
- Hay siete entry points CLI (`pyproject.toml:13-20`).

El DSL no es «configuración JSON» en el sentido pasivo. Tiene:

- operadores relacionales `de`, `donde`, `unir`, `agrupar` y `resumen`
  (`ESPECIFICACION.md:81-105`);
- expresiones recursivas, comparadores, lógica, accesores y UDF (`nucleo/algebra.py:178-249`);
- validación sintáctico-semántica (`nucleo/algebra.py:188`);
- evaluación de AST (`nucleo/algebra.py:263`);
- macros que bajan a forma canónica (`nucleo/macro.py:42-109`);
- transformaciones estructurales para mutación (`nucleo/mutacion.py:139-247`);
- metaprogramación: las medidas se convierten en hechos y se miden con el mismo lenguaje
  (`nucleo/medida.py:263-290`).

Esto corresponde al peldaño 5: **DSL externo interpretado mediante recorrido de AST**.

### Abstracciones repetidas

#### «Ninguna fila debe violar…»

De 18 medidas declaradas, 15 usan la macro `ninguno` y sólo tres están en forma canónica. La
abstracción ya existe en `nucleo/macro.py:42`; la plantilla de autoría también la usa
(`tools/medida.py:42`). Esto demuestra repetición de intención, pero no necesidad de un lenguaje más
potente: una macro cubre el 83 % del catálogo.

#### Despacho por cabeza de lista

La identificación de operadores se repite entre validación y ejecución
(`nucleo/algebra.py:207`, `:267`, `:419`, `:435`). Parte es inherente a un intérprete. Parte podría
centralizarse en metadatos de operadores para evitar desincronización.

#### Resolución global de proyecto

Varios módulos resuelven `PROY` al importar, por ejemplo `tools/medida.py:40`, `tools/corpus.py:28` y
`tools/mutar_codigo.py:33`. Esto dificulta embedding, composición y tests aislados. Es deuda de API,
no falta de lenguaje.

### Lógica configurable hardcodeada

Hay que distinguir dos clases.

Hardcode legítimo, porque define el lenguaje:

- comparadores (`nucleo/algebra.py:120`);
- accesores y lógicos (`nucleo/algebra.py:178`);
- agregados (`nucleo/algebra.py:305`);
- fuentes y dispatch (`nucleo/algebra.py:344`);
- macros disponibles (`nucleo/macro.py:90`).

Un lenguaje necesita un vocabulario cerrado. Esto no es un Goodhart escondido mientras esté
especificado y probado.

Hardcode discutible:

- `MACROS` sólo puede ampliarse modificando Python;
- `ESCALARES` es un registro global mutable (`nucleo/algebra.py:59`);
- los nombres físicos `catalogos/`, `corpus/` y `diferencial/` son parte fija de `Proyecto`
  (`nucleo/proyecto.py:113-126`);
- el CLI todavía dice que `agrupar` no tiene usuario, aunque está activo
  (`tools/medida.py:116`, `nucleo/algebra.py:389`). Es deuda/documentación desincronizada.

En cambio, los límites de recursos no están escondidos: son parámetros explícitos por evaluación,
con valores predeterminados de 100.000 filas, producto de 1.000.000 y profundidad 64
(`nucleo/algebra.py:24-46`).

### Carencia de verificación demostrable

Oracle valida forma, aridad y operaciones, pero no posee un esquema declarado para cada relación.

`oracle-medida --relaciones` infiere campos y tipos observando la evidencia disponible
(`tools/medida.py:76-99`). Por eso `validar_expr()` puede aceptar
`["campo", "m", "mruio"]`; el error sólo aparece al evaluar, cuando el acceso devuelve un valor
ausente (`nucleo/algebra.py:269-287`).

Además, `cargar()` usa `json.loads()` y entrega listas sin información de origen a
`Medida.de_datos()` (`nucleo/medida.py:179`). Los errores JSON tienen línea y columna, pero los
errores semánticos posteriores no pueden apuntar al token ofensivo (`tools/medida.py:150-160`).

Éste es el problema técnico más importante que sí podría justificar trabajo de lenguaje.

### Dependencias críticas del ecosistema actual

- Python 3.11 y biblioteca estándar.
- JSON como formato canónico, serializable, mutable y apto para hashing.
- Decoradores Python como FFI/UDF (`nucleo/algebra.py:84`).
- Los perfiles empaquetados se descubren sin enumerar nombres en el núcleo
  (`nucleo/proyecto.py:50`).
- Las UDF externas ejecutan Python con todos los permisos del proceso, tras
  `--confiar-escalares` (`nucleo/proyecto.py:158-219`).

Esto último no es una puerta trasera oculta: es una frontera de confianza explícita. Pero cualquier
lenguaje nuevo tendrá que conservarla, reemplazarla con una sandbox real o perder la
interoperabilidad existente.

## 2. El problema real

Reformulado en una frase:

> **Quien escribe medidas debe manipular S-expressions JSON posicionales, con validación incompleta
> de nombres y tipos de campos y sin diagnósticos semánticos con ubicación de origen.**

Clasificación:

- **Expresividad:** no demostrada como problema. Las 18 medidas actuales cierran sobre cinco
  operadores; el propio diseño retira construcciones sin dos usuarios (`ESPECIFICACION.md:101-114`).
- **Audiencia:** posiblemente importante, pero no hay evidencia en el repositorio sobre autores no
  programadores. Esto falta medir.
- **Verificación:** sí, es un problema real. Faltan esquemas estructurales de relaciones y chequeo de
  campos y tipos antes de evaluar.
- **Deuda técnica disfrazada:** sí, parcialmente. Estado global de proyecto/UDF, dispatch repetido y
  documentación desincronizada no se arreglan creando otra sintaxis.

## 3. Escalera de alternativas

| Peldaño | Qué resuelve | Qué no resuelve | Dictamen |
|---|---|---|---|
| 1. Refactor/API | Elimina `PROY` global, encapsula UDF, centraliza metadatos y diagnósticos | JSON posicional, autores no programadores, spans | **Justificado** |
| 2. API fluida/builder | Autocompletado y composición para autores Python; baja al IR actual | Ejecuta código anfitrión; mala opción para entrada no confiable o no programadores | **Justificado sólo para programadores** |
| 3. Declarativo con esquema | Campos nombrados, validación estructural, autocompletado de editor y versionado | No da comentarios o sintaxis verdaderamente humana; composición limitada | **Recomendado** |
| 4. DSL embebido | Abstracciones reutilizables y ecosistema Python | Seguridad, audiencia no técnica y portabilidad | **No justificado por el catálogo actual** |
| 5. DSL externo interpretado | Aislamiento, semántica limitada, análisis previo | Parser, diagnósticos, formatter y LSP propios | **Ya existe**; nuevo frontend sólo condicional |
| 6. Lenguaje completo | Control de ejecución y extensibilidad general | No resuelve por sí mismo esquema ni UX; multiplica runtime y tooling | **Desaconsejado** |

La secuencia correcta es detenerse primero en el peldaño 3:

1. Separar el IR canónico de su formato de autoría.
2. Declarar esquemas de relaciones.
3. Añadir una forma JSON de campos nombrados que baje al IR actual.
4. Medir si eso sigue siendo insuficiente.
5. Sólo entonces probar una sintaxis textual.

Para este árbol de expresiones, TOML es incómodo y YAML introduciría dependencia, ambigüedad de
tipos y otra superficie de parsing. JSON con objetos nombrados y esquema versionado es el candidato
de menor costo.

## 4. Diseño técnico condicional de un frontend externo

No se recomienda reemplazar el DSL actual. Si el experimento demuestra que hace falta sintaxis
humana, se recomienda el siguiente diseño.

### Semántica

Debe conservar exactamente el modelo existente:

- relaciones como bolsas de hechos escalares;
- fuentes, filtros, producto, agrupación y resumen;
- comparadores con tipos compatibles;
- umbral defendido, alcance obligatorio y testigos derivados;
- UDF declaradas por el host.

Prohibido a propósito:

- estado mutable;
- I/O, red y acceso a variables de entorno;
- bucles generales y recursión;
- clases, excepciones e importación arbitraria;
- reflexión;
- definición de nuevos operadores desde la propia medida;
- FFI genérica.

Si se agregan estas capacidades, Oracle deja de ser un lenguaje declarativo verificable y empieza a
competir con Python.

### Modelo de ejecución recomendado

```text
fuente textual → CST/AST con spans → chequeo de esquema/tipos
               → IR JSON canónico → intérprete actual
```

Se recomienda **lowering al IR actual y evaluación por el intérprete existente**.

No se recomienda:

- bytecode: no hay bucles ni carga computacional que lo justifique;
- transpilación a Python: aumenta el riesgo de inyección y complica la correspondencia de errores;
- backend nativo o WASM: no hay evidencia de cuello de botella ni necesidad de ejecución fuera de
  Python;
- segundo evaluador: duplicaría semántica y pondría en riesgo la equivalencia del oráculo.

### Sistema de tipos

Conviene un sistema pequeño y estructural:

- `Bool`, `Int`, `Float`, `Number`, `String`;
- `Record {campo: Tipo}`;
- `Relation<Record>`;
- alias de fila y columnas derivadas;
- firma de UDF: nombre, argumentos, retorno, unidad y procedencia;
- reglas para agregados, comparadores y flotantes.

Debe detectar estáticamente:

- relación, alias o campo desconocido;
- uso de `col` antes de `agrupar`;
- comparaciones incompatibles;
- agregado aplicado al tipo incorrecto;
- resultado del resumen incompatible con el umbral.

No hace falta inferencia Hindley–Milner, genéricos ni tipos nominales. El costo está en declarar el
esquema de los sensores y mantenerlo sincronizado, no en un algoritmo sofisticado de tipos.

### Interoperabilidad

- Reemplazar el diccionario global por una instancia `RegistroEscalares`.
- Conservar el decorador `@escalar`.
- Añadir tipos de argumentos y retorno a su contrato.
- Exponer al DSL sólo metadatos y llamadas, nunca módulos u objetos Python arbitrarios.
- Mantener `--confiar-escalares` para código externo.
- Ejecutar UDF no confiables en proceso aislado si eventualmente aparece ese requisito; hoy no
  existe esa sandbox.

### Parsing

- **Lark/LALR:** mejor opción para el spike. Gramática legible, spans automáticos y parser interactivo
  para recuperación de errores. Añade una dependencia Python. Véase la
  [documentación de Lark](https://lark-parser.readthedocs.io/) y su
  [manejo interactivo de errores](https://lark-parser.readthedocs.io/en/stable/examples/advanced/error_handling.html).
- **Recursive descent escrito a mano:** razonable si la gramática queda muy pequeña. Cero
  dependencias y control total de diagnósticos; el costo es mantener lexer, precedencias,
  recuperación y formatter.
- **`tokenize` de Python:** sólo sirve si la sintaxis es deliberadamente un subconjunto de Python.
  Su documentación advierte que el comportamiento sobre Python sintácticamente inválido no está
  definido; no conviene para una gramática distinta. Véase la
  [documentación oficial](https://docs.python.org/3/library/tokenize.html).
- **Tree-sitter:** apropiado posteriormente para editor, resaltado e incrementalidad; no como parser
  único del runtime durante el spike. Implicaría mantener una segunda gramática. Véase la
  [documentación oficial](https://tree-sitter.github.io/).
- **ANTLR:** útil si se requieren múltiples lenguajes anfitriones, pero runtime generado y pipeline
  más pesado. No hay ese requisito actualmente.

### Errores como requisito

Cada nodo debe conservar:

- archivo, offset inicial/final, línea y columna;
- código estable de diagnóstico;
- fase: parsing, resolución, tipos, lowering o ejecución;
- fragmento y caret;
- nombre inválido y candidatos cercanos;
- contexto de alias y relación;
- posibilidad de reportar varios errores por archivo.

Criterio de aceptación: al menos el 90 % de un corpus de errores sembrados debe señalar el token
responsable y proponer una corrección accionable.

## 5. Costo total de propiedad

**Estas cifras son estimaciones, no hechos del repositorio.** Asumen una implementación de producción
por alguien que ya conoce Oracle.

| Componente | Peldaño 3: esquema/JSON nombrado | Peldaño 5: nueva sintaxis | Peldaño 6: lenguaje completo |
|---|---:|---:|---:|
| Diseño y especificación | 16–32 h | 40–80 h | 120–240 h |
| Parser/esquema/CST | 24–48 h | 60–120 h | 80–180 h |
| Análisis semántico y tipos | 32–64 h | 80–180 h | 240–600 h |
| Runtime/lowering/backend | 16–32 h | 24–60 h | 320–900 h |
| Biblioteca mínima/macros | 16–32 h | 24–60 h | 160–400 h |
| Tests | 32–64 h | 100–220 h | 400–1.000 h |
| Resaltado | 0–4 h | 16–40 h | 40–80 h |
| Formateador | 0–8 h | 40–100 h | 80–200 h |
| LSP | 8–24 h | 120–300 h | 300–800 h |
| Debugger/visualizador de traza | 0 h | 40–120 h | 200–600 h |
| Empaquetado | 8–16 h | 16–32 h | 80–200 h |
| Documentación | 16–32 h | 40–80 h | 160–400 h |
| **Total** | **168–356 h** | **600–1.392 h** | **2.180–5.600 h** |
| **Mantenimiento anual** | **40–80 h** | **150–350 h** | **500–1.200 h** |

### Bus factor

`git shortlog -sne --all` reporta un solo contribuidor: **bus factor observable = 1**.

Si el único mantenedor se ausenta seis meses:

- el esquema JSON puede congelarse y seguir consumiendo el runtime actual;
- un frontend propio debe congelar gramática y versiones; cualquier bug de parser o formatter queda
  sin dueño;
- un lenguaje completo deja bloqueados releases, compatibilidad, seguridad y evolución del tooling;
- sin un segundo mantenedor que pueda modificar parser, checker y runtime, no debería declararse
  estable.

## 6. Migración y rollback

1. Declarar la lista JSON actual como **IR canónico v1**, no como formato legado.
2. Incorporar un loader por versión o extensión.
3. Hacer que cualquier formato nuevo baje a `Medida.a_datos()` (`nucleo/medida.py:168`).
4. Permitir coexistencia de `.json` y, sólo si se aprueba, `.ora`.
5. Mantener mutación, inventario, evaluación y huellas trabajando exclusivamente con el IR.
6. Exigir pruebas diferenciales: fuente nueva y JSON viejo deben producir bytes canónicos
   equivalentes.
7. Migrar primero seis medidas representativas; después el resto, sin conversión obligatoria.
8. No eliminar soporte JSON durante al menos dos versiones estables.

Rollback:

- se deshabilita el loader nuevo;
- se conservan o regeneran las declaraciones JSON canónicas;
- no se toca el evaluador ni el formato de veredicto;
- no se pierden catálogos, corpus, mutantes ni fixtures;
- si el frontend se abandona a mitad, sus archivos no se convierten en la única fuente de verdad.

## 7. Precedentes

### HCL / Terraform

HCL mantiene una sintaxis nativa humana y una variante JSON generable por máquinas; la aplicación
sigue definiendo su esquema y semántica. Lo acertado es separar superficie humana y representación
estructurada. Lo costoso —esto es una inferencia— es mantener ambas superficies y todo el tooling;
HCL no elimina el trabajo semántico de la aplicación. Además, su implementación principal está
orientada a Go. Véase la [documentación oficial de HCL](https://hcl.readthedocs.io/en/latest/).

### Starlark / Bazel

Funcionó al ser embebible, determinista y hermético, con capacidades del dominio aportadas por el
host. Lo consiguió prohibiendo tipos definidos por usuarios, reflexión, excepciones, recursión y
bucles no acotados. Es un buen precedente para limitar capacidades, pero su tipado dinámico no
resolvería por sí solo los errores de campos de Oracle. Véase la
[especificación oficial](https://github.com/bazelbuild/starlark/blob/master/spec.md).

### Jsonnet

Resolvió composición y repetición en configuraciones complejas mediante un lenguaje funcional
completo y salida JSON. El costo es un modelo mental mayor; su propia documentación señala que
programadores imperativos deben cambiar de mentalidad y que las variables externas globales generan
problemas de composición. Oracle tiene 15 de 18 medidas cubiertas por una macro, por lo que todavía
no demuestra el nivel de duplicación que motivó Jsonnet. Véase la
[referencia oficial](https://jsonnet.org/ref/language.html).

### CUE y la experiencia de GCL

CUE prioriza validación y restricciones sobre eliminación de boilerplate. Su historia documenta que
el modelo de herencia y overrides de GCL produjo una complejidad que volvió intratable el tooling
previsto. Es el precedente más directamente aplicable: agregar poder de abstracción puede destruir
analizabilidad y diagnósticos. Véanse la [historia de CUE](https://cuelang.org/docs/introduction/) y
su [caso de configuración](https://cuelang.org/docs/concept/configuration-use-case/).

## 8. El argumento más fuerte para no hacerlo

Oracle pretende juzgar otros sistemas. Su componente más sensible debe ser el más pequeño, explícito
y fácil de verificar.

Crear un lenguaje completo introduce otra especificación, parser, checker, runtime, biblioteca,
empaquetado, compatibilidad y tooling. Cada error en ese stack puede producir precisamente lo que
Oracle intenta detectar: falsos verdes y falsos rojos.

El catálogo actual no exige variables, funciones de usuario, módulos, control de flujo, recursión ni
tipos avanzados. Quince de dieciocho medidas son una sola macro. Construir una VM para eso no es
arquitectura; es sustituir una representación verbosa por una plataforma mucho más grande.

Además, las fallas concretas seguirían allí:

- un compilador no inventa esquemas de sensores;
- una sintaxis elegante no elimina `PROY` y `ESCALARES` globales;
- una VM no corrige documentación desincronizada;
- un backend propio no mejora la defensa de umbrales ni la declaración de alcance;
- reimplementar el ecosistema Python perjudica las UDF; conservarlo obliga a diseñar FFI y
  seguridad.

El proyecto aumentaría drásticamente su superficie de fallo para resolver problemas que un esquema,
mejores diagnósticos y un builder podrían resolver con una fracción del costo.

## Criterios de descarte

Abandonar la iniciativa de sintaxis o lenguaje propio si se cumple cualquiera:

1. Un formato JSON nombrado con esquema reduce los errores de autoría al mismo nivel que el frontend
   textual. En ese caso el peldaño 3 ya resolvió el problema.
2. El frontend no reduce al menos **30 %** el tiempo mediano de seis tareas de autoría frente al JSON
   actual.
3. No reduce al menos **50 %** los errores de estructura, alias, campos y tipos.
4. No puede bajar las 18 medidas actuales al mismo `a_datos()` canónico.
5. Cambia algún resultado de los 319 tests o necesita un segundo evaluador.
6. Requiere control de flujo, imports o nuevas capacidades antes de existir dos medidas reales que
   las necesiten.
7. No consigue diagnóstico con ubicación correcta en al menos **90 %** de 30 errores sembrados.
8. Supera 24 horas en el spike sin haber producido una comparación medible.
9. No aparece un segundo mantenedor capaz de modificar parser y checker antes de declararlo estable.
10. La estimación de producción supera 800 horas-persona para el frontend o 200 horas al año de
    mantenimiento sin al menos tres proyectos consumidores independientes.

## Spike mínimo de validación

**Presupuesto máximo: 24 horas-persona.**

- 2 h: seleccionar seis medidas representativas: macro, forma canónica, `unir`, `agrupar`, UDF y
  meta.
- 6 h: declarar esquemas de relaciones y validar nombres y tipos sobre el JSON actual.
- 5 h: crear una forma JSON con campos nombrados y lowering al IR actual.
- 6 h: parser Lark mínimo para la misma forma semántica, con spans; sin imports, módulos ni runtime
  nuevo.
- 3 h: sembrar 30 errores y medir calidad de diagnósticos.
- 2 h: comparar tiempo de autoría, errores y equivalencia canónica.

El spike debe comparar tres variantes:

1. JSON actual.
2. JSON nombrado con esquema.
3. Sintaxis textual mínima.

Si la segunda variante alcanza las métricas, **no se construye la tercera en producción**. Si la
tercera gana claramente, se autoriza únicamente el frontend y el checker, nunca una VM.

## Supuestos e información faltante

Supuestos utilizados:

- «Lenguaje propio» significa reemplazar o complementar la superficie JSON actual.
- El catálogo actual es representativo de la expresividad necesaria a corto plazo.
- Python seguirá siendo el lenguaje anfitrión.
- No existe un requisito actual de ejecutar UDF no confiables.
- Los resultados actuales del intérprete son la referencia de compatibilidad.

Información que falta:

- quién escribirá medidas: programadores, especialistas del dominio o usuarios no técnicos;
- cuántos autores y proyectos se esperan;
- cuántas medidas nuevas se escribirán por mes o año;
- registro real de errores y tiempo actual de autoría;
- necesidad comprobada de composición entre archivos, parámetros o módulos;
- requisitos de ejecución no confiable, portabilidad o embedding fuera de Python;
- presupuesto y disponibilidad de un segundo mantenedor.

Esa información podría cambiar el veredicto sobre **un frontend textual**. No cambia, con la
evidencia actual, el dictamen contra una VM, transpilador o lenguaje completo.

## Relacionado

- [[2026-07-30-INFORME-Oracle-Metalenguaje-De-Medidas-v1.0|Oracle: un metalenguaje de medidas]]
- [[2026-07-29-GUIA-Convencion-Documentacion-Vault-v1.0|Convención de documentación del vault]]
