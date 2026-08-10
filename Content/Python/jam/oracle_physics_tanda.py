"""Oráculo manual del resultado de un ``drop(points)``.

Juzga el estado final, no cómo se calculó: toda pieza debe haber encontrado soporte y ninguna pareja
puede quedar interpenetrada. La cantidad apilada es diagnóstico, no una obligación universal.
"""

from __future__ import annotations

from . import geometry


def verificar(resultados, *, tol: float = geometry.TOL_CM) -> dict:
    """Devuelve las dos decisiones binarias de una tanda ya asentada."""
    resultados = list(resultados)
    sin_suelo = [r["pieza"].nombre for r in resultados if not r["apoyada"]]
    choques = []
    for i, actual in enumerate(resultados):
        for siguiente in resultados[i + 1:]:
            a, b = actual["pieza"], siguiente["pieza"]
            profundidad = geometry.penetracion(a.aabb, b.aabb, tol)
            if profundidad > 0.0:
                choques.append((a.nombre, b.nombre, round(profundidad, 1)))
    return {
        "cantidad": len(resultados),
        "sin_suelo": sin_suelo,
        "completa": not sin_suelo,
        "interpenetra": choques,
        "sin_interpenetracion": not choques,
    }


def es_ok(resultado: dict) -> bool:
    return bool(resultado["completa"] and resultado["sin_interpenetracion"])
