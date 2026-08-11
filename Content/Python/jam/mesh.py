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


def _skeletal_mesh(value):
    skeletal_type = getattr(unreal, "SkeletalMesh", None)
    if skeletal_type is not None and isinstance(value, skeletal_type):
        return value
    if isinstance(value, str) and value.strip():
        loaded = unreal.load_asset(value.strip())
        return loaded if skeletal_type is not None and isinstance(loaded, skeletal_type) else None
    return None


def _info(value) -> str:
    """Resumen legible de una malla: lo que hace falta para juzgarla, no el volcado del motor.

    `GetTriangleCount` no existe en Geometry Script 5.8 —está comentado en el propio header del
    motor—; la alternativa limpia es `GetNumTriangleIDs`, que coincide con el conteo real en una
    malla compacta (todo lo que produce Jam lo es: copia, simplify y merge dejan `auto_compact` o
    `append_mesh` sin huecos). Antes esto mostraba la primera línea del volcado de debug de
    `GetMeshInfoString` —pensado para depurar el motor, no para leer en un Inspector— que sólo
    trae vértices. El número de triángulos, que es la unidad en la que se piden los objetivos de
    Simplify, nunca llegaba a mostrarse: se podía correr `mesh_simplify_count` sin ver jamás si el
    objetivo se había cumplido.

    `piezas` viene de `GetNumConnectedComponents`: cuando es más de una, es la señal de que un
    Simplify puede quedarse muy por debajo del objetivo sin que sea un error — cada pieza aislada
    tiene su propio piso mínimo de triángulos, y el colapso de aristas no toca un borde abierto.
    """
    try:
        vertices = unreal.GeometryScript_MeshQueries.get_vertex_count(value)
        triangulos = unreal.GeometryScript_MeshQueries.get_num_triangle_i_ds(value)
        cerrada = unreal.GeometryScript_MeshQueries.get_is_closed_mesh(value)
        piezas = unreal.GeometryScript_MeshQueries.get_num_connected_components(value)
        estado = "cerrada" if cerrada else "abierta"
        detalle_piezas = "" if piezas == 1 else f" · {piezas} piezas"
        return f"{triangulos} triángulos · {vertices} vértices · {estado}{detalle_piezas}"
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


def _material_ids(source) -> list[int]:
    """Material ID de cada triángulo por la lista nativa, sin iterar millones de veces en Python."""
    dynamic = _dynamic_mesh(source)
    if dynamic is None:
        raise TypeError("la entrada no es una malla procedural M")
    returned = unreal.GeometryScript_Materials.get_all_triangle_material_i_ds(dynamic)
    if not isinstance(returned, tuple) or len(returned) < 3 or not bool(returned[-1]):
        return []
    index_list = returned[1]
    converted = unreal.GeometryScript_List.convert_index_list_to_array(index_list)
    if isinstance(converted, tuple):
        converted = converted[-1]
    return [int(value) for value in converted]


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


def _copy_options(*, lod_type: str, lod_index: int, apply_build_settings: bool,
                  request_tangents: bool, use_build_scale: bool, skeletal: bool):
    from . import mesh_copy_core as core

    contract = core.options(
        lod_type=lod_type, lod_index=lod_index,
        apply_build_settings=apply_build_settings, request_tangents=request_tangents,
        use_build_scale=use_build_scale, skeletal=skeletal)
    options = unreal.GeometryScriptCopyMeshFromAssetOptions()
    options.set_editor_property("apply_build_settings", contract.apply_build_settings)
    options.set_editor_property("request_tangents", contract.request_tangents)
    options.set_editor_property("use_build_scale", contract.use_build_scale)
    lod = unreal.GeometryScriptMeshReadLOD()
    lod.set_editor_property(
        "lod_type", getattr(unreal.GeometryScriptLODType, contract.lod_member))
    lod.set_editor_property("lod_index", contract.lod_index)
    return options, lod


def _copy_outcome(copied, fallback, asset):
    result = (copied[0] or fallback) if isinstance(copied, tuple) else (copied or fallback)
    outcome = copied[-1] if isinstance(copied, tuple) and len(copied) > 1 else None
    if outcome is not None and "FAIL" in str(outcome).upper():
        raise RuntimeError(f"Geometry Script no pudo leer {asset.get_name()}: {outcome}")
    return result


def _material_list(returned, asset):
    if not isinstance(returned, tuple) or not returned:
        return ()
    outcome = returned[-1]
    if "FAIL" in str(outcome).upper():
        raise RuntimeError(f"Geometry Script no pudo leer materiales de {asset.get_name()}: {outcome}")
    return tuple(returned[0])


def _copy_static_mesh(source, *, lod_type: str = "max_available", lod_index: int = 0,
                      apply_build_settings: bool = True, request_tangents: bool = True,
                      use_build_scale: bool = True):
    asset = _static_mesh(source)
    if asset is None:
        raise TypeError("la entrada no es un StaticMesh A válido")
    options, lod = _copy_options(
        lod_type=lod_type, lod_index=lod_index, apply_build_settings=apply_build_settings,
        request_tangents=request_tangents, use_build_scale=use_build_scale, skeletal=False)
    result = _new_mesh()
    result = _copy_outcome(
        unreal.GeometryScript_AssetUtils.copy_mesh_from_static_mesh_v2(
            asset, result, options, lod, use_section_materials=True),
        result, asset)
    materials = _material_list(
        unreal.GeometryScript_AssetUtils.get_section_material_list_from_static_mesh(asset, lod),
        asset)
    if materials:
        _MESH_MATERIALS[id(result)] = materials
    return result, asset


def _copy_skeletal_mesh(source, *, lod_type: str = "max_available", lod_index: int = 0,
                        apply_build_settings: bool = True, request_tangents: bool = True,
                        use_build_scale: bool = True):
    asset = _skeletal_mesh(source)
    if asset is None:
        raise TypeError("la entrada no es un SkeletalMesh A válido")
    options, lod = _copy_options(
        lod_type=lod_type, lod_index=lod_index, apply_build_settings=apply_build_settings,
        request_tangents=request_tangents, use_build_scale=use_build_scale, skeletal=True)
    result = _new_mesh()
    result = _copy_outcome(
        unreal.GeometryScript_AssetUtils.copy_mesh_from_skeletal_mesh(
            asset, result, options, lod), result, asset)
    materials = _material_list(
        unreal.GeometryScript_AssetUtils.get_lod_material_list_from_skeletal_mesh(asset, lod),
        asset)
    if materials:
        _MESH_MATERIALS[id(result)] = materials
    return result, asset


def _linear_color_from_hex(value: str):
    """Convierte ``#RRGGBB``/``#RRGGBBAA`` sRGB al espacio lineal de Geometry Script.

    La cuenta vive en `jam.shader` (pura) para que el color de un material y el de un vértice no
    puedan divergir: son el mismo hex y tienen que dar el mismo lineal.
    """
    from . import shader

    return unreal.LinearColor(*shader.color_de_hex(value))


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


def _pasos(*valores, minimo: int = 0) -> bool:
    return all(isinstance(v, int) and v >= minimo for v in valores)


def box(*, size_x: float = 100.0, size_y: float = 100.0, size_z: float = 100.0,
        steps_x: int = 0, steps_y: int = 0, steps_z: int = 0) -> dict:
    """Caja con el pivote en la BASE: apoya sola, que es lo que un kit necesita."""
    size_x, size_y, size_z = float(size_x), float(size_y), float(size_z)
    steps_x, steps_y, steps_z = int(steps_x), int(steps_y), int(steps_z)
    if not all(math.isfinite(v) and v > 0.0 for v in (size_x, size_y, size_z)):
        return {"error": "size_x/y/z deben ser mayores que cero."}
    if not _pasos(steps_x, steps_y, steps_z):
        return {"error": "steps_x/y/z no pueden ser negativos."}
    result = _new_mesh()
    unreal.GeometryScript_Primitives.append_box(
        result, _primitive_options(), _identity(),
        dimension_x=size_x, dimension_y=size_y, dimension_z=size_z,
        steps_x=steps_x, steps_y=steps_y, steps_z=steps_z,
        origin=unreal.GeometryScriptPrimitiveOriginMode.BASE)
    return {"mesh": result, "info": f"{_info(result)} · {size_x:g}×{size_y:g}×{size_z:g}cm"}


def capsule(*, radius: float = 30.0, length: float = 150.0,
            hemisphere_steps: int = 5, sides: int = 12) -> dict:
    """Cápsula (cilindro con casquetes). La forma de colisión y blockout por excelencia."""
    radius, length = float(radius), float(length)
    hemisphere_steps, sides = int(hemisphere_steps), int(sides)
    if not all(math.isfinite(v) for v in (radius, length)) or radius <= 0.0 or length < 0.0:
        return {"error": "radius debe ser mayor que cero y length no puede ser negativo."}
    if hemisphere_steps < 1 or sides < 3:
        return {"error": "hemisphere_steps al menos 1 y sides al menos 3."}
    result = _new_mesh()
    unreal.GeometryScript_Primitives.append_capsule(
        result, _primitive_options(), _identity(), radius=radius, line_length=length,
        hemisphere_steps=hemisphere_steps, circle_steps=sides,
        origin=unreal.GeometryScriptPrimitiveOriginMode.BASE)
    return {"mesh": result, "info": f"{_info(result)} · r{radius:g} + {length:g}cm"}


def torus(*, major_radius: float = 100.0, minor_radius: float = 25.0,
          major_steps: int = 24, minor_steps: int = 12) -> dict:
    major_radius, minor_radius = float(major_radius), float(minor_radius)
    major_steps, minor_steps = int(major_steps), int(minor_steps)
    if not all(math.isfinite(v) and v > 0.0 for v in (major_radius, minor_radius)):
        return {"error": "major_radius y minor_radius deben ser mayores que cero."}
    if minor_radius >= major_radius:
        return {"error": "minor_radius tiene que ser menor que major_radius o el toro se cierra."}
    if major_steps < 3 or minor_steps < 3:
        return {"error": "major_steps y minor_steps deben ser al menos 3."}
    result = _new_mesh()
    unreal.GeometryScript_Primitives.append_torus(
        result, _primitive_options(), _identity(), unreal.GeometryScriptRevolveOptions(),
        major_radius=major_radius, minor_radius=minor_radius,
        major_steps=major_steps, minor_steps=minor_steps,
        origin=unreal.GeometryScriptPrimitiveOriginMode.CENTER)
    return {"mesh": result, "info": f"{_info(result)} · R{major_radius:g}/r{minor_radius:g}"}


def disc(*, radius: float = 100.0, sides: int = 24, start_angle: float = 0.0,
         end_angle: float = 360.0, hole_radius: float = 0.0) -> dict:
    """Disco plano. Con `hole_radius` es un anillo y con los ángulos, una porción."""
    radius, hole_radius = float(radius), float(hole_radius)
    start_angle, end_angle = float(start_angle), float(end_angle)
    sides = int(sides)
    if not math.isfinite(radius) or radius <= 0.0:
        return {"error": "radius debe ser mayor que cero."}
    if not math.isfinite(hole_radius) or hole_radius < 0.0 or hole_radius >= radius:
        return {"error": "hole_radius debe estar entre 0 y radius."}
    if not all(math.isfinite(v) for v in (start_angle, end_angle)) or end_angle <= start_angle:
        return {"error": "end_angle tiene que ser mayor que start_angle."}
    if sides < 3:
        return {"error": "sides debe ser al menos 3."}
    result = _new_mesh()
    unreal.GeometryScript_Primitives.append_disc(
        result, _primitive_options(), _identity(), radius=radius, angle_steps=sides,
        start_angle=start_angle, end_angle=end_angle, hole_radius=hole_radius)
    forma = "anillo" if hole_radius > 0.0 else "disco"
    return {"mesh": result, "info": f"{_info(result)} · {forma} r{radius:g}"}


def round_rect(*, size_x: float = 200.0, size_y: float = 200.0, corner_radius: float = 20.0,
               steps_round: int = 6) -> dict:
    size_x, size_y, corner_radius = float(size_x), float(size_y), float(corner_radius)
    steps_round = int(steps_round)
    if not all(math.isfinite(v) and v > 0.0 for v in (size_x, size_y)):
        return {"error": "size_x y size_y deben ser mayores que cero."}
    if not math.isfinite(corner_radius) or corner_radius <= 0.0 \
            or corner_radius > min(size_x, size_y) / 2.0:
        return {"error": "corner_radius debe caber en la mitad del lado más corto."}
    if steps_round < 1:
        return {"error": "steps_round debe ser al menos 1."}
    result = _new_mesh()
    unreal.GeometryScript_Primitives.append_round_rectangle_xy(
        result, _primitive_options(), _identity(),
        dimension_x=size_x, dimension_y=size_y, corner_radius=corner_radius,
        steps_round=steps_round)
    return {"mesh": result, "info": f"{_info(result)} · {size_x:g}×{size_y:g} r{corner_radius:g}"}


def stairs(*, step_width: float = 150.0, step_height: float = 18.0, step_depth: float = 28.0,
           steps: int = 10, floating: bool = False) -> dict:
    """Escalera recta. Geometry Script la regala y es de lo que más se usa en un blockout."""
    step_width, step_height, step_depth = float(step_width), float(step_height), float(step_depth)
    steps = int(steps)
    if not all(math.isfinite(v) and v > 0.0 for v in (step_width, step_height, step_depth)):
        return {"error": "step_width/height/depth deben ser mayores que cero."}
    if steps < 1 or steps > 256:
        return {"error": "steps debe estar entre 1 y 256."}
    result = _new_mesh()
    unreal.GeometryScript_Primitives.append_linear_stairs(
        result, _primitive_options(), _identity(), step_width=step_width,
        step_height=step_height, step_depth=step_depth, num_steps=steps,
        floating=bool(floating))
    return {"mesh": result,
            "info": (f"{_info(result)} · {steps} escalones · sube {steps * step_height:g}cm "
                     f"en {steps * step_depth:g}cm")}


def stairs_curved(*, step_width: float = 150.0, step_height: float = 18.0,
                  inner_radius: float = 200.0, curve_angle: float = 90.0,
                  steps: int = 12, floating: bool = False) -> dict:
    step_width, step_height = float(step_width), float(step_height)
    inner_radius, curve_angle = float(inner_radius), float(curve_angle)
    steps = int(steps)
    if not all(math.isfinite(v) and v > 0.0 for v in (step_width, step_height, inner_radius)):
        return {"error": "step_width/height e inner_radius deben ser mayores que cero."}
    if not math.isfinite(curve_angle) or abs(curve_angle) < 1.0 or abs(curve_angle) > 360.0:
        return {"error": "curve_angle debe estar entre 1 y 360 grados (con signo para el sentido)."}
    if steps < 1 or steps > 256:
        return {"error": "steps debe estar entre 1 y 256."}
    result = _new_mesh()
    unreal.GeometryScript_Primitives.append_curved_stairs(
        result, _primitive_options(), _identity(), step_width=step_width,
        step_height=step_height, inner_radius=inner_radius, curve_angle=curve_angle,
        num_steps=steps, floating=bool(floating))
    return {"mesh": result,
            "info": (f"{_info(result)} · {steps} escalones · {curve_angle:g}° · "
                     f"sube {steps * step_height:g}cm")}


def sphere_box(*, radius: float = 80.0, steps: int = 6) -> dict:
    """Esfera de topología cúbica: cuadrángulos parejos en vez de los polos de la lat/long."""
    radius = float(radius)
    steps = int(steps)
    if not math.isfinite(radius) or radius <= 0.0:
        return {"error": "radius debe ser mayor que cero."}
    if steps < 1 or steps > 64:
        return {"error": "steps debe estar entre 1 y 64."}
    result = _new_mesh()
    unreal.GeometryScript_Primitives.append_sphere_box(
        result, _primitive_options(), _identity(), radius=radius,
        steps_x=steps, steps_y=steps, steps_z=steps,
        origin=unreal.GeometryScriptPrimitiveOriginMode.CENTER)
    return {"mesh": result, "info": f"{_info(result)} · r{radius:g} · topología de caja"}


def revolve(source, *, steps: int = 24, capped: bool = True, degrees: float = 360.0,
            samples: int = 32) -> dict:
    """Torno: revoluciona el perfil de una curva ``S`` alrededor del eje Z.

    El perfil se lee en el plano XZ —x = distancia al eje, z = altura—, que es como se dibuja un
    perfil de torno de toda la vida. Sirve para columnas, balaustres, vasijas y molduras: la pieza
    arquitectónica que hoy había que aproximar con un pipe.
    """
    from . import curve as curva_mod

    steps, samples = int(steps), int(samples)
    degrees = float(degrees)
    if steps < 3:
        return {"error": "steps debe ser al menos 3."}
    if not math.isfinite(degrees) or abs(degrees) < 1.0 or abs(degrees) > 360.0:
        return {"error": "degrees debe estar entre 1 y 360."}

    paths = curva_mod.paths_of(source, samples=samples)
    if not paths:
        return {"error": "mesh_revolve necesita una curva S válida."}
    if len(paths) > 1:
        return {"error": "mesh_revolve toma UNA curva; usá un solo perfil."}

    perfil = [(abs(float(p[0])), float(p[2])) for p in paths[0].points]
    if all(x <= 1e-6 for x, _z in perfil):
        return {"error": "el perfil está sobre el eje: separalo en X para que haya algo que girar."}

    opciones = unreal.GeometryScriptRevolveOptions()
    opciones.set_editor_property("revolve_degrees", degrees)
    result = _new_mesh()
    unreal.GeometryScript_Primitives.append_revolve_path(
        result, _primitive_options(), _identity(),
        [unreal.Vector2D(x, z) for x, z in perfil], opciones,
        steps=steps, capped=bool(capped))
    return {"mesh": result,
            "info": f"{_info(result)} · perfil de {len(perfil)} puntos · {degrees:g}°"}


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


def copy_static(source, *, lod_type: str = "max_available", lod_index: int = 0,
                apply_build_settings: bool = True, request_tangents: bool = True,
                use_build_scale: bool = True) -> dict:
    """Copia un LOD de StaticMesh A a M y conserva materiales ordenados por section."""
    try:
        result, asset = _copy_static_mesh(
            source, lod_type=lod_type, lod_index=lod_index,
            apply_build_settings=apply_build_settings, request_tangents=request_tangents,
            use_build_scale=use_build_scale)
    except (TypeError, ValueError, RuntimeError) as exc:
        return {"error": str(exc)}
    return {"mesh": result, "info": (f"{_info(result)} · Static {asset.get_name()} · "
                                      f"{len(_materials(result))} materiales")}


def copy_skeletal(source, *, lod_type: str = "max_available", lod_index: int = 0,
                  apply_build_settings: bool = True, request_tangents: bool = True,
                  use_build_scale: bool = True) -> dict:
    """Copia un LOD de SkeletalMesh A a M y conserva su lista de materiales."""
    try:
        result, asset = _copy_skeletal_mesh(
            source, lod_type=lod_type, lod_index=lod_index,
            apply_build_settings=apply_build_settings, request_tangents=request_tangents,
            use_build_scale=use_build_scale)
    except (TypeError, ValueError, RuntimeError) as exc:
        return {"error": str(exc)}
    return {"mesh": result, "info": (f"{_info(result)} · Skeletal {asset.get_name()} · "
                                      f"{len(_materials(result))} materiales")}


def from_asset(source) -> dict:
    """Alias histórico de ``copy_static`` para no romper presets guardados."""
    return copy_static(source)


# ---- procedencia: qué rama produjo cada triángulo ----------------------------------------------
# El cable `M` transporta un `UDynamicMesh` pelado, así que no hay dónde colgar metadata al lado de
# la malla. La procedencia tiene que viajar ENCIMA, en un canal por vértice — que además es como la
# transporta Pivot Painter de verdad.
#
# Medido en el editor (`tools/experiments/sonda_procedencia.py`), no supuesto:
#   · cada `append_simple_swept_polygon` ocupa un rango CONTIGUO de vértices, exactamente
#     `lados × puntos` (las tapas reutilizan los anillos, no agregan vértices);
#   · escribir UVs triángulo por triángulo cuesta 1.6 µs — 32 ms para un árbol de 20k triángulos,
#     o sea que la ruta UV es viable y no hace falta apretar todo en el color de vértice;
#   · el canal sobrevive `transform`, `merge` contra una malla sin el canal, y el horneado a
#     StaticMesh con los valores intactos;
#   · `set_num_uv_sets` hay que llamarlo DESPUÉS de generar la geometría: cada `append_*` reinicia
#     el juego de atributos y se lleva puestos los canales extra. Por eso los tramos se ANOTAN
#     durante el barrido y se estampan todos juntos al final (medido: pedir los canales antes da
#     0 escrituras válidas de 92; pedirlos después, 92 de 92).
#
# Reparto: UV1 = (pivote.x, pivote.y) · UV2 = (pivote.z, largo de la rama). Cuatro floats alcanzan
# para el pivote COMPLETO sin necesidad de la textura que usa Pivot Painter 2, y dejan el color de
# vértice libre para la máscara de viento de `mesh_vertex_gradient`.

CANAL_PIVOTE_XY = 1
CANAL_PIVOTE_ZL = 2
CANALES_UV = 3


def _triangulos(dynamic) -> int:
    # `GetTriangleCount` está COMENTADO en el header de 5.7; el que existe es este.
    return unreal.GeometryScript_MeshQueries.get_num_triangle_i_ds(dynamic)


def _estampar_pivotes(dynamic, tramos) -> int:
    """Escribe el pivote de cada rama en SUS triángulos. Devuelve cuántos estampó.

    `tramos` es la lista de `(tri_desde, tri_hasta, pivote, largo)` anotada durante el barrido: una
    vez que dos barridos comparten malla ya no hay forma de saber qué triángulo vino de cuál, así
    que el rango hay que capturarlo en el momento.

    Los tres vértices de cada triángulo llevan el MISMO valor. `SetMeshTriangleUVs` convierte cada
    triángulo en una isla UV aislada —lo dice su header— y para un canal de datos eso viene bien:
    la interpolación del shader entre tres esquinas iguales da una constante, que es exactamente el
    pivote de la rama.
    """
    if not tramos:
        return 0
    unreal.GeometryScript_UVs.set_num_uv_sets(dynamic, CANALES_UV)
    estampados = 0
    for desde, hasta, pivote, largo in tramos:
        xy = unreal.GeometryScriptUVTriangle()
        zl = unreal.GeometryScriptUVTriangle()
        punto_xy = unreal.Vector2D(float(pivote[0]), float(pivote[1]))
        punto_zl = unreal.Vector2D(float(pivote[2]), float(largo))
        for atributo in ("uv0", "uv1", "uv2"):
            setattr(xy, atributo, punto_xy)
            setattr(zl, atributo, punto_zl)
        for tid in range(desde, hasta):
            unreal.GeometryScript_UVs.set_mesh_triangle_u_vs(
                dynamic, CANAL_PIVOTE_XY, tid, xy, defer_change_notifications=True)
            unreal.GeometryScript_UVs.set_mesh_triangle_u_vs(
                dynamic, CANAL_PIVOTE_ZL, tid, zl, defer_change_notifications=True)
            estampados += 1
    return estampados


def _pivote_de(path) -> tuple[tuple[float, float, float], float]:
    """El pivote de una rama es dónde NACE, y su largo es cuánto se aleja de ahí.

    Son las dos cosas que necesita el shader de viento: alrededor de qué punto girar y cuánto
    amplificar el giro hacia la punta.
    """
    return path.points[0], float(path.length)


def ribbon(source, *, width: float = 360.0, plane: str = "xy", join: str = "miter",
           miter_limit: float = 4.0, uv_scale: float = 200.0,
           material_id: int = 0, samples: int = 32) -> dict:
    """Convierte cada recorrido abierto S en una superficie M con UV0 longitudinal.

    Los buffers nacen en el núcleo puro; este adaptador sólo traduce tipos y los anexa a un
    ``DynamicMesh``. Cada recorrido conserva su isla y recibe el mismo Material ID explícito.
    """
    from . import curve, ribbon_core

    try:
        material_id, samples = int(material_id), int(samples)
    except (TypeError, ValueError, OverflowError):
        return {"error": "material_id y samples de mesh_ribbon deben ser enteros."}
    if material_id < 0 or material_id > 1023:
        return {"error": "material_id de mesh_ribbon debe estar entre 0 y 1023."}
    if samples < 2 or samples > 4096:
        return {"error": "samples de mesh_ribbon debe estar entre 2 y 4096."}
    paths = curve.paths_of(source, samples=samples)
    if not paths:
        return {"error": "mesh_ribbon necesita una curva S válida con al menos dos puntos."}

    result = _new_mesh()
    total_vertices = total_triangles = 0
    max_u = 0.0
    for path in paths:
        built = ribbon_core.ribbon_buffers(
            path.points, width=width, plane=plane, join=join,
            miter_limit=miter_limit, uv_scale=uv_scale)
        if "error" in built:
            return built
        buffers = unreal.GeometryScriptSimpleMeshBuffers()
        buffers.set_editor_property(
            "vertices", [unreal.Vector(*vertex) for vertex in built["vertices"]])
        buffers.set_editor_property(
            "triangles", [unreal.IntVector(*triangle) for triangle in built["triangles"]])
        buffers.set_editor_property(
            "normals", [unreal.Vector(*normal) for normal in built["normals"]])
        buffers.set_editor_property(
            "uv0", [unreal.Vector2D(*uv) for uv in built["uv0"]])
        unreal.GeometryScript_MeshEdits.append_buffers_to_mesh(
            result, buffers, material_id=material_id)
        total_vertices += len(built["vertices"])
        total_triangles += len(built["triangles"])
        max_u = max(max_u, built["length_u"] / float(uv_scale))

    suffix = f" · {len(paths)} cintas" if len(paths) > 1 else ""
    return {
        "mesh": result,
        "info": (_info(result) + suffix
                 + f" · ancho {float(width):g} cm · UV0 hasta {max_u:.2f} U"
                 + f" · Material ID {material_id}"),
        "vertices": total_vertices,
        "triangles": total_triangles,
        "uv_max": max_u,
        "material_id": material_id,
    }


def extrude(source, *, distance: float = 300.0, direction_x: float = 0.0,
            direction_y: float = 0.0, direction_z: float = 1.0,
            uv_scale: float = 100.0) -> dict:
    """Extruye linealmente una superficie M abierta y cose su frontera como un sólido.

    Esta frontera deliberada evita mezclar dos operaciones nativas distintas: sobre componentes
    cerrados Geometry Script interpreta la extrusión completa como shell. Ese caso tendrá un verbo
    propio cuando una receta lo necesite.
    """
    from . import mesh_extrude_core as core

    try:
        config = core.configurar(
            distance=distance, direction_x=direction_x, direction_y=direction_y,
            direction_z=direction_z, uv_scale=uv_scale)
        result = _clone(source)
    except (TypeError, ValueError) as exc:
        return {"error": str(exc)}
    queries = unreal.GeometryScript_MeshQueries
    if bool(queries.get_is_closed_mesh(result)):
        _MESH_MATERIALS.pop(id(result), None)
        return {"error": ("mesh_extrude necesita una superficie abierta; "
                          "una malla cerrada requiere shell.")}
    triangles_before = int(queries.get_num_triangle_i_ds(result))
    if triangles_before < 1:
        _MESH_MATERIALS.pop(id(result), None)
        return {"error": "mesh_extrude necesita una superficie abierta con triángulos."}

    options = unreal.GeometryScriptMeshLinearExtrudeOptions()
    options.set_editor_property("distance", config.distance)
    options.set_editor_property(
        "direction_mode", unreal.GeometryScriptLinearExtrudeDirection.FIXED_DIRECTION)
    options.set_editor_property("direction", unreal.Vector(*config.direction))
    options.set_editor_property(
        "area_mode", unreal.GeometryScriptPolyOperationArea.ENTIRE_SELECTION)
    options.set_editor_property("uv_scale", config.uv_factor)
    options.set_editor_property("solids_to_shells", True)
    unreal.GeometryScript_MeshModeling.apply_mesh_linear_extrude_faces(
        result, options, unreal.GeometryScriptMeshSelection())
    triangles_after = int(queries.get_num_triangle_i_ds(result))
    closed = bool(queries.get_is_closed_mesh(result))
    if triangles_after <= triangles_before or not closed:
        _MESH_MATERIALS.pop(id(result), None)
        return {"error": ("Geometry Script no pudo cerrar la extrusión: "
                          f"{triangles_before}→{triangles_after} triángulos, "
                          f"malla {'cerrada' if closed else 'abierta'}.")}
    unreal.GeometryScript_Normals.recompute_normals(
        result, unreal.GeometryScriptCalculateNormalsOptions())
    direction = ",".join(f"{component:g}" for component in config.direction)
    return {
        "mesh": result,
        "triangles_before": triangles_before,
        "triangles_after": triangles_after,
        "info": (f"{_info(result)} · extrusión {config.distance:g} cm hacia ({direction}) · "
                 f"UV lateral {config.uv_scale:g} cm/UV"),
    }


def pipe(source, *, radius_start: float = 30.0, radius_end: float = 5.0,
         sides: int = 10, samples: int = 16, capped: bool = True,
         profile_rotation: float = 0.0, miter_limit: float = 4.0,
         radius_from_parent: float = 0.0, pivot_uvs: bool = False) -> dict:
    """Barre un perfil circular a lo largo de una curva S con taper lineal.

    Con `radius_from_parent` mayor que cero el radio deja de ser un número fijo y pasa a ser una
    FRACCIÓN del grosor que tenía el padre en el punto donde nació la rama (`CurvePath.parent_radius`,
    que ya viajaba en los datos sin que nadie lo leyera). Es el ``ParentRadius`` de TreeGen y es la
    diferencia entre un árbol y un montón de tubos: sin esto, una rama de tercer nivel sale igual de
    gorda que el tronco, y el ojo lo nota antes que cualquier otra cosa.
    """
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

    radius_from_parent = float(radius_from_parent)
    if not math.isfinite(radius_from_parent) or radius_from_parent < 0.0:
        return {"error": "radius_from_parent no puede ser negativo."}

    result = _new_mesh()
    tramos = []
    heredados = 0
    for path in paths:
        path_scale = float(getattr(path, "scale", 1.0))
        # El taper es una RAZÓN, no dos números sueltos: heredar el grosor del padre tiene que
        # conservar la forma de la rama, no sólo su arranque.
        base, punta = radius_start, radius_end
        parent = float(getattr(path, "parent_radius", 0.0))
        if radius_from_parent > 0.0 and parent > 1e-6:
            razon = radius_end / radius_start
            base = parent * radius_from_parent
            punta = base * razon
            heredados += 1
        profile = [
            unreal.Vector2D(
                math.cos(2.0 * math.pi * index / sides) * base * path_scale,
                math.sin(2.0 * math.pi * index / sides) * base * path_scale,
            )
            for index in range(sides)
        ]
        sweep_path = [unreal.Vector(*point) for point in path.points]
        antes = _triangulos(result) if pivot_uvs else 0
        unreal.GeometryScript_Primitives.append_simple_swept_polygon(
            result, _primitive_options(), _identity(), profile, sweep_path,
            loop=False, capped=bool(capped), start_scale=1.0,
            end_scale=punta / base,
            rotation_angle_deg=profile_rotation, miter_limit=miter_limit)
        if pivot_uvs:
            pivote, largo = _pivote_de(path)
            tramos.append((antes, _triangulos(result), pivote, largo))
    suffix = f" · {len(paths)} sweeps" if len(paths) > 1 else ""
    if pivot_uvs:
        estampados = _estampar_pivotes(result, tramos)
        suffix += (f" · pivote en UV{CANAL_PIVOTE_XY}/UV{CANAL_PIVOTE_ZL} "
                   f"({estampados} triángulos, {len(tramos)} ramas)")
    if heredados:
        suffix += f" · {heredados} con radio del padre ×{radius_from_parent:g}"
    return {"mesh": result, "info": _info(result) + suffix}


def pipe_profile(source, profile, *, radius: float = 30.0, sides: int = 10,
                 samples: int = 16, capped: bool = True,
                 profile_rotation: float = 0.0, miter_limit: float = 4.0,
                 pivot_uvs: bool = False) -> dict:
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
    tramos = []
    for path in paths:
        points = path.points
        antes = _triangulos(result) if pivot_uvs else 0
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
        if pivot_uvs:
            pivote, largo = _pivote_de(path)
            tramos.append((antes, _triangulos(result), pivote, largo))
    suffix = f" · {len(paths)} sweeps" if len(paths) > 1 else ""
    if pivot_uvs:
        estampados = _estampar_pivotes(result, tramos)
        suffix += (f" · pivote en UV{CANAL_PIVOTE_XY}/UV{CANAL_PIVOTE_ZL} "
                   f"({estampados} triángulos, {len(tramos)} ramas)")
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


def vertex_color_gradient(source, *, eje: str = "z", desde: float = 0.0, hasta: float = 1.0,
                          power: float = 1.0, canal: str = "todos") -> dict:
    """Pinta un gradiente 0..1 en el color de vértice — la máscara que el shader de viento necesita.

    `mesh_color` pone un color plano, que sirve para teñir pero no dice NADA por vértice. El viento
    necesita lo contrario: cuánto puede moverse cada punto. Ver `fields.gradiente`.

    `canal` elige dónde escribirlo. Un árbol usa varios a la vez —rojo para el tronco, verde para la
    rama, azul para la hoja— así que escribir en uno solo tiene que dejar los otros como estaban.
    """
    from . import fields

    canal = str(canal).strip().lower()
    if canal not in ("todos", "r", "g", "b", "a"):
        return {"error": "canal debe ser 'todos', 'r', 'g', 'b' o 'a'."}
    try:
        result = _clone(source)
        pesos = fields.gradiente(_posiciones(result), eje=eje, desde=desde, hasta=hasta,
                                 power=power)
    except (TypeError, ValueError) as exc:
        return {"error": str(exc)}
    if not pesos:
        return {"error": "la malla no tiene vértices."}

    # Hay que CREAR el overlay antes de poder leerlo: en una malla recién generada no existe, y
    # `get_mesh_per_vertex_colors` devuelve una lista inválida en vez de fallar.
    unreal.GeometryScript_VertexColors.set_mesh_constant_vertex_color(
        result, unreal.LinearColor(0.0, 0.0, 0.0, 1.0),
        unreal.GeometryScriptColorFlags(), clear_existing=True)
    devuelto = unreal.GeometryScript_VertexColors.get_mesh_per_vertex_colors(result)
    lista = devuelto[1] if isinstance(devuelto, tuple) and len(devuelto) > 1 else devuelto
    if lista is None:
        return {"error": "la malla no admite colores por vértice."}

    for indice, peso in enumerate(pesos):
        previo = lista.get_color_list_item(indice) if hasattr(lista, "get_color_list_item") else None
        r = peso if canal in ("todos", "r") else (previo.r if previo else 0.0)
        g = peso if canal in ("todos", "g") else (previo.g if previo else 0.0)
        b = peso if canal in ("todos", "b") else (previo.b if previo else 0.0)
        a = peso if canal == "a" else (previo.a if previo else 1.0)
        lista.set_color_list_item(indice, unreal.LinearColor(r, g, b, a))
    unreal.GeometryScript_VertexColors.set_mesh_per_vertex_colors(result, lista)

    medio = sum(pesos) / len(pesos)
    return {"mesh": result,
            "info": f"{_info(result)} · gradiente {eje}\u2191 canal {canal} · medio {medio:.2f}"}


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


# ---------------------------------------------------------------------------------------------
# UVs procedurales: proyectar, desplegar, empaquetar — y MEDIR el resultado
# ---------------------------------------------------------------------------------------------
#
# Es la cadena de Houdini (proyección → uvlayout) con lo que Jam le agrega: un veredicto. Unas UVs
# no se juzgan mirando el checker, se juzgan por dos números que `GetMeshUVSizeInfo` sabe dar:
#
#   · la DENSIDAD DE TEXEL — cuánta área UV le toca a cada centímetro de superficie. Si varía entre
#     partes, el checker sale de distinto tamaño y la textura se ve estirada en unas y apretada en
#     otras;
#   · el APROVECHAMIENTO del atlas — cuánto del cuadrado 0..1 ocupan las islas. Lo que sobra es
#     memoria de textura pagada y no usada.
#
# Y una tercera cosa que no es una opinión sino un error: triángulos SIN UVs asignadas.

def _metrica_uv(area_malla: float, area_uv: float, caja_min, caja_max,
                valido: bool, sin_uv: bool) -> dict:
    """La CUENTA, separada de Unreal para poder probarla.

    Es donde vivía el bug que hacía que el oráculo mintiera, así que tiene que ser verificable sin
    un editor: recibe los seis números que devuelve el motor y devuelve el veredicto en crudo.
    """
    ancho = max(0.0, float(caja_max[0]) - float(caja_min[0]))
    alto = max(0.0, float(caja_max[1]) - float(caja_min[1]))
    area_caja = ancho * alto
    return {
        "valido": bool(valido),
        "sin_uv": bool(sin_uv),
        "area_malla": float(area_malla),
        "area_uv": float(area_uv),
        # Densidad LINEAL: cuánto UV le toca a cada metro de superficie. Es la raíz del cociente de
        # áreas porque lo que se compara al mirar un checker son lados, no áreas — dos partes con la
        # mitad de densidad lineal muestran cuadros del doble de tamaño.
        "densidad": (math.sqrt(float(area_uv) / float(area_malla)) * 100.0
                     if area_malla > 1e-9 and area_uv > 0.0 else 0.0),
        # Cuánto de la región que ocupan las islas está REALMENTE cubierto por triángulos.
        #
        # La primera versión medía el área de la caja de las islas y la llamaba «atlas usado». Eso
        # miente justo donde importa: una proyección cúbica apila las seis caras en el mismo
        # cuadrado, así que la caja da 1×1 y parecía «100% aprovechado» cuando en realidad está todo
        # ENCIMADO. Midiendo área de triángulos contra área de la caja, ese caso da >1 —que es la
        # señal de encimado, un defecto real: rompe lightmaps y horneados— y un empaquetado bueno se
        # acerca a 1 por abajo.
        "cobertura": (float(area_uv) / area_caja) if area_caja > 1e-9 else 0.0,
        "caja": (ancho, alto),
        # Las islas tienen que vivir dentro del cuadrado 0..1; afuera, la textura se repite y el
        # desplegado no sirve para atlas ni para hornear.
        "dentro_01": (float(caja_min[0]) >= -1e-4 and float(caja_min[1]) >= -1e-4
                      and float(caja_max[0]) <= 1.0 + 1e-4 and float(caja_max[1]) <= 1.0 + 1e-4),
    }


def _medir_uv(malla, canal: int) -> dict:
    """Los números que hacen juzgable un desplegado. `valido=False` si el canal no existe."""
    # Devuelve la MALLA primero (`UPARAM(DisplayName = "Copy From Mesh")`) y después los seis
    # out-params. Leer la tupla desde el índice 0 da un `DynamicMesh` donde va el área.
    devuelto = unreal.GeometryScript_UVs.get_mesh_uv_size_info(
        malla, canal, unreal.GeometryScriptMeshSelection(), True)
    area_malla, area_uv, _caja3d, caja_uv, valido, sin_uv = devuelto[1:7]
    if caja_uv is None:
        return _metrica_uv(area_malla, area_uv, (0.0, 0.0), (0.0, 0.0), valido, sin_uv)
    return _metrica_uv(area_malla, area_uv,
                       (caja_uv.min.x, caja_uv.min.y), (caja_uv.max.x, caja_uv.max.y),
                       valido, sin_uv)


def _veredicto_uv(medida: dict, canal: int) -> str:
    if not medida["valido"]:
        return f"UV{canal} NO existe en la malla"
    if medida["area_uv"] <= 0.0:
        return f"UV{canal} existe pero está VACÍO (ningún triángulo tiene UVs)"
    partes = [f"densidad {medida['densidad']:.2f} UV/m"]
    if medida["cobertura"] > 1.02:
        partes.append(f"⚠ islas ENCIMADAS ({medida['cobertura']:.1f}× la caja que ocupan)")
    else:
        partes.append(f"{medida['cobertura'] * 100:.0f}% de su caja aprovechado")
    if not medida["dentro_01"]:
        partes.append("⚠ se sale del 0..1")
    if medida["sin_uv"]:
        partes.append("⚠ hay triángulos SIN UV")
    return " · ".join(partes)


def uv_box(source, *, size_x: float = 0.0, size_y: float = 0.0, size_z: float = 0.0,
           yaw: float = 0.0, pitch: float = 0.0, roll: float = 0.0,
           channel: int = 0, min_island_tris: int = 2) -> dict:
    """Proyección CÚBICA: seis planos, y cada triángulo cae en el que mejor mira.

    Es el «UV cubic map» de la caja de herramientas de Houdini y el desplegado por defecto de
    cualquier cosa dura y facetada —una chapa, un contenedor, un casco—, porque no necesita costuras
    dibujadas a mano y no estira.

    Con `size_*` en 0 la caja se ajusta sola a la malla, que es lo que se quiere casi siempre: así la
    proyección no depende de dónde esté el objeto ni de cuánto mida.
    """
    try:
        result = _clone(source)
        canal = int(channel)
        tam = [float(size_x), float(size_y), float(size_z)]
        rot = [float(pitch), float(yaw), float(roll)]
        minimo = max(1, int(min_island_tris))
    except (TypeError, ValueError) as exc:
        return {"error": str(exc)}
    if canal < 0 or canal > 7:
        return {"error": "channel de mesh_uv_box debe estar entre 0 y 7."}

    caja = unreal.GeometryScript_MeshQueries.get_mesh_bounding_box(result)
    # `unreal.Box` no expone `get_center()`/`get_size()`: sólo `min` y `max`.
    centro = unreal.Vector((caja.min.x + caja.max.x) * 0.5,
                           (caja.min.y + caja.max.y) * 0.5,
                           (caja.min.z + caja.max.z) * 0.5)
    extension = (caja.max.x - caja.min.x, caja.max.y - caja.min.y, caja.max.z - caja.min.z)
    for i, valor in enumerate(tam):
        if valor <= 0.0:
            # Ajustarse a la malla es el default porque una caja fija hace que la MISMA malla
            # movida dé otras UVs; el desplegado dejaría de ser una propiedad de la forma.
            tam[i] = max(1.0, extension[i])
    transformada = unreal.Transform(
        location=centro, rotation=unreal.Rotator(rot[0], rot[1], rot[2]),
        scale=unreal.Vector(tam[0], tam[1], tam[2]))
    unreal.GeometryScript_UVs.set_mesh_u_vs_from_box_projection(
        result, canal, transformada, unreal.GeometryScriptMeshSelection(), minimo)
    medida = _medir_uv(result, canal)
    return {"mesh": result, "uv": medida,
            "info": f"caja {tam[0]:.0f}×{tam[1]:.0f}×{tam[2]:.0f} → {_veredicto_uv(medida, canal)}"}


def uv_unwrap(source, *, method: str = "conformal", channel: int = 0,
              align_to_axes: bool = True) -> dict:
    """Despliega la malla resolviendo el aplanado, no proyectando: menos estiramiento, más costuras.

    `conformal` conserva los ángulos (lo que se ve como «no deforma»); `spectral_conformal` hace lo
    mismo con menos islas y más cálculo; `exp_map` es el más rápido y el que peor se porta en formas
    con mucha curvatura. La diferencia entre los tres se MIDE con la densidad que devuelve el verbo.
    """
    metodos = {"conformal": "CONFORMAL", "exp_map": "EXP_MAP",
               "spectral_conformal": "SPECTRAL_CONFORMAL"}
    if str(method) not in metodos:
        return {"error": f"method de mesh_uv_unwrap: «{method}» (hay {sorted(metodos)})"}
    try:
        result = _clone(source)
        canal = int(channel)
    except (TypeError, ValueError) as exc:
        return {"error": str(exc)}
    if canal < 0 or canal > 7:
        return {"error": "channel de mesh_uv_unwrap debe estar entre 0 y 7."}

    opciones = unreal.GeometryScriptRecomputeUVsOptions()
    opciones.set_editor_property(
        "method", getattr(unreal.GeometryScriptUVFlattenMethod, metodos[str(method)]))
    opciones.set_editor_property("auto_align_islands_with_axes", bool(align_to_axes))
    unreal.GeometryScript_UVs.recompute_mesh_u_vs(
        result, canal, opciones, unreal.GeometryScriptMeshSelection())
    medida = _medir_uv(result, canal)
    return {"mesh": result, "uv": medida,
            "info": f"{method} → {_veredicto_uv(medida, canal)}"}


def uv_pack(source, *, resolution: int = 1024, channel: int = 0,
            optimize_rotation: bool = True) -> dict:
    """Empaqueta las islas en el cuadrado 0..1 — el `uvlayout` de Houdini.

    Proyectar o desplegar deja las islas donde caigan, encimadas y desaprovechando el atlas. Esto es
    el paso que las acomoda, y el número que devuelve dice cuánto del atlas quedó usado: es la única
    forma de saber si conviene subir la resolución de la textura o simplemente empaquetar mejor.
    """
    try:
        result = _clone(source)
        canal = int(channel)
        res = int(resolution)
    except (TypeError, ValueError) as exc:
        return {"error": str(exc)}
    if canal < 0 or canal > 7:
        return {"error": "channel de mesh_uv_pack debe estar entre 0 y 7."}
    if res < 16 or res > 8192:
        return {"error": "resolution de mesh_uv_pack debe estar entre 16 y 8192."}

    opciones = unreal.GeometryScriptRepackUVsOptions()
    opciones.set_editor_property("target_image_width", res)
    opciones.set_editor_property("optimize_island_rotation", bool(optimize_rotation))
    unreal.GeometryScript_UVs.repack_mesh_u_vs(result, canal, opciones)
    medida = _medir_uv(result, canal)
    return {"mesh": result, "uv": medida,
            "info": f"atlas {res}px → {_veredicto_uv(medida, canal)}"}


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


def reassign_material_ids(source, *, from_id: int = 1, to_id: int = 0) -> dict:
    """Fusiona una section en otra existente sin modificar M ni inventar un slot sin material."""
    from . import mesh_material_ids_core as core

    try:
        plan = core.remap_plan(from_id, to_id, _material_ids(source))
        result = _clone(source)
    except (TypeError, ValueError) as exc:
        return {"error": str(exc)}
    unreal.GeometryScript_Materials.remap_material_i_ds(
        result, plan.from_id, plan.to_id)
    return {
        "mesh": result,
        "info": (f"ID {plan.from_id}→{plan.to_id} · "
                 f"{len(plan.used_before)}→{len(plan.used_after)} IDs usados · {_info(result)}"),
    }


def clean_material_ids(source, *, remove_duplicate_materials: bool = True) -> dict:
    """Compacta IDs usados a 0..N-1 y mantiene alineada la lista de materiales del cable M."""
    from . import mesh_material_ids_core as core

    try:
        ids = _material_ids(source)
        mapping = core.compact_mapping(ids)
        result = _clone(source)
    except (TypeError, ValueError) as exc:
        return {"error": str(exc)}

    source_slots = list(_materials(source))
    max_id = max(mapping)
    # La función nativa exige una posición por cada ID posible. Una malla procedural puede no traer
    # el sidecar de MaterialInterface; los None sólo completan el contrato y no se publican luego.
    native_slots = source_slots + [None] * max(0, max_id + 1 - len(source_slots))
    remove_duplicates = bool(remove_duplicate_materials and source_slots)
    returned = unreal.GeometryScript_Materials.compact_material_i_ds(
        result, native_slots, remove_duplicates)
    compacted_slots = []
    if isinstance(returned, tuple):
        compacted_slots = next(
            (list(value) for value in returned[1:] if isinstance(value, (list, tuple))), [])

    if source_slots:
        if not compacted_slots:
            # Fallback conservador para versiones que no expongan el out-param: sólo los slots
            # realmente usados, en el mismo orden que el mapeo determinista de IDs.
            compacted_slots = [native_slots[old] for old in mapping]
        _MESH_MATERIALS[id(result)] = tuple(compacted_slots)
    else:
        _MESH_MATERIALS.pop(id(result), None)

    slots_before = len(source_slots)
    slots_after = len(compacted_slots) if source_slots else 0
    slots_text = (f" · slots {slots_before}→{slots_after}" if source_slots
                  else " · sin lista de slots")
    return {
        "mesh": result,
        "info": (f"IDs {list(mapping)}→{list(mapping.values())}{slots_text} · {_info(result)}"),
    }


def validate(source, *, require_closed: bool = False, max_components: int = 0,
             require_uv: bool = False, require_materials: bool = False) -> dict:
    """Mide salud topológica y requisitos de producción sin modificar ni clonar la entrada."""
    from . import mesh_validate_core as core

    dynamic = _dynamic_mesh(source)
    if dynamic is None:
        return {"error": "mesh_validate necesita una entrada M válida."}
    queries = unreal.GeometryScript_MeshQueries
    loops_result = queries.get_num_open_border_loops(dynamic)
    loops = int(loops_result[0] if isinstance(loops_result, tuple) else loops_result)
    ambiguous = bool(loops_result[-1]) if isinstance(loops_result, tuple) else False
    try:
        material_ids = tuple(sorted(set(_material_ids(dynamic))))
    except (TypeError, RuntimeError):
        material_ids = ()
    facts = core.MeshFacts(
        vertices=int(queries.get_vertex_count(dynamic)),
        triangle_ids=int(queries.get_num_triangle_i_ds(dynamic)),
        dense=bool(queries.get_is_dense_mesh(dynamic)),
        closed=bool(queries.get_is_closed_mesh(dynamic)),
        border_loops=loops,
        ambiguous_borders=ambiguous,
        components=int(queries.get_num_connected_components(dynamic)),
        uv_channels=int(queries.get_num_uv_sets(dynamic)),
        material_ids=material_ids,
        material_slots=len(_materials(dynamic)),
    )
    try:
        defects = core.judge(
            facts, require_closed=bool(require_closed), max_components=int(max_components),
            require_uv=bool(require_uv), require_materials=bool(require_materials))
    except ValueError as exc:
        return {"error": str(exc)}
    return {"mesh": dynamic, "ok": not defects, "defects": defects,
            "info": core.summary(facts)}


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
    if isinstance(entrada, bool):
        return "B"
    if isinstance(entrada, (int, float)):
        return "N"
    if isinstance(entrada, str):
        return "T"
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


def _colores_por_vertice(dynamic):
    """Color por vértice si la malla lo tiene; lista vacía si no. Falla cerrado."""
    try:
        devuelto = unreal.GeometryScript_VertexColors.get_mesh_per_vertex_colors(dynamic)
    except Exception:  # noqa: BLE001
        return []
    if not (isinstance(devuelto, tuple) and len(devuelto) >= 3 and bool(devuelto[2])):
        return []
    crudo = devuelto[1]
    convertir = getattr(crudo, "convert_color_list_to_array", None)
    if convertir is not None:
        crudo = convertir()
        if isinstance(crudo, tuple):
            crudo = crudo[-1]
    try:
        return [(float(c.r), float(c.g), float(c.b)) for c in crudo]
    except Exception:  # noqa: BLE001
        return []


def inspeccionar(valor, *, filas: int = 8, filtro: str = "", orden: str = "",
                 descendente: bool = False) -> dict:
    """Tabla de datos de CUALQUIER cosa que viaje por un cable, malla incluida.

    Router entre el núcleo puro —que sabe de frames, puntos, curvas y series— y la extracción de
    vértices de una `DynamicMesh`, que necesita el motor. Una malla es el único tipo cuyos datos no
    se pueden leer sin Unreal, y era justamente el que quedaba en blanco en el inspector.
    """
    from . import debug

    dynamic = _dynamic_mesh(valor)
    if dynamic is None:
        return debug.tabla_datos(valor, filas=filas, filtro=filtro,
                                 orden=orden, descendente=descendente)
    try:
        posiciones = _posiciones(dynamic)
        normales = _normales(dynamic)
        colores = _colores_por_vertice(dynamic)
    except Exception:  # noqa: BLE001
        return {"columnas": [], "filas": [], "total": 0, "orden": "", "descendente": False}
    columnas, todas = debug.columnas_de_vertices(posiciones, normales, colores)
    return debug.armar(columnas, todas, filas=filas, filtro=filtro,
                       orden=orden, descendente=descendente)


def contar(valor) -> int:
    """Cuántos elementos tiene el dato; para una malla, sus vértices."""
    from . import debug

    dynamic = _dynamic_mesh(valor)
    if dynamic is not None:
        try:
            return len(_posiciones(dynamic))
        except Exception:  # noqa: BLE001
            return 0
    return debug.tabla_datos(valor, filas=1)["total"]


def colocar_visualizacion(dynamic, *, nombre: str = "JamDebug") -> dict:
    """Deja una malla de debug en la escena como actor, dentro de la transacción de Preview.

    Usa un ``DynamicMeshActor``: la visualización es transitoria por definición y no tiene por qué
    ensuciar Content con un StaticMesh. Cae dentro del `_preview` que envuelve al Run, así que
    Discard se la lleva con el resto.
    """
    malla = _dynamic_mesh(dynamic)
    if malla is None:
        return {"error": "la visualización no es una malla procedural M."}
    try:
        actor = unreal.get_editor_subsystem(unreal.EditorActorSubsystem).spawn_actor_from_class(
            unreal.DynamicMeshActor, unreal.Vector(0.0, 0.0, 0.0), unreal.Rotator())
        if actor is None:
            return {"error": "Unreal no pudo crear el actor de visualización."}
        actor.set_actor_label(f"{nombre}_viz")
        componente = actor.get_editor_property("dynamic_mesh_component")
        destino = componente.get_dynamic_mesh()
        unreal.GeometryScript_MeshEdits.append_mesh(destino, malla, _identity())
        material = unreal.load_asset(VERTEX_COLOR_MATERIAL)
        if material is not None:
            componente.set_material(0, material)
        # No hace falta marcarlo: `panel._preview` captura por diferencia TODO actor nuevo del
        # Run, así que Discard ya se lo lleva.
        return {"actor": actor}
    except Exception as exc:  # noqa: BLE001
        return {"error": f"falló la visualización: {type(exc).__name__}: {exc}"}


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


def noise(source, *, amplitud: float = 100.0, frecuencia: float = 0.003,
          seed: int = 7, por_normal: bool = True) -> dict:
    """Desplaza M con el Perlin nativo corregido de UE 5.8, sin modificar la entrada.

    Usa exclusivamente ``apply_perlin_noise_to_mesh2``: la variante de compatibilidad anterior a
    5.7 elevaba la frecuencia al cuadrado y no representa el parámetro que muestra el nodo.
    """
    from . import mesh_noise_core as core

    try:
        config = core.configurar(
            amplitud=amplitud, frecuencia=frecuencia, seed=seed, por_normal=por_normal)
        result = _clone(source)
    except (TypeError, ValueError) as exc:
        return {"error": str(exc)}

    layer = unreal.GeometryScriptPerlinNoiseLayerOptions()
    layer.set_editor_property("magnitude", config.amplitud)
    layer.set_editor_property("frequency", config.frecuencia)
    layer.set_editor_property("random_seed", config.seed)
    options = unreal.GeometryScriptPerlinNoiseOptions()
    options.set_editor_property("base_layer", layer)
    options.set_editor_property("apply_along_normal", config.por_normal)
    result.apply_perlin_noise_to_mesh2(unreal.GeometryScriptMeshSelection(), options)
    unreal.GeometryScript_Normals.recompute_normals(
        result, unreal.GeometryScriptCalculateNormalsOptions())
    direccion = "por normal" if config.por_normal else "en XYZ"
    return {"mesh": result,
            "info": (f"{_info(result)} · Perlin ±{config.amplitud:g}cm · "
                     f"{config.frecuencia:g}/cm · {direccion} · seed {config.seed}")}


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


def weld(source, *, tolerance_cm: float = 0.01, only_unique_pairs: bool = True) -> dict:
    """Suelda bordes abiertos coincidentes de M para cerrar «grietas» entre piezas.

    Nace del caso `casa_madera`: un asset de kit con 17932 piezas —una por triángulo, cero
    vértices compartidos— donde Simplify se quedaba muy por debajo del objetivo porque un colapso
    de aristas no toca un borde abierto. Soldar no garantiza cerrar la malla del todo —piezas
    genuinamente separadas por diseño quedan intactas, a propósito— pero le da al simplificador
    márgen real donde antes no tenía ninguno.

    El default de Geometry Script (``1e-6``, prácticamente cero) no perdona el error de punto
    flotante típico de piezas colocadas a mano; `0,01 cm` (0,1 mm) suelda lo casi-coincidente sin
    arriesgar fusionar geometría que de verdad está separada.
    """
    from . import mesh_simplify_core as core

    try:
        tolerance = core.distance(tolerance_cm, "tolerance_cm")
        result = _clone(source)
    except (TypeError, ValueError) as exc:
        return {"error": str(exc)}
    options = unreal.GeometryScriptWeldEdgesOptions()
    options.set_editor_property("tolerance", tolerance)
    options.set_editor_property("only_unique_pairs", bool(only_unique_pairs))
    unreal.GeometryScript_MeshRepair.weld_mesh_edges(result, options)
    return {"mesh": result, "info": _info(result)}


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


def _simplify_options(method: str, preserve_seams: bool, regularize: float):
    """Cruza el contrato puro a las opciones reales de Geometry Script 5.8.1."""
    from . import mesh_simplify_core as core

    contract = core.options(
        method=method, preserve_seams=preserve_seams, regularize=regularize)
    result = unreal.GeometryScriptSimplifyMeshOptions()
    result.set_editor_property(
        "method", getattr(unreal.GeometryScriptRemoveMeshSimplificationType,
                          contract.method_member))
    # Preservar significa prohibir las tres formas en que el simplificador puede atravesar o
    # reacomodar una costura. El algoritmo V2 conserva además UVs, color, tangentes y normales.
    allow_seam_changes = not contract.preserve_seams
    result.set_editor_property("allow_seam_collapse", allow_seam_changes)
    result.set_editor_property("allow_seam_smoothing", allow_seam_changes)
    result.set_editor_property("allow_seam_splits", allow_seam_changes)
    result.set_editor_property("regularize_weight", contract.regularize)
    result.set_editor_property("auto_compact", True)
    return result


def simplify_count(source, *, target_triangles: int = 5000, method: str = "attributes",
                   preserve_seams: bool = True, regularize: float = 0.000001) -> dict:
    """Reduce M hasta una cantidad objetivo de triángulos, sin modificar la entrada."""
    from . import mesh_simplify_core as core

    try:
        target = core.triangle_target(target_triangles)
        options = _simplify_options(method, preserve_seams, regularize)
        result = _clone(source)
    except (TypeError, ValueError) as exc:
        return {"error": str(exc)}
    unreal.GeometryScript_MeshSimplification.apply_simplify_to_triangle_count(
        result, target, options)
    return {"mesh": result, "info": f"objetivo {target} tris · {_info(result)}"}


def simplify_tolerance(source, *, tolerance_cm: float = 1.0, method: str = "attributes",
                       preserve_seams: bool = True, regularize: float = 0.000001) -> dict:
    """Reduce M sin exceder una desviación geométrica en centímetros."""
    from . import mesh_simplify_core as core

    try:
        tolerance = core.distance(tolerance_cm, "tolerance_cm")
        options = _simplify_options(method, preserve_seams, regularize)
        result = _clone(source)
    except (TypeError, ValueError) as exc:
        return {"error": str(exc)}
    unreal.GeometryScript_MeshSimplification.apply_simplify_to_tolerance(
        result, tolerance, options)
    return {"mesh": result, "info": f"tolerancia {tolerance:g} cm · {_info(result)}"}


def simplify_edge_length(source, *, edge_length_cm: float = 5.0,
                         method: str = "attributes", preserve_seams: bool = True,
                         regularize: float = 0.000001) -> dict:
    """Colapsa aristas según un largo objetivo; no promete una teselación uniforme."""
    from . import mesh_simplify_core as core

    try:
        length = core.distance(edge_length_cm, "edge_length_cm")
        options = _simplify_options(method, preserve_seams, regularize)
        result = _clone(source)
    except (TypeError, ValueError) as exc:
        return {"error": str(exc)}
    unreal.GeometryScript_MeshSimplification.apply_simplify_to_edge_length(
        result, length, options)
    return {"mesh": result,
            "info": f"arista objetivo {length:g} cm (no uniforme) · {_info(result)}"}


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


def uv_triangulos(malla, canal: int = 0) -> list:
    """Los triángulos de un canal UV, para dibujarlos. Lista de tres pares `(u, v)`.

    Se lee POR TRIÁNGULO y no por vértice: `get_mesh_per_vertex_u_vs` devuelve vacío en cuanto hay
    islas —que es siempre, en un desplegado real—, porque un vértice compartido entre dos islas
    tiene más de un UV y no hay «uno por vértice» que devolver.
    """
    salida = []
    total = unreal.GeometryScript_MeshQueries.get_num_triangle_i_ds(malla)
    for tid in range(total):
        devuelto = unreal.GeometryScript_UVs.get_mesh_triangle_uv_element_i_ds(malla, canal, tid)
        elementos, validos = devuelto[1], devuelto[2]
        if not validos:
            continue
        tri = []
        for eid in (elementos.x, elementos.y, elementos.z):
            posicion = unreal.GeometryScript_UVs.get_mesh_uv_element_position(malla, canal, int(eid))
            uv, ok = posicion[1], posicion[2]
            if not ok:
                break
            tri.append((float(uv.x), float(uv.y)))
        if len(tri) == 3:
            salida.append(tri)
    return salida


def mostrar(source, *, location=None, name: str = "JamPreview") -> dict:
    """Muestra una malla `M` en el nivel SIN hornearla a StaticMesh.

    Es la pieza del live view. Medido en UE 5.8.1 recocinando el mismo grafo seis veces seguidas
    (`mide_recoccion_58.py`): **1.7 ms por vuelta contra 215 ms horneando**, 129x.

    Lo caro no resultó ser hornear sino DESHACER lo horneado: escribir el StaticMesh cuesta ~38 ms,
    pero borrar el asset que dejó la vuelta anterior cuesta ~157 ms, y una recocción paga las dos
    cosas. Mostrar con un `DynamicMeshComponent` no paga ninguna: no hay asset que escribir ni que
    borrar. El asset recién se escribe en Bake, que es cuando alguien decidió quedarse con el
    resultado. Es la cocina de Houdini.

    El actor queda marcado como transitorio para que un Preview no ensucie el nivel guardado.
    """
    malla = _dynamic_mesh(source)
    if malla is None:
        return {"error": "mesh_mostrar necesita una malla M válida."}

    destino = location or unreal.Vector(0.0, 0.0, 0.0)
    actor = unreal.EditorLevelLibrary.spawn_actor_from_class(unreal.DynamicMeshActor, destino)
    if actor is None:
        return {"error": "no se pudo crear el actor de preview."}

    componente = actor.get_dynamic_mesh_component()
    if componente is None:
        unreal.EditorLevelLibrary.destroy_actor(actor)
        return {"error": "el actor de preview no expone su DynamicMeshComponent."}

    # `set_dynamic_mesh` y no `append_mesh` sobre el suyo: reemplazar es la semántica del preview,
    # y acumular dejaría la malla anterior adentro en cada recocción del live view.
    componente.set_dynamic_mesh(malla)
    actor.set_actor_label(name)
    contados = unreal.GeometryScript_MeshQueries.get_num_triangle_i_ds(malla)
    return {"actor": actor, "triangulos": int(contados),
            "info": f"PREVIEW ✓ — {contados} triángulos sin hornear"}
