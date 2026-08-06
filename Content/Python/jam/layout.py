"""Posiciones de nodos: alinear y distribuir. Cerebro PURO (cero `import unreal`).

Es aritmética sobre rectángulos, y por eso mismo va acá y no en Slate: son las mismas cuentas con
cualquier pan, cualquier zoom y cualquier DPI, y se testean sin abrir el editor. El C++ manda los
rectángulos, recibe posiciones y las aplica.

Un nodo es `{"id", "x", "y", "w", "h"}` — `x/y` es su esquina superior izquierda, en coordenadas de
MODELO (antes del pan y del zoom).

**A qué se alinea.** Al borde del cuadro que envuelve la selección, no a «el último que
seleccionaste». Es lo que hace Grasshopper, y tiene una ventaja concreta: el resultado depende sólo
de lo que se ve, así que alinear dos veces seguidas da lo mismo (es idempotente) y no hay que
acordarse en qué orden se hizo clic.
"""

from __future__ import annotations

MODOS = ("izquierda", "derecha", "arriba", "abajo", "centro-x", "centro-y")
EJES = ("x", "y")


def _rect(n: dict) -> tuple[float, float, float, float]:
    return (float(n["x"]), float(n["y"]), float(n.get("w", 0.0)), float(n.get("h", 0.0)))


def alinear(nodos: list[dict], modo: str) -> dict[str, tuple[float, float]]:
    """`{id: (x, y)}` con la posición de cada nodo después de alinear.

    Devuelve TODOS los nodos, también los que no se movieron: así el que aplica no tiene que
    adivinar cuáles cambiaron, y comparar el resultado contra la entrada es una sola operación.
    """
    if modo not in MODOS:
        raise ValueError(f"modo desconocido: {modo!r} (esperaba uno de {MODOS})")
    if len(nodos) < 2:
        return {str(n["id"]): (float(n["x"]), float(n["y"])) for n in nodos}

    izq = min(_rect(n)[0] for n in nodos)
    der = max(_rect(n)[0] + _rect(n)[2] for n in nodos)
    arr = min(_rect(n)[1] for n in nodos)
    aba = max(_rect(n)[1] + _rect(n)[3] for n in nodos)

    salida: dict[str, tuple[float, float]] = {}
    for n in nodos:
        x, y, w, h = _rect(n)
        if modo == "izquierda":
            x = izq
        elif modo == "derecha":
            x = der - w
        elif modo == "arriba":
            y = arr
        elif modo == "abajo":
            y = aba - h
        elif modo == "centro-x":
            # centros alineados en X = quedan en una COLUMNA (es el «align center horizontally»
            # de Blueprint: mueve en X, no en Y)
            x = (izq + der) * 0.5 - w * 0.5
        elif modo == "centro-y":
            y = (arr + aba) * 0.5 - h * 0.5
        salida[str(n["id"])] = (x, y)
    return salida


def distribuir(nodos: list[dict], eje: str) -> dict[str, tuple[float, float]]:
    """Reparte los nodos con el MISMO HUECO entre uno y el siguiente, sobre `eje` («x» o «y»).

    Los dos extremos no se tocan: definen el tramo. Con menos de 3 nodos no hay nada que repartir.

    Se igualan los HUECOS, no los centros. Con nodos de distinto tamaño —que es el caso normal en
    Jam, donde un nodo con 6 params es el triple de alto que uno sin params— igualar los centros
    deja huecos visiblemente distintos aunque los números digan que está bien.
    """
    if eje not in EJES:
        raise ValueError(f"eje desconocido: {eje!r} (esperaba uno de {EJES})")
    if len(nodos) < 3:
        return {str(n["id"]): (float(n["x"]), float(n["y"])) for n in nodos}

    i, j = (0, 2) if eje == "x" else (1, 3)   # índices de (x,y,w,h) para posición y tamaño
    orden = sorted(nodos, key=lambda n: _rect(n)[i])

    inicio = _rect(orden[0])[i]
    ultimo = _rect(orden[-1])
    fin = ultimo[i] + ultimo[j]
    ocupado = sum(_rect(n)[j] for n in orden)
    hueco = (fin - inicio - ocupado) / (len(orden) - 1)

    salida: dict[str, tuple[float, float]] = {}
    cursor = inicio
    for n in orden:
        r = _rect(n)
        pos = [r[0], r[1]]
        pos[0 if eje == "x" else 1] = cursor
        salida[str(n["id"])] = (pos[0], pos[1])
        cursor += r[j] + hueco
    return salida


def en_marco(nodos: list[dict], x0: float, y0: float, x1: float, y1: float) -> list[str]:
    """Ids de los nodos que TOCAN el rectángulo (marquee). Cruzar alcanza, no hace falta contener.

    Los dos puntos vienen como se arrastró, en cualquier orden: se normalizan. Un rectángulo de área
    cero (clic sin arrastre) no toca nada, que es lo que hace que un clic en el fondo limpie la
    selección en vez de seleccionar lo que esté debajo del cursor.
    """
    ax, bx = (x0, x1) if x0 <= x1 else (x1, x0)
    ay, by = (y0, y1) if y0 <= y1 else (y1, y0)
    if ax == bx or ay == by:
        return []
    tocados = []
    for n in nodos:
        x, y, w, h = _rect(n)
        if x < bx and x + w > ax and y < by and y + h > ay:
            tocados.append(str(n["id"]))
    return tocados


def marco_de(nodos: list[dict]) -> tuple[float, float, float, float]:
    """AABB `(x0, y0, x1, y1)` de los nodos — el encuadre de `F` y de la captura del grafo."""
    if not nodos:
        return (0.0, 0.0, 0.0, 0.0)
    return (min(_rect(n)[0] for n in nodos),
            min(_rect(n)[1] for n in nodos),
            max(_rect(n)[0] + _rect(n)[2] for n in nodos),
            max(_rect(n)[1] + _rect(n)[3] for n in nodos))


#: Huecos del auto-layout, en unidades de MODELO. El horizontal es generoso porque entre columna y
#: columna es donde viajan los cables: apretarlas hace que los splines se superpongan a los nodos.
#: Paso de la grilla, en unidades de MODELO. Es el MISMO 24 que dibuja `SJamGridLayer` en el .cpp;
#: los ata `PasoDeLaGrillaEnElCppTests`, porque ajustar a una grilla distinta de la que se ve sería
#: peor que no ajustar nada.
PASO_GRILLA = 24.0

HUECO_X = 90.0
HUECO_Y = 34.0


def auto(nodos: list[dict], aristas: list[tuple[str, str]]) -> dict[str, tuple[float, float]]:
    """Acomoda el grafo entero por capas topológicas: `{id: (x, y)}`.

    Es el *layout por capas* de Graphviz/Blueprint llevado a lo mínimo que rinde: **el flujo se lee
    de izquierda a derecha**, cada nodo a la derecha de todo lo que lo alimenta. Un grafo que creció
    a los saltos deja de tener cables que van para atrás.

    Tres pasos, y el del medio es el que hace que sirva:

    1. **Capa** = camino más largo desde una fuente. Con el más largo (y no el más corto) un nodo
       nunca queda a la izquierda de algo que lo alimenta, que es justo el cable para atrás que se
       quiere eliminar.
    2. **Orden dentro de la capa** = baricentro de sus predecesores, dos pasadas. Sin esto las capas
       salen bien pero los cables se cruzan entre ellas; es la heurística de Sugiyama, y dos pasadas
       ya sacan la mayoría de los cruces sin volverse impredecible.
    3. **Coordenadas** con el alto REAL de cada nodo. Los nodos de Jam no miden todos igual —depende
       de cuántos params tiene el verbo— y espaciar por una altura fija los encimaría.

    El resultado se ancla en la esquina superior izquierda de lo que había: acomodar no puede
    mandar el grafo a mil unidades de donde lo estabas mirando.

    Un CICLO no revienta: los nodos que no se pueden ordenar caen a la última capa. El Compile de
    Jam ya rechaza los ciclos, pero acomodar es un gesto de edición y tiene que sobrevivir a un
    grafo a medio cablear.
    """
    if not nodos:
        return {}

    por_id = {str(n["id"]): n for n in nodos}
    # Sólo las aristas con las DOS puntas adentro: al acomodar una selección, un cable que sale
    # hacia afuera no dice nada sobre el orden interno.
    pares = [(str(a), str(b)) for a, b in aristas
             if str(a) in por_id and str(b) in por_id and str(a) != str(b)]

    preds: dict[str, list[str]] = {k: [] for k in por_id}
    sucs: dict[str, list[str]] = {k: [] for k in por_id}
    for a, b in pares:
        if b not in sucs[a]:
            sucs[a].append(b)
        if a not in preds[b]:
            preds[b].append(a)

    # ---- 1. capa por camino más largo (Kahn; lo que quede sin resolver es un ciclo) ----
    grado = {k: len(preds[k]) for k in por_id}
    capa = {k: 0 for k in por_id}
    listos = [k for k in por_id if grado[k] == 0]
    vistos = 0
    while listos:
        k = listos.pop(0)
        vistos += 1
        for s in sucs[k]:
            capa[s] = max(capa[s], capa[k] + 1)
            grado[s] -= 1
            if grado[s] == 0:
                listos.append(s)
    if vistos < len(por_id):
        # Ciclo: los no resueltos van al fondo, todos juntos, en vez de tirar una excepción en
        # medio de un gesto de edición.
        fondo = max(capa.values(), default=0) + 1
        for k in por_id:
            if grado[k] > 0:
                capa[k] = fondo

    columnas: dict[int, list[str]] = {}
    for k in sorted(por_id, key=lambda i: (capa[i], float(por_id[i].get("y", 0.0)), i)):
        columnas.setdefault(capa[k], []).append(k)

    # ---- 2. baricentro: dos pasadas para descruzar ----
    for _ in range(2):
        for c in sorted(columnas)[1:]:
            fila = {k: i for i, k in enumerate(columnas[c - 1])}
            def bary(k: str) -> float:
                previos = [fila[p] for p in preds[k] if p in fila]
                return sum(previos) / len(previos) if previos else float(columnas[c].index(k))
            columnas[c].sort(key=lambda k: (bary(k), k))

    # ---- 3. coordenadas, con el alto real de cada nodo ----
    x0, y0, _x1, _y1 = marco_de(nodos)
    pos: dict[str, tuple[float, float]] = {}
    x = x0
    for c in sorted(columnas):
        ids = columnas[c]
        ancho = max((_rect(por_id[k])[2] for k in ids), default=0.0)
        # Cada columna centrada contra la más alta: un grafo con una columna de 1 nodo y otra de 8
        # se lee mucho peor con todo pegado arriba.
        alto = sum(_rect(por_id[k])[3] for k in ids) + HUECO_Y * max(0, len(ids) - 1)
        altos = [sum(_rect(por_id[i])[3] for i in columnas[o]) + HUECO_Y * max(0, len(columnas[o]) - 1)
                 for o in columnas]
        y = y0 + (max(altos, default=0.0) - alto) * 0.5
        for k in ids:
            pos[k] = (x, y)
            y += _rect(por_id[k])[3] + HUECO_Y
        x += ancho + HUECO_X
    return pos


def ajustar_a_grilla(nodos: list[dict], paso: float = PASO_GRILLA) -> dict[str, tuple[float, float]]:
    """`{id: (x, y)}` con cada nodo llevado al cruce de grilla más cercano.

    Ajusta la ESQUINA superior izquierda, que es el ancla con la que ya trabajan alinear, distribuir
    y el auto-layout. Ajustar el centro haría que dos nodos de distinta altura —y en Jam la altura
    depende de cuántos params tiene el verbo— terminaran con sus bordes desalineados, que es
    justamente lo que uno quiere arreglar al ajustar a la grilla.

    Es idempotente: ajustar dos veces da lo mismo. Y devuelve TODOS los nodos, también los que no se
    movieron, para que el que aplica no tenga que adivinar cuáles cambiaron.
    """
    if paso <= 0.0:
        raise ValueError("el paso de la grilla tiene que ser positivo")
    salida: dict[str, tuple[float, float]] = {}
    for n in nodos:
        x, y, _w, _h = _rect(n)
        salida[str(n["id"])] = (round(x / paso) * paso, round(y / paso) * paso)
    return salida


#: Radio de agarre de un cable, en unidades de MODELO. Generoso a propósito: un cable dibujado mide
#: 2,6 px de grueso y pedir precisión de píxel para agarrarlo lo volvería inusable.
AGARRE_CABLE = 14.0


def _punto_del_cable(ax: float, ay: float, bx: float, by: float, t: float) -> tuple[float, float]:
    """Un punto del cable en `t ∈ [0,1]`.

    Es la MISMA curva que dibuja `SJamWireLayer`: un Hermite cúbico con tangentes horizontales de
    largo `max(50, |bx-ax| * 0.6)`. Reproducirla importa — si el hit-test usara la recta entre las
    puntas, agarrar un cable por la panza fallaría justo donde se lo ve.
    """
    dx = max(50.0, abs(bx - ax) * 0.6)
    t2, t3 = t * t, t * t * t
    h00 = 2 * t3 - 3 * t2 + 1
    h10 = t3 - 2 * t2 + t
    h01 = -2 * t3 + 3 * t2
    h11 = t3 - t2
    return (h00 * ax + h10 * dx + h01 * bx + h11 * dx,
            h00 * ay + h01 * by)


def cable_mas_cercano(x: float, y: float, cables: list[dict], *,
                      agarre: float = AGARRE_CABLE, muestras: int = 32) -> dict | None:
    """El cable bajo el punto `(x, y)`, o `None` si no hay ninguno cerca.

    Devuelve `{"cable", "x", "y", "t", "distancia"}` — el punto devuelto está SOBRE la curva, no
    donde se hizo clic, para que un punto de paso nazca pegado al cable y no saltando.

    Un cable es `{"id", "ax", "ay", "bx", "by"}` en coordenadas de MODELO. Se muestrea la curva
    porque la distancia exacta de un punto a un cúbico no tiene forma cerrada simple, y para agarrar
    un cable con el mouse 32 muestras sobran: el error máximo queda muy por debajo del radio de
    agarre.

    Con varios cables encimados gana el MÁS CERCANO, que es el que se ve arriba.
    """
    if agarre <= 0.0:
        raise ValueError("el radio de agarre tiene que ser positivo")
    mejor = None
    for c in cables:
        ax, ay = float(c["ax"]), float(c["ay"])
        bx, by = float(c["bx"]), float(c["by"])
        for i in range(muestras + 1):
            t = i / muestras
            px, py = _punto_del_cable(ax, ay, bx, by, t)
            d = ((px - x) ** 2 + (py - y) ** 2) ** 0.5
            if d <= agarre and (mejor is None or d < mejor["distancia"]):
                mejor = {"cable": str(c["id"]), "x": px, "y": py, "t": t, "distancia": d}
    return mejor
