"""Adaptador Jam ↔ Unreal — la ÚNICA capa que toca `unreal` para LEER geometría del nivel.

El cerebro (`jam.geometry` + los oráculos) razona sobre datos planos; acá los extraemos del motor.
Cuando UE cambie (UE6/Scene Graph deprecan Actors, C++→Verse), se reescribe ESTE archivo, no el
cerebro. Una `pieza` = (nombre, AABB): lo mínimo que el oráculo necesita para dictaminar.
"""

from __future__ import annotations

import unreal

from .geometry import AABB, Pieza, Vec3


def _sub():
    return unreal.get_editor_subsystem(unreal.EditorActorSubsystem)


def _mundo():
    return unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()


_SIN_HIT = {"hit": False, "punto": None, "normal": None, "actor": None}


def raycast_entre(a: Vec3, b: Vec3, *, ignorar=None) -> dict:
    """Traza un rayo de `a` a `b` contra la geometría real del nivel (trace complejo). Devuelve
    {hit, punto: Vec3, normal: Vec3, actor: str|None}. Es la primitiva: el rayo vertical (piso) y el
    de la cámara (dónde estoy mirando) son casos de esto, y sirve igual para pegar contra una pared.
    El HitResult se lee por `to_tuple()` (5.7 no expone sus campos como atributos):
    [0]=blocking_hit, [5]=impact_point, [7]=impact_normal, [9]=actor."""
    r = unreal.SystemLibrary.line_trace_single(
        _mundo(), unreal.Vector(a.x, a.y, a.z), unreal.Vector(b.x, b.y, b.z),
        unreal.TraceTypeQuery.TRACE_TYPE_QUERY1, True, ignorar or [],
        unreal.DrawDebugTrace.NONE, True)
    # Sin impacto, la función devuelve None (no un HitResult vacío): sin esta guarda, trazar al aire
    # tiraba AttributeError en vez de decir "no hay superficie".
    if r is None:
        return dict(_SIN_HIT)
    t = r.to_tuple()
    if not t[0]:   # blocking_hit
        return dict(_SIN_HIT)
    p, n, act = t[5], t[7], t[9]
    return {"hit": True,
            "punto": Vec3(p.x, p.y, p.z),
            "normal": Vec3(n.x, n.y, n.z),
            "actor": act.get_actor_label() if act else None}


def raycast(x: float, y: float, *, desde: float = 1.0e6, hasta: float = -1.0e6, ignorar=None) -> dict:
    """Rayo VERTICAL hacia abajo en (x,y): la superficie bajo ese punto."""
    return raycast_entre(Vec3(x, y, desde), Vec3(x, y, hasta), ignorar=ignorar)


def camara() -> dict | None:
    """Cámara del viewport del editor: {'loc': Vec3, 'rot': (pitch,yaw,roll), 'adelante': Vec3}.
    None si no hay viewport (headless). Es lo que permite colocar DONDE MIRÁS en vez del origen."""
    try:
        info = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_level_viewport_camera_info()
    except Exception:  # noqa: BLE001
        return None
    if not info or info[0] is None or info[1] is None:
        return None
    loc, rot = info[0], info[1]
    f = unreal.MathLibrary.get_forward_vector(rot)
    return {"loc": Vec3(loc.x, loc.y, loc.z),
            "rot": (rot.pitch, rot.yaw, rot.roll),
            "adelante": Vec3(f.x, f.y, f.z)}


def punto_de_mira(*, alcance: float = 100000.0) -> dict:
    """Dónde está mirando el viewport: traza desde la cámara hacia adelante y devuelve el impacto
    (como la mira de Dash). Si no pega nada, devuelve un punto a 10 m adelante con hit=False.
    Devuelve {hit, punto, normal, actor} o None si no hay viewport."""
    cam = camara()
    if cam is None:
        return None
    o, d = cam["loc"], cam["adelante"]
    fin = Vec3(o.x + d.x * alcance, o.y + d.y * alcance, o.z + d.z * alcance)
    r = raycast_entre(o, fin)
    if r["hit"]:
        return r
    lejos = Vec3(o.x + d.x * 1000.0, o.y + d.y * 1000.0, o.z + d.z * 1000.0)
    return {"hit": False, "punto": lejos, "normal": Vec3(0.0, 0.0, 1.0), "actor": None}


def tags(actor) -> list[str]:
    """Tags del actor como strings. Jam marca con tags lo suyo (`jam:preview`, `jam:ghost`) para
    poder distinguirlo del resto del nivel sin depender de nombres."""
    try:
        return [str(t) for t in actor.get_editor_property("tags")]
    except Exception:  # noqa: BLE001
        return []


def set_tags(actor, valores: list[str]) -> None:
    try:
        actor.set_editor_property("tags", [unreal.Name(t) for t in valores])
    except Exception:  # noqa: BLE001
        pass


def seleccionar(actores) -> None:
    """Deja los actores SELECCIONADOS en el editor: aparecen resaltados, en el Outliner y en Details
    (y con F la cámara vuela hasta ellos). Sin esto, lo que Jam coloca es invisible si cae fuera de
    cuadro — que es exactamente cómo se siente un «Confirmar» que "no hizo nada"."""
    try:
        _sub().set_selected_level_actors(list(actores))
    except Exception:  # noqa: BLE001
        pass


def aabb(actor) -> AABB:
    """AABB (datos) del actor, en cm."""
    origin, extent = actor.get_actor_bounds(False)
    return AABB(Vec3(origin.x, origin.y, origin.z), Vec3(extent.x, extent.y, extent.z))


def pieza(actor) -> Pieza:
    """Pieza (dato puro) del actor: nombre + AABB + location (pivote) + yaw. Todo lo que un oráculo
    puede necesitar, extraído acá para que el cerebro no toque `unreal`."""
    loc = actor.get_actor_location()
    yaw = actor.get_actor_rotation().yaw
    return Pieza(actor.get_actor_label(), aabb(actor), Vec3(loc.x, loc.y, loc.z), yaw)


def piezas(actores) -> list:
    return [pieza(a) for a in actores]


def actores_nivel() -> list:
    return _sub().get_all_level_actors()


# ---- puentes actor → oráculo puro (para callers que tienen actores del editor) ----

def placement(actor, otros) -> dict:
    from . import oracle_placement
    otras = piezas([o for o in otros if o != actor])
    return oracle_placement.verificar(pieza(actor), otras)


def placement_texto(actor, otros) -> str:
    from . import oracle_placement
    otras = piezas([o for o in otros if o != actor])
    return oracle_placement.verificar_texto(pieza(actor), otras)


def scatter_texto(actores, centro, semi, cantidad, **kw) -> str:
    from . import oracle_scatter
    return oracle_scatter.verificar_texto(piezas(actores), centro, semi, cantidad, **kw)


def scatter(actores, centro, semi, cantidad, **kw) -> dict:
    from . import oracle_scatter
    return oracle_scatter.verificar(piezas(actores), centro, semi, cantidad, **kw)


def snap_grilla_texto(actor, grilla=100.0, **kw) -> str:
    from . import oracle_snap
    return oracle_snap.texto_grilla(pieza(actor), grilla, **kw)


def snap_grilla(actor, grilla=100.0, **kw) -> dict:
    from . import oracle_snap
    return oracle_snap.verificar_grilla(pieza(actor), grilla, **kw)


def snap_ras_texto(actor, objetivo, eje="x", **kw) -> str:
    from . import oracle_snap
    return oracle_snap.texto_ras(pieza(actor), pieza(objetivo), eje, **kw)


def physics_texto(actor, soportes=None, **kw) -> str:
    from . import oracle_physics, physics
    if soportes is None:
        soportes = physics.soportes_del_nivel()
    sp = piezas([s for s in soportes if s != actor])
    return oracle_physics.verificar_texto(pieza(actor), sp, **kw)


def physics(actor, soportes=None, **kw) -> dict:
    from . import oracle_physics, physics as _ph
    if soportes is None:
        soportes = _ph.soportes_del_nivel()
    sp = piezas([s for s in soportes if s != actor])
    return oracle_physics.verificar(pieza(actor), sp, **kw)


def reemplazo_texto(nuevo, objetivo, **kw) -> str:
    from . import oracle_reemplazo
    return oracle_reemplazo.verificar_texto(pieza(nuevo), objetivo, **kw)


def reemplazo(nuevo, objetivo, **kw) -> dict:
    from . import oracle_reemplazo
    return oracle_reemplazo.verificar(pieza(nuevo), objetivo, **kw)
