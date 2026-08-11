"""¿La cinta de `mesh_ribbon` mira para arriba o para abajo EN UNREAL?

Brian abrió «Borde de camino» en el viewport y no vio la superficie: sólo el contorno de selección,
con el piso visible a través. «Muro sobre spline», que se construye encima de la misma cinta, se ve
del lado equivocado. Las sondas anteriores daban verde porque miden las NORMALES DE SOMBREADO que le
pasamos a los buffers —y ésas dicen `(0,0,1)`, hacia arriba—, pero el backface culling no las usa:
usa el ORDEN DE LOS ÍNDICES de cada triángulo, que nadie mide.

Esta sonda no discute convenciones de winding. Mide un CONTROL y un TRATAMIENTO con la misma vara:

  · control     `mesh_box` nativo, que en el viewport se ve bien.
  · tratamiento `mesh_ribbon`, que no se ve.

Si Unreal reporta la cara de arriba de la caja hacia +Z y la de la cinta hacia -Z, la cinta está
invertida respecto de lo que el motor considera frente, y no hace falta saber si UE es CW o CCW.

    UnrealEditor-Cmd <proyecto>.uproject -run=pythonscript \
        -script=<plugin>/tools/experiments/investiga_winding_ribbon_58.py \
        -RenderOffScreen -unattended -nosplash -stdout

Salida en el `BotOO*.log` MÁS RECIENTE: con el editor GUI abierto, este proceso escribe `BotOO_2.log`.
"""

from __future__ import annotations

import unreal

from jam import mesh


def log(mensaje: str) -> None:
    unreal.log(f"[WINDING] {mensaje}")


def normal_geometrica(a, b, c):
    """Normal por regla de la mano derecha sobre el orden en que UE guarda el triángulo."""
    ux, uy, uz = b.x - a.x, b.y - a.y, b.z - a.z
    vx, vy, vz = c.x - a.x, c.y - a.y, c.z - a.z
    nx, ny, nz = uy * vz - uz * vy, uz * vx - ux * vz, ux * vy - uy * vx
    largo = (nx * nx + ny * ny + nz * nz) ** 0.5
    if largo < 1e-9:
        return None
    return (nx / largo, ny / largo, nz / largo)


def caras_hacia_arriba(malla, etiqueta: str):
    """Cuenta triángulos por su normal de CARA — la que computa Unreal desde el winding.

    Se usa `get_triangle_face_normal` y no un cross product propio a propósito: la pregunta es qué
    considera frente EL MOTOR, así que la respuesta tiene que venir del motor.
    """
    consultas = unreal.GeometryScript_MeshQueries
    total = consultas.get_num_triangle_i_ds(malla)
    arriba = abajo = plano = 0
    muestra = []
    for tid in range(total):
        n = consultas.get_triangle_face_normal(malla, tid)
        if isinstance(n, tuple):
            # El binding envuelve la salida junto con otros valores; el Vector es el que interesa.
            n = next(v for v in n if isinstance(v, unreal.Vector))
        if len(muestra) < 3:
            muestra.append((round(n.x, 3), round(n.y, 3), round(n.z, 3)))
        if n.z > 0.1:
            arriba += 1
        elif n.z < -0.1:
            abajo += 1
        else:
            plano += 1
    log(f"{etiqueta}: {total} triángulos · +Z={arriba} · -Z={abajo} · verticales={plano}")
    log(f"{etiqueta}: primeras normales de cara {muestra}")
    return arriba, abajo


def main() -> None:
    log("=" * 70)
    # Si el binding no expone lo que la sonda asume, mejor verlo acá que interpretar un error suelto.
    disponibles = [n for n in dir(unreal.GeometryScript_MeshQueries)
                   if "triangle" in n.lower() and not n.startswith("_")]
    log(f"API de triángulos disponible: {disponibles}")

    # CONTROL: una caja nativa. Su tapa superior tiene que dar +Z si la vara está bien calibrada.
    caja = mesh.box(size_x=200.0, size_y=200.0, size_z=10.0)
    if "error" in caja:
        log(f"FALLA control: {caja['error']}")
        return
    c_arriba, c_abajo = caras_hacia_arriba(caja["mesh"], "control mesh_box")

    # TRATAMIENTO: la cadena EXACTA del tutorial «Borde de camino», con sus mismos parámetros. No se
    # arma una cinta de laboratorio: el defecto se vio por este camino y por acá se lo mide.
    from jam import curve as curva_mod

    eje = curva_mod.bezier(start_x=0.0, start_y=0.0, start_z=0.0,
                           end_x=900.0, end_y=0.0, end_z=80.0,
                           bend_x=0.0, bend_y=320.0, bend_z=-40.0, segments=12)
    if "error" in eje:
        log(f"FALLA eje: {eje['error']}")
        return
    uniforme = curva_mod.resample(eje["curve"], count=25, samples=32)
    if "error" in uniforme:
        log(f"FALLA resample: {uniforme['error']}")
        return
    borde = curva_mod.offset(uniforme["curve"], distance=180.0, side="left", plane="xy",
                             join="miter", miter_limit=2.5, samples=32)
    if "error" in borde:
        log(f"FALLA offset: {borde['error']}")
        return
    cinta = mesh.ribbon(borde["curve"], width=360.0, plane="xy", join="miter",
                        miter_limit=2.5, uv_scale=200.0, material_id=0, samples=32)
    if "error" in cinta:
        log(f"FALLA tratamiento: {cinta['error']}")
        return
    t_arriba, t_abajo = caras_hacia_arriba(cinta["mesh"], "tratamiento mesh_ribbon")

    # El tutorial recalcula normales DESPUÉS de la cinta. Eso toca el sombreado, no el winding: si
    # después de este paso la cara sigue mirando para abajo, queda descartado como remedio.
    suavizada = mesh.normals(cinta["mesh"], angle_weighted=True, area_weighted=True)
    if "error" not in suavizada:
        caras_hacia_arriba(suavizada.get("mesh", cinta["mesh"]), "tras mesh_normals")

    log("-" * 70)
    log(f"control: tapa +Z presente = {c_arriba > 0} (tiene {c_arriba} caras +Z, {c_abajo} caras -Z)")
    log(f"tratamiento: la cinta plana quedó {'ARRIBA (+Z)' if t_arriba and not t_abajo else ''}"
        f"{'ABAJO (-Z) ← INVERTIDA' if t_abajo and not t_arriba else ''}"
        f"{'MEZCLADA ← incoherente' if t_arriba and t_abajo else ''}")

    # Esta sonda nació para diagnosticar y quedó como sonda de REGRESIÓN: el defecto ya se corrigió
    # en `ribbon_core`, así que ver la cinta hacia abajo otra vez significa que alguien lo revirtió.
    if t_abajo > 0 and t_arriba == 0:
        log("VEREDICTO ROJO: la cinta volvió a mirar para ABAJO — invisible desde arriba por "
            "backface culling, y el muro extruido hereda la vuelta. Es la regresión de 2026-08-10.")
    elif t_arriba > 0 and t_abajo == 0 and c_arriba > 0:
        log("VEREDICTO VERDE: la cinta le muestra al motor la cara de arriba, igual que la caja "
            "nativa del control.")
    else:
        log("VEREDICTO: resultado incoherente — revisar la sonda antes de sacar conclusiones.")
    log("JAM_WINDING_58 MEDIDO")


main()
