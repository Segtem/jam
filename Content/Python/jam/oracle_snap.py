"""Oráculo de SNAP / ALINEACIÓN — PURO (0 unreal). Dash cuadra; Jam verifica que quedó alineado.

Dos preguntas deterministas sobre `piezas` (geometry.Pieza):
  - EN GRILLA: ¿el pivote (pieza.location) cae en múltiplos de la grilla (±tol) y el yaw en su paso?
  - AL RAS:    ¿la cara de la pieza toca la de `objetivo` sobre un eje (gap ±tol) compartiendo las
               otras dos (adyacente, no diagonal), sin clavarse ni dejar hueco?
"""

from __future__ import annotations

from . import geometry

_EJES = {"x": 0, "y": 1, "z": 2}


def _comps(v3) -> tuple[float, float, float]:
    return (v3.x, v3.y, v3.z)


def _mult_cercano(v: float, paso: float, tol: float) -> bool:
    return abs(v - round(v / paso) * paso) <= tol


def verificar_grilla(pieza, grilla: float = 100.0, *, paso_yaw: float = 90.0,
                     tol: float = geometry.TOL_CM, tol_yaw: float = 0.5) -> dict:
    """¿El pivote de la pieza está en la grilla y el yaw en su paso?"""
    loc = pieza.location
    ejes_ok = {e: _mult_cercano(getattr(loc, e), grilla, tol) for e in ("x", "y", "z")}
    yaw = pieza.yaw
    yaw_ok = _mult_cercano(yaw, paso_yaw, tol_yaw)
    en_grilla = all(ejes_ok.values()) and yaw_ok
    return {"en_grilla": en_grilla, "ejes_ok": ejes_ok, "yaw": round(yaw, 1), "yaw_ok": yaw_ok}


def verificar_ras(pieza, objetivo, eje: str = "x", *, tol: float = geometry.TOL_CM) -> dict:
    """¿`pieza` quedó al ras contra `objetivo` sobre `eje`? Devuelve estado + gap del eje."""
    i = _EJES[eje]
    ca, va = _comps(pieza.aabb.origin), _comps(pieza.aabb.extent)
    cb, vb = _comps(objetivo.aabb.origin), _comps(objetivo.aabb.extent)
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


def texto_grilla(pieza, grilla: float = 100.0, **kw) -> str:
    r = verificar_grilla(pieza, grilla, **kw)
    label = pieza.nombre
    if r["en_grilla"]:
        return f"[{label}] EN GRILLA ✓ — pivote en múltiplos de {int(grilla)}cm, yaw {r['yaw']}°"
    faltan = [e for e, ok in r["ejes_ok"].items() if not ok]
    detalle = f"ejes fuera: {','.join(faltan)}" if faltan else ""
    if not r["yaw_ok"]:
        detalle = (detalle + "; " if detalle else "") + f"yaw {r['yaw']}° fuera de paso"
    return f"[{label}] FUERA DE GRILLA ✗ — {detalle}"


def texto_ras(pieza, objetivo, eje: str = "x", **kw) -> str:
    r = verificar_ras(pieza, objetivo, eje, **kw)
    label = pieza.nombre
    otro = objetivo.nombre
    if r["estado"] == "al_ras":
        return f"[{label}] AL RAS ✓ — cara {eje} contra «{otro}» (gap {r['gap']}cm)"
    if r["estado"] == "hueco":
        return f"[{label}] CON HUECO ✗ — {r['gap']}cm de aire hasta «{otro}» sobre {eje}"
    if r["estado"] == "clavado":
        return f"[{label}] CLAVADO ✗ — solapa {abs(r['gap'])}cm con «{otro}» sobre {eje}"
    return f"[{label}] DESALINEADO ✗ — no comparte cara con «{otro}» (diagonal/separado)"
