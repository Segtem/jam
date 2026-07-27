"""Núcleo de mallas procedimentales de Jam sobre Geometry Script.

Por los cables `M` viaja un ``unreal.DynamicMesh`` transitorio. Las primitivas y operadores no crean
paquetes en Content; sólo ``mesh_to_static`` cruza la frontera ``M → A`` y registra el StaticMesh en
la transacción Preview/Bake/Discard del Graph.
"""

from __future__ import annotations

import math
import random
import re

import unreal


CARPETA = "/Game/Jam/Meshes"
VERTEX_COLOR_MATERIAL = (
    "/Engine/EngineDebugMaterials/VertexColorMaterial.VertexColorMaterial"
)
# DynamicMesh transporta IDs de material pero no la lista de MaterialInterface correspondiente.
# Este sidecar vive sólo durante Run y acompaña clones/merges hasta ``to_static``.
_MESH_MATERIALS: dict[int, tuple[object | None, ...]] = {}


def _slug(value: str, fallback: str = "GeneratedMesh") -> str:
    clean = re.sub(r"[^A-Za-z0-9_]+", "_", str(value or "")).strip("_")
    return clean or fallback


def asset_path_for(name: str = "GeneratedMesh", folder: str = CARPETA) -> str:
    """Ruta final determinista del ``StaticMesh`` producido por ``mesh_to_static``."""
    root = str(folder or CARPETA).rstrip("/")
    if not root.startswith("/Game/"):
        root = CARPETA
    asset_name = _slug(name)
    if not asset_name.lower().startswith("sm_"):
        asset_name = "SM_" + asset_name
    return f"{root}/{asset_name}"


def _dynamic_mesh(value):
    dynamic_type = getattr(unreal, "DynamicMesh", None)
    return value if dynamic_type is not None and isinstance(value, dynamic_type) else None


def _static_mesh(value):
    static_type = getattr(unreal, "StaticMesh", None)
    if static_type is not None and isinstance(value, static_type):
        return value
    if isinstance(value, str) and value.strip():
        from . import library
        return library.cargar_malla(value.strip())
    return None


def _info(value) -> str:
    try:
        return str(unreal.GeometryScript_MeshQueries.get_mesh_info_string(value)).splitlines()[0]
    except Exception:  # noqa: BLE001
        return "DynamicMesh"


def _primitive_options():
    return unreal.GeometryScriptPrimitiveOptions()


def _identity():
    return unreal.Transform()


def _new_mesh():
    return unreal.DynamicMesh()


def _clone(source):
    source = _dynamic_mesh(source)
    if source is None:
        raise TypeError("la entrada no es una malla procedural M")
    result = _new_mesh()
    unreal.GeometryScript_MeshEdits.append_mesh(result, source, _identity())
    if id(source) in _MESH_MATERIALS:
        _MESH_MATERIALS[id(result)] = _MESH_MATERIALS[id(source)]
    return result


def _materials(source) -> tuple[object | None, ...]:
    mesh = _dynamic_mesh(source)
    return _MESH_MATERIALS.get(id(mesh), ()) if mesh is not None else ()


def _normalized(vector):
    length = math.sqrt(sum(component * component for component in vector))
    if length < 1e-8:
        return (0.0, 0.0, 0.0)
    return tuple(component / length for component in vector)


def _dot(a, b):
    return sum(left * right for left, right in zip(a, b))


def _cross(a, b):
    return (
        a[1] * b[2] - a[2] * b[1],
        a[2] * b[0] - a[0] * b[2],
        a[0] * b[1] - a[1] * b[0],
    )


def _rotate_about(vector, axis, degrees):
    """Rodrigues puro para rotar la normal de una copia alrededor de la tangente."""
    axis = _normalized(axis)
    radians = math.radians(degrees)
    cosine, sine = math.cos(radians), math.sin(radians)
    crossed = _cross(axis, vector)
    projected = _dot(axis, vector) * (1.0 - cosine)
    return _normalized(tuple(
        vector[index] * cosine + crossed[index] * sine + axis[index] * projected
        for index in range(3)
    ))


def _copy_static_mesh(source):
    asset = _static_mesh(source)
    if asset is None:
        raise TypeError("la entrada no es un StaticMesh A válido")
    result = _new_mesh()
    copied = unreal.GeometryScript_AssetUtils.copy_mesh_from_static_mesh(
        asset, result, unreal.GeometryScriptCopyMeshFromAssetOptions(),
        unreal.GeometryScriptMeshReadLOD())
    if isinstance(copied, tuple):
        result = copied[0] or result
        outcome = copied[1] if len(copied) > 1 else None
        if outcome is not None and "FAIL" in str(outcome).upper():
            raise RuntimeError(f"Geometry Script no pudo leer {asset.get_name()}: {outcome}")
    return result, asset


def _linear_color_from_hex(value: str):
    """Convierte ``#RRGGBB``/``#RRGGBBAA`` sRGB al espacio lineal de Geometry Script."""
    text = str(value or "").strip().lstrip("#")
    if not re.fullmatch(r"[0-9A-Fa-f]{6}(?:[0-9A-Fa-f]{2})?", text):
        raise ValueError("color debe usar formato #RRGGBB o #RRGGBBAA.")

    channels = [int(text[index:index + 2], 16) / 255.0 for index in range(0, len(text), 2)]
    if len(channels) == 3:
        channels.append(1.0)

    def srgb_to_linear(channel: float) -> float:
        return channel / 12.92 if channel <= 0.04045 else ((channel + 0.055) / 1.055) ** 2.4

    red, green, blue, alpha = channels
    return unreal.LinearColor(
        srgb_to_linear(red), srgb_to_linear(green), srgb_to_linear(blue), alpha)


def _has_vertex_colors(source) -> bool:
    """True cuando M contiene un overlay de color válido; falla cerrado en APIs UE antiguas."""
    try:
        result = unreal.GeometryScript_VertexColors.get_mesh_per_vertex_colors(source)
        return isinstance(result, tuple) and len(result) >= 3 and bool(result[2])
    except Exception:  # noqa: BLE001
        return False


def triangle(*, size: float = 100.0) -> dict:
    size = float(size)
    if not math.isfinite(size) or size <= 0.0:
        return {"error": "size debe ser mayor que cero."}
    height = math.sqrt(3.0) * size * 0.5
    points = [
        unreal.Vector2D(-size * 0.5, -height / 3.0),
        unreal.Vector2D(size * 0.5, -height / 3.0),
        unreal.Vector2D(0.0, height * 2.0 / 3.0),
    ]
    result = _new_mesh()
    unreal.GeometryScript_Primitives.append_triangulated_polygon(
        result, _primitive_options(), _identity(), points, allow_self_intersections=False)
    return {"mesh": result, "info": _info(result)}


def quad(*, width: float = 100.0, height: float = 100.0) -> dict:
    return grid(width=width, height=height, columns=2, rows=2)


def grid(*, width: float = 500.0, height: float = 500.0,
         columns: int = 6, rows: int = 6) -> dict:
    width, height = float(width), float(height)
    columns, rows = int(columns), int(rows)
    if not all(math.isfinite(v) and v > 0.0 for v in (width, height)):
        return {"error": "width y height deben ser mayores que cero."}
    if columns < 2 or rows < 2:
        return {"error": "columns y rows deben ser al menos 2 (cantidad de vértices)."}
    result = _new_mesh()
    unreal.GeometryScript_Primitives.append_rectangle_xy(
        result, _primitive_options(), _identity(),
        dimension_x=width, dimension_y=height, steps_width=columns, steps_height=rows)
    return {"mesh": result, "info": _info(result)}


def cylinder(*, radius: float = 50.0, height: float = 200.0,
             sides: int = 16, height_steps: int = 1, capped: bool = True) -> dict:
    radius, height = float(radius), float(height)
    sides, height_steps = int(sides), int(height_steps)
    if not all(math.isfinite(v) and v > 0.0 for v in (radius, height)):
        return {"error": "radius y height deben ser mayores que cero."}
    if sides < 3 or height_steps < 0:
        return {"error": "sides debe ser al menos 3 y height_steps no puede ser negativo."}
    result = _new_mesh()
    unreal.GeometryScript_Primitives.append_cylinder(
        result, _primitive_options(), _identity(), radius=radius, height=height,
        radial_steps=sides, height_steps=height_steps, capped=bool(capped),
        origin=unreal.GeometryScriptPrimitiveOriginMode.BASE)
    return {"mesh": result, "info": _info(result)}


def cone(*, base_radius: float = 60.0, top_radius: float = 0.0, height: float = 200.0,
         sides: int = 16, height_steps: int = 4, capped: bool = True) -> dict:
    base_radius, top_radius, height = float(base_radius), float(top_radius), float(height)
    sides, height_steps = int(sides), int(height_steps)
    if not all(math.isfinite(v) for v in (base_radius, top_radius, height)) \
            or base_radius <= 0.0 or top_radius < 0.0 or height <= 0.0:
        return {"error": "base_radius/height deben ser positivos y top_radius no puede ser negativo."}
    if sides < 3 or height_steps < 1:
        return {"error": "sides debe ser al menos 3 y height_steps al menos 1."}
    result = _new_mesh()
    unreal.GeometryScript_Primitives.append_cone(
        result, _primitive_options(), _identity(), base_radius=base_radius,
        top_radius=top_radius, height=height, radial_steps=sides, height_steps=height_steps,
        capped=bool(capped), origin=unreal.GeometryScriptPrimitiveOriginMode.BASE)
    return {"mesh": result, "info": _info(result)}


def sphere(*, radius: float = 100.0, latitude_steps: int = 8,
           longitude_steps: int = 12) -> dict:
    radius = float(radius)
    latitude_steps, longitude_steps = int(latitude_steps), int(longitude_steps)
    if not math.isfinite(radius) or radius <= 0.0:
        return {"error": "radius debe ser mayor que cero."}
    if latitude_steps < 4 or longitude_steps < 4:
        return {"error": "latitude_steps y longitude_steps deben ser al menos 4."}
    result = _new_mesh()
    unreal.GeometryScript_Primitives.append_sphere_lat_long(
        result, _primitive_options(), _identity(), radius=radius,
        steps_phi=latitude_steps, steps_theta=longitude_steps,
        origin=unreal.GeometryScriptPrimitiveOriginMode.CENTER)
    return {"mesh": result, "info": _info(result)}


def from_asset(source) -> dict:
    """Convierte la geometría del mejor LOD disponible de StaticMesh A a DynamicMesh M."""
    try:
        result, asset = _copy_static_mesh(source)
    except (TypeError, RuntimeError) as exc:
        return {"error": str(exc)}
    return {"mesh": result, "info": f"{_info(result)} · from {asset.get_name()}"}


def pipe(source, *, radius_start: float = 30.0, radius_end: float = 5.0,
         sides: int = 10, samples: int = 16, capped: bool = True,
         profile_rotation: float = 0.0, miter_limit: float = 4.0) -> dict:
    """Barre un perfil circular a lo largo de una curva S con taper lineal."""
    from . import curve

    radius_start, radius_end = float(radius_start), float(radius_end)
    sides, samples = int(sides), int(samples)
    profile_rotation, miter_limit = float(profile_rotation), float(miter_limit)
    values = (radius_start, radius_end, profile_rotation, miter_limit)
    if not all(math.isfinite(value) for value in values) or radius_start <= 0.0 or radius_end < 0.0:
        return {"error": "radius_start debe ser positivo y radius_end no puede ser negativo."}
    if sides < 3 or samples < 2:
        return {"error": "sides debe ser al menos 3 y samples al menos 2."}
    if miter_limit < 1.0:
        return {"error": "miter_limit debe ser al menos 1."}
    paths = curve.paths_of(source, samples=samples)
    if not paths:
        return {"error": "mesh_pipe necesita una curva S válida con al menos dos puntos."}
    if any(path.length < 1e-4 for path in paths):
        return {"error": "mesh_pipe recibió una curva de longitud cero."}

    result = _new_mesh()
    for path in paths:
        path_scale = float(getattr(path, "scale", 1.0))
        profile = [
            unreal.Vector2D(
                math.cos(2.0 * math.pi * index / sides) * radius_start * path_scale,
                math.sin(2.0 * math.pi * index / sides) * radius_start * path_scale,
            )
            for index in range(sides)
        ]
        sweep_path = [unreal.Vector(*point) for point in path.points]
        unreal.GeometryScript_Primitives.append_simple_swept_polygon(
            result, _primitive_options(), _identity(), profile, sweep_path,
            loop=False, capped=bool(capped), start_scale=1.0,
            end_scale=radius_end / radius_start,
            rotation_angle_deg=profile_rotation, miter_limit=miter_limit)
    suffix = f" · {len(paths)} sweeps" if len(paths) > 1 else ""
    return {"mesh": result, "info": _info(result) + suffix}


def pipe_profile(source, profile, *, radius: float = 30.0, sides: int = 10,
                 samples: int = 16, capped: bool = True,
                 profile_rotation: float = 0.0, miter_limit: float = 4.0) -> dict:
    """Barre un círculo sobre S usando una serie ``N[]`` como multiplicador de radio por frame."""
    from . import curve, fields

    try:
        radius, profile_rotation, miter_limit = (
            float(radius), float(profile_rotation), float(miter_limit))
        sides, samples = int(sides), int(samples)
    except (TypeError, ValueError):
        return {"error": "los parámetros de mesh_pipe_profile deben ser numéricos."}
    if not all(math.isfinite(item) for item in (radius, profile_rotation, miter_limit)) \
            or radius <= 0.0:
        return {"error": "radius debe ser un número finito mayor que cero."}
    if sides < 3 or samples < 2:
        return {"error": "sides debe ser al menos 3 y samples al menos 2."}
    if miter_limit < 1.0:
        return {"error": "miter_limit debe ser al menos 1."}
    if not isinstance(profile, fields.ScalarSeries) or len(profile.values) < 2:
        return {"error": "mesh_pipe_profile necesita un perfil N[] válido."}
    if any(not math.isfinite(value) or value < 0.0 for value in profile.values):
        return {"error": "el perfil N[] sólo puede contener radios finitos no negativos."}
    if not any(value > 0.0 for value in profile.values):
        return {"error": "el perfil N[] no puede ser completamente cero."}

    paths = curve.paths_of(source, samples=samples)
    if not paths:
        return {"error": "mesh_pipe_profile necesita una curva S válida con al menos dos puntos."}
    if any(path.length < 1e-4 for path in paths):
        return {"error": "mesh_pipe_profile recibió una curva de longitud cero."}

    unit_profile = [
        unreal.Vector2D(
            math.cos(2.0 * math.pi * index / sides),
            math.sin(2.0 * math.pi * index / sides),
        )
        for index in range(sides)
    ]
    result = _new_mesh()
    for path in paths:
        points = path.points
        lengths = [math.dist(a, b) for a, b in zip(points, points[1:])]
        total_length = sum(lengths)
        walked = 0.0
        previous_outward = None
        sweep_path = []
        path_scale = float(getattr(path, "scale", 1.0))
        for index, point in enumerate(points):
            if index == 0:
                tangent_raw = tuple(points[1][axis] - point[axis] for axis in range(3))
            elif index == len(points) - 1:
                tangent_raw = tuple(point[axis] - points[index - 1][axis] for axis in range(3))
            else:
                tangent_raw = tuple(
                    points[index + 1][axis] - points[index - 1][axis] for axis in range(3))
            tangent = _normalized(tangent_raw)
            if previous_outward is not None:
                projection = _dot(previous_outward, tangent)
                outward = _normalized(tuple(
                    previous_outward[axis] - tangent[axis] * projection for axis in range(3)))
            else:
                outward = (0.0, 0.0, 0.0)
            if outward == (0.0, 0.0, 0.0):
                reference = (0.0, 0.0, 1.0) if abs(tangent[2]) < 0.95 else (1.0, 0.0, 0.0)
                outward = _normalized(_cross(tangent, reference))
            previous_outward = outward
            parameter = walked / total_length if total_length > 1e-8 else 0.0
            local_radius = radius * path_scale * profile.at(parameter)
            sweep_path.append(unreal.Transform(
                location=unreal.Vector(*point),
                rotation=unreal.MathLibrary.make_rot_from_xz(
                    unreal.Vector(*tangent), unreal.Vector(*outward)),
                scale=unreal.Vector(1.0, local_radius, local_radius),
            ))
            if index < len(lengths):
                walked += lengths[index]

        unreal.GeometryScript_Primitives.append_sweep_polygon(
            result, _primitive_options(), _identity(), unit_profile, sweep_path,
            loop=False, capped=bool(capped), start_scale=1.0, end_scale=1.0,
            rotation_angle_deg=profile_rotation, miter_limit=miter_limit)
    suffix = f" · {len(paths)} sweeps" if len(paths) > 1 else ""
    return {
        "mesh": result,
        "info": (f"{_info(result)}{suffix} · perfil {profile.shape} "
                 f"{profile.values[0]:g}→{profile.values[-1]:g} × {radius:g}cm"),
    }


def along_curve(source, asset, *, count: int = 12, start: float = 0.1, end: float = 0.95,
                radial_offset: float = 30.0, turns: float = 2.0,
                angle_offset: float = 0.0, scale_start: float = 0.45,
                scale_end: float = 0.25, scale_x: float = 1.0,
                scale_y: float = 1.0, scale_z: float = 1.0,
                orientation: str = "outward", rotation_jitter: float = 0.0,
                scale_jitter: float = 0.0, offset_jitter: float = 0.0,
                seed: int = 7, crossed: bool = False, double_sided: bool = False,
                samples: int = 32) -> dict:
    """Copia un StaticMesh sobre frames de una curva con variación determinista.

    El eje X local sigue la tangente. La normal Z puede mirar hacia afuera, mantenerse vertical o
    girar al azar; ``crossed`` agrega otra tarjeta a 90° y ``double_sided`` duplica el reverso.
    """
    from . import curve

    try:
        scale_start, scale_end = float(scale_start), float(scale_end)
        scale_x, scale_y, scale_z = float(scale_x), float(scale_y), float(scale_z)
        rotation_jitter = float(rotation_jitter)
        scale_jitter, offset_jitter = float(scale_jitter), float(offset_jitter)
        seed = int(seed)
    except (TypeError, ValueError):
        return {"error": "los parámetros de escala y variación deben ser numéricos."}
    scales = (scale_start, scale_end, scale_x, scale_y, scale_z)
    variations = (rotation_jitter, scale_jitter, offset_jitter)
    if not all(math.isfinite(value) and value > 0.0 for value in scales):
        return {"error": "todas las escalas deben ser mayores que cero."}
    if not all(math.isfinite(value) and value >= 0.0 for value in variations):
        return {"error": "los jitter deben ser números finitos mayores o iguales que cero."}
    if scale_jitter >= 1.0:
        return {"error": "scale_jitter debe estar entre 0 y un valor menor que 1."}
    orientation = str(orientation or "outward").strip().lower()
    if orientation not in {"outward", "world_up", "random"}:
        return {"error": "orientation debe ser outward, world_up o random."}
    paths = curve.paths_of(source, samples=samples)
    if not paths:
        return {"error": "mesh_along_curve necesita una curva S válida."}
    if len(paths) * int(count) > 4096:
        return {"error": "mesh_along_curve no puede muestrear más de 4096 frames por nodo."}
    try:
        template, static_mesh = _copy_static_mesh(asset)
    except (TypeError, RuntimeError) as exc:
        return {"error": str(exc)}

    result = _new_mesh()
    rng = random.Random(seed)
    copies = 0
    frame_count = 0
    for path in paths:
        sampled = curve.frames(
            path, count=count, start=start, end=end, radial_offset=radial_offset,
            turns=turns, angle_offset=angle_offset, samples=samples)
        if "error" in sampled:
            return sampled
        frames = sampled["frames"]
        frame_count += len(frames)
        for index, frame in enumerate(frames):
            fraction = index / (len(frames) - 1) if len(frames) > 1 else 0.0
            uniform_scale = scale_start + (scale_end - scale_start) * fraction
            uniform_scale *= 1.0 + rng.uniform(-scale_jitter, scale_jitter)
            tangent = frame.tangent
            normal = frame.outward
            if orientation == "world_up":
                world_up = (0.0, 0.0, 1.0)
                projected = tuple(
                    world_up[axis] - tangent[axis] * _dot(world_up, tangent)
                    for axis in range(3)
                )
                normal = _normalized(projected)
                if normal == (0.0, 0.0, 0.0):
                    normal = frame.outward
            elif orientation == "random":
                normal = _rotate_about(normal, tangent, rng.uniform(0.0, 360.0))
            if rotation_jitter > 0.0:
                normal = _rotate_about(
                    normal, tangent, rng.uniform(-rotation_jitter, rotation_jitter))

            side = _normalized(_cross(tangent, normal))
            position = frame.position
            if offset_jitter > 0.0:
                normal_shift = rng.uniform(-offset_jitter, offset_jitter)
                side_shift = rng.uniform(-offset_jitter, offset_jitter)
                position = tuple(
                    position[axis] + normal[axis] * normal_shift + side[axis] * side_shift
                    for axis in range(3)
                )

            normals = [normal]
            if bool(crossed):
                normals.append(_rotate_about(normal, tangent, 90.0))
            if bool(double_sided):
                normals += [tuple(-component for component in item) for item in tuple(normals)]

            for copy_normal in normals:
                transform = unreal.Transform(
                    location=unreal.Vector(*position),
                    rotation=unreal.MathLibrary.make_rot_from_xz(
                        unreal.Vector(*tangent), unreal.Vector(*copy_normal)),
                    scale=unreal.Vector(
                        uniform_scale * scale_x,
                        uniform_scale * scale_y,
                        uniform_scale * scale_z,
                    ),
                )
                unreal.GeometryScript_MeshEdits.append_mesh(result, template, transform)
                copies += 1
    return {
        "mesh": result,
        "info": (f"{_info(result)} · {copies} copias/{frame_count} frames × "
                 f"{len(paths)} curvas × {static_mesh.get_name()} · seed {seed}"),
    }


def copy_to_frames(source, asset, *, asset_offset_x: float = 0.0,
                   asset_offset_y: float = 0.0, asset_offset_z: float = 0.0,
                   asset_pitch: float = 0.0, asset_yaw: float = 0.0,
                   asset_roll: float = 0.0, asset_scale: float = 1.0,
                   scale_x: float = 1.0, scale_y: float = 1.0,
                   scale_z: float = 1.0, inherit_scale: bool = True) -> dict:
    """Copia una StaticMesh ``A`` sobre cada frame ``F`` y combina el resultado como ``M``.

    La distribución y variación pertenecen a los nodos F anteriores. Aquí sólo se corrige el pivot y
    orientación local del asset, y luego se alinea X con tangent y Z con outward.
    """
    from . import curve, variants

    try:
        asset_offset_x, asset_offset_y, asset_offset_z = (
            float(asset_offset_x), float(asset_offset_y), float(asset_offset_z))
        asset_pitch, asset_yaw, asset_roll = (
            float(asset_pitch), float(asset_yaw), float(asset_roll))
        asset_scale, scale_x, scale_y, scale_z = (
            float(asset_scale), float(scale_x), float(scale_y), float(scale_z))
    except (TypeError, ValueError):
        return {"error": "los parámetros de copy_mesh_to_frames deben ser numéricos."}
    numeric = (
        asset_offset_x, asset_offset_y, asset_offset_z,
        asset_pitch, asset_yaw, asset_roll, asset_scale, scale_x, scale_y, scale_z,
    )
    if not all(math.isfinite(item) for item in numeric):
        return {"error": "copy_mesh_to_frames contiene un número no finito."}
    selection = source if isinstance(source, variants.FrameAssetSelection) else None
    frame_set = selection.frames if selection is not None else source
    if not isinstance(frame_set, curve.FrameSet) or not frame_set.frames:
        return {"error": "copy_mesh_to_frames necesita un stream F o AF válido y no vacío."}
    if any(item <= 0.0 for item in (asset_scale, scale_x, scale_y, scale_z)):
        return {"error": "asset_scale y scale_x/y/z deben ser mayores que cero."}
    if len(frame_set.frames) > 4096:
        return {"error": "copy_mesh_to_frames no puede copiar más de 4096 frames por nodo."}
    if any(not math.isfinite(frame.scale) or frame.scale <= 0.0 for frame in frame_set.frames):
        return {"error": "copy_mesh_to_frames recibió un frame con escala inválida."}

    asset_paths = selection.assets if selection is not None else tuple(
        asset for _frame in frame_set.frames)
    templates: dict[str, tuple[object, object]] = {}
    try:
        for asset_path in dict.fromkeys(asset_paths):
            templates[asset_path] = _copy_static_mesh(asset_path)
    except (TypeError, RuntimeError) as exc:
        return {"error": str(exc)}

    needs_correction = any(abs(item) > 1e-8 for item in (
        asset_offset_x, asset_offset_y, asset_offset_z,
        asset_pitch, asset_yaw, asset_roll,
    ))
    if needs_correction:
        for template, _static_mesh_asset in templates.values():
            correction = unreal.Transform(
                location=unreal.Vector(asset_offset_x, asset_offset_y, asset_offset_z),
                rotation=unreal.Rotator(
                    pitch=asset_pitch, yaw=asset_yaw, roll=asset_roll),
                scale=unreal.Vector(1.0, 1.0, 1.0),
            )
            unreal.GeometryScript_MeshTransforms.transform_mesh(template, correction)

    result = _new_mesh()
    for frame, asset_path in zip(frame_set.frames, asset_paths):
        template, _static_mesh_asset = templates[asset_path]
        inherited = frame.scale if bool(inherit_scale) else 1.0
        uniform = asset_scale * inherited
        transform = unreal.Transform(
            location=unreal.Vector(*frame.position),
            rotation=unreal.MathLibrary.make_rot_from_xz(
                unreal.Vector(*frame.tangent), unreal.Vector(*frame.outward)),
            scale=unreal.Vector(
                uniform * scale_x, uniform * scale_y, uniform * scale_z),
        )
        unreal.GeometryScript_MeshEdits.append_mesh(result, template, transform)

    inherited_label = "hereda escala F" if inherit_scale else "escala independiente"
    names = sorted({static_mesh.get_name() for _template, static_mesh in templates.values()})
    return {
        "mesh": result,
        "info": (f"{_info(result)} · {len(frame_set.frames)} copias × "
                 f"{len(names)} asset(s) [{', '.join(names)}] · {inherited_label}"),
    }


def leaf(source, *, asset=None, count: int = 4, start: float = 0.1, end: float = 0.95,
         radial_offset: float = 20.0, rotate_per_index: float = 137.0,
         angle_offset: float = 0.0, leaves_per_cluster: int = 3,
         length: float = 90.0, width: float = 45.0,
         asset_scale: float = 1.0, asset_pitch: float = 0.0,
         asset_yaw: float = 0.0, asset_roll: float = 0.0,
         size_start: float = 1.0, size_end: float = 0.7,
         splay: float = 70.0, lift: float = 18.0,
         rotation_jitter: float = 12.0, scale_jitter: float = 0.2,
         offset_jitter: float = 4.0, seed: int = 7,
         inherit_scale: bool = False, double_sided: bool = True,
         samples: int = 32) -> dict:
    """Construye racimos de hojas lanceoladas sobre una curva o lista de curvas ``S``.

    Es el equivalente del actor ``Leaf`` de TreeGen. Con ``asset`` instancia una StaticMesh de
    follaje completa (``TreeLeaves``/``PineFrond``); sin ella genera una silueta portable con pivote
    en la base. En ambos modos agrupa varias copias por frame y conserva la jerarquía de CurveSet.
    """
    from . import curve

    try:
        count, leaves_per_cluster, samples, seed = (
            int(count), int(leaves_per_cluster), int(samples), int(seed))
        start, end, radial_offset = float(start), float(end), float(radial_offset)
        rotate_per_index, angle_offset = float(rotate_per_index), float(angle_offset)
        length, width = float(length), float(width)
        asset_scale = float(asset_scale)
        asset_pitch, asset_yaw, asset_roll = (
            float(asset_pitch), float(asset_yaw), float(asset_roll))
        size_start, size_end = float(size_start), float(size_end)
        splay, lift = float(splay), float(lift)
        rotation_jitter, scale_jitter, offset_jitter = (
            float(rotation_jitter), float(scale_jitter), float(offset_jitter))
    except (TypeError, ValueError):
        return {"error": "los parámetros de mesh_leaf deben ser numéricos."}

    numeric = (start, end, radial_offset, rotate_per_index, angle_offset, length, width,
               asset_scale, asset_pitch, asset_yaw, asset_roll,
               size_start, size_end, splay, lift, rotation_jitter, scale_jitter, offset_jitter)
    if not all(math.isfinite(item) for item in numeric):
        return {"error": "mesh_leaf contiene un número no finito."}
    if count < 1 or count > 128 or leaves_per_cluster < 1 or leaves_per_cluster > 12:
        return {"error": "count debe estar entre 1–128 y leaves_per_cluster entre 1–12."}
    if start < 0.0 or end > 1.0 or start > end:
        return {"error": "start/end deben cumplir 0 ≤ start ≤ end ≤ 1."}
    if length <= 0.0 or width <= 0.0 or asset_scale <= 0.0 \
            or size_start <= 0.0 or size_end <= 0.0:
        return {"error": "length, width, asset_scale y size deben ser mayores que cero."}
    if splay < 0.0 or splay > 360.0 or abs(lift) > 89.0:
        return {"error": "splay debe estar entre 0–360 y lift entre -89–89 grados."}
    if rotation_jitter < 0.0 or offset_jitter < 0.0 or not 0.0 <= scale_jitter < 1.0:
        return {"error": "los jitter deben ser positivos y scale_jitter menor que 1."}

    paths = curve.paths_of(source, samples=samples)
    if not paths:
        return {"error": "mesh_leaf necesita una curva S válida."}
    frame_count = len(paths) * count
    # Una malla de follaje real ya define sus caras/material; reflejarla para simular dos caras
    # duplicaría toda su geometría. ``double_sided`` sólo completa el fallback planar procedural.
    copies_per_leaf = 1 if asset is not None else (2 if bool(double_sided) else 1)
    total_copies = frame_count * leaves_per_cluster * copies_per_leaf
    if total_copies > 8192:
        return {"error": "mesh_leaf no puede producir más de 8192 copias por nodo."}

    static_mesh = None
    if asset is not None:
        try:
            template, static_mesh = _copy_static_mesh(asset)
        except (TypeError, RuntimeError) as exc:
            return {"error": str(exc)}
        # TreeGen expone un Spawn Transform porque cada fronda importada puede tener otro eje local.
        # Corregimos la plantilla una sola vez; después todas las copias siguen usando X como avance.
        asset_transform = unreal.Transform(
            rotation=unreal.Rotator(
                pitch=asset_pitch, yaw=asset_yaw, roll=asset_roll),
            scale=unreal.Vector(asset_scale, asset_scale, asset_scale),
        )
        unreal.GeometryScript_MeshTransforms.transform_mesh(template, asset_transform)
    else:
        # Hoja normalizada en XY: base en X=0, nervadura hacia +X y punta en X=1.
        template = _new_mesh()
        outline = [
            unreal.Vector2D(0.0, 0.0),
            unreal.Vector2D(0.22, -0.34),
            unreal.Vector2D(0.58, -0.50),
            unreal.Vector2D(0.86, -0.26),
            unreal.Vector2D(1.0, 0.0),
            unreal.Vector2D(0.86, 0.26),
            unreal.Vector2D(0.58, 0.50),
            unreal.Vector2D(0.22, 0.34),
        ]
        unreal.GeometryScript_Primitives.append_triangulated_polygon(
            template, _primitive_options(), _identity(), outline,
            allow_self_intersections=False)

    result = _new_mesh()
    rng = random.Random(seed)
    copies = 0
    turns = rotate_per_index * max(0, count - 1) / 360.0
    for path in paths:
        sampled = curve.frames(
            path, count=count, start=start, end=end, radial_offset=radial_offset,
            turns=turns, angle_offset=angle_offset, samples=samples)
        if "error" in sampled:
            return sampled
        frames = sampled["frames"]
        for frame_index, frame in enumerate(frames):
            fraction = frame_index / (len(frames) - 1) if len(frames) > 1 else 0.0
            size = size_start + (size_end - size_start) * fraction
            if bool(inherit_scale):
                size *= float(getattr(path, "scale", 1.0))
            for leaf_index in range(leaves_per_cluster):
                fan = (leaf_index / (leaves_per_cluster - 1) - 0.5
                       if leaves_per_cluster > 1 else 0.0)
                direction = _rotate_about(frame.outward, frame.tangent, fan * splay)
                lift_radians = math.radians(lift + rng.uniform(-rotation_jitter, rotation_jitter))
                direction = _normalized(tuple(
                    direction[axis] * math.cos(lift_radians)
                    + frame.tangent[axis] * math.sin(lift_radians)
                    for axis in range(3)
                ))
                normal = _normalized(_cross(direction, frame.tangent))
                if normal == (0.0, 0.0, 0.0):
                    normal = frame.outward
                normal = _rotate_about(
                    normal, direction, rng.uniform(-rotation_jitter, rotation_jitter))

                side = _normalized(_cross(direction, normal))
                position = frame.position
                if offset_jitter > 0.0:
                    along_shift = rng.uniform(-offset_jitter, offset_jitter)
                    side_shift = rng.uniform(-offset_jitter, offset_jitter)
                    position = tuple(
                        position[axis]
                        + direction[axis] * along_shift
                        + side[axis] * side_shift
                        for axis in range(3)
                    )
                varied_size = size * (1.0 + rng.uniform(-scale_jitter, scale_jitter))
                normals = [normal]
                if static_mesh is None and bool(double_sided):
                    normals.append(tuple(-component for component in normal))
                for copy_normal in normals:
                    transform = unreal.Transform(
                        location=unreal.Vector(*position),
                        rotation=unreal.MathLibrary.make_rot_from_xz(
                            unreal.Vector(*direction), unreal.Vector(*copy_normal)),
                        scale=(unreal.Vector(varied_size, varied_size, varied_size)
                               if static_mesh is not None else
                               unreal.Vector(length * varied_size, width * varied_size, 1.0)),
                    )
                    unreal.GeometryScript_MeshEdits.append_mesh(result, template, transform)
                    copies += 1

    return {
        "mesh": result,
        "info": (f"{_info(result)} · {copies} hojas/{frame_count} racimos × "
                 f"{len(paths)} curvas · "
                 f"{static_mesh.get_name() if static_mesh is not None else 'procedural'} · "
                 f"seed {seed}"),
    }


def transform(source, *, x: float = 0.0, y: float = 0.0, z: float = 0.0,
              pitch: float = 0.0, yaw: float = 0.0, roll: float = 0.0,
              scale_x: float = 1.0, scale_y: float = 1.0, scale_z: float = 1.0) -> dict:
    try:
        result = _clone(source)
    except TypeError as exc:
        return {"error": str(exc)}
    values = [x, y, z, pitch, yaw, roll, scale_x, scale_y, scale_z]
    if not all(math.isfinite(float(v)) for v in values):
        return {"error": "la transformación contiene un número no finito."}
    if any(abs(float(v)) < 1e-6 for v in (scale_x, scale_y, scale_z)):
        return {"error": "la escala no puede contener cero."}
    xf = unreal.Transform(
        location=unreal.Vector(float(x), float(y), float(z)),
        # El constructor posicional de Rotator en Python usa roll/pitch/yaw, distinto del orden de
        # los campos del nodo. Los nombres explícitos mantienen el contrato visual sin ambigüedad.
        rotation=unreal.Rotator(pitch=float(pitch), yaw=float(yaw), roll=float(roll)),
        scale=unreal.Vector(float(scale_x), float(scale_y), float(scale_z)),
    )
    unreal.GeometryScript_MeshTransforms.transform_mesh(result, xf)
    return {"mesh": result, "info": _info(result)}


def vertex_color(source, *, color: str = "#808080") -> dict:
    """Asigna un color sRGB constante a M sin modificar la malla de entrada."""
    try:
        result = _clone(source)
        linear_color = _linear_color_from_hex(color)
    except (TypeError, ValueError) as exc:
        return {"error": str(exc)}

    unreal.GeometryScript_VertexColors.set_mesh_constant_vertex_color(
        result, linear_color, unreal.GeometryScriptColorFlags(), clear_existing=True)
    normalized = "#" + str(color).strip().lstrip("#").upper()
    return {"mesh": result, "info": f"{_info(result)} · vertex color {normalized}"}


def uv_scale(source, *, u: float = 1.0, v: float = 1.0, channel: int = 0,
             origin_u: float = 0.0, origin_v: float = 0.0) -> dict:
    """Escala un canal UV existente sin modificar M; la selección vacía significa toda la malla."""
    try:
        result = _clone(source)
        u, v, origin_u, origin_v = map(float, (u, v, origin_u, origin_v))
        channel = int(channel)
    except (TypeError, ValueError) as exc:
        return {"error": str(exc)}
    if not all(math.isfinite(item) for item in (u, v, origin_u, origin_v)):
        return {"error": "mesh_uv_scale contiene un número no finito."}
    if abs(u) < 1e-8 or abs(v) < 1e-8:
        return {"error": "u y v de mesh_uv_scale no pueden ser cero."}
    if channel < 0 or channel > 7:
        return {"error": "channel de mesh_uv_scale debe estar entre 0 y 7."}
    selection = unreal.GeometryScriptMeshSelection()
    # `scale_mesh_u_vs`, no `scale_mesh_uvs`: el mangler de UE parte `UVs` en `U` + `Vs`.
    unreal.GeometryScript_UVs.scale_mesh_u_vs(
        result, channel, unreal.Vector2D(u, v), unreal.Vector2D(origin_u, origin_v), selection)
    return {"mesh": result, "info": f"{_info(result)} · UV{channel} × ({u:g}, {v:g})"}


def assign_material(source, *, material: str) -> dict:
    """Asigna un único material/section a todos los triángulos de M y conserva el slot hasta A."""
    try:
        result = _clone(source)
    except TypeError as exc:
        return {"error": str(exc)}
    path = str(material or "").strip()
    if not path:
        return {"error": "mesh_material necesita un ObjectPath de material."}
    material_object = unreal.load_asset(path)
    if material_object is None:
        return {"error": f"no pude cargar el material «{path}»."}
    # `clear_material_i_ds`/`remap_material_i_ds`: el mangler de UE parte `IDs` en `I` + `Ds`.
    unreal.GeometryScript_Materials.clear_material_i_ds(result, clear_value=0)
    _MESH_MATERIALS[id(result)] = (material_object,)
    name = material_object.get_name() if hasattr(material_object, "get_name") else path.rsplit("/", 1)[-1]
    return {"mesh": result, "info": f"{_info(result)} · material slot 0: {name}"}


def merge(sources) -> dict:
    meshes = list(sources or [])
    if len(meshes) < 2 or any(_dynamic_mesh(item) is None for item in meshes):
        return {"error": "mesh_merge necesita al menos dos entradas M válidas."}
    result = _clone(meshes[0])
    combined_materials = list(_materials(meshes[0]))
    for item in meshes[1:]:
        addition = _clone(item)
        item_materials = list(_materials(item))
        if item_materials:
            offset = len(combined_materials)
            # Cada input conserva sus IDs locales; se desplazan antes de append para crear sections
            # independientes y mantener la correspondencia con la lista de slots del resultado.
            for material_id in reversed(range(len(item_materials))):
                unreal.GeometryScript_Materials.remap_material_i_ds(
                    addition, material_id, offset + material_id)
            combined_materials.extend(item_materials)
        unreal.GeometryScript_MeshEdits.append_mesh(result, addition, _identity())
    if combined_materials:
        _MESH_MATERIALS[id(result)] = tuple(combined_materials)
    return {"mesh": result, "info": _info(result)}


def _posiciones(dynamic) -> list[tuple[float, float, float]]:
    """Todas las posiciones de vértice de una DynamicMesh, como tuplas puras."""
    # Firma real en 5.7: (target_mesh, skip_gaps) → (mesh, position_list, has_gaps), donde
    # position_list es un GeometryScriptVectorList y los vectores viven en su campo `list`.
    devuelto = unreal.GeometryScript_MeshQueries.get_all_vertex_positions(dynamic, True)
    crudo = devuelto[1] if isinstance(devuelto, tuple) and len(devuelto) > 1 else devuelto
    # GeometryScriptVectorList no es iterable: hay que pedirle el array explícitamente.
    convertir = getattr(crudo, "convert_vector_list_to_array", None)
    if convertir is not None:
        crudo = convertir()
        if isinstance(crudo, tuple):
            crudo = crudo[-1]
    return [(float(v.x), float(v.y), float(v.z)) for v in crudo]


def _secciones(dynamic, asset=None) -> int:
    """Cuántos slots de material tiene la malla. Un árbol sin follaje tiene uno menos."""
    explicitos = _materials(dynamic)
    if explicitos:
        return len(explicitos)
    if asset is not None:
        materiales = asset.get_editor_property("static_materials")
        if materiales:
            return len(materiales)
    try:
        maximo = unreal.GeometryScript_Materials.get_max_material_id(dynamic)
        if isinstance(maximo, tuple):
            maximo = maximo[0]
        return max(1, int(maximo) + 1)
    except Exception:  # noqa: BLE001
        return 1


COLORES_EJE = ("#E03A3A", "#3AC04A", "#3A7AE0")   # X rojo, Y verde, Z azul — la convención de siempre


def _flecha_unitaria(grosor: float):
    """Flecha de 1cm de largo apuntando a +Z: vástago + punta. Se estampa escalada por cada eje."""
    plantilla = _new_mesh()
    unreal.GeometryScript_Primitives.append_cylinder(
        plantilla, _primitive_options(), _identity(),
        radius=grosor * 0.5, height=0.78, radial_steps=6, height_steps=1)
    cabeza = unreal.Transform()
    cabeza.set_editor_property("translation", unreal.Vector(0.0, 0.0, 0.78))
    unreal.GeometryScript_Primitives.append_cone(
        plantilla, _primitive_options(), cabeza,
        base_radius=grosor * 1.6, top_radius=0.0, height=0.22, radial_steps=6, height_steps=1)
    return plantilla


def _estampar(destino, plantilla, transforms) -> None:
    """Una sola llamada para las N copias: `append_mesh_transformed` acepta la lista entera."""
    if not transforms:
        return
    unreal.GeometryScript_MeshEdits.append_mesh_transformed(
        destino, plantilla, transforms, _identity(), constant_transform_is_relative=True)


def _pintado(malla, color_hex: str):
    unreal.GeometryScript_VertexColors.set_mesh_constant_vertex_color(
        malla, _linear_color_from_hex(color_hex), unreal.GeometryScriptColorFlags(),
        clear_existing=True)
    return malla


def _describir(entrada) -> str:
    """Nombre legible del tipo que llegó por el cable, para el veredicto del nodo."""
    from . import curve, fields, variants
    if isinstance(entrada, curve.FrameSet):
        return "F"
    if isinstance(entrada, (curve.CurvePath, curve.CurveSet)):
        return "S"
    if isinstance(entrada, fields.ScalarSeries):
        return "N[]"
    if isinstance(entrada, variants.FrameAssetSelection):
        return "AF"
    if _dynamic_mesh(entrada) is not None:
        return "M"
    if isinstance(entrada, (list, tuple)) and entrada and hasattr(entrada[0], "pos"):
        return "P"
    return "?"


def debug_de_cualquier_cosa(entrada, *, tamano: float = 30.0, grosor: float = 1.2,
                            escalar_con_dato: bool = True, cada: int = 1,
                            solo_direccion: bool = False) -> dict:
    """Un solo nodo para ver CUALQUIER cable: dibuja lo que corresponde al tipo que llegó.

    Tener un verbo por tipo obligaba a saber de antemano cuál conectar. Con un pin comodín se
    arrastra el cable y el nodo se da cuenta solo:

        F     → ejes de colores por frame (posición + orientación + escala)
        P     → un cubo por punto, con el peso de la máscara como tamaño
        S     → el recorrido de cada curva, con arranque y punta marcados
        N[]   → la serie dibujada como gráfico, para editar un taper viendo su forma
        M     → caja envolvente + espinas de normales (delata normales dadas vuelta)
        AF    → los frames, coloreados por la variante que les tocó
    """
    from . import curve, debug, fields, variants

    if grosor <= 0.0:
        return {"error": "grosor debe ser mayor que cero."}
    tipo = _describir(entrada)
    try:
        if tipo == "F":
            piezas = debug.ejes_de_frames(
                entrada.frames, largo=float(tamano),
                escalar_con_frame=bool(escalar_con_dato), solo_tangente=bool(solo_direccion))
        elif tipo == "AF":
            piezas = debug.ejes_de_frames(
                entrada.frames.frames, largo=float(tamano),
                escalar_con_frame=bool(escalar_con_dato), solo_tangente=True)
            variantes = list(dict.fromkeys(entrada.assets))
            piezas = [pieza._replace(eje=variantes.index(ruta) % 3)
                      for pieza, ruta in zip(piezas, entrada.assets)]
        elif tipo == "S":
            piezas = debug.tramos_de_curvas(curve.paths_of(entrada, samples=32))
        elif tipo == "N[]":
            piezas = debug.perfil_de_serie(
                entrada.values, ancho=float(tamano) * 8.0, alto=float(tamano) * 4.0)
        elif tipo == "M":
            malla = _dynamic_mesh(entrada)
            piezas = debug.espinas_de_normales(
                _posiciones(malla), _normales(malla), largo=float(tamano) * 0.3,
                cada=max(1, int(cada)))
            caja = unreal.GeometryScript_MeshQueries.get_mesh_bounding_box(malla)
            if isinstance(caja, tuple):
                caja = caja[1] if len(caja) > 1 else caja[0]
            centro, extension = caja.get_editor_property("min"), caja.get_editor_property("max")
            piezas += debug.aristas_de_caja(
                (centro.x, centro.y, centro.z), (extension.x, extension.y, extension.z))
        elif tipo == "P":
            marcadores = debug.marcadores_de_puntos(
                entrada, tamano=float(tamano) * 0.35,
                escalar_con_peso=bool(escalar_con_dato))
            return _dibujar_marcadores(marcadores)
        else:
            return {"error": "debug no reconoce lo que llegó por el cable "
                             "(espera P, F, S, N[], M o AF)."}
    except ValueError as exc:
        return {"error": str(exc)}

    resultado = _dibujar_ejes(piezas, float(grosor))
    return {"mesh": resultado, "info": f"{_info(resultado)} · {tipo} · {len(piezas)} trazos"}


def _dibujar_marcadores(marcadores) -> dict:
    plantilla = _new_mesh()
    unreal.GeometryScript_Primitives.append_box(
        plantilla, _primitive_options(), _identity(),
        dimension_x=1.0, dimension_y=1.0, dimension_z=1.0)
    resultado = _new_mesh()
    _estampar(resultado, plantilla, [
        unreal.Transform(location=unreal.Vector(*m.origen), rotation=unreal.Rotator(),
                         scale=unreal.Vector(m.tamano, m.tamano, m.tamano))
        for m in marcadores])
    _pintado(resultado, "#E0A020")
    pesos = [m.peso for m in marcadores]
    return {"mesh": resultado,
            "info": (f"{_info(resultado)} · P · {len(marcadores)} puntos · "
                     f"peso {min(pesos):.2f}→{max(pesos):.2f}")}


def _dibujar_ejes(ejes, grosor: float):
    plantilla = _flecha_unitaria(grosor)
    resultado = _new_mesh()
    por_color: dict[int, list] = {}
    for eje in ejes:
        transform = unreal.Transform(
            location=unreal.Vector(*eje.origen),
            rotation=unreal.MathLibrary.make_rot_from_z(unreal.Vector(*eje.direccion)),
            scale=unreal.Vector(1.0, 1.0, eje.largo))
        por_color.setdefault(eje.eje, []).append(transform)
    for indice in sorted(por_color):
        rama = _new_mesh()
        _estampar(rama, plantilla, por_color[indice])
        _pintado(rama, COLORES_EJE[indice % len(COLORES_EJE)])
        unreal.GeometryScript_MeshEdits.append_mesh(resultado, rama, _identity())
    return resultado


def _normales(dynamic) -> list[tuple[float, float, float]]:
    """Normal por vértice, promediando los splits para que el desplazamiento no abra costuras."""
    devuelto = unreal.GeometryScript_Normals.get_mesh_per_vertex_normals(dynamic, True)
    crudo = devuelto[1] if isinstance(devuelto, tuple) and len(devuelto) > 1 else devuelto
    convertir = getattr(crudo, "convert_vector_list_to_array", None)
    if convertir is not None:
        crudo = convertir()
        if isinstance(crudo, tuple):
            crudo = crudo[-1]
    return [(float(v.x), float(v.y), float(v.z)) for v in crudo]


def corteza(source, *, amplitud: float = 2.0, escala: float = 0.06, alargue: float = 0.25,
            octavas: int = 3, surcos: float = 0.6, seed: int = 7) -> dict:
    """Da relieve de corteza a `M` desplazando cada vértice por su normal con ruido estirado."""
    from . import bark

    try:
        result = _clone(source)
    except TypeError as exc:
        return {"error": str(exc)}

    lista = unreal.GeometryScript_MeshQueries.get_all_vertex_positions(result, True)
    lista = lista[1] if isinstance(lista, tuple) and len(lista) > 1 else lista
    posiciones = _posiciones(result)
    normales = _normales(result)
    if len(normales) != len(posiciones):
        return {"error": "la malla no tiene una normal por vértice; recalculá normales antes."}
    try:
        nuevas = bark.desplazar(
            posiciones, normales, amplitud=float(amplitud), escala=float(escala),
            alargue=float(alargue), octavas=int(octavas), surcos=float(surcos), seed=int(seed))
    except ValueError as exc:
        return {"error": str(exc)}

    # `GeometryScriptVectorList` no se puede construir desde Python: se muta la que devolvió el motor
    # (ya viene con el tamaño correcto) y se escribe de vuelta en bloque.
    for indice, (x, y, z) in enumerate(nuevas):
        lista.set_vector_list_item(indice, unreal.Vector(x, y, z))
    unreal.GeometryScript_MeshEdits.set_all_mesh_vertex_positions(result, lista)
    unreal.GeometryScript_Normals.recompute_normals(
        result, unreal.GeometryScriptCalculateNormalsOptions())
    return {"mesh": result,
            "info": f"{_info(result)} · relieve ±{amplitud:g}cm · surcos {surcos:g}"}


def medir(source, *, franjas: int = 8) -> dict:
    """Firma de forma de una malla `M` o de un StaticMesh `A`, para el oráculo de `compare`."""
    from . import compare

    asset = None
    dynamic = _dynamic_mesh(source)
    if dynamic is None:
        try:
            dynamic, asset = _copy_static_mesh(source)
        except (TypeError, RuntimeError) as exc:
            return {"error": f"medir necesita una malla M o un StaticMesh A: {exc}"}
    try:
        posiciones = _posiciones(dynamic)
        triangulos = unreal.GeometryScript_MeshQueries.get_num_triangle_i_ds(dynamic)
        if isinstance(triangulos, tuple):
            triangulos = triangulos[0]
        medida = compare.medir(
            posiciones, triangulos=int(triangulos),
            secciones=_secciones(dynamic, asset), franjas=int(franjas))
    except (ValueError, TypeError) as exc:
        return {"error": str(exc)}
    return {"medida": medida}


def comparar(source, referencia, *, franjas: int = 8, tolerancia_perfil: float = 0.15,
             tolerancia_silueta: float = 0.18, solo_forma: bool = False, **tolerancias) -> dict:
    """Mide `source` y la referencia con la MISMA regla y devuelve el diff métrica a métrica."""
    from . import compare

    izquierda = medir(source, franjas=franjas)
    if "error" in izquierda:
        return {"error": "malla generada: " + izquierda["error"]}
    derecha = medir(referencia, franjas=franjas)
    if "error" in derecha:
        return {"error": "referencia: " + derecha["error"]}

    limites = {k: float(v) for k, v in tolerancias.items() if v is not None}
    resultado = compare.comparar(
        izquierda["medida"], derecha["medida"], tolerancias=limites,
        tolerancia_perfil=float(tolerancia_perfil),
        tolerancia_silueta=float(tolerancia_silueta), solo_forma=bool(solo_forma))
    resultado["generada"] = izquierda["medida"]
    resultado["referencia"] = derecha["medida"]
    return resultado


def normals(source, *, angle_weighted: bool = True, area_weighted: bool = True) -> dict:
    try:
        result = _clone(source)
    except TypeError as exc:
        return {"error": str(exc)}
    options = unreal.GeometryScriptCalculateNormalsOptions()
    options.set_editor_property("angle_weighted", bool(angle_weighted))
    options.set_editor_property("area_weighted", bool(area_weighted))
    unreal.GeometryScript_Normals.recompute_normals(result, options)
    return {"mesh": result, "info": _info(result)}


def to_static(source, *, name: str = "GeneratedMesh", folder: str = CARPETA,
              collision: bool = True, recompute_tangents: bool = True,
              show_vertex_colors: bool = True) -> dict:
    mesh = _dynamic_mesh(source)
    if mesh is None:
        return {"error": "mesh_to_static necesita una entrada M válida."}

    from . import panel
    final_path = asset_path_for(name, folder)
    output_path = panel.preview_asset_path(final_path)
    exists = unreal.EditorAssetLibrary.does_asset_exist(output_path)
    if exists and not output_path.startswith("/Game/JamPreview/"):
        return {"error": f"el asset final «{output_path}» ya existe; usá otro name."}
    if exists and not unreal.EditorAssetLibrary.delete_asset(output_path):
        return {"error": f"no pude limpiar el temporal «{output_path}»."}

    options = unreal.GeometryScriptCreateNewStaticMeshAssetOptions()
    options.set_editor_property("enable_recompute_normals", False)
    options.set_editor_property("enable_recompute_tangents", bool(recompute_tangents))
    options.set_editor_property("enable_collision", bool(collision))
    try:
        created_result = unreal.GeometryScript_NewAssetUtils.create_new_static_mesh_asset_from_mesh(
            mesh, output_path, options)
        created = created_result[0] if isinstance(created_result, tuple) else created_result
        if created is None or not unreal.EditorAssetLibrary.does_asset_exist(output_path):
            raise RuntimeError("Geometry Script no creó el StaticMesh")
        explicit_materials = _materials(mesh)
        if explicit_materials:
            for slot, material in enumerate(explicit_materials):
                if material is not None:
                    created.set_material(slot, material)
        elif bool(show_vertex_colors) and _has_vertex_colors(mesh):
            material = unreal.load_asset(VERTEX_COLOR_MATERIAL)
            if material is None:
                raise RuntimeError("no pude cargar el material lector de Vertex Color de Unreal")
            created.set_material(0, material)
        if not unreal.EditorAssetLibrary.save_asset(output_path, only_if_is_dirty=False):
            raise RuntimeError("Unreal no pudo guardar el StaticMesh")
        panel.register_preview_asset(output_path)
    except Exception as exc:  # noqa: BLE001
        try:
            if output_path.startswith("/Game/JamPreview/"):
                unreal.EditorAssetLibrary.delete_asset(output_path)
        except Exception:  # noqa: BLE001
            pass
        return {"error": f"falló la creación del StaticMesh: {type(exc).__name__}: {exc}"}

    return {"mesh": created, "ruta": output_path, "final": final_path, "info": _info(mesh)}
