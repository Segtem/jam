"""Pivote y anclas — CEREBRO PURO (0 `import unreal`; corre en un python3 pelado).

Todo lo que Jam coloca se coloca *por algún punto*: la base (apoyar), el centro (girar), una esquina
(embaldosar), una cara lateral (pegar piezas de pared). Ese punto es el ANCLA. El pivote que trae el
asset casi nunca es el que uno quiere — en los packs comerciales suele estar en cualquier lado, a
veces FUERA de la malla — y de ahí salen los «flota», «se hunde» y «no cierra la junta».

Este módulo resuelve dos cosas, sin tocar el motor:
  · `location_para(...)`: qué location darle a un actor para que SU ancla caiga en un punto dado.
  · `diagnostico(...)`: dónde está el pivote dentro de su propia caja, y si sirve para tilear.

Es la base de `place anchor=…`, y va a ser la misma para scatter (apoyar cada instancia) y para
spline (pegar pieza con pieza por sus caras).
"""

from __future__ import annotations

from .geometry import AABB, Vec3

# Cada ancla = dónde cae, por eje, dentro de la caja: "min" | "c" (centro) | "max".
ANCLAS: dict[str, tuple[str, str, str]] = {
    "pivot":      ("pivot", "pivot", "pivot"),   # el que trae el asset (sin corrección)
    "center":     ("c", "c", "c"),
    "base":       ("c", "c", "min"),             # apoyar: lo que casi siempre se quiere
    "top":        ("c", "c", "max"),             # apilar algo encima
    "corner":     ("min", "min", "min"),         # embaldosar desde una esquina
    "corner_top": ("min", "min", "max"),
    "xmin":       ("min", "c", "min"),           # caras laterales A RAS DE LA BASE: pegar piezas
    "xmax":       ("max", "c", "min"),
    "ymin":       ("c", "min", "min"),
    "ymax":       ("c", "max", "min"),
}

TOL_REL = 0.02   # 2% del lado: cuándo consideramos que el pivote "está" en un borde/centro


def _coord(centro: float, extent: float, modo: str, pivote: float) -> float:
    if modo == "pivot":
        return pivote
    if modo == "min":
        return centro - extent
    if modo == "max":
        return centro + extent
    return centro


def punto_ancla(aabb: AABB, ancla: str, location: Vec3 | None = None) -> Vec3:
    """Posición (mundo) del ancla de esa caja. `location` sólo se usa para el ancla «pivot»."""
    modos = ANCLAS.get(ancla, ANCLAS["pivot"])
    loc = location or Vec3(aabb.origin.x, aabb.origin.y, aabb.origin.z)
    return Vec3(
        _coord(aabb.origin.x, aabb.extent.x, modos[0], loc.x),
        _coord(aabb.origin.y, aabb.extent.y, modos[1], loc.y),
        _coord(aabb.origin.z, aabb.extent.z, modos[2], loc.z),
    )


def location_para(aabb: AABB, location: Vec3, ancla: str, objetivo: Vec3) -> Vec3:
    """Qué `location` darle al actor para que su ANCLA caiga exactamente en `objetivo`.
    Se mide sobre la caja REAL (ya rotada y escalada), así que sirve con cualquier pivote."""
    p = punto_ancla(aabb, ancla, location)
    return Vec3(objetivo.x + (location.x - p.x),
                objetivo.y + (location.y - p.y),
                objetivo.z + (location.z - p.z))


def diagnostico(aabb: AABB, location: Vec3 | None = None) -> dict:
    """Dónde está el pivote DENTRO de su propia caja, normalizado 0..1 por eje (0=min, 1=max).
    Devuelve {u: (ux,uy,uz), fuera: bool, en_base: bool, centrado_planta: bool, tileable: bool}."""
    loc = location or Vec3(0.0, 0.0, 0.0)
    u = []
    for c, e, p in ((aabb.origin.x, aabb.extent.x, loc.x),
                    (aabb.origin.y, aabb.extent.y, loc.y),
                    (aabb.origin.z, aabb.extent.z, loc.z)):
        lado = 2.0 * e
        u.append(0.5 if lado <= 1e-6 else (p - (c - e)) / lado)
    ux, uy, uz = u
    fuera = any(v < -TOL_REL or v > 1.0 + TOL_REL for v in u)
    en_base = abs(uz) <= TOL_REL
    centrado_planta = abs(ux - 0.5) <= TOL_REL and abs(uy - 0.5) <= TOL_REL
    en_esquina = abs(ux) <= TOL_REL and abs(uy) <= TOL_REL
    return {"u": (ux, uy, uz), "fuera": fuera, "en_base": en_base,
            "centrado_planta": centrado_planta, "en_esquina": en_esquina,
            # tileable = se puede repetir sin recalcular: pivote en la base y en planta previsible
            "tileable": (not fuera) and en_base and (centrado_planta or en_esquina)}


def _altura(uz: float) -> str:
    if abs(uz) <= TOL_REL:
        return "en la BASE"
    if abs(uz - 1.0) <= TOL_REL:
        return "arriba de todo"
    if abs(uz - 0.5) <= TOL_REL:
        return "a media altura"
    return f"a {uz * 100:.0f}% de la altura"


def diagnostico_texto(nombre: str, aabb: AABB, location: Vec3 | None = None) -> str:
    """Veredicto del pivote: dónde está y si el asset se va a portar bien al repetirlo."""
    d = diagnostico(aabb, location)
    ux, uy, uz = d["u"]
    med = (f"{aabb.extent.x * 2:.0f}×{aabb.extent.y * 2:.0f}×{aabb.extent.z * 2:.0f}cm")
    if d["fuera"]:
        donde = f"FUERA de la malla ✗ (x {ux * 100:.0f}%, y {uy * 100:.0f}%, z {uz * 100:.0f}%)"
    elif d["centrado_planta"]:
        donde = f"centrado en planta, {_altura(uz)}"
    elif d["en_esquina"]:
        donde = f"en una esquina de la planta, {_altura(uz)}"
    else:
        donde = f"descentrado (x {ux * 100:.0f}%, y {uy * 100:.0f}%), {_altura(uz)}"

    if d["tileable"]:
        cierre = "SIRVE PARA REPETIR ✓ — apoya solo y se puede tilear sin corregir"
    else:
        cierre = ("REQUIERE ANCLA ✗ — colocalo con «anchor=base» (o corner/xmin…) para que caiga "
                  "donde querés, en vez de por su pivote")
    return f"[{nombre}] pivote {donde} · caja {med}\n    {cierre}"
