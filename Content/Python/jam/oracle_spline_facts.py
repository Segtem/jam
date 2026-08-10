"""Hechos L0 de la cadena modular sobre spline.

Comparte evidencia entre el runtime y el diferencial sin importar Unreal ni decidir umbrales.
"""

from __future__ import annotations


def hechos(colocaciones, largo_curva: float) -> dict:
    colocaciones = list(colocaciones)
    largo_curva = float(largo_curva)
    cubierto = sum(float(c.largo) for c in colocaciones)
    juntas = []
    for i, (a, b) in enumerate(zip(colocaciones, colocaciones[1:])):
        fin_a = float(a.s) + float(a.largo) / 2.0
        inicio_b = float(b.s) - float(b.largo) / 2.0
        juntas.append({"id": i, "solape": max(0.0, fin_a - inicio_b)})
    return {
        "spline_modular": [{
            "piezas": len(colocaciones),
            "largo_curva": largo_curva,
            "cubierto": cubierto,
            "cobertura": cubierto / largo_curva if largo_curva > 0 else 0.0,
        }],
        "junta_spline": juntas,
    }
