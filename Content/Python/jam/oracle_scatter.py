"""Oráculo de SCATTER — Dash esparce; Jam verifica que el reparto sea sano.

Cuatro preguntas deterministas sobre un conjunto de instancias esparcidas:
  1. ¿Cantidad?  — ¿se colocaron las que se pidieron? (una región saturada deja faltantes).
  2. ¿Contención? — ¿el centro de cada instancia cae dentro de la región objetivo?
  3. ¿Sin interpenetrar? — ¿ningún par de instancias está clavado? (reusa el AABB de colocación).
  4. ¿Cobertura? — ¿el reparto cubre la región o quedó amontonado?
     (fracción de celdas de una grilla NxN sobre la región que contienen ≥1 instancia).

Reusa `jam.oracle_placement` para el AABB y la profundidad de interpenetración — una sola fuente
de verdad para "dos piezas clavadas".
"""

from __future__ import annotations

import unreal

from . import oracle_placement


def _centro_xy(actor: unreal.Actor) -> tuple[float, float]:
    origin, _ = oracle_placement.aabb(actor)
    return origin.x, origin.y


def verificar(
    actores: list[unreal.Actor],
    centro: tuple[float, float],
    semi: tuple[float, float],
    cantidad_pedida: int,
    *,
    grilla: int = 3,
    cobertura_min: float = 0.6,
    tol: float = oracle_placement._TOL_CM,
) -> dict:
    """Veredicto del scatter: cantidad, instancias fuera de región, pares que interpenetran, cobertura."""
    n = len(actores)
    cx, cy = centro
    sx, sy = semi

    fuera = []
    for a in actores:
        x, y = _centro_xy(a)
        if abs(x - cx) > sx + tol or abs(y - cy) > sy + tol:
            fuera.append(a.get_actor_label())

    choques = []
    for i in range(len(actores)):
        for j in range(i + 1, len(actores)):
            d = oracle_placement._penetracion(actores[i], actores[j], tol)
            if d > 0.0:
                choques.append((actores[i].get_actor_label(), actores[j].get_actor_label(), round(d, 1)))

    celdas = set()
    if sx > 0 and sy > 0:
        for a in actores:
            x, y = _centro_xy(a)
            gx = min(grilla - 1, max(0, int((x - (cx - sx)) / (2 * sx) * grilla)))
            gy = min(grilla - 1, max(0, int((y - (cy - sy)) / (2 * sy) * grilla)))
            celdas.add((gx, gy))
    cobertura = len(celdas) / (grilla * grilla) if grilla else 0.0

    return {
        "cantidad": n,
        "cantidad_ok": n == cantidad_pedida,
        "fuera": fuera,
        "interpenetra": choques,
        "cobertura": round(cobertura, 3),
        "cobertura_ok": cobertura >= cobertura_min,
    }


def es_ok(r: dict) -> bool:
    return r["cantidad_ok"] and not r["fuera"] and not r["interpenetra"] and r["cobertura_ok"]


def verificar_texto(
    actores: list[unreal.Actor],
    centro: tuple[float, float],
    semi: tuple[float, float],
    cantidad_pedida: int,
    **kw,
) -> str:
    r = verificar(actores, centro, semi, cantidad_pedida, **kw)
    lineas = [f"SCATTER · {r['cantidad']}/{cantidad_pedida} instancias · cobertura {int(r['cobertura'] * 100)}%"]
    if not r["cantidad_ok"]:
        lineas.append(f"  ✗ cantidad: faltan {cantidad_pedida - r['cantidad']} (región saturada)")
    if r["fuera"]:
        lineas.append(f"  ✗ fuera de región: {', '.join(r['fuera'])}")
    if r["interpenetra"]:
        muestra = "; ".join(f"{a}×{b} ({d}cm)" for a, b, d in r["interpenetra"][:4])
        extra = "" if len(r["interpenetra"]) <= 4 else f" (+{len(r['interpenetra']) - 4} más)"
        lineas.append(f"  ✗ interpenetran {len(r['interpenetra'])} pares: {muestra}{extra}")
    if not r["cobertura_ok"]:
        lineas.append(f"  ✗ cobertura {int(r['cobertura'] * 100)}% < mínimo — reparto amontonado")
    if es_ok(r):
        lineas.append("  ✓ REPARTO SANO — cantidad, contenido, sin clavarse, bien cubierto")
    return "\n".join(lineas)
