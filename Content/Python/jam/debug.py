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
