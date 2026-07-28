"""Verifica en el editor REAL que el pivote estampado por `mesh_pipe` sea correcto y sobreviva.

La suite mockea `unreal`, así que el estampado —que es puro adaptador— no lo cubre ningún test de
Python. Esto lo corre por el camino de verdad: construye un árbol de dos niveles con `curve_bezier`
+ `curve_frames` + `branch_from_frames`, lo barre con `pivot_uvs=True`, y comprueba tres cosas que
un bug silencioso rompería sin que nada se queje:

    1. cada triángulo lleva el pivote de SU rama y no el de otra (tantos pivotes distintos como
       ramas);
    2. el pivote de cada rama coincide con el arranque real de esa curva;
    3. todo eso sigue ahí después de hornear a StaticMesh.

Correr:

    UnrealEditor-Cmd <proyecto>.uproject -run=pythonscript \\
        -script=<plugin>/tools/experiments/verifica_pivote.py \\
        -RenderOffScreen -unattended -nosplash -stdout

La salida queda en Saved/Logs/<proyecto>.log — el stdout del commandlet no la reenvía.
"""

from __future__ import annotations

import unreal

from jam import curve, mesh


FALLAS = []


def log(mensaje: str) -> None:
    unreal.log(f"[PIVOTE] {mensaje}")


def exigir(condicion: bool, descripcion: str) -> None:
    log(("  OK   " if condicion else "  FALLA") + f" · {descripcion}")
    if not condicion:
        FALLAS.append(descripcion)


def uvs_de(dynamic, canal: int):
    """Los UVs del canal, leídos POR TRIÁNGULO.

    `get_mesh_per_vertex_u_vs` devuelve vacío acá y no es un bug: `SetMeshTriangleUVs` crea —lo dice
    su propio header— una isla UV aislada por triángulo, así que un vértice compartido tiene varios
    UVs y no hay «uno por vértice» que devolver. Para un canal de DATOS la isla no molesta: los tres
    vértices del triángulo llevan el mismo valor, así que la interpolación del shader da una
    constante, que es justo lo que se quiere.
    """
    salida = []
    for tid in range(unreal.GeometryScript_MeshQueries.get_num_triangle_i_ds(dynamic)):
        devuelto = unreal.GeometryScript_UVs.get_mesh_triangle_uv_element_i_ds(dynamic, canal, tid)
        elementos, validos = devuelto[1], devuelto[2]
        if not validos:
            continue
        for eid in (elementos.x, elementos.y, elementos.z):
            posicion = unreal.GeometryScript_UVs.get_mesh_uv_element_position(dynamic, canal, int(eid))
            uv, ok = posicion[1], posicion[2]
            if ok:
                salida.append((round(uv.x, 2), round(uv.y, 2)))
    return salida


def main() -> None:
    log("=" * 68)

    tronco = curve.bezier(end_z=900.0, bend_x=90.0, segments=10)["curve"]
    # `curve.frames` no toma radios: el que los propaga a `CurveFrame.radius` es `frame_stream`,
    # que es lo que llama el verbo. El radio del padre es justo lo que lee `radius_from_parent`.
    frames = curve.frame_stream(tronco, count=6, start=0.25, end=0.9,
                                radius_start=40.0, radius_end=12.0, seed=3)["frame_set"]
    ramas = curve.branch_from_frames(frames, length_min=0.35, length_max=0.55,
                                     relative_to_parent=True, seed=3)["curve"]
    esperados = {(round(p.points[0][0], 2), round(p.points[0][1], 2)) for p in ramas.paths}
    log(f"árbol: {len(ramas.paths)} ramas, {len(esperados)} arranques distintos")

    salida = mesh.pipe(ramas, radius_start=20.0, radius_end=4.0, sides=8, samples=12,
                       radius_from_parent=0.6, pivot_uvs=True)
    if "error" in salida:
        log(f"mesh_pipe falló: {salida['error']}")
        FALLAS.append("mesh_pipe")
        return
    malla = salida["mesh"]
    log(f"barrido: {salida['info']}")

    # 1 — un pivote por rama, no uno solo para todo
    xy = uvs_de(malla, mesh.CANAL_PIVOTE_XY)
    distintos = set(xy)
    exigir(len(distintos) == len(esperados),
           f"pivotes distintos en UV{mesh.CANAL_PIVOTE_XY}: {len(distintos)} "
           f"(ramas: {len(esperados)})")

    # 2 — y es el arranque REAL de cada rama, no un número cualquiera
    exigir(distintos == esperados,
           "cada pivote coincide con el arranque de su rama"
           + ("" if distintos == esperados else f" · sobran {distintos - esperados}"))

    # El canal Z/largo tiene que traer largos positivos y variados: si todos fueran iguales,
    # el estampado estaría escribiendo el mismo tramo una y otra vez.
    zl = uvs_de(malla, mesh.CANAL_PIVOTE_ZL)
    largos = {v for _, v in zl}
    exigir(all(v > 0.0 for v in largos) and len(largos) > 1,
           f"largos en UV{mesh.CANAL_PIVOTE_ZL}: {len(largos)} distintos, "
           f"min {min(largos):.0f} max {max(largos):.0f}")

    # 3 — sobrevive el horneado
    ruta = "/Game/Jam/_Sonda/SM_VerificaPivote"
    opciones = unreal.GeometryScriptCreateNewStaticMeshAssetOptions()
    opciones.set_editor_property("enable_recompute_normals", False)
    devuelto = unreal.GeometryScript_NewAssetUtils.create_new_static_mesh_asset_from_mesh(
        malla, ruta, opciones)
    creado = devuelto[0] if isinstance(devuelto, tuple) else devuelto
    if creado is None:
        exigir(False, "hornear a StaticMesh")
        return
    releida = unreal.DynamicMeshPool().request_mesh()
    unreal.GeometryScript_AssetUtils.copy_mesh_from_static_mesh(
        creado, releida, unreal.GeometryScriptCopyMeshFromAssetOptions(),
        unreal.GeometryScriptMeshReadLOD())
    tras = set(uvs_de(releida, mesh.CANAL_PIVOTE_XY))
    exigir(tras == distintos,
           f"los pivotes sobreviven el horneado ({len(tras)} de {len(distintos)})")

    log("=" * 68)
    log("VEREDICTO: " + ("TODO VERDE" if not FALLAS else f"{len(FALLAS)} FALLA(S): {FALLAS}"))


main()
