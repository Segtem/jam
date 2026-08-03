"""Juicio puro sobre los datos observables de una representación Nanite.

El adaptador del motor obtiene los conteos; este módulo decide qué significan y cómo se cuentan.
No modifica assets y no conoce ``unreal``, por lo que el mismo contrato sirve para Graph, tests y
futuros sensores de Oracle.
"""

from __future__ import annotations


def medida(*, asset: str, enabled: bool, vertices: int, triangles: int,
           uv_channels: int, lods: int, lod: int = 0) -> dict:
    """Normaliza la lectura del motor y rechaza respuestas imposibles.

    Cero es observable y puede ser un defecto válido; un conteo negativo, en cambio, indica que el
    adaptador leyó una API equivocada o recibió un dato corrupto.
    """
    conteos = {
        "vertices": int(vertices),
        "triangles": int(triangles),
        "uv_channels": int(uv_channels),
        "lods": int(lods),
        "lod": int(lod),
    }
    negativos = [nombre for nombre, valor in conteos.items() if valor < 0]
    if negativos:
        raise ValueError(f"conteos Nanite negativos: {', '.join(negativos)}")
    if conteos["lods"] and conteos["lod"] >= conteos["lods"]:
        raise ValueError(
            f"LOD {conteos['lod']} fuera de rango para una malla con {conteos['lods']} LOD(s)")
    return {
        "asset": str(asset),
        "enabled": bool(enabled),
        **conteos,
    }


def diagnosticar(datos: dict) -> list[str]:
    """Defectos estructurales que esta medición puede defender.

    Deliberadamente no juzga calidad visual, fidelidad del fallback, materiales ni comportamiento
    al fracturar: esos fenómenos necesitan sensores propios y no se infieren de tres conteos.
    """
    defectos: list[str] = []
    if not datos["enabled"]:
        defectos.append("Nanite está deshabilitado")
        return defectos
    if datos["vertices"] <= 0:
        defectos.append("la representación Nanite no tiene vértices")
    if datos["triangles"] <= 0:
        defectos.append("la representación Nanite no tiene triángulos")
    return defectos


def es_valido(datos: dict) -> bool:
    return not diagnosticar(datos)


def _nombre(asset: str) -> str:
    return str(asset).rsplit("/", 1)[-1].split(".", 1)[0] or str(asset)


def texto_analisis(datos: dict) -> str:
    estado = "habilitado" if datos["enabled"] else "deshabilitado"
    return (
        f"NANITE ANÁLISIS ✓ — «{_nombre(datos['asset'])}» · {estado} · "
        f"{datos['triangles']} triángulos · {datos['vertices']} vértices · "
        f"{datos['uv_channels']} canal(es) UV · {datos['lods']} LOD(s)"
    )


def texto_validacion(datos: dict) -> str:
    defectos = diagnosticar(datos)
    if defectos:
        return "NANITE ✗ — " + "; ".join(defectos)
    return (
        f"NANITE ✓ — representación presente: {datos['triangles']} triángulos, "
        f"{datos['vertices']} vértices y {datos['uv_channels']} canal(es) UV"
    )
