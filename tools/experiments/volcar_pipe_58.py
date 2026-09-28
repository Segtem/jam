"""Sonda de editor: vuelca lo que PRODUCE Unreal para `mesh_pipe` (tubo sobre una curva), para que
el núcleo lo reproduzca (tarea `base-comun`). La curva de entrada de cada caso se describe con verbos
que YA son de la base común, así el núcleo la reconstruye igual. Mismo formato que
`volcar_primitivas_58.py`; escribe `Content/Python/tests/fixtures/pipe_unreal.json`.
"""

import importlib.util
import json
import os
import traceback

import unreal

AQUI = os.path.dirname(os.path.abspath(__file__)) if "__file__" in globals() else \
    os.path.expanduser("~/Dev/jam/tools/experiments")
_spec = importlib.util.spec_from_file_location("volcar", os.path.join(AQUI, "volcar_primitivas_58.py"))
SALIDA = os.path.expanduser("~/Dev/jam/Content/Python/tests/fixtures/pipe_unreal.json")

CURVAS = {
    "recta": ("curve_line", {"desde": "0,0,0", "hasta": "0,0,300"}),
    "bezier": ("curve_bezier", {"end_x": 200, "end_z": 300, "bend_x": 150, "bend_y": 60, "segments": 12}),
    "esquina": ("curve_line", {"desde": "0,0,0", "hasta": "300,0,0"}),
}
PARAMS = [{}, {"radius_start": 20, "radius_end": 20, "sides": 6, "capped": False},
          {"radius_start": 40, "radius_end": 10, "sides": 3, "profile_rotation": 30},
          {"sides": 8, "miter_limit": 1.0}, {"sides": 2}]


def curva(nombre):
    from jam import comun
    verbo, params = CURVAS[nombre]
    dato, _ = comun.IMPLEMENTA[verbo](None, **params)
    return dato


def main():
    from jam import comun, curve
    medir = None
    try:
        import sys
        sys.argv = ["x"]
        modulo = importlib.util.module_from_spec(_spec)
        # No correr el main del otro archivo: sólo se quieren sus funciones.
        codigo = open(_spec.origin, encoding="utf-8").read().split("\ntry:\n    datos =")[0]
        exec(compile(codigo, _spec.origin, "exec"), modulo.__dict__)
        medir, correr = modulo.medir, modulo.correr
    except Exception:  # noqa: BLE001
        raise
    casos = []
    # Una polilínea con una esquina de 90°: dos tramos. Se arma con curve_polyline sobre series.
    esquina = curve.CurvePath(((0.0, 0.0, 0.0), (300.0, 0.0, 0.0), (300.0, 300.0, 0.0)))
    entradas = {"recta": curva("recta"), "bezier": curva("bezier"), "esquina": esquina}
    for nombre, entrada in entradas.items():
        for params in PARAMS:
            base = {"verbo": "mesh_pipe", "curva": nombre, "puntos": [list(p) for p in entrada.points],
                    "params": params}
            try:
                casos.append({**base, "motor": medir(correr("mesh_pipe", entrada, params))})
            except RuntimeError as e:
                casos.append({**base, "error": str(e)})
    return casos


try:
    datos = {"veredicto": "VERDE", "motor": "unreal 5.8.1", "casos": main()}
except Exception:  # noqa: BLE001
    datos = {"veredicto": "EXCEPCION", "excepcion": traceback.format_exc()}
with open(SALIDA, "w", encoding="utf-8") as f:
    json.dump(datos, f, ensure_ascii=False, indent=1)
unreal.log(f"JAM_PIPE {datos['veredicto']} → {SALIDA}")
