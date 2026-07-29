"""Verifica `jam.api.acomodar` por el CAMINO REAL: adentro del editor, con el mismo JSON que arma
el C++ (`SJamGraphEditor::AcomodarSeleccion`) y el mismo formato de respuesta que parsea.

Llamar a `jam.layout` directo desde un test ya está cubierto por `tests/test_layout.py`. Lo que ESTO
prueba es lo otro: que el nombre `acomodar` exista en `jam.api`, que el JSON con comillas dobles
sobreviva el viaje por `ToPyStr` y que la respuesta tenga las claves que el C++ va a leer.
"""

from __future__ import annotations

import json

import unreal

import jam.api as _a


def fila(i: str, x: float, y: float, h: float) -> str:
    # el mismo printf del C++: ancho fijo (NodeWidth=184), alto por cantidad de params
    return '{"id":"%s","x":%.3f,"y":%.3f,"w":%.3f,"h":%.3f}' % (i, x, y, 184.0, h)


def main() -> None:
    fallas: list[str] = []

    entrada = "[%s]" % ",".join([
        fila("n1", 100.0, 0.0, 34.0),
        fila("n2", 40.0, 90.0, 126.0),
        fila("n3", 300.0, 200.0, 57.0),
    ])

    for accion, comprobar in (
        ("izquierda", lambda p: {round(v[0]) for v in p.values()} == {40}),
        ("abajo", lambda p: {round(v[1] + h) for v, h in
                             zip(p.values(), (34.0, 126.0, 57.0))} == {257}),
        ("dist-y", lambda p: len(p) == 3),
    ):
        res = _a.acomodar(entrada, accion)
        try:
            d = json.loads(res)
        except Exception as e:                                   # noqa: BLE001
            fallas.append(f"{accion}: la respuesta no es JSON ({e}): {res!r}")
            continue
        if not d.get("ok"):
            fallas.append(f"{accion}: ok=False → {d}")
            continue
        pos = d.get("pos")
        if not isinstance(pos, dict) or set(pos) != {"n1", "n2", "n3"}:
            fallas.append(f"{accion}: `pos` no trae los tres ids → {pos}")
            continue
        if any(not isinstance(v, list) or len(v) != 2 for v in pos.values()):
            fallas.append(f"{accion}: cada posición tiene que ser [x, y] → {pos}")
            continue
        if not comprobar(pos):
            fallas.append(f"{accion}: las posiciones no son las esperadas → {pos}")
        unreal.log(f"[verifica_acomodar] {accion}: {pos}")

    # una acción inventada no puede pasar por buena en silencio: el C++ muestra el error
    mala = json.loads(_a.acomodar(entrada, "diagonal"))
    if mala.get("ok") is not False or not mala.get("error"):
        fallas.append(f"una acción desconocida tendría que devolver ok=False con error → {mala}")

    # menos de dos nodos: devuelve lo mismo que entró, no un error
    uno = json.loads(_a.acomodar('[{"id":"n1","x":5,"y":7,"w":184,"h":34}]', "izquierda"))
    if not uno.get("ok") or uno["pos"]["n1"] != [5.0, 7.0]:
        fallas.append(f"un solo nodo tendría que quedar donde está → {uno}")

    if fallas:
        unreal.log_error("[verifica_acomodar] VEREDICTO: ROJO")
        for f in fallas:
            unreal.log_error(f"  · {f}")
    else:
        unreal.log("[verifica_acomodar] VEREDICTO: TODO VERDE")


main()
