"""Kit — cómo se agarra cada asset. CEREBRO PURO (0 `import unreal`).

Un pack no viene normalizado: `casa_kit` trae el pivote abajo en una esquina, otro lo trae al centro,
otro fuera de la malla. Mientras el pivote esté en cualquier lado, la pieza **no se mueve bien**: el
gizmo del editor la agarra de una esquina y al rotarla se va de paseo en vez de girar en su lugar.

Acá se anota, POR ASSET, por qué punto hay que agarrarlo (su ancla normalizada). Se normaliza una vez
y desde entonces todas las herramientas —place, scatter, spline— tratan a ese asset como si su pivote
estuviera ahí. No se toca la malla del disco: el pack queda intacto (y en los comerciales, además,
tocarlo no corresponde).
"""

from __future__ import annotations

import json

# ruta del asset → ancla con la que hay que agarrarlo
_ANCLAS: dict[str, str] = {}

DEFECTO = "base"


def set_ancla(ruta: str, ancla: str) -> None:
    if ruta:
        _ANCLAS[ruta] = ancla or DEFECTO


def ancla(ruta: str | None, defecto: str = DEFECTO) -> str:
    """Por qué punto agarrar ese asset. Si nunca se normalizó, el default (`base`: apoyar)."""
    return _ANCLAS.get(ruta or "", defecto)


def normalizado(ruta: str | None) -> bool:
    return (ruta or "") in _ANCLAS


def olvidar(ruta: str) -> None:
    _ANCLAS.pop(ruta, None)


def todos() -> dict[str, str]:
    return dict(_ANCLAS)


def to_json() -> str:
    return json.dumps(_ANCLAS, ensure_ascii=True, indent=1, sort_keys=True)


def from_json(texto: str) -> int:
    """Carga el registro (lo pisa). Devuelve cuántos assets normalizados quedaron."""
    _ANCLAS.clear()
    try:
        d = json.loads(texto or "{}")
    except ValueError:
        return 0
    for k, v in d.items():
        if isinstance(k, str) and isinstance(v, str):
            _ANCLAS[k] = v
    return len(_ANCLAS)


def sugerir(diag: dict) -> str:
    """Qué ancla conviene según el diagnóstico del pivote (`jam.pivot.diagnostico`).

    Un pivote en una esquina de la planta se puede respetar (sirve para embaldosar desde esa esquina)
    pero para MOVER la pieza es incómodo: se normaliza a `base`, que es el punto natural de agarre.
    Si el pivote ya está en la base y centrado, no hay nada que normalizar."""
    if diag.get("fuera"):
        return "base"
    if diag.get("en_base") and diag.get("centrado_planta"):
        return "pivot"        # ya está donde tiene que estar
    return "base"
