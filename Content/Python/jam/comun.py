"""La BASE COMÚN: verbos que se calculan en el núcleo y corren igual en Unreal, Godot y Unity.

Tarea `base-comun`. Cada entrada de `IMPLEMENTA` recibe lo que llega por el cable y los params del
verbo, y devuelve un dato del núcleo (una `malla_core.Malla`). Ningún motor recalcula: cada adaptador
sólo lo vuelve suyo con su primitiva «malla desde datos». Un verbo entra acá con el MISMO nombre que
tenía en Unreal (decisión de Brian, 2026-09-28): si un motor corriera otro código, la base no sería
común.

Cerebro puro: cero `import unreal`.
"""

from __future__ import annotations

from . import malla_core


def _resultado(result: dict, clave: str, etiqueta: str) -> tuple:
    """`(dato, texto)` de un cálculo del núcleo que devuelve `{clave, info}` o `{error}`."""
    if "error" in result:
        raise RuntimeError(result["error"])
    return result[clave], f"{etiqueta} ✓ — {result['info']}"


def mesh_box(_entrada=None, *, size_x=100.0, size_y=100.0, size_z=100.0,
             steps_x=0, steps_y=0, steps_z=0) -> malla_core.Malla:
    m = malla_core.caja(size_x=size_x, size_y=size_y, size_z=size_z,
                        steps_x=steps_x, steps_y=steps_y, steps_z=steps_z)
    return m, f"BOX M ✓ — {malla_core.info(m)}"


# ---- primitivas planas y operadores de malla (agy1, contra el fixture de Unreal) ----

def mesh_quad(_entrada=None, *, width=100.0, height=100.0) -> tuple:
    from . import malla_plana
    m = malla_plana.quad(width=width, height=height)
    return m, f"QUAD M ✓ — {malla_core.info(m)}"


def mesh_grid(_entrada=None, *, width=500.0, height=500.0, columns=6, rows=6) -> tuple:
    from . import malla_plana
    m = malla_plana.grid(width=width, height=height, columns=columns, rows=rows)
    return m, f"GRID M ✓ — {malla_core.info(m)}"


def mesh_disc(_entrada=None, *, radius=100.0, sides=24, start_angle=0.0, end_angle=360.0,
              hole_radius=0.0) -> tuple:
    from . import malla_plana
    m = malla_plana.disc(radius=radius, sides=sides, start_angle=start_angle,
                         end_angle=end_angle, hole_radius=hole_radius)
    return m, f"DISC M ✓ — {malla_core.info(m)}"


# ---- sólidos de revolución (agy2, contra el fixture de Unreal) ----

def mesh_cylinder(_entrada=None, *, radius=50.0, height=200.0, sides=16, height_steps=1,
                  capped=True) -> tuple:
    from . import malla_revolucion
    m = malla_revolucion.cilindro(radius=radius, height=height, sides=sides,
                                  height_steps=height_steps, capped=capped)
    return m, f"CYLINDER M ✓ — {malla_core.info(m)}"


def mesh_cone(_entrada=None, *, base_radius=60.0, top_radius=0.0, height=200.0, sides=16,
              height_steps=4, capped=True) -> tuple:
    from . import malla_revolucion
    m = malla_revolucion.cono(base_radius=base_radius, top_radius=top_radius, height=height,
                              sides=sides, height_steps=height_steps, capped=capped)
    return m, f"CONE M ✓ — {malla_core.info(m)}"


def mesh_sphere(_entrada=None, *, radius=100.0, latitude_steps=8, longitude_steps=12) -> tuple:
    from . import malla_revolucion
    m = malla_revolucion.esfera(radius=radius, latitude_steps=latitude_steps,
                                longitude_steps=longitude_steps)
    return m, f"SPHERE M ✓ — {malla_core.info(m)}"


def _exigir_malla(valor, verbo: str) -> malla_core.Malla:
    if not isinstance(valor, malla_core.Malla):
        raise RuntimeError(f"{verbo} necesita una malla M del núcleo")
    return valor


def mesh_transform(entrada=None, *, x=0.0, y=0.0, z=0.0, pitch=0.0, yaw=0.0, roll=0.0,
                   scale_x=1.0, scale_y=1.0, scale_z=1.0) -> tuple:
    from . import malla_ops
    m = malla_ops.transformar(_exigir_malla(entrada, "mesh_transform"), x=x, y=y, z=z, pitch=pitch,
                              yaw=yaw, roll=roll, scale_x=scale_x, scale_y=scale_y, scale_z=scale_z)
    return m, f"TRANSFORM M ✓ — {malla_core.info(m)}"


def mesh_merge(entrada=None) -> tuple:
    from . import malla_ops
    m = malla_ops.juntar([_exigir_malla(v, "mesh_merge") for v in (entrada or [])])
    return m, f"MERGE M ✓ — {malla_core.info(m)}"


def mesh_pipe(entrada=None, *, radius_start=30.0, radius_end=5.0, sides=10, samples=16, capped=True,
              profile_rotation=0.0, miter_limit=4.0, radius_from_parent=0.0, pivot_uvs=False) -> tuple:
    """El tubo sobre una curva (agy1, contra el fixture de Unreal). En Unreal sigue con Geometry
    Script, que además arma los UV de Pivot Painter (`pivot_uvs`), que la malla del núcleo no lleva."""
    from . import malla_tubo
    m = malla_tubo.tubo(entrada, radius_start=radius_start, radius_end=radius_end, sides=sides,
                        samples=samples, capped=capped, profile_rotation=profile_rotation,
                        miter_limit=miter_limit, radius_from_parent=radius_from_parent,
                        pivot_uvs=pivot_uvs)
    return m, f"PIPE M ✓ — {malla_core.info(m)}"


# ---- curvas y series: se mudaron de `tools.py` tal cual (misma firma, mismo texto) ----

def graph_curve(_input=None, *, start_value=1.0, end_value=0.15, shape="custom",
                  power=2.0, midpoint=0.55, mid_value=0.72, samples=16) -> tuple:
    from . import fields
    result = fields.graph_curve(
        start_value=float(start_value), end_value=float(end_value), shape=str(shape),
        power=float(power), midpoint=float(midpoint), mid_value=float(mid_value),
        samples=int(samples),
    )
    return _resultado(result, "series", "GRAPH CURVE N[]")


def series_range(_input=None, *, start=0.0, end=1.0, count=11) -> tuple:
    from . import fields
    result = fields.series_range(start=float(start), end=float(end), count=int(count))
    return _resultado(result, "series", "RANGE N[]")


def series_remap(series_input, *, source_min=0.0, source_max=1.0,
                   target_min=0.0, target_max=1.0, clamp=True) -> tuple:
    from . import fields
    result = fields.series_remap(
        series_input, source_min=float(source_min), source_max=float(source_max),
        target_min=float(target_min), target_max=float(target_max), clamp=bool(clamp))
    return _resultado(result, "series", "REMAP N[]")


def curve_bezier(_input=None, *, start_x=0.0, start_y=0.0, start_z=0.0,
                   end_x=0.0, end_y=0.0, end_z=500.0,
                   bend_x=0.0, bend_y=0.0, bend_z=0.0, segments=8) -> tuple:
    from . import curve
    result = curve.bezier(
        start_x=float(start_x), start_y=float(start_y), start_z=float(start_z),
        end_x=float(end_x), end_y=float(end_y), end_z=float(end_z),
        bend_x=float(bend_x), bend_y=float(bend_y), bend_z=float(bend_z),
        segments=int(segments),
    )
    return _resultado(result, "curve", "BEZIER S")


def curve_polyline(_input=None, *, x=None, y=None, z=None, closed=False) -> tuple:
    from . import curve
    result = curve.polyline(x=x, y=y, z=z, closed=bool(closed))
    return _resultado(result, "curve", "POLYLINE S")


def curve_interpolate(_input=None, *, x=None, y=None, z=None, segments=8) -> tuple:
    from . import curve
    result = curve.interpolate(x=x, y=y, z=z, segments=int(segments))
    return _resultado(result, "curve", "INTERPOLATE S")


def curve_line(_input=None, *, desde="0,0,0", hasta="0,0,300") -> tuple:
    from . import curve, math_core
    result = curve.line(math_core._vector(desde, "desde"), math_core._vector(hasta, "hasta"))
    return _resultado(result, "curve", "LINE S")


def curve_line_sdl(_input=None, *, origen="0,0,0", direccion="0,0,1", largo=300.0) -> tuple:
    from . import curve, math_core
    result = curve.line_sdl(math_core._vector(origen, "origen"),
                            math_core._vector(direccion, "direccion"), largo)
    return _resultado(result, "curve", "LINE SDL S")


def curve_move(curve_input, *, desplazamiento="0,0,100") -> tuple:
    from . import curve, math_core
    result = curve.move(curve_input, math_core._vector(desplazamiento, "desplazamiento"))
    return _resultado(result, "curve", "MOVE S")


def curve_resample(curve_input, *, count=24, samples=32) -> tuple:
    from . import curve
    result = curve.resample(curve_input, count=int(count), samples=int(samples))
    return _resultado(result, "curve", "RESAMPLE S")


def curve_smooth(curve_input, *, iterations=2, strength=0.5,
                   preserve_ends=True, samples=32) -> tuple:
    from . import curve
    result = curve.smooth(
        curve_input, iterations=int(iterations), strength=float(strength),
        preserve_ends=bool(preserve_ends), samples=int(samples))
    return _resultado(result, "curve", "SMOOTH S")


# ---- frames y ramas: también se mudaron de `tools.py` tal cual ----

def curve_frames(curve_input, *, count=12, start=0.0, end=1.0,
                   radial_offset=0.0, turns=0.0, angle_offset=0.0,
                   radius_start=0.0, radius_end=0.0, samples=32, seed=7) -> tuple:
    from . import curve
    result = curve.frame_stream(
        curve_input, count=int(count), start=float(start), end=float(end),
        radial_offset=float(radial_offset), turns=float(turns),
        angle_offset=float(angle_offset), radius_start=float(radius_start),
        radius_end=float(radius_end), samples=int(samples), seed=int(seed),
    )
    return _resultado(result, "frame_set", "FRAMES F")


def distribute_frames(frame_input, *, count=12, start=0.0, end=1.0,
                        rotate_per_index=137.5, angle_offset=0.0,
                        angle_jitter=0.0, parameter_jitter=0.0, seed=7) -> tuple:
    from . import curve
    result = curve.distribute_frames(
        frame_input, count=int(count), start=float(start), end=float(end),
        rotate_per_index=float(rotate_per_index), angle_offset=float(angle_offset),
        angle_jitter=float(angle_jitter), parameter_jitter=float(parameter_jitter),
        seed=int(seed),
    )
    return _resultado(result, "frame_set", "DISTRIBUTE F")


def transform_frames(frame_input, *, offset_x=0.0, offset_y=0.0, offset_z=0.0,
                       pitch=0.0, yaw=0.0, roll=0.0, scale=1.0,
                       offset_jitter_x=0.0, offset_jitter_y=0.0,
                       offset_jitter_z=0.0, pitch_jitter=0.0,
                       yaw_jitter=0.0, roll_jitter=0.0, scale_jitter=0.0,
                       inherit_scale=True, seed=7) -> tuple:
    from . import curve
    result = curve.transform_frames(
        frame_input, offset_x=float(offset_x), offset_y=float(offset_y),
        offset_z=float(offset_z), pitch=float(pitch), yaw=float(yaw), roll=float(roll),
        scale=float(scale), offset_jitter_x=float(offset_jitter_x),
        offset_jitter_y=float(offset_jitter_y), offset_jitter_z=float(offset_jitter_z),
        pitch_jitter=float(pitch_jitter), yaw_jitter=float(yaw_jitter),
        roll_jitter=float(roll_jitter), scale_jitter=float(scale_jitter),
        inherit_scale=bool(inherit_scale), seed=int(seed),
    )
    return _resultado(result, "frame_set", "TRANSFORM F")


def points_to_frames(stream_input, *, orientacion="normal", escala=1.0,
                       escala_desde_peso=True, giro_al_azar=True, seed=7) -> tuple:
    """Puente P → F: convierte el stream de puntos de Flow en frames que consume el tab Mesh."""
    from . import curve
    result = curve.frames_desde_puntos(
        stream_input, orientacion=str(orientacion), escala=float(escala),
        escala_desde_peso=bool(escala_desde_peso), giro_al_azar=bool(giro_al_azar),
        seed=int(seed))
    return _resultado(result, "frame_set", "POINTS TO F")


def branch_from_frames(frame_input, *, length_min=200.0, length_max=400.0,
                         angle=55.0, angle_jitter=0.0, curl=20.0,
                         curl_jitter=0.0, segments=8, inherit_scale=True,
                         relative_to_parent=False, profile=None, seed=7) -> tuple:
    from . import curve
    result = curve.branch_from_frames(
        frame_input, length_min=float(length_min), length_max=float(length_max),
        angle=float(angle), angle_jitter=float(angle_jitter), curl=float(curl),
        curl_jitter=float(curl_jitter), segments=int(segments),
        inherit_scale=bool(inherit_scale),
        relative_to_parent=bool(relative_to_parent), profile=profile, seed=int(seed),
    )
    return _resultado(result, "curve", "BRANCH FROM F")


def curve_child(curve_input, *, at=0.5, length=300.0, angle=55.0, azimuth=0.0,
                  bend=40.0, radial_offset=0.0, segments=8, samples=32) -> tuple:
    from . import curve
    result = curve.child(
        curve_input, at=float(at), length=float(length), angle=float(angle),
        azimuth=float(azimuth), bend=float(bend), radial_offset=float(radial_offset),
        segments=int(segments), samples=int(samples),
    )
    return _resultado(result, "curve", "CHILD S")


def curve_branches(curve_input, *, count=12, start=0.2, end=0.92,
                     length_min=200.0, length_max=400.0,
                     parent_scale_start=1.0, parent_scale_end=1.0,
                     angle=70.0, angle_jitter=8.0, rotate_per_index=137.0,
                     azimuth=0.0, azimuth_jitter=5.0, bend=40.0,
                     bend_jitter=20.0, radial_offset=0.0,
                     segments=8, samples=32, seed=7) -> tuple:
    from . import curve
    result = curve.branches(
        curve_input, count=int(count), start=float(start), end=float(end),
        length_min=float(length_min), length_max=float(length_max),
        parent_scale_start=float(parent_scale_start), parent_scale_end=float(parent_scale_end),
        angle=float(angle), angle_jitter=float(angle_jitter),
        rotate_per_index=float(rotate_per_index), azimuth=float(azimuth),
        azimuth_jitter=float(azimuth_jitter), bend=float(bend),
        bend_jitter=float(bend_jitter), radial_offset=float(radial_offset),
        segments=int(segments), samples=int(samples), seed=int(seed),
    )
    return _resultado(result, "curve", "BRANCHES S")


def curve_fuse_collinear(curve_input, *, angle_tolerance=1.0,
                           distance_tolerance=0.01, samples=32) -> tuple:
    from . import curve
    result = curve.fuse_collinear(
        curve_input, angle_tolerance=float(angle_tolerance),
        distance_tolerance=float(distance_tolerance), samples=int(samples))
    return _resultado(result, "curve", "FUSE COLLINEAR S")


def curve_subdivide(curve_input, *, mode="distance", distance=100.0,
                      count=1, samples=32) -> tuple:
    from . import curve
    result = curve.subdivide(
        curve_input, mode=mode, distance=float(distance), count=int(count),
        samples=int(samples))
    return _resultado(result, "curve", "SUBDIVIDE S")


def curve_offset(curve_input, *, distance=100.0, side="left", plane="xy",
                   join="miter", miter_limit=4.0, samples=32) -> tuple:
    from . import curve
    result = curve.offset(
        curve_input, distance=float(distance), side=side, plane=plane, join=join,
        miter_limit=float(miter_limit), samples=int(samples))
    return _resultado(result, "curve", "OFFSET S")



IMPLEMENTA = {"mesh_box": mesh_box, **{v: globals()[v] for v in (
    "mesh_quad", "mesh_grid", "mesh_disc", "mesh_transform", "mesh_merge",
    "mesh_cylinder", "mesh_cone", "mesh_sphere", "mesh_pipe",
    "graph_curve", "series_range", "series_remap", "curve_bezier", "curve_polyline",
    "curve_interpolate", "curve_line", "curve_line_sdl", "curve_move", "curve_resample",
    "curve_smooth", "curve_frames", "distribute_frames", "transform_frames", "points_to_frames",
    "branch_from_frames", "curve_child", "curve_branches", "curve_fuse_collinear", "curve_subdivide",
    "curve_offset")}}
