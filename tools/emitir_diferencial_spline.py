"""Diferencial del spline modular que usa el Graph contra `spline_core`.

    python tools/emitir_diferencial_spline.py
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

from jam import oracle_spline_facts, spline_core  # noqa: E402
from jam.geometry import Vec3                     # noqa: E402
import catalogos.escalares                        # noqa: F401,E402
from nucleo.diferencial import Procedencia        # noqa: E402
from nucleo.dominio import Dominio, generar       # noqa: E402
from nucleo.medida import cargar_catalogo         # noqa: E402
from nucleo.proyecto import (Proyecto, catalogos_a_cargar,  # noqa: E402
                             escalares_del_proyecto)


PROYECTO = Proyecto(RAIZ / "medidas")
DESTINO = PROYECTO.diferencial / "spline.json"
MEDIDAS = ("spline.cobertura", "spline.sin_solape")
DEFECTOS = ("cobertura_baja", "solape")
PROCEDENCIA = Procedencia(
    raiz=RAIZ,
    emisor=("tools/emitir_diferencial_spline.py",
            "Content/Python/jam/oracle_spline_facts.py", "medidas/escalares.py"),
    referencia=("Content/Python/jam/spline_core.py",),
    desde_proyecto="..",
)


def montar(defecto: str | None, i: int = 0) -> dict:
    semilla = int.from_bytes(
        hashlib.sha256(f"{defecto or 'limpio'}\0{i}".encode()).digest()[:8], "big")
    rng = random.Random(semilla)
    largo = rng.uniform(700.0, 1700.0)
    modulo = largo / 5.0
    cantidad = 4 if defecto == "cobertura_baja" else 5
    colocaciones = [
        spline_core.Colocacion(
            Vec3((j + 0.5) * modulo, rng.uniform(-1000.0, 1000.0), 0.0),
            rng.uniform(-180.0, 180.0), modulo, 0, (j + 0.5) * modulo, j)
        for j in range(cantidad)
    ]
    if defecto == "solape":
        c = colocaciones[2]
        colocaciones[2] = c._replace(s=c.s - 2.0)
    return {"colocaciones": colocaciones, "largo_curva": largo}


def hechos(mundo: dict) -> dict:
    return oracle_spline_facts.hechos(mundo["colocaciones"], mundo["largo_curva"])


def referencia(mundo: dict) -> bool:
    r = spline_core.verificar_continuidad(
        mundo["colocaciones"], mundo["largo_curva"])
    return bool(r["sin_solape"] and r["cobertura_ok"])


SPLINE = Dominio(
    nombre="spline", montar=montar, hechos=hechos, referencia=referencia,
    defectos=DEFECTOS, repeticiones=20,
    descripcion="Brianholl/jam · spline_core.verificar_continuidad",
)


def main() -> int:
    with escalares_del_proyecto(PROYECTO, confiar=True):
        catalogo = cargar_catalogo(catalogos_a_cargar(PROYECTO))
        medidas = [catalogo[mid] for mid in MEDIDAS]
        fixture = generar(SPLINE, medidas, procedencia=PROCEDENCIA)

    DESTINO.parent.mkdir(parents=True, exist_ok=True)
    DESTINO.write_text(
        json.dumps(fixture, ensure_ascii=False, indent=1, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8")
    print(f"{len(medidas)} medidas × {fixture['mundos']} escenarios · escrito: {DESTINO}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
