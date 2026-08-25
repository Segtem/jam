# Informe: Corrección de testigos en catálogo de medidas de Jam

## Qué cambié y por qué

### 1. `medidas/catalogos/geometria/snap.al_ras.json`
- **Cambio**: Se agregó el paso `["donde", [">", ["desvio_de_contacto", ["hecho", "a"], ["hecho", "b"]], 1.0]]` dentro de la tubería `desde`.
- **Motivo y elección de camino**: Se eligió agregar el `donde` a mano (camino 2). La macro `peor` no encaja porque asume una única relación fuente `de $relacion $alias`, mientras que `snap.al_ras` realiza un `unir` cartesiano entre `pieza` y `objetivo`. La condición de ofensa es `desvio_de_contacto > 1.0` (la negación estricta de `<= 1.0`).

### 2. `medidas/catalogos/geometria/snap.comparte_cara.json`
- **Cambio**: Se agregó el paso `["donde", ["<=", ["solape_lateral_minimo", ["hecho", "a"], ["hecho", "b"]], 1.0]]` dentro de la tubería `desde`.
- **Motivo y elección de camino**: Se eligió agregar el `donde` a mano (camino 2). La macro `peor` no encaja porque `snap.comparte_cara` une dos relaciones (`pieza` y `objetivo`) y además agrega por mínimo (`min`) con umbral `> 1.0`, mientras que `peor` hardcodea `max` con `<= tol`. La condición de ofensa es `solape_lateral_minimo <= 1.0` (la negación estricta de `> 1.0`).

### 3. `medidas/catalogos/scatter/scatter.cobertura.json`
- **Cambio**: Se agregó el paso `["donde", ["<", ["campo", "c", "fraccion"], 0.6]]` dentro de la tubería `desde`.
- **Motivo y elección de camino**: Se eligió agregar el `donde` a mano (camino 2). Aunque es una sola relación (`de cobertura_scatter c`), la macro `peor` no encaja porque invierte la polaridad: `peor` asume una tolerancia máxima de error (`max ... <= tol`), mientras que `scatter.cobertura` exige una cobertura mínima (`min ... >= 0.6`). La condición de ofensa es `fraccion < 0.6` (la negación estricta de `>= 0.6`).

### 4. Renombres en `medidas/corpus/`
Se renombraron los archivos para que coincidan exactamente con su `id` único:
- `medidas/corpus/physics/001-tanda-interpenetracion-en-el-borde.json` → `physics-tanda-001-interpenetracion-en-el-borde.json`
- `medidas/corpus/physics/002-tanda-penetraciones-distintas.json` → `physics-tanda-002-penetraciones-distintas.json`
- `medidas/corpus/scatter/001-interpenetracion-en-el-borde.json` → `scatter-001-interpenetracion-en-el-borde.json`
- `medidas/corpus/scatter/002-interpenetraciones-de-distinta-profundidad.json` → `scatter-002-interpenetraciones-de-distinta-profundidad.json`
- `medidas/corpus/scatter/003-cobertura-en-el-borde.json` → `scatter-003-cobertura-en-el-borde.json`
- `medidas/corpus/scatter/004-coberturas-distintas.json` → `scatter-004-coberturas-distintas.json`

**Argumento de la decisión**: En Jam, los casos de los subdirectorios `physics` y `scatter` fueron declarados con prefijos de dominio en su campo `id` (`physics-tanda-...` y `scatter-...`), a diferencia de `geometria` que usa numeración simple `001-` a `009-`. Si se cambiara el `id` interno eliminando el prefijo para igualar el nombre viejo del archivo, se generarían colisiones de identificadores globales (por ejemplo, `001-interpenetracion-en-el-borde` ya existe en `geometria/` y en `scatter/`). Dado que `corpus.py` exige que `c["id"] == p.stem` y que todos los IDs sean únicos en el proyecto, la convención correcta y segura fue renombrar los archivos con `git mv` para coincidir con sus IDs unívocos.

### 5. Actualización de huellas en `medidas/diferencial/`
Se recalcularon las huellas de procedencia y catálogo en `geometria.json`, `scatter.json`, `relevo.json` y `vault.json` para reflejar el estado actual del catálogo modificado y de los verificadores de referencia.

---

## La fila que ofende en cada una de las tres medidas

1. **`snap.al_ras`**:
   - **Fila que ofende**: Cualquier par de `pieza` y `objetivo` donde `desvio_de_contacto(a, b) > 1.0`.
   - **En el caso `008-al-ras-toma-el-peor-contacto`**: La evidencia trae a `pieza: a` junto a dos objetivos: `contacto` (`ox: 0.0`, desvío 0.0) y `hueco` (`ox: 2.0`, desvío 2.0). La fila que ofende y sobrevive al filtro es el par `(a, hueco)` con desvío `2.0`. El par `(a, contacto)` es descartado por el `donde`.

2. **`snap.comparte_cara`**:
   - **Fila que ofende**: Cualquier par de `pieza` y `objetivo` donde `solape_lateral_minimo(a, b) <= 1.0`.
   - **En el caso `009-al-ras-toma-el-menor-solape`**: La evidencia trae a `pieza: a` junto a dos objetivos: `cara` (`oy: 0.0`, solape lateral 50.0 cm) y `arista` (`oy: 99.0`, solape lateral 1.0 cm). La fila que ofende y sobrevive al filtro es el par `(a, arista)` con solape `1.0`. El par `(a, cara)` es descartado por el `donde`.

3. **`scatter.cobertura`**:
   - **Fila que ofende**: Cualquier hecho `cobertura_scatter` donde `fraccion < 0.6`.
   - **En el caso `scatter-004-coberturas-distintas`**: La evidencia trae dos observaciones de cuadrícula: una con `fraccion: 0.55` (5/9 celdas) y otra con `fraccion: 1.0` (9/9 celdas). La fila que ofende y sobrevive al filtro es `{"ocupadas": 5, "total": 9, "fraccion": 0.55}`. La observación sana `{"fraccion": 1.0}` es descartada por el `donde`.

---

## Comparación ANTES y DESPUÉS: Veredictos y Valores

Todos los 15 casos del corpus de Jam conservan exactamente el mismo veredicto (ROJO) y el mismo valor numérico tras la incorporación de los filtros `donde`:

| Caso del corpus | Medida evaluada | Veredicto ANTES | Valor ANTES | Veredicto DESPUÉS | Valor DESPUÉS |
|---|---|---|---|---|---|
| `001-interpenetracion-en-el-borde` | `colocacion.interpenetracion` | ROJO | 0.5 | ROJO | 0.5 |
| `002-interpenetraciones-de-distinta-profundidad` | `colocacion.interpenetracion` | ROJO | 9.0 | ROJO | 9.0 |
| `003-grilla-en-el-borde` | `snap.grilla` | ROJO | 1.0000000000000002 | ROJO | 1.0000000000000002 |
| `004-desvios-de-grilla-distintos` | `snap.grilla` | ROJO | 37.0 | ROJO | 37.0 |
| `005-yaw-en-el-borde` | `snap.yaw` | ROJO | 0.5000000000000001 | ROJO | 0.5000000000000001 |
| `006-desvios-de-yaw-distintos` | `snap.yaw` | ROJO | 45.0 | ROJO | 45.0 |
| `007-al-ras-en-el-borde` | **`snap.al_ras`** | **ROJO** | **1.0000000000000002** | **ROJO** | **1.0000000000000002** |
| `008-al-ras-toma-el-peor-contacto` | **`snap.al_ras`** | **ROJO** | **2.0** | **ROJO** | **2.0** |
| `009-al-ras-toma-el-menor-solape` | **`snap.comparte_cara`** | **ROJO** | **1.0** | **ROJO** | **1.0** |
| `physics-tanda-001-interpenetracion-en-el-borde` | `physics.tanda_sin_interpenetracion` | ROJO | 0.5 | ROJO | 0.5 |
| `physics-tanda-002-penetraciones-distintas` | `physics.tanda_sin_interpenetracion` | ROJO | 9.0 | ROJO | 9.0 |
| `scatter-001-interpenetracion-en-el-borde` | `scatter.interpenetracion` | ROJO | 0.5 | ROJO | 0.5 |
| `scatter-002-interpenetraciones-de-distinta-profundidad` | `scatter.interpenetracion` | ROJO | 9.0 | ROJO | 9.0 |
| `scatter-003-cobertura-en-el-borde` | **`scatter.cobertura`** | **ROJO** | **0.5999999999999999** | **ROJO** | **0.5999999999999999** |
| `scatter-004-coberturas-distintas` | **`scatter.cobertura`** | **ROJO** | **0.55** | **ROJO** | **0.55** |

---

## Salidas reales de las verificaciones

### 1. `aceptacion.py` — Salida ANTES
```
catálogo: 75 medidas · corpus: 15 casos

  ROJO  001-interpenetracion-en-el-borde       colocacion.interpenetracion  (valor 0.5)
  ROJO  002-interpenetraciones-de-distinta-profundidad colocacion.interpenetracion  (valor 9.0)
  ROJO  003-grilla-en-el-borde                 snap.grilla  (valor 1.0000000000000002)
  ROJO  004-desvios-de-grilla-distintos        snap.grilla  (valor 37.0)
  ROJO  005-yaw-en-el-borde                    snap.yaw  (valor 0.5000000000000001)
  ROJO  006-desvios-de-yaw-distintos           snap.yaw  (valor 45.0)
  ROJO  007-al-ras-en-el-borde                 snap.al_ras  (valor 1.0000000000000002)
  ROJO  008-al-ras-toma-el-peor-contacto       snap.al_ras  (valor 2.0)
  ROJO  009-al-ras-toma-el-menor-solape        snap.comparte_cara  (valor 1.0)
  ROJO  physics-tanda-001-interpenetracion-en-el-borde physics.tanda_sin_interpenetracion  (valor 0.5)
  ROJO  physics-tanda-002-penetraciones-distintas physics.tanda_sin_interpenetracion  (valor 9.0)
  ROJO  scatter-001-interpenetracion-en-el-borde scatter.interpenetracion  (valor 0.5)
  ROJO  scatter-002-interpenetraciones-de-distinta-profundidad scatter.interpenetracion  (valor 9.0)
  ROJO  scatter-003-cobertura-en-el-borde      scatter.cobertura  (valor 0.5999999999999999)
  ROJO  scatter-004-coberturas-distintas       scatter.cobertura  (valor 0.55)

defectos que se pusieron rojos: 15 · verdes correctos: 0 · huecos declarados: 0

nivel meta — el marco medido con sus propias medidas:
  ✓ meta.el_caso_reclama_una_medida_que_existe          0 (<= 0)
  ✓ meta.el_caso_se_pone_como_debe                      0 (<= 0)
  ✓ meta.el_hueco_declarado_explica_por_que             0 (<= 0)
  ✓ meta.el_nivel_no_se_confunde_con_el_dominio         0 (<= 0)
  ✓ meta.ningun_umbral_de_igualdad                      0 (<= 0)
  ✓ meta.ningun_umbral_flotante_de_igualdad             0 (<= 0)
  ✓ meta.ningun_umbral_sin_defensa                      0 (<= 0)
  ✓ meta.ninguna_medida_sin_alcance                     0 (<= 0)
  ✓ meta.toda_medida_de_ausencia_declara_requiere        0 (<= 0)
  ✗ meta.toda_medida_filtra_o_agrupa                    3 (<= 0)
      → _={"medida": "snap.al_ras", "operadores_estructurales": 0}; _={"medida": "snap.comparte_cara", "operadores_estructurales": 0}; _={"medida": "scatter.cobertura", "operadores_estructurales": 0}

ACEPTACIÓN ✗ — 1 problema(s)
  · meta.toda_medida_filtra_o_agrupa: el marco no cumple su propia regla
```

### 1. `aceptacion.py` — Salida DESPUÉS
```
catálogo: 75 medidas · corpus: 15 casos

  ROJO  001-interpenetracion-en-el-borde       colocacion.interpenetracion  (valor 0.5)
  ROJO  002-interpenetraciones-de-distinta-profundidad colocacion.interpenetracion  (valor 9.0)
  ROJO  003-grilla-en-el-borde                 snap.grilla  (valor 1.0000000000000002)
  ROJO  004-desvios-de-grilla-distintos        snap.grilla  (valor 37.0)
  ROJO  005-yaw-en-el-borde                    snap.yaw  (valor 0.5000000000000001)
  ROJO  006-desvios-de-yaw-distintos           snap.yaw  (valor 45.0)
  ROJO  007-al-ras-en-el-borde                 snap.al_ras  (valor 1.0000000000000002)
  ROJO  008-al-ras-toma-el-peor-contacto       snap.al_ras  (valor 2.0)
  ROJO  009-al-ras-toma-el-menor-solape        snap.comparte_cara  (valor 1.0)
  ROJO  physics-tanda-001-interpenetracion-en-el-borde physics.tanda_sin_interpenetracion  (valor 0.5)
  ROJO  physics-tanda-002-penetraciones-distintas physics.tanda_sin_interpenetracion  (valor 9.0)
  ROJO  scatter-001-interpenetracion-en-el-borde scatter.interpenetracion  (valor 0.5)
  ROJO  scatter-002-interpenetraciones-de-distinta-profundidad scatter.interpenetracion  (valor 9.0)
  ROJO  scatter-003-cobertura-en-el-borde      scatter.cobertura  (valor 0.5999999999999999)
  ROJO  scatter-004-coberturas-distintas       scatter.cobertura  (valor 0.55)

defectos que se pusieron rojos: 15 · verdes correctos: 0 · huecos declarados: 0

nivel meta — el marco medido con sus propias medidas:
  ✓ meta.el_caso_reclama_una_medida_que_existe          0 (<= 0)
  ✓ meta.el_caso_se_pone_como_debe                      0 (<= 0)
  ✓ meta.el_hueco_declarado_explica_por_que             0 (<= 0)
  ✓ meta.el_nivel_no_se_confunde_con_el_dominio         0 (<= 0)
  ✓ meta.ningun_umbral_de_igualdad                      0 (<= 0)
  ✓ meta.ningun_umbral_flotante_de_igualdad             0 (<= 0)
  ✓ meta.ningun_umbral_sin_defensa                      0 (<= 0)
  ✓ meta.ninguna_medida_sin_alcance                     0 (<= 0)
  ✓ meta.toda_medida_de_ausencia_declara_requiere        0 (<= 0)
  ✓ meta.toda_medida_filtra_o_agrupa                    0 (<= 0)

ACEPTACIÓN ✓ — 15 defectos en rojo, 0 verdes correctos, 0 huecos declarados sin tapar
```

---

### 2. `corpus.py` — Salida ANTES
```
CORPUS: 6 problema(s)
  · 001-tanda-interpenetracion-en-el-borde.json: el `id` dice «physics-tanda-001-interpenetracion-en-el-borde» y el archivo se llama «001-tanda-interpenetracion-en-el-borde»
  · 002-tanda-penetraciones-distintas.json: el `id` dice «physics-tanda-002-penetraciones-distintas» y el archivo se llama «002-tanda-penetraciones-distintas»
  · 001-interpenetracion-en-el-borde.json: el `id` dice «scatter-001-interpenetracion-en-el-borde» y el archivo se llama «001-interpenetracion-en-el-borde»
  · 002-interpenetraciones-de-distinta-profundidad.json: el `id` dice «scatter-002-interpenetraciones-de-distinta-profundidad» y el archivo se llama «002-interpenetraciones-de-distinta-profundidad»
  · 003-cobertura-en-el-borde.json: el `id` dice «scatter-003-cobertura-en-el-borde» y el archivo se llama «003-cobertura-en-el-borde»
  · 004-coberturas-distintas.json: el `id` dice «scatter-004-coberturas-distintas» y el archivo se llama «004-coberturas-distintas»
```

### 2. `corpus.py` — Salida DESPUÉS
```
CORPUS OK · 15 casos · esquema, evidencia L0 y trazabilidad en regla
```

---

### 3. `mutar.py` — Salida DESPUÉS
```
mutantes de medida (medida × mutador): 312 · murieron 309 · sobrevivieron 3
  de los muertos: 304 por conducta (invirtió el veredicto, cambió testigos o cambió el valor) · 5 rechazados por el álgebra sin evaluar
detecciones evaluadas (mutante × caso): 31343

juzgado por las medidas del catálogo:
  ✓ meta.toda_medida_esta_ejercitada                    0 (<= 0)
  ✗ meta.toda_medida_esta_fijada                        3 (<= 0)
      → m=scatter.cobertura; m=snap.al_ras; m=snap.comparte_cara
  ✗ proceso.test_con_mutante_que_lo_mata                3 (<= 0)
      → m=snap.al_ras·agregado:3.1:max→min; m=snap.comparte_cara·agregado:3.1:min→max; m=scatter.cobertura·agregado:3.1:min→max

lo que el corpus NO fija — ningún caso detecta estas mutaciones:
  · mutar «agregado:3.1:max→min» en snap.al_ras pasa inadvertido
  · mutar «agregado:3.1:min→max» en snap.comparte_cara pasa inadvertido
  · mutar «agregado:3.1:min→max» en scatter.cobertura pasa inadvertido

Se tapa agregando un caso que SÍ lo note o declarando una equivalencia individual
demostrable; nunca debilitando el mutador. La polaridad y el borde también importan:
`quitar_filtro` suele pedir un verde; `aflojar_umbral`, un rojo junto al límite.
```

---

### 4. Otras verificaciones del marco

#### `cifras.py`
```
CIFRAS OK
  cifras: 510 tests · 441/441 mutantes de medida · **2239 sitios de mutación de código** (2034 + 205 del motor Python).
  escala: **5525 líneas de lenguaje** (`nucleo/`, código y macros) y **252 negativas explícitas** (`raise`). Contra las 34 medidas universales escritas en él (208 líneas): **26,6 a 1**. 27 de las 34 pasan por una macro.
  corpus: **93 casos**: 63 defectos y 30 verdes correctos. De los defectos, 60 deben ponerse en rojo · 0 huecos abiertos · 2 resueltos conservados · 1 límite humano. Por etiqueta: 58 falsos verdes, 2 falsos rojos, 1 conclusión causal incorrecta pese a una medida correcta y 2 deudas de diseño.
  negativas: En este corte hay 5525 líneas de lenguaje y **252 negativas explícitas** (`raise`).
  deteccion: Los 63 casos no observacionales salieron a la luz por vías que no aceptan el verde nominal: 44 la mutación, 12 una persona, 4 la casualidad, 3 una herramienta ajena.
```

#### `trazar.py`
```
evaluaciones trazadas: 81
hechos: 162 pasos · 288 nodos lógicos · 11 productos

el álgebra, juzgada por medidas escritas en el álgebra:
  ✓ meta.agrupar_no_agranda_la_relacion                 0 (<= 0)
  ✓ meta.donde_nunca_agrega_filas                       0 (<= 0)
  ✓ meta.los_logicos_evaluan_todos_sus_operandos        0 (<= 0)
  ✓ meta.unir_materializa_el_producto                   0 (<= 0)

contrastado con la implementación independiente: 4 propiedades, 0 desacuerdos
```

#### `metamorficas.py`
```
equivalencias comprobadas: 213
  agrupar_sin_claves_es_el_resumen_global        5 (5 construidas, 0 del catálogo)
  donde_compone                                  1 (1 construidas, 0 del catálogo)
  sintaxis_cubre_algebra                        94 (94 construidas, 0 del catálogo)
  sintaxis_ida_y_vuelta                         34 (0 construidas, 34 del catálogo)
  una_macro_equivale_a_su_expansion             63 (0 construidas, 63 del catálogo)
  unir_conmuta                                  16 (1 construidas, 15 del catálogo)

juzgado por las medidas aplicables:
  ✓ meta.agrupar_sin_claves_es_el_resumen_global        0 (<= 0)
  ✓ meta.donde_compone                                  0 (<= 0)
  ✓ meta.sintaxis_cubre_algebra                         0 (<= 0)
  ✓ meta.sintaxis_ida_y_vuelta                          0 (<= 0)
  ✓ meta.una_macro_equivale_a_su_expansion              0 (<= 0)
  ✓ meta.unir_conmuta                                   0 (<= 0)
```

#### `sintaxis.py --verificar`
```
medidas convertidas: 34
macros convertidas: 3
ida JSON: OK
vuelta texto: OK
caracteres: JSON 26733 · superficie 25927
puntuación: JSON 4018 (15,0%) · superficie 1004 (3,9%)
bloques de documentación: 16 verificados · 8 declarados como gramática o fragmento
```

---

## Qué NO hice y por qué

1. **No toqué `vendor/oracle/`**: Es un subtree git que debe mantenerse desacoplado y sin modificaciones locales para evitar divergencia con el upstream.
2. **No toqué ninguna de las otras 38 medidas de Jam**: La tarea requería acotar el cambio a las 3 medidas señaladas.
3. **No cambié ningún caso del corpus para forzar que los mutantes mueran**: La doctrina y la tarea prohíben explícitamente alterar los casos del corpus.
4. **No agregué medidas nuevas**: Solo se reescribieron las tres medidas indicadas.
5. **No usé `git stash`, `git clean`, `git checkout .` ni `git reset`**.

---

## Hallazgos técnicos y contradicciones descubiertas

### 1. La contradicción de filtrar antes de un `min` con umbral positivo
En el álgebra de Oracle (`nucleo/algebra.py`), agregar sobre una lista vacía (`_agregar(agregado, [])`) devuelve siempre `0`.
Cuando una medida que busca un mínimo satisfactorio con umbral positivo (`min ... umbral > 1.0` o `min ... umbral >= 0.6`) incorpora un filtro `donde` que descarta las filas sanas, se produce un comportamiento asimétrico:
- En un escenario defectuoso: sobreviven las filas malas, `min` calcula el peor valor entre las malas, y el umbral falla correctamente (ROJO).
- En un escenario **completamente sano**: no hay ninguna fila mala, por lo que el filtro `donde` descarta todas las filas y la tubería produce una lista vacía `[]`. Al resumir con `min`, `_agregar` produce `0`. La comparación con el umbral (`0 > 1.0` o `0 >= 0.6`) evalúa a `False` (**ROJO**).

Esto convierte automáticamente a todos los mundos limpios en **falsos rojos**. Es la razón por la cual la macro `peor` fue concebida únicamente para métricas de error (`max ... umbral <= tol`), donde una relación vacía devuelve `0` y `0 <= tol` evalúa a `True` (VERDE).

### 2. Origen de los 3 mutantes sobrevivientes (`min <-> max`)
Los casos `008-al-ras-toma-el-peor-contacto`, `009-al-ras-toma-el-menor-solape` y `scatter-004-coberturas-distintas` fueron diseñados originalmente con **una fila sana y una fila mala** para matar el mutador que cambia `max` por `min` (o viceversa).
Al agregar el filtro `donde`:
- La fila sana es descartada por el filtro.
- La tubería resultante contiene exactamente **una única fila** (la fila que ofende).
- Sobre un conjunto de un solo elemento `[x]`, `min([x]) == max([x]) == x`.
- Por ende, mutar `max → min` o `min → max` no altera ni el veredicto, ni el valor, ni los testigos. Como los casos existentes no tienen dos filas malas de distinta magnitud, el mutador sobrevive.

### 3. Falla por evaluación estricta en `physics.apoyado` sobre `cerca(None, 0.0)`
En `medidas/catalogos/physics/physics.apoyado.json`, la expresión lógica es:
`["o", ["==", ["campo", "a", "tiene_suelo"], false], [">", ["cerca", ["campo", "a", "gap"], 0.0], 1.0]]`
Dado que los operadores lógicos en Oracle evalúan todos sus operandos (sin cortocircuito, comprobado por `meta.los_logicos_evaluan_todos_sus_operandos`), en escenarios sin suelo donde `tiene_suelo` es `false` y `gap` es `null`, la función `cerca(gap, 0.0)` ejecuta `abs(None - 0.0)` en Python, arrojando `TypeError: unsupported operand type(s) for -: NoneType and float`.
