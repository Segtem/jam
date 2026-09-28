"""La base común corre igual en Unreal y en Godot (tarea `base-comun`, paso 2), medido por los DOS.

    python tools/experiments/verifica_base_comun_godot.py

1. Lee lo que midió Unreal sobre la caja del núcleo: `~/Dev/games/JamPlayground/Saved/
   jam_caja_comun.json` (lo escribe `verifica_caja_comun_58.py`, que se corre antes en el editor).
2. Levanta Godot headless con `~/Dev/games/JamGodot` (plugin Jam), corre el MISMO texto con el
   núcleo en este proceso —`caja = mesh_box …` → `mesh_preview @caja`— y pide los hechos que Godot
   mide sobre las mallas que guardó.
3. Compara: triángulos, vértices y caja envolvente iguales; área con tolerancia relativa 1e-6
   (Godot guarda float32); toda cara frontal hacia afuera según la convención de Godot.
Sale 0 si los dos motores dan lo mismo.
"""

from __future__ import annotations

import json
import subprocess
import sys
import time
from pathlib import Path

JAM = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(JAM / "Content/Python"))
sys.modules["unreal"] = None   # el núcleo corre SIN Unreal: es la prueba

from jam import adaptador_godot as ag  # noqa: E402

UNREAL = Path.home() / "Dev/games/JamPlayground/Saved/jam_caja_comun.json"
PROYECTO = Path.home() / "Dev/games/JamGodot"


def main() -> int:
    medido_unreal = json.loads(UNREAL.read_text())
    if medido_unreal.get("veredicto") != "VERDE":
        raise SystemExit(f"la medición de Unreal no es VERDE: {UNREAL}")
    godot = subprocess.Popen(["godot", "--headless", "--editor", "--path", str(PROYECTO)],
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    fallas, filas = [], []
    try:
        for _ in range(60):
            try:
                cliente = ag.Cliente(plazo=10)
                break
            except ag.ErrorAdaptador:
                time.sleep(1)
        else:
            raise SystemExit("Godot no abrió el puerto del plugin Jam")
        adaptador = ag.AdaptadorGodot(cliente)
        for i, caso in enumerate(medido_unreal["casos"]):
            params = " ".join(f"{k}={v}" for k, v in caso["caso"].items())
            r = ag.correr_texto(f"caja = mesh_box {params}\nver = mesh_preview @caja name=caso{i}\n",
                                adaptador)
            if not r["ok"]:
                fallas.append(f"caso {i}: no corrió en Godot: {r['errores'] or r['report']}")
        en_godot = {m["nodo"]: m["hechos"] for m in cliente.pedir("hechos")["mallas"]}
        for i, caso in enumerate(medido_unreal["casos"]):
            u, g = caso["nucleo"], en_godot.get(f"caso{i}", {})
            area_u = u["area_volumen"][0]
            fila = {"caso": caso["caso"], "unreal": {k: u[k] for k in ("triangulos", "vertices", "min", "max")}
                    | {"area": area_u}, "godot": g}
            filas.append(fila)
            if (g.get("triangulos"), g.get("posiciones"), g.get("min"), g.get("max")) != (
                    u["triangulos"], u["vertices"], u["min"], u["max"]):
                fallas.append(f"caso {i}: Unreal y Godot miden distinto")
            if abs(g.get("area", 0) - area_u) > 1e-6 * area_u:
                fallas.append(f"caso {i}: área {g.get('area')} contra {area_u}")
            if g.get("caras_hacia_afuera") != g.get("triangulos"):
                fallas.append(f"caso {i}: en Godot hay caras frontales hacia adentro")
        cliente.pedir("descartar")
        cliente.cerrar()
    finally:
        godot.terminate()
        godot.wait(20)
    print(json.dumps({"veredicto": "VERDE" if not fallas else "ROJO", "casos": filas,
                      "fallas": fallas}, ensure_ascii=False, indent=1))
    return 0 if not fallas else 1


if __name__ == "__main__":
    sys.exit(main())
