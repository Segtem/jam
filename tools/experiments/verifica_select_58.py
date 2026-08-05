"""Verifica el condicional de punta a punta en UE 5.8.1: comparación → select → consumidor.

Los tests cubren las piezas por separado con registros de mentira. Esto comprueba lo único que
ellos no pueden: que la cadena COMPLETA compila y corre con el catálogo real, que el booleano
producido por una comparación llega hasta el pin `cond` del select, y que cambiar la comparación
cambia la rama elegida.

Se corre dos veces el MISMO grafo cambiando un solo número, para que la diferencia observada sólo
pueda venir del condicional.

El veredicto queda en `BotOO.log` con el prefijo `JAM_SELECT_58`.
"""

from __future__ import annotations

import unreal

from jam.graph import JamGraph, ejecutar_detalle


def exigir(condicion: bool, mensaje: str) -> None:
    if not condicion:
        raise RuntimeError(mensaje)


def armar(a: float) -> JamGraph:
    """`a > 10` decide entre una caja y una esfera. Las dos se construyen igual: es dataflow."""
    g = JamGraph()
    g.add("mesh_box", {"size_x": "100", "size_y": "100", "size_z": "100"}, nid="caja")
    g.add("mesh_sphere", {"radius": "50"}, nid="esfera")
    g.add("compare_greater", {"a": str(a), "b": "10"}, nid="cmp")
    g.add("select_mesh", {}, nid="sel")
    g.add("mesh_clean_material_ids", {}, nid="fin")
    g.connect("cmp", "sel", "cond")
    g.connect("caja", "sel", "si")
    g.connect("esfera", "sel", "no")
    g.connect("sel", "fin")
    return g


try:
    _rep_si, estados_si = ejecutar_detalle(armar(20.0))    # 20 > 10 → rama «sí» (caja)
    _rep_no, estados_no = ejecutar_detalle(armar(5.0))     # 5 > 10 es falso → rama «no» (esfera)

    for nombre, estados in (("sí", estados_si), ("no", estados_no)):
        exigir(estados["sel"]["estado"] != "error",
               f"el select falló en la rama {nombre}: {estados['sel']}")
        exigir(estados["fin"]["estado"] != "error",
               f"el consumidor falló en la rama {nombre}: {estados['fin']}")

    exigir("sí" in estados_si["sel"]["texto"],
           f"con 20 > 10 tendría que haber seguido por «sí»: {estados_si['sel']['texto']}")
    exigir("no" in estados_no["sel"]["texto"],
           f"con 5 > 10 tendría que haber seguido por «no»: {estados_no['sel']['texto']}")

    # La prueba que de verdad importa: el de abajo recibió mallas DISTINTAS según la condición.
    exigir(estados_si["fin"]["texto"] != estados_no["fin"]["texto"],
           "las dos ramas dieron el mismo resultado: el select no está eligiendo nada")

    unreal.log(
        "JAM_SELECT_58 TODO VERDE — "
        f"rama_si={estados_si['sel']['texto']} → {estados_si['fin']['texto'][-58:]} · "
        f"rama_no={estados_no['sel']['texto']} → {estados_no['fin']['texto'][-58:]}")
except Exception as exc:  # noqa: BLE001
    unreal.log_error(f"JAM_SELECT_58 ROJO — {type(exc).__name__}: {exc}")
finally:
    unreal.SystemLibrary.quit_editor()
