"""Verifica la CADENA COMPLETA de una perilla: crear la función → guardarla → aparecer en el spec.

`verifica_perillas_funcion_58.py` prueba la ficha y la expansión con cuerpos armados a mano. Esto
prueba lo único que falta: que una definición GUARDADA aparezca en `api.spec_all()` —el spec que
carga el canvas de Slate— con sus perillas como `params`, que es de donde el C++ las dibuja.

Crea una definición temporal, la verifica y la borra. El veredicto queda en `BotOO.log` con el
prefijo `JAM_PERILLAS_SPEC_58`.
"""
from __future__ import annotations

import json

import unreal

from jam import api


def exigir(condicion: bool, mensaje: str) -> None:
    if not condicion:
        raise RuntimeError(mensaje)


ID = ""
try:
    creado = json.loads(api.function_manage("create", "", "PerillaDePrueba"))
    exigir(creado.get("ok"), f"no pude crear la definición: {creado}")
    # La identidad viaja dentro de la ficha, como `fn:<id>` — es el verbo estable de la instancia.
    verbo = (creado.get("tool") or {}).get("verbo", "")
    ID = verbo.split(":", 1)[1] if ":" in verbo else ""
    exigir(bool(ID), f"la creación no devolvió identidad: {creado}")

    # Cuerpo con un pin y una perilla.
    # El cuerpo tiene que ser VÁLIDO: `validar_cuerpo` exige que cada `output` esté alimentado.
    # Un pin (`puntos`, sin default) y una perilla (`cantidad`, con default).
    cuerpo = {
        "nodes": {
            "p": {"verb": "input", "params": {"name": "puntos", "type": "P"}, "x": 0, "y": 0},
            "k": {"verb": "input",
                  "params": {"name": "cantidad", "type": "N", "default": "24"}, "x": 0, "y": 80},
            "s": {"verb": "scatter", "params": {}, "x": 200, "y": 0},
            "o": {"verb": "output", "params": {"name": "pts", "type": "P"}, "x": 400, "y": 0},
        },
        "edges": [["p", "out", "s", "in"], ["k", "out", "s", "count"], ["s", "out", "o", "in"]],
    }
    act = json.loads(api.function_manage("update", ID, json.dumps(cuerpo)))
    exigir(act.get("ok"), f"no pude guardar el cuerpo: {act}")

    # LA prueba: el spec que consume Slate.
    spec = json.loads(api.spec_all())
    ficha = next((t for t in spec["tools"] if t.get("verbo", "").endswith(ID)), None)
    exigir(ficha is not None, f"la función no aparece en spec_all: {ID}")
    exigir([p["name"] for p in ficha.get("inputs", [])] == ["puntos"],
           f"los pines no son los esperados: {ficha.get('inputs')}")
    perillas = ficha.get("params", [])
    exigir([p["nombre"] for p in perillas] == ["cantidad"], f"perillas: {perillas}")
    exigir(perillas[0]["tipo"] == "int", f"control esperado int: {perillas[0]}")
    exigir(perillas[0]["default"] == "24", f"default esperado 24: {perillas[0]}")

    unreal.log(
        "JAM_PERILLAS_SPEC_58 TODO VERDE — "
        f"«{ficha['label']}» en el spec con pines={[p['name'] for p in ficha['inputs']]} "
        f"perillas={[(p['nombre'], p['tipo'], p['default']) for p in perillas]}")
except Exception as exc:  # noqa: BLE001
    unreal.log_error(f"JAM_PERILLAS_SPEC_58 ROJO — {type(exc).__name__}: {exc}")
finally:
    if ID:
        try:
            api.function_manage("delete", ID)   # no dejar basura en el proyecto
        except Exception:  # noqa: BLE001
            pass
    unreal.SystemLibrary.quit_editor()
