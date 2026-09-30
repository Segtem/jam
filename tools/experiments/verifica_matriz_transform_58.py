"""Sonda de editor: `mesh_transform` con una matriz cableada, el primer consumidor de escena de las
matrices (tarea `matrices-ue`), corrido en Unreal por el camino real (`api.run_text`) y comparado con
lo que calcula el núcleo (`malla_ops.transformar`, `M · v`) sobre la misma caja asimétrica.

En Unreal la matriz llega a Geometry Script como `FTransform` (`ue.transform_de_matriz`: la
transposición de convención vive ahí). Si la transposición faltara, la rotación saldría al revés y la
traslación en la fila equivocada: las cajas no coincidirían. Mide caja envolvente, área y volumen
(positivo = caras hacia afuera, también con espejo), y que una cizalla dé error en el nodo.
Marca `JAM_MATRIZ_TRANSFORM`.
"""

import json
import os
import traceback

import unreal

from jam import api, graph, malla_ops, math_core as mc
from jam import comun

MARCA = "JAM_MATRIZ_TRANSFORM"
CAJA = "caja = mesh_box size_x=100 size_y=50 size_z=30\n"
CASOS = [
    ("rotar_y_trasladar",
     "r = matrix_rotation eje=0,0,1 ángulo=90\nt = matrix_translation traslación=10,20,30\n"
     "m = matrix_multiply a=@t b=@r\ntr = mesh_transform @caja matrix=@m\n",
     mc._mx_por_mx(mc._mx_traslacion((10, 20, 30)), mc._mx_rotacion((0, 0, 1), 90)), {}),
    ("escala_y_rotacion_oblicua",
     "s = matrix_scale_matrix escala=2,1,0.5\nr = matrix_rotation eje=1,1,0 ángulo=30\n"
     "m = matrix_multiply a=@r b=@s\ntr = mesh_transform @caja matrix=@m\n",
     mc._mx_por_mx(mc._mx_rotacion((1, 1, 0), 30), mc._mx_escala((2, 1, 0.5))), {}),
    ("espejo",
     "m = matrix_scale_matrix escala=-1,1,1\ntr = mesh_transform @caja matrix=@m\n",
     mc._mx_escala((-1, 1, 1)), {}),
    ("campos_y_despues_matriz",
     "m = matrix_translation traslación=0,0,100\ntr = mesh_transform @caja scale_z=2 yaw=45 matrix=@m\n",
     mc._mx_traslacion((0, 0, 100)), {"scale_z": 2.0, "yaw": 45.0}),
]


def medir_unreal(dm):
    q = unreal.GeometryScript_MeshQueries
    caja = q.get_mesh_bounding_box(dm)
    area, volumen = q.get_mesh_volume_area(dm)[:2] if isinstance(q.get_mesh_volume_area(dm), tuple) \
        else (None, None)
    return {"min": [round(caja.min.x, 2), round(caja.min.y, 2), round(caja.min.z, 2)],
            "max": [round(caja.max.x, 2), round(caja.max.y, 2), round(caja.max.z, 2)],
            "area": area, "volumen": volumen}


def medir_nucleo(matriz, campos):
    base, _ = comun.IMPLEMENTA["mesh_box"](None, size_x=100, size_y=50, size_z=30)
    m = malla_ops.transformar(base, matriz=matriz, **campos)
    xs, ys, zs = zip(*m.vertices)
    return {"min": [round(min(xs), 2), round(min(ys), 2), round(min(zs), 2)],
            "max": [round(max(xs), 2), round(max(ys), 2), round(max(zs), 2)]}


def main():
    r, fallas = {}, []
    for nombre, texto, matriz, campos in CASOS:
        corrida = json.loads(api.run_text(CAJA + texto, '{"nodes": {}, "edges": []}'))
        estado = corrida.get("nodes", {}).get("tr", {})
        if estado.get("estado") != "ok":
            fallas.append(f"{nombre}: el nodo no corrió: {estado}")
            continue
        u = medir_unreal(graph.ultima_corrida()["tr"])
        n = medir_nucleo(matriz, campos)
        r[nombre] = {"unreal": u, "nucleo": n}
        d = max(abs(a - b) for k in ("min", "max") for a, b in zip(u[k], n[k]))
        if d > 0.05:
            fallas.append(f"{nombre}: la caja difiere {d:.3f} cm — Unreal {u} · núcleo {n}")
        if u["volumen"] is not None and u["volumen"] <= 0:
            fallas.append(f"{nombre}: volumen {u['volumen']} en Unreal: caras hacia adentro")
    cizalla = "1 0.5 0 0 0 1 0 0 0 0 1 0 0 0 0 1".replace(" ", ",")
    malo = json.loads(api.run_text(
        CAJA + f'tr = mesh_transform @caja matrix="{cizalla}"\n', '{"nodes": {}, "edges": []}'))
    texto_error = malo.get("nodes", {}).get("tr", {}).get("texto", "")
    r["cizalla"] = texto_error
    if "cizalla" not in texto_error:
        fallas.append(f"la cizalla no se rechazó con su motivo: {texto_error!r}")
    api.discard()
    return r, fallas


try:
    resultado, fallas = main()
except Exception:  # noqa: BLE001
    resultado, fallas = {}, [traceback.format_exc()]
veredicto = "ROJO" if fallas else "VERDE"
destino = os.path.join(unreal.Paths.project_saved_dir(), "jam_matriz_transform.json")
with open(destino, "w", encoding="utf-8") as f:
    json.dump({"veredicto": veredicto, **resultado, "fallas": fallas}, f, ensure_ascii=False, indent=1)
unreal.log(f"{MARCA} {veredicto} → {destino}")
