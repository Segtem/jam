"""Sonda de editor: la caja del NÚCLEO (`malla_core.caja` → `mesh.desde_malla`) es la misma que la de
Geometry Script (`mesh.box`), medida por el motor. Tarea `base-comun`.

Compara triángulos, vértices (tras soldar), caja envolvente, área y volumen, y que TODA cara que el
motor considera frontal (`get_triangle_face_normal`) mire hacia afuera. Resultado en
`Saved/jam_caja_comun.json` y la marca `JAM_CAJA_COMUN`.
"""

import json
import os
import traceback

import unreal

CASOS = [dict(size_x=100, size_y=100, size_z=100),
         dict(size_x=200, size_y=80, size_z=50, steps_x=2, steps_y=1, steps_z=3),
         dict(size_x=37.5, size_y=410, size_z=12, steps_x=0, steps_y=4, steps_z=0)]


def medir(dm):
    q = unreal.GeometryScript_MeshQueries
    caja = q.get_mesh_bounding_box(dm)
    area_vol = q.get_mesh_volume_area(dm)
    nums = [v for v in (area_vol if isinstance(area_vol, tuple) else (area_vol,))
            if isinstance(v, float)]
    tris = q.get_num_triangle_i_ds(dm)
    centro = ((caja.min.x + caja.max.x) / 2, (caja.min.y + caja.max.y) / 2, (caja.min.z + caja.max.z) / 2)
    adentro = 0
    for tid in range(tris):
        n = q.get_triangle_face_normal(dm, tid)
        if isinstance(n, tuple):
            n = next(v for v in n if isinstance(v, unreal.Vector))
        pos = q.get_triangle_positions(dm, tid)
        pts = [v for v in (pos if isinstance(pos, tuple) else (pos,)) if isinstance(v, unreal.Vector)]
        cx = sum(p.x for p in pts) / 3 - centro[0]
        cy = sum(p.y for p in pts) / 3 - centro[1]
        cz = sum(p.z for p in pts) / 3 - centro[2]
        if n.x * cx + n.y * cy + n.z * cz <= 0:
            adentro += 1
    return {"triangulos": tris,
            "vertices": q.get_vertex_count(dm) if hasattr(q, "get_vertex_count")
            else len(q.get_all_vertex_positions(dm)[0] if isinstance(q.get_all_vertex_positions(dm), tuple)
                     else q.get_all_vertex_positions(dm)),
            "min": [round(caja.min.x, 3), round(caja.min.y, 3), round(caja.min.z, 3)],
            "max": [round(caja.max.x, 3), round(caja.max.y, 3), round(caja.max.z, 3)],
            "area_volumen": [round(v, 2) for v in nums],
            "caras_hacia_adentro": adentro}


def main():
    from jam import malla_core, mesh
    r, fallas = [], []
    for caso in CASOS:
        gs = medir(mesh.box(**caso)["mesh"])
        malla = malla_core.caja(**caso)
        comun = medir(mesh.desde_malla(malla))
        r.append({"caso": caso, "geometry_script": gs, "nucleo": comun,
                  "hechos_nucleo": malla_core.hechos(malla)})
        if gs != comun:
            fallas.append(f"{caso}: distinta")
        if comun["caras_hacia_adentro"]:
            fallas.append(f"{caso}: {comun['caras_hacia_adentro']} caras del núcleo miran adentro")
    return {"casos": r, "fallas": fallas}


try:
    resultado = main()
    veredicto = "VERDE" if not resultado["fallas"] else "ROJO"
except Exception:  # noqa: BLE001
    resultado = {"excepcion": traceback.format_exc()}
    veredicto = "EXCEPCION"
destino = os.path.join(unreal.Paths.project_saved_dir(), "jam_caja_comun.json")
with open(destino, "w", encoding="utf-8") as f:
    json.dump({"veredicto": veredicto, **resultado}, f, ensure_ascii=False, indent=2)
unreal.log(f"JAM_CAJA_COMUN {veredicto} → {destino}")
