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
