"""Hechos L0 sobre la CARA VISIBLE de una malla que Jam genera con buffers propios.

Nace del defecto del 2026-08-10: «Borde de camino» se veía transparente desde arriba y «Muro sobre
spline» aparecía dado vuelta, con 790 tests en verde. Las medidas existentes miraban el array de
normales —que estaba bien— y ninguna miraba el ORDEN DE LOS ÍNDICES, que es lo que decide qué lado
dibuja el motor. Los puntos ciegos de `spline.cobertura` y `spline.sin_solape` ya declaraban no ver
«visibilidad» ni «triángulos»: el defecto cayó exactamente ahí.

Este módulo no decide umbrales ni conoce Unreal: sólo expone, por triángulo y por superficie, hacia
dónde mira la cara y cuánto se aparta de la normal de sombreado declarada para esos mismos vértices.
"""

from __future__ import annotations

import math


def _resta(p, q):
    return (p[0] - q[0], p[1] - q[1], p[2] - q[2])


def _cross(u, v):
    return (u[1] * v[2] - u[2] * v[1],
            u[2] * v[0] - u[0] * v[2],
            u[0] * v[1] - u[1] * v[0])


def _largo(v):
    return math.sqrt(v[0] * v[0] + v[1] * v[1] + v[2] * v[2])


def normal_de_cara(vertices, triangulo):
    """La normal que computa Unreal para esa terna de índices, o None si el triángulo es degenerado.

    El orden `(c-a) × (b-a)` es el opuesto al cross matemático habitual. La constante es EMPÍRICA:
    se fijó comparando, dentro de UE 5.8.1, una malla nativa (`mesh_box`, cuya tapa da +Z) contra la
    cinta de `mesh_ribbon`, con `tools/experiments/investiga_winding_ribbon_58.py`. No se deriva de
    ninguna documentación: se midió.
    """
    a, b, c = (vertices[i] for i in triangulo)
    n = _cross(_resta(c, a), _resta(b, a))
    largo = _largo(n)
    if largo < 1e-12:
        return None
    return (n[0] / largo, n[1] / largo, n[2] / largo)


def hechos(vertices, triangulos, normales) -> dict:
    """Evidencia por triángulo y por superficie. Sin umbrales: sólo números y conteos."""
    vertices = [tuple(float(c) for c in v) for v in vertices]
    triangulos = [tuple(int(i) for i in t) for t in triangulos]
    normales = [tuple(float(c) for c in n) for n in normales]

    caras = []
    acumulada = [0.0, 0.0, 0.0]
    for indice, triangulo in enumerate(triangulos):
        cara = normal_de_cara(vertices, triangulo)
        if cara is None:
            # Un triángulo degenerado no tiene lado visible: se declara como tal en vez de
            # desaparecer del conteo, que lo volvería invisible para la medida.
            caras.append({"id": indice, "acuerdo": -1.0, "degenerado": 1})
            continue
        # Promedio de las normales de sombreado de sus tres vértices: es contra eso que se compara.
        suma = [0.0, 0.0, 0.0]
        for i in triangulo:
            for eje in range(3):
                suma[eje] += normales[i][eje]
        largo = _largo(suma)
        acuerdo = 0.0 if largo < 1e-12 else sum(
            cara[eje] * suma[eje] / largo for eje in range(3))
        for eje in range(3):
            acumulada[eje] += cara[eje]
        caras.append({"id": indice, "acuerdo": acuerdo, "degenerado": 0})

    largo_acumulada = _largo(acumulada)
    unidad = ([componente / largo_acumulada for componente in acumulada]
              if largo_acumulada > 1e-12 else [0.0, 0.0, 0.0])
    # Cuánto se aparta la cara MÁS torcida del lado dominante de la superficie: una cinta que se da
    # vuelta en el medio queda con este número en negativo aunque el promedio siga siendo correcto.
    peor = 1.0
    for indice, triangulo in enumerate(triangulos):
        cara = normal_de_cara(vertices, triangulo)
        if cara is None:
            continue
        peor = min(peor, sum(cara[eje] * unidad[eje] for eje in range(3)))

    return {
        "cara_malla": caras,
        "superficie_malla": [{
            "triangulos": len(triangulos),
            "peor_acuerdo_con_la_superficie": peor if triangulos else 1.0,
            "degenerados": sum(c["degenerado"] for c in caras),
        }],
    }
