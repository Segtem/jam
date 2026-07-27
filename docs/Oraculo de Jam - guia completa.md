# El Oráculo de Jam — guía completa

> Documento de referencia para estudiar el sistema de verificación del plugin Jam (Unreal Engine 5.7).
> Contiene la tesis, la arquitectura, el código real de los doce oráculos, cómo se prueban, cómo se
> escribe uno nuevo, y el caso de estudio completo de la comparación contra TreeGen.
>
> Todo el código citado es código real del repositorio `~/Dev/jam`, no pseudocódigo.

---

## Índice

1. [Qué es un oráculo y por qué Jam existe](#1-qué-es-un-oráculo-y-por-qué-jam-existe)
2. [El principio arquitectónico: cerebro puro / adaptador](#2-el-principio-arquitectónico-cerebro-puro--adaptador)
3. [Anatomía canónica de un oráculo](#3-anatomía-canónica-de-un-oráculo)
4. [El núcleo geométrico compartido](#4-el-núcleo-geométrico-compartido)
5. [Los oráculos de escena](#5-los-oráculos-de-escena)
6. [El oráculo de pivote y anclas](#6-el-oráculo-de-pivote-y-anclas)
7. [El oráculo de continuidad de spline](#7-el-oráculo-de-continuidad-de-spline)
8. [El oráculo de espacio: winnability](#8-el-oráculo-de-espacio-winnability)
9. [El oráculo de forma: comparar contra una referencia](#9-el-oráculo-de-forma-comparar-contra-una-referencia)
10. [Los oráculos de contrato](#10-los-oráculos-de-contrato)
11. [El oráculo transaccional: Preview / Bake / Discard](#11-el-oráculo-transaccional-preview--bake--discard)
12. [Cómo se prueba un oráculo](#12-cómo-se-prueba-un-oráculo)
13. [Receta: escribir un oráculo nuevo](#13-receta-escribir-un-oráculo-nuevo)
14. [Tabla resumen de todos los oráculos](#14-tabla-resumen-de-todos-los-oráculos)
15. [Glosario](#15-glosario)
16. [Ejercicios](#16-ejercicios)

---

# 1. Qué es un oráculo y por qué Jam existe

## 1.1 La definición corta

Un **oráculo** es una función determinista que responde una pregunta verificable sobre un artefacto
producido, y devuelve un veredicto legible.

No genera nada. No corrige nada. **Mide y dictamina.**

```
artefacto  →  [oráculo]  →  veredicto
```

Esa asimetría es todo el punto: en Jam, quien *crea* y quien *verifica* están deliberadamente
separados. La creación puede venir de un LLM, de una herramienta procedural, de la mano del artista o
de un algoritmo. El oráculo no sabe ni le importa. Sólo mide el resultado.

## 1.2 El problema que resuelve

Las herramientas de asistencia in-editor (Dash es el referente explícito de Jam) hacen que sea muy
fácil colocar cosas. Ponés un objeto, esparcís cien, alineás una pared a un spline. Lo que **no** te
dicen es si el resultado está bien:

- ¿La pieza que acabás de colocar quedó clavada dentro de otra?
- ¿Los cien objetos esparcidos cayeron dentro de la región, o la mitad se fue afuera?
- ¿La pared sigue realmente la curva, o los segmentos se despegaron en las curvas cerradas?
- ¿El objeto que soltaste quedó apoyado, o levitando cinco centímetros?
- ¿El mapa que generaste se puede *terminar*, o la llave quedó detrás de la puerta que abre?

Todas esas preguntas tienen respuesta **determinista**. Ninguna requiere criterio artístico. Y todas
son exactamente el tipo de defecto que se cuela en producción porque a simple vista no se ve.

## 1.3 La tesis

> **Jam = un lenguaje para crear + un verificador determinista.**

La apuesta estratégica del proyecto está en la segunda mitad. La primera mitad —generar geometría,
esparcir, colocar— es replicable: hay competencia, hay herramientas mejores, y los LLMs mejoran solos.
La creación se delega a la mejor herramienta disponible en cada momento.

Lo que no se delega es la medición. El oráculo es:

- **el diferenciador de producto**: Dash coloca, Jam coloca *y te dice si quedó bien*;
- **la defensa anti-lock-in**: el oráculo razona sobre datos puros, no sobre objetos de Unreal, así
  que sobrevive a un cambio de motor;
- **la defensa anti-Goodhart**: no se le inyecta al generador lo que se va a medir. El generador crea
  libre; se mide desde afuera. Si le decís al generador cuál es la métrica, optimiza la métrica en vez
  del objetivo.

## 1.4 Las tres propiedades que un oráculo debe cumplir

**1. Determinista.** Mismo input, mismo veredicto, siempre. Sin aleatoriedad, sin dependencia del
orden de iteración, sin timestamps. Esto permite usarlo en tests de regresión.

**2. Puro cuando se puede.** El razonamiento no importa `unreal`. Se le pasan datos; devuelve datos.
Un adaptador separado se encarga de extraer esos datos del motor. Consecuencia práctica enorme: se
puede probar sin abrir el editor.

**3. Explicativo, no binario.** Un oráculo que devuelve `False` es inútil. Uno que devuelve
`"CLAVADO ✗ — solapa 12.4cm con «Muro_03» sobre x"` te dice qué arreglar. Todos los oráculos de Jam
tienen una función `verificar()` que devuelve el dict crudo y otra `*_texto()` que arma el veredicto
legible.

## 1.5 Dos familias de oráculo

Jam tiene dos familias claramente distintas, y conviene no confundirlas:

| Familia | Verifica | Cuándo corre | Ejemplos |
|---|---|---|---|
| **De escena** | el resultado *en el mundo* | después de ejecutar | placement, physics, snap, scatter, pared, reemplazo, forma |
| **De contrato** | que la operación *sea legal* | antes de ejecutar | Compile/Preflight, Flow.validar, check_unreal_api |

Los de escena responden «¿quedó bien?». Los de contrato responden «¿esto siquiera se puede correr?».
Los segundos son los que evitan efectos parciales: si el grafo no compila, no se toca la escena.

---

# 2. El principio arquitectónico: cerebro puro / adaptador

## 2.1 La regla

> El cerebro no importa `unreal`. Nunca.

Esta regla atraviesa todo el proyecto y es la razón de que los oráculos sean testeables. La estructura
es siempre:

```
┌─────────────────────────────────────────────────────────────┐
│  ADAPTADOR   jam/ue.py            import unreal  ✔          │
│  extrae datos del motor → tipos puros                       │
└───────────────────────────┬─────────────────────────────────┘
                            │  Pieza, AABB, Vec3  (namedtuples)
                            ▼
┌─────────────────────────────────────────────────────────────┐
│  CEREBRO     jam/geometry.py      import unreal  ✘          │
│              jam/oracle_*.py      import unreal  ✘          │
│  razona sobre datos puros → veredicto (dict + texto)        │
└─────────────────────────────────────────────────────────────┘
```

El docstring de `geometry.py` lo enuncia sin rodeos:

```python
"""Geometría pura de Jam — el CEREBRO sin Unreal.

AABBs como DATOS + la matemática del oráculo (penetración por regla del eje separador, escenografía
de fondo). **CERO `import unreal`**: corre en cualquier Python, testeable sin el editor, y sobrevive a
los cambios de motor (UE6/Scene Graph deprecan Actors). El adaptador `jam.ue` extrae estos datos del
motor; los oráculos razonan sobre estos datos. Esta es la línea de defensa anti-lock-in.
"""
```

## 2.2 La frontera exacta

El adaptador es minúsculo. Todo el contacto con Unreal para los oráculos de escena cabe en dos
funciones:

```python
# jam/ue.py  — ESTE archivo sí importa unreal

def pieza(actor) -> Pieza:
    """Pieza (dato puro) del actor: nombre + AABB + location (pivote) + yaw. Todo lo que un oráculo
    puede necesitar, extraído acá para que el cerebro no toque `unreal`."""
    loc = actor.get_actor_location()
    yaw = actor.get_actor_rotation().yaw
    return Pieza(actor.get_actor_label(), aabb(actor), Vec3(loc.x, loc.y, loc.z), yaw)


def piezas(actores) -> list:
    return [pieza(a) for a in actores]
```

Eso es todo. Un actor de Unreal —un objeto gordo, con cientos de propiedades, componentes, mundo,
transform jerárquico— se reduce a cuatro datos:

```python
Pieza = namedtuple("Pieza", "nombre aabb location yaw")
```

Un nombre, una caja, un pivote y un ángulo. Con eso los siete oráculos de escena hacen su trabajo.

## 2.3 Por qué esto importa tanto

**Testeabilidad.** Los tests de los oráculos construyen `Pieza` a mano y corren en milisegundos, sin
editor. La suite completa de Jam son 116 tests que corren en menos de un segundo.

**Supervivencia.** UE6 va hacia Verse + Scene Graph, que deprecan Actors y C++. Cuando eso pase, hay
que reescribir `ue.py` —dos funciones— y no una línea del cerebro.

**Portabilidad conceptual.** El mismo oráculo de interpenetración vale para Unreal, Godot, Blender o
un archivo JSON. La matemática de dos cajas clavadas no depende del motor.

## 2.4 El puente

Para quien ya tiene actores del editor a mano, `ue.py` ofrece puentes de conveniencia:

```python
# ---- puentes actor → oráculo puro (para callers que tienen actores del editor) ----

def placement(actor, otros) -> dict:
    from . import oracle_placement
    otras = piezas([o for o in otros if o != actor])
    ...
```

Nótese que el puente **no** contiene lógica: traduce y delega. Si aparece una decisión en el puente,
es una señal de que se está filtrando cerebro dentro del adaptador.

---

# 3. Anatomía canónica de un oráculo

Todos los oráculos de escena de Jam tienen exactamente la misma forma. Aprender una es aprender las
siete. La plantilla tiene **tres funciones**:

```python
def verificar(...) -> dict:   # 1. MIDE  → dict crudo con todos los números
def es_ok(r: dict) -> bool:   # 2. JUZGA → el veredicto binario, derivado del dict
def verificar_texto(...) -> str:  # 3. EXPLICA → el mensaje para el humano
```

## 3.1 El ejemplo completo más corto

`oracle_placement.py` entero, con su docstring:

```python
"""Oráculo de COLOCACIÓN — PURO (0 `import unreal`). Razona sobre `piezas` (nombre, AABB) de
`jam.geometry`; el adaptador `jam.ue` las extrae del nivel.

Dos preguntas deterministas sobre una pieza recién colocada:
  1. ¿Tiene bounds válidos? (una malla degenerada / vacía = colocación inútil).
  2. ¿Interpenetra otra pieza? (defecto clásico de kitbash: dos módulos clavados uno en otro).

La profundidad de interpenetración = mínimo, sobre los 3 ejes, de la superposición (eje separador),
con tolerancia para que "tocarse" no cuente como clavarse. La escenografía de fondo se ignora.
"""

from __future__ import annotations

from . import geometry

_TOL_CM = geometry.TOL_CM


def verificar(pieza, otras, tol: float = geometry.TOL_CM) -> dict:
    """Veredicto de colocación de `pieza` (geometry.Pieza) frente a `otras` (lista de Pieza, que NO
    debe incluir a la propia; el fondo se ignora)."""
    a = pieza.aabb
    bounds_ok = geometry.volumen(a) > 1e-3
    choques = []
    for o in otras:
        if geometry.es_fondo(o.aabb):
            continue
        d = geometry.penetracion(a, o.aabb, tol)
        if d > 0.0:
            choques.append((o.nombre, round(d, 1)))
    e = a.extent
    return {
        "bounds_ok": bounds_ok,
        "extent": (round(e.x, 1), round(e.y, 1), round(e.z, 1)),
        "interpenetra": choques,
    }


def es_ok(r: dict) -> bool:
    return bool(r["bounds_ok"]) and not r["interpenetra"]


def verificar_texto(pieza, otras, tol: float = geometry.TOL_CM) -> str:
    nombre = pieza.nombre
    r = verificar(pieza, otras, tol)
    if not r["bounds_ok"]:
        return f"[{nombre}] COLOCACIÓN INVÁLIDA ✗ — bounds degenerados {r['extent']}"
    if r["interpenetra"]:
        detalle = ", ".join(f"{n} ({d}cm)" for n, d in r["interpenetra"])
        return f"[{nombre}] INTERPENETRA ✗ — clavado en: {detalle}"
    return f"[{nombre}] COLOCADO LIMPIO ✓ — extent {r['extent']}cm, sin interpenetrar"
```

52 líneas. Cero dependencias fuera de `geometry`. Corre en cualquier Python 3.

## 3.2 Por qué tres funciones y no una

**`verificar()` devuelve el dict crudo** con *todos* los números medidos, incluso los que pasan. Eso
permite:
- que otro oráculo lo reuse (scatter reusa la penetración de placement);
- que un test afirme sobre un número concreto, no sobre un booleano;
- que la UI pinte gradientes en vez de rojo/verde.

**`es_ok()` centraliza la regla de aprobación.** Si mañana «tocarse» pasa a contar como defecto, se
cambia en un lugar. Y como es una función y no un campo del dict, se puede aplicar a un dict que vino
serializado de otro proceso.

**`verificar_texto()` es la interfaz humana.** Nótese el patrón de los mensajes: siempre
`[sujeto] VEREDICTO ✓/✗ — evidencia numérica`. No dice «hay un problema»; dice *qué* problema, *con
quién*, y *cuántos centímetros*.

## 3.3 El formato del veredicto

La convención de texto es rígida a propósito:

```
[Barril_02] APOYADO ✓ — asentado sobre «Piso_01» (gap 0.3cm)
[Barril_02] FLOTANDO ✗ — 12.7cm de aire sobre «Piso_01»
[Barril_02] SIN SUELO ✗ — no hay soporte debajo (caería al vacío)
```

Tres partes:
1. **`[sujeto]`** — qué pieza se está juzgando, entre corchetes.
2. **`VEREDICTO ✓/✗`** — en mayúsculas, con el símbolo. Escaneable de un vistazo en un log largo.
3. **`— evidencia`** — el número que justifica el veredicto y el otro actor involucrado, entre comillas
   angulares.

Esto no es cosmético: cuando un grafo de 30 nodos escupe 30 líneas, la columna de ✓/✗ se lee vertical
y el ojo va directo al ✗.

---

# 4. El núcleo geométrico compartido

`jam/geometry.py` es el módulo del que dependen casi todos los oráculos de escena. Son ~60 líneas de
matemática pura. Vale la pena leerlo entero porque cada función encapsula una decisión de diseño.

## 4.1 Los tipos

```python
from collections import namedtuple

Vec3 = namedtuple("Vec3", "x y z")
AABB = namedtuple("AABB", "origin extent")   # origin, extent: Vec3, en cm (extent = semi-extensión)
Pieza = namedtuple("Pieza", "nombre aabb location yaw")

TOL_CM = 1.0                # menos que esto = tocándose, no interpenetrando
MAX_VECINO_CM = 50000.0     # semi-extensión > 500 m en un eje = escenografía de fondo
```

Puntos clave:

- **`namedtuple` y no clases.** Inmutables, comparables, imprimibles, serializables, y sin métodos que
  tienten a meter lógica adentro del dato.
- **`extent` es SEMI-extensión.** Es la convención de Unreal (`BoxExtent`). Una caja de 200cm de ancho
  tiene `extent.x == 100`. Confundir esto es el error número uno al escribir un oráculo nuevo.
- **Todo en centímetros.** La unidad de Unreal. No hay conversiones escondidas.
- **`location` ≠ `aabb.origin`.** `location` es el **pivote** del actor; `aabb.origin` es el **centro
  de la caja**. Casi nunca coinciden, y esa diferencia es justamente lo que mide el oráculo de pivote
  (sección 6).

## 4.2 Penetración por regla del eje separador

La función más reusada del proyecto:

```python
def penetracion(a: AABB, b: AABB, tol: float = TOL_CM) -> float:
    """Profundidad de interpenetración en cm entre dos AABB; 0.0 si están separados (eje separador)."""
    solapes = []
    for ca, ea, cb, eb in (
        (a.origin.x, a.extent.x, b.origin.x, b.extent.x),
        (a.origin.y, a.extent.y, b.origin.y, b.extent.y),
        (a.origin.z, a.extent.z, b.origin.z, b.extent.z),
    ):
        solape = (ea + eb) - abs(ca - cb)
        if solape <= tol:
            return 0.0
        solapes.append(solape)
    return min(solapes)
```

**Cómo funciona.** Para cada eje se calcula cuánto se superponen las dos cajas:

```
solape = (semi_a + semi_b) - distancia_entre_centros
```

- Si el solape en **cualquier** eje es ≤ tolerancia, existe un *eje separador*: las cajas no se tocan,
  y se devuelve `0.0` de inmediato (cortocircuito, sin calcular los otros ejes).
- Si los tres ejes se superponen, las cajas están clavadas. La **profundidad** es el **mínimo** de los
  tres solapes: es la distancia más corta que habría que mover una caja para separarlas.

**Por qué el mínimo y no el máximo.** Imaginá dos cajas que se solapan 50cm en X, 3cm en Y y 40cm en
Z. Están *apenas* tocándose por la cara Y. Moviéndolas 3cm en Y se separan. Reportar 50cm sería
alarmista y no diría dónde está el problema real.

**Por qué la tolerancia.** Dos módulos de kit apoyados uno contra otro comparten cara exactamente. En
punto flotante eso da un solape de 0.0000001cm. Sin tolerancia, todo kit modular bien armado daría
«CLAVADO ✗». `TOL_CM = 1.0` significa: hasta un centímetro es *tocarse*, no *clavarse*.

## 4.3 Escenografía de fondo

```python
def es_fondo(a: AABB, max_cm: float = MAX_VECINO_CM) -> bool:
    """True si el AABB es escenografía de fondo (descomunal: SkySphere, atmósfera). La
    interpenetración sólo tiene sentido entre piezas de escala comparable."""
    e = a.extent
    return max(e.x, e.y, e.z) > max_cm
```

Sin este filtro, el oráculo de colocación reportaría que **todo** interpenetra con la SkySphere, con
la niebla atmosférica y con el volumen de post-proceso, porque esos actores envuelven el mapa entero.

Es un ejemplo de una lección general: **un oráculo ingenuo produce ruido, y el ruido es peor que el
silencio**. Un veredicto que grita siempre se ignora siempre. Buena parte del trabajo de afinar un
oráculo consiste en excluir los casos que técnicamente cumplen la condición pero no son el defecto que
se busca.

En `tools.py` hay una versión más agresiva del mismo problema, con su comentario:

```python
def es_terreno_o_proxy(a) -> bool:
    """Landscape y HLOD no son «vecinos»: el landscape es el suelo (ya lo mide el apoyo) y los
    HLOD de World Partition son COPIAS de baja resolución de lo que ya está en el nivel —
    contarlos daba «CLAVA ✗» contra todo en cualquier mapa de mundo abierto."""
```

## 4.4 Búsqueda de soporte

```python
def soporte_top(a: AABB, soportes, tol: float = TOL_CM):
    """Top del AABB del soporte más alto que solapa a `a` en XY y no asoma por encima de su centro.
    `soportes` = lista de Pieza (que NO debe incluir a la propia). Devuelve (z_top, nombre) o (None, None)."""
    mejor = None
    for s in soportes:
        os_, es = s.aabb.origin, s.aabb.extent
        if abs(os_.x - a.origin.x) > (es.x + a.extent.x) or abs(os_.y - a.origin.y) > (es.y + a.extent.y):
            continue  # no solapa en XY → no es soporte
        s_top = os_.z + es.z
        if s_top > a.origin.z + tol:
            continue  # el soporte asoma por encima del centro → no está "debajo"
        if mejor is None or s_top > mejor[0]:
            mejor = (s_top, s.nombre)
    return mejor if mejor else (None, None)
```

Dos filtros y un máximo:

1. **Solape en XY.** Si la caja candidata no está debajo en planta, no puede sostener nada.
2. **No asoma por encima del centro.** Una pared que atraviesa la pieza solapa en XY, pero no es un
   *soporte*: es un obstáculo. El criterio «su tope no puede estar por encima del centro de la pieza»
   la descarta.
3. **El más alto gana.** Si hay piso, mesa y plato apilados, el soporte es el plato.

Esta función es la base del oráculo de física (sección 5.2).

---
# 5. Los oráculos de escena

Siete oráculos, uno por cada capacidad de Jam. Cada uno nació emparejado con una herramienta: la
herramienta hace, el oráculo verifica. Esa simetría es deliberada — **no se agrega una capacidad sin
su oráculo**.

| Herramienta | Oráculo | Pregunta central |
|---|---|---|
| `place` | `oracle_placement` | ¿quedó sin clavarse? |
| `drop` (física) | `oracle_physics` | ¿quedó apoyado? |
| `snap` | `oracle_snap` | ¿quedó en grilla / al ras? |
| `scatter` | `oracle_scatter` | ¿el reparto es sano? |
| `spline` / `pared` | `oracle_pared` | ¿la pared sigue la curva? |
| `replace` | `oracle_reemplazo` | ¿se preservó el footprint? |
| (mapa) | `oracle_espacio` | ¿el mapa se puede terminar? |

## 5.1 Colocación — `oracle_placement`

Ya lo vimos entero en la sección 3.1. Lo que importa retener:

- Es el oráculo **base**: `oracle_scatter` y `oracle_physics` reusan su matemática.
- Mide dos cosas: bounds degenerados e interpenetración.
- El caso «bounds degenerados» captura un fallo silencioso real: colocar un asset cuya malla no cargó
  produce un actor con caja de volumen cero. Visualmente no hay nada; el Outliner dice que sí. El
  oráculo lo caza.

### El uso real, con todos los filtros

En producción, el oráculo puro se envuelve con la lógica de qué cuenta como vecino. Este es el código
real que corre después de un `place`:

```python
def _veredicto_entorno(actor) -> str:
    """Oráculo de PLACE: ¿el ladrillo quedó bien en su entorno? APOYADO sobre superficie (raycast,
    gap≈0, con su pendiente) + SIN CLAVARSE con vecinos reales (excluye soporte, landscape y no-geometría)."""
    import unreal as U
    from . import geometry, oracle_placement, physics, ue
    aabb = ue.aabb(actor)
    base_z = aabb.origin.z - aabb.extent.z

    # 1) superficie debajo (raycast desde la base, ignorando el propio actor)
    hit = ue.raycast(aabb.origin.x, aabb.origin.y, desde=base_z + 20.0, ignorar=[actor])
    soporte = hit["actor"] if hit["hit"] else None
    if not hit["hit"]:
        apoyo = "SIN SUELO ✗ — flota (no hay superficie debajo)"
    else:
        gap = base_z - hit["punto"].z
        pend = 90.0 - _grados_normal(hit["normal"])
        apoyo = (f"APOYADO ✓ sobre «{soporte}» (pendiente {pend:.0f}°)" if abs(gap) <= 5.0
                 else f"MAL APOYADO ✗ — {gap:+.1f}cm de «{soporte}»")

    # 2) vecinos = geometría real, sin el propio, sin el soporte, sin terreno ni proxies
    vecinos = [a for a in ue.actores_nivel()
               if a != actor and physics._es_geometria(a) and not es_terreno_o_proxy(a)
               and ghost.TAG not in ue.tags(a)   # el fantasma está justo donde colocás: no es vecino
               and a.get_actor_label() != soporte]
    r = oracle_placement.verificar(ue.pieza(actor), ue.piezas(vecinos))
    if r["interpenetra"]:
        det = ", ".join(f"{n} ({d}cm)" for n, d in r["interpenetra"])
        clava = f"CLAVA ✗ con {det}"
    else:
        clava = "sin clavarse con vecinos ✓"

    ok = hit["hit"] and (soporte is None or abs(base_z - hit["punto"].z) <= 5.0) and not r["interpenetra"]
    cab = f"[{actor.get_actor_label()}] {'BIEN COLOCADO ✓' if ok else 'REVISAR ✗'}"
    return f"{cab} — {apoyo} · {clava}\n{_donde(actor)}"
```

**Lección pedagógica.** Contá las exclusiones de la lista `vecinos`: el propio actor, lo que no es
geometría, terreno y proxies HLOD, el fantasma de previsualización, y el soporte. **Cinco filtros**.
Cada uno se agregó porque sin él el oráculo daba un falso positivo en un caso real.

Un oráculo maduro es 20% matemática y 80% saber qué no contar.

## 5.2 Física — `oracle_physics`

```python
"""Oráculo de PHYSICS (drop) — Dash suelta; Jam verifica que quedó asentado.

Tras soltar un actor, cuatro estados deterministas por AABB frente al soporte de abajo:
  - APOYADO:  la base del actor coincide (±tol) con el top del soporte  → sano.
  - FLOTANDO: hay aire bajo la base (quedó levitando)                   → defecto.
  - HUNDIDO:  la base quedó por debajo del top del soporte (clavado)    → defecto.
  - SIN_SUELO: no hay soporte debajo (caería al vacío)                  → defecto.
"""

def verificar(pieza, soportes, *, tol: float = geometry.TOL_CM) -> dict:
    a = pieza.aabb
    base = a.origin.z - a.extent.z
    z_top, label = geometry.soporte_top(a, soportes, tol)
    if z_top is None:
        return {"estado": "sin_suelo", "gap": None, "soporte": None, "apoyado": False}
    gap = base - z_top
    if abs(gap) <= tol:
        estado = "apoyado"
    elif gap > 0:
        estado = "flotando"
    else:
        estado = "hundido"
    return {"estado": estado, "gap": round(gap, 1), "soporte": label, "apoyado": estado == "apoyado"}
```

**El patrón de la máquina de estados.** En vez de devolver un booleano, devuelve uno de cuatro estados
nombrados. Un solo número —`gap = base - z_top`— produce tres estados según su signo:

```
gap > tol    →  flotando   (hay aire)
|gap| ≤ tol  →  apoyado    (coinciden)
gap < -tol   →  hundido    (se metió adentro)
```

y el cuarto estado (`sin_suelo`) es la ausencia de soporte.

Esto es mucho más útil que `apoyado: bool`, porque *flotando* y *hundido* tienen causas y arreglos
distintos: flotando suele ser un pivote mal puesto; hundido suele ser una malla con colisión
incorrecta.

```python
def verificar_texto(pieza, soportes, *, tol: float = geometry.TOL_CM) -> str:
    r = verificar(pieza, soportes, tol=tol)
    label = pieza.nombre
    if r["estado"] == "sin_suelo":
        return f"[{label}] SIN SUELO ✗ — no hay soporte debajo (caería al vacío)"
    if r["estado"] == "flotando":
        return f"[{label}] FLOTANDO ✗ — {r['gap']}cm de aire sobre «{r['soporte']}»"
    if r["estado"] == "hundido":
        return f"[{label}] HUNDIDO ✗ — {abs(r['gap'])}cm clavado en «{r['soporte']}»"
    return f"[{label}] APOYADO ✓ — asentado sobre «{r['soporte']}» (gap {r['gap']}cm)"
```

## 5.3 Snap — `oracle_snap`

Dos verificaciones independientes: estar en grilla y estar al ras.

```python
"""Oráculo de SNAP / ALINEACIÓN — PURO (0 unreal). Dash cuadra; Jam verifica que quedó alineado.

Dos preguntas deterministas sobre `piezas` (geometry.Pieza):
  - EN GRILLA: ¿el pivote (pieza.location) cae en múltiplos de la grilla (±tol) y el yaw en su paso?
  - AL RAS:    ¿la cara de la pieza toca la de `objetivo` sobre un eje (gap ±tol) compartiendo las
               otras dos (adyacente, no diagonal), sin clavarse ni dejar hueco?
"""

def _mult_cercano(v: float, paso: float, tol: float) -> bool:
    return abs(v - round(v / paso) * paso) <= tol


def verificar_grilla(pieza, grilla: float = 100.0, *, paso_yaw: float = 90.0,
                     tol: float = geometry.TOL_CM, tol_yaw: float = 0.5) -> dict:
    """¿El pivote de la pieza está en la grilla y el yaw en su paso?"""
    loc = pieza.location
    ejes_ok = {e: _mult_cercano(getattr(loc, e), grilla, tol) for e in ("x", "y", "z")}
    yaw = pieza.yaw
    yaw_ok = _mult_cercano(yaw, paso_yaw, tol_yaw)
    en_grilla = all(ejes_ok.values()) and yaw_ok
    return {"en_grilla": en_grilla, "ejes_ok": ejes_ok, "yaw": round(yaw, 1), "yaw_ok": yaw_ok}
```

`_mult_cercano` es el truco: `round(v / paso) * paso` da el múltiplo más cercano; la distancia a ese
múltiplo se compara con la tolerancia. Sirve igual para posiciones (grilla de 100cm) que para
rotaciones (paso de 90°).

Nótese que `ejes_ok` es un **dict por eje**, no un booleano. Eso permite que el mensaje diga *cuál*
eje está fuera:

```python
def texto_grilla(pieza, grilla: float = 100.0, **kw) -> str:
    r = verificar_grilla(pieza, grilla, **kw)
    label = pieza.nombre
    if r["en_grilla"]:
        return f"[{label}] EN GRILLA ✓ — pivote en múltiplos de {int(grilla)}cm, yaw {r['yaw']}°"
    faltan = [e for e, ok in r["ejes_ok"].items() if not ok]
    detalle = f"ejes fuera: {','.join(faltan)}" if faltan else ""
    if not r["yaw_ok"]:
        detalle = (detalle + "; " if detalle else "") + f"yaw {r['yaw']}° fuera de paso"
    return f"[{label}] FUERA DE GRILLA ✗ — {detalle}"
```

### Al ras: cuatro estados

```python
def verificar_ras(pieza, objetivo, eje: str = "x", *, tol: float = geometry.TOL_CM) -> dict:
    """¿`pieza` quedó al ras contra `objetivo` sobre `eje`? Devuelve estado + gap del eje."""
    i = _EJES[eje]
    ca, va = _comps(pieza.aabb.origin), _comps(pieza.aabb.extent)
    cb, vb = _comps(objetivo.aabb.origin), _comps(objetivo.aabb.extent)
    gap = abs(ca[i] - cb[i]) - (va[i] + vb[i])            # >0 hueco, ~0 al ras, <0 solapado
    otros_solapan = all((va[j] + vb[j]) - abs(ca[j] - cb[j]) > tol for j in range(3) if j != i)
    if not otros_solapan:
        estado = "desalineado"      # no comparten cara (diagonal / separados en otro eje)
    elif abs(gap) <= tol:
        estado = "al_ras"
    elif gap > 0:
        estado = "hueco"
    else:
        estado = "clavado"
    return {"estado": estado, "gap": round(gap, 1), "eje": eje, "al_ras": estado == "al_ras"}
```

**La sutileza importante**: `otros_solapan`. Dos cajas pueden tener `gap ≈ 0` en X y sin embargo estar
en diagonal, sin compartir cara. La condición «los *otros dos* ejes deben solaparse» distingue
*adyacente* de *diagonal*. Sin ella, dos piezas separadas en Y darían «AL RAS ✓» falsamente.

Es el mismo razonamiento del eje separador, pero al revés: acá se *exige* solape en dos ejes y
*coincidencia* en el tercero.

## 5.4 Scatter — `oracle_scatter`

El primer oráculo que verifica un **conjunto**, no una pieza. Cuatro preguntas:

```python
"""Oráculo de SCATTER — Dash esparce; Jam verifica que el reparto sea sano.

Cuatro preguntas deterministas sobre un conjunto de instancias esparcidas:
  1. ¿Cantidad?  — ¿se colocaron las que se pidieron? (una región saturada deja faltantes).
  2. ¿Contención? — ¿el centro de cada instancia cae dentro de la región objetivo?
  3. ¿Sin interpenetrar? — ¿ningún par de instancias está clavado? (reusa el AABB de colocación).
  4. ¿Cobertura? — ¿el reparto cubre la región o quedó amontonado?
     (fracción de celdas de una grilla NxN sobre la región que contienen ≥1 instancia).

Reusa `jam.oracle_placement` para el AABB y la profundidad de interpenetración — una sola fuente
de verdad para "dos piezas clavadas".
"""
```

### La medida de cobertura

Esta es la parte conceptualmente más rica:

```python
    celdas = set()
    if sx > 0 and sy > 0:
        for p in piezas:
            x, y = _centro_xy(p)
            gx = min(grilla - 1, max(0, int((x - (cx - sx)) / (2 * sx) * grilla)))
            gy = min(grilla - 1, max(0, int((y - (cy - sy)) / (2 * sy) * grilla)))
            celdas.add((gx, gy))
    cobertura = len(celdas) / (grilla * grilla) if grilla else 0.0
```

Se divide la región en una grilla NxN (por defecto 3×3 = 9 celdas) y se cuenta **cuántas celdas
contienen al menos una instancia**. La cobertura es esa fracción.

**Por qué esto y no la varianza o la distancia media al vecino.** Porque responde exactamente a la
pregunta que importa: *«¿quedó todo amontonado en una esquina?»*. Cien objetos perfectamente
distribuidos en la esquina superior izquierda tienen varianza baja y buena distancia entre vecinos,
pero cobertura 1/9 = 11%. El oráculo lo caza.

Es un ejemplo de **elegir la métrica por la pregunta, no por elegancia matemática**.

### La comparación de pares es O(n²)

```python
    choques = []
    for i in range(len(piezas)):
        for j in range(i + 1, len(piezas)):
            d = geometry.penetracion(piezas[i].aabb, piezas[j].aabb, tol)
            if d > 0.0:
                choques.append((piezas[i].nombre, piezas[j].nombre, round(d, 1)))
```

Para 200 instancias son 19.900 comparaciones de AABB — trivial. Para 20.000 serían 200 millones, y
haría falta una grilla espacial. Es una limitación conocida y aceptada: el scatter de Jam trabaja en
ese orden de magnitud.

### El texto agregado

Cuando hay muchos defectos, el oráculo **resume en vez de inundar**:

```python
    if r["interpenetra"]:
        muestra = "; ".join(f"{a}×{b} ({d}cm)" for a, b, d in r["interpenetra"][:4])
        extra = "" if len(r["interpenetra"]) <= 4 else f" (+{len(r['interpenetra']) - 4} más)"
        lineas.append(f"  ✗ interpenetran {len(r['interpenetra'])} pares: {muestra}{extra}")
```

Muestra los primeros cuatro y cuenta el resto. Un veredicto de 500 líneas no se lee.

Salida típica:

```
SCATTER · 47/50 instancias · cobertura 78%
  ✗ cantidad: faltan 3 (región saturada)
  ✗ interpenetran 6 pares: Roca_04×Roca_11 (8.2cm); Roca_07×Roca_23 (3.1cm) (+4 más)
```

## 5.5 Pared por spline — `oracle_pared`

El oráculo más geométricamente interesante, porque no puede usar AABB.

```python
"""Oráculo de PARED por spline — Dash reparte a lo largo de la curva; Jam verifica que la pared sea
continua y siga el spline.

Los segmentos van GIRADOS según la tangente, así que el AABB del resto del kit no aplica a sus caras.
El oráculo razona sobre las JUNTAS: el extremo delantero del segmento i y el trasero del i+1 deberían
caer sobre el punto del spline en esa junta. Si los segmentos son muy largos para lo que curva el
spline, se despegan (kink) → discontinua.

  - COBERTURA: ¿la pared cubre el largo del spline? (n·paso ≈ largo).
  - CONTINUA:  ¿cada junta queda a ≤tol del punto del spline? (máx de las desviaciones).
"""
```

**El problema.** Un AABB es *axis-aligned*: alineado a los ejes del mundo. Una pared que sigue una
curva tiene segmentos rotados en todos los ángulos. El AABB de un segmento rotado 45° es una caja
mucho más grande que el segmento, y sus caras no coinciden con las caras reales. Toda la matemática de
las secciones anteriores es inaplicable.

**La solución.** No mirar las cajas: mirar las **juntas**. Cada segmento tiene un centro y un vector
*forward* (su tangente). El extremo delantero del segmento *i* se calcula analíticamente:

```python
    def extremo(i, signo):
        cx, cy = centros[i]
        fx, fy = forwards[i]
        return (cx + signo * (paso / 2.0) * fx, cy + signo * (paso / 2.0) * fy)
```

Y se compara con dónde *debería* estar según la curva:

```python
    max_gap = 0.0
    juntas = []
    for i in range(min(n - 1, len(puntos))):
        fin_i = extremo(i, +1)
        ini_j = extremo(i + 1, -1)
        px, py = puntos[i]
        g = max(math.dist(fin_i, (px, py)), math.dist(ini_j, (px, py)))
        max_gap = max(max_gap, g)
        juntas.append(round(g, 1))

    continua = (n <= 1) or (max_gap <= tol)
    largo_real = n * paso
    cobertura_ok = abs(largo_real - build["largo_spline"]) <= tol
```

Para cada junta se toman **dos** distancias —la del extremo del segmento saliente y la del extremo del
entrante, ambas contra el punto de la curva— y se queda con la peor. El veredicto usa el **máximo**
sobre todas las juntas: una sola junta despegada arruina la pared.

**Qué defecto real caza.** Piezas de 400cm sobre una curva cerrada: cada segmento es una cuerda de un
arco, y en el medio de la curva los extremos se despegan hacia afuera. Visualmente es un «kink», una
pared que hace esquinas donde debería curvar. El oráculo lo reporta con el número exacto de
centímetros de despegue.

```
PARED · 12 segmentos · 4800.0cm sobre spline de 4790.0cm
  ✗ discontinua: junta despegada 87.3cm del spline (segmentos muy largos para la curva)
```

**Detalle de diseño**: el oráculo recibe `build: dict` —los datos que produjo el constructor— y no
actores. Es puro sobre el *plan*, no sobre el resultado. Eso permite verificar **antes** de construir.

## 5.6 Reemplazo — `oracle_reemplazo`

El oráculo del flujo blockout → arte final.

```python
"""Oráculo de REEMPLAZO — Dash cambia la malla; Jam verifica que el footprint se preservó.

Tres preguntas deterministas sobre el asset que reemplazó a un blockout, contra el `objetivo`
(footprint capturado del blockout antes de borrarlo):
  - CENTRADO: ¿el centro XY del nuevo AABB calza con el del blockout (±tol)?
  - APOYADO:  ¿la base (z_min) coincide (±tol)? (no quedó flotando ni hundido al vestir).
  - FOOTPRINT: ¿el ancho×largo del AABB calza (±tol_fp)? (no se angostó ni ensanchó el hueco).

PRESERVA = las tres.
"""

def verificar(pieza, objetivo: dict, *, tol: float = geometry.TOL_CM, tol_fp: float = 2.0) -> dict:
    on, en = pieza.aabb.origin, pieza.aabb.extent
    dcx = on.x - objetivo["cx"]
    dcy = on.y - objetivo["cy"]
    dbase = (on.z - en.z) - objetivo["base"]
    dfx = en.x - objetivo["ex"]
    dfy = en.y - objetivo["ey"]
    centrado = abs(dcx) <= tol and abs(dcy) <= tol
    apoyado = abs(dbase) <= tol
    footprint = abs(dfx) <= tol_fp and abs(dfy) <= tol_fp
    return {
        "preserva": centrado and apoyado and footprint,
        "centrado": centrado, "apoyado": apoyado, "footprint": footprint,
        "d_centro": (round(dcx, 1), round(dcy, 1)),
        "d_base": round(dbase, 1),
        "d_footprint": (round(dfx, 1), round(dfy, 1)),
    }
```

**El concepto clave: capturar antes de destruir.** El `objetivo` es un dict con el footprint del
blockout, tomado *antes* de borrarlo. El oráculo compara el reemplazo contra esa foto.

**Dos tolerancias distintas.** `tol` (1cm) para posición y `tol_fp` (2cm) para tamaño. El tamaño
admite más error porque un asset artístico nunca mide exactamente lo mismo que la caja gris que
reemplaza; lo que no se admite es que se corra de lugar.

**Por qué importa.** En un nivel armado con blockouts, cada caja gris define un hueco en la
composición: un pasillo pasa por al lado, una puerta encaja, el jugador cabe. Si al vestir el nivel el
asset final es 30cm más ancho, el pasillo deja de funcionar. Ese defecto se descubre semanas después,
jugando. El oráculo lo dice en el momento.

```
[Casa_03] FOOTPRINT ROTO ✗ — descentrado (12.0, 3.0)cm; planta cambió (28.0, 5.0)cm (angosta/ensancha el hueco)
```

---
# 6. El oráculo de pivote y anclas

Este oráculo no juzga una colocación: juzga un **asset**. Es un oráculo *aguas arriba* — detecta un
defecto en la materia prima antes de que contamine todo lo que se construya con ella.

## 6.1 El problema

El pivote de una malla es su origen local: el punto por el que Unreal la agarra. Cuando un asset viene
con el pivote en un lugar arbitrario —el centro de masa, una esquina al azar, o directamente fuera de
la malla— todo lo que se construya con él hereda ese error.

Un censo real sobre la biblioteca del proyecto encontró **96 de 120 mallas con el pivote fuera de
donde debería estar**. Eso significa que colocar «en el piso» no pone la pieza en el piso, sino su
pivote, y la pieza queda flotando o hundida a una altura impredecible por asset.

## 6.2 La medición: coordenadas normalizadas

```python
def diagnostico(aabb: AABB, location: Vec3 | None = None) -> dict:
    """Dónde está el pivote DENTRO de su propia caja, normalizado 0..1 por eje (0=min, 1=max).
    Devuelve {u: (ux,uy,uz), fuera: bool, en_base: bool, centrado_planta: bool, tileable: bool}."""
    loc = location or Vec3(0.0, 0.0, 0.0)
    u = []
    for c, e, p in ((aabb.origin.x, aabb.extent.x, loc.x),
                    (aabb.origin.y, aabb.extent.y, loc.y),
                    (aabb.origin.z, aabb.extent.z, loc.z)):
        lado = 2.0 * e
        u.append(0.5 if lado <= 1e-6 else (p - (c - e)) / lado)
    ux, uy, uz = u
    fuera = any(v < -TOL_REL or v > 1.0 + TOL_REL for v in u)
    en_base = abs(uz) <= TOL_REL
    centrado_planta = abs(ux - 0.5) <= TOL_REL and abs(uy - 0.5) <= TOL_REL
    en_esquina = abs(ux) <= TOL_REL and abs(uy) <= TOL_REL
    return {"u": (ux, uy, uz), "fuera": fuera, "en_base": en_base,
            "centrado_planta": centrado_planta, "en_esquina": en_esquina,
            # tileable = se puede repetir sin recalcular: pivote en la base y en planta previsible
            "tileable": (not fuera) and en_base and (centrado_planta or en_esquina)}
```

**La idea central: normalizar.** La posición del pivote se expresa como fracción del tamaño de la caja
en cada eje:

```
u = (pivote - min_caja) / lado_caja
```

- `u = 0.0` → el pivote está en la cara mínima de ese eje
- `u = 0.5` → en el centro
- `u = 1.0` → en la cara máxima
- `u < 0` o `u > 1` → **fuera de la propia malla**

La normalización hace la métrica **independiente de la escala**. Un barril de 80cm y una torre de 20m
con el pivote en la base dan ambos `uz = 0.0`. Se pueden comparar assets de cualquier tamaño con el
mismo criterio.

## 6.3 El concepto derivado: `tileable`

```python
"tileable": (not fuera) and en_base and (centrado_planta or en_esquina)
```

Un asset es **tileable** —repetible sin corrección— si cumple tres condiciones:

1. el pivote está **dentro** de la malla;
2. está en la **base** (`uz ≈ 0`), así apoya solo;
3. en planta está **en el centro o en una esquina** — las dos únicas posiciones desde las que se puede
   predecir dónde caerá la pieza siguiente.

Un pivote en `(0.37, 0.81)` en planta no es ni centro ni esquina: para tilear con él hay que calcular
un offset distinto por asset. Eso es exactamente lo que rompe los kits modulares.

Esto es un buen ejemplo de un oráculo que **define un concepto de dominio**. «Tileable» no es una
propiedad que Unreal exponga; es una noción de arte técnico que el oráculo formaliza en tres
condiciones verificables.

## 6.4 El veredicto, en lenguaje de artista

```python
def diagnostico_texto(nombre: str, aabb: AABB, location: Vec3 | None = None) -> str:
    """Veredicto del pivote: dónde está y si el asset se va a portar bien al repetirlo."""
    d = diagnostico(aabb, location)
    ux, uy, uz = d["u"]
    med = (f"{aabb.extent.x * 2:.0f}×{aabb.extent.y * 2:.0f}×{aabb.extent.z * 2:.0f}cm")
    if d["fuera"]:
        donde = f"FUERA de la malla ✗ (x {ux * 100:.0f}%, y {uy * 100:.0f}%, z {uz * 100:.0f}%)"
    elif d["centrado_planta"]:
        donde = f"centrado en planta, {_altura(uz)}"
    elif d["en_esquina"]:
        donde = f"en una esquina de la planta, {_altura(uz)}"
    else:
        donde = f"descentrado (x {ux * 100:.0f}%, y {uy * 100:.0f}%), {_altura(uz)}"

    if d["tileable"]:
        cierre = "SIRVE PARA REPETIR ✓ — apoya solo y se puede tilear sin corregir"
    else:
        cierre = ("REQUIERE ANCLA ✗ — colocalo con «anchor=base» (o corner/xmin…) para que caiga "
                  ...)
```

Y la altura se traduce a lenguaje natural:

```python
def _altura(uz: float) -> str:
    if abs(uz) <= TOL_REL:
        return "en la BASE"
    if abs(uz - 1.0) <= TOL_REL:
        return "arriba de todo"
    if abs(uz - 0.5) <= TOL_REL:
        return "a media altura"
    return f"a {uz * 100:.0f}% de la altura"
```

Salida real (capturada de una corrida del editor):

```
[PineFrond] pivote descentrado (x 42%, y 96%), a 83% de la altura · caja 132×162×73cm
    REQUIERE ANCLA ✗ — colocalo con «anchor=base» (o corner/xmin…) para que caiga donde querés,
    en vez de por su pivote
    → «normalize» lo arregla de una vez para todas las herramientas
```

**Tres cosas que hace bien este mensaje:**

1. **Traduce los números a palabras.** «a 83% de la altura» en vez de `uz=0.83`.
2. **Da la salida táctica**: usá `anchor=base` ahora.
3. **Da la salida estratégica**: `normalize` lo arregla para siempre.

Un oráculo que sólo dice qué está mal genera frustración. Uno que dice cómo salir genera adopción.

---

# 7. El oráculo de continuidad de spline

Verifica que las piezas colocadas a lo largo de una curva la **tileen** correctamente.

```python
def verificar_continuidad(colocaciones, largo_curva, *, tol=1.0):
    """Oráculo del spline: ¿las piezas TILEAN la curva? Que ninguna se solape con la siguiente (juntas
    limpias) y que la cobertura sea alta (no quedó media curva vacía). Puro."""
    n = len(colocaciones)
    solapes = []
    for i in range(n - 1):
        a, b = colocaciones[i], colocaciones[i + 1]
        fin_a = a.s + a.largo / 2.0
        ini_b = b.s - b.largo / 2.0
        if ini_b < fin_a - tol:
            solapes.append((i, round(fin_a - ini_b, 1)))
    cubierto = sum(c.largo for c in colocaciones)
    cobertura = cubierto / largo_curva if largo_curva > 0 else 0.0
    return {"piezas": n, "solapes": solapes, "cobertura": round(cobertura, 3),
            "cobertura_ok": cobertura >= 0.9, "sin_solape": not solapes}
```

**El cambio de espacio.** En vez de razonar en 3D, este oráculo trabaja en **coordenada de arco**: `s`
es la distancia recorrida a lo largo de la curva, y `largo` es cuánto ocupa la pieza sobre esa curva.
El problema 3D se reduce a intervalos en una recta.

Esa reducción es el aporte conceptual: *si tu problema tiene una parametrización natural, verificá en
esa parametrización, no en el espacio ambiente*. Es mucho más simple y mucho más exacto.

**Las dos condiciones:**

- **Sin solape**: el final de la pieza *i* no puede pasar del inicio de la *i+1*. Si pasa, las piezas
  se pisan y se ve doble geometría en la junta.
- **Cobertura ≥ 90%**: la suma de los largos debe cubrir casi toda la curva. Si no, quedaron huecos.

Este oráculo nació de un defecto concreto: una herramienta de pared **estiraba** las piezas para que
calzaran. Estirar destruye las proporciones del asset y se nota inmediatamente. La solución fue
colocar las piezas a su largo real y aceptar que sobra un pedacito; el oráculo verifica que ese
pedacito sea chico y que nada se pise.

---

# 8. El oráculo de espacio: winnability

El oráculo más distinto de todos, porque no mide geometría: mide **jugabilidad**.

```python
"""Oráculo de ESPACIO para BotOO — winnability de un mapa de extracción.

Modela el loop de Hunt: Showdown con las primitivas del grafo (`oraculo.mazes.spacegraph`):

    entrada --- pista(da el "sello") --- ... --- cripta(jefe) --( puerta: exige sello )-- extracción

- `key` en un nodo  = pickup al ENTRAR (la pista te entrega el sello para desterrar al Antiguo).
- `door_id` en una arista = exige tener esa llave (no extraés sin haber banisheado al jefe).
- `start`/`goal` = entrada / punto de extracción.

El oráculo (`solve_graph`, BFS sobre (nodo, llaves, flags)) dictamina si el mapa se puede
TERMINAR. Un mapa donde el sello es inalcanzable → `solvable=False`: eso es lo que Dash no puede
decirte.
"""
```

## 8.1 El modelo

Un mapa se representa como un grafo donde:

- los **nodos** son espacios, y algunos entregan una llave al entrar;
- las **aristas** son conexiones, y algunas exigen una llave para cruzarse.

```python
def mapa_botoo_ganable() -> SpaceGraph:
    """Un contrato de extracción SANO: la pista entrega el sello, con él se extrae."""
    nodes = {
        "entrada": _n("entrada", type="spawn", start=True),
        "pista": _n("pista", type="clue", key="sello_antiguo"),
        "galeria": _n("galeria"),
        "cripta": _n("cripta", type="boss"),
        "extraccion": _n("extraccion", type="extract", goal=True),
    }
    edges = [
        GraphEdge(a="entrada", b="pista", kind="door"),
        GraphEdge(a="entrada", b="galeria", kind="door"),
        GraphEdge(a="galeria", b="cripta", kind="door"),
        # sólo se extrae con el sello (desterraste al Antiguo):
        GraphEdge(a="cripta", b="extraccion", kind="door", door_id="sello_antiguo"),
    ]
    return SpaceGraph(nodes=nodes, edges=edges, space="extraction")
```

## 8.2 El algoritmo: BFS sobre estados

La resolución no es un BFS sobre nodos, sino sobre **(nodo, conjunto de llaves)**. Eso es esencial:
estar en la galería *con* el sello es un estado distinto de estar en la galería *sin* el sello, porque
desde uno se puede avanzar y desde el otro no.

El espacio de estados es `nodos × 2^llaves`, lo cual es exponencial en el número de llaves pero
perfectamente manejable para los pocos ítems de un mapa de extracción.

## 8.3 El contra-ejemplo: la prueba de que el oráculo no es un sello de goma

```python
def mapa_botoo_roto() -> SpaceGraph:
    """El MISMO mapa pero con la pista amurallada: el sello es inalcanzable → NO ganable.

    Es el caso que prueba que el oráculo no es un sello de goma: un diseñador que olvida
    conectar la pista produce un mapa de extracción imposible, y el oráculo lo caza."""
    g = mapa_botoo_ganable()
    # cortamos la única arista que llega a la pista:
    g.edges = [e for e in g.edges if not (e.a == "entrada" and e.b == "pista")]
    return g
```

**Esta es la lección metodológica más importante de todo el documento.**

Un oráculo que siempre dice ✓ no vale nada, y es sorprendentemente fácil escribir uno sin darse
cuenta. La única defensa es **construir deliberadamente el caso que debe fallar** y verificar que
falla.

Por eso Jam mantiene, al lado de cada caso sano, su versión rota. No como test negativo accesorio:
como parte de la definición del oráculo. Un oráculo se entrega con su contra-ejemplo o no se entrega.

Veremos la versión ejecutable de esta idea —*mutation testing*— en la sección 12.

---

# 9. El oráculo de forma: comparar contra una referencia

El oráculo más reciente y el más pedagógicamente rico, porque nació de una pregunta concreta y su
desarrollo está documentado de punta a punta.

## 9.1 El problema

Jam construyó un generador de árboles procedurales replicando el flujo de TreeGen (un plugin de UE
4.24). El resultado corría sin errores... y no se parecía al árbol de TreeGen.

La pregunta del usuario fue exactamente la correcta:

> «Funciona, pero no genera el árbol que está en TreeGen. ¿Cómo podemos verificar dónde está el
> error?»

Mirar y opinar no escala. Hacía falta medir. Pero, ¿medir contra qué?

## 9.2 El hallazgo: la referencia ya existía

TreeGen distribuye sus árboles de ejemplo **ya horneados** como StaticMesh en `/TreeGen/Examples/`. No
hacía falta reconstruir el Blueprint para tener una verdad de referencia: venía en la caja.

```
Pine       tris=25268   verts=18424   secciones=2   alto=3574cm
Birch      tris=20360   verts=13482   secciones=3   alto=1372cm
Bamboo     tris=26798   verts=17630   secciones=2   alto=1235cm
BirchBig   tris=181824  verts=121239  secciones=3   alto=1306cm
```

Y los slots de material revelaron la primera divergencia estructural, sin necesidad de mirar nada:

```
Pine   slot 0: M_Pine     slot 1: M_PineFrond
Birch  slot 0: M_Birch    slot 1: M_BirchPeel   slot 2: M_Leaves
```

**El follaje de TreeGen está horneado dentro de la malla del árbol**, como una sección de material
más. La implementación de Jam mandaba el follaje a un actor de instancias separado, así que la malla
generada era madera pelada. Ese dato —dos números y dos nombres— explicaba de entrada buena parte del
«no se parece».

**Lección**: antes de construir el oráculo, buscá si la verdad de referencia ya está disponible en
alguna forma medible. Muy seguido lo está.

## 9.3 Qué medir

El módulo `compare.py` mide seis cosas:

```python
@dataclass(frozen=True)
class Medida:
    """Firma de forma de una malla. Comparable entre una DynamicMesh y una StaticMesh."""

    vertices: int
    triangulos: int
    secciones: int
    alto: float
    ancho: float
    base_z: float
    perfil: tuple[float, ...]
```

| Métrica | Tolerancia | Qué detecta |
|---|---|---|
| `alto` | ±30% | escala general equivocada |
| `ancho` | ±35% | copa demasiado abierta o cerrada |
| `esbeltez` | ±20% | la **proporción** alto/ancho |
| `vertices` | ±50% | densidad de geometría |
| `triangulos` | ±50% | ídem |
| `secciones` | **exacta** | falta un material entero |
| `perfil` | distancia ≤ 0.15 | **dónde** está distribuida la masa a lo alto |
| `silueta` | distancia ≤ 0.18 | el **contorno**: cono contra cilindro |

> Las dos últimas —`esbeltez` y `silueta`— se agregaron después, cuando el oráculo aprobó un árbol
> que a simple vista estaba mal. La historia completa está en §9.9, y es la lección más importante
> de esta sección.

**Por qué `secciones` no admite tolerancia.** Porque una sección de menos no es una desviación
cuantitativa: es una ausencia estructural. En un árbol, típicamente significa que falta todo el
follaje. No tiene sentido decir «te falta media sección».

**Por qué tolerancias tan anchas en el resto.** Estas son mallas procedurales comparadas contra un
artefacto hecho con otro sistema. Exigir coincidencia exacta sería inútil. Lo que importa es el orden
de magnitud y la silueta.

## 9.4 El perfil de masa: la métrica que localiza el error

Ésta es la idea central del oráculo.

```python
def medir(posiciones, *, triangulos: int, secciones: int, franjas: int = FRANJAS) -> Medida:
    """Convierte una nube de vértices en una firma comparable.

    `posiciones` es cualquier iterable de (x, y, z). El perfil se normaliza por altura relativa, así
    que dos árboles de tamaños distintos siguen siendo comparables en FORMA.
    """
    puntos = [(float(p[0]), float(p[1]), float(p[2])) for p in posiciones]
    if not puntos:
        raise ValueError("medir necesita al menos un vértice.")
    if franjas < 1:
        raise ValueError("franjas debe ser al menos 1.")
    if not all(math.isfinite(c) for p in puntos for c in p):
        raise ValueError("la malla contiene una coordenada no finita.")

    zs = [p[2] for p in puntos]
    z_min, z_max = min(zs), max(zs)
    alto = z_max - z_min
    ancho = max(
        max(p[0] for p in puntos) - min(p[0] for p in puntos),
        max(p[1] for p in puntos) - min(p[1] for p in puntos),
    )

    conteo = [0] * franjas
    for _x, _y, z in puntos:
        if alto <= 1e-6:
            conteo[0] += 1
            continue
        indice = int((z - z_min) / alto * franjas)
        conteo[min(indice, franjas - 1)] += 1
    total = float(len(puntos))
    perfil = tuple(c / total for c in conteo)

    return Medida(
        vertices=len(puntos), triangulos=int(triangulos), secciones=int(secciones),
        alto=alto, ancho=ancho, base_z=z_min, perfil=perfil,
    )
```

**El conteo de vértices dice *cuánta* geometría hay. El perfil dice *dónde*.**

Se divide la malla en franjas horizontales (8 por defecto) y se mide qué fracción de los vértices cae
en cada una. Detalles importantes:

- **Normalizado por altura relativa**, no absoluta. Dos árboles de escalas distintas con la misma
  silueta dan el mismo perfil. Compara **forma**, no tamaño.
- **`min(indice, franjas - 1)`** captura el vértice más alto, que si no caería en la franja `franjas`
  (fuera del array).
- **Malla plana** (`alto ≈ 0`): todo va a la franja 0 en vez de dividir por cero.

### La distancia entre perfiles

```python
def distancia_perfil(a, b) -> float:
    """Distancia de variación total entre dos perfiles: 0 = misma silueta, 1 = disjuntos."""
    if len(a) != len(b):
        raise ValueError("los perfiles deben tener la misma cantidad de franjas.")
    return sum(abs(x - y) for x, y in zip(a, b)) / 2.0
```

Es la **distancia de variación total** entre dos distribuciones de probabilidad. La división por 2 la
normaliza al rango [0, 1]:

- `0.0` → distribuciones idénticas
- `1.0` → distribuciones disjuntas (no comparten ninguna franja)

Es simétrica, acotada e interpretable: «0.30» significa que el 30% de la masa está en franjas
distintas.

## 9.5 La comparación, ordenada por gravedad

```python
TOLERANCIAS = {"alto": 0.30, "ancho": 0.35, "vertices": 0.50, "triangulos": 0.50}
TOLERANCIA_PERFIL = 0.15


def comparar(generada: Medida, referencia: Medida, *, tolerancias: dict | None = None,
             tolerancia_perfil: float = TOLERANCIA_PERFIL) -> dict:
    """Diff métrica a métrica, ordenado por gravedad.

    Devuelve {ok, filas, peor, texto}. `filas` trae, por métrica, el valor de cada lado, la razón y
    si pasa. Se ordena por desvío para que lo primero que se lee sea lo que más separa a las dos
    mallas.
    """
    limites = dict(TOLERANCIAS)
    limites.update(tolerancias or {})
    filas = []

    for nombre in ("alto", "ancho", "vertices", "triangulos"):
        g = float(getattr(generada, nombre))
        r = float(getattr(referencia, nombre))
        razon = _razon(g, r)
        desvio = abs(razon - 1.0) if math.isfinite(razon) else float("inf")
        filas.append({
            "metrica": nombre, "generada": g, "referencia": r, "razon": razon,
            "desvio": desvio, "limite": limites[nombre], "ok": desvio <= limites[nombre],
        })

    # Las secciones son estructurales: 1 sección donde la referencia tiene 2 significa que falta un
    # material entero (en un árbol, típicamente el follaje). No admite tolerancia.
    filas.append({
        "metrica": "secciones", "generada": float(generada.secciones),
        "referencia": float(referencia.secciones),
        "razon": _razon(generada.secciones, referencia.secciones),
        "desvio": 0.0 if generada.secciones == referencia.secciones else 1.0,
        "limite": 0.0, "ok": generada.secciones == referencia.secciones,
    })

    distancia = distancia_perfil(generada.perfil, referencia.perfil)
    filas.append({
        "metrica": "perfil", "generada": distancia, "referencia": 0.0, "razon": distancia,
        "desvio": distancia, "limite": tolerancia_perfil, "ok": distancia <= tolerancia_perfil,
    })

    filas.sort(key=lambda f: (f["ok"], -f["desvio"]))
    fallan = [f for f in filas if not f["ok"]]
    peor = fallan[0]["metrica"] if fallan else None
    return {"ok": not fallan, "filas": filas, "peor": peor,
            "texto": reporte(filas, generada, referencia)}
```

**El ordenamiento es la característica de usabilidad clave:**

```python
filas.sort(key=lambda f: (f["ok"], -f["desvio"]))
```

Ordena por `(pasa, -desvío)`: primero los que fallan, y dentro de ellos, el de mayor desvío arriba.
Con seis métricas, lo primero que leés es lo que más te separa de la referencia. El campo `peor` lo
nombra explícitamente.

**La razón acotada:**

```python
def _razon(generada: float, referencia: float) -> float:
    """gen/ref, acotado. 1.0 = idéntico. 0 y 0 se consideran iguales."""
    if abs(referencia) < 1e-9:
        return 1.0 if abs(generada) < 1e-9 else float("inf")
    return generada / referencia
```

Cero contra cero es coincidencia perfecta, no división por cero. Algo contra cero es infinito, y el
desvío infinito lo manda al tope del orden.

## 9.6 El adaptador: medir dos cosas con la misma regla

El desafío técnico: comparar una `DynamicMesh` (lo que produce el grafo, en memoria) con una
`StaticMesh` (el asset de referencia en Content). Son tipos distintos con APIs distintas.

La solución: **convertir la referencia a DynamicMesh y medir ambas con el mismo código.**

```python
def medir(source, *, franjas: int = 8) -> dict:
    """Firma de forma de una malla `M` o de un StaticMesh `A`, para el oráculo de `compare`."""
    from . import compare

    asset = None
    dynamic = _dynamic_mesh(source)
    if dynamic is None:
        try:
            dynamic, asset = _copy_static_mesh(source)
        except (TypeError, RuntimeError) as exc:
            return {"error": f"medir necesita una malla M o un StaticMesh A: {exc}"}
    try:
        posiciones = _posiciones(dynamic)
        triangulos = unreal.GeometryScript_MeshQueries.get_num_triangle_i_ds(dynamic)
        if isinstance(triangulos, tuple):
            triangulos = triangulos[0]
        medida = compare.medir(
            posiciones, triangulos=int(triangulos),
            secciones=_secciones(dynamic, asset), franjas=int(franjas))
    except (ValueError, TypeError) as exc:
        return {"error": str(exc)}
    return {"medida": medida}
```

Esto garantiza que la comparación sea **manzana con manzana**. Si se midiera la StaticMesh con la API
de StaticMesh y la DynamicMesh con la de Geometry Script, cualquier diferencia de criterio (¿cuenta
vértices soldados o partidos?) contaminaría el diff.

### Los gotchas de la API

```python
def _posiciones(dynamic) -> list[tuple[float, float, float]]:
    """Todas las posiciones de vértice de una DynamicMesh, como tuplas puras."""
    # Firma real en 5.7: (target_mesh, skip_gaps) → (mesh, position_list, has_gaps), donde
    # position_list es un GeometryScriptVectorList y los vectores viven en su campo `list`.
    devuelto = unreal.GeometryScript_MeshQueries.get_all_vertex_positions(dynamic, True)
    crudo = devuelto[1] if isinstance(devuelto, tuple) and len(devuelto) > 1 else devuelto
    # GeometryScriptVectorList no es iterable: hay que pedirle el array explícitamente.
    convertir = getattr(crudo, "convert_vector_list_to_array", None)
    if convertir is not None:
        crudo = convertir()
        if isinstance(crudo, tuple):
            crudo = crudo[-1]
    return [(float(v.x), float(v.y), float(v.z)) for v in crudo]
```

Dos trampas reales de UE 5.7 documentadas en el código: la función devuelve una tupla de tres
elementos, y el contenedor de vectores no es iterable.

## 9.7 El verbo del grafo

```python
def t_mesh_compare(mesh_input, *, asset=None, franjas=8, alto=0.30, ancho=0.35,
                   vertices=0.50, triangulos=0.50, perfil=0.15) -> str:
    """Oráculo de forma: compara `M` contra un StaticMesh de referencia y DEJA PASAR la malla.

    No modifica nada. Se intercala antes de `Mesh to Static` para que el mismo Run que construye el
    árbol diga cuánto se parece al de referencia.
    """
    from . import mesh
    resultado = mesh.comparar(
        mesh_input, asset, franjas=int(franjas), tolerancia_perfil=float(perfil),
        alto=float(alto), ancho=float(ancho),
        vertices=float(vertices), triangulos=float(triangulos))
    if "error" in resultado:
        raise RuntimeError(resultado["error"])
    _RUNTIME_DATA_OUTPUTS["mesh_compare"] = mesh._dynamic_mesh(mesh_input)
    marca = "✓" if resultado["ok"] else "✗"
    titulo = (f"COMPARE {marca} — se parece a la referencia" if resultado["ok"]
              else f"COMPARE {marca} — lo que más separa: {resultado['peor']}")
    return f"{titulo}\n{resultado['texto']}"
```

**El detalle de diseño más importante: `M → M`, deja pasar la malla.**

El oráculo no es un nodo terminal. Consume la malla y devuelve *la misma malla, intacta*. Eso permite
intercalarlo en cualquier punto de la cadena:

```
merge → color → uv → material → [COMPARE] → normals → Mesh to Static → Place
```

El mismo Run que construye el árbol emite el veredicto. No hay un paso «ahora verificá» que se pueda
olvidar. **Un oráculo que hay que acordarse de correr es un oráculo que no se corre.**

## 9.8 El caso de estudio completo: el lazo cerrado

### Iteración 1 — el diagnóstico

```
✗ alto              690 vs     3574  (0.19×)
✗ ancho             668 vs     1329  (0.50×)
✗ perfil        distancia 0.301 (límite 0.15)
✓ vertices         9234 vs    18424  (0.50×)
✓ triangulos      13946 vs    25268  (0.55×)
✓ secciones           2 vs        2  (1.00×)

masa por franja (base → copa):
  generada       0%    0%    2%   16%   22%   25%   29%    6%
  referencia     7%   10%   16%   16%   16%   17%   18%    1%
```

Leamos esto como lo leería un artista técnico:

- **`secciones 2 vs 2 ✓`** — la corrección del follaje horneado funcionó. Ya no falta un material.
- **`alto 0.19×`** — el árbol es cinco veces más bajo. Es lo peor y encabeza la lista.
- **`perfil 0.301`** — el doble del límite. Y las cifras dicen *exactamente* dónde: **cero masa en
  las tres franjas de abajo** (0%, 0%, 2%) contra 7%, 10%, 16% de la referencia. Y exceso arriba
  (29% vs 18%).

**El diagnóstico se lee solo**: el árbol de Jam no tiene nada en su tercio inferior. Investigando: el
tronco aportaba 228 vértices de 9234 (2.5%) y las ramas arrancaban al 18% de su altura. Todo el árbol
vivía arriba.

### Iteración 2 — la corrección guiada

Los ajustes salieron directamente de esa lectura:

- tronco cinco veces más alto, más grueso y con más resolución de barrido (para que aporte masa);
- ramas arrancando al 8% de la altura en vez del 18% (para llenar las franjas bajas);
- 26 ramas madre en vez de 12;
- ramas y ramitas más largas (para el ancho).

```
✓ ancho             966 vs     1329  (0.73×)
✓ perfil        distancia 0.123 (límite 0.15)
✓ vertices        16473 vs    18424  (0.89×)
✓ alto             3313 vs     3574  (0.93×)
✓ triangulos      25055 vs    25268  (0.99×)
✓ secciones           2 vs        2  (1.00×)

masa por franja (base → copa):
  generada       0%    6%   17%   20%   16%   16%   17%    7%
  referencia     7%   10%   16%   16%   16%   17%   18%    1%
```

Las seis métricas dentro de tolerancia.

### Lo que el oráculo todavía marca

Aun con todo en verde, el perfil sigue señalando dos diferencias reales:

- **Franja 0: 0% vs 7%.** TreeGen le cuelga follaje al **tronco** directamente, no sólo a las ramas.
  Jam todavía no lo hace.
- **Franja 7: 7% vs 1%.** La copa de Jam pesa más; TreeGen afina más hacia la punta.

Ninguna rompe la tolerancia, pero ambas son *información accionable* para el siguiente paso. Un
oráculo bien diseñado sigue enseñando después de que el test pasa.

---

## 9.9 El oráculo aprobó y el resultado estaba mal

Ésta es la parte más instructiva de todo el documento, y ocurrió **después** de que las seis métricas
dieran verde.

### Lo que pasó

Con el oráculo en ✓, se abrió el editor y se miró el árbol. Era un **poste** de 33 metros con muñones
uniformes, no un pino. Un humano lo vio en un segundo; seis métricas no lo habían visto.

### Por qué se le escapó

Dos agujeros, ambos estructurales:

**1. No había métrica de proporción.** `alto` daba 0.93× y `ancho` 0.73×: cada uno cómodo dentro de su
tolerancia. Pero la relación alto/ancho era 3.43 contra 2.69 de la referencia — 28% más esbelto. La
proporción no era ninguna de las seis, y es lo primero que lee el ojo.

**2. El perfil vertical no puede distinguir un cono de un cilindro.** Los dos reparten la masa
uniformemente a lo largo del eje. Éste es el test que lo demuestra:

```python
    def test_a_cone_and_a_cylinder_have_the_same_vertical_profile(self):
        # Éste es el agujero que motivó la silueta: los dos reparten la masa igual a lo largo del
        # eje, así que el perfil vertical no puede distinguirlos.
        cono = compare.medir(solido(lambda u: 1.0 - 0.9 * u), triangulos=1, secciones=1)
        cilindro = compare.medir(solido(lambda _u: 1.0), triangulos=1, secciones=1)

        self.assertEqual(cono.perfil, cilindro.perfil)
        self.assertAlmostEqual(compare.distancia_perfil(cono.perfil, cilindro.perfil), 0.0)
        # Pero la silueta sí los separa.
        self.assertGreater(compare.distancia_silueta(cono.silueta, cilindro.silueta), 0.3)
```

Un cono y un cilindro tienen **exactamente el mismo perfil vertical**. Y la diferencia entre un pino y
un poste con muñones es justamente ésa.

### La métrica que faltaba: la silueta

```python
    # SILUETA: radio máximo de cada franja respecto del eje central, normalizado al mayor.
    # El perfil vertical no distingue un cono de un cilindro —ambos reparten la masa parejo a lo
    # largo del eje—, y esa es justo la diferencia entre un pino y un poste con muñones. La silueta
    # sí: en un cono el radio cae con la altura, en un cilindro se queda.
    cx = (max(p[0] for p in puntos) + min(p[0] for p in puntos)) / 2.0
    cy = (max(p[1] for p in puntos) + min(p[1] for p in puntos)) / 2.0
    radios = [0.0] * franjas
    for x, y, z in puntos:
        indice = 0 if alto <= 1e-6 else min(int((z - z_min) / alto * franjas), franjas - 1)
        radio = math.hypot(x - cx, y - cy)
        if radio > radios[indice]:
            radios[indice] = radio
    mayor = max(radios)
    silueta = tuple((r / mayor) if mayor > 1e-9 else 0.0 for r in radios)
```

Y su distancia, que **no** es variación total:

```python
def distancia_silueta(a, b) -> float:
    """Diferencia media entre dos siluetas normalizadas: 0 = mismo contorno, 1 = opuestos.

    No es variación total porque una silueta no es una distribución: no suma 1. Como cada radio ya
    está normalizado a [0, 1], el promedio de las diferencias absolutas queda acotado en [0, 1].
    """
```

**Detalle conceptual**: el perfil de masa *es* una distribución (suma 1), así que la variación total
es la distancia correcta. La silueta *no* lo es —son ocho radios independientes—, así que la métrica
correcta es la diferencia media. Usar variación total ahí habría sido un error de tipo.

### El veredicto con el ojo nuevo

Sobre exactamente el mismo árbol que antes daba ✓:

```
JAM vs TreeGen Pine — ok=False  peor=esbeltez
  ✗ esbeltez         3.43 vs     2.69  (1.28×)
  ✗ silueta       distancia 0.246 (límite 0.18)
  ✓ ancho             966 vs     1329  (0.73×)
  ✓ perfil        distancia 0.123 (límite 0.15)
  ✓ vertices        16473 vs    18424  (0.89×)
  ✓ alto             3313 vs     3574  (0.93×)
  ✓ triangulos      25055 vs    25268  (0.99×)
  ✓ secciones           2 vs        2  (1.00×)

silueta: radio de cada franja, normalizado al mayor:
  generada      41%   84%  100%   88%   91%   82%   86%   71%
  referencia    57%  100%   91%   70%   63%   56%   41%   32%
```

La línea de silueta es el diagnóstico entero: la referencia **se angosta monótonamente** desde la
segunda franja (100 → 91 → 70 → 63 → 56 → 41 → 32); la generada se queda ancha hasta arriba. Cono
contra cilindro, en dos filas de números.

### Las tres lecciones

**1. Esto es Goodhart, y lo cometió quien escribió el oráculo.** Los parámetros del árbol se
ajustaron *leyendo las métricas*. Se optimizó la métrica, no el objetivo. El principio anti-Goodhart
dice que no hay que inyectarle al generador lo que se va a medir — y ajustar a mano mirando el
veredicto es exactamente esa inyección, con un humano de intermediario.

**2. Un oráculo verde no es una garantía, es la ausencia de una refutación.** Sólo prueba que no
detectó nada, y eso depende enteramente de qué mira. Las métricas acotan el error por abajo, nunca por
arriba.

**3. El ojo humano sigue siendo parte del sistema.** No como sustituto del oráculo sino como su
fuente: cada vez que alguien mira el resultado y encuentra algo que las métricas no vieron, ese
hallazgo se convierte en una métrica nueva. El oráculo no reemplaza al artista; **acumula** lo que el
artista descubre, para que no haya que volver a descubrirlo.

> El ciclo sano es: el oráculo caza lo que ya sabemos mirar, el humano caza lo nuevo, y lo nuevo se
> convierte en oráculo.

**Éste es el lazo que hacía falta**: de «no se parece» a un número por eje, y del número al parámetro
que hay que mover.

---
# 10. Los oráculos de contrato

Los oráculos de escena responden «¿quedó bien?» *después* de ejecutar. Los de contrato responden
«¿esto se puede correr?» **antes**, y su valor es evitar efectos parciales.

## 10.1 Por qué existen: el problema del efecto parcial

Un grafo de 30 nodos donde el nodo 24 falla deja el mundo en un estado intermedio: 23 nodos ya
crearon actores y assets. El usuario tiene que limpiar a mano y no sabe qué quedó a medias.

La regla que Jam adoptó:

> **Si el grafo no compila, no se toca la escena. Ni un actor.**

## 10.2 Compile / Preflight del Graph

```python
def compilar(g: JamGraph, *, registro: dict | None = None, resolver_asset=None,
             resolver_pick=None, transformar_asset=None) -> GraphPlan:
    """Compila el DAG completo sin ejecutar tools ni modificar Unreal.

    Valida nodos, endpoints, pines, tipos, cardinalidad, ciclos, variables, expresiones, params y la
    presencia de assets explícitos. En runtime también comprueba que nombres/rutas y Pick resuelvan.
    """
```

Lo que valida, en orden:

| Validación | Ejemplo de error que caza |
|---|---|
| verbos conocidos | `verbo desconocido: «pts_line»` |
| endpoints existen | `origen inexistente: «foliage_color»` |
| nombres de pin válidos | pin `profile` en un nodo que no lo tiene |
| **compatibilidad de tipos** | `esperaba S, recibió F` |
| **cardinalidad** | dos cables a una entrada unaria |
| ciclos | `A → B → A` |
| autoconexiones | `A → A` |
| variables duplicadas | dos nodos `number` llamados `n` |
| expresiones resolubles | `= count * 2` con `count` inexistente |
| **assets explícitos** | `requiere asset explícito: cable Asset/Pick, campo asset o entrada A` |

### El patrón de acumulación de diagnósticos

```python
    diagnosticos: dict[str, list[str]] = {}

    def error(nid: str, mensaje: str) -> None:
        mensajes = diagnosticos.setdefault(nid, [])
        if mensaje not in mensajes:
            mensajes.append(mensaje)
```

Tres decisiones:

1. **Acumula, no aborta.** Se recolectan *todos* los errores del grafo antes de rendirse. Un usuario
   que arregla un error y descubre otro, y otro, abandona.
2. **Indexado por `node id`.** Cada error se asocia a su nodo, para que la UI pinte ese nodo en rojo.
   Los errores globales (como un ciclo) van a la clave `_graph` y se muestran en todos.
3. **Deduplica.** El mismo mensaje no se repite en el mismo nodo.

### El fallback silencioso que este oráculo eliminó

Este Preflight nació de un bug concreto y muy instructivo. El ejecutor del grafo heredaba el
comportamiento cómodo de la barra de comandos:

```
asset explícito/cableado vacío
→ asset activo de la sesión
→ si tampoco existe, primer asset de la biblioteca
→ ejecutar la tool
```

Consecuencia: un nodo `Place` **aislado**, sin nada conectado y con el campo vacío, colocaba objetos
igual. La UI mostraba `asset` como un pin explícito, así que el fallback invisible contradecía el
modelo visual del grafo.

La regla nueva: en el grafo, un consumidor acepta un asset **sólo** por (1) cable al pin `asset`,
(2) valor escrito en el campo, o (3) cable principal desde un productor compatible. El fallback sigue
existiendo en la barra de comandos, donde es cómodo y esperable.

**Lección**: la comodidad en una interfaz puede ser una mentira en otra. Un oráculo de contrato es
también un mecanismo para hacer explícito lo que estaba implícito.

## 10.3 Flow.validar

El equivalente para el evaluador de flujo de puntos:

```python
    def validar(self, ops: dict | None = None) -> dict[str, list[str]]:
        """Preflight puro: valida operaciones, endpoints, pines, tipos y cardinalidad.

        No llama ninguna operación ni toca Unreal. Devuelve `{node_id: [mensajes]}`; vacío significa
        que el Flow puede evaluarse. `ops` declara las implementaciones del adaptador Unreal.
        """
        tabla_fn = {**OPS, **(ops or {})}
        diagnosticos: dict[str, list[str]] = {}
        ...
        for nid, nodo in self.nodos.items():
            kind = nodo.get("kind", "")
            meta = OPS_META.get(kind)
            implementacion = tabla_fn.get(kind)
            if kind in VALOR_KINDS:
                aridades[nid] = 0
            elif meta is not None:
                aridades[nid] = int(meta.get("aridad", 0 if meta.get("source") else 1))
                if implementacion is None:
                    error(nid, f"operación «{kind}» sin implementación disponible")
            elif implementacion is not None:  # compatibilidad con ops puras históricas
                aridades[nid] = int(implementacion[1])
            else:
                aridades[nid] = None
                error(nid, f"operación desconocida: «{kind}»")
```

### El defecto que eliminó: el fallo silencioso

Antes, una operación desconocida se evaluaba a lista vacía `[]` **sin error**. El grafo «funcionaba»,
producía cero puntos, y no había forma de saber por qué. Renombrar una operación rompía grafos
guardados en silencio.

Ahora una op desconocida o sin implementación es un error de Preflight que impide la ejecución.

**Principio general: fallar ruidosamente es mejor que degradar en silencio.** Un `[]` vacío es un
resultado válido y un error indistinguibles.

### Las variables duplicadas

```python
        # Dos variables con el mismo nombre hacían que el orden de inserción decidiera silenciosamente.
        nombres: dict[str, str] = {}
        for nid, nodo in self.nodos.items():
            if nodo.get("kind") not in VALOR_KINDS:
                continue
            nombre = str(nodo.get("params", {}).get("name") or nid)
            anterior = nombres.get(nombre)
            if anterior is not None:
                error(anterior, f"nombre de variable duplicado: «{nombre}»")
                error(nid, f"nombre de variable duplicado: «{nombre}»")
            else:
                nombres[nombre] = nid
```

Nótese que marca **los dos** nodos, no sólo el segundo. El usuario necesita ver ambos para decidir
cuál renombrar.

## 10.4 El oráculo de nombres de API

Éste es el oráculo más meta del proyecto: verifica que **el código pueda siquiera llamar al motor**.

### El bug que lo motivó

Un Run real falló con:

```
[mesh_uv_scale] AttributeError:
    type object 'GeometryScript_UVs' has no attribute 'scale_mesh_uvs'
```

La causa: el generador de bindings de Python de Unreal **parte las siglas**. `ScaleMeshUVs` no se
expone como `scale_mesh_uvs` sino como `scale_mesh_u_vs` (`UVs` → `U` + `Vs`). Y `ClearMaterialIDs`
es `clear_material_i_ds` (`IDs` → `I` + `Ds`). Un `ID` suelto no se parte, por eso
`get_max_material_id` sí es correcto — justo lo bastante inconsistente para no notarlo.

**Por qué la suite de tests no lo detectó**: los tests mockean el módulo `unreal`. Un nombre inventado
pasa verde contra un mock. Ése era el agujero estructural.

### El verificador

```python
"""Verifica contra el editor REAL que cada API de Unreal que llama Jam exista.

La suite headless mockea `unreal`, así que un nombre mal escrito la pasa entera y recién explota en
mitad de un Run. Pasó con `GeometryScript_UVs.scale_mesh_uvs`: el nombre real es `scale_mesh_u_vs`
porque el mangler de UE parte `UVs` en `U` + `Vs` (y `IDs` en `I` + `Ds`). Este script cierra ese
agujero: extrae los `unreal.Clase.metodo` del código de Jam y comprueba cada uno en un editor vivo.
"""

# `unreal.Clase.metodo`, sólo métodos en snake_case (descarta constantes y enums).
PATRON = re.compile(r"\bunreal\.([A-Za-z_][A-Za-z_0-9]*)\.([a-z_][a-z_0-9]*)\b")

IGNORAR_CLASES = {"log", "log_warning", "log_error"}


def llamadas(raiz: Path) -> dict[tuple[str, str], list[str]]:
    """{(clase, metodo): [archivo:linea, …]} de todo lo que Jam le pide a Unreal."""
    encontrado: dict[tuple[str, str], list[str]] = {}
    for archivo in sorted(raiz.glob("*.py")):
        for numero, linea in enumerate(archivo.read_text(encoding="utf-8").splitlines(), 1):
            if linea.lstrip().startswith("#"):
                continue
            for clase, metodo in PATRON.findall(linea):
                if clase in IGNORAR_CLASES:
                    continue
                encontrado.setdefault((clase, metodo), []).append(f"{archivo.name}:{numero}")
    return encontrado
```

Y la verificación, con **sugerencia automática**:

```python
    for (clase, metodo), lugares in sorted(objetivo.items()):
        tipo = getattr(unreal, clase, None)
        if tipo is None:
            clases_faltantes.append(f"unreal.{clase}  ← {', '.join(lugares)}")
            continue
        if not hasattr(tipo, metodo):
            # Sugerencia: el error casi siempre es el mangler (UVs → u_vs, IDs → i_ds).
            candidatos = [
                nombre for nombre in dir(tipo)
                if not nombre.startswith("_")
                and nombre.replace("_", "") == metodo.replace("_", "")
            ]
            pista = f"  ¿será «{candidatos[0]}»?" if candidatos else ""
            faltantes.append(f"unreal.{clase}.{metodo}{pista}  ← {', '.join(lugares)}")
```

**El truco de la sugerencia**: comparar los nombres *sin guiones bajos*. `scale_mesh_uvs` y
`scale_mesh_u_vs` colapsan ambos a `scalemeshuvs`, así que el candidato correcto se encuentra solo.
Es una heurística de una línea que convierte «no existe» en «quisiste decir esto».

### El resultado

Sobre 47 llamadas encontró **4 rotas**:

| Rota | Correcta | Estado |
|---|---|---|
| `GeometryScript_UVs.scale_mesh_uvs` | `scale_mesh_u_vs` | la que reventó |
| `GeometryScript_Materials.clear_material_ids` | `clear_material_i_ds` | latente |
| `GeometryScript_Materials.remap_material_ids` | `remap_material_i_ds` | latente |
| `MaterialInstanceDynamic.create` | `MaterialLibrary.create_dynamic_material_instance` | **silenciosa** |

Las dos «latentes» no habían aparecido porque el error del UV cortaba la cascada antes de llegar a
ellas.

La cuarta es la más instructiva:

```python
    try:
        # `unreal.MaterialInstanceDynamic` NO expone `create` desde Python: la fábrica vive en
        # MaterialLibrary. Como el except devolvía el material base, el fantasma venía saliendo
        # opaco y sin color en silencio.
        mid = unreal.MaterialLibrary.create_dynamic_material_instance(dueno, b)
        if mid is None:
            return b
        mid.set_vector_parameter_value("Color", color)
        mid.set_scalar_parameter_value("Opacity", opacidad)
        return mid
    except Exception:  # noqa: BLE001
        return b   # sin parámetros (fallback del motor): al menos translúcido
```

Estaba envuelta en un `try/except` que devolvía un fallback razonable. Resultado: los fantasmas de
previsualización venían saliendo **sin color desde siempre**, sin un solo error en el log. Nadie lo
notó porque el fallback era plausible.

**Lección sobre `try/except` amplios**: convierten un fallo en una degradación silenciosa. Son útiles
para robustez, pero esconden bugs. Un oráculo externo que verifique la precondición es la contramedida.

### El test que impide la regresión

El verificador necesita un editor vivo. Para que el defecto no vuelva entre corridas, hay un test puro
que prohíbe las formas mal escritas **tanto en el código como en los stubs de la suite**:

```python
class ManglerTests(unittest.TestCase):
    """Los tres nombres que la suite mockeada dejó pasar y explotaron en un Run real."""

    ROTOS = (
        "scale_mesh_uvs",       # es scale_mesh_u_vs
        "translate_mesh_uvs",   # es translate_mesh_u_vs
        "rotate_mesh_uvs",      # es rotate_mesh_u_vs
        "recompute_mesh_uvs",   # es recompute_mesh_u_vs
        "clear_material_ids",   # es clear_material_i_ds
        "remap_material_ids",   # es remap_material_i_ds
        "compact_material_ids",
        "set_all_triangle_material_ids",
        "get_max_material_id",  # este SÍ es correcto: `ID` suelto no se parte
    )
    # `get_max_material_id` queda fuera: es la forma buena, sirve para no volverse paranoico.
    PROHIBIDOS = tuple(nombre for nombre in ROTOS if nombre != "get_max_material_id")

    def test_the_stubs_of_the_suite_use_the_same_names_as_the_engine(self):
        # Si un stub se escribe con el nombre malo, el test verde vuelve a mentir.
        ...
```

**El detalle que cierra el círculo**: verificar también los *stubs de los tests*. Si alguien escribe
el mock con el nombre equivocado, el test vuelve a pasar en verde mientras el código real falla. El
oráculo tiene que cubrir la herramienta de verificación misma.

---

# 11. El oráculo transaccional: Preview / Bake / Discard

No es un oráculo que mide: es un mecanismo que hace **verificable el acto de ejecutar**. Se apoya en
la misma filosofía: nada se da por hecho hasta comprobarlo.

## 11.1 El ciclo

```
Compile  →  Run (Preview)  →  Bake     (fija el resultado)
   ↓             ↓          ↘  Discard  (lo borra)
 error       error → rollback
```

- **Compile**: sólo diagnóstico, sin efectos.
- **Run**: ejecuta y deja el resultado marcado como provisional.
- **Bake**: quita las marcas; el resultado queda fijo.
- **Discard**: borra todo lo provisional.

## 11.2 El staging transaccional

```python
def _preview(fn, widget=None, *, owner: str = "dash") -> str:
    """Ejecuta una Preview como staging transaccional de actores y assets de Content.

    El Preview anterior del mismo owner permanece hasta que la nueva ejecución termina. Ante una
    excepción se destruyen los actores/assets nuevos y se conserva el anterior; sólo un éxito hace
    el swap.
    """
    global _PREVIEW_CONTEXT
    anteriores = _actores_preview(owner)
    assets_anteriores = _asset_records_for_owner(owner, anteriores)
    antes = {a.get_path_name() for a in _todos()}
    contexto_anterior = _PREVIEW_CONTEXT
    contexto = {"owner": owner, "id": uuid.uuid4().hex[:10], "assets": []}
    _PREVIEW_CONTEXT = contexto
    try:
        texto = fn(widget)
    except Exception as exc:  # noqa: BLE001
        nuevos = [a for a in _todos() if a.get_path_name() not in antes]
        borrados, fallidos = _destruir_actores(nuevos)
        assets_borrados, assets_fallidos = _discard_staged_assets(contexto["assets"])
        ...
        return (f"[error] PREVIEW revertida — {type(exc).__name__}: {exc}\n"
                f"ROLLBACK ✓ · {borrados} actor(es) nuevos eliminados{extra}; "
                f"se conserva el Preview anterior de «{owner}»{extra_assets}.")
    finally:
        _PREVIEW_CONTEXT = contexto_anterior
```

### La técnica: diff de actores del nivel

```python
    antes = {a.get_path_name() for a in _todos()}
    # ... se ejecuta la operación ...
    nuevos = [a for a in _todos() if a.get_path_name() not in antes]
```

En vez de pedirle a cada herramienta que registre lo que crea —lo cual dependería de que ninguna se
olvide— se toma una foto del nivel antes y después. **Todo lo nuevo es del Preview, por construcción.**

Es una decisión de robustez importante: el mecanismo no confía en la disciplina de las herramientas.

### Los tags como fuente de verdad

Cada actor temporal lleva:

```
jam:preview
jam:preview-owner=<owner>
jam:preview-label=<nombre original en base64>
```

Los tags viven en el **nivel**, no en memoria de Python. Consecuencias:

- Bake y Discard funcionan **después de recargar los módulos de Python**;
- borrar un actor a mano no deja referencias inválidas;
- dos interfaces (la barra y la ventana de grafo) mantienen previews independientes por `owner`.

### El orden de operaciones importa

```python
    nuevos = [a for a in _todos() if a.get_path_name() not in antes]
    # Marcar primero el staging: si luego falla la limpieza del anterior, ambos siguen recuperables.
    try:
        _marcar_preview(nuevos, owner, contexto["assets"])
    except Exception as exc:
        ...rollback...
```

Se marca lo nuevo **antes** de borrar lo viejo. Si algo falla en el medio, quedan dos previews
marcados —feo pero recuperable— en vez de un huérfano sin marcar.

Y para los assets de Content:

```python
    # Si queda un asset temporal sin borrar, el actor anterior conserva el tag que permite recuperar
    # su ruta y reintentar. Es preferible ver dos previews un instante a dejar Content huérfano.
```

**El criterio general: ante la duda, preferí el estado feo y recuperable al estado limpio y perdido.**

## 11.3 La convención visible en el Outliner

| Acción | Nombre del actor | Estado real |
|---|---|---|
| `Compile` | no crea ni renombra | sólo valida |
| `Run graph` | `prev_<nombre>` | tiene `jam:preview`; Discard puede borrarlo |
| `Discard` | desaparece | se eliminan los marcados |
| `Bake` | `bake_<nombre>` | se quitan los tags; ya no responde a Discard |

**El prefijo es una señal visual; la pertenencia al Preview siempre se decide por tag.** Escribir
`bake_` a mano en otro actor no cambia su estado. Es la separación entre *presentación* y *verdad*.

## 11.4 Un bug real que este diseño destapó

Reproduciendo `Run → Bake → Run`, un actor ya horneado perdía su asset. La causa: el componente
conservaba internamente la referencia al objeto de la ruta temporal aun después de renombrar el asset;
al ejecutar de nuevo, Unreal liberaba ese objeto transitorio y el componente quedaba vacío.

La corrección añadió dos garantías, ambas del espíritu del oráculo:

- después de promover el asset, **cargarlo explícitamente, reasignarlo y verificar su Object Path**;
- **releer y verificar cada escritura de tags** — antes una excepción quedaba oculta, así que se podía
  mostrar el prefijo `bake_` aunque Unreal hubiera conservado el tag `jam:preview`.

> No alcanza con escribir: hay que releer y comprobar que lo escrito quedó.

---
# 12. Cómo se prueba un oráculo

Un oráculo mal probado es peor que ninguno: da confianza falsa. Jam usa cuatro técnicas.

## 12.1 Núcleo puro, probado sin motor

Como el cerebro no importa `unreal`, los tests construyen los datos a mano:

```python
def columna(alturas, x=0.0, y=0.0):
    return [(x, y, z) for z in alturas]


class MedirTests(unittest.TestCase):
    def test_measures_bounds_and_normalizes_the_profile_by_relative_height(self):
        m = compare.medir(columna([0, 25, 50, 75, 100]), triangulos=8, secciones=2, franjas=4)

        self.assertEqual(m.vertices, 5)
        self.assertEqual(m.triangulos, 8)
        self.assertEqual(m.secciones, 2)
        self.assertAlmostEqual(m.alto, 100.0)
        self.assertAlmostEqual(m.base_z, 0.0)
        # z=100 cae en la última franja, no fuera del rango.
        self.assertEqual(sum(m.perfil), 1.0)
        self.assertAlmostEqual(m.perfil[-1], 2 / 5)
```

Cinco puntos en una columna. Sin editor, sin assets, sin mundo. 116 tests corren en menos de un
segundo.

## 12.2 Probar las propiedades, no sólo los casos

Un test de caso verifica un input concreto. Un test de **propiedad** verifica una invariante del
diseño:

```python
    def test_the_profile_is_scale_invariant(self):
        chico = compare.medir(columna([0, 10, 20, 30]), triangulos=2, secciones=1, franjas=4)
        grande = compare.medir(columna([0, 100, 200, 300]), triangulos=2, secciones=1, franjas=4)

        # Misma silueta a distinto tamaño ⇒ mismo perfil. Eso permite comparar FORMA sin escala.
        self.assertEqual(chico.perfil, grande.perfil)
        self.assertNotAlmostEqual(chico.alto, grande.alto)
```

Este test no verifica un número: verifica que **el perfil sea invariante a escala**, que es la razón
de ser de la métrica. Si alguien «optimiza» `medir()` y rompe esa propiedad, el test lo caza aunque
todos los números concretos cambien.

Otras propiedades verificadas en la suite:

```python
    def test_profile_distance_is_bounded_and_symmetric(self):
        a, b = (1.0, 0.0), (0.0, 1.0)
        self.assertAlmostEqual(compare.distancia_perfil(a, b), 1.0)
        self.assertAlmostEqual(compare.distancia_perfil(b, a), 1.0)
        self.assertAlmostEqual(compare.distancia_perfil(a, a), 0.0)
        with self.assertRaises(ValueError):
            compare.distancia_perfil((1.0,), (0.5, 0.5))
```

Simetría, acotamiento, identidad y rechazo de entradas incompatibles: las cuatro propiedades de una
distancia.

## 12.3 Los casos degenerados

```python
    def test_flat_and_empty_meshes_are_handled(self):
        plano = compare.medir([(0.0, 0.0, 7.0)] * 4, triangulos=2, secciones=1, franjas=4)
        self.assertAlmostEqual(plano.alto, 0.0)
        self.assertEqual(plano.perfil, (1.0, 0.0, 0.0, 0.0))

        with self.assertRaises(ValueError):
            compare.medir([], triangulos=0, secciones=1)
        with self.assertRaises(ValueError):
            compare.medir([(0.0, 0.0, float("nan"))], triangulos=0, secciones=1)
```

Malla plana (división por cero), malla vacía, coordenada no finita. Los tres son casos que **ocurren
de verdad**: una malla plana es un plano; una vacía es un asset que no cargó; un NaN sale de una
operación geométrica degenerada.

## 12.4 Mutation testing: la prueba de que el test discrimina

Ésta es la técnica más valiosa y la menos usada en general.

**El problema**: un test que pasa no prueba que el test *sirva*. Puede estar verificando algo trivial
que siempre se cumple.

**La técnica**: romper deliberadamente el código y verificar que el test falla.

Ejemplo real. El ejemplo de árbol de dos niveles tiene un test que afirma que la escala se hereda en
cascada entre niveles:

```python
            # La escala cae en cascada: tronco → rama → ramita. El helper de runtime guarda el
            # ÚLTIMO resultado por verbo, así que acá vuelven las 104 ramitas del nivel 2.
            ramitas = tools.dato_producido_runtime("branch_from_frames")
            self.assertEqual(len(ramitas.paths), 104)
            escalas = [path.scale for path in ramitas.paths]
            promedio = sum(escalas) / len(escalas)
            nominal_l2 = float(document["nodes"]["l2_transform"]["params"]["scale"])
            nominal_l1 = float(document["nodes"]["l1_transform"]["params"]["scale"])
            # Sin herencia el promedio daría el nominal del nivel 2 (0.62); con herencia da el
            # producto de los dos niveles. Eso es lo que separa una jerarquía real de dos cadenas
            # independientes pegadas una al lado de la otra.
            self.assertAlmostEqual(promedio, nominal_l1 * nominal_l2, delta=0.05)
            self.assertLess(promedio, nominal_l2)
```

Y la verificación de que el test discrimina, ejecutada como mutación:

```python
d["nodes"]["l2_transform"]["params"]["inherit_scale"] = "false"
# ... correr el test ...
# → AssertionError: 0.6114 != 0.5084 within 0.05 delta
```

Con la herencia rota, el promedio salta de 0.508 a 0.611 y el test **falla**. Eso demuestra que la
aserción no pasaba por casualidad.

**Cuándo aplicarla**: siempre que un test pase a la primera. Un test que pasa sin haberte hecho
trabajar es sospechoso.

## 12.5 El caso rota junto al caso sano

Ya visto en la sección 8.3, pero vale repetirlo como técnica general: junto a cada generador de caso
válido, mantener un generador del caso inválido.

```python
def mapa_botoo_ganable() -> SpaceGraph:
    """Un contrato de extracción SANO: la pista entrega el sello, con él se extrae."""

def mapa_botoo_roto() -> SpaceGraph:
    """El MISMO mapa pero con la pista amurallada: el sello es inalcanzable → NO ganable.

    Es el caso que prueba que el oráculo no es un sello de goma."""
```

Nótese que el roto se construye **derivando del sano** y quitando una sola arista. Eso garantiza que
la única diferencia entre ambos es el defecto que se quiere detectar.

## 12.6 El límite de la suite mockeada

Toda esta disciplina tiene un techo, y conviene tenerlo presente:

> Los tests con `unreal` mockeado verifican **tu lógica**, no **tu integración**.

Un nombre de API inventado, una firma cambiada entre versiones del motor, un tipo de retorno
inesperado: nada de eso lo ve un mock. Por eso Jam complementa con:

- `tools/check_unreal_api.py`, que corre contra un editor real;
- corridas del grafo completo en `UnrealEditor-Cmd -run=pythonscript`;
- y la aceptación explícita de que hay cosas que **sólo** se verifican en el editor interactivo (por
  ejemplo, `place`, que crashea en un commandlet porque el `PlacementSubsystem` necesita el editor de
  nivel).

Ser explícito sobre qué no se está verificando es parte de la honestidad del sistema.

---

# 13. Receta: escribir un oráculo nuevo

## Paso 1 — Formulá la pregunta como algo medible

Mal: «¿el nivel se ve bien?»
Bien: «¿alguna pieza interpenetra a otra más de 1cm?»

Un oráculo no puede tener criterio estético. Si la pregunta no se puede responder con un número y un
umbral, no es un oráculo — es una revisión de arte.

**Test de la pregunta**: ¿dos personas distintas, con los mismos datos, llegarían al mismo veredicto?
Si no, reformulá.

## Paso 2 — Decidí qué datos mínimos necesita

Escribí la firma antes que el cuerpo:

```python
def verificar(pieza, otras, tol: float = geometry.TOL_CM) -> dict:
```

Si necesitás un actor de Unreal, parás y pensás de nuevo. Casi siempre alcanza con nombre, caja,
posición y ángulo. Si de verdad hace falta algo más, se agrega a `Pieza` — pero cada campo nuevo es
una atadura al motor.

## Paso 3 — Escribí el núcleo puro

En un archivo `oracle_<algo>.py`, con `from __future__ import annotations`, importando sólo
`geometry` y la librería estándar. **Cero `import unreal`.**

Las tres funciones canónicas:

```python
def verificar(...) -> dict:       # todos los números, incluso los que pasan
def es_ok(r: dict) -> bool:       # la regla de aprobación, en un solo lugar
def verificar_texto(...) -> str:  # [sujeto] VEREDICTO ✓/✗ — evidencia
```

## Paso 4 — Elegí la tolerancia y justificala en un comentario

Toda tolerancia es una decisión de producto. Documentá por qué:

```python
TOL_CM = 1.0                # menos que esto = tocándose, no interpenetrando
MAX_VECINO_CM = 50000.0     # semi-extensión > 500 m en un eje = escenografía de fondo
```

Una tolerancia sin justificación se convierte en un número mágico que nadie se anima a tocar.

## Paso 5 — Enumerá qué NO contar

Éste es el paso que separa un oráculo de juguete de uno usable. Preguntate:

- ¿Qué cumple técnicamente la condición pero no es el defecto que busco?
- ¿Qué va a disparar en el 100% de los casos y por lo tanto se va a ignorar?

Ejemplos reales del proyecto: la escenografía de fondo, el landscape, los proxies HLOD, el fantasma de
previsualización, el propio actor, el soporte de abajo. **Seis exclusiones** para que
«¿interpenetra?» sea útil.

## Paso 6 — Escribí el contra-ejemplo primero

Antes de dar el oráculo por terminado, construí el caso que **debe** fallar y verificá que falla. Si
no se te ocurre un caso que falle, tu oráculo probablemente siempre dice ✓.

## Paso 7 — Tests: casos, propiedades, degenerados, mutación

- casos concretos con números verificables a mano;
- propiedades invariantes (simetría, acotamiento, invariancia de escala);
- degenerados (vacío, plano, cero, NaN, infinito);
- una mutación que demuestre que el test discrimina.

## Paso 8 — Conectalo donde no se pueda olvidar

Un oráculo que hay que acordarse de correr no se corre. Opciones, de mejor a peor:

1. **Intercalado en el flujo** — como `mesh_compare`, que consume y devuelve la malla, así que vive
   dentro de la cadena de construcción;
2. **Automático después de la acción** — como el veredicto de `place`, que se imprime siempre;
3. **Un botón** — como `Compile`;
4. **Un script que hay que invocar** — como `check_unreal_api.py`. Aceptable sólo si necesita un
   entorno especial.

## Paso 9 — Escribí el mensaje para quien lo va a leer a las 2 a.m.

```
[Casa_03] FOOTPRINT ROTO ✗ — descentrado (12.0, 3.0)cm; planta cambió (28.0, 5.0)cm (angosta/ensancha el hueco)
```

Qué pieza, qué falló, cuánto, y —entre paréntesis— por qué importa. Si podés, agregá la salida:

```
    → «normalize» lo arregla de una vez para todas las herramientas
```

---

# 14. Tabla resumen de todos los oráculos

## Oráculos de escena

| Módulo | Entrada | Mide | Veredicto ✓ |
|---|---|---|---|
| `oracle_placement` | `Pieza` + vecinos | bounds, interpenetración | bounds válidos y sin clavarse |
| `oracle_physics` | `Pieza` + soportes | gap contra el soporte | `apoyado` (\|gap\| ≤ tol) |
| `oracle_snap` | `Pieza` (+ objetivo) | múltiplos de grilla; gap de cara | `en_grilla` / `al_ras` |
| `oracle_scatter` | lista de `Pieza` + región | cantidad, contención, pares, cobertura | los cuatro |
| `oracle_pared` | `build` dict | desvío de juntas, cobertura | continua y cubre |
| `oracle_reemplazo` | `Pieza` + footprint | centro, base, planta | preserva las tres |
| `oracle_espacio` | `SpaceGraph` | alcanzabilidad con llaves | `solvable` |
| `pivot.diagnostico` | `AABB` + pivote | posición normalizada 0..1 | `tileable` |
| `spline_core` | colocaciones + largo | solapes, cobertura | sin solape y ≥90% |
| `compare` | posiciones + conteos | 8 métricas de forma | todas en tolerancia |

## Oráculos de contrato

| Mecanismo | Cuándo | Qué garantiza |
|---|---|---|
| `graph.compilar` | antes de Run | el grafo es ejecutable; nada se toca si no |
| `Flow.validar` | antes de evaluar | ninguna op desconocida degrada a `[]` |
| `check_unreal_api` | manual, editor vivo | cada API que Jam llama existe |
| `_preview` | durante Run | rollback total ante excepción |
| `LoadGraphJson` | al abrir archivo | un JSON inválido no destruye el canvas |

## Los números del sistema

- **10** oráculos de escena y forma
- **5** mecanismos de contrato
- **116** tests, ~1 segundo
- **50** llamadas distintas a la API de Unreal, todas verificadas
- **~60** líneas de matemática pura en `geometry.py` que sostienen 7 oráculos

---

# 15. Glosario

**AABB** — *Axis-Aligned Bounding Box*. Caja alineada a los ejes del mundo que contiene una malla. En
Jam: `AABB(origin, extent)`, donde `extent` es la **semi**-extensión.

**Adaptador** — la capa que traduce entre el motor y los datos puros. En Jam, `jam/ue.py`. Es el único
lugar que importa `unreal` para los oráculos de escena.

**Cerebro** — la lógica que razona sobre datos puros, sin dependencia del motor. `geometry.py`,
`oracle_*.py`, `compare.py`, `curve.py`.

**Cobertura** (scatter) — fracción de celdas de una grilla NxN sobre la región objetivo que contienen
al menos una instancia. Detecta amontonamiento.

**Contra-ejemplo** — el caso construido deliberadamente para que el oráculo lo rechace. Sin él, no hay
evidencia de que el oráculo discrimine.

**Determinista** — mismo input, mismo veredicto, siempre.

**Eje separador** — si en algún eje las proyecciones de dos cajas no se superponen, las cajas no se
tocan. Base del cálculo de interpenetración.

**Escenografía de fondo** — actor cuya caja envuelve el mapa (SkySphere, niebla). Se excluye de los
tests de interpenetración porque si no todo choca con todo.

**Footprint** — la huella de un blockout: centro XY, base Z y semi-extensiones. Lo que un reemplazo
debe preservar.

**Mangler** — el generador de nombres de los bindings de Python de Unreal. Parte las siglas: `UVs` →
`u_vs`, `IDs` → `i_ds`.

**Mutation testing** — romper el código a propósito para verificar que el test falla. Prueba que el
test discrimina.

**Oráculo** — función determinista que mide un artefacto y emite un veredicto verificable.

**Perfil de masa** — distribución de vértices por franja de altura, normalizada. Métrica de forma
invariante a escala.

**Pieza** — el dato mínimo que un oráculo de escena necesita de un actor:
`(nombre, aabb, location, yaw)`.

**Preflight** — validación completa previa a la ejecución, sin efectos secundarios.

**Preview / Bake / Discard** — ciclo transaccional: ejecutar provisionalmente, fijar o descartar.

**Semi-extensión** — la mitad del tamaño de la caja en un eje. Convención de Unreal (`BoxExtent`).

**Tileable** — un asset cuyo pivote permite repetirlo sin corregir: dentro de la malla, en la base, y
centrado o en esquina en planta.

**Tolerancia** — margen bajo el cual una diferencia no cuenta como defecto. Siempre una decisión de
producto que debe justificarse.

**Variación total** — distancia entre dos distribuciones: `Σ|a−b| / 2`. Acotada en [0, 1].

**Winnability** — propiedad de un mapa: existe una secuencia de acciones que lleva de la entrada a la
meta respetando las llaves.

---

# 16. Ejercicios

## Nivel 1 — Comprensión

1. Explicá por qué `penetracion()` devuelve el **mínimo** de los solapes y no el máximo. Construí un
   ejemplo numérico de dos cajas donde la diferencia importe.

2. `extent` es la semi-extensión. Si una caja tiene `extent.x = 150`, ¿cuánto mide de ancho? Reescribí
   la fórmula del solape usando ancho completo y comprobá que da lo mismo.

3. ¿Por qué el oráculo de física tiene cuatro estados en vez de un booleano `apoyado`? Dá un caso
   donde *flotando* y *hundido* requieran arreglos distintos.

4. En `verificar_ras`, ¿qué pasa si se elimina la condición `otros_solapan`? Construí dos piezas que
   pasarían el test incorrectamente.

5. El perfil de masa está normalizado por altura relativa. ¿Qué información se pierde con esa
   normalización, y cómo la recupera el oráculo?

## Nivel 2 — Análisis

6. La cobertura del scatter usa una grilla 3×3. Diseñá una distribución de 9 instancias que dé
   cobertura 100% pero que visualmente esté mal repartida. ¿Cómo mejorarías la métrica?

7. El oráculo de pared no puede usar AABB porque los segmentos van rotados. Proponé una verificación
   alternativa que sí use cajas, y explicá por qué la de las juntas es mejor.

8. `_razon()` devuelve `inf` cuando la referencia es cero y la generada no. Rastreá qué pasa con ese
   `inf` a través de `comparar()` hasta el texto final.

9. En `_preview`, se marcan los actores nuevos **antes** de borrar los anteriores. Describí
   exactamente qué estado quedaría si se invirtiera el orden y fallara el paso intermedio.

10. El verificador de API sugiere candidatos comparando nombres sin guiones bajos. ¿Qué falsos
    positivos podría producir esa heurística? ¿Importa?

## Nivel 3 — Diseño

11. **Escribí un oráculo de escala.** Dado un conjunto de piezas de un kit, verificá que ninguna tenga
    una escala no uniforme (`scale.x ≠ scale.y ≠ scale.z`), que rompe las normales. Definí la
    tolerancia y justificala. Incluí el contra-ejemplo.

12. **Escribí un oráculo de orientación.** Verificá que un conjunto de piezas colocadas sobre un
    spline tengan sus tangentes alineadas con la curva (ninguna girada al revés). Pensá cuál es el
    dato mínimo que necesitás y si alcanza con `Pieza`.

13. **Escribí un oráculo de densidad de UV.** Dado el área de superficie de una malla y el área que
    ocupa en el espacio UV, verificá que el *texel density* sea consistente entre piezas de un kit.
    ¿Qué tolerancia usarías y por qué?

14. **Ya resuelto en §9.9** — la silueta radial. Antes de leer esa sección, intentá responder por tu
    cuenta: ¿qué defecto detecta que el perfil vertical no puede detectar? Después compará tu
    respuesta con el test del cono y el cilindro. Variante abierta: la silueta usa el radio MÁXIMO
    por franja. ¿Qué cambiaría si usara el percentil 90? ¿Y la media?

15. **Diseñá el oráculo de silueta.** Proyectá la malla sobre un plano y compará la silueta resultante
    contra la de la referencia. Definí cómo representar la silueta, cómo compararlas, y qué tolerancia
    tiene sentido. ¿Qué detectaría que las seis métricas actuales no?

## Nivel 4 — Crítica

16. El oráculo de scatter es O(n²) en el número de instancias. Diseñá una versión con grilla espacial
    y estimá a partir de qué n vale la pena. ¿Cambia el veredicto o sólo el tiempo?

17. Las tolerancias de `compare.py` son anchas (±30% a ±50%). Argumentá a favor y en contra de
    estrecharlas. ¿Qué se gana y qué se rompe?

18. Toda la disciplina de tests puros tiene un techo: no ve la integración. Proponé un mecanismo
    adicional —distinto de los tres que Jam ya usa— para cerrar más ese hueco.

19. El principio anti-Goodhart dice que no hay que inyectarle al generador lo que se va a medir. En
    §9.8 los parámetros del árbol se ajustaron **leyendo el oráculo**, y §9.9 muestra el resultado:
    seis métricas en verde y un poste de 33 metros. Dado eso, ¿cómo debería ajustarse un generador
    sin caer en Goodhart? ¿Alcanza con tener más métricas, o el problema es de método?

20. El oráculo puede dar ✓ y aun así mostrar 0% vs 7% en la franja inferior del perfil. ¿Debería
    reportar «✓ con observaciones»? Diseñá ese tercer estado y decidí si vale la pena, sabiendo lo
    que cuenta §9.9 sobre lo que un verde realmente significa.

---

## Apéndice A — Cómo correr las verificaciones

**Suite completa** (headless, sin editor):

```bash
cd <plugin>/Content/Python
for t in tests/test_*.py; do PYTHONPATH=$PWD python3 "$t"; done
```

**Verificador de nombres de API** (necesita un editor):

```bash
UnrealEditor-Cmd <proyecto>.uproject -run=pythonscript \
    -script=<plugin>/tools/check_unreal_api.py \
    -RenderOffScreen -unattended -nosplash -stdout
```

> Nota: usar `-RenderOffScreen`, **no** `-nullrhi` (produce SIGFPE en UE 5.7.x).

**Correr un grafo completo y compararlo contra una referencia:**

```python
import json, unreal
from jam import api, mesh, tools

doc = json.loads(open("<ruta>/Ejemplo.jamgraph").read())
# `place` necesita el editor de nivel: se recorta para poder correr headless.
fuera = {"preview"}
doc["nodes"] = {k: v for k, v in doc["nodes"].items() if k not in fuera}
doc["edges"] = [e for e in doc["edges"] if e[0] not in fuera and e[2] not in fuera]

salida = json.loads(api.run_graph_json(json.dumps(doc)))
generada = tools.dato_producido_runtime("mesh_normals")
r = mesh.comparar(generada, "/TreeGen/Examples/Pine")
for linea in r["texto"].splitlines():
    unreal.log(linea)
```

## Apéndice B — Mapa de archivos

```
Content/Python/jam/
├── geometry.py          núcleo puro: AABB, penetración, soporte, fondo
├── ue.py                ADAPTADOR: actor → Pieza  (único con import unreal)
├── oracle_placement.py  interpenetración y bounds
├── oracle_physics.py    apoyado / flotando / hundido / sin suelo
├── oracle_snap.py       grilla y al ras
├── oracle_scatter.py    cantidad, contención, pares, cobertura
├── oracle_pared.py      continuidad de juntas sobre spline
├── oracle_reemplazo.py  preservación de footprint
├── oracle_espacio.py    winnability (BFS con llaves)
├── pivot.py             diagnóstico de pivote, concepto `tileable`
├── spline_core.py       continuidad por coordenada de arco
├── compare.py           oráculo de forma: 6 métricas + perfil de masa
├── graph.py             Compile / Preflight del grafo de verbos
├── flow.py              Preflight del grafo de flujo
├── panel.py             transacción Preview / Bake / Discard
└── mesh.py              adaptador de medición (medir, comparar)

tools/
└── check_unreal_api.py  verificador de nombres contra editor vivo

Content/Python/tests/
├── test_compare.py            11 tests del oráculo de forma
├── test_graph_preflight.py    20 tests del Preflight
├── test_flow_validation.py     8 tests de Flow.validar
├── test_preview_transaction.py 12 tests de la transacción
├── test_unreal_api_names.py    4 tests del verificador
├── test_mesh.py               47 tests de geometría y ejemplos
├── test_presets.py            11 tests de presets
└── test_nanite.py              3 tests
```

## Apéndice C — Las diez ideas que hay que retener

1. **Un oráculo mide, no corrige.** La separación entre crear y verificar es el diseño, no un
   accidente.
2. **El cerebro no importa el motor.** Datos puros adentro, veredicto afuera; el adaptador es
   minúsculo.
3. **Tres funciones**: `verificar` (números), `es_ok` (regla), `verificar_texto` (humano).
4. **El veredicto explica**: `[sujeto] ESTADO ✓/✗ — evidencia numérica`.
5. **Un oráculo ingenuo produce ruido**, y el ruido se ignora. El 80% del trabajo es saber qué no
   contar.
6. **Sin contra-ejemplo no hay oráculo.** Si no se te ocurre un caso que falle, probablemente siempre
   dice ✓.
7. **Fallar ruidosamente le gana a degradar en silencio.** Un `try/except` amplio esconde bugs
   durante meses.
8. **Localizar le gana a cuantificar.** El conteo dice cuánto; el perfil dice dónde. Lo segundo es
   accionable.
9. **Los tests mockeados verifican tu lógica, no tu integración.** Hace falta una capa que toque el
   motor real.
9b. **Un verde no es una garantía: es la ausencia de una refutación.** Sólo dice que las métricas que
   tenés no vieron nada. Cuando el ojo humano encuentra lo que se les escapó, eso se convierte en la
   métrica siguiente.
10. **Un oráculo que hay que acordarse de correr no se corre.** Intercalalo en el flujo.
