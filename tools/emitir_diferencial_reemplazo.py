"""Diferencial de reemplazo contra ``oracle_reemplazo``.

    python tools/emitir_diferencial_reemplazo.py
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

from jam import oracle_reemplazo, oracle_reemplazo_facts  # noqa: E402
from jam.geometry import AABB, Pieza, Vec3                # noqa: E402
import catalogos.escalares                               # noqa: F401,E402
from nucleo.diferencial import Procedencia               # noqa: E402
from nucleo.dominio import Dominio, generar              # noqa: E402
from nucleo.medida import cargar_catalogo                # noqa: E402
from nucleo.proyecto import (Proyecto, catalogos_a_cargar,  # noqa: E402
                             escalares_del_proyecto)


PROYECTO = Proyecto(RAIZ / "medidas")
DESTINO = PROYECTO.diferencial / "reemplazo.json"
MEDIDAS = ("reemplazo.centrado", "reemplazo.apoyado", "reemplazo.footprint")
DEFECTOS = ("descentrado", "base", "footprint")
PROCEDENCIA = Procedencia(
    raiz=RAIZ,
    emisor=("tools/emitir_diferencial_reemplazo.py",
            "Content/Python/jam/oracle_reemplazo_facts.py", "medidas/escalares.py"),
    referencia=("Content/Python/jam/oracle_reemplazo.py",),
    desde_proyecto="..",
)


def montar(defecto: str | None, i: int = 0) -> dict:
    semilla = int.from_bytes(
        hashlib.sha256(f"{defecto or 'limpio'}\0{i}".encode()).digest()[:8], "big")
    rng = random.Random(semilla)
    cx, cy, base = (rng.uniform(-50000.0, 50000.0) for _ in range(3))
    ex, ey, ez = (rng.uniform(25.0, 500.0) for _ in range(3))
    dx = dy = dz = dfx = dfy = 0.0
    if defecto == "descentrado":
        if i % 2:
            dy = rng.choice((-1.0, 1.0)) * 10.0
        else:
            dx = rng.choice((-1.0, 1.0)) * 10.0
    elif defecto == "base":
        dz = rng.choice((-1.0, 1.0)) * 10.0
    elif defecto == "footprint":
        if i % 2:
            dfy = rng.choice((-1.0, 1.0)) * 10.0
        else:
            dfx = rng.choice((-1.0, 1.0)) * 10.0

    origen = Vec3(cx + dx, cy + dy, base + ez + dz)
    extension = Vec3(ex + dfx, ey + dfy, ez)
    pieza = Pieza("reemplazo", AABB(origen, extension), origen, 0.0)
    objetivo = {"cx": cx, "cy": cy, "base": base, "ex": ex, "ey": ey, "ez": ez}
    return {"pieza": pieza, "objetivo": objetivo}


def hechos(mundo: dict) -> dict:
    return oracle_reemplazo_facts.hechos(mundo["pieza"], mundo["objetivo"])


def referencia(mundo: dict) -> bool:
    return oracle_reemplazo.es_ok(
        oracle_reemplazo.verificar(mundo["pieza"], mundo["objetivo"]))


REEMPLAZO = Dominio(
    nombre="reemplazo", montar=montar, hechos=hechos, referencia=referencia,
    defectos=DEFECTOS, repeticiones=20,
    descripcion="Brianholl/jam · oracle_reemplazo (implementación independiente)",
)


def main() -> int:
    with escalares_del_proyecto(PROYECTO, confiar=True):
        catalogo = cargar_catalogo(catalogos_a_cargar(PROYECTO))
        medidas = [catalogo[mid] for mid in MEDIDAS]
        fixture = generar(REEMPLAZO, medidas, procedencia=PROCEDENCIA)

    DESTINO.parent.mkdir(parents=True, exist_ok=True)
    DESTINO.write_text(
        json.dumps(fixture, ensure_ascii=False, indent=1, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8")
    print(f"{len(medidas)} medidas × {fixture['mundos']} escenarios · escrito: {DESTINO}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
