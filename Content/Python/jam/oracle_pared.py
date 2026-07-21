"""Oráculo de PARED por spline — Dash reparte a lo largo de la curva; Jam verifica que la pared sea
continua y siga el spline.

Los segmentos van GIRADOS según la tangente, así que el AABB del resto del kit no aplica a sus caras.
El oráculo razona sobre las JUNTAS: el extremo delantero del segmento i y el trasero del i+1 deberían
caer sobre el punto del spline en esa junta. Si los segmentos son muy largos para lo que curva el
spline, se despegan (kink) → discontinua.

  - COBERTURA: ¿la pared cubre el largo del spline? (n·paso ≈ largo).
  - CONTINUA:  ¿cada junta queda a ≤tol del punto del spline? (máx de las desviaciones).
"""

from __future__ import annotations

import math

import unreal

from . import pared

_WORLD = unreal.SplineCoordinateSpace.WORLD


def verificar(build: dict, *, tol: float = 50.0) -> dict:
    """Veredicto de la pared construida por `pared.construir`. `tol` en cm (junta despegada tolerable)."""
    sc = pared.spline_de(build.get("actor_spline"))
    n = build["n"]
    paso = build.get("paso", 0.0)
    centros = build["centros"]
    forwards = build["forwards"]

    def extremo(i, signo):
        cx, cy = centros[i]
        fx, fy = forwards[i]
        return (cx + signo * (paso / 2.0) * fx, cy + signo * (paso / 2.0) * fy)

    max_gap = 0.0
    juntas = []
    if sc is not None:
        for i in range(n - 1):
            fin_i = extremo(i, +1)
            ini_j = extremo(i + 1, -1)
            p = sc.get_location_at_distance_along_spline((i + 1) * paso, _WORLD)
            g = max(math.dist(fin_i, (p.x, p.y)), math.dist(ini_j, (p.x, p.y)))
            max_gap = max(max_gap, g)
            juntas.append(round(g, 1))

    continua = (n <= 1) or (max_gap <= tol)
    largo_real = n * paso
    cobertura_ok = abs(largo_real - build["largo_spline"]) <= tol
    return {
        "n": n,
        "max_gap": round(max_gap, 1),
        "continua": continua,
        "cobertura_ok": cobertura_ok,
        "largo_real": round(largo_real, 1),
        "largo_spline": round(build["largo_spline"], 1),
        "juntas": juntas,
    }


def es_ok(r: dict) -> bool:
    return bool(r["continua"] and r["cobertura_ok"] and r["n"] >= 1)


def verificar_texto(build: dict, *, tol: float = 50.0) -> str:
    r = verificar(build, tol=tol)
    lineas = [f"PARED · {r['n']} segmentos · {r['largo_real']}cm sobre spline de {r['largo_spline']}cm"]
    if not r["cobertura_ok"]:
        lineas.append(f"  ✗ cobertura: la pared mide {r['largo_real']} vs spline {r['largo_spline']}")
    if not r["continua"]:
        lineas.append(f"  ✗ discontinua: junta despegada {r['max_gap']}cm del spline "
                      f"(segmentos muy largos para la curva)")
    if es_ok(r):
        lineas.append(f"  ✓ PARED CONTINUA — sigue el spline, juntas ≤{int(tol)}cm (máx {r['max_gap']}cm)")
    return "\n".join(lineas)
