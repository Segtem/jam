"""Reemplazar — cambia una caja de blockout por el asset real preservando el footprint (el "replace"
de Dash, pero verificando que el contrato espacial se mantenga).

`reemplazar(blockout, asset)` mide el AABB del blockout, spawnea el asset real en su lugar,
opcionalmente lo escala para que su AABB calce con el del blockout, y alinea centro-XY + base.
Después borra el blockout. Devuelve (nuevo_actor, objetivo) donde `objetivo` es el footprint que
`jam.oracle_reemplazo` debe verificar que se preservó.

Por qué importa: el oráculo de espacio validó la winnability sobre el footprint del blockout. Si el
arte final ocupa otro footprint, el pasillo se angosta o el hueco se tapa — Dash cambia la malla y
no te avisa; Jam sí.
"""

from __future__ import annotations

import unreal

from . import oracle_placement, place


def _actor_sub() -> unreal.EditorActorSubsystem:
    return unreal.get_editor_subsystem(unreal.EditorActorSubsystem)


def reemplazar(blockout, asset, *, ajustar_escala: bool = True, borrar_blockout: bool = True):
    """Sustituye `blockout` por `asset`. Si `ajustar_escala`, escala el asset para calzar el AABB
    del blockout. Alinea centro-XY + base. Devuelve (nuevo_actor, objetivo_footprint)."""
    ob, eb = oracle_placement.aabb(blockout)
    objetivo = {"cx": ob.x, "cy": ob.y, "base": ob.z - eb.z, "ex": eb.x, "ey": eb.y, "ez": eb.z}
    rot = blockout.get_actor_rotation()
    loc = blockout.get_actor_location()
    nuevo = place.colocar(asset, (loc.x, loc.y, loc.z), (rot.roll, rot.pitch, rot.yaw))
    if nuevo is None:
        return None, objetivo

    if ajustar_escala:
        _, en = oracle_placement.aabb(nuevo)  # AABB nativo (escala 1)
        sx = eb.x / en.x if en.x > 1e-4 else 1.0
        sy = eb.y / en.y if en.y > 1e-4 else 1.0
        sz = eb.z / en.z if en.z > 1e-4 else 1.0
        nuevo.set_actor_scale3d(unreal.Vector(sx, sy, sz))

    # realinear centro-XY + base al footprint del blockout (el pivote puede no estar en el centro)
    on2, en2 = oracle_placement.aabb(nuevo)
    dx = objetivo["cx"] - on2.x
    dy = objetivo["cy"] - on2.y
    dz = objetivo["base"] - (on2.z - en2.z)
    l = nuevo.get_actor_location()
    nuevo.set_actor_location(unreal.Vector(l.x + dx, l.y + dy, l.z + dz), False, True)

    if borrar_blockout:
        _actor_sub().destroy_actor(blockout)
    return nuevo, objetivo
