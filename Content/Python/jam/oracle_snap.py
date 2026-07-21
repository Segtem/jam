"""Oráculo de SNAP / ALINEACIÓN — Dash cuadra; Jam verifica que quedó alineado dentro de tolerancia.

Dos preguntas deterministas por AABB:
  - EN GRILLA: ¿el pivote cae en múltiplos de la grilla (±tol) y el yaw en su paso?
  - AL RAS:    ¿la cara del actor toca la de `objetivo` sobre un eje (gap ±tol) compartiendo las
               otras dos (adyacente, no diagonal), sin clavarse ni dejar hueco?

Reusa el AABB de `jam.oracle_placement`.
"""

from __future__ import annotations

import unreal

from . import oracle_placement
from .snap import _EJES, _vec_comp


def _mult_cercano(v: float, paso: float, tol: float) -> bool:
    return abs(v - round(v / paso) * paso) <= tol


def verificar_grilla(actor, grilla: float = 100.0, *, paso_yaw: float = 90.0,
                     tol: float = oracle_placement._TOL_CM, tol_yaw: float = 0.5) -> dict:
    """¿El pivote del actor está en la grilla y el yaw en su paso?"""
    loc = actor.get_actor_location()
    ejes_ok = {e: _mult_cercano(getattr(loc, e), grilla, tol) for e in ("x", "y", "z")}
    yaw = actor.get_actor_rotation().yaw
    yaw_ok = _mult_cercano(yaw, paso_yaw, tol_yaw)
    en_grilla = all(ejes_ok.values()) and yaw_ok
    return {"en_grilla": en_grilla, "ejes_ok": ejes_ok, "yaw": round(yaw, 1), "yaw_ok": yaw_ok}


def verificar_ras(actor, objetivo, eje: str = "x", *, tol: float = oracle_placement._TOL_CM) -> dict:
    """¿`actor` quedó al ras contra `objetivo` sobre `eje`? Devuelve estado + gap del eje."""
    i = _EJES[eje]
    oa, ea = oracle_placement.aabb(actor)
    ob, eb = oracle_placement.aabb(objetivo)
    ca, cb = _vec_comp(oa), _vec_comp(ob)
    va, vb = _vec_comp(ea), _vec_comp(eb)
    gap = abs(ca[i] - cb[i]) - (va[i] + vb[i])            # >0 hueco, ~0 al ras, <0 solapado
    otros_solapan = all((va[j] + vb[j]) - abs(ca[j] - cb[j]) > tol for j in range(3) if j != i)
    if not otros_solapan:
        estado = "desalineado"      # no comparten cara (diagonal / separados en otro eje)
    elif abs(gap) <= tol:
        estado = "al_ras"
    elif gap > 0:
        estado = "hueco"
    else:
        estado = "clavado"
    return {"estado": estado, "gap": round(gap, 1), "eje": eje, "al_ras": estado == "al_ras"}


def es_ok_grilla(r: dict) -> bool:
    return bool(r["en_grilla"])


def es_ok_ras(r: dict) -> bool:
    return bool(r["al_ras"])


def texto_grilla(actor, grilla: float = 100.0, **kw) -> str:
    r = verificar_grilla(actor, grilla, **kw)
    label = actor.get_actor_label()
    if r["en_grilla"]:
        return f"[{label}] EN GRILLA ✓ — pivote en múltiplos de {int(grilla)}cm, yaw {r['yaw']}°"
    faltan = [e for e, ok in r["ejes_ok"].items() if not ok]
    detalle = f"ejes fuera: {','.join(faltan)}" if faltan else ""
    if not r["yaw_ok"]:
        detalle = (detalle + "; " if detalle else "") + f"yaw {r['yaw']}° fuera de paso"
    return f"[{label}] FUERA DE GRILLA ✗ — {detalle}"


def texto_ras(actor, objetivo, eje: str = "x", **kw) -> str:
    r = verificar_ras(actor, objetivo, eje, **kw)
    label = actor.get_actor_label()
    otro = objetivo.get_actor_label()
    if r["estado"] == "al_ras":
        return f"[{label}] AL RAS ✓ — cara {eje} contra «{otro}» (gap {r['gap']}cm)"
    if r["estado"] == "hueco":
        return f"[{label}] CON HUECO ✗ — {r['gap']}cm de aire hasta «{otro}» sobre {eje}"
    if r["estado"] == "clavado":
        return f"[{label}] CLAVADO ✗ — solapa {abs(r['gap'])}cm con «{otro}» sobre {eje}"
    return f"[{label}] DESALINEADO ✗ — no comparte cara con «{otro}» (diagonal/separado)"
