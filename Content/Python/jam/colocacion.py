"""`place` en la base común: DÓNDE va cada instancia, calculado en el núcleo. Cerebro puro.

Es la misma decisión que toma Unreal en `tools.t_place` → `place.colocar` / `scatter.instanciar_puntos`,
escrita sin el motor: el reparto por huella (`scatter_core.repartir_o_apilar`), la variación por
semilla (`scatter_core.variacion`), el ancla medida sobre la caja YA girada y escalada
(`pivot.location_para`) y el `surface` por un raycast que pone el motor. Al motor le llegan
instancias hechas —posición, yaw, escala— por la primitiva `colocar` del contrato
(`docs/contrato-motor.md`).

Lo que Unreal hace y esto todavía no: `align` (orientar a la normal) y `view` (el punto de mira del
viewport; por el contrato no hay viewport). Los dos se rechazan con su porqué en vez de ignorarse.
"""

from __future__ import annotations

import math

from . import pivot, scatter_core as sc
from .geometry import AABB, Vec3


class ErrorColocacion(ValueError):
    pass


def caja_de(minimo, maximo) -> AABB:
    return AABB(Vec3(*((a + b) / 2.0 for a, b in zip(minimo, maximo))),
                Vec3(*((b - a) / 2.0 for a, b in zip(minimo, maximo))))


def caja_de_mundo(local: AABB, pos, yaw: float, escala) -> AABB:
    """La caja envolvente de `local` escalada, girada `yaw` alrededor de Z y trasladada a `pos`: la
    de sus 8 esquinas, que es lo que miden Unreal (`FBox::TransformBy`) y los otros motores."""
    c, s = math.cos(math.radians(yaw)), math.sin(math.radians(yaw))
    o, e = local.origin, local.extent
    xs, ys, zs = [], [], []
    for dx in (-1, 1):
        for dy in (-1, 1):
            for dz in (-1, 1):
                x = (o.x + dx * e.x) * escala[0]
                y = (o.y + dy * e.y) * escala[1]
                xs.append(pos[0] + x * c - y * s)
                ys.append(pos[1] + x * s + y * c)
                zs.append(pos[2] + (o.z + dz * e.z) * escala[2])
    return caja_de((min(xs), min(ys), min(zs)), (max(xs), max(ys), max(zs)))


def _anclar(local: AABB, pos, yaw, escala, ancla: str):
    """La posición del pivote para que el ANCLA caiga en `pos`, como `place.colocar`."""
    if not ancla or ancla == "pivot":
        return tuple(pos)
    if ancla not in pivot.ANCLAS:
        raise ErrorColocacion(f"ancla desconocida «{ancla}»: {', '.join(pivot.ANCLAS)}")
    mundo = caja_de_mundo(local, pos, yaw, escala)
    n = pivot.location_para(mundo, Vec3(*pos), ancla, Vec3(*pos))
    return (n.x, n.y, n.z)


def instancia(local: AABB, pos, yaw: float, escala, ancla: str) -> dict:
    p = _anclar(local, pos, yaw, escala, ancla)
    return {"pos": [p[0], p[1], p[2]], "yaw": float(yaw), "escala": [float(v) for v in escala]}


def planear(cajas: list[AABB], *, puntos=None, x=0.0, y=0.0, z=0.0, view=False, surface=True,
            anchor="base", sink=0.0, align=False, yaw=0.0, scale=1.0, scale_min=1.0,
            scale_max=1.0, raycast=None) -> tuple[list[dict], int]:
    """`(instancias, pisados)`. `cajas` = la caja local de cada asset (con varios, uno por punto
    según su semilla, como Unreal). `raycast(desde, hacia)` → `{golpe, punto, normal}`.

    Con `puntos`, una instancia por punto que sobreviva al reparto (`surface` no se usa: el punto
    ya dice dónde está, igual que en Unreal). Sin puntos, una en `x, y, z`."""
    if view:
        raise ErrorColocacion("view=true necesita el punto de mira del viewport, que el contrato no "
                              "tiene: dale x/y/z")
    if align:
        raise ErrorColocacion("align=true (orientar a la normal) todavía no está en la base común")
    if not cajas:
        raise ErrorColocacion("no sé QUÉ colocar: cableá un asset")
    if puntos:
        puntos = list(puntos)
        radios = [sc.radio_footprint(c) * max(scale_min, scale_max) for c in cajas]
        vivos, pisados = sc.repartir_o_apilar(
            puntos, [radios[p.seed % len(cajas)] for p in puntos], apilar=False)
        salida = []
        for p in vivos:
            escala, giro = sc.variacion(p, (scale_min, scale_max))
            salida.append({**instancia(cajas[p.seed % len(cajas)],
                                       (p.pos.x, p.pos.y, p.pos.z - sink), giro, escala, anchor),
                           "asset": p.seed % len(cajas)})
        return salida, len(pisados)
    pos = (x, y, z - sink)
    if surface:
        if raycast is None:
            raise ErrorColocacion("surface=true necesita un raycast del motor")
        g = raycast((x, y, 1.0e6), (x, y, -1.0e6))
        if g.get("golpe"):
            # Como `place.colocar`: el golpe PISA la z, sink incluido (con surface, sink no hunde).
            pos = (x, y, g["punto"][2])
    # Sin ancla explícita, Unreal usa la del kit o «base» si apoya en una superficie.
    ancla = anchor or ("base" if surface else "")
    return [{**instancia(cajas[0], pos, yaw, (scale, scale, scale), ancla), "asset": 0}], 0
