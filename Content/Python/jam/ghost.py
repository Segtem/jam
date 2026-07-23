"""Fantasma — la malla real siguiendo el punto de mira, antes de colocarla.

El gizmo dice DÓNDE va a caer la pieza; el fantasma muestra QUÉ va a caer, con su forma y su tamaño
reales, apoyado en el piso como quedaría. Es el paso previo natural a «Confirmar / Colocar».

Reglas para que el fantasma no contamine nada:
  · va marcado con el tag `jam:ghost` → los oráculos lo ignoran como vecino (si no, cada pieza
    «CLAVA» contra su propio fantasma, que está exactamente donde uno va a colocar).
  · sin colisión → no puede bloquear el raycast del punto de mira (si no, se apuntaría a sí mismo).
  · se le intenta poner un material translúcido del motor para que se lea como fantasma y no como
    una pieza ya colocada.
"""

from __future__ import annotations

import unreal

TAG = "jam:ghost"

# Materiales translúcidos que trae el motor (los del editor de físicas). Se usa el primero que cargue.
_MATERIALES = (
    "/Engine/EditorMaterials/PhAT_ElemSelectedMaterial",
    "/Engine/EditorMaterials/PhAT_ElemUnselectedMaterial",
    "/Engine/EngineMaterials/Widget3DPassThrough_Translucent",
)

_ESTADO: dict = {"handle": None, "actor": None, "ruta": None, "dz": 0.0, "fallos": 0}


def encendido() -> bool:
    return _ESTADO["handle"] is not None


def _sub():
    return unreal.get_editor_subsystem(unreal.EditorActorSubsystem)


def _vivo(actor) -> bool:
    try:
        return actor is not None and bool(unreal.SystemLibrary.is_valid(actor))
    except Exception:  # noqa: BLE001
        return False


def _material():
    for ruta in _MATERIALES:
        try:
            m = unreal.load_asset(ruta)
            if isinstance(m, unreal.MaterialInterface):
                return m
        except Exception:  # noqa: BLE001
            continue
    return None


def _destruir() -> None:
    if _vivo(_ESTADO["actor"]):
        try:
            _sub().destroy_actor(_ESTADO["actor"])
        except Exception:  # noqa: BLE001
            pass
    _ESTADO["actor"] = None
    _ESTADO["ruta"] = None


def _asegurar_actor():
    """El fantasma del asset ACTIVO. Si cambió el asset (o alguien lo borró), lo rehace."""
    from . import session, ue
    ruta = session.asset()
    if not ruta:
        _destruir()
        return None
    if _vivo(_ESTADO["actor"]) and _ESTADO["ruta"] == ruta:
        return _ESTADO["actor"]

    _destruir()
    malla = unreal.load_asset(ruta)
    if not isinstance(malla, unreal.StaticMesh):
        return None
    actor = _sub().spawn_actor_from_object(malla, unreal.Vector(0.0, 0.0, 0.0))
    if actor is None:
        return None

    actor.set_actor_label(f"JamGhost_{malla.get_name()}")
    ue.set_tags(actor, [TAG])
    actor.set_actor_enable_collision(False)   # no debe bloquear el raycast de la mira

    mat = _material()
    if mat is not None:
        try:
            comp = actor.static_mesh_component
            for i in range(comp.get_num_materials()):
                comp.set_material(i, mat)
        except Exception:  # noqa: BLE001
            pass

    # offset del pivote a la base: para apoyarlo, no para clavarlo a medias en el piso
    o, e = actor.get_actor_bounds(False)
    loc = actor.get_actor_location()
    _ESTADO["dz"] = loc.z - (o.z - e.z)
    _ESTADO["actor"] = actor
    _ESTADO["ruta"] = ruta
    return actor


def _tick(_delta=0.0) -> None:
    try:
        from . import ue
        actor = _asegurar_actor()
        if actor is None:
            return
        mira = ue.punto_de_mira()
        if mira is None or mira["punto"] is None:
            return
        p = mira["punto"]
        actor.set_actor_location(unreal.Vector(p.x, p.y, p.z + _ESTADO["dz"]), False, False)
        _ESTADO["fallos"] = 0
    except Exception as e:  # noqa: BLE001
        _ESTADO["fallos"] += 1
        if _ESTADO["fallos"] >= 5:
            unreal.log_warning(f"[Jam] fantasma apagado tras 5 fallos: {e}")
            apagar()


def encender() -> str:
    from . import session
    if encendido():
        return "el fantasma ya estaba encendido."
    if not session.asset():
        return "no hay asset activo: elegí uno en Content (o «pick») y volvé a encender el fantasma."
    _ESTADO["fallos"] = 0
    _ESTADO["handle"] = unreal.register_slate_post_tick_callback(_tick)
    _tick()
    return ("FANTASMA ON ✓ — la malla sigue el punto de mira (sin colisión y fuera del oráculo). "
            "«Confirmar / Colocar» pone la pieza de verdad ahí.")


def apagar() -> str:
    h = _ESTADO["handle"]
    if h is not None:
        try:
            unreal.unregister_slate_post_tick_callback(h)
        except Exception:  # noqa: BLE001
            pass
        _ESTADO["handle"] = None
    tenia = _vivo(_ESTADO["actor"])
    _destruir()
    return "fantasma OFF — borrado del nivel." if tenia else "el fantasma ya estaba apagado."


def limpiar_huerfanos() -> int:
    """Borra fantasmas que hayan quedado de una sesión anterior (por si el editor se cerró crudo)."""
    from . import ue
    n = 0
    for a in _sub().get_all_level_actors():
        if TAG in ue.tags(a):
            try:
                _sub().destroy_actor(a)
                n += 1
            except Exception:  # noqa: BLE001
                pass
    _ESTADO["actor"] = None
    _ESTADO["ruta"] = None
    return n
