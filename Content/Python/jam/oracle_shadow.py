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
