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
