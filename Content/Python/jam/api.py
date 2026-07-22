"""jam.api — el ÚNICO contrato entre Jam y CUALQUIER interfaz.

Una interfaz (la Dash Bar en C++, una CLI externa, una web…) sólo necesita estas funciones. Así la UI
es un cliente FINO y reemplazable: hoy la llama el módulo C++/Slate vía ExecPythonCommandEx; mañana
puede llamarla un proceso Python FUERA de Unreal (por la ejecución remota del editor) sin tocar el
cerebro. Todo entra/sale como str o JSON — nunca objetos de UE. Ante UE6/Verse, la UI se reescribe
contra ESTE contrato; el cerebro no se toca.

Contrato:
    spec()                → JSON {categorias, tools} para armar la UI
    assets(query, limit)  → JSON de assets del proyecto (Content browser)
    run(command)          → corre una línea de DSL, devuelve el veredicto (texto)
    run_graph(json)       → corre un JamGraph (JSON), devuelve el reporte (texto)
    confirm() / discard() → fija o descarta el preview activo
"""

from __future__ import annotations


def spec() -> str:
    from . import tools
    return tools.spec_json()


def assets(query: str = "", limit: int = 60) -> str:
    from . import library
    return library.buscar_json(query, limit=limit)


def run(command: str) -> str:
    from . import panel
    return panel.ejecutar_dsl(command, None)


def run_graph(graph_json: str) -> str:
    from . import panel
    return panel.ejecutar_grafo(graph_json, None)


def confirm() -> str:
    from . import panel
    return panel.ejecutar_dsl("confirm", None)


def discard() -> str:
    from . import panel
    return panel.ejecutar_dsl("discard", None)
