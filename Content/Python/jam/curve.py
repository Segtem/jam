"""Curvas transitivas del Graph.

`CurvePath` es el dato liviano que viaja por cables `S` cuando la curva nace dentro del Graph. No
crea actores ni Content. Los consumidores también aceptan un Actor/SplineComponent real, de modo que
`create_spline → mesh_pipe` sirve como variante editable desde el viewport.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import unreal


@dataclass(frozen=True)
class CurvePath:
    points: tuple[tuple[float, float, float], ...]
    scale: float = 1.0
    source_parent_index: int = -1
    source_local_index: int = -1
    seed: int = 0
    pivot_index: int = -1
    parent_radius: float = 0.0

    @property
    def length(self) -> float:
        return sum(math.dist(a, b) for a, b in zip(self.points, self.points[1:]))


@dataclass(frozen=True)
class CurveSet:
    """Lista inmutable de curvas que sigue viajando por un único cable ``S``.

    TreeGen no entrega una sola rama: su actor ``Branch`` produce muchas curvas hijas y los hijos
    consumen el conjunto completo. Mantener ese comportamiento en el mismo tipo visual evita crear
    decenas de nodos manuales y conserva la semántica de listas de Grasshopper.
    """

    paths: tuple[CurvePath, ...]

    @property
    def length(self) -> float:
        return sum(path.length for path in self.paths)


@dataclass(frozen=True)
class CurveFrame:
    """Frame jerárquico sobre una curva.

    Los cuatro primeros campos mantienen el contrato geométrico usado por ``curve.child`` y los
    generadores de malla. El resto es metadata de flow: permite que los próximos nodos distribuyan,
    transformen y elijan assets sin perder de qué curva padre ni de qué muestra nació cada frame.
    """

    position: tuple[float, float, float]
    tangent: tuple[float, float, float]
    outward: tuple[float, float, float]
    parameter: float
    parent_index: int = 0
    local_index: int = 0
    scale: float = 1.0
    radius: float = 0.0
    seed: int = 0
    pivot_index: int = -1
    # Largo de la curva de la que nació el frame. Permite que un hijo mida una FRACCIÓN del padre en
    # vez de centímetros absolutos: sin esto, alargar el tronco deja las ramas donde estaban.
    parent_length: float = 0.0


@dataclass(frozen=True)
class FrameSet:
    """Stream inmutable ``F`` de frames, posiblemente proveniente de varias curvas padre."""

    frames: tuple[CurveFrame, ...]
    parent_count: int

    def __len__(self) -> int:
        return len(self.frames)


def bezier(*, start_x: float = 0.0, start_y: float = 0.0, start_z: float = 0.0,
           end_x: float = 0.0, end_y: float = 0.0, end_z: float = 500.0,
           bend_x: float = 0.0, bend_y: float = 0.0, bend_z: float = 0.0,
           segments: int = 8) -> dict:
    """Curva Bézier cuadrática; `bend_*` desplaza el control desde el punto medio."""
    raw = (start_x, start_y, start_z, end_x, end_y, end_z, bend_x, bend_y, bend_z)
    try:
        values = tuple(float(value) for value in raw)
    except (TypeError, ValueError):
        return {"error": "las coordenadas de curve_bezier deben ser numéricas."}
    if not all(math.isfinite(value) for value in values):
        return {"error": "curve_bezier contiene una coordenada no finita."}
    segments = int(segments)
    if segments < 2 or segments > 128:
        return {"error": "segments debe estar entre 2 y 128."}

    sx, sy, sz, ex, ey, ez, bx, by, bz = values
    if math.dist((sx, sy, sz), (ex, ey, ez)) < 1e-4:
        return {"error": "el inicio y el final de curve_bezier no pueden coincidir."}
    control = ((sx + ex) * 0.5 + bx, (sy + ey) * 0.5 + by, (sz + ez) * 0.5 + bz)
    points = []
    for index in range(segments + 1):
        t = index / segments
        one_minus = 1.0 - t
        points.append((
            one_minus * one_minus * sx + 2.0 * one_minus * t * control[0] + t * t * ex,
            one_minus * one_minus * sy + 2.0 * one_minus * t * control[1] + t * t * ey,
            one_minus * one_minus * sz + 2.0 * one_minus * t * control[2] + t * t * ez,
        ))
    path = CurvePath(tuple(points))
    return {"curve": path, "info": f"{len(path.points)} points · {path.length:.1f} cm"}


def _spline_points(value, samples: int) -> tuple[tuple[float, float, float], ...]:
    """Convierte un SplineComponent/Actor en puntos; helper interno sin listas."""
    if isinstance(value, CurvePath):
        return value.points

    spline = None
    spline_type = getattr(unreal, "SplineComponent", None)
    if spline_type is not None and isinstance(value, spline_type):
        spline = value
    elif value is not None and hasattr(value, "get_component_by_class") and spline_type is not None:
        spline = value.get_component_by_class(spline_type)
    if spline is None:
        return ()

    samples = max(2, min(256, int(samples)))
    length = float(spline.get_spline_length())
    world = unreal.SplineCoordinateSpace.WORLD
    result = []
    for index in range(samples + 1):
        point = spline.get_location_at_distance_along_spline(length * index / samples, world)
        result.append((float(point.x), float(point.y), float(point.z)))
    return tuple(result)


def paths_of(value, *, samples: int = 16) -> tuple[CurvePath, ...]:
    """Normaliza una curva o colección ``S`` a una tupla de ``CurvePath`` válidos."""
    if isinstance(value, CurveSet):
        return tuple(path for path in value.paths if len(path.points) >= 2)
    if isinstance(value, CurvePath):
        return (value,) if len(value.points) >= 2 else ()
    points = _spline_points(value, samples)
    return (CurvePath(points),) if len(points) >= 2 else ()


def points_of(value, *, samples: int = 16) -> tuple[tuple[float, float, float], ...]:
    """Normaliza un ``S`` singular a una polilínea; una colección requiere ``paths_of``."""
    paths = paths_of(value, samples=samples)
    return paths[0].points if len(paths) == 1 else ()


def _normalized(vector):
    length = math.sqrt(sum(component * component for component in vector))
    if length < 1e-8:
        return (0.0, 0.0, 0.0)
    return tuple(component / length for component in vector)


def _cross(a, b):
    return (
        a[1] * b[2] - a[2] * b[1],
        a[2] * b[0] - a[0] * b[2],
        a[0] * b[1] - a[1] * b[0],
    )


def _sample_polyline(points, normalized_distance: float):
    lengths = [math.dist(a, b) for a, b in zip(points, points[1:])]
    total = sum(lengths)
    if total < 1e-6:
        return points[0], (0.0, 0.0, 0.0)
    target = min(1.0, max(0.0, normalized_distance)) * total
    walked = 0.0
    for index, segment_length in enumerate(lengths):
        if segment_length < 1e-8:
            continue
        if walked + segment_length >= target or index == len(lengths) - 1:
            local = min(1.0, max(0.0, (target - walked) / segment_length))
            start, end = points[index], points[index + 1]
            position = tuple(start[axis] + (end[axis] - start[axis]) * local for axis in range(3))
            tangent = _normalized(tuple(end[axis] - start[axis] for axis in range(3)))
            return position, tangent
        walked += segment_length
    return points[-1], _normalized(tuple(points[-1][i] - points[-2][i] for i in range(3)))


def frames(value, *, count: int = 12, start: float = 0.1, end: float = 0.95,
           radial_offset: float = 0.0, turns: float = 2.0,
           angle_offset: float = 0.0, samples: int = 32) -> dict:
    """Muestrea frames equidistantes con giro helicoidal estable, incluso en curvas verticales."""
    try:
        count, samples = int(count), int(samples)
        start, end = float(start), float(end)
        radial_offset, turns, angle_offset = (
            float(radial_offset), float(turns), float(angle_offset))
    except (TypeError, ValueError):
        return {"error": "los parámetros de curve_frames deben ser numéricos."}
    if count < 1 or count > 512:
        return {"error": "count debe estar entre 1 y 512."}
    if not all(math.isfinite(v) for v in (start, end, radial_offset, turns, angle_offset)):
        return {"error": "curve_frames contiene un número no finito."}
    if start < 0.0 or end > 1.0 or start > end:
        return {"error": "start/end deben cumplir 0 ≤ start ≤ end ≤ 1."}

    points = points_of(value, samples=max(samples, count * 2))
    if len(points) < 2 or sum(math.dist(a, b) for a, b in zip(points, points[1:])) < 1e-6:
        return {"error": "curve_frames necesita una curva S válida con longitud mayor que cero."}

    result = []
    for index in range(count):
        fraction = index / (count - 1) if count > 1 else 0.0
        parameter = start + (end - start) * fraction
        position, tangent = _sample_polyline(points, parameter)
        reference = (0.0, 0.0, 1.0) if abs(tangent[2]) < 0.95 else (1.0, 0.0, 0.0)
        first_axis = _normalized(_cross(tangent, reference))
        second_axis = _normalized(_cross(tangent, first_axis))
        angle = math.radians(angle_offset + turns * 360.0 * fraction)
        outward = tuple(
            first_axis[axis] * math.cos(angle) + second_axis[axis] * math.sin(angle)
            for axis in range(3)
        )
        displaced = tuple(position[axis] + outward[axis] * radial_offset for axis in range(3))
        result.append(CurveFrame(displaced, tangent, outward, parameter))
    return {"frames": tuple(result), "info": f"{len(result)} frames · {start:.2f}→{end:.2f}"}


def frame_stream(value, *, count: int = 12, start: float = 0.0, end: float = 1.0,
                 radial_offset: float = 0.0, turns: float = 0.0,
                 angle_offset: float = 0.0, radius_start: float = 0.0,
                 radius_end: float = 0.0, samples: int = 32, seed: int = 7) -> dict:
    """Convierte cada curva ``S`` en un stream jerárquico de frames ``F``.

    ``frames`` se conserva como helper singular para los verbos existentes. Este wrapper es el
    contrato público del Graph: expande también un ``CurveSet`` y anota procedencia, escala, radio,
    semilla estable e índice de pivote en cada muestra.
    """
    try:
        count, samples, seed = int(count), int(samples), int(seed)
        start, end = float(start), float(end)
        radial_offset, turns, angle_offset = (
            float(radial_offset), float(turns), float(angle_offset))
        radius_start, radius_end = float(radius_start), float(radius_end)
    except (TypeError, ValueError):
        return {"error": "los parámetros de curve_frames deben ser numéricos."}
    numeric = (start, end, radial_offset, turns, angle_offset, radius_start, radius_end)
    if not all(math.isfinite(item) for item in numeric):
        return {"error": "curve_frames contiene un número no finito."}
    if count < 1 or count > 512:
        return {"error": "count debe estar entre 1 y 512."}
    if samples < 2 or samples > 256:
        return {"error": "samples debe estar entre 2 y 256."}
    if start < 0.0 or end > 1.0 or start > end:
        return {"error": "start/end deben cumplir 0 ≤ start ≤ end ≤ 1."}
    if radius_start < 0.0 or radius_end < 0.0:
        return {"error": "radius_start/radius_end no pueden ser negativos."}

    paths = paths_of(value, samples=max(samples, count * 2))
    if not paths:
        return {"error": "curve_frames necesita una curva S válida con longitud mayor que cero."}
    if len(paths) * count > 4096:
        return {"error": "curve_frames no puede producir más de 4096 frames por nodo."}

    stream = []
    for parent_index, path in enumerate(paths):
        sampled = frames(
            path, count=count, start=start, end=end, radial_offset=radial_offset,
            turns=turns, angle_offset=angle_offset, samples=samples,
        )
        if "error" in sampled:
            return sampled
        for local_index, frame in enumerate(sampled["frames"]):
            fraction = local_index / (count - 1) if count > 1 else 0.0
            radius = (radius_start + (radius_end - radius_start) * fraction) * path.scale
            frame_seed = (
                seed * 1_000_003 + parent_index * 97_409 + local_index * 65_537
            ) & 0x7fffffff
            stream.append(CurveFrame(
                frame.position, frame.tangent, frame.outward, frame.parameter,
                parent_index=parent_index, local_index=local_index,
                scale=path.scale, radius=radius, seed=frame_seed,
                pivot_index=len(stream), parent_length=path.length,
            ))

    frame_set = FrameSet(tuple(stream), len(paths))
    return {
        "frame_set": frame_set,
        "info": f"{len(frame_set)} frames/{frame_set.parent_count} curvas · {start:.2f}→{end:.2f}",
    }


def _interpolate_frame(items: tuple[CurveFrame, ...], fraction: float) -> CurveFrame:
    """Interpola un frame dentro de un único padre; ``fraction`` está normalizado a su lista."""
    if len(items) == 1:
        return items[0]
    position = min(1.0, max(0.0, fraction)) * (len(items) - 1)
    left_index = min(len(items) - 1, int(math.floor(position)))
    right_index = min(len(items) - 1, left_index + 1)
    alpha = position - left_index
    left, right = items[left_index], items[right_index]

    def blend(a, b):
        return a + (b - a) * alpha

    tangent = _normalized(tuple(blend(left.tangent[i], right.tangent[i]) for i in range(3)))
    outward_raw = tuple(blend(left.outward[i], right.outward[i]) for i in range(3))
    projection = sum(outward_raw[i] * tangent[i] for i in range(3))
    outward = _normalized(tuple(
        outward_raw[i] - tangent[i] * projection for i in range(3)
    ))
    if outward == (0.0, 0.0, 0.0):
        outward = left.outward
    return CurveFrame(
        tuple(blend(left.position[i], right.position[i]) for i in range(3)),
        tangent,
        outward,
        blend(left.parameter, right.parameter),
        parent_index=left.parent_index,
        scale=blend(left.scale, right.scale),
        radius=blend(left.radius, right.radius),
        parent_length=left.parent_length,
    )


def distribute_frames(value, *, count: int = 12, start: float = 0.0, end: float = 1.0,
                      rotate_per_index: float = 137.5, angle_offset: float = 0.0,
                      angle_jitter: float = 0.0, parameter_jitter: float = 0.0,
                      seed: int = 7) -> dict:
    """Redistribuye un stream ``F`` por cada padre sin perder atributos jerárquicos.

    El dominio ``start/end`` se refiere a cada lista de frames padre. El giro se aplica alrededor de
    la tangente ya interpolada y los jitters provienen de un PRNG local determinista por muestra.
    """
    import random

    try:
        count, seed = int(count), int(seed)
        start, end = float(start), float(end)
        rotate_per_index, angle_offset = float(rotate_per_index), float(angle_offset)
        angle_jitter, parameter_jitter = float(angle_jitter), float(parameter_jitter)
    except (TypeError, ValueError):
        return {"error": "los parámetros de distribute_frames deben ser numéricos."}
    numeric = (start, end, rotate_per_index, angle_offset, angle_jitter, parameter_jitter)
    if not all(math.isfinite(item) for item in numeric):
        return {"error": "distribute_frames contiene un número no finito."}
    if not isinstance(value, FrameSet) or not value.frames:
        return {"error": "distribute_frames necesita un stream F válido y no vacío."}
    if count < 1 or count > 512:
        return {"error": "count debe estar entre 1 y 512 por padre."}
    if start < 0.0 or end > 1.0 or start > end:
        return {"error": "start/end deben cumplir 0 ≤ start ≤ end ≤ 1."}
    if angle_jitter < 0.0:
        return {"error": "angle_jitter no puede ser negativo."}
    if parameter_jitter < 0.0 or parameter_jitter > 1.0:
        return {"error": "parameter_jitter debe estar entre 0 y 1."}

    by_parent: dict[int, list[CurveFrame]] = {}
    for frame in value.frames:
        by_parent.setdefault(frame.parent_index, []).append(frame)
    if len(by_parent) * count > 4096:
        return {"error": "distribute_frames no puede producir más de 4096 frames por nodo."}

    output = []
    for parent_index in sorted(by_parent):
        source = tuple(sorted(
            by_parent[parent_index], key=lambda item: (item.local_index, item.parameter)
        ))
        for local_index in range(count):
            base_fraction = local_index / (count - 1) if count > 1 else 0.0
            rng_seed = (
                seed * 1_000_003 + parent_index * 97_409 + local_index * 65_537
            ) & 0x7fffffff
            rng = random.Random(rng_seed)
            fraction = start + (end - start) * base_fraction
            if parameter_jitter:
                fraction += rng.uniform(-parameter_jitter, parameter_jitter) * (end - start)
            fraction = min(end, max(start, fraction))
            sampled = _interpolate_frame(source, fraction)

            angle = angle_offset + rotate_per_index * local_index
            if angle_jitter:
                angle += rng.uniform(-angle_jitter, angle_jitter)
            radians = math.radians(angle)
            side = _normalized(_cross(sampled.tangent, sampled.outward))
            outward = _normalized(tuple(
                sampled.outward[axis] * math.cos(radians)
                + side[axis] * math.sin(radians)
                for axis in range(3)
            ))
            output.append(CurveFrame(
                sampled.position, sampled.tangent, outward, sampled.parameter,
                parent_index=parent_index, local_index=local_index,
                scale=sampled.scale, radius=sampled.radius, seed=rng_seed,
                pivot_index=len(output), parent_length=sampled.parent_length,
            ))

    result = FrameSet(tuple(output), value.parent_count)
    return {
        "frame_set": result,
        "info": (f"{len(result)} frames/{len(by_parent)} padres · "
                 f"{start:.2f}→{end:.2f} · giro {rotate_per_index:.1f}°"),
    }


def _rotate_vector(vector, axis, degrees: float):
    """Rotación Rodrigues, usada para componer la base local sin depender de tipos de Unreal."""
    axis = _normalized(axis)
    radians = math.radians(degrees)
    cosine, sine = math.cos(radians), math.sin(radians)
    dot = sum(vector[index] * axis[index] for index in range(3))
    crossed = _cross(axis, vector)
    return tuple(
        vector[index] * cosine
        + crossed[index] * sine
        + axis[index] * dot * (1.0 - cosine)
        for index in range(3)
    )


def transform_frames(value, *, offset_x: float = 0.0, offset_y: float = 0.0,
                     offset_z: float = 0.0, pitch: float = 0.0, yaw: float = 0.0,
                     roll: float = 0.0, scale: float = 1.0,
                     offset_jitter_x: float = 0.0, offset_jitter_y: float = 0.0,
                     offset_jitter_z: float = 0.0, pitch_jitter: float = 0.0,
                     yaw_jitter: float = 0.0, roll_jitter: float = 0.0,
                     scale_jitter: float = 0.0, inherit_scale: bool = True,
                     seed: int = 7) -> dict:
    """Aplica transform base y variación determinista en los ejes locales de cada frame ``F``.

    La base local es X=tangente, Z=exterior y Y=Z×X. Yaw rota alrededor de Z, pitch alrededor de Y y
    roll alrededor de X. ``inherit_scale`` controla tanto la escala resultante como los offsets.
    """
    import random

    try:
        seed = int(seed)
        offset_x, offset_y, offset_z = float(offset_x), float(offset_y), float(offset_z)
        pitch, yaw, roll, scale = float(pitch), float(yaw), float(roll), float(scale)
        offset_jitter_x, offset_jitter_y, offset_jitter_z = (
            float(offset_jitter_x), float(offset_jitter_y), float(offset_jitter_z))
        pitch_jitter, yaw_jitter, roll_jitter = (
            float(pitch_jitter), float(yaw_jitter), float(roll_jitter))
        scale_jitter = float(scale_jitter)
    except (TypeError, ValueError):
        return {"error": "los parámetros de transform_frames deben ser numéricos."}
    numeric = (
        offset_x, offset_y, offset_z, pitch, yaw, roll, scale,
        offset_jitter_x, offset_jitter_y, offset_jitter_z,
        pitch_jitter, yaw_jitter, roll_jitter, scale_jitter,
    )
    if not all(math.isfinite(item) for item in numeric):
        return {"error": "transform_frames contiene un número no finito."}
    if not isinstance(value, FrameSet) or not value.frames:
        return {"error": "transform_frames necesita un stream F válido y no vacío."}
    jitters = (
        offset_jitter_x, offset_jitter_y, offset_jitter_z,
        pitch_jitter, yaw_jitter, roll_jitter, scale_jitter,
    )
    if any(item < 0.0 for item in jitters):
        return {"error": "los valores jitter de transform_frames no pueden ser negativos."}
    if scale <= 0.0:
        return {"error": "scale debe ser mayor que cero."}
    if scale_jitter >= scale:
        return {"error": "scale_jitter debe ser menor que scale para evitar frames degenerados."}

    output = []
    for frame in value.frames:
        rng_seed = (
            seed * 1_000_003 + frame.seed * 9_176
            + frame.parent_index * 97_409 + frame.local_index * 65_537
        ) & 0x7fffffff
        rng = random.Random(rng_seed)

        def varied(base, jitter):
            return base + rng.uniform(-jitter, jitter) if jitter else base

        move_x = varied(offset_x, offset_jitter_x)
        move_y = varied(offset_y, offset_jitter_y)
        move_z = varied(offset_z, offset_jitter_z)
        local_pitch = varied(pitch, pitch_jitter)
        local_yaw = varied(yaw, yaw_jitter)
        local_roll = varied(roll, roll_jitter)
        local_scale = varied(scale, scale_jitter)

        axis_x = _normalized(frame.tangent)
        axis_z = _normalized(frame.outward)
        axis_y = _normalized(_cross(axis_z, axis_x))
        parent_scale = frame.scale if inherit_scale else 1.0
        position = tuple(
            frame.position[index]
            + parent_scale * (
                axis_x[index] * move_x
                + axis_y[index] * move_y
                + axis_z[index] * move_z
            )
            for index in range(3)
        )

        # Rotaciones extrínsecas sobre la base local actual: Z (yaw), Y (pitch), X (roll).
        axis_x = _rotate_vector(axis_x, axis_z, local_yaw)
        axis_y = _rotate_vector(axis_y, axis_z, local_yaw)
        axis_x = _rotate_vector(axis_x, axis_y, local_pitch)
        axis_z = _rotate_vector(axis_z, axis_y, local_pitch)
        axis_y = _rotate_vector(axis_y, axis_x, local_roll)
        axis_z = _rotate_vector(axis_z, axis_x, local_roll)
        tangent = _normalized(axis_x)
        projection = sum(axis_z[index] * tangent[index] for index in range(3))
        outward = _normalized(tuple(
            axis_z[index] - tangent[index] * projection for index in range(3)
        ))

        output.append(CurveFrame(
            position, tangent, outward, frame.parameter,
            parent_index=frame.parent_index, local_index=frame.local_index,
            scale=parent_scale * local_scale, radius=frame.radius,
            seed=rng_seed, pivot_index=frame.pivot_index,
            parent_length=frame.parent_length,
        ))

    result = FrameSet(tuple(output), value.parent_count)
    inherited = "hereda escala" if inherit_scale else "escala independiente"
    return {
        "frame_set": result,
        "info": f"{len(result)} frames · escala {scale:.3f} · {inherited}",
    }


def frames_desde_puntos(muestras, *, orientacion: str = "normal", escala: float = 1.0,
                        escala_desde_peso: bool = True, giro_al_azar: bool = True,
                        seed: int = 7) -> dict:
    """Convierte un stream de puntos ``P`` (Flow) en un stream de frames ``F`` (Mesh).

    Es el puente entre los dos vocabularios de Jam: hasta acá, las 29 ops de Flow —poisson, máscaras
    de pendiente y altura, los nueve weights— no podían alimentar ningún verbo de malla, y los verbos
    de malla no podían aprovechar ninguna distribución de Flow.

    No hay nada que inventar: un ``Sample`` ya trae todo lo que un frame necesita.

        pos     → position
        normal  → orientación (o vertical, según `orientacion`)
        seed    → seed  (la variación de cada pieza sigue siendo estable)
        weight  → scale (con `escala_desde_peso`)

    Que el **peso** mande la **escala** es lo que vuelve útil todo el tab Weight: una máscara de ruido
    o de altura pasa a decidir el tamaño de cada árbol, no sólo si aparece o no.

    `parent_length` queda en 0 porque estos frames no nacen de una curva: un `branch_from_frames` con
    `relative_to_parent` los rechaza con su mensaje, que es lo correcto.
    """
    import random

    orientacion = str(orientacion or "normal").strip().lower()
    if orientacion not in ("normal", "vertical"):
        return {"error": "orientacion debe ser «normal» o «vertical»."}
    try:
        escala, seed = float(escala), int(seed)
    except (TypeError, ValueError):
        return {"error": "los parámetros de points_to_frames deben ser numéricos."}
    if not math.isfinite(escala) or escala <= 0.0:
        return {"error": "escala debe ser un número finito mayor que cero."}

    puntos = list(muestras or [])
    if not puntos:
        return {"error": "points_to_frames necesita un stream P con al menos un punto."}
    if len(puntos) > 4096:
        return {"error": "points_to_frames no puede producir más de 4096 frames por nodo."}

    salida = []
    for indice, muestra in enumerate(puntos):
        try:
            posicion = (float(muestra.pos.x), float(muestra.pos.y), float(muestra.pos.z))
            normal = (float(muestra.normal.x), float(muestra.normal.y), float(muestra.normal.z))
            peso = float(getattr(muestra, "weight", 1.0))
            semilla = int(getattr(muestra, "seed", 0))
        except (AttributeError, TypeError, ValueError):
            return {"error": "el stream P no contiene muestras válidas (pos/normal/seed)."}

        tangente = _normalized(normal) if orientacion == "normal" else (0.0, 0.0, 1.0)
        if tangente == (0.0, 0.0, 0.0):
            tangente = (0.0, 0.0, 1.0)
        # Una referencia que no sea paralela a la tangente, para sacar la perpendicular.
        referencia = (1.0, 0.0, 0.0) if abs(tangente[0]) < 0.9 else (0.0, 1.0, 0.0)
        hacia_afuera = _normalized(_cross(tangente, referencia))
        if giro_al_azar:
            angulo = random.Random(semilla ^ (seed * 2_654_435_761)).uniform(0.0, 360.0)
            hacia_afuera = _rotate_vector(hacia_afuera, tangente, angulo)

        salida.append(CurveFrame(
            posicion, tangente, hacia_afuera,
            indice / (len(puntos) - 1) if len(puntos) > 1 else 0.0,
            parent_index=0, local_index=indice,
            scale=escala * (peso if escala_desde_peso else 1.0),
            radius=0.0, seed=semilla, pivot_index=indice, parent_length=0.0,
        ))

    conjunto = FrameSet(tuple(salida), 1)
    escalas = [f.scale for f in salida]
    detalle = (f" · escala {min(escalas):.2f}→{max(escalas):.2f} desde el peso"
               if escala_desde_peso else f" · escala {escala:g}")
    return {"frame_set": conjunto,
            "info": f"{len(conjunto)} frames desde P · orientación {orientacion}{detalle}"}


def branch_from_frames(value, *, length_min: float = 200.0,
                       length_max: float = 400.0, angle: float = 55.0,
                       angle_jitter: float = 0.0, curl: float = 20.0,
                       curl_jitter: float = 0.0, segments: int = 8,
                       inherit_scale: bool = True, relative_to_parent: bool = False,
                       profile=None, seed: int = 7) -> dict:
    """Crea una curva hija ``S`` por frame usando su base, jerarquía y escala.

    ``angle`` parte de la tangente hacia ``outward``. ``curl`` suma giro gradualmente a lo largo de
    la curva; integrar la dirección por segmentos produce un arco real en lugar de sólo mover el tip.

    Dos controles gobiernan el LARGO, y son los que hacen que el árbol escale y se afine como una
    unidad en vez de quedar como un poste con muñones:

    - ``relative_to_parent``: interpreta ``length_min/max`` como FRACCIÓN del largo del padre en vez
      de centímetros. Sin esto, alargar el tronco deja las ramas donde estaban.
    - ``profile`` (``N[]``): modula el largo según dónde nace el frame sobre el padre (0=base,
      1=punta). Es el equivalente del ``BranchScaleCurve`` de TreeGen y lo que produce la silueta
      cónica: ramas largas abajo, cortas arriba.
    """
    import random

    from . import fields

    try:
        length_min, length_max = float(length_min), float(length_max)
        angle, angle_jitter = float(angle), float(angle_jitter)
        curl, curl_jitter = float(curl), float(curl_jitter)
        segments, seed = int(segments), int(seed)
    except (TypeError, ValueError):
        return {"error": "los parámetros de branch_from_frames deben ser numéricos."}
    numeric = (length_min, length_max, angle, angle_jitter, curl, curl_jitter)
    if not all(math.isfinite(item) for item in numeric):
        return {"error": "branch_from_frames contiene un número no finito."}
    if not isinstance(value, FrameSet) or not value.frames:
        return {"error": "branch_from_frames necesita un stream F válido y no vacío."}
    if length_min <= 0.0 or length_max < length_min:
        return {"error": "length_min/max deben cumplir 0 < min ≤ max."}
    if angle < 0.0 or angle > 180.0 or angle_jitter < 0.0:
        return {"error": "angle debe estar entre 0 y 180 y angle_jitter no puede ser negativo."}
    if curl_jitter < 0.0:
        return {"error": "curl_jitter no puede ser negativo."}
    if segments < 2 or segments > 128:
        return {"error": "segments debe estar entre 2 y 128."}
    if len(value.frames) > 4096:
        return {"error": "branch_from_frames no puede producir más de 4096 curvas por nodo."}
    if relative_to_parent:
        if length_max > 4.0:
            return {"error": "con relative_to_parent, length_min/max son fracciones del padre "
                             "(0..4), no centímetros."}
        if not any(frame.parent_length > 1e-6 for frame in value.frames):
            return {"error": "relative_to_parent necesita frames con largo de padre; el stream F "
                             "tiene que venir de curve_frames sobre una curva real."}
    if profile is not None and (not isinstance(profile, fields.ScalarSeries)
                                or len(profile.values) < 2):
        return {"error": "el perfil de branch_from_frames debe ser una serie N[] válida."}
    if profile is not None:
        if any(not math.isfinite(v) or v < 0.0 for v in profile.values):
            return {"error": "el perfil N[] sólo puede contener factores finitos no negativos."}
        if not any(v > 0.0 for v in profile.values):
            return {"error": "el perfil N[] no puede ser completamente cero."}

    paths = []
    for frame in value.frames:
        rng_seed = (
            seed * 1_000_003 + frame.seed * 9_176
            + frame.parent_index * 97_409 + frame.local_index * 65_537
        ) & 0x7fffffff
        rng = random.Random(rng_seed)
        inherited_scale = frame.scale if inherit_scale else 1.0
        length = rng.uniform(length_min, length_max)
        if relative_to_parent:
            length *= frame.parent_length
        if profile is not None:
            # `parameter` es dónde nace el frame sobre su padre: 0 en la base, 1 en la punta.
            length *= profile.at(frame.parameter)
        length *= inherited_scale
        if length <= 1e-6:
            return {"error": "el largo de una rama quedó en cero; revisá el perfil N[] o "
                             "length_min/max."}
        branch_angle = min(180.0, max(
            0.0, angle + rng.uniform(-angle_jitter, angle_jitter)
        ))
        branch_curl = curl + rng.uniform(-curl_jitter, curl_jitter)
        step_length = length / segments
        position = frame.position
        points = [position]
        for segment_index in range(segments):
            fraction = (segment_index + 0.5) / segments
            radians = math.radians(branch_angle + branch_curl * fraction)
            direction = _normalized(tuple(
                frame.tangent[axis] * math.cos(radians)
                + frame.outward[axis] * math.sin(radians)
                for axis in range(3)
            ))
            position = tuple(
                position[axis] + direction[axis] * step_length for axis in range(3)
            )
            points.append(position)

        paths.append(CurvePath(
            tuple(points), scale=inherited_scale,
            source_parent_index=frame.parent_index,
            source_local_index=frame.local_index, seed=rng_seed,
            pivot_index=frame.pivot_index, parent_radius=frame.radius,
        ))

    result = CurveSet(tuple(paths))
    inherited = "hereda escala" if inherit_scale else "escala independiente"
    if relative_to_parent:
        rango = (f"{length_min * 100:.0f}→{length_max * 100:.0f}% del padre "
                 f"({min(p.length for p in paths):.0f}→{max(p.length for p in paths):.0f}cm)")
    else:
        rango = f"{length_min:.1f}→{length_max:.1f} cm"
    perfil = f" · perfil {profile.shape}" if profile is not None else ""
    return {
        "curve": result,
        "info": (f"{len(result.paths)} ramas · {segments} segmentos · "
                 f"{rango} · {inherited}{perfil}"),
    }


def child(value, *, at: float = 0.5, length: float = 300.0, angle: float = 55.0,
          azimuth: float = 0.0, bend: float = 40.0, radial_offset: float = 0.0,
          segments: int = 8, samples: int = 32) -> dict:
    """Crea una curva hija en el frame local de una curva padre.

    ``angle`` se mide desde la tangente del padre (0° continúa el padre, 90° sale perpendicular) y
    ``azimuth`` gira alrededor de esa tangente. ``bend`` desplaza el control Bézier en la dirección
    de crecimiento del padre: valores positivos levantan la rama y negativos la hacen caer.
    """
    try:
        at, length, angle, azimuth, bend, radial_offset = (
            float(at), float(length), float(angle), float(azimuth), float(bend),
            float(radial_offset),
        )
        segments, samples = int(segments), int(samples)
    except (TypeError, ValueError):
        return {"error": "los parámetros de curve_child deben ser numéricos."}
    if not all(math.isfinite(v) for v in (at, length, angle, azimuth, bend, radial_offset)):
        return {"error": "curve_child contiene un número no finito."}
    if at < 0.0 or at > 1.0:
        return {"error": "at debe estar entre 0 y 1."}
    if length <= 1e-4:
        return {"error": "length debe ser mayor que cero."}
    if angle < 0.0 or angle > 180.0:
        return {"error": "angle debe estar entre 0 y 180 grados."}
    if segments < 2 or segments > 128:
        return {"error": "segments debe estar entre 2 y 128."}

    sampled = frames(
        value, count=1, start=at, end=at, radial_offset=radial_offset,
        turns=0.0, angle_offset=azimuth, samples=samples,
    )
    if "error" in sampled:
        return {"error": sampled["error"].replace("curve_frames", "curve_child")}

    frame = sampled["frames"][0]
    radians = math.radians(angle)
    direction = _normalized(tuple(
        frame.tangent[axis] * math.cos(radians) + frame.outward[axis] * math.sin(radians)
        for axis in range(3)
    ))
    start = frame.position
    end = tuple(start[axis] + direction[axis] * length for axis in range(3))
    midpoint = tuple((start[axis] + end[axis]) * 0.5 for axis in range(3))
    control = tuple(midpoint[axis] + frame.tangent[axis] * bend for axis in range(3))

    points = []
    for index in range(segments + 1):
        t = index / segments
        one_minus = 1.0 - t
        points.append(tuple(
            one_minus * one_minus * start[axis]
            + 2.0 * one_minus * t * control[axis]
            + t * t * end[axis]
            for axis in range(3)
        ))
    path = CurvePath(tuple(points), scale=float(getattr(value, "scale", 1.0)))
    return {
        "curve": path,
        "info": (f"{len(path.points)} points · {path.length:.1f} cm · "
                 f"padre {at:.2f} · {angle:.1f}°/{azimuth:.1f}°"),
    }


def branches(value, *, count: int = 12, start: float = 0.2, end: float = 0.92,
             length_min: float = 200.0, length_max: float = 400.0,
             parent_scale_start: float = 1.0, parent_scale_end: float = 1.0,
             angle: float = 70.0, angle_jitter: float = 8.0,
             rotate_per_index: float = 137.0, azimuth: float = 0.0,
             azimuth_jitter: float = 5.0, bend: float = 40.0,
             bend_jitter: float = 20.0, radial_offset: float = 0.0,
             segments: int = 8, samples: int = 32, seed: int = 7) -> dict:
    """Genera ``count`` ramas por cada curva padre, como el actor Branch de TreeGen.

    Los anclajes recorren ``start→end`` y el azimut suma ``rotate_per_index`` en cada índice. El
    default de 137° reproduce el patrón filotáxico usado en el mapa de ejemplo de TreeGen sin
    superponer todas las ramas en un solo plano. Longitud, ángulo, azimut y bend usan un PRNG local,
    por lo que el mismo seed siempre produce el mismo árbol.
    """
    import random

    try:
        count, segments, samples, seed = int(count), int(segments), int(samples), int(seed)
        start, end = float(start), float(end)
        length_min, length_max = float(length_min), float(length_max)
        parent_scale_start, parent_scale_end = (
            float(parent_scale_start), float(parent_scale_end))
        angle, angle_jitter = float(angle), float(angle_jitter)
        rotate_per_index, azimuth, azimuth_jitter = (
            float(rotate_per_index), float(azimuth), float(azimuth_jitter))
        bend, bend_jitter, radial_offset = (
            float(bend), float(bend_jitter), float(radial_offset))
    except (TypeError, ValueError):
        return {"error": "los parámetros de curve_branches deben ser numéricos."}

    numeric = (start, end, length_min, length_max, parent_scale_start, parent_scale_end,
               angle, angle_jitter,
               rotate_per_index, azimuth, azimuth_jitter, bend, bend_jitter, radial_offset)
    if not all(math.isfinite(item) for item in numeric):
        return {"error": "curve_branches contiene un número no finito."}
    if count < 1 or count > 128:
        return {"error": "count debe estar entre 1 y 128 por curva padre."}
    if start < 0.0 or end > 1.0 or start > end:
        return {"error": "start/end deben cumplir 0 ≤ start ≤ end ≤ 1."}
    if length_min <= 0.0 or length_max < length_min:
        return {"error": "length_min/max deben cumplir 0 < min ≤ max."}
    if parent_scale_start <= 0.0 or parent_scale_end <= 0.0:
        return {"error": "parent_scale_start/end deben ser mayores que cero."}
    if angle < 0.0 or angle > 180.0 or angle_jitter < 0.0:
        return {"error": "angle debe estar entre 0 y 180 y angle_jitter no puede ser negativo."}
    if azimuth_jitter < 0.0 or bend_jitter < 0.0:
        return {"error": "los jitter no pueden ser negativos."}
    if segments < 2 or segments > 128 or samples < 2 or samples > 256:
        return {"error": "segments debe estar entre 2–128 y samples entre 2–256."}

    parents = paths_of(value, samples=samples)
    if not parents:
        return {"error": "curve_branches necesita una curva S válida."}
    if len(parents) * count > 512:
        return {"error": "curve_branches no puede producir más de 512 ramas por nodo."}

    rng = random.Random(seed)
    generated = []
    for parent_index, parent in enumerate(parents):
        for index in range(count):
            fraction = index / (count - 1) if count > 1 else 0.0
            at = start + (end - start) * fraction
            parent_scale = (parent_scale_start
                            + (parent_scale_end - parent_scale_start) * fraction)
            result = child(
                parent,
                at=at,
                length=rng.uniform(length_min, length_max) * parent_scale,
                angle=min(180.0, max(0.0, angle + rng.uniform(-angle_jitter, angle_jitter))),
                azimuth=(azimuth + rotate_per_index * index
                         + rotate_per_index * count * parent_index
                         + rng.uniform(-azimuth_jitter, azimuth_jitter)),
                bend=bend + rng.uniform(-bend_jitter, bend_jitter),
                radial_offset=radial_offset,
                segments=segments,
                samples=samples,
            )
            if "error" in result:
                return result
            generated.append(CurvePath(
                result["curve"].points,
                scale=float(getattr(parent, "scale", 1.0)) * parent_scale,
            ))

    collection = CurveSet(tuple(generated))
    return {
        "curve": collection,
        "info": (f"{len(collection.paths)} ramas/{len(parents)} padres · "
                 f"{start:.2f}→{end:.2f} · seed {seed}"),
    }
