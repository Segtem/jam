"""Oráculo de COLOCACIÓN — lo que Dash coloca pero no verifica.

Dos preguntas deterministas sobre un asset recién colocado:
  1. ¿Tiene bounds válidos? (una malla degenerada / vacía = colocación inútil).
  2. ¿Interpenetra otra pieza? (defecto clásico de kitbash: dos módulos clavados uno en otro).

Se apoya en AABB (`get_actor_bounds`): barato, determinista, funciona headless. La profundidad de
interpenetración = mínimo, sobre los 3 ejes, de la superposición (regla del eje separador). Con
tolerancia para que "tocarse" no cuente como clavarse.
"""

from __future__ import annotations

import unreal

_TOL_CM = 1.0  # menos que esto = tocándose, no interpenetrando
_MAX_VECINO_CM = 50000.0  # semi-extensión > 500 m en un eje = escenografía de fondo
#                          (SkySphere, atmósfera): envuelve el mapa, no cuenta como interpenetración


def aabb(actor: unreal.Actor) -> tuple[unreal.Vector, unreal.Vector]:
    """(origen, semi-extensión) del AABB del actor, en cm."""
    origin, extent = actor.get_actor_bounds(False)
    return origin, extent


def _penetracion(a: unreal.Actor, b: unreal.Actor, tol: float = _TOL_CM) -> float:
    """Profundidad de interpenetración en cm entre dos AABB; 0.0 si están separados."""
    oa, ea = aabb(a)
    ob, eb = aabb(b)
    solapes = []
    for ca, ea_i, cb, eb_i in (
        (oa.x, ea.x, ob.x, eb.x),
        (oa.y, ea.y, ob.y, eb.y),
        (oa.z, ea.z, ob.z, eb.z),
    ):
        solape = (ea_i + eb_i) - abs(ca - cb)
        if solape <= tol:
            return 0.0  # eje separador → no se tocan
        solapes.append(solape)
    return min(solapes)


def es_fondo(actor: unreal.Actor) -> bool:
    """True si el actor es escenografía de fondo (AABB descomunal que envuelve el mapa: SkySphere,
    atmósfera). La interpenetración sólo tiene sentido entre actores de escala comparable."""
    _, e = aabb(actor)
    return max(e.x, e.y, e.z) > _MAX_VECINO_CM


def verificar(actor: unreal.Actor, otros: list[unreal.Actor], tol: float = _TOL_CM) -> dict:
    """Veredicto de colocación de `actor` frente a `otros` (ignora la escenografía de fondo)."""
    _, extent = aabb(actor)
    vol = extent.x * extent.y * extent.z
    bounds_ok = vol > 1e-3
    choques = []
    for o in otros:
        if o == actor or es_fondo(o):
            continue
        d = _penetracion(actor, o, tol)
        if d > 0.0:
            choques.append((o.get_actor_label(), round(d, 1)))
    return {
        "bounds_ok": bounds_ok,
        "extent": (round(extent.x, 1), round(extent.y, 1), round(extent.z, 1)),
        "interpenetra": choques,
    }


def verificar_texto(actor: unreal.Actor, otros: list[unreal.Actor], tol: float = _TOL_CM) -> str:
    r = verificar(actor, otros, tol)
    label = actor.get_actor_label()
    if not r["bounds_ok"]:
        return f"[{label}] COLOCACIÓN INVÁLIDA ✗ — bounds degenerados {r['extent']}"
    if r["interpenetra"]:
        detalle = ", ".join(f"{n} ({d}cm)" for n, d in r["interpenetra"])
        return f"[{label}] INTERPENETRA ✗ — clavado en: {detalle}"
    return f"[{label}] COLOCADO LIMPIO ✓ — extent {r['extent']}cm, sin interpenetrar"
