"""Adaptador puro de Jam a Oracle para ejecutar medidas sin gobernar todavía el resultado.

Jam conserva los oráculos escritos a mano como referencia operativa. Esta sombra aplana `Pieza` a
hechos L0, evalúa el proyecto `medidas/` mediante la fachada pública `Motor` y explicita cualquier
desacuerdo. No importa `unreal` y no introduce conocimiento de Jam dentro de Oracle.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from . import bridge

bridge.ensure_oraculo_on_path()

from oracle_metalenguaje import Informe, Motor  # noqa: E402


RAIZ = Path(__file__).resolve().parents[3]
PROYECTO = RAIZ / "medidas"


@dataclass(frozen=True)
class ComparacionSombra:
    """Resultado observable de la sombra; un fallo nunca se confunde con una coincidencia."""

    informe: Informe | None
    diferencias: tuple[str, ...] = ()
    error: str | None = None

    @property
    def coincide(self) -> bool:
        return self.error is None and not self.diferencias


@lru_cache(maxsize=1)
def motor_geometria() -> Motor:
    """Carga una sola instancia inmutable del proyecto versionado de Jam."""
    return Motor.desde_proyecto(PROYECTO, confiar_escalares=True)


def _plano(pieza) -> dict:
    """Convierte `geometry.Pieza` al hecho plano declarado por `medidas/escalares.py`."""
    a, loc = pieza.aabb, pieza.location
    return {
        "id": pieza.nombre,
        "ox": a.origin.x,
        "oy": a.origin.y,
        "oz": a.origin.z,
        "ex": a.extent.x,
        "ey": a.extent.y,
        "ez": a.extent.z,
        "lx": loc.x,
        "ly": loc.y,
        "lz": loc.z,
        "yaw": pieza.yaw,
    }


def hechos_geometria(pieza, otras=()) -> dict:
    """Construye las relaciones L0; `vecina` existe aunque esté vacía."""
    return {"pieza": [_plano(pieza)], "vecina": [_plano(otra) for otra in otras]}


def hechos_al_ras(pieza, objetivo, eje: str) -> dict:
    """Relaciones para juzgar una cara solicitada sin incorporar tipos de Unreal."""
    return {
        "pieza": [_plano(pieza)],
        "objetivo": [_plano(objetivo) | {"eje": eje}],
    }


def _comparar_evidencia(evidencia: dict, esperados: dict[str, bool]) -> ComparacionSombra:
    try:
        informe = motor_geometria().evaluar(evidencia)
        obtenidos = {veredicto.id: veredicto.ok for veredicto in informe.veredictos}
        diferencias = []
        for medida, esperado in esperados.items():
            if medida not in obtenidos:
                diferencias.append(f"{medida}: no fue evaluada")
            elif obtenidos[medida] != esperado:
                diferencias.append(
                    f"{medida}: referencia={esperado}, Motor={obtenidos[medida]}")
        return ComparacionSombra(informe=informe, diferencias=tuple(diferencias))
    except Exception as exc:  # noqa: BLE001 — la sombra informa, la referencia sigue gobernando
        return ComparacionSombra(
            informe=None,
            error=f"{type(exc).__name__}: {exc}",
        )


def comparar_placement(pieza, otras, referencia: dict) -> ComparacionSombra:
    return _comparar_evidencia(
        hechos_geometria(pieza, otras),
        {
            "colocacion.bounds": bool(referencia["bounds_ok"]),
            "colocacion.interpenetracion": not bool(referencia["interpenetra"]),
        },
    )


def comparar_snap(
    pieza,
    referencia: dict,
    *,
    grilla: float = 100.0,
    paso_yaw: float = 90.0,
    tol: float = 1.0,
    tol_yaw: float = 0.5,
) -> ComparacionSombra:
    configuracion = (float(grilla), float(paso_yaw), float(tol), float(tol_yaw))
    declarada = (100.0, 90.0, 1.0, 0.5)
    if configuracion != declarada:
        return ComparacionSombra(
            informe=None,
            error=("configuración no declarada por el catálogo "
                   f"(grilla, paso_yaw, tol, tol_yaw)={configuracion}"),
        )
    return _comparar_evidencia(
        hechos_geometria(pieza),
        {
            "snap.grilla": all(bool(ok) for ok in referencia["ejes_ok"].values()),
            "snap.yaw": bool(referencia["yaw_ok"]),
        },
    )


def comparar_al_ras(
    pieza,
    objetivo,
    eje: str,
    referencia: dict,
    *,
    tol: float = 1.0,
) -> ComparacionSombra:
    if float(tol) != 1.0:
        return ComparacionSombra(
            informe=None,
            error=f"tolerancia de al_ras no declarada por el catálogo: {float(tol)}",
        )
    return _comparar_evidencia(
        hechos_al_ras(pieza, objetivo, eje),
        {
            "snap.al_ras": abs(float(referencia["gap"])) <= float(tol),
            "snap.comparte_cara": referencia["estado"] != "desalineado",
        },
    )


def comparar_scatter(
    piezas,
    centro,
    semi,
    cantidad_pedida: int,
    referencia: dict,
    *,
    grilla: int = 3,
    cobertura_min: float = 0.6,
    tol: float = 1.0,
) -> ComparacionSombra:
    """Compara las cuatro decisiones binarias del reparto contra las medidas declaradas."""
    configuracion = (int(grilla), float(cobertura_min), float(tol))
    declarada = (3, 0.6, 1.0)
    if configuracion != declarada:
        return ComparacionSombra(
            informe=None,
            error=("configuración de scatter no declarada por el catálogo "
                   f"(grilla, cobertura_min, tol)={configuracion}"),
        )

    from . import oracle_scatter_facts

    return _comparar_evidencia(
        oracle_scatter_facts.hechos(
            piezas, centro, semi, cantidad_pedida, grilla=grilla),
        {
            "scatter.cantidad": bool(referencia["cantidad_ok"]),
            "scatter.contencion": not bool(referencia["fuera"]),
            "scatter.interpenetracion": not bool(referencia["interpenetra"]),
            "scatter.cobertura": bool(referencia["cobertura_ok"]),
        },
    )


def comparar_spline_modular(
    colocaciones,
    largo_curva: float,
    referencia: dict,
    *,
    tol: float = 1.0,
    cobertura_min: float = 0.9,
) -> ComparacionSombra:
    """Compara el juicio del verbo operativo `spline`, no el constructor legado `pared` R7."""
    configuracion = (float(tol), float(cobertura_min))
    declarada = (1.0, 0.9)
    if configuracion != declarada:
        return ComparacionSombra(
            informe=None,
            error=("configuración de spline no declarada por el catálogo "
                   f"(tol, cobertura_min)={configuracion}"),
        )

    from . import oracle_spline_facts

    return _comparar_evidencia(
        oracle_spline_facts.hechos(colocaciones, largo_curva),
        {
            "spline.cobertura": bool(referencia["cobertura_ok"]),
            "spline.sin_solape": bool(referencia["sin_solape"]),
        },
    )


def comparar_physics(
    pieza,
    soportes,
    referencia: dict,
    *,
    tol: float = 1.0,
) -> ComparacionSombra:
    """Compara existencia de suelo y contacto vertical del drop unitario."""
    if float(tol) != 1.0:
        return ComparacionSombra(
            informe=None,
            error=f"tolerancia de physics no declarada por el catálogo: {float(tol)}",
        )

    from . import oracle_physics_facts

    apoyado_en_alcance = (
        referencia["estado"] == "sin_suelo" or bool(referencia["apoyado"]))
    return _comparar_evidencia(
        oracle_physics_facts.hechos(pieza, soportes, tol=tol),
        {
            "physics.tiene_suelo": referencia["estado"] != "sin_suelo",
            "physics.apoyado": apoyado_en_alcance,
        },
    )


def comparar_physics_tanda(
    resultados,
    referencia: dict,
    *,
    tol: float = 1.0,
) -> ComparacionSombra:
    """Compara completitud y penetración del resultado final de ``drop(points)``."""
    if float(tol) != 1.0:
        return ComparacionSombra(
            informe=None,
            error=f"tolerancia de physics.tanda no declarada por el catálogo: {float(tol)}",
        )

    from . import oracle_physics_tanda_facts

    return _comparar_evidencia(
        oracle_physics_tanda_facts.hechos(resultados),
        {
            "physics.tanda_completa": bool(referencia["completa"]),
            "physics.tanda_sin_interpenetracion": bool(
                referencia["sin_interpenetracion"]),
        },
    )


def comparar_reemplazo(
    pieza,
    objetivo: dict,
    referencia: dict,
    *,
    tol: float = 1.0,
    tol_fp: float = 2.0,
) -> ComparacionSombra:
    """Compara centro, base y footprint del reemplazo operativo."""
    if (float(tol), float(tol_fp)) != (1.0, 2.0):
        return ComparacionSombra(
            informe=None,
            error=("tolerancias de reemplazo no declaradas por el catálogo: "
                   f"(tol, tol_fp)=({float(tol)}, {float(tol_fp)})"),
        )

    from . import oracle_reemplazo_facts

    return _comparar_evidencia(
        oracle_reemplazo_facts.hechos(pieza, objetivo),
        {
            "reemplazo.centrado": bool(referencia["centrado"]),
            "reemplazo.apoyado": bool(referencia["apoyado"]),
            "reemplazo.footprint": bool(referencia["footprint"]),
        },
    )


def comparar_espacio(graph, referencia: dict) -> ComparacionSombra:
    """Compara el contrato vivo de entrada, extracción, llaves y puertas."""
    from . import oracle_espacio_facts

    problemas = oracle_espacio_facts.configuracion_no_soportada(graph)
    if problemas:
        return ComparacionSombra(
            informe=None,
            error="configuración de espacio no declarada: " + "; ".join(problemas),
        )
    if bool(referencia.get("truncated")):
        return ComparacionSombra(
            informe=None,
            error="el solver de referencia truncó la búsqueda; no hay veredicto comparable",
        )
    fila = oracle_espacio_facts.hechos(graph)["espacio"][0]
    return _comparar_evidencia(
        {"espacio": [fila]},
        {
            "espacio.inicio_unico": fila["inicios"] == 1,
            "espacio.meta_unica": fila["metas"] == 1,
            "espacio.ganable": bool(referencia["solvable"]),
        },
    )
