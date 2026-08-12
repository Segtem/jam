"""Buffers puros para tender una superficie entre varias curvas (el «Loft» del tutorial).

No importa ``unreal``: el adaptador fino de :mod:`jam.mesh` traduce estas tuplas a Geometry Script,
igual que con la cinta.

**Ruled Surface y Loft son el mismo verbo acá.** Grasshopper los separa porque el reglado entre dos
curvas es más barato de resolver en NURBS; en una malla la diferencia desaparece —son las mismas
filas de cuadriláteros— y tener dos nodos que hacen lo mismo obliga a elegir entre ellos sin ningún
criterio. Tender entre dos curvas ES el reglado.
"""

from __future__ import annotations

import math

from .curve_sampling_core import resample_points
# El winding y la convención de normales se COMPARTEN con la cinta, no se reescriben. Es el código
# que ya costó un tutorial invisible y una sesión entera de diagnóstico (`investiga_winding_ribbon_58`):
# duplicarlo acá sería duplicar la posibilidad de que una de las dos superficies quede dada vuelta
# sin que nada lo relacione con la otra.
from .ribbon_core import _normals


def _largo(puntos) -> float:
    return sum(math.dist(a, b) for a, b in zip(puntos, puntos[1:]))


def _hay_que_dar_vuelta(anterior, siguiente) -> bool:
    """¿La curva siguiente está recorrida al revés que la anterior?

    Se compara cuánto miden los travesaños —las rectas que unen muestra con muestra— contra cuánto
    medirían con la segunda curva invertida. Si invertirla los acorta, las dos curvas van en
    sentidos opuestos y la superficie saldría cruzada en X.

    Es una MEDIDA y no una suposición sobre cómo las dibujó el usuario: dos curvas que alguien trazó
    en direcciones distintas son un caso normal, no un error, y pedirle que las redibuje sería
    cobrarle a él un problema que la herramienta puede ver sola. Se corrige y se informa, como
    `miter_limit` cae a bevel en vez de estirar la esquina en silencio.
    """
    derecho = sum(math.dist(a, b) for a, b in zip(anterior, siguiente))
    invertido = sum(math.dist(a, b) for a, b in zip(anterior, tuple(reversed(siguiente))))
    return invertido < derecho


def loft_buffers(curvas, *, samples: int = 16, uv_scale: float = 200.0) -> dict:
    """Vértices, triángulos, normales y UV0 de la superficie que pasa por todas las curvas.

    Todas las curvas se remuestrean a la MISMA cantidad de puntos por longitud de arco: sin eso no
    existe la correspondencia «muestra i de una con muestra i de la otra», que es lo que define un
    loft. Remuestrear por arco y no por índice hace que una curva de 3 puntos y otra de 40 tiendan
    parejo en vez de amontonar la superficie donde la segunda tenía más detalle.

    Devuelve además ``invertidas``: cuántas curvas hubo que dar vuelta para que el recorrido fuera
    coherente. Es información, no un error — pero si aparece y el usuario no lo esperaba, explica
    por qué la superficie salió como salió.
    """
    try:
        samples = int(samples)
        uv_scale = float(uv_scale)
    except (TypeError, ValueError, OverflowError):
        return {"error": "mesh_loft recibió samples o uv_scale inválidos."}
    if samples < 2 or samples > 512:
        return {"error": "samples de mesh_loft debe estar entre 2 y 512."}
    if not math.isfinite(uv_scale) or uv_scale <= 0.0:
        return {"error": "uv_scale de mesh_loft tiene que ser mayor que cero."}

    entradas = [tuple(tuple(float(c) for c in punto) for punto in curva) for curva in curvas]
    if len(entradas) < 2:
        return {"error": "mesh_loft necesita al menos dos curvas para tender entre ellas."}
    if len(entradas) * samples > 4096:
        return {"error": "mesh_loft no puede producir más de 4096 vértices."}

    filas = []
    for curva in entradas:
        if len(curva) < 2:
            return {"error": "mesh_loft recibió una curva de menos de dos puntos."}
        remuestreada = resample_points(curva, count=samples)
        if "error" in remuestreada:
            return {"error": remuestreada["error"].replace("curve_resample", "mesh_loft")}
        filas.append(tuple(remuestreada["points"]))

    invertidas = 0
    for i in range(1, len(filas)):
        if _hay_que_dar_vuelta(filas[i - 1], filas[i]):
            filas[i] = tuple(reversed(filas[i]))
            invertidas += 1

    # Dos filas pegadas que caen exactamente encima no tienen superficie entre ellas: cada
    # cuadrilátero sería un triángulo de área cero, y sus normales las decidiría el redondeo.
    for i in range(1, len(filas)):
        if all(math.dist(a, b) < 1e-6 for a, b in zip(filas[i - 1], filas[i])):
            return {"error": "mesh_loft recibió dos curvas superpuestas: no hay superficie entre ellas."}

    vertices = tuple(punto for fila in filas for punto in fila)

    def indice(fila, columna):
        return fila * samples + columna

    # El MISMO orden que la cinta. En sus términos, la fila 0 es el borde izquierdo y la fila 1 el
    # derecho, y la columna avanza a lo largo del recorrido; con esa correspondencia los índices de
    # abajo son literalmente los de `ribbon_buffers`. Que las dos superficies se dibujen del mismo
    # lado no es casualidad: es la misma regla escrita una sola vez.
    triangles = tuple(
        triangulo
        for fila in range(len(filas) - 1)
        for columna in range(samples - 1)
        for triangulo in (
            (indice(fila, columna), indice(fila, columna + 1), indice(fila + 1, columna)),
            (indice(fila + 1, columna), indice(fila, columna + 1), indice(fila + 1, columna + 1)),
        )
    )
    normals = _normals(vertices, triangles)
    if normals is None:
        return {"error": "mesh_loft produjo un triángulo degenerado; revisá las curvas."}

    # U recorre la curva (distancia real acumulada) y V cruza de una curva a la otra, para que una
    # textura mantenga escala aunque las curvas midan distinto.
    us = []
    for fila in filas:
        acumulado = [0.0]
        for a, b in zip(fila, fila[1:]):
            acumulado.append(acumulado[-1] + math.dist(a, b))
        us.append(acumulado)
    v_total = max(len(filas) - 1, 1)
    uv0 = tuple(
        (us[fila][columna] / uv_scale, fila / v_total)
        for fila in range(len(filas))
        for columna in range(samples)
    )

    largo_max = max(fila[-1] for fila in us)
    return {
        "vertices": vertices,
        "triangles": triangles,
        "normals": normals,
        "uv0": uv0,
        "length_u": largo_max,
        "invertidas": invertidas,
        "filas": len(filas),
    }
