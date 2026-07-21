"""Pared por spline — coloca segmentos modulares de muro a lo largo de un spline (el "scatter a lo
largo de curva" de Dash, aplicado a muros para BotOO).

Flujo tipo Dash: `crear_spline()` agrega a la escena un actor con un SplineComponent EDITABLE (vía
SubobjectDataSubsystem — `add_component_by_class` no existe en Python 5.7) que se moldea en el
viewport; después `construir(actor)` lee sus puntos y levanta la pared, un segmento por tramo de
`largo_segmento`, orientado según la tangente. El oráculo (`jam.oracle_pared`) verifica que la cadena
sea continua (los segmentos no se despegan del spline en las juntas) y cubra el largo.
"""

from __future__ import annotations

import math

import unreal

from . import library, place

_WORLD = unreal.SplineCoordinateSpace.WORLD


def _sds() -> unreal.SubobjectDataSubsystem:
    return unreal.get_engine_subsystem(unreal.SubobjectDataSubsystem)


def _actor_sub() -> unreal.EditorActorSubsystem:
    return unreal.get_editor_subsystem(unreal.EditorActorSubsystem)


def crear_spline(puntos=None, *, seleccionar: bool = True):
    """Crea un actor con un SplineComponent editable. `puntos` = lista de (x,y[,z]) en mundo (cm);
    por defecto una L. Devuelve el actor (queda seleccionado para editarlo en el viewport)."""
    if puntos is None:
        puntos = [(0.0, 0.0, 0.0), (600.0, 0.0, 0.0), (600.0, 600.0, 0.0)]
    actor = _actor_sub().spawn_actor_from_class(
        unreal.Actor, unreal.Vector(0, 0, 0), unreal.Rotator(0, 0, 0)
    )
    actor.set_actor_label("Jam_spline_pared")
    sds = _sds()
    handles = sds.k2_gather_subobject_data_for_instance(actor)
    params = unreal.AddNewSubobjectParams()
    params.set_editor_property("parent_handle", handles[0])
    params.set_editor_property("new_class", unreal.SplineComponent)
    h, fail = sds.add_new_subobject(params)
    if fail and str(fail):
        unreal.log_error(f"[Jam] crear_spline: {fail}")
    sds.rename_subobject(h, unreal.Text("JamSplinePared"))
    sc = actor.get_component_by_class(unreal.SplineComponent)
    vecs = [unreal.Vector(p[0], p[1], p[2] if len(p) > 2 else 0.0) for p in puntos]
    sc.set_spline_points(vecs, _WORLD, True)
    if seleccionar:
        _actor_sub().set_selected_level_actors([actor])
    return actor


def spline_de(actor):
    """El SplineComponent del actor, o None."""
    return actor.get_component_by_class(unreal.SplineComponent) if actor else None


def seleccionado_con_spline():
    """Primer actor seleccionado que tenga un SplineComponent, o None."""
    for a in _actor_sub().get_selected_level_actors():
        if spline_de(a):
            return a
    return None


def construir(actor, asset, *, alto: float = 300.0, espesor: float = 40.0,
              largo_segmento: float = 200.0, z_base=None) -> dict:
    """Levanta una pared de segmentos modulares a lo largo del spline de `actor`.
    Devuelve un dict con los actores + los datos que necesita el oráculo (centros, forwards, paso)."""
    sc = spline_de(actor)
    if sc is None:
        return {"segmentos": [], "n": 0, "paso": 0.0, "largo_spline": 0.0,
                "centros": [], "forwards": [], "actor_spline": actor}
    largo = sc.get_spline_length()
    n = max(1, round(largo / largo_segmento))
    paso = largo / n
    mesh = library.cargar_malla(asset) if isinstance(asset, str) else asset
    segmentos, centros, forwards = [], [], []
    for i in range(n):
        s = (i + 0.5) * paso
        loc = sc.get_location_at_distance_along_spline(s, _WORLD)
        dirv = sc.get_direction_at_distance_along_spline(s, _WORLD)  # unitario
        yaw = math.degrees(math.atan2(dirv.y, dirv.x))
        zb = loc.z if z_base is None else z_base
        seg = place.colocar(mesh, (loc.x, loc.y, zb + alto / 2.0), (0.0, 0.0, yaw))
        seg.set_actor_scale3d(unreal.Vector(paso / 100.0, espesor / 100.0, alto / 100.0))
        seg.set_actor_label(f"Jam_muro_{i}")
        segmentos.append(seg)
        centros.append((loc.x, loc.y))
        forwards.append((dirv.x, dirv.y))
    return {"segmentos": segmentos, "n": n, "paso": paso, "largo_spline": largo,
            "centros": centros, "forwards": forwards, "actor_spline": actor}
