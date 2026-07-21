"""Oráculo de REEMPLAZO — Dash cambia la malla; Jam verifica que el footprint se preservó.

Tres preguntas deterministas sobre el asset que reemplazó a un blockout, contra el `objetivo`
(footprint capturado del blockout antes de borrarlo):
  - CENTRADO: ¿el centro XY del nuevo AABB calza con el del blockout (±tol)?
  - APOYADO:  ¿la base (z_min) coincide (±tol)? (no quedó flotando ni hundido al vestir).
  - FOOTPRINT: ¿el ancho×largo del AABB calza (±tol_fp)? (no se angostó ni ensanchó el hueco).

PRESERVA = las tres. Reusa el AABB de `jam.oracle_placement`.
"""

from __future__ import annotations

import unreal

from . import oracle_placement


def verificar(nuevo, objetivo: dict, *, tol: float = oracle_placement._TOL_CM, tol_fp: float = 2.0) -> dict:
    """Compara el AABB de `nuevo` con el footprint `objetivo` del blockout."""
    on, en = oracle_placement.aabb(nuevo)
    dcx = on.x - objetivo["cx"]
    dcy = on.y - objetivo["cy"]
    dbase = (on.z - en.z) - objetivo["base"]
    dfx = en.x - objetivo["ex"]
    dfy = en.y - objetivo["ey"]
    centrado = abs(dcx) <= tol and abs(dcy) <= tol
    apoyado = abs(dbase) <= tol
    footprint = abs(dfx) <= tol_fp and abs(dfy) <= tol_fp
    return {
        "preserva": centrado and apoyado and footprint,
        "centrado": centrado,
        "apoyado": apoyado,
        "footprint": footprint,
        "d_centro": (round(dcx, 1), round(dcy, 1)),
        "d_base": round(dbase, 1),
        "d_footprint": (round(dfx, 1), round(dfy, 1)),
    }


def es_ok(r: dict) -> bool:
    return bool(r["preserva"])


def verificar_texto(nuevo, objetivo: dict, **kw) -> str:
    r = verificar(nuevo, objetivo, **kw)
    label = nuevo.get_actor_label()
    if r["preserva"]:
        return f"[{label}] FOOTPRINT PRESERVADO ✓ — centro, base y planta calzan con el blockout"
    fallas = []
    if not r["centrado"]:
        fallas.append(f"descentrado {r['d_centro']}cm")
    if not r["apoyado"]:
        fallas.append(f"base corrida {r['d_base']}cm")
    if not r["footprint"]:
        fallas.append(f"planta cambió {r['d_footprint']}cm (angosta/ensancha el hueco)")
    return f"[{label}] FOOTPRINT ROTO ✗ — {'; '.join(fallas)}"
