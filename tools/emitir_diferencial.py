"""Genera la prueba diferencial de geometría para el repo `oracle`.

    python tools/emitir_diferencial.py [--n 300]

Jam tiene los oráculos de colocación y snap escritos a mano, y son una **implementación
independiente**: no comparten una línea con el álgebra de `oracle`. Este script genera mundos, los
juzga con esos oráculos, y vuelca (evidencia, veredicto esperado) como DATOS.

Con eso `oracle` se verifica contra una implementación que no conoce, y sin ninguna dependencia en
tiempo de ejecución: la única cosa que viaja entre los repos es un archivo de hechos.

Además comprueba que el fixture tenga **las dos polaridades** para cada medida. Un diferencial de una
sola polaridad deja la medida floja — es la lección que dio el sensor de mutación: si ningún caso
espera verde, quitarle el filtro a la medida pasa inadvertido.
"""

from __future__ import annotations

import json
import random
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "Content" / "Python"))

from jam import oracle_placement, oracle_snap                      # noqa: E402
from jam.geometry import AABB, Pieza, Vec3                         # noqa: E402

DESTINO = RAIZ / "medidas" / "diferencial" / "geometria.json"


def _pieza(nombre, c, e, loc=None, yaw=0.0) -> Pieza:
    loc = loc or c
    return Pieza(nombre=nombre, aabb=AABB(Vec3(*c), Vec3(*e)), location=Vec3(*loc), yaw=yaw)


def _plano(p: Pieza) -> dict:
    """El hecho `pieza`, plano como manda L0: sin objetos ni anidamiento."""
    a, l = p.aabb, p.location
    return {"id": p.nombre,
            "ox": a.origin.x, "oy": a.origin.y, "oz": a.origin.z,
            "ex": a.extent.x, "ey": a.extent.y, "ez": a.extent.z,
            "lx": l.x, "ly": l.y, "lz": l.z, "yaw": p.yaw}


def _mundo(semilla: int) -> list[Pieza]:
    """Mezcla a propósito: posiciones en y fuera de grilla, yaw en y fuera de paso, volúmenes
    degenerados, y SIEMPRE una escenografía de fondo que envuelve todo."""
    r = random.Random(semilla)
    coord = lambda: r.choice([0.0, 100.0, 200.0, -100.0, 25.0, 100.5, 137.0])   # noqa: E731
    yaws = [0.0, 90.0, 180.0, 90.4, 92.0, 45.0]
    ext = lambda: r.choice([50.0, 25.0, 200.0, 0.0, 0.0001])                    # noqa: E731

    piezas = [_pieza(f"p{i}", (coord(), coord(), r.choice([0.0, 25.0, 100.0])),
                     (ext(), ext(), 50.0), yaw=r.choice(yaws))
              for i in range(r.randint(2, 5))]
    piezas.append(_pieza("SkySphere", (0.0, 0.0, 0.0), (60000.0, 60000.0, 60000.0)))
    return piezas


def generar(n: int) -> dict:
    grupos: dict[str, list[dict]] = {m: [] for m in
                                     ("colocacion.bounds", "colocacion.interpenetracion",
                                      "snap.grilla", "snap.yaw")}
    for semilla in range(n):
        mundo = _mundo(semilla)
        sujeto, otras = mundo[0], mundo[1:]

        col = oracle_placement.verificar(sujeto, otras)
        grupos["colocacion.bounds"].append(
            {"evidencia": {"pieza": [_plano(sujeto)]}, "esperado_ok": bool(col["bounds_ok"])})
        grupos["colocacion.interpenetracion"].append(
            {"evidencia": {"pieza": [_plano(sujeto)], "vecina": [_plano(o) for o in otras]},
             "esperado_ok": col["interpenetra"] == []})

        snap = oracle_snap.verificar_grilla(sujeto)
        grupos["snap.grilla"].append(
            {"evidencia": {"pieza": [_plano(sujeto)]},
             "esperado_ok": all(snap["ejes_ok"].values())})
        grupos["snap.yaw"].append(
            {"evidencia": {"pieza": [_plano(sujeto)]}, "esperado_ok": bool(snap["yaw_ok"])})

    return grupos


def main() -> int:
    n = 300
    if "--n" in sys.argv:
        n = int(sys.argv[sys.argv.index("--n") + 1])

    grupos = generar(n)
    problemas = []
    print(f"mundos generados: {n}\n")
    for medida, casos in sorted(grupos.items()):
        verdes = sum(1 for c in casos if c["esperado_ok"])
        rojos = len(casos) - verdes
        print(f"  {medida:<32} {verdes:>4} verdes · {rojos:>4} rojos")
        # las DOS polaridades o la medida queda floja (lección del sensor de mutación)
        if verdes < 10 or rojos < 10:
            problemas.append(f"{medida}: {verdes} verdes y {rojos} rojos — falta una polaridad")

    if problemas:
        print("\nNO SE ESCRIBE — el fixture no discriminaría:")
        for p in problemas:
            print("  ·", p)
        return 1

    DESTINO.parent.mkdir(parents=True, exist_ok=True)
    DESTINO.write_text(json.dumps(
        {"origen": "Brianholl/jam · oracle_placement + oracle_snap (implementación independiente)",
         "mundos": n, "grupos": grupos}, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"\nescrito: {DESTINO}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
