"""Diferencial del drop unitario contra `oracle_physics`.

    python tools/emitir_diferencial_physics.py
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

from jam import oracle_physics, oracle_physics_facts  # noqa: E402
from jam.geometry import AABB, Pieza, Vec3            # noqa: E402
import catalogos.escalares                            # noqa: F401,E402
from nucleo.diferencial import Procedencia           # noqa: E402
from nucleo.dominio import Dominio, generar          # noqa: E402
from nucleo.medida import cargar_catalogo            # noqa: E402
from nucleo.proyecto import (Proyecto, catalogos_a_cargar,  # noqa: E402
                             escalares_del_proyecto)


PROYECTO = Proyecto(RAIZ / "medidas")
DESTINO = PROYECTO.diferencial / "physics.json"
MEDIDAS = ("physics.tiene_suelo", "physics.apoyado")
DEFECTOS = ("sin_suelo", "flotando", "hundido")
PROCEDENCIA = Procedencia(
    raiz=RAIZ,
    emisor=("tools/emitir_diferencial_physics.py",
            "Content/Python/jam/oracle_physics_facts.py", "medidas/escalares.py"),
    referencia=("Content/Python/jam/oracle_physics.py", "Content/Python/jam/geometry.py"),
    desde_proyecto="..",
)


def _pieza(nombre: str, x: float, y: float, z: float, ex=25.0, ey=25.0, ez=25.0):
    centro = Vec3(x, y, z)
    return Pieza(nombre, AABB(centro, Vec3(ex, ey, ez)), centro, 0.0)


def montar(defecto: str | None, i: int = 0) -> dict:
    semilla = int.from_bytes(
        hashlib.sha256(f"{defecto or 'limpio'}\0{i}".encode()).digest()[:8], "big")
    rng = random.Random(semilla)
    x, y, z0 = (rng.uniform(-50000.0, 50000.0) for _ in range(3))
    soporte = _pieza("piso", x, y, z0, 200.0, 200.0, 50.0)
    top = z0 + 50.0
    gap = {None: 0.0, "flotando": 25.0, "hundido": -15.0}.get(defecto, 0.0)
    sujeto = _pieza("sujeto", x, y, top + 25.0 + gap)
    soportes = [
        _pieza("subsuelo", x, y, z0 - 200.0, 300.0, 300.0, 25.0),
        soporte,
    ]
    if defecto == "sin_suelo":
        soportes = [_pieza("piso_lejano", x + 1000.0, y, z0, 50.0, 50.0, 50.0)]
    return {"pieza": sujeto, "soportes": soportes}


def hechos(mundo: dict) -> dict:
    return oracle_physics_facts.hechos(mundo["pieza"], mundo["soportes"])


def referencia(mundo: dict) -> bool:
    return oracle_physics.es_ok(
        oracle_physics.verificar(mundo["pieza"], mundo["soportes"]))


PHYSICS = Dominio(
    nombre="physics", montar=montar, hechos=hechos, referencia=referencia,
    defectos=DEFECTOS, repeticiones=20,
    descripcion="Brianholl/jam · oracle_physics (implementación independiente)",
)


def main() -> int:
    with escalares_del_proyecto(PROYECTO, confiar=True):
        catalogo = cargar_catalogo(catalogos_a_cargar(PROYECTO))
        medidas = [catalogo[mid] for mid in MEDIDAS]
        fixture = generar(PHYSICS, medidas, procedencia=PROCEDENCIA)

    DESTINO.parent.mkdir(parents=True, exist_ok=True)
    DESTINO.write_text(
        json.dumps(fixture, ensure_ascii=False, indent=1, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8")
    print(f"{len(medidas)} medidas × {fixture['mundos']} escenarios · escrito: {DESTINO}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
