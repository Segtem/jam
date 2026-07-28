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
