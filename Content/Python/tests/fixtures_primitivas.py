"""El JUEZ de las primitivas de la base común: lo que el núcleo produce contra lo que Unreal produjo.

La referencia es `fixtures/primitivas_unreal.json`, que escribe `tools/experiments/
volcar_primitivas_58.py` corriendo cada verbo por el camino real del Graph. No se edita a mano ni se
regenera para que un test pase: si el motor cambia, se vuelve a volcar y se mira el diff.

`juzgar(malla, caso)` devuelve la lista de diferencias (vacía = igual al motor):
- triángulos, vértices distintos, caja envolvente (1e-3) y área (1e-3 relativo);
- cada triángulo del motor tiene su gemelo en el núcleo (las tres posiciones, en cualquier orden,
  a menos de 1e-3), y el gemelo DIBUJA la misma cara: `malla_core.cara_frontal` apunta hacia el
  mismo lado que la normal que midió Unreal.
Un caso con `error` exige que el núcleo levante `MallaError` con el MISMO mensaje.
"""

from __future__ import annotations

import json
import math
from pathlib import Path

from jam import malla_core

FIXTURE = Path(__file__).resolve().parent / "fixtures" / "primitivas_unreal.json"
TOL = 1e-3


def casos(verbo: str) -> list[dict]:
    datos = json.loads(FIXTURE.read_text(encoding="utf-8"))
    return [c for c in datos["casos"] if c["verbo"] == verbo]


def _cerca(a, b) -> bool:
    return all(abs(x - y) <= TOL for x, y in zip(a, b))


def juzgar(malla: malla_core.Malla, caso: dict) -> list[str]:
    m = caso["motor"]
    h = malla_core.hechos(malla)
    dif = []
    if h["triangulos"] != m["triangulos"]:
        dif.append(f"triángulos {h['triangulos']} ≠ motor {m['triangulos']}")
    if h["posiciones"] != m["vertices"]:
        dif.append(f"vértices distintos {h['posiciones']} ≠ motor {m['vertices']}")
    if not (_cerca(h["min"], m["min"]) and _cerca(h["max"], m["max"])):
        dif.append(f"caja {h['min']}..{h['max']} ≠ motor {m['min']}..{m['max']}")
    if m.get("area") and abs(h["area"] - m["area"]) > TOL * max(1.0, m["area"]):
        dif.append(f"área {h['area']} ≠ motor {m['area']}")
    if dif:
        return dif   # con la forma distinta, comparar triángulo a triángulo sólo haría ruido

    nuestros = [(tuple(malla.vertices[i] for i in tri), tri) for tri in malla.triangulos]
    usados = set()
    for k, t in enumerate(m["tris"]):
        gemelo = None
        for j, (pts, tri) in enumerate(nuestros):
            if j in usados:
                continue
            if all(any(_cerca(p, q) for q in pts) for p in t["p"]):
                gemelo = (j, tri)
                break
        if gemelo is None:
            dif.append(f"el triángulo {k} del motor {t['p']} no está en el núcleo")
            continue
        usados.add(gemelo[0])
        cara = malla_core.cara_frontal(malla.vertices, gemelo[1])
        if sum(cara[i] * t["n"][i] for i in range(3)) <= 0.0:
            dif.append(f"el triángulo {k} {t['p']} está dado vuelta (el núcleo dibuja la otra cara)")
        if len(dif) > 5:
            dif.append("…")
            break
    return dif


def juzgar_error(funcion, caso: dict) -> list[str]:
    """Un caso que el motor RECHAZA: el núcleo tiene que rechazarlo con el mismo mensaje."""
    try:
        funcion(**caso["params"])
    except malla_core.MallaError as e:
        return [] if str(e) == caso["error"] else [f"mensaje «{e}» ≠ motor «{caso['error']}»"]
    return [f"el núcleo aceptó {caso['params']}, que el motor rechaza: «{caso['error']}»"]


def area_esperada_finita(caso: dict) -> bool:
    return caso.get("motor", {}).get("area") is not None and math.isfinite(caso["motor"]["area"])
