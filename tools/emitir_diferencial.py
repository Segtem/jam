"""El dominio `geometria` de Jam, declarado. Diferencial contra `oracle_placement` y `oracle_snap`.

    python tools/emitir_diferencial.py

Los oráculos de colocación y snap de Jam son una **implementación independiente**: no comparten una
línea con el álgebra de oracle. Acá se montan escenarios, se extraen sus hechos, y se contrasta.

Antes esto generaba 300 mundos al azar y confiaba en que la mezcla cubriera todo. Ahora los defectos
van **declarados** —uno por medida— con variación por repetición: apuntado en vez de a la escopeta, y
el `Dominio` se niega si alguna medida se queda sin una de sus dos polaridades.

Y lo que se fue, igual que en los otros dos arneses: la función que reimplementaba las medidas en
Python para saber qué debería dar cada una.
"""

from __future__ import annotations

import json
import random
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "Content" / "Python"))
sys.path.insert(0, str(RAIZ / "vendor" / "oracle"))

from jam import oracle_placement, oracle_snap        # noqa: E402
from jam.geometry import AABB, Pieza, Vec3           # noqa: E402
from nucleo.dominio import Dominio, generar          # noqa: E402
from nucleo.medida import cargar_catalogo            # noqa: E402
from nucleo.proyecto import (Proyecto, catalogos_a_cargar,  # noqa: E402
                             registrar_escalares)

PROYECTO = Proyecto(RAIZ / "medidas")
DESTINO = PROYECTO.diferencial / "geometria.json"

MEDIDAS = ("colocacion.bounds", "colocacion.interpenetracion", "snap.grilla", "snap.yaw")
DEFECTOS = ("volumen_degenerado", "interpenetracion", "fuera_de_grilla", "yaw_fuera_de_paso")


def _pieza(nombre, centro, extension, loc=None, yaw=0.0) -> Pieza:
    return Pieza(nombre=nombre, aabb=AABB(Vec3(*centro), Vec3(*extension)),
                 location=Vec3(*(loc or centro)), yaw=yaw)


def _plano(p: Pieza) -> dict:
    """El hecho `pieza`, plano como manda L0: sin objetos ni anidamiento."""
    a, l = p.aabb, p.location
    return {"id": p.nombre,
            "ox": a.origin.x, "oy": a.origin.y, "oz": a.origin.z,
            "ex": a.extent.x, "ey": a.extent.y, "ez": a.extent.z,
            "lx": l.x, "ly": l.y, "lz": l.z, "yaw": p.yaw}


def montar(defecto: str | None, i: int = 0) -> list[Pieza]:
    """Un mundo con el defecto declarado puesto, y el resto variado por la repetición.

    El sujeto es siempre la primera pieza. Y siempre hay una escenografía descomunal: sin ella, la
    regla que la ignora existe sin estar verificada — eso ya pasó una vez y lo delató la mutación.
    """
    r = random.Random(hash((defecto or "limpio", i)) & 0xFFFF)
    en_grilla = lambda: float(r.randrange(-3, 4) * 100)          # noqa: E731

    centro = [en_grilla(), en_grilla(), 0.0]
    extension = (50.0, 50.0, 50.0)
    yaw = float(r.choice([0, 90, 180, 270]))

    if defecto == "volumen_degenerado":
        extension = (0.0, 50.0, 50.0)
    elif defecto == "fuera_de_grilla":
        centro[0] += r.choice([1.5, 7.0, 37.0])
    elif defecto == "yaw_fuera_de_paso":
        yaw += r.choice([0.6, 2.0, 45.0])

    sujeto = _pieza("sujeto", tuple(centro), extension, yaw=yaw)
    vecinas = [_pieza(f"v{j}", (en_grilla() + 1000.0, en_grilla(), 0.0), (50.0, 50.0, 50.0))
               for j in range(r.randint(1, 3))]
    if defecto == "interpenetracion":
        vecinas.append(_pieza("clavada", (centro[0] + 20.0, centro[1], centro[2]),
                              (50.0, 50.0, 50.0)))
    vecinas.append(_pieza("SkySphere", (0.0, 0.0, 0.0), (60000.0, 60000.0, 60000.0)))
    return [sujeto, *vecinas]


def hechos(mundo: list[Pieza]) -> dict:
    return {"pieza": [_plano(mundo[0])], "vecina": [_plano(p) for p in mundo[1:]]}


def referencia(mundo: list[Pieza]) -> bool:
    """Los oráculos escritos a mano de Jam, corridos de verdad."""
    sujeto, otras = mundo[0], mundo[1:]
    col = oracle_placement.verificar(sujeto, otras)
    snap = oracle_snap.verificar_grilla(sujeto)
    return (bool(col["bounds_ok"]) and col["interpenetra"] == []
            and all(snap["ejes_ok"].values()) and bool(snap["yaw_ok"]))


GEOMETRIA = Dominio(
    nombre="geometria", montar=montar, hechos=hechos, referencia=referencia,
    defectos=DEFECTOS, repeticiones=50,
    descripcion="Brianholl/jam · oracle_placement + oracle_snap (implementación independiente)")


def main() -> int:
    registrar_escalares(PROYECTO)
    catalogo = cargar_catalogo(catalogos_a_cargar(PROYECTO))
    medidas = [catalogo[m] for m in MEDIDAS if m in catalogo]
    fixture = generar(GEOMETRIA, medidas)

    DESTINO.parent.mkdir(parents=True, exist_ok=True)
    DESTINO.write_text(json.dumps(fixture, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"{len(medidas)} medidas × {fixture['mundos']} escenarios · escrito: {DESTINO}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
