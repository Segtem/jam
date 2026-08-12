"""Clasificar las caras rojas de `mesh_ribbon` por su GEOMETRÍA.

    python tools/clasifica_caras_rojas_ribbon.py

Existe porque la hipótesis que estaba escrita en `ribbon_core._sin_pliegues` —«degeneración por
avance despreciable»— se midió con esta sonda y resultó falsa: ninguna de las 9 caras rojas es
degenerada (la más chica tiene 3.203 cm²) y 3 de ellas son bevels, donde angostar es una homotecia
sobre el vértice y no puede cambiar el signo de la normal.

Contar cuántos mundos quedan en rojo no alcanza para elegir un remedio: hay que mirar QUÉ tienen
adentro. Un número que baja puede estar bajando por otra cosa.

La hipótesis escrita en `ribbon_core` era una sola: «avance despreciable». Los números dicen que hay
más de un caso. Acá cada cara roja se describe por lo que se puede medir del triángulo mismo:
su ÁREA, el avance del eje entre las dos muestras y el avance de cada borde.

Un triángulo de área cero no tiene orientación: su normal la decide el redondeo. Esa es una
categoría distinta de «se plegó», y no se arregla con el mismo remedio.
"""
import math
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "Content" / "Python"))

from jam import oracle_malla_facts  # noqa: E402

import importlib.util  # noqa: E402
spec = importlib.util.spec_from_file_location("emisor", RAIZ / "tools" / "emitir_diferencial_malla.py")
emisor = importlib.util.module_from_spec(spec)
spec.loader.exec_module(emisor)


def area(vertices, tri):
    a, b, c = (vertices[i] for i in tri)
    u = [b[k] - a[k] for k in range(3)]
    v = [c[k] - a[k] for k in range(3)]
    n = [u[1] * v[2] - u[2] * v[1], u[2] * v[0] - u[0] * v[2], u[0] * v[1] - u[1] * v[0]]
    return 0.5 * math.sqrt(sum(x * x for x in n))


def lado(a, b):
    return math.sqrt(sum((b[k] - a[k]) ** 2 for k in range(3)))


print(" mundo cara   acuerdo   área(cm²)   lado_min   largo_eje   av_izq   av_der")
print("-" * 82)
casos = {"bevel (el eje no avanza)": 0, "avance desparejo entre bordes": 0, "otro": 0}
for i in range(20):
    mundo = emisor.montar("curva_mas_cerrada_que_el_ancho", i)
    vertices, triangulos = mundo["vertices"], mundo["triangulos"]
    caras = oracle_malla_facts.hechos(vertices, triangulos, mundo["normales"])["cara_malla"]
    for idx, (tri, cara) in enumerate(zip(triangulos, caras)):
        if float(cara["acuerdo"]) > 0.0:
            continue
        muestra = min(tri) // 2
        if (muestra + 1) * 2 + 1 >= len(vertices):
            continue
        izq_a, der_a = vertices[muestra * 2], vertices[muestra * 2 + 1]
        izq_b, der_b = vertices[(muestra + 1) * 2], vertices[(muestra + 1) * 2 + 1]
        eje_a = tuple((izq_a[k] + der_a[k]) / 2 for k in range(3))
        eje_b = tuple((izq_b[k] + der_b[k]) / 2 for k in range(3))
        largo_eje = lado(eje_a, eje_b)
        a = area(vertices, tri)
        lados = [lado(vertices[tri[0]], vertices[tri[1]]),
                 lado(vertices[tri[1]], vertices[tri[2]]),
                 lado(vertices[tri[2]], vertices[tri[0]])]
        av_i, av_d = lado(izq_a, izq_b), lado(der_a, der_b)
        print(f" {i:>5} {idx:>4}   {float(cara['acuerdo']):+7.3f} {a:>11.3f} {min(lados):>10.3f} "
              f"{largo_eje:>11.3f} {av_i:>8.2f} {av_d:>8.2f}")
        # Las categorías salen de los datos, no de la hipótesis: la primera versión de esta sonda
        # buscaba «área ~0» y «avance chico» y mandaba las 9 caras a «otro», que es la forma en que
        # una clasificación avisa que estaba mirando lo que no era.
        if largo_eje < 1e-6:
            casos["bevel (el eje no avanza)"] += 1
        elif min(av_i, av_d) < 0.6 * largo_eje:
            casos["avance desparejo entre bordes"] += 1
        else:
            casos["otro"] += 1

print()
print("  reparto:", casos)
