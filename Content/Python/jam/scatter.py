"""Scatter — esparce N instancias de una malla sobre una región (el "Scatter Suite" de Dash).

MVP: scatter de ÁREA — reparte `cantidad` copias de un asset sobre un rectángulo XY a una
altura de suelo dada, por **grilla con jitter** (determinista por `seed`): una grilla que cubre
la región de forma pareja, con cada instancia sacudida dentro de su celda. Devuelve los actores.
El oráculo (`jam.oracle_scatter`) verifica cantidad, contención, no-interpenetración y cobertura.

Crecimientos posteriores: dart-throwing / Poisson-disk para reparto orgánico, scatter SOBRE una
superficie por raycast (hoy es plano a `suelo_z`), y scatter a lo largo de una curva.
"""

from __future__ import annotations

import math
import random

import unreal

from . import library, place


def _puntos_grilla_jitter(centro, semi, cantidad, seed, jitter=0.4):
    """Puntos (x,y) en una grilla que cubre [centro ± semi], cada uno sacudido dentro de su celda.
    `jitter` ∈ [0,1] = fracción del medio-lado de celda que se puede desplazar (0.4 = queda en celda).
    Devuelve exactamente `cantidad` puntos (rellena la grilla en orden fila×columna)."""
    rng = random.Random(seed)
    cx, cy = centro
    sx, sy = semi
    aspecto = (sx / sy) if sy else 1.0
    cols = max(1, round(math.sqrt(cantidad * aspecto)))
    filas = max(1, math.ceil(cantidad / cols))
    celda_x = 2 * sx / cols
    celda_y = 2 * sy / filas
    pts = []
    for r in range(filas):
        for c in range(cols):
            if len(pts) >= cantidad:
                break
            base_x = cx - sx + (c + 0.5) * celda_x
            base_y = cy - sy + (r + 0.5) * celda_y
            jx = rng.uniform(-jitter, jitter) * celda_x * 0.5
            jy = rng.uniform(-jitter, jitter) * celda_y * 0.5
            pts.append((base_x + jx, base_y + jy))
    return pts


def esparcir(
    asset,
    centro=(0.0, 0.0),
    semi=(500.0, 500.0),
    cantidad=9,
    *,
    suelo_z=0.0,
    seed=0,
    jitter=0.4,
    escala=(1.0, 1.0, 1.0),
    yaw_aleatorio=True,
):
    """Esparce `cantidad` copias de `asset` sobre el rectángulo XY [centro ± semi] a z=`suelo_z` (cm).
    `asset` = ruta ObjectPath o StaticMesh cargado. Determinista por `seed`. Devuelve los actores."""
    mesh = library.cargar_malla(asset) if isinstance(asset, str) else asset
    if mesh is None:
        unreal.log_error(f"[Jam] scatter: no se pudo cargar el asset {asset!r}")
        return []
    pts = _puntos_grilla_jitter(centro, semi, cantidad, seed, jitter)
    rng = random.Random(seed * 7919 + 1)  # yaw independiente de las posiciones
    actores = []
    for i, (x, y) in enumerate(pts):
        yaw = rng.uniform(0.0, 360.0) if yaw_aleatorio else 0.0
        a = place.colocar(mesh, (x, y, suelo_z), (0.0, 0.0, yaw), escala)
        if a is not None:
            a.set_actor_label(f"Jam_scatter_{i}")
            actores.append(a)
    return actores
