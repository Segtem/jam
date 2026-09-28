"""Sonda de editor: vuelca lo que PRODUCE Unreal para las primitivas de la próxima tanda de la base
común (tarea `base-comun`), para que el núcleo las reproduzca sin tener el motor a mano.

Cada caso corre el verbo por el camino real (`tools.t_*`, el mismo que el Graph) y guarda, por
triángulo, sus tres posiciones EN EL ORDEN DEL MOTOR y la normal de la cara que Unreal dibuja
(`get_triangle_face_normal`), más los hechos (triángulos, vértices, caja, área, volumen). Escribe
`Content/Python/tests/fixtures/primitivas_unreal.json` y la marca `JAM_PRIMITIVAS`.
"""

import json
import os
import traceback

import unreal

SALIDA = os.path.expanduser("~/Dev/jam/Content/Python/tests/fixtures/primitivas_unreal.json")

FUENTES = {
    "mesh_quad": [{}, {"width": 250, "height": 40}],
    "mesh_grid": [{}, {"width": 300, "height": 120, "columns": 4, "rows": 2},
                  {"width": 100, "height": 100, "columns": 2, "rows": 2}, {"columns": 1, "rows": 1}],
    "mesh_cylinder": [{}, {"radius": 30, "height": 80, "sides": 5, "height_steps": 3, "capped": False},
                      {"radius": 20, "height": 50, "sides": 3, "height_steps": 1, "capped": True},
                      {"sides": 2}, {"height_steps": 0}],
    "mesh_cone": [{}, {"base_radius": 40, "top_radius": 20, "height": 100, "sides": 6,
                       "height_steps": 1, "capped": True},
                  {"base_radius": 50, "top_radius": 0, "height": 70, "sides": 3, "height_steps": 2,
                   "capped": False}],
    "mesh_sphere": [{}, {"radius": 50, "latitude_steps": 3, "longitude_steps": 4},
                    {"radius": 10, "latitude_steps": 5, "longitude_steps": 7},
                    {"latitude_steps": 1}, {"longitude_steps": 2}],
    "mesh_disc": [{}, {"radius": 50, "sides": 6, "start_angle": 0, "end_angle": 180},
                  {"radius": 80, "sides": 8, "hole_radius": 30}],
    "mesh_triangle": [{}, {"size": 37}],
    "mesh_capsule": [{}, {"radius": 20, "length": 60, "hemisphere_steps": 2, "sides": 5},
                     {"hemisphere_steps": 0}],
    "mesh_torus": [{}, {"major_radius": 60, "minor_radius": 10, "major_steps": 5, "minor_steps": 3},
                   {"major_steps": 2}],
    "mesh_round_rect": [{}, {"size_x": 150, "size_y": 40, "corner_radius": 10, "steps_round": 2},
                        {"corner_radius": 0}],
    "mesh_stairs": [{}, {"step_width": 80, "step_height": 25, "step_depth": 40, "steps": 3, "floating": True}],
    "mesh_stairs_curved": [{}, {"step_width": 60, "step_height": 20, "inner_radius": 50,
                                "curve_angle": -120, "steps": 4, "floating": True}],
    "mesh_sphere_box": [{}, {"radius": 30, "steps": 2}, {"steps": 0}],
}
TRANSFORMS = [{"x": 10, "y": -20, "z": 30}, {"yaw": 90}, {"pitch": 30, "yaw": 10, "roll": 45},
              {"scale_x": 2, "scale_y": 0.5, "scale_z": 3}, {"scale_x": -1},
              {"x": 5, "pitch": -20, "yaw": 135, "roll": 5, "scale_x": 1.5, "scale_y": 1.5, "scale_z": 0.25}]


def _vec(v):
    return [round(v.x, 4), round(v.y, 4), round(v.z, 4)]


def medir(dm):
    q = unreal.GeometryScript_MeshQueries
    caja = q.get_mesh_bounding_box(dm)
    av = q.get_mesh_volume_area(dm)
    nums = [v for v in (av if isinstance(av, tuple) else (av,)) if isinstance(v, float)]
    tris = []
    for tid in range(q.get_num_triangle_i_ds(dm)):
        pos = q.get_triangle_positions(dm, tid)
        pts = [v for v in (pos if isinstance(pos, tuple) else (pos,)) if isinstance(v, unreal.Vector)]
        n = q.get_triangle_face_normal(dm, tid)
        if isinstance(n, tuple):
            n = next(v for v in n if isinstance(v, unreal.Vector))
        tris.append({"p": [_vec(p) for p in pts], "n": _vec(n)})
    from jam import mesh
    crudas = mesh._posiciones(dm)
    # «vertices» es la cuenta CRUDA de la DynamicMesh (un cono con punta deja un vértice por lado en
    # el ápice); «posiciones» son las distintas, a 0,001 cm: el hecho geométrico que se compara entre
    # motores. Lo encontró agy2: el juez comparaba posiciones contra la cuenta cruda.
    return {"triangulos": len(tris), "vertices": len(crudas),
            "posiciones": len({tuple(round(c, 3) for c in p) for p in crudas}),
            "min": _vec(caja.min), "max": _vec(caja.max),
            "area": round(nums[0], 4) if nums else None, "volumen": round(nums[1], 4) if len(nums) > 1 else None,
            "tris": tris}


#: La REFERENCIA tiene que ser Geometry Script. Un verbo que ya pasó a la base común corre en
#: Unreal con el código del núcleo, así que volcarlo por el camino del Graph mediría al núcleo
#: contra sí mismo (pasó: el re-volcado del cono cambió). Para esos, la función de `mesh.py`, que es
#: la de Geometry Script; para los demás, el verbo.
REFERENCIA_GEOMETRY_SCRIPT = {"mesh_box": "box", "mesh_quad": "quad", "mesh_grid": "grid",
                              "mesh_disc": "disc", "mesh_cylinder": "cylinder", "mesh_cone": "cone",
                              "mesh_sphere": "sphere", "mesh_triangle": "triangle",
                              "mesh_capsule": "capsule", "mesh_torus": "torus",
                              "mesh_round_rect": "round_rect", "mesh_stairs": "stairs",
                              "mesh_stairs_curved": "stairs_curved", "mesh_sphere_box": "sphere_box"}


def correr(verbo, entrada, params):
    from jam import mesh, tools
    if verbo in REFERENCIA_GEOMETRY_SCRIPT:
        resultado = getattr(mesh, REFERENCIA_GEOMETRY_SCRIPT[verbo])(**params)
        if "error" in resultado:
            raise RuntimeError(resultado["error"])
        return resultado["mesh"]
    tools.limpiar_asset_producido_runtime(verbo)
    tools.REGISTRO[verbo]["fn"](entrada, **params)
    return tools.dato_producido_runtime(verbo)


def caso(verbo, entrada, params, **extra):
    """Un caso: la malla medida o, si el motor la rechaza, su mensaje (el núcleo tiene que rechazar
    lo mismo)."""
    try:
        return {"verbo": verbo, "params": params, **extra, "motor": medir(correr(verbo, entrada, params))}
    except RuntimeError as e:
        return {"verbo": verbo, "params": params, **extra, "error": str(e)}


def main():
    from jam import registro, tools
    sin_referencia = sorted(v for v in FUENTES if v in registro.COMUNES
                            and tools.REGISTRO[v].get("source") and v not in REFERENCIA_GEOMETRY_SCRIPT)
    if sin_referencia:
        raise RuntimeError(f"{sin_referencia} ya son comunes y no tienen su función de Geometry "
                           "Script en REFERENCIA_GEOMETRY_SCRIPT: se volcaría el núcleo contra sí mismo")
    casos = []
    for verbo, lista in FUENTES.items():
        for params in lista:
            casos.append(caso(verbo, None, params))
    caja = correr("mesh_box", None, {"size_x": 100, "size_y": 60, "size_z": 40})
    for params in TRANSFORMS:
        casos.append(caso("mesh_transform", caja, params, fuente="mesh_box size_x=100 size_y=60 size_z=40"))
    otra = correr("mesh_transform", caja, {"x": 200, "yaw": 30})
    casos.append({"verbo": "mesh_merge", "fuente": ["mesh_box size_x=100 size_y=60 size_z=40",
                                                    "la misma con mesh_transform x=200 yaw=30"],
                  "params": {}, "motor": medir(correr("mesh_merge", [caja, otra], {}))})
    return casos


try:
    datos = {"veredicto": "VERDE", "motor": "unreal 5.8.1", "casos": main()}
except Exception:  # noqa: BLE001
    datos = {"veredicto": "EXCEPCION", "excepcion": traceback.format_exc()}
with open(SALIDA, "w", encoding="utf-8") as f:
    json.dump(datos, f, ensure_ascii=False, indent=1)
unreal.log(f"JAM_PRIMITIVAS {datos['veredicto']} → {SALIDA}")
