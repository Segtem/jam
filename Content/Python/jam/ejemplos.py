"""Los ejemplos que ofrece el editor web: los `.jamgraph` de `Resources/Examples` y los textos de
`tools/vitrina` (`*.jam`). Cerebro puro: sin `unreal`.

Cada ejemplo dice si corre en el motor conectado —todos sus verbos disponibles— y, si no, cuáles le
faltan. Así el que abre el editor en Godot sabe qué puede probar sin adivinar.
"""

from __future__ import annotations

import json
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[3]
CARPETAS = (RAIZ / "tools" / "vitrina", RAIZ / "Resources" / "Examples")
#: Lo que se abre si no hay otro grafo: la vitrina de la base común, que corre en los tres motores.
INICIAL = "base_comun"


def _archivos() -> dict[str, Path]:
    salida = {}
    for carpeta in CARPETAS:
        for f in sorted(carpeta.glob("*.jam")) + sorted(carpeta.glob("*.jamgraph")):
            salida.setdefault(f.stem, f)
    return salida


def grafo(nombre: str) -> dict:
    """El JSON del canvas del ejemplo. Un `.jam` es texto: se lee y se acomoda con `texto.aplicar`."""
    from . import texto
    f = _archivos().get(nombre)
    if f is None:
        raise KeyError(f"no hay un ejemplo «{nombre}»")
    if f.suffix == ".jam":
        return texto.aplicar(f.read_text(encoding="utf-8"))
    return json.loads(f.read_text(encoding="utf-8"))


def listar(motor: str, implementados=None) -> list[dict]:
    """`[{nombre, corre, faltan}]`: el ejemplo corre si todos sus verbos están disponibles en `motor`."""
    from .registro import REGISTRO, disponible
    salida = []
    for nombre in _archivos():
        try:
            verbos = {n.get("verb", "") for n in grafo(nombre).get("nodes", {}).values()}
        except Exception as e:  # noqa: BLE001 — un ejemplo roto se lista con su error, no tumba la lista
            salida.append({"nombre": nombre, "corre": False, "faltan": [f"no se pudo leer: {e}"]})
            continue
        faltan = sorted(v for v in verbos if v in REGISTRO and not disponible(v, motor, implementados)[0])
        salida.append({"nombre": nombre, "corre": not faltan, "faltan": faltan})
    return sorted(salida, key=lambda e: (not e["corre"], e["nombre"] != INICIAL, e["nombre"]))
