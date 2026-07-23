"""Spline — CEREBRO PURO (0 `import unreal`). Colocar piezas modulares A LO LARGO de una curva.

Es scatter en 1D: en vez de sembrar un área, se camina una curva y se ponen piezas una atrás de otra,
cada una orientada a la tangente. La diferencia con el `pared` viejo (R7) es clave: aquel ESTIRABA
cada segmento para rellenar el tramo (distorsión); acá cada pieza va a su LARGO REAL, edge-to-edge,
como un kit modular — que es lo que hace calles con adoquines, cercas, molduras, muros de piedra.

La curva llega como una POLILÍNEA (lista de puntos ya muestreados del spline: eso lo hace el
adaptador, es lo único que necesita el motor). Acá se camina por longitud de arco: se elige la pieza,
se la centra en su tramo, se la orienta a la tangente local, y se avanza su largo. Sin motor.
"""

from __future__ import annotations

import math
from collections import namedtuple

from .geometry import Vec3

# pos: centro de la pieza sobre la curva · yaw: grados (tangente) · largo: el que ocupa · idx: qué
# asset del set · s: distancia de arco del centro · seed: semilla estable de la pieza
Colocacion = namedtuple("Colocacion", "pos yaw largo idx s seed")


def _acumuladas(polilinea):
    """Longitud de arco acumulada en cada vértice de la polilínea. cum[i] = largo hasta el vértice i."""
    cum = [0.0]
    for i in range(1, len(polilinea)):
        a, b = polilinea[i - 1], polilinea[i]
        cum.append(cum[-1] + math.dist((a.x, a.y, a.z), (b.x, b.y, b.z)))
    return cum


def largo_total(polilinea) -> float:
    return _acumuladas(polilinea)[-1] if len(polilinea) > 1 else 0.0


def _en_distancia(polilinea, cum, s):
    """(pos, yaw) a la distancia de arco `s` sobre la polilínea: interpola el punto y toma la tangente
    del segmento donde cae. Es el `get_location/direction_at_distance` pero puro sobre la polilínea."""
    s = max(0.0, min(cum[-1], s))
    # segmento que contiene s
    i = 1
    while i < len(cum) and cum[i] < s:
        i += 1
    i = min(i, len(polilinea) - 1)
    a, b = polilinea[i - 1], polilinea[i]
    seg = cum[i] - cum[i - 1]
    t = 0.0 if seg <= 1e-9 else (s - cum[i - 1]) / seg
    pos = Vec3(a.x + (b.x - a.x) * t, a.y + (b.y - a.y) * t, a.z + (b.z - a.z) * t)
    yaw = math.degrees(math.atan2(b.y - a.y, b.x - a.x))
    return pos, yaw


def caminar(polilinea, largos, *, gap=0.0, seed=0, jitter_yaw=0.0, cerrada=False):
    """Camina la curva colocando piezas edge-to-edge. `largos` = largo (cm) de cada asset del set
    (se elige por semilla, como el mesh selector). `gap` = separación entre piezas (cm). Devuelve la
    lista de `Colocacion`. La última pieza que no entra entera NO se coloca (kit modular: sin recortes)."""
    if len(polilinea) < 2 or not largos:
        return []
    cum = _acumuladas(polilinea)
    total = cum[-1]
    out = []
    s = 0.0
    n = 0
    while s < total - 1e-6:
        # elegir pieza por semilla estable de esta posición en la cadena
        semilla = _hash(seed, n)
        idx = semilla % len(largos)
        L = largos[idx]
        if L <= 0:
            break
        if s + L > total + 1e-6:
            break                      # no entra entera: se corta acá (sin estirar ni recortar)
        centro = s + L / 2.0
        pos, yaw = _en_distancia(polilinea, cum, centro)
        if jitter_yaw:
            yaw += (_hash(seed, n * 7 + 3) % 1000 / 1000.0 * 2 - 1) * jitter_yaw
        out.append(Colocacion(pos, yaw, L, idx, centro, semilla))
        s += L + gap
        n += 1
    return out


def _hash(seed, n):
    h = (seed * 2654435761 ^ (n + 1) * 40503) & 0xFFFFFFFF
    h = (h ^ (h >> 13)) * 1274126177 & 0xFFFFFFFF
    return (h ^ (h >> 16)) & 0xFFFFFFFF


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


def texto_continuidad(r, largo_curva) -> str:
    lineas = [f"SPLINE · {r['piezas']} piezas · cobertura {int(r['cobertura'] * 100)}% "
              f"de {largo_curva:.0f}cm"]
    if r["solapes"]:
        m = "; ".join(f"junta {i}: {d}cm" for i, d in r["solapes"][:4])
        lineas.append(f"  ✗ {len(r['solapes'])} piezas se solapan ({m})")
    if not r["cobertura_ok"]:
        lineas.append("  ✗ cobertura baja — la curva quedó a medio llenar")
    if r["sin_solape"] and r["cobertura_ok"]:
        lineas.append("  ✓ CADENA MODULAR SANA — piezas a su largo real, edge-to-edge, sin estirar")
    return "\n".join(lineas)
