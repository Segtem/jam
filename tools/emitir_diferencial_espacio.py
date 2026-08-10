"""Diferencial del espacio vivo contra el solver histórico de JamSpace.

    python tools/emitir_diferencial_espacio.py
"""

from __future__ import annotations

import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "Content" / "Python"))
sys.path.insert(0, str(RAIZ / "vendor" / "oracle"))

from jam import bridge, oracle_espacio, oracle_espacio_facts  # noqa: E402
import catalogos.escalares                                   # noqa: F401,E402
from nucleo.diferencial import Procedencia                   # noqa: E402
from nucleo.dominio import Dominio, generar                  # noqa: E402
from nucleo.medida import cargar_catalogo                    # noqa: E402
from nucleo.proyecto import (Proyecto, catalogos_a_cargar,   # noqa: E402
                             escalares_del_proyecto)

bridge.ensure_oraculo_on_path()

from oraculo.mazes.spacegraph import GraphEdge, GraphNode, SpaceGraph  # noqa: E402


PROYECTO = Proyecto(RAIZ / "medidas")
DESTINO = PROYECTO.diferencial / "espacio.json"
MEDIDAS = ("espacio.inicio_unico", "espacio.meta_unica", "espacio.ganable")
DEFECTOS = ("sin_inicio", "sin_meta", "llave_inalcanzable", "puerta_sin_llave")
PROCEDENCIA = Procedencia(
    raiz=RAIZ,
    emisor=("tools/emitir_diferencial_espacio.py",
            "Content/Python/jam/oracle_espacio_facts.py", "medidas/escalares.py"),
    referencia=("Content/Python/jam/oracle_espacio.py", "oraculo/mazes/spacegraph.py"),
    desde_proyecto="..",
)


def montar(defecto: str | None, i: int = 0) -> SpaceGraph:
    sufijo = f"_{i}"
    ids = {nombre: nombre + sufijo for nombre in ("entrada", "pista", "galeria", "cripta", "meta")}
    nodos = {
        ids["entrada"]: GraphNode(ids["entrada"], start=defecto != "sin_inicio"),
        ids["pista"]: GraphNode(
            ids["pista"], key=None if defecto == "puerta_sin_llave" else "sello"),
        ids["galeria"]: GraphNode(ids["galeria"]),
        ids["cripta"]: GraphNode(ids["cripta"]),
        ids["meta"]: GraphNode(ids["meta"], goal=defecto != "sin_meta"),
    }
    aristas = [
        GraphEdge(ids["entrada"], ids["galeria"]),
        GraphEdge(ids["galeria"], ids["cripta"]),
        GraphEdge(ids["cripta"], ids["meta"], door_id="sello"),
    ]
    if defecto != "llave_inalcanzable":
        aristas.append(GraphEdge(ids["entrada"], ids["pista"]))
    return SpaceGraph(nodes=nodos, edges=aristas, space="extraction", seed=i)


def hechos(graph: SpaceGraph) -> dict:
    return oracle_espacio_facts.hechos(graph)


def referencia(graph: SpaceGraph) -> bool:
    return bool(oracle_espacio.veredicto(graph)["solvable"])


ESPACIO = Dominio(
    nombre="espacio", montar=montar, hechos=hechos, referencia=referencia,
    defectos=DEFECTOS, repeticiones=20,
    descripcion="Brianholl/jam · solve_graph histórico (implementación independiente)",
)


def main() -> int:
    with escalares_del_proyecto(PROYECTO, confiar=True):
        catalogo = cargar_catalogo(catalogos_a_cargar(PROYECTO))
        medidas = [catalogo[mid] for mid in MEDIDAS]
        fixture = generar(ESPACIO, medidas, procedencia=PROCEDENCIA)
    DESTINO.parent.mkdir(parents=True, exist_ok=True)
    import json
    DESTINO.write_text(
        json.dumps(fixture, ensure_ascii=False, indent=1, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8")
    print(f"{len(medidas)} medidas × {fixture['mundos']} escenarios · escrito: {DESTINO}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
