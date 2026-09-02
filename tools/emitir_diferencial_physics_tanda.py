"""Diferencial del juicio de ``drop(points)`` contra ``oracle_physics_tanda``.

    python tools/emitir_diferencial_physics_tanda.py
"""

from __future__ import annotations

import hashlib
import json
import random
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "Content" / "Python"))
sys.path.insert(0, str(RAIZ / "vendor" / "oracle-pkg"))

# Oracle viene del wheel de PyPI: los nombres internos (`nucleo`, `catalogos`) sólo
# existen después de importar la fachada, que es la que los registra.
import oracle_metalenguaje  # noqa: F401,E402

from jam import (oracle_physics_tanda, oracle_physics_tanda_facts,  # noqa: E402
                 physics_core)
from jam.geometry import AABB, Pieza, Vec3                         # noqa: E402
import catalogos.escalares                                        # noqa: F401,E402
from nucleo.diferencial import Procedencia                        # noqa: E402
from nucleo.dominio import Dominio, generar                       # noqa: E402
from nucleo.medida import cargar_catalogo                         # noqa: E402
from nucleo.proyecto import (Proyecto, catalogos_a_cargar,        # noqa: E402
                             escalares_del_proyecto)


PROYECTO = Proyecto(RAIZ / "medidas")
DESTINO = PROYECTO.diferencial / "physics_tanda.json"
MEDIDAS = ("physics.tanda_completa", "physics.tanda_sin_interpenetracion")
DEFECTOS = ("sin_suelo", "parcial", "interpenetracion")
PROCEDENCIA = Procedencia(
    raiz=RAIZ,
    emisor=("tools/emitir_diferencial_physics_tanda.py",
            "Content/Python/jam/oracle_physics_tanda_facts.py",
            "Content/Python/jam/physics_core.py", "medidas/escalares.py"),
    referencia=("Content/Python/jam/oracle_physics_tanda.py",
                "Content/Python/jam/geometry.py"),
    desde_proyecto="..",
)


def _pieza(nombre: str, x: float, y: float, z: float,
           ex=25.0, ey=25.0, ez=25.0) -> Pieza:
    centro = Vec3(x, y, z)
    return Pieza(nombre, AABB(centro, Vec3(ex, ey, ez)), centro, 0.0)


def montar(defecto: str | None, i: int = 0):
    semilla = int.from_bytes(
        hashlib.sha256(f"{defecto or 'limpio'}\0{i}".encode()).digest()[:8], "big")
    rng = random.Random(semilla)
    x, y, z0 = (rng.uniform(-50000.0, 50000.0) for _ in range(3))
    piso = _pieza("piso", x, y, z0 - 25.0, 250.0, 250.0, 25.0)

    if defecto == "sin_suelo":
        piezas = [_pieza(f"p{j}", x + 1000.0 * j, y, z0 + 500.0) for j in range(3)]
        return physics_core.asentar_tanda(piezas, [])
    if defecto == "parcial":
        piezas = [_pieza("con_piso", x, y, z0 + 500.0),
                  _pieza("sin_piso", x + 1000.0, y, z0 + 500.0)]
        return physics_core.asentar_tanda(piezas, [piso])

    piezas = [_pieza(f"p{j}", x, y, z0 + 500.0 + j * 100.0) for j in range(3)]
    resultados = physics_core.asentar_tanda(piezas, [piso])
    if defecto == "interpenetracion":
        resultados[1] = resultados[1] | {
            "pieza": physics_core.bajar(resultados[1]["pieza"], 20.0),
        }
    return resultados


def hechos(resultados: list[dict]) -> dict:
    return oracle_physics_tanda_facts.hechos(resultados)


def referencia(resultados: list[dict]) -> bool:
    return oracle_physics_tanda.es_ok(oracle_physics_tanda.verificar(resultados))


PHYSICS_TANDA = Dominio(
    nombre="physics_tanda", montar=montar, hechos=hechos, referencia=referencia,
    defectos=DEFECTOS, repeticiones=20,
    descripcion="Brianholl/jam · oracle_physics_tanda (implementación independiente)",
)


def main() -> int:
    with escalares_del_proyecto(PROYECTO, confiar=True):
        catalogo = cargar_catalogo(catalogos_a_cargar(PROYECTO))
        medidas = [catalogo[mid] for mid in MEDIDAS]
        fixture = generar(PHYSICS_TANDA, medidas, procedencia=PROCEDENCIA)

    DESTINO.parent.mkdir(parents=True, exist_ok=True)
    DESTINO.write_text(
        json.dumps(fixture, ensure_ascii=False, indent=1, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8")
    print(f"{len(medidas)} medidas × {fixture['mundos']} escenarios · escrito: {DESTINO}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
