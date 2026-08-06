"""Verifica el NODO reroute con el catálogo real: tiene que ser transparente de verdad.

Los tests lo cubren con un registro de mentira. Esto comprueba lo único que importa de un punto de
paso: que el nodo de abajo reciba EXACTAMENTE lo mismo con y sin el reroute en el medio. Se corre
el mismo grafo dos veces y se comparan los reportes.

El veredicto queda en `BotOO.log` con el prefijo `JAM_REROUTE_NODO_58`.
"""
from __future__ import annotations

import unreal

from jam.graph import JamGraph, ejecutar_detalle


def exigir(condicion: bool, mensaje: str) -> None:
    if not condicion:
        raise RuntimeError(mensaje)


def armar(con_reroute: bool) -> JamGraph:
    g = JamGraph()
    g.add("mesh_box", {"size_x": "100", "size_y": "100", "size_z": "100"}, nid="caja")
    g.add("mesh_clean_material_ids", {}, nid="fin")
    if con_reroute:
        g.add("reroute_mesh", {}, nid="rr")
        g.connect("caja", "rr")
        g.connect("rr", "fin")
    else:
        g.connect("caja", "fin")
    return g


try:
    _r1, sin = ejecutar_detalle(armar(False))
    _r2, con = ejecutar_detalle(armar(True))

    exigir(con["rr"]["estado"] != "error", f"el reroute falló: {con['rr']}")
    exigir(sin["fin"]["estado"] != "error", f"falló sin reroute: {sin['fin']}")
    # LA prueba: el de abajo no puede notar la diferencia.
    exigir(sin["fin"]["texto"] == con["fin"]["texto"],
           f"el reroute cambió el dato:\n  sin: {sin['fin']['texto']}\n  con: {con['fin']['texto']}")

    unreal.log(
        "JAM_REROUTE_NODO_58 TODO VERDE — "
        f"reroute={con['rr']['texto']} · idéntico con y sin: {con['fin']['texto'][-52:]}")
except Exception as exc:  # noqa: BLE001
    unreal.log_error(f"JAM_REROUTE_NODO_58 ROJO — {type(exc).__name__}: {exc}")
finally:
    unreal.SystemLibrary.quit_editor()
