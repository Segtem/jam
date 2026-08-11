"""Diferencial de la cara visible de las mallas que Jam genera con buffers propios.

    python tools/emitir_diferencial_malla.py

Nace del defecto medido el 2026-08-10: `mesh_ribbon` le entregaba a Unreal el winding invertido, así
que «Borde de camino» era invisible desde arriba y «Muro sobre spline» aparecía dado vuelta, con 790
tests en verde. Las medidas de `spline` declaraban no ver «visibilidad» ni «triángulos»; el defecto
cayó justo en ese hueco.

Las dos polaridades del corpus son reales, no inventadas: en UE 5.8.1 el defecto dio 48/48 caras
hacia -Z y el arreglo 48/48 hacia +Z, con un `mesh_box` nativo como control en ambas corridas.
"""

from __future__ import annotations

import hashlib
import math
import json
import random
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "Content" / "Python"))
sys.path.insert(0, str(RAIZ / "vendor" / "oracle"))

from jam import oracle_malla_facts, ribbon_core    # noqa: E402
import catalogos.escalares                         # noqa: F401,E402
from nucleo.diferencial import Procedencia         # noqa: E402
from nucleo.dominio import Dominio, generar        # noqa: E402
from nucleo.medida import cargar_catalogo          # noqa: E402
from nucleo.proyecto import (Proyecto, catalogos_a_cargar,  # noqa: E402
                             escalares_del_proyecto)


PROYECTO = Proyecto(RAIZ / "medidas")
DESTINO = PROYECTO.diferencial / "malla.json"
MEDIDAS = ("malla.cara_visible", "malla.superficie_sin_vueltas")
DEFECTOS = ("winding_invertido", "normales_invertidas", "una_cara_dada_vuelta",
            "curva_mas_cerrada_que_el_ancho")
PROCEDENCIA = Procedencia(
    raiz=RAIZ,
    emisor=("tools/emitir_diferencial_malla.py",
            "Content/Python/jam/oracle_malla_facts.py", "medidas/escalares.py"),
    referencia=("Content/Python/jam/ribbon_core.py",),
    desde_proyecto="..",
)


def montar(defecto: str | None, i: int = 0) -> dict:
    """Una cinta real de `ribbon_core`, y encima el defecto que corresponda.

    Todos los mundos viven en el plano XY porque es donde el defecto se vio y donde la referencia
    puede juzgar contra un eje conocido sin repetir la cuenta del sensor.
    """
    semilla = int.from_bytes(
        hashlib.sha256(f"{defecto or 'limpio'}\0{i}".encode()).digest()[:8], "big")
    rng = random.Random(semilla)

    # Recorridos variados: rectos, curvados hacia cualquier lado y con pendiente en Z. La cinta sigue
    # siendo horizontal en su conjunto, pero sus caras dejan de ser todas exactamente (0,0,1).
    #
    # El giro por paso va ACOTADO y el ancho queda por debajo del paso a propósito. Sin ese límite,
    # una cinta sin ningún defecto inyectado ya sale con caras dadas vuelta: cuando el recorrido
    # dobla más cerrado que su propio ancho, los bordes se cruzan y el cuadrilátero entre dos
    # muestras se pliega. Cuatro de veinte mundos «limpios» caían ahí en la primera tirada. Ese caso
    # no se esconde: es el defecto `curva_mas_cerrada_que_el_ancho`, acá abajo.
    cantidad = rng.randint(2, 6)
    paso_min = 200.0
    ancho = rng.uniform(60.0, paso_min * 0.7)
    cerrada = defecto == "curva_mas_cerrada_que_el_ancho"
    if cerrada:
        # Giro brusco y cinta ancha: exactamente la combinación que pliega el offset.
        ancho = rng.uniform(400.0, 900.0)
    giro_max = math.radians(140.0 if cerrada else 22.0)

    rumbo = 0.0
    puntos = [(0.0, 0.0, 0.0)]
    for _ in range(1, cantidad):
        rumbo += rng.uniform(-giro_max, giro_max)
        largo = rng.uniform(paso_min, 500.0)
        anterior = puntos[-1]
        puntos.append((
            anterior[0] + largo * math.cos(rumbo),
            anterior[1] + largo * math.sin(rumbo),
            anterior[2] + rng.uniform(-30.0, 30.0),
        ))
    construido = ribbon_core.ribbon_buffers(
        puntos, width=ancho, plane="xy",
        join="miter", miter_limit=rng.uniform(1.5, 4.0))
    if "error" in construido:
        # Un recorrido que el núcleo rechaza no es un mundo: se reemplaza por una recta segura en vez
        # de emitir un escenario vacío que ninguna medida podría juzgar.
        construido = ribbon_core.ribbon_buffers(
            ((0.0, 0.0, 0.0), (500.0, 0.0, 0.0)), width=200.0, plane="xy")

    vertices = list(construido["vertices"])
    triangulos = [tuple(t) for t in construido["triangles"]]
    normales = list(construido["normals"])

    if defecto == "winding_invertido":
        # El defecto EXACTO del 2026-08-10: se da vuelta el orden de los índices y las normales de
        # sombreado quedan como estaban.
        triangulos = [(t[0], t[2], t[1]) for t in triangulos]
    elif defecto == "normales_invertidas":
        # El espejo: el motor dibuja la cara correcta pero la ilumina desde el lado contrario.
        normales = [(-n[0], -n[1], -n[2]) for n in normales]
    elif defecto == "una_cara_dada_vuelta":
        # Un solo triángulo al revés en el medio: el promedio de la superficie sigue mirando bien.
        j = len(triangulos) // 2
        t = triangulos[j]
        triangulos[j] = (t[0], t[2], t[1])

    return {"vertices": vertices, "triangulos": triangulos, "normales": normales}


def hechos(mundo: dict) -> dict:
    return oracle_malla_facts.hechos(
        mundo["vertices"], mundo["triangulos"], mundo["normales"])


def referencia(mundo: dict) -> bool:
    """Juicio INDEPENDIENTE: cada lado contra el eje conocido del mundo, no uno contra el otro.

    El sensor compara la cara con la normal de sombreado de sus propios vértices. Acá se comprueba
    por separado que ambas miren hacia arriba, que es lo que un humano espera de una cinta apoyada
    en el plano XY. Dos caminos distintos para el mismo veredicto.
    """
    vertices, triangulos, normales = (
        mundo["vertices"], mundo["triangulos"], mundo["normales"])
    for triangulo in triangulos:
        cara = oracle_malla_facts.normal_de_cara(vertices, triangulo)
        if cara is None or cara[2] <= 0.0:
            return False
    return all(normal[2] > 0.0 for normal in normales)


MALLA = Dominio(
    nombre="malla", montar=montar, hechos=hechos, referencia=referencia,
    defectos=DEFECTOS, repeticiones=20,
    descripcion="Brianholl/jam · cara visible de ribbon_core en UE 5.8.1",
)


def main() -> int:
    with escalares_del_proyecto(PROYECTO, confiar=True):
        catalogo = cargar_catalogo(catalogos_a_cargar(PROYECTO))
        medidas = [catalogo[mid] for mid in MEDIDAS]
        fixture = generar(MALLA, medidas, procedencia=PROCEDENCIA)

    DESTINO.parent.mkdir(parents=True, exist_ok=True)
    DESTINO.write_text(
        json.dumps(fixture, ensure_ascii=False, indent=1, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8")
    print(f"{len(medidas)} medidas × {fixture['mundos']} escenarios · escrito: {DESTINO}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
