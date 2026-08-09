"""Series numéricas transitivas para controlar perfiles y falloffs del Graph.

``ScalarSeries`` viaja por cables ``N[]``. No crea assets ni actores: representa una función
muestreada en dominio normalizado 0..1 que otros verbos pueden interpolar de forma determinista.
"""

from __future__ import annotations

import math
from dataclasses import dataclass


@dataclass(frozen=True)
class ScalarSeries:
    values: tuple[float, ...]
    shape: str = "custom"

    def at(self, parameter: float) -> float:
        """Interpola linealmente la serie en el dominio normalizado 0..1."""
        if not self.values:
            raise ValueError("la serie N[] está vacía")
        if len(self.values) == 1:
            return self.values[0]
        position = min(1.0, max(0.0, float(parameter))) * (len(self.values) - 1)
        left = min(len(self.values) - 1, int(math.floor(position)))
        right = min(len(self.values) - 1, left + 1)
        alpha = position - left
        return self.values[left] + (self.values[right] - self.values[left]) * alpha


def _smoothstep(value: float) -> float:
    return value * value * (3.0 - 2.0 * value)


def graph_curve(*, start_value: float = 1.0, end_value: float = 0.15,
                shape: str = "custom", power: float = 2.0,
                midpoint: float = 0.55, mid_value: float = 0.72,
                samples: int = 16) -> dict:
    """Crea un falloff N[] editable, con extremos exactos y muestreo reproducible."""
    try:
        start_value, end_value = float(start_value), float(end_value)
        power, midpoint, mid_value = float(power), float(midpoint), float(mid_value)
        samples = int(samples)
    except (TypeError, ValueError):
        return {"error": "los parámetros de graph_curve deben ser numéricos."}
    numeric = (start_value, end_value, power, midpoint, mid_value)
    if not all(math.isfinite(item) for item in numeric):
        return {"error": "graph_curve contiene un número no finito."}
    if samples < 2 or samples > 256:
        return {"error": "samples de graph_curve debe estar entre 2 y 256."}
    if power <= 0.0:
        return {"error": "power de graph_curve debe ser mayor que cero."}
    if midpoint <= 0.0 or midpoint >= 1.0:
        return {"error": "midpoint de graph_curve debe estar entre 0 y 1, sin incluir extremos."}

    shape = str(shape or "custom").strip().lower()
    if shape not in {"linear", "ease_in", "ease_out", "smooth", "custom"}:
        return {"error": "shape debe ser linear, ease_in, ease_out, smooth o custom."}

    values = []
    for index in range(samples):
        t = index / (samples - 1)
        if shape == "linear":
            blend = t
            value = start_value + (end_value - start_value) * blend
        elif shape == "ease_in":
            blend = t ** power
            value = start_value + (end_value - start_value) * blend
        elif shape == "ease_out":
            blend = 1.0 - (1.0 - t) ** power
            value = start_value + (end_value - start_value) * blend
        elif shape == "smooth":
            blend = _smoothstep(t)
            value = start_value + (end_value - start_value) * blend
        elif t <= midpoint:
            blend = _smoothstep(t / midpoint)
            value = start_value + (mid_value - start_value) * blend
        else:
            blend = _smoothstep((t - midpoint) / (1.0 - midpoint))
            value = mid_value + (end_value - mid_value) * blend
        values.append(value)

    series = ScalarSeries(tuple(values), shape)
    return {
        "series": series,
        "info": (f"{samples} muestras · {start_value:g}→{end_value:g} · {shape}"
                 + (f" · medio {midpoint:g}:{mid_value:g}" if shape == "custom" else "")),
    }


def series_range(*, start: float = 0.0, end: float = 1.0, count: int = 11) -> dict:
    """Crea ``count`` valores equidistantes, incluidos ambos extremos."""
    try:
        start, end, count = float(start), float(end), int(count)
    except (TypeError, ValueError, OverflowError):
        return {"error": "start, end y count de series_range deben ser numéricos."}
    if not math.isfinite(start) or not math.isfinite(end):
        return {"error": "series_range contiene un extremo no finito."}
    if count < 2 or count > 4096:
        return {"error": "count de series_range debe estar entre 2 y 4096."}
    step = (end - start) / (count - 1)
    values = tuple(start + step * index for index in range(count - 1)) + (end,)
    return {"series": ScalarSeries(values, "range"),
            "info": f"{count} muestras · {start:g}→{end:g} · paso {step:g}"}


def series_remap(source, *, source_min: float = 0.0, source_max: float = 1.0,
                 target_min: float = 0.0, target_max: float = 1.0,
                 clamp: bool = True) -> dict:
    """Remapea cada valor de una serie entre dos dominios, con clamp opcional."""
    if not isinstance(source, ScalarSeries) or not source.values:
        return {"error": "series_remap necesita una serie N[] válida y no vacía."}
    try:
        source_min, source_max = float(source_min), float(source_max)
        target_min, target_max = float(target_min), float(target_max)
    except (TypeError, ValueError, OverflowError):
        return {"error": "los dominios de series_remap deben ser numéricos."}
    limits = (source_min, source_max, target_min, target_max)
    if not all(math.isfinite(value) for value in limits):
        return {"error": "series_remap contiene un límite no finito."}
    if source_min == source_max:
        return {"error": "source_min y source_max de series_remap no pueden ser iguales."}
    if not all(math.isfinite(value) for value in source.values):
        return {"error": "series_remap recibió una serie con valores no finitos."}

    output = []
    for value in source.values:
        parameter = (value - source_min) / (source_max - source_min)
        if clamp:
            parameter = min(1.0, max(0.0, parameter))
        output.append(target_min + (target_max - target_min) * parameter)
    series = ScalarSeries(tuple(output), f"remap({source.shape})")
    return {"series": series,
            "info": (f"{len(output)} muestras · {source_min:g}..{source_max:g} → "
                     f"{target_min:g}..{target_max:g} · "
                     f"{'clamp' if clamp else 'extrapola'}")}


def gradiente(posiciones, *, eje: str = "z", desde: float = 0.0, hasta: float = 1.0,
              power: float = 1.0) -> list[float]:
    """Un escalar 0..1 por vértice según su posición en un eje — la máscara de viento del follaje.

    Es el ``VertexColourScalar`` de TreeGen. El shader de viento necesita saber cuánto puede moverse
    cada vértice: cero en la base del tronco, uno en la punta de las hojas. Sin ese canal el árbol
    entero se dobla como un bloque rígido, que es el tell más visible de un árbol mal hecho.

    `desde`/`hasta` son fracciones del alto real de la malla, no centímetros: así el mismo nodo
    sirve para un arbusto y para un pino de treinta metros. `power` curva el reparto — con 2 el
    movimiento se concentra en la punta, que es como se comporta una rama de verdad.

    Devuelve una lista vacía si no hay posiciones. Si la malla es plana en ese eje devuelve todo en
    cero: no hay gradiente que repartir, y inventar uno sería peor que no ponerlo.
    """
    indice = {"x": 0, "y": 1, "z": 2}.get(str(eje).strip().lower())
    if indice is None:
        raise ValueError("eje debe ser 'x', 'y' o 'z'.")
    posiciones = list(posiciones)
    if not posiciones:
        return []
    try:
        desde, hasta, power = float(desde), float(hasta), float(power)
    except (TypeError, ValueError) as exc:
        raise ValueError("desde, hasta y power deben ser numéricos.") from exc
    if not all(math.isfinite(v) for v in (desde, hasta, power)) or power <= 0.0:
        raise ValueError("power debe ser un número finito mayor que cero.")
    if hasta <= desde:
        raise ValueError("hasta tiene que ser mayor que desde.")

    valores = [float(p[indice]) for p in posiciones]
    minimo, maximo = min(valores), max(valores)
    span = maximo - minimo
    if span < 1e-9:
        return [0.0] * len(valores)

    ancho = hasta - desde
    salida = []
    for valor in valores:
        fraccion = (valor - minimo) / span
        normal = (fraccion - desde) / ancho
        salida.append(min(max(normal, 0.0), 1.0) ** power)
    return salida
