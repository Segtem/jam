"""Fantasmas — la malla real antes de colocarla. DOS, y cada uno contesta una pregunta distinta:

  · AZUL «en vivo»: sigue el punto de mira. Contesta *dónde estoy apuntando*.
  · GRIS «objetivo»: está en lo que dicen los campos x/y/z. Contesta *dónde va a caer si coloco*.

Con `view` encendido y offsets en cero, los dos coinciden. Al separarlos (offset, o `view` apagado y
coordenadas a mano) se ve exactamente la diferencia entre la mira y el destino — que es lo que se
sentía raro cuando había un solo fantasma que a veces seguía la mira y a veces no.

Los dos se colocan por el ANCLA (`jam.pivot`), así que apoyan como apoyaría la pieza de verdad.

Reglas para que no contaminen nada:
  · tag `jam:ghost` → los oráculos los excluyen como vecinos (si no, cada pieza «CLAVA» contra su
    propio fantasma, que está justo donde uno va a colocar).
  · sin colisión → no pueden bloquear el raycast del punto de mira (si no, se apuntaría a sí mismo).
  · material translúcido con color (`jam.materials`) para leerlos como lo que son.
"""

from __future__ import annotations

import unreal

from .geometry import Vec3

TAG = "jam:ghost"

AZUL = unreal.LinearColor(0.1, 0.55, 1.0, 1.0)    # en vivo: dónde apunto
GRIS = unreal.LinearColor(0.6, 0.6, 0.62, 1.0)    # objetivo: dónde cae

# objetivo = lo que dicen los campos de la herramienta (x/y/z + si son offset de la mira)
_OBJETIVO: dict = {"x": 0.0, "y": 0.0, "z": 0.0, "view": True, "anchor": "base"}
_ESTADO: dict = {"handle": None, "fallos": 0,
                 "live": {"actor": None, "ruta": None},
                 "fixed": {"actor": None, "ruta": None}}


def encendido() -> bool:
    return _ESTADO["handle"] is not None


def _sub():
    return unreal.get_editor_subsystem(unreal.EditorActorSubsystem)


def _vivo(actor) -> bool:
    try:
        return actor is not None and bool(unreal.SystemLibrary.is_valid(actor))
    except Exception:  # noqa: BLE001
        return False


def _destruir(modo: str) -> None:
    slot = _ESTADO[modo]
    if _vivo(slot["actor"]):
        try:
            _sub().destroy_actor(slot["actor"])
        except Exception:  # noqa: BLE001
            pass
    slot["actor"] = None
    slot["ruta"] = None


def _asegurar(modo: str, color):
    """El fantasma de ese modo, para el asset ACTIVO. Lo rehace si cambió el asset o lo borraron."""
    from . import materials, session, ue
    slot = _ESTADO[modo]
    ruta = session.asset()
    if not ruta:
        _destruir(modo)
        return None
    if _vivo(slot["actor"]) and slot["ruta"] == ruta:
        return slot["actor"]

    _destruir(modo)
    malla = unreal.load_asset(ruta)
    if not isinstance(malla, unreal.StaticMesh):
        return None
    actor = _sub().spawn_actor_from_object(malla, unreal.Vector(0.0, 0.0, 0.0))
    if actor is None:
        return None

    actor.set_actor_label(f"JamGhost_{modo}_{malla.get_name()}")
    ue.set_tags(actor, [TAG])
    actor.set_actor_enable_collision(False)   # no debe bloquear el raycast de la mira

    mat = materials.instancia(color, 0.35, actor)
    if mat is not None:
        try:
            comp = actor.static_mesh_component
            for i in range(comp.get_num_materials()):
                comp.set_material(i, mat)
        except Exception:  # noqa: BLE001
            pass

    slot["actor"] = actor
    slot["ruta"] = ruta
    return actor


def _poner_en(actor, destino: Vec3) -> None:
    """Mueve el actor para que su ANCLA caiga en `destino` (mismo cálculo que hace `place`)."""
    from . import pivot as pv
    from . import ue
    loc = actor.get_actor_location()
    nueva = pv.location_para(ue.aabb(actor), Vec3(loc.x, loc.y, loc.z),
                             _OBJETIVO["anchor"] or "base", destino)
    actor.set_actor_location(unreal.Vector(nueva.x, nueva.y, nueva.z), False, False)


def objetivo(x: float, y: float, z: float, view: bool = True, anchor: str = "base") -> str:
    """Fija lo que muestra el fantasma GRIS: los valores de los campos de la herramienta."""
    _OBJETIVO.update({"x": float(x), "y": float(y), "z": float(z),
                      "view": bool(view), "anchor": anchor or "base"})
    if encendido():
        _tick()
    return (f"objetivo del fantasma: ({x:.0f}, {y:.0f}, {z:.0f})"
            + (" como offset de la mira" if view else " en absolutas"))


def _destinos():
    """(destino del azul, destino del gris). El azul es la mira cruda; el gris, donde caería la
    pieza según los campos: mira+offset si `view`, o las coordenadas absolutas si no."""
    from . import ue
    mira = ue.punto_de_mira()
    p = mira["punto"] if mira else None
    obj = _OBJETIVO
    if obj["view"]:
        if p is None:
            return None, None
        return p, Vec3(p.x + obj["x"], p.y + obj["y"], p.z + obj["z"])
    return p, Vec3(obj["x"], obj["y"], obj["z"])


def _tick(_delta=0.0) -> None:
    try:
        live_dest, fixed_dest = _destinos()

        # el azul sólo tiene sentido cuando la mira participa (view): si no, sería un fantasma
        # siguiendo al mouse mientras la pieza cae en otro lado — justo lo que confundía.
        if _OBJETIVO["view"] and live_dest is not None:
            a = _asegurar("live", AZUL)
            if a is not None:
                _poner_en(a, live_dest)
        else:
            _destruir("live")

        if fixed_dest is not None:
            g = _asegurar("fixed", GRIS)
            if g is not None:
                _poner_en(g, fixed_dest)

        _ESTADO["fallos"] = 0
    except Exception as e:  # noqa: BLE001
        _ESTADO["fallos"] += 1
        if _ESTADO["fallos"] >= 5:
            unreal.log_warning(f"[Jam] fantasmas apagados tras 5 fallos: {e}")
            apagar()


def encender() -> str:
    from . import session
    if encendido():
        return "los fantasmas ya estaban encendidos."
    if not session.asset():
        return "no hay asset activo: elegí uno en Content (o «pick») y volvé a encender el fantasma."
    _ESTADO["fallos"] = 0
    _ESTADO["handle"] = unreal.register_slate_post_tick_callback(_tick)
    _tick()
    return ("FANTASMAS ON ✓ — AZUL sigue el punto de mira · GRIS está donde va a caer la pieza "
            "según x/y/z. «Confirmar / Colocar» pone la pieza de verdad en el gris.")


def apagar() -> str:
    h = _ESTADO["handle"]
    if h is not None:
        try:
            unreal.unregister_slate_post_tick_callback(h)
        except Exception:  # noqa: BLE001
            pass
        _ESTADO["handle"] = None
    tenia = _vivo(_ESTADO["live"]["actor"]) or _vivo(_ESTADO["fixed"]["actor"])
    _destruir("live")
    _destruir("fixed")
    return "fantasmas OFF — borrados del nivel." if tenia else "los fantasmas ya estaban apagados."


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
    for modo in ("live", "fixed"):
        _ESTADO[modo]["actor"] = None
        _ESTADO[modo]["ruta"] = None
    return n
