"""Mide las tres cosas de las que depende llevar PROCEDENCIA por el pipeline de mallas de Jam.

El cable `M` transporta un `UDynamicMesh` pelado: no hay dónde colgar metadata al lado. Para que un
nodo de aguas abajo sepa de qué curva salió cada vértice —lo que necesita Pivot Painter para que el
viento mueva cada rama sobre su propio pivote— el dato tiene que viajar ENCIMA de la malla, en un
canal por vértice.

De los canales posibles, sólo el color de vértice se escribe de una sola llamada
(`SetMeshPerVertexColors`); los UVs se escriben triángulo por triángulo. Antes de construir sobre
esa base hay tres preguntas que no se pueden contestar leyendo headers:

    1. ¿Los rangos de vértice de cada `append_simple_swept_polygon` son contiguos y predecibles?
       Si no lo son, no hay forma de saber qué vértices son de qué rama.
    2. ¿El canal SOBREVIVE el resto del pipeline —merge, transform, hornear a StaticMesh— o se
       pierde en el camino? Un canal que no sobrevive no sirve de transporte.
    3. ¿Cuánto cuesta la ruta de UVs por triángulo? Si es tolerable, hay 2 floats más de espacio.

Correr:

    UnrealEditor-Cmd <proyecto>.uproject -run=pythonscript \\
        -script=<plugin>/tools/experiments/sonda_procedencia.py \\
        -RenderOffScreen -unattended -nosplash -stdout

No escribe nada en el proyecto: todas las mallas son transitorias salvo el StaticMesh de la
pregunta 2, que se crea bajo /Game/Jam/_Sonda y se puede borrar.
"""

from __future__ import annotations

import time

import unreal


def log(mensaje: str) -> None:
    # unreal.log va a LogPython y no sale por el stdout del commandlet: hay que imprimir.
    print(f"[SONDA] {mensaje}", flush=True)


def nueva_malla():
    return unreal.DynamicMeshPool().request_mesh()


def contar(malla) -> int:
    return unreal.GeometryScript_MeshQueries.get_vertex_count(malla)


def colores(malla):
    """Los colores por vértice como lista de tuplas, o None si la malla no tiene el overlay."""
    devuelto = unreal.GeometryScript_VertexColors.get_mesh_per_vertex_colors(malla)
    if not isinstance(devuelto, tuple) or len(devuelto) < 3:
        return None
    lista, valido = devuelto[1], devuelto[2]
    if not valido:
        return None
    convertir = getattr(lista, "convert_color_list_to_array", None)
    crudo = convertir() if convertir else lista
    if isinstance(crudo, tuple):
        crudo = crudo[-1]
    return [(c.r, c.g, c.b, c.a) for c in crudo]


# ---------------------------------------------------------------- pregunta 1
def pregunta_rangos() -> list[tuple[int, int]]:
    """¿Cada barrido ocupa un rango contiguo y conocido de vértices?"""
    log("--- 1. rangos de vértice por barrido ---")
    malla = nueva_malla()
    opciones = unreal.GeometryScriptPrimitiveOptions()
    identidad = unreal.Transform()
    rangos = []
    for i, (lados, puntos) in enumerate(((8, 5), (6, 9), (12, 3))):
        antes = contar(malla)
        perfil = [unreal.Vector2D(10.0 * (i + 1), 0.0)] * lados
        import math
        perfil = [unreal.Vector2D(math.cos(2 * math.pi * k / lados) * 10.0 * (i + 1),
                                  math.sin(2 * math.pi * k / lados) * 10.0 * (i + 1))
                  for k in range(lados)]
        camino = [unreal.Vector(0.0, i * 200.0, z * 50.0) for z in range(puntos)]
        unreal.GeometryScript_Primitives.append_simple_swept_polygon(
            malla, opciones, identidad, perfil, camino,
            loop=False, capped=True, start_scale=1.0, end_scale=0.4,
            rotation_angle_deg=0.0, miter_limit=4.0)
        despues = contar(malla)
        rangos.append((antes, despues))
        esperado = lados * puntos
        log(f"barrido {i}: lados={lados} puntos={puntos} → vértices {antes}..{despues} "
            f"({despues - antes} nuevos; lados*puntos={esperado}, "
            f"{'coincide' if despues - antes == esperado else 'DIFIERE: las tapas suman'})")
    total = contar(malla)
    contiguos = all(b == rangos[i + 1][0] for i, (_, b) in enumerate(rangos[:-1]))
    log(f"total {total} · rangos contiguos: {contiguos}")
    log("VEREDICTO 1: " + ("los rangos sirven de procedencia" if contiguos
                           else "NO se puede mapear vértice→rama por rango"))
    return rangos


# ---------------------------------------------------------------- pregunta 2
def pregunta_supervivencia() -> None:
    """¿El color de vértice sobrevive merge, transform y el horneado a StaticMesh?"""
    log("--- 2. supervivencia del canal por el pipeline ---")
    opciones = unreal.GeometryScriptPrimitiveOptions()
    identidad = unreal.Transform()

    a = nueva_malla()
    unreal.GeometryScript_Primitives.append_box(a, opciones, identidad, 100.0, 100.0, 100.0)
    # Marca también en UV2, que es la ruta de Pivot Painter: hay que saber si sobrevive el horneado.
    unreal.GeometryScript_UVs.set_num_uv_sets(a, 3)
    marca_uv = unreal.GeometryScriptUVTriangle()
    marca_uv.uv0 = unreal.Vector2D(0.75, 0.125)
    marca_uv.uv1 = unreal.Vector2D(0.75, 0.125)
    marca_uv.uv2 = unreal.Vector2D(0.75, 0.125)
    for tid in range(unreal.GeometryScript_MeshQueries.get_num_triangle_i_ds(a)):
        unreal.GeometryScript_UVs.set_mesh_triangle_u_vs(a, 2, tid, marca_uv,
                                                         defer_change_notifications=True)
    # Marca reconocible: rojo 0.25 en TODOS los vértices de A.
    unreal.GeometryScript_VertexColors.set_mesh_constant_vertex_color(
        a, unreal.LinearColor(0.25, 0.0, 0.0, 1.0),
        unreal.GeometryScriptColorFlags(), clear_existing=True)
    marcados = colores(a)
    log(f"A pintada: {len(marcados) if marcados else 0} vértices, primero {marcados[0] if marcados else None}")

    # --- transform ---
    xf = unreal.Transform(location=unreal.Vector(500.0, 0.0, 0.0))
    unreal.GeometryScript_MeshTransforms.transform_mesh(a, xf)
    tras_transform = colores(a)
    ok_transform = bool(tras_transform) and abs(tras_transform[0][0] - 0.25) < 1e-3
    log(f"tras transform: {'CONSERVA' if ok_transform else 'PIERDE'} el color")

    # --- merge con una malla SIN colores (el caso peligroso) ---
    b = nueva_malla()
    unreal.GeometryScript_Primitives.append_box(b, opciones, identidad, 50.0, 50.0, 50.0)
    unreal.GeometryScript_MeshEdits.append_mesh(a, b, identidad)
    tras_merge = colores(a)
    if tras_merge:
        rojos = sum(1 for c in tras_merge if abs(c[0] - 0.25) < 1e-3)
        log(f"tras merge con malla SIN colores: {len(tras_merge)} vértices, "
            f"{rojos} conservan el 0.25 → "
            f"{'CONSERVA los de A' if rojos >= 8 else 'PIERDE la marca'}")
    else:
        log("tras merge: PIERDE el overlay entero")

    # --- hornear a StaticMesh y leer de vuelta ---
    try:
        ruta = "/Game/Jam/_Sonda/SM_SondaColor"
        opciones_asset = unreal.GeometryScriptCreateNewStaticMeshAssetOptions()
        opciones_asset.set_editor_property("enable_recompute_normals", False)
        devuelto = unreal.GeometryScript_NewAssetUtils.create_new_static_mesh_asset_from_mesh(
            a, ruta, opciones_asset)
        creado = devuelto[0] if isinstance(devuelto, tuple) else devuelto
        log(f"horneado en {ruta}: {'ok' if creado is not None else 'FALLÓ'}")
        if creado is not None:
            leida = nueva_malla()
            unreal.GeometryScript_AssetUtils.copy_mesh_from_static_mesh(
                creado, leida, unreal.GeometryScriptCopyMeshFromAssetOptions(),
                unreal.GeometryScriptMeshReadLOD())
            tras_hornear = colores(leida)
            if tras_hornear:
                rojos = sum(1 for c in tras_hornear if abs(c[0] - 0.25) < 0.02)
                log(f"tras hornear+releer: {len(tras_hornear)} vértices, {rojos} con la marca "
                    f"\u2192 {'SOBREVIVE' if rojos > 0 else 'SE PIERDE'}")
                log(f"  precisión: primero {tras_hornear[0]} (era 0.25 exacto; "
                    f"un StaticMesh guarda FColor de 8 bits)")
            else:
                log("tras hornear+releer: SIN colores")
            # ¿y los UVs de datos? Es la ruta que la pregunta 3 volvió viable. No hay getter del
            # número de canales: se lee el canal 2 directo y se ve si trae la marca.
            devuelto_uv = unreal.GeometryScript_UVs.get_mesh_per_vertex_u_vs(leida, 2)
            lista_uv = devuelto_uv[1] if isinstance(devuelto_uv, tuple) else devuelto_uv
            valido = devuelto_uv[2] if isinstance(devuelto_uv, tuple) and len(devuelto_uv) > 2 else True
            convertir = getattr(lista_uv, "convert_uv_list_to_array", None)
            crudo = convertir() if convertir else lista_uv
            if isinstance(crudo, tuple):
                crudo = crudo[-1]
            marcados_uv = [uv for uv in crudo if abs(uv.x - 0.75) < 1e-4 and abs(uv.y - 0.125) < 1e-4]
            log(f"  UV canal 2 tras hornear: válido={valido} · {len(marcados_uv)} de {len(list(crudo))} "
                f"con la marca (0.75, 0.125) \u2192 "
                f"{'SOBREVIVE' if marcados_uv else 'SE PIERDE'}")
    except Exception as exc:  # noqa: BLE001 — la sonda reporta, no decide
        log(f"horneado falló: {type(exc).__name__}: {exc}")


# ---------------------------------------------------------------- pregunta 3
def pregunta_costo_uvs() -> None:
    """¿Cuánto cuesta escribir UVs triángulo por triángulo? Es la única ruta a 2 floats más."""
    log("--- 3. costo de la ruta UV por triángulo ---")
    malla = nueva_malla()
    opciones = unreal.GeometryScriptPrimitiveOptions()
    unreal.GeometryScript_Primitives.append_sphere_lat_long(
        malla, opciones, unreal.Transform(), 100.0, 32, 64)
    triangulos = unreal.GeometryScript_MeshQueries.get_num_triangle_i_ds(malla)
    unreal.GeometryScript_UVs.set_num_uv_sets(malla, 3)
    log(f"malla de prueba: {triangulos} triángulos, 3 canales UV")

    uv = unreal.GeometryScriptUVTriangle()
    uv.uv0 = unreal.Vector2D(0.5, 0.5)
    uv.uv1 = unreal.Vector2D(0.5, 0.5)
    uv.uv2 = unreal.Vector2D(0.5, 0.5)
    arranque = time.perf_counter()
    escritos = 0
    for tid in range(triangulos):
        unreal.GeometryScript_UVs.set_mesh_triangle_u_vs(
            malla, 1, tid, uv, defer_change_notifications=True)
        escritos += 1
    tardanza = time.perf_counter() - arranque
    log(f"{escritos} triángulos en {tardanza * 1000:.0f} ms "
        f"({tardanza / max(escritos, 1) * 1e6:.1f} µs cada uno)")
    log(f"VEREDICTO 3: un árbol de 20k triángulos tardaría ~{tardanza / max(escritos, 1) * 20000:.1f} s")


def main() -> None:
    log("=" * 70)
    try:
        pregunta_rangos()
    except Exception as exc:  # noqa: BLE001
        log(f"pregunta 1 falló: {type(exc).__name__}: {exc}")
    try:
        pregunta_supervivencia()
    except Exception as exc:  # noqa: BLE001
        log(f"pregunta 2 falló: {type(exc).__name__}: {exc}")
    try:
        pregunta_costo_uvs()
    except Exception as exc:  # noqa: BLE001
        log(f"pregunta 3 falló: {type(exc).__name__}: {exc}")
    log("=" * 70)


main()
