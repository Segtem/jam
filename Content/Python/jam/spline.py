"""Spline — adaptador: muestrea el SplineComponent → cerebro (`jam.spline_core`) → coloca piezas.

Lo único que necesita al motor: muestrear el spline editable en una polilínea (puntos + z real) y
medir el largo de cada asset (su módulo). El resto —caminar la curva, elegir pieza, orientar a la
tangente, verificar la cadena— es puro. Cada pieza se coloca con `jam.place`, así hereda la
normalización de pivote, el ancla y el align a la normal.

Es el «Path Scatter» de Dash / el `Copy to Points` sobre una curva de Houdini, con piezas MODULARES a
su largo real (sin estirar) como diferencia con el `pared` viejo (R7).
"""

from __future__ import annotations

import unreal

from . import library, pared, place, spline_core as sp, ue
from .geometry import Vec3

_WORLD = unreal.SplineCoordinateSpace.WORLD


def _polilinea(sc, muestras_por_cm=0.02):
    """Muestrea el SplineComponent en una polilínea (lista de Vec3, con z real). La densidad se ajusta
    al largo para que las curvas queden suaves sin explotar el conteo."""
    largo = sc.get_spline_length()
    n = max(2, int(largo * muestras_por_cm) + 1)
    pts = []
    for i in range(n + 1):
        s = largo * i / n
        p = sc.get_location_at_distance_along_spline(s, _WORLD)
        pts.append(Vec3(p.x, p.y, p.z))
    return pts


def _largo_modulo(malla, eje="x") -> float:
    """Largo del módulo: la extensión de la malla en su eje de avance (X por defecto)."""
    aabb = ue.aabb_malla(malla)
    return {"x": aabb.extent.x, "y": aabb.extent.y}.get(eje, aabb.extent.x) * 2.0


def construir(actor, assets, *, gap=0.0, seed=0, eje="x", anchor="base", align=False,
              surface=False, scale=1.0, jitter_yaw=0.0):
    """Levanta la cadena modular sobre el spline de `actor`. `assets` = ruta o lista (kit). Devuelve
    (actores, veredicto_dict)."""
    sc = pared.spline_de(actor)
    if sc is None:
        return [], {"error": "el actor no tiene SplineComponent"}
    rutas = [assets] if isinstance(assets, str) else list(assets)
    mallas = [m for m in (library.cargar_malla(r) for r in rutas) if m is not None]
    if not mallas:
        return [], {"error": f"ningún asset cargable en {rutas!r}"}

    poli = _polilinea(sc)
    largos = [_largo_modulo(m, eje) * scale for m in mallas]
    colocaciones = sp.caminar(poli, largos, gap=gap, seed=seed, jitter_yaw=jitter_yaw)

    actores = []
    for i, c in enumerate(colocaciones):
        malla = mallas[c.idx]
        a = place.colocar(malla, (c.pos.x, c.pos.y, c.pos.z), (0.0, 0.0, c.yaw),
                          (scale, scale, scale), anchor=anchor, align=align,
                          surface=surface, view=False)
        if a is not None:
            a.set_actor_label(f"Jam_spline_{i}")
            actores.append(a)

    largo = sp.largo_total(poli)
    v = sp.verificar_continuidad(colocaciones, largo)
    v.update({"largo_curva": round(largo, 1), "assets": len(mallas), "modulos": [round(x) for x in largos]})
    return actores, v
