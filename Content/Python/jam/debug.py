"""Ayudantes visuales del Graph — PUROS (0 `import unreal`).

El oráculo dice cuánto se parece el resultado a una referencia, pero no deja **ver** lo que pasa a
mitad de la cadena. Si los frames apuntan mal, o una máscara mató los puntos equivocados, no hay
manera de darse cuenta hasta que la malla final sale rara — y para entonces ya no se sabe qué nodo
tuvo la culpa.

Estos nodos convierten un stream en GEOMETRÍA que se ve: ejes y flechas sobre cada frame, marcadores
sobre cada punto. Salen por un cable `M` como cualquier otra malla, así que se pueden mergear con el
resultado real, hornear, o colocar sueltos y descartar después.

Convención de ejes, la misma que usan los verbos de malla al orientar (`make_rot_from_xz`):

    X (rojo)   = tangent   — hacia dónde crece
    Y (verde)  = lateral   — cross(tangent, outward)
    Z (azul)   = outward   — hacia afuera
"""

from __future__ import annotations

import math
from collections import namedtuple


# Un tramo a dibujar: de dónde sale, hacia dónde, cuánto mide y qué eje representa (0=X, 1=Y, 2=Z).
Eje = namedtuple("Eje", "origen direccion largo eje")
# Un marcador de punto: dónde y de qué tamaño (el peso de la máscara ya aplicado).
Marcador = namedtuple("Marcador", "origen tamano peso")

MAX_ELEMENTOS = 4096


def _normalizar(vector) -> tuple[float, float, float]:
    largo = math.sqrt(sum(c * c for c in vector))
    if largo < 1e-8:
        return (0.0, 0.0, 0.0)
    return tuple(c / largo for c in vector)


def _cruz(a, b) -> tuple[float, float, float]:
    return (a[1] * b[2] - a[2] * b[1],
            a[2] * b[0] - a[0] * b[2],
            a[0] * b[1] - a[1] * b[0])


def ejes_de_frames(frames, *, largo: float = 30.0, escalar_con_frame: bool = True,
                   solo_tangente: bool = False) -> list[Eje]:
    """Tres ejes (o sólo la tangente) por cada frame de un stream ``F``.

    Con `escalar_con_frame`, el largo de los ejes sigue la escala del frame: así se ve de un vistazo
    si la escala cae en cascada entre niveles o si una máscara la está manejando.
    """
    frames = list(frames or [])
    if not frames:
        raise ValueError("debug_frames necesita un stream F con al menos un frame.")
    if largo <= 0.0 or not math.isfinite(largo):
        raise ValueError("largo debe ser un número finito mayor que cero.")
    if len(frames) * 3 > MAX_ELEMENTOS:
        raise ValueError(f"debug_frames no puede dibujar más de {MAX_ELEMENTOS // 3} frames.")

    salida = []
    for frame in frames:
        tangente = _normalizar(frame.tangent)
        hacia_afuera = _normalizar(frame.outward)
        if tangente == (0.0, 0.0, 0.0):
            continue
        lateral = _normalizar(_cruz(tangente, hacia_afuera))
        if lateral == (0.0, 0.0, 0.0):
            # tangente y outward paralelos: se elige cualquier perpendicular estable.
            referencia = (1.0, 0.0, 0.0) if abs(tangente[0]) < 0.9 else (0.0, 1.0, 0.0)
            lateral = _normalizar(_cruz(tangente, referencia))
            hacia_afuera = _normalizar(_cruz(lateral, tangente))
        medida = largo * (float(getattr(frame, "scale", 1.0)) if escalar_con_frame else 1.0)
        if medida <= 0.0:
            continue
        origen = tuple(float(c) for c in frame.position)
        salida.append(Eje(origen, tangente, medida, 0))
        if not solo_tangente:
            salida.append(Eje(origen, lateral, medida * 0.6, 1))
            salida.append(Eje(origen, hacia_afuera, medida * 0.6, 2))
    if not salida:
        raise ValueError("ningún frame tenía una tangente utilizable.")
    return salida


def tramos_de_curvas(paths, *, marcar_extremos: bool = True) -> list[Eje]:
    """Segmentos que dibujan cada polilínea ``S``, más la dirección en la que corre.

    Una curva es invisible hasta que algo la barre. Ver el recorrido Y el sentido explica de una
    cuáles ramas salieron para el lado equivocado, o dónde se despegó una junta.

    El índice de color reutiliza el de los ejes: 0 = cuerpo, 1 = arranque, 2 = punta.
    """
    paths = list(paths or [])
    if not paths:
        raise ValueError("debug_curve necesita una curva S con al menos una polilínea.")
    total = sum(max(0, len(p.points) - 1) for p in paths)
    if total == 0:
        raise ValueError("las curvas de debug_curve no tienen segmentos.")
    if total + len(paths) * 2 > MAX_ELEMENTOS:
        raise ValueError(f"debug_curve no puede dibujar más de {MAX_ELEMENTOS} segmentos.")

    salida = []
    for path in paths:
        puntos = [tuple(float(c) for c in p) for p in path.points]
        for actual, siguiente in zip(puntos, puntos[1:]):
            delta = tuple(b - a for a, b in zip(actual, siguiente))
            largo = math.sqrt(sum(c * c for c in delta))
            if largo < 1e-6:
                continue
            salida.append(Eje(actual, _normalizar(delta), largo, 0))
        if marcar_extremos and len(puntos) >= 2:
            arranque = _normalizar(tuple(b - a for a, b in zip(puntos[0], puntos[1])))
            punta = _normalizar(tuple(b - a for a, b in zip(puntos[-2], puntos[-1])))
            referencia = max(1.0, math.dist(puntos[0], puntos[-1]) * 0.08)
            salida.append(Eje(puntos[0], arranque, referencia, 1))
            salida.append(Eje(puntos[-1], punta, referencia, 2))
    return salida


def perfil_de_serie(valores, *, ancho: float = 200.0, alto: float = 100.0) -> list[Eje]:
    """Dibuja una serie ``N[]`` como un gráfico en el plano XZ, más su línea de base.

    Un `Graph Curve` maneja el taper de un pipe y el largo de las ramas, y hasta ahora se editaba a
    ciegas: los números no dicen qué forma tienen. Esto lo hace mirable.
    """
    valores = [float(v) for v in (valores or [])]
    if len(valores) < 2:
        raise ValueError("debug_series necesita una serie N[] con al menos dos valores.")
    if ancho <= 0.0 or alto <= 0.0 or not math.isfinite(ancho) or not math.isfinite(alto):
        raise ValueError("ancho y alto deben ser números finitos mayores que cero.")
    if not all(math.isfinite(v) for v in valores):
        raise ValueError("la serie contiene un valor no finito.")

    tope = max(abs(v) for v in valores) or 1.0
    def punto(indice):
        return (ancho * indice / (len(valores) - 1), 0.0, alto * valores[indice] / tope)

    salida = [Eje((0.0, 0.0, 0.0), (1.0, 0.0, 0.0), ancho, 1)]   # base
    for indice in range(len(valores) - 1):
        a, b = punto(indice), punto(indice + 1)
        delta = tuple(y - x for x, y in zip(a, b))
        largo = math.sqrt(sum(c * c for c in delta))
        if largo > 1e-6:
            salida.append(Eje(a, _normalizar(delta), largo, 0))
    return salida


def espinas_de_normales(posiciones, normales, *, largo: float = 8.0,
                        cada: int = 1) -> list[Eje]:
    """Una espina por vértice a lo largo de su normal: delata normales dadas vuelta.

    `cada` submuestrea (1 = todos los vértices) para que una malla densa no genere un bosque.
    """
    posiciones, normales = list(posiciones), list(normales)
    if len(posiciones) != len(normales):
        raise ValueError("hacen falta tantas normales como posiciones.")
    if not posiciones:
        raise ValueError("debug_normals necesita una malla con vértices.")
    if largo <= 0.0 or not math.isfinite(largo):
        raise ValueError("largo debe ser un número finito mayor que cero.")
    if int(cada) < 1:
        raise ValueError("cada debe ser al menos 1.")

    salida = []
    for indice in range(0, len(posiciones), int(cada)):
        direccion = _normalizar(normales[indice])
        if direccion == (0.0, 0.0, 0.0):
            continue
        salida.append(Eje(tuple(float(c) for c in posiciones[indice]), direccion, largo, 2))
        if len(salida) >= MAX_ELEMENTOS:
            break
    if not salida:
        raise ValueError("ningún vértice tenía una normal utilizable.")
    return salida


def aristas_de_caja(minimo, maximo) -> list[Eje]:
    """Las 12 aristas de una caja: el bounding box de una malla, para ver su extensión real."""
    minimo = tuple(float(c) for c in minimo)
    maximo = tuple(float(c) for c in maximo)
    if any(b < a for a, b in zip(minimo, maximo)):
        raise ValueError("la caja tiene un mínimo mayor que su máximo.")
    esquinas = [(minimo[0] if not (i & 1) else maximo[0],
                 minimo[1] if not (i & 2) else maximo[1],
                 minimo[2] if not (i & 4) else maximo[2]) for i in range(8)]
    salida = []
    for a in range(8):
        for bit in (1, 2, 4):
            b = a | bit
            if b == a:
                continue
            delta = tuple(y - x for x, y in zip(esquinas[a], esquinas[b]))
            largo = math.sqrt(sum(c * c for c in delta))
            if largo > 1e-6:
                salida.append(Eje(esquinas[a], _normalizar(delta), largo, 1))
    return salida


def marcadores_de_puntos(muestras, *, tamano: float = 10.0,
                         escalar_con_peso: bool = True, minimo: float = 0.15) -> list[Marcador]:
    """Un marcador por punto de un stream ``P``; su tamaño puede seguir el peso de la máscara.

    Ver el peso como TAMAÑO es lo que vuelve legible una cadena de weights: un punto casi apagado se
    dibuja chico en vez de desaparecer, así se distingue «lo filtró la máscara» de «nunca estuvo».
    `minimo` evita que un peso 0 lo haga invisible.
    """
    muestras = list(muestras or [])
    if not muestras:
        raise ValueError("debug_points necesita un stream P con al menos un punto.")
    if tamano <= 0.0 or not math.isfinite(tamano):
        raise ValueError("tamano debe ser un número finito mayor que cero.")
    if len(muestras) > MAX_ELEMENTOS:
        raise ValueError(f"debug_points no puede dibujar más de {MAX_ELEMENTOS} puntos.")
    if not 0.0 <= minimo <= 1.0:
        raise ValueError("minimo debe estar entre 0 y 1.")

    salida = []
    for muestra in muestras:
        try:
            origen = (float(muestra.pos.x), float(muestra.pos.y), float(muestra.pos.z))
            peso = float(getattr(muestra, "weight", 1.0))
        except (AttributeError, TypeError, ValueError):
            raise ValueError("el stream P no contiene muestras válidas (pos/weight).") from None
        factor = max(minimo, min(1.0, peso)) if escalar_con_peso else 1.0
        salida.append(Marcador(origen, tamano * factor, peso))
    return salida
