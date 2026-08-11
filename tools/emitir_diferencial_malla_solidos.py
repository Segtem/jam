"""Diferencial de los sólidos cerrados que Jam produce con `mesh_extrude` y las primitivas.

    python tools/emitir_diferencial_malla_solidos.py

Complementa `emitir_diferencial_malla.py`, que cubre superficies abiertas. Un sólido no se juzga por
el lado que muestra sino por si sus caras miran hacia AFUERA: invertidas, la pieza se ve como si uno
estuviera adentro. Es la versión en volumen del defecto que dejó invisible a «Borde de camino».

Los mundos son prismas construidos acá, en Python puro, porque el núcleo del extrude sólo configura:
la extrusión real la hace Geometry Script y no se puede generar sin motor. La contraparte con mallas
reales del motor es `tools/experiments/verifica_malla_solidos_58.py`, que aplica ESTAS medidas a un
`mesh_box`, una esfera y un extrude de verdad.
"""

from __future__ import annotations

import hashlib
import json
import math
import random
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "Content" / "Python"))
sys.path.insert(0, str(RAIZ / "vendor" / "oracle"))

from jam import oracle_malla_facts                 # noqa: E402
import catalogos.escalares                         # noqa: F401,E402
from nucleo.diferencial import Procedencia         # noqa: E402
from nucleo.dominio import Dominio, generar        # noqa: E402
from nucleo.medida import cargar_catalogo          # noqa: E402
from nucleo.proyecto import (Proyecto, catalogos_a_cargar,  # noqa: E402
                             escalares_del_proyecto)


PROYECTO = Proyecto(RAIZ / "medidas")
DESTINO = PROYECTO.diferencial / "malla_solidos.json"
MEDIDAS = ("malla.solido_hacia_afuera", "malla.solido_esta_cerrado")
DEFECTOS = ("solido_invertido", "una_cara_invertida", "tapa_faltante")
PROCEDENCIA = Procedencia(
    raiz=RAIZ,
    emisor=("tools/emitir_diferencial_malla_solidos.py",
            "Content/Python/jam/oracle_malla_facts.py", "medidas/escalares.py"),
    referencia=("Content/Python/jam/oracle_malla_facts.py",),
    desde_proyecto="..",
)


def _prisma(lados: int, radio: float, altura: float, rng: random.Random):
    """Prisma cerrado sobre un polígono convexo: base, tapa y laterales.

    La orientación NO se razona: se construye con una convención cualquiera, se mide el volumen y se
    invierte todo si salió del lado equivocado. Un error de signo mío no puede entrar al corpus
    disfrazado de mundo limpio.
    """
    # La planta varía por escala anisotrópica y no por radio suelto en cada vértice. Un radio
    # distinto por vértice produce polígonos ESTRELLADOS, y sobre un cóncavo no valen ni la
    # triangulación en abanico ni el atajo de la referencia: el primer intento así generó un
    # desacuerdo real entre sensor y referencia. Escalar los ejes conserva la convexidad.
    escala_x, escala_y = rng.uniform(0.6, 1.6), rng.uniform(0.6, 1.6)
    giro = rng.uniform(0.0, 2.0 * math.pi)
    base, tapa = [], []
    for i in range(lados):
        angulo = giro + 2.0 * math.pi * i / lados
        x, y = radio * escala_x * math.cos(angulo), radio * escala_y * math.sin(angulo)
        base.append((x, y, 0.0))
        tapa.append((x, y, altura))

    vertices = base + tapa
    triangulos = []
    # Las dos tapas recorren el polígono en sentidos OPUESTOS entre sí, y cada una en el sentido
    # contrario al del lateral que la toca: es lo que hace que toda arista compartida aparezca dos
    # veces y al revés. Con la base en el mismo sentido que los laterales el prisma queda abierto
    # aunque se vea entero — lo detectó `malla.solido_esta_cerrado` en este mismo generador.
    for i in range(1, lados - 1):                       # base, mirando hacia abajo
        triangulos.append((0, i + 1, i))
    for i in range(1, lados - 1):                       # tapa, mirando hacia arriba
        triangulos.append((lados, lados + i, lados + i + 1))
    for i in range(lados):                              # laterales
        j = (i + 1) % lados
        triangulos.append((i, j, lados + i))
        triangulos.append((j, lados + j, lados + i))

    volumen = oracle_malla_facts.hechos_solido(
        vertices, triangulos)["solido_malla"][0]["volumen_orientado"]
    if volumen < 0:
        triangulos = [(t[0], t[2], t[1]) for t in triangulos]
    return vertices, triangulos


def montar(defecto: str | None, i: int = 0) -> dict:
    semilla = int.from_bytes(
        hashlib.sha256(f"{defecto or 'limpio'}\0{i}".encode()).digest()[:8], "big")
    rng = random.Random(semilla)
    vertices, triangulos = _prisma(
        rng.randint(3, 9), rng.uniform(50.0, 600.0), rng.uniform(20.0, 900.0), rng)

    if defecto == "solido_invertido":
        # Todas las caras al revés: cerrado y coherente, pero mirando para adentro.
        triangulos = [(t[0], t[2], t[1]) for t in triangulos]
    elif defecto == "una_cara_invertida":
        j = len(triangulos) // 2
        t = triangulos[j]
        triangulos[j] = (t[0], t[2], t[1])
    elif defecto == "tapa_faltante":
        # Un agujero: el volumen con signo sigue dando un número, y sin la guarda de
        # `solido_esta_cerrado` ese número pasaría por veredicto.
        triangulos = triangulos[1:]

    return {"vertices": vertices, "triangulos": triangulos}


def hechos(mundo: dict) -> dict:
    return oracle_malla_facts.hechos_solido(mundo["vertices"], mundo["triangulos"])


def referencia(mundo: dict) -> bool:
    """Juicio INDEPENDIENTE: cara por cara contra el centro, sin volumen con signo.

    El sensor resuelve el sólido con un único número global. Acá se recorre cada triángulo y se
    comprueba que su normal se aleje del centro, más la condición de que cada arista tenga su par.
    Es el atajo que el sensor evita a propósito —falla en cóncavos—, y sirve como referencia porque
    todos los mundos de este corpus son prismas CONVEXOS —planta elíptica, sin radios sueltos— donde sí
    vale. Con polígonos estrellados esta referencia se equivoca, y el primer intento lo demostró.
    """
    vertices, triangulos = mundo["vertices"], mundo["triangulos"]
    centro = [sum(v[eje] for v in vertices) / len(vertices) for eje in range(3)]
    for triangulo in triangulos:
        normal = oracle_malla_facts.normal_de_cara(vertices, triangulo)
        if normal is None:
            return False
        medio = [sum(vertices[i][eje] for i in triangulo) / 3.0 for eje in range(3)]
        hacia_afuera = sum(normal[eje] * (medio[eje] - centro[eje]) for eje in range(3))
        if hacia_afuera <= 0.0:
            return False
    aristas = {}
    for triangulo in triangulos:
        for inicio, fin in zip(triangulo, triangulo[1:] + triangulo[:1]):
            aristas[(inicio, fin)] = aristas.get((inicio, fin), 0) + 1
    return all(aristas.get((fin, inicio), 0) == 1 for (inicio, fin) in aristas)


SOLIDOS = Dominio(
    nombre="malla_solidos", montar=montar, hechos=hechos, referencia=referencia,
    defectos=DEFECTOS, repeticiones=20,
    descripcion="Brianholl/jam · sólidos cerrados de mesh_extrude y primitivas",
)


def main() -> int:
    with escalares_del_proyecto(PROYECTO, confiar=True):
        catalogo = cargar_catalogo(catalogos_a_cargar(PROYECTO))
        medidas = [catalogo[mid] for mid in MEDIDAS]
        fixture = generar(SOLIDOS, medidas, procedencia=PROCEDENCIA)

    DESTINO.parent.mkdir(parents=True, exist_ok=True)
    DESTINO.write_text(
        json.dumps(fixture, ensure_ascii=False, indent=1, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8")
    print(f"{len(medidas)} medidas × {fixture['mundos']} escenarios · escrito: {DESTINO}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
