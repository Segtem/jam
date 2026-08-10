"""Dominio `scatter`: diferencial contra el oráculo operativo escrito a mano de Jam.

    python tools/emitir_diferencial_scatter.py

Cada defecto se monta aislado. El sensor sólo emite piezas, configuración, conteo y ocupación de
celdas; decidir si esos hechos son aceptables queda en las medidas declarativas.
"""

from __future__ import annotations

import hashlib
import json
import random
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "Content" / "Python"))
sys.path.insert(0, str(RAIZ / "vendor" / "oracle"))

from jam import oracle_scatter, oracle_scatter_facts  # noqa: E402
from jam.geometry import AABB, Pieza, Vec3        # noqa: E402
import catalogos.escalares                        # noqa: F401,E402
from nucleo.diferencial import Procedencia        # noqa: E402
from nucleo.dominio import Dominio, generar       # noqa: E402
from nucleo.medida import cargar_catalogo         # noqa: E402
from nucleo.proyecto import (Proyecto, catalogos_a_cargar,  # noqa: E402
                             escalares_del_proyecto)


PROYECTO = Proyecto(RAIZ / "medidas")
DESTINO = PROYECTO.diferencial / "scatter.json"
MEDIDAS = (
    "scatter.cantidad",
    "scatter.contencion",
    "scatter.interpenetracion",
    "scatter.cobertura",
)
DEFECTOS = ("cantidad_faltante", "fuera_de_region", "interpenetracion", "cobertura_baja")
PROCEDENCIA = Procedencia(
    raiz=RAIZ,
    emisor=("tools/emitir_diferencial_scatter.py", "Content/Python/jam/geometry.py",
            "Content/Python/jam/oracle_scatter_facts.py", "medidas/escalares.py"),
    referencia=("Content/Python/jam/oracle_scatter.py",),
    desde_proyecto="..",
)


def _pieza(nombre: str, x: float, y: float) -> Pieza:
    centro = Vec3(float(x), float(y), 0.0)
    return Pieza(nombre, AABB(centro, Vec3(25.0, 25.0, 25.0)), centro, 0.0)


def _posiciones_sanas(cx: float, cy: float, rng: random.Random) -> list[tuple[float, float]]:
    return [
        (cx + x + rng.uniform(-25.0, 25.0), cy + y + rng.uniform(-25.0, 25.0))
        for y in (-300.0, 0.0, 300.0)
        for x in (-300.0, 0.0, 300.0)
    ]


def _posiciones_amontonadas(cx: float, cy: float, rng: random.Random) -> list[tuple[float, float]]:
    # Nueve piezas separadas, pero sólo cinco de nueve celdas ocupadas.
    celdas = ((-300.0, -300.0), (0.0, -300.0), (300.0, -300.0),
              (-300.0, 0.0), (0.0, 0.0))
    posiciones = []
    for index in range(9):
        x, y = celdas[index % len(celdas)]
        repeticion = index // len(celdas)
        desplazamiento = -45.0 if repeticion == 0 else 45.0
        posiciones.append((cx + x + desplazamiento + rng.uniform(-3.0, 3.0),
                           cy + y + rng.uniform(-3.0, 3.0)))
    return posiciones


def montar(defecto: str | None, i: int = 0) -> dict:
    semilla = int.from_bytes(
        hashlib.sha256(f"{defecto or 'limpio'}\0{i}".encode()).digest()[:8], "big")
    rng = random.Random(semilla)
    cx = float(rng.randrange(-20, 21) * 1000)
    cy = float(rng.randrange(-20, 21) * 1000)
    semi = (450.0, 450.0)
    posiciones = _posiciones_sanas(cx, cy, rng)

    if defecto == "cantidad_faltante":
        posiciones.pop()
    elif defecto == "fuera_de_region":
        posiciones[0] = (cx + semi[0] + 10.0, posiciones[0][1])
    elif defecto == "interpenetracion":
        posiciones[-1] = posiciones[0]
    elif defecto == "cobertura_baja":
        posiciones = _posiciones_amontonadas(cx, cy, rng)

    return {
        "piezas": [_pieza(f"i{index:02d}", x, y) for index, (x, y) in enumerate(posiciones)],
        "centro": (cx, cy),
        "semi": semi,
        "pedidas": 9,
        "grilla": 3,
        "cobertura_min": 0.6,
    }


def hechos(mundo: dict) -> dict:
    return oracle_scatter_facts.hechos(
        mundo["piezas"], mundo["centro"], mundo["semi"], mundo["pedidas"],
        grilla=mundo["grilla"])


def referencia(mundo: dict) -> bool:
    resultado = oracle_scatter.verificar(
        mundo["piezas"], mundo["centro"], mundo["semi"], mundo["pedidas"],
        grilla=mundo["grilla"], cobertura_min=mundo["cobertura_min"])
    return oracle_scatter.es_ok(resultado)


SCATTER = Dominio(
    nombre="scatter", montar=montar, hechos=hechos, referencia=referencia,
    defectos=DEFECTOS, repeticiones=20,
    descripcion="Brianholl/jam · oracle_scatter (implementación independiente)",
)


def main() -> int:
    with escalares_del_proyecto(PROYECTO, confiar=True):
        catalogo = cargar_catalogo(catalogos_a_cargar(PROYECTO))
        medidas = [catalogo[mid] for mid in MEDIDAS]
        fixture = generar(SCATTER, medidas, procedencia=PROCEDENCIA)

    DESTINO.parent.mkdir(parents=True, exist_ok=True)
    DESTINO.write_text(
        json.dumps(fixture, ensure_ascii=False, indent=1, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8")
    print(f"{len(medidas)} medidas × {fixture['mundos']} escenarios · escrito: {DESTINO}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
