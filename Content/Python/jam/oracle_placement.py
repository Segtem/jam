"""Oráculo de COLOCACIÓN — PURO (0 `import unreal`). Razona sobre `piezas` (nombre, AABB) de
`jam.geometry`; el adaptador `jam.ue` las extrae del nivel.

Dos preguntas deterministas sobre una pieza recién colocada:
  1. ¿Tiene bounds válidos? (una malla degenerada / vacía = colocación inútil).
  2. ¿Interpenetra otra pieza? (defecto clásico de kitbash: dos módulos clavados uno en otro).

La profundidad de interpenetración = mínimo, sobre los 3 ejes, de la superposición (eje separador),
con tolerancia para que "tocarse" no cuente como clavarse. La escenografía de fondo se ignora.
"""

from __future__ import annotations

from . import geometry

# Re-export: otros oráculos usan este nombre como default de tolerancia.
_TOL_CM = geometry.TOL_CM


def verificar(pieza, otras, tol: float = geometry.TOL_CM) -> dict:
    """Veredicto de colocación de `pieza`=(nombre, AABB) frente a `otras`=[(nombre, AABB)]
    (que NO debe incluir a la propia pieza; el fondo se ignora)."""
    nombre, a = pieza
    bounds_ok = geometry.volumen(a) > 1e-3
    choques = []
    for n, o in otras:
        if geometry.es_fondo(o):
            continue
        d = geometry.penetracion(a, o, tol)
        if d > 0.0:
            choques.append((n, round(d, 1)))
    e = a.extent
    return {
        "bounds_ok": bounds_ok,
        "extent": (round(e.x, 1), round(e.y, 1), round(e.z, 1)),
        "interpenetra": choques,
    }


def es_ok(r: dict) -> bool:
    return bool(r["bounds_ok"]) and not r["interpenetra"]


def verificar_texto(pieza, otras, tol: float = geometry.TOL_CM) -> str:
    nombre, _a = pieza
    r = verificar(pieza, otras, tol)
    if not r["bounds_ok"]:
        return f"[{nombre}] COLOCACIÓN INVÁLIDA ✗ — bounds degenerados {r['extent']}"
    if r["interpenetra"]:
        detalle = ", ".join(f"{n} ({d}cm)" for n, d in r["interpenetra"])
        return f"[{nombre}] INTERPENETRA ✗ — clavado en: {detalle}"
    return f"[{nombre}] COLOCADO LIMPIO ✓ — extent {r['extent']}cm, sin interpenetrar"
