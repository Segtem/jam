"""Oráculo de PHYSICS (drop) — Dash suelta; Jam verifica que quedó asentado.

Tras soltar un actor, cuatro estados deterministas por AABB frente al soporte de abajo:
  - APOYADO:  la base del actor coincide (±tol) con el top del soporte  → sano.
  - FLOTANDO: hay aire bajo la base (quedó levitando)                   → defecto.
  - HUNDIDO:  la base quedó por debajo del top del soporte (clavado)    → defecto.
  - SIN_SUELO: no hay soporte debajo (caería al vacío)                  → defecto.

Reusa el AABB de `jam.oracle_placement` y la búsqueda de soporte de `jam.physics` — una sola
fuente de verdad para "qué hay debajo".
"""

from __future__ import annotations

from . import geometry


def verificar(pieza, soportes, *, tol: float = geometry.TOL_CM) -> dict:
    """Veredicto de asentamiento de `pieza` (geometry.Pieza) frente a `soportes` (lista de Pieza que
    NO incluye a la propia). El adaptador `jam.ue` arma las piezas del nivel."""
    a = pieza.aabb
    base = a.origin.z - a.extent.z
    z_top, label = geometry.soporte_top(a, soportes, tol)
    if z_top is None:
        return {"estado": "sin_suelo", "gap": None, "soporte": None, "apoyado": False}
    gap = base - z_top
    if abs(gap) <= tol:
        estado = "apoyado"
    elif gap > 0:
        estado = "flotando"
    else:
        estado = "hundido"
    return {"estado": estado, "gap": round(gap, 1), "soporte": label, "apoyado": estado == "apoyado"}


def es_ok(r: dict) -> bool:
    return bool(r["apoyado"])


def verificar_texto(pieza, soportes, *, tol: float = geometry.TOL_CM) -> str:
    r = verificar(pieza, soportes, tol=tol)
    label = pieza.nombre
    if r["estado"] == "sin_suelo":
        return f"[{label}] SIN SUELO ✗ — no hay soporte debajo (caería al vacío)"
    if r["estado"] == "flotando":
        return f"[{label}] FLOTANDO ✗ — {r['gap']}cm de aire sobre «{r['soporte']}»"
    if r["estado"] == "hundido":
        return f"[{label}] HUNDIDO ✗ — {abs(r['gap'])}cm clavado en «{r['soporte']}»"
    return f"[{label}] APOYADO ✓ — asentado sobre «{r['soporte']}» (gap {r['gap']}cm)"
