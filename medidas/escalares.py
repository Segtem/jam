"""Escalares del dominio GEOMETRÍA. El segundo dominio, y existe para probar que el álgebra es
general: si sirve para «un agente construyendo herramientas» y para «piezas en un nivel», que no se
parecen en nada, sirve.

Un hecho `pieza` es plano, como manda L0 — sin objetos ni anidamiento:

    pieza(id, ox, oy, oz, ex, ey, ez, lx, ly, lz, yaw)
          └ origen del AABB ┘ └ semi-extensión ┘ └ pivote ┘

Las cuentas son las mismas que hace el oráculo escrito a mano de Jam. La prueba diferencial
(`diferencial/`) comprueba que dan el MISMO veredicto sobre cientos de mundos generados por esa
implementación independiente; si divergen, esto está mal.
"""

from __future__ import annotations

from oracle_metalenguaje import escalar

TOL_CM = 1.0            # menos que esto = tocándose, no interpenetrando
MAX_VECINO_CM = 50000.0  # semi-extensión > 500 m = escenografía de fondo (envuelve el mapa)


def _ejes(p: dict):
    return ((p["ox"], p["ex"]), (p["oy"], p["ey"]), (p["oz"], p["ez"]))


@escalar("penetracion", "cm")
def penetracion(a: dict, b: dict, tol: float = TOL_CM) -> float:
    """Profundidad efectiva en cm después de descontar la tolerancia de contacto.

    Devuelve 0 cuando algún eje no supera la tolerancia: «tocarse» no es «clavarse». Por encima,
    informa sólo el exceso, y por eso el umbral de la medida puede ser `<= 0` sin repetir `tol`.
    """
    solapes = []
    for (ca, ea), (cb, eb) in zip(_ejes(a), _ejes(b)):
        solape = (ea + eb) - abs(ca - cb)
        if solape <= tol:
            return 0.0
        solapes.append(solape)
    return min(solapes) - tol


@escalar("es_fondo")
def es_fondo(p: dict, max_cm: float = MAX_VECINO_CM) -> bool:
    """¿Es escenografía descomunal (SkySphere, atmósfera)? Sin este filtro cualquier pieza
    «interpenetra» el cielo y toda medida de colocación da rojo siempre."""
    return max(p["ex"], p["ey"], p["ez"]) > max_cm


@escalar("volumen", "cm3")
def volumen(p: dict) -> float:
    return p["ex"] * p["ey"] * p["ez"]


@escalar("desvio_de_grilla", "cm")
def desvio_de_grilla(p: dict, grilla: float) -> float:
    """El peor desvío del PIVOTE respecto de la grilla, sobre los tres ejes."""
    return max(abs(v - round(v / grilla) * grilla) for v in (p["lx"], p["ly"], p["lz"]))


@escalar("desvio_de_paso", "grados")
def desvio_de_paso(valor: float, paso: float) -> float:
    return abs(valor - round(valor / paso) * paso)


def _eje_de(config: dict) -> str:
    eje = config.get("eje")
    if eje not in {"x", "y", "z"}:
        raise ValueError(f"eje de snap inválido: {eje!r}")
    return eje


@escalar("desvio_de_contacto", "cm")
def desvio_de_contacto(a: dict, b: dict) -> float:
    """Distancia absoluta entre las caras que deberían tocarse sobre el eje elegido.

    Da cero tanto sin hueco como sin solape. Que las caras realmente se compartan en los otros dos
    ejes es otra pregunta y la responde `solape_lateral_minimo`.
    """
    eje = _eje_de(b)
    distancia_centros = abs(a[f"o{eje}"] - b[f"o{eje}"])
    suma_extensiones = a[f"e{eje}"] + b[f"e{eje}"]
    return abs(distancia_centros - suma_extensiones)


@escalar("solape_lateral_minimo", "cm")
def solape_lateral_minimo(a: dict, b: dict) -> float:
    """Menor solape sobre los dos ejes laterales a la cara solicitada."""
    eje = _eje_de(b)
    laterales = [otro for otro in ("x", "y", "z") if otro != eje]
    return min(
        (a[f"e{otro}"] + b[f"e{otro}"])
        - abs(a[f"o{otro}"] - b[f"o{otro}"])
        for otro in laterales
    )


@escalar("fuera_de_region")
def fuera_de_region(instancia: dict, configuracion: dict, tol: float = TOL_CM) -> bool:
    """Si el centro XY de una instancia queda fuera del rectángulo del scatter.

    El tamaño de la pieza no participa: ése es también el contrato del oráculo operativo. Una pieza
    grande puede sobresalir aunque su centro esté adentro; ese punto ciego queda en la medida.
    """
    return (
        abs(instancia["ox"] - configuracion["cx"]) > configuracion["sx"] + tol
        or abs(instancia["oy"] - configuracion["cy"]) > configuracion["sy"] + tol
    )
