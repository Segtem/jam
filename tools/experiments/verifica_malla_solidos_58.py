"""Las medidas de sólido de `malla`, aplicadas a mallas REALES de UE 5.8.1.

El corpus diferencial usa prismas construidos en Python, porque el núcleo del extrude sólo configura
y la extrusión real la hace Geometry Script. Eso deja una pregunta sin responder que ningún test puro
puede contestar: **¿el signo de `volumen_orientado` es el que corresponde en el motor?** Si estuviera
al revés, la medida daría verde justamente a los sólidos dados vuelta.

Acá se contesta como se contestó el winding: con primitivas NATIVAS como control. Un `mesh_box` y una
esfera del motor están bien orientados por construcción, así que su volumen orientado tiene que dar
POSITIVO. Después se mide un `mesh_extrude` de verdad, que es el caso que interesa.

    UnrealEditor-Cmd <proyecto>.uproject -run=pythonscript \
        -script=<plugin>/tools/experiments/verifica_malla_solidos_58.py \
        -RenderOffScreen -unattended -nosplash -stdout

Salida en el `BotOO*.log` más reciente, EXCLUYENDO `BotOO-CRC.log`, que no lleva salida de Python.
"""

from __future__ import annotations

import unreal

from jam import curve, mesh, oracle_malla_facts


FALLAS = []


def log(mensaje: str) -> None:
    unreal.log(f"[MALLA-SOLIDOS] {mensaje}")


def exigir(condicion: bool, descripcion: str) -> None:
    log(("  OK   " if condicion else "  FALLA") + f" · {descripcion}")
    if not condicion:
        FALLAS.append(descripcion)


def leer(malla):
    """Vértices y triángulos tal como quedaron EN EL MOTOR, no como los mandamos."""
    consultas = unreal.GeometryScript_MeshQueries
    total = consultas.get_num_triangle_i_ds(malla)
    vertices, triangulos = [], []
    for tid in range(total):
        posiciones = consultas.get_triangle_positions(malla, tid)
        puntos = [v for v in posiciones if isinstance(v, unreal.Vector)][-3:]
        base = len(vertices)
        # Se reconstruye con vértices propios por triángulo: para el volumen con signo y el conteo
        # de aristas hace falta la identidad de cada vértice, y `get_triangle_positions` sólo da
        # posiciones. Se sueldan por coordenada redondeada, que es exacto en mallas generadas.
        for punto in puntos:
            vertices.append((round(punto.x, 4), round(punto.y, 4), round(punto.z, 4)))
        triangulos.append((base, base + 1, base + 2))
    # Soldadura: índices únicos por posición.
    unicos, mapa = {}, []
    for vertice in vertices:
        if vertice not in unicos:
            unicos[vertice] = len(unicos)
        mapa.append(unicos[vertice])
    lista = [None] * len(unicos)
    for vertice, indice in unicos.items():
        lista[indice] = vertice
    return lista, [tuple(mapa[i] for i in t) for t in triangulos]


def medir(malla, etiqueta: str, espera_cerrada: bool = True):
    vertices, triangulos = leer(malla)
    hechos = oracle_malla_facts.hechos_solido(vertices, triangulos)["solido_malla"][0]
    log(f"{etiqueta}: {hechos['triangulos']} tris · volumen_orientado="
        f"{hechos['volumen_orientado']:.1f} · aristas_sueltas={hechos['aristas_sueltas']}")
    if espera_cerrada:
        exigir(hechos["aristas_sueltas"] == 0, f"{etiqueta} está cerrada")
        exigir(hechos["volumen_orientado"] > 0.0,
               f"{etiqueta} tiene sus caras hacia afuera (volumen orientado positivo)")
    return hechos


def main() -> None:
    log("=" * 70)

    # CONTROL 1 y 2: primitivas nativas. Fijan el signo sin teorizar sobre la convención.
    caja = mesh.box(size_x=200.0, size_y=140.0, size_z=90.0)
    if "error" in caja:
        log(f"FALLA caja: {caja['error']}")
        return
    medir(caja["mesh"], "control mesh_box")

    esfera = mesh.sphere(radius=120.0)
    if "error" in esfera:
        log(f"FALLA esfera: {esfera['error']}")
    else:
        medir(esfera["mesh"], "control mesh_sphere")

    # TRATAMIENTO: el camino real de «Muro sobre spline» — la cinta extruida a sólido.
    eje = curve.bezier(start_x=0.0, start_y=0.0, start_z=0.0,
                       end_x=900.0, end_y=0.0, end_z=0.0,
                       bend_x=0.0, bend_y=260.0, bend_z=0.0, segments=12)
    cinta = mesh.ribbon(eje["curve"], width=30.0, plane="xy")
    if "error" in cinta:
        log(f"FALLA cinta: {cinta['error']}")
        return
    muro = mesh.extrude(cinta["mesh"], distance=300.0,
                        direction_x=0.0, direction_y=0.0, direction_z=1.0)
    if "error" in muro:
        log(f"FALLA extrude: {muro['error']}")
        return
    medir(muro["mesh"], "tratamiento mesh_extrude (muro)")

    # Un sólido dado vuelta TIENE que salir rojo: sin esto, los verdes de arriba no prueban nada.
    vertices, triangulos = leer(caja["mesh"])
    invertidos = [(t[0], t[2], t[1]) for t in triangulos]
    control_malo = oracle_malla_facts.hechos_solido(vertices, invertidos)["solido_malla"][0]
    log(f"caja invertida a propósito: volumen_orientado={control_malo['volumen_orientado']:.1f}")
    exigir(control_malo["volumen_orientado"] < 0.0,
           "una caja invertida da volumen orientado NEGATIVO (la medida discrimina)")

    log("-" * 70)
    if FALLAS:
        log(f"JAM_MALLA_SOLIDOS_58 ROJO — {len(FALLAS)} falla(s)")
        for falla in FALLAS:
            log(f"  · {falla}")
    else:
        log("JAM_MALLA_SOLIDOS_58 TODO VERDE")


main()
