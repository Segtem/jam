"""Scatter — adaptador: candidatos → muestreo de la superficie real → máscaras → colocar.

La lógica (generadores, máscaras, variación) vive en `jam.scatter_core`, puro. Acá pasa lo único que
necesita el motor: raycastear cada candidato contra la geometría real para llenar el `Sample`
(posición sobre la superficie, normal, pendiente), y spawnear con `jam.place` — que ya hereda la
normalización de pivote, el ancla y el align a la normal.

Es el «Surface Scatter» de Dash, con las máscaras componibles como diferencial verificable.
"""

from __future__ import annotations

import math
import random

import unreal

from . import library, place, scatter_core as sc
from .geometry import Vec3


def _grados_pendiente(normal: Vec3) -> float:
    """Grados desde la horizontal: 0 = piso plano (normal vertical), 90 = pared."""
    nz = max(-1.0, min(1.0, normal.z))
    return 90.0 - math.degrees(math.asin(abs(nz)))


def _muestrear(centro, semi, puntos, *, suelo_z, seed_base, ignorar):
    """Cada candidato (x,y) → Sample: raycast a la superficie real (o al plano `suelo_z` si no pega).
    La pendiente y la normal salen del impacto — es lo que alimenta las máscaras de ángulo."""
    from . import ue
    sx, sy = semi
    cx, cy = centro
    out = []
    for (x, y) in puntos:
        hit = ue.raycast(x, y, ignorar=ignorar)
        if hit["hit"]:
            p, n = hit["punto"], hit["normal"]
            pos = Vec3(p.x, p.y, p.z)
            normal = Vec3(n.x, n.y, n.z)
        else:
            pos = Vec3(x, y, suelo_z)
            normal = Vec3(0.0, 0.0, 1.0)
        uv = ((x - (cx - sx)) / (2 * sx) if sx else 0.5,
              (y - (cy - sy)) / (2 * sy) if sy else 0.5)
        out.append(sc.Sample(pos, normal, _grados_pendiente(normal),
                             sc.semilla_de(seed_base, x, y), uv))
    return out


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
    """Firma histórica (grilla plana, compat con presets viejos). Para el scatter rico usá
    `esparcir_rico`. Devuelve los actores."""
    mesh = library.cargar_malla(asset) if isinstance(asset, str) else asset
    if mesh is None:
        unreal.log_error(f"[Jam] scatter: no se pudo cargar el asset {asset!r}")
        return []
    pts = sc.grid_jitter(centro, semi, cantidad, seed, jitter)
    rng = random.Random(seed * 7919 + 1)
    actores = []
    for i, (x, y) in enumerate(pts):
        yaw = rng.uniform(0.0, 360.0) if yaw_aleatorio else 0.0
        a = place.colocar(mesh, (x, y, suelo_z), (0.0, 0.0, yaw), escala)
        if a is not None:
            a.set_actor_label(f"Jam_scatter_{i}")
            actores.append(a)
    return actores


def esparcir_rico(
    assets,
    centro=(0.0, 0.0),
    semi=(500.0, 500.0),
    *,
    cantidad=24,
    patron="poisson",       # poisson | grid | radial
    spacing=0.0,            # cm, separación mínima; 0 = AUTO desde la huella real de la malla
    anillos=3,              # patrón radial
    seed=0,
    surface=True,           # raycast a la geometría real
    align=False,            # orientar a la normal de la superficie
    slope_min=0.0, slope_max=90.0,
    height_min=None, height_max=None,
    noise=0.0,              # 0 = sin ruido; >0 = umbral (deja donde el ruido lo supera)
    noise_scale=500.0,      # cm por mancha de ruido
    density=1.0,            # fracción a conservar (add/remove)
    scale_min=1.0, scale_max=1.0,
    espaciado=1.0,          # factor del footprint para el dedup (1.0 = huellas justo sin pisarse)
    sink=0.0,
    anchor="",
    suelo_z=0.0,
):
    """Surface Scatter con tubería de máscaras. `assets` = una ruta o una lista (se elige por semilla,
    como el mesh selector de PCG). La separación por defecto sale de la HUELLA REAL de la malla, y un
    dedup final por footprint garantiza que nada quede clavado (lo que el oráculo verifica).
    Devuelve (actores, veredicto_dict)."""
    rutas = [assets] if isinstance(assets, str) else list(assets)
    mallas = [m for m in (library.cargar_malla(r) for r in rutas) if m is not None]
    if not mallas:
        return [], {"error": f"ningún asset cargable en {rutas!r}"}

    # footprint real de la malla más grande × la escala máxima: la separación mínima honesta
    from . import ue
    radios = [sc.radio_footprint(ue.aabb_malla(m)) for m in mallas]
    radio_max = max(radios) * max(scale_min, scale_max)
    if spacing <= 0.0:
        spacing = radio_max * 2.0 * espaciado   # diámetro: dos huellas juntas sin pisarse

    # 1) candidatos
    if patron == "poisson":
        pts = sc.poisson_disk(centro, semi, spacing, seed)
        if cantidad and len(pts) > cantidad:
            pts = pts[:cantidad]
    elif patron == "radial":
        pts = sc.radial(centro, min(semi), cantidad, anillos, seed)
    else:
        pts = sc.grid_jitter(centro, semi, cantidad, seed)

    # 2) muestreo de la superficie (raycast); si no, plano a suelo_z
    if surface:
        samples = _muestrear(centro, semi, pts, suelo_z=suelo_z, seed_base=seed, ignorar=[])
    else:
        samples = [sc.Sample(Vec3(x, y, suelo_z), Vec3(0, 0, 1), 0.0,
                             sc.semilla_de(seed, x, y), (0.5, 0.5)) for (x, y) in pts]

    # 3) tubería de máscaras (sólo las que el usuario activó)
    mascaras = []
    if slope_min > 0.0 or slope_max < 90.0:
        mascaras.append(sc.mask_slope(slope_min, slope_max))
    if height_min is not None or height_max is not None:
        mascaras.append(sc.mask_height(
            height_min if height_min is not None else -1e12,
            height_max if height_max is not None else 1e12))
    if noise > 0.0:
        mascaras.append(sc.mask_noise(noise, 1.0 / max(1.0, noise_scale), seed))
    if density < 1.0:
        mascaras.append(sc.mask_density(density, seed))
    vivos, descartes = sc.aplicar_mascaras(samples, mascaras)

    # 3b) dedup por FOOTPRINT real: aunque poisson dé separación 2D, con multi-asset o escala variada
    # dos huellas pueden pisarse. Acá se garantiza que ninguna quede clavada (lo que el oráculo mide).
    radio_por_sample = [radios[s.seed % len(mallas)] * max(scale_min, scale_max) for s in vivos]
    vivos, pisados = sc.dedup_por_radio(vivos, radio_por_sample, espaciado)

    # 4) colocar con variación (asset, escala, yaw por semilla estable)
    actores = []
    for i, s in enumerate(vivos):
        malla = mallas[s.seed % len(mallas)]
        esc, yaw = sc.variacion(s, (scale_min, scale_max))
        a = place.colocar(
            malla, (s.pos.x, s.pos.y, s.pos.z - sink), (0.0, 0.0, yaw), esc,
            surface=False, anchor=anchor, align=align, view=False)
        if a is not None:
            a.set_actor_label(f"Jam_scatter_{i}")
            actores.append(a)

    veredicto = {
        "candidatos": len(pts),
        "colocados": len(actores),
        "filtrados": len(descartes),
        "pisados": len(pisados),
        "spacing": round(spacing, 1),
        "mascaras": len(mascaras),
        "assets": len(mallas),
        "patron": patron,
    }
    return actores, veredicto


# ---------- nodos del FLOW que SÍ tocan el motor (el resto vive puro en `jam.flow`) ----------
# Con esto, una cadena estilo Houdini `source_surface → mask_* → instance` corre por el evaluador de
# `jam.flow` sin que ese módulo importe unreal. `jam.flow` sigue siendo el cerebro; acá el adaptador.

def _op_source_surface(entradas, p):
    """Fuente que muestrea la SUPERFICIE REAL: candidatos + raycast → Samples con normal y pendiente
    de verdad (lo que las máscaras de ángulo necesitan). Es el `Scatter SOP` sobre geometría."""
    centro, semi = p["centro"], p["semi"]
    patron = p.get("patron", "poisson")
    seed = int(p.get("seed", 0))
    if patron == "grid":
        pts = sc.grid_jitter(centro, semi, int(p.get("cantidad", 24)), seed)
    elif patron == "radial":
        pts = sc.radial(centro, min(semi), int(p.get("cantidad", 24)), int(p.get("anillos", 3)), seed)
    else:
        pts = sc.poisson_disk(centro, semi, p.get("spacing", 150.0), seed)
        lim = int(p.get("cantidad", 0))
        if lim and len(pts) > lim:
            pts = pts[:lim]
    return _muestrear(centro, semi, pts, suelo_z=p.get("suelo_z", 0.0), seed_base=seed, ignorar=[])


def _op_instance(entradas, p):
    """Terminal: instancia una malla en cada punto del stream (el `Copy to Points` de Houdini).
    Devuelve el stream tal cual (para encadenar) y deja los actores en `p['_actores']`."""
    rutas = p.get("assets") or []
    if isinstance(rutas, str):
        rutas = [rutas]
    mallas = [m for m in (library.cargar_malla(r) for r in rutas) if m is not None]
    stream = entradas[0] if entradas else []
    actores = []
    if mallas:
        for i, s in enumerate(stream):
            malla = mallas[s.seed % len(mallas)]
            esc, yaw = sc.variacion(s, (p.get("scale_min", 1.0), p.get("scale_max", 1.0)))
            a = place.colocar(malla, (s.pos.x, s.pos.y, s.pos.z - p.get("sink", 0.0)),
                              (0.0, 0.0, yaw), esc, surface=False,
                              anchor=p.get("anchor", ""), align=p.get("align", False), view=False)
            if a is not None:
                a.set_actor_label(f"Jam_scatter_{i}")
                actores.append(a)
    p["_actores"] = actores
    return stream


def ops_flow() -> dict:
    """Las operaciones del flow que necesitan el motor, para pasarle a `flow.Flow.evaluar(ops=…)`."""
    return {"source_surface": (_op_source_surface, 0), "instance": (_op_instance, 1)}
