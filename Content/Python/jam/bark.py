"""Relieve de corteza — PURO (0 `import unreal`).

TreeGen consigue la corteza dibujando una textura a un render target y sampleándola por UV durante
`DrawRadius` para deformar el radio del anillo. Jam no necesita el rodeo del render target: puede
calcular el ruido directamente, y hacerlo en Python puro lo vuelve testeable sin motor.

La idea de la corteza: el ruido se **estira a lo largo del eje**. Un ruido isótropo da bultos de
papa; uno con frecuencia alta alrededor del tronco y baja a lo largo produce los surcos verticales
que el ojo lee como corteza. Eso es lo que hace `alargue`.

El adaptador (`mesh.bark`) lee posiciones y normales de la malla, llama acá, y escribe de vuelta.
"""

from __future__ import annotations

import math


MASCARA = 0xFFFFFFFF


def _hash(x: int, y: int, z: int, seed: int) -> float:
    """Ruido blanco determinista en [-1, 1] para la celda entera (x, y, z)."""
    h = (x * 374761393 + y * 668265263 + z * 1442695040888963407 + seed * 1274126177) & MASCARA
    h = ((h ^ (h >> 13)) * 1274126177) & MASCARA
    h = (h ^ (h >> 16)) & MASCARA
    return (h / MASCARA) * 2.0 - 1.0


def _suave(t: float) -> float:
    """Smoothstep de quinto orden: derivadas continuas, sin las bandas del lineal."""
    return t * t * t * (t * (t * 6.0 - 15.0) + 10.0)


def ruido(x: float, y: float, z: float, seed: int = 0) -> float:
    """Value noise 3D interpolado, en [-1, 1]."""
    xi, yi, zi = math.floor(x), math.floor(y), math.floor(z)
    xf, yf, zf = x - xi, y - yi, z - zi
    u, v, w = _suave(xf), _suave(yf), _suave(zf)

    def esquina(dx, dy, dz):
        return _hash(int(xi) + dx, int(yi) + dy, int(zi) + dz, seed)

    def mezcla(a, b, t):
        return a + (b - a) * t

    x00 = mezcla(esquina(0, 0, 0), esquina(1, 0, 0), u)
    x10 = mezcla(esquina(0, 1, 0), esquina(1, 1, 0), u)
    x01 = mezcla(esquina(0, 0, 1), esquina(1, 0, 1), u)
    x11 = mezcla(esquina(0, 1, 1), esquina(1, 1, 1), u)
    return mezcla(mezcla(x00, x10, v), mezcla(x01, x11, v), w)


def fbm(x: float, y: float, z: float, *, octavas: int = 3, seed: int = 0,
        lacunaridad: float = 2.0, ganancia: float = 0.5) -> float:
    """Suma de octavas de `ruido`, normalizada a [-1, 1]."""
    total = 0.0
    amplitud = 1.0
    frecuencia = 1.0
    suma_amplitudes = 0.0
    for octava in range(max(1, int(octavas))):
        total += amplitud * ruido(x * frecuencia, y * frecuencia, z * frecuencia, seed + octava * 7919)
        suma_amplitudes += amplitud
        amplitud *= ganancia
        frecuencia *= lacunaridad
    return total / suma_amplitudes if suma_amplitudes > 0 else 0.0


def relieve_corteza(x: float, y: float, z: float, *, escala: float, alargue: float,
                    octavas: int, surcos: float, seed: int) -> float:
    """Campo de corteza en [-1, 1] evaluado en un punto del mundo.

    `surcos` mezcla entre ruido liso (0, bultos suaves) y ruido *ridged* (1, surcos marcados con
    lomos anchos). La corteza real es asimétrica: grietas angostas y profundas entre lomos planos, y
    eso es justo lo que produce la transformación ridged.
    """
    base = fbm(x * escala, y * escala, z * escala * alargue, octavas=octavas, seed=seed)
    # ridged: |n| invertido ⇒ los ceros del ruido se vuelven crestas y el resto cae en surcos.
    afilado = 1.0 - 2.0 * abs(base)
    mezcla = min(1.0, max(0.0, surcos))
    return base * (1.0 - mezcla) + afilado * mezcla


def desplazar(posiciones, normales, *, amplitud: float = 2.0, escala: float = 0.06,
              alargue: float = 0.25, octavas: int = 3, surcos: float = 0.6,
              seed: int = 7) -> list[tuple[float, float, float]]:
    """Devuelve las posiciones desplazadas a lo largo de su normal según el campo de corteza.

    Desplazar por la NORMAL y no radialmente desde el eje Z hace que funcione igual en un tronco
    vertical que en una rama inclinada.

    LÍMITE CONOCIDO: `amplitud` es absoluta, así que tiene que ser MENOR que el radio más fino de la
    malla. Un tronco que afina a 0.7cm con un relieve de ±1.5cm manda los vértices de la punta al
    otro lado del eje e invierte la geometría. La función no puede detectarlo porque no conoce el
    eje del barrido; lo controla quien arma el grafo, dejando que el perfil del pipe no baje a una
    aguja.
    """
    posiciones = list(posiciones)
    normales = list(normales)
    if len(posiciones) != len(normales):
        raise ValueError("hacen falta tantas normales como posiciones.")
    if not posiciones:
        raise ValueError("desplazar necesita al menos un vértice.")
    if not math.isfinite(amplitud):
        raise ValueError("amplitud debe ser finita.")
    if escala <= 0.0 or not math.isfinite(escala):
        raise ValueError("escala debe ser mayor que cero.")
    if alargue <= 0.0 or not math.isfinite(alargue):
        raise ValueError("alargue debe ser mayor que cero.")
    if int(octavas) < 1 or int(octavas) > 8:
        raise ValueError("octavas debe estar entre 1 y 8.")

    salida = []
    for (x, y, z), (nx, ny, nz) in zip(posiciones, normales):
        campo = relieve_corteza(x, y, z, escala=escala, alargue=alargue,
                                octavas=int(octavas), surcos=surcos, seed=int(seed))
        d = amplitud * campo
        salida.append((x + nx * d, y + ny * d, z + nz * d))
    return salida
