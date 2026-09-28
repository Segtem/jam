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


IMPLEMENTA = {"mesh_box": mesh_box, **{v: globals()[v] for v in (
    "graph_curve", "series_range", "series_remap", "curve_bezier", "curve_polyline",
    "curve_interpolate", "curve_line", "curve_line_sdl", "curve_move", "curve_resample",
    "curve_smooth")}}
