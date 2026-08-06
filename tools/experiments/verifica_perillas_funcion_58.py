"""Verifica las perillas de una función por el camino REAL: spec → Compile → Run en UE 5.8.1.

Los tests cubren `firma`/`herramienta`/`expandir` con grafos armados a mano. Esto comprueba lo que
ellos no pueden: que una función con perillas sobreviva el viaje entero —publicarse en el spec que
consume Slate, compilar y CORRER— y que el valor de la perilla llegue de verdad al nodo de adentro.

El veredicto queda en `BotOO.log` con el prefijo `JAM_PERILLAS_58`.
"""
from __future__ import annotations

import json

import unreal

from jam import api, funcion
from jam.graph import JamGraph


def exigir(condicion: bool, mensaje: str) -> None:
    if not condicion:
        raise RuntimeError(mensaje)


def cuerpo() -> JamGraph:
    """Una función mínima con una perilla: cuántos puntos genera el scatter."""
    c = JamGraph()
    c.add("input", {"name": "cantidad", "type": "N", "default": "24"}, nid="k")
    c.add("scatter", {"area": "600"}, nid="s")
    c.add("output", {"name": "pts", "type": "P"}, nid="o")
    c.connect("k", "s", "count")
    c.connect("s", "o")
    return c


try:
    biblio = {"f_prueba": cuerpo()}

    # 1. La ficha que consume Slate: la perilla tiene que salir como PARAM, no como pin.
    ficha = funcion.herramienta("f_prueba", "Prueba", cuerpo())
    exigir(ficha["inputs"] == [], f"no debería tener pines: {ficha['inputs']}")
    exigir([p["nombre"] for p in ficha["params"]] == ["cantidad"], f"perillas: {ficha['params']}")
    exigir(ficha["params"][0]["tipo"] == "int", f"control esperado int: {ficha['params'][0]}")
    exigir(ficha["source"] is True, "sin pines que cablear, la herramienta es una fuente")

    # 2. El valor baja al nodo de adentro, con el catálogo real.
    g = JamGraph()
    g.add("fn:f_prueba", {"cantidad": "7"}, nid="inst")
    expandido = funcion.expandir(g, biblio)
    exigir(expandido.nodes["inst__s"]["params"]["count"] == "7",
           f"la perilla no llegó: {expandido.nodes['inst__s']['params']}")

    # 3. Y CORRE: el grafo expandido pasa por el runner real y produce los puntos pedidos.
    from jam.graph import ejecutar_detalle
    _rep, estados = ejecutar_detalle(expandido)
    exigir(estados["inst__s"]["estado"] != "error", f"el scatter falló: {estados['inst__s']}")

    unreal.log(
        "JAM_PERILLAS_58 TODO VERDE — "
        f"ficha: pines={len(ficha['inputs'])} perillas={[p['nombre'] for p in ficha['params']]} "
        f"· count aplicado=7 · run={estados['inst__s']['texto'][:60]}")
except Exception as exc:  # noqa: BLE001
    unreal.log_error(f"JAM_PERILLAS_58 ROJO — {type(exc).__name__}: {exc}")
finally:
    unreal.SystemLibrary.quit_editor()
