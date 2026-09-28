"""La colocación de la base común da lo mismo en Unreal y en otro motor, medido por los DOS.

    python tools/experiments/verifica_colocar.py --motor godot
    python tools/experiments/verifica_colocar.py --motor unity

1. Lee lo que colocó Unreal: `~/Dev/games/JamPlayground/Saved/jam_colocar.json` (lo escribe
   `verifica_colocar_58.py`, que se corre antes en el editor).
2. Copia el banco del motor (JamGodot / JamUnity) a un directorio temporal —los casos FIJAN, y fijar
   guarda la escena: el banco de verdad no se toca— y lo levanta headless.
3. Corre los casos de `casos_colocar.py` con el núcleo en este proceso: cada uno parte de un Preview
   descartado, y de su último paso se comparan las cajas de mundo de cada instancia, que MIDE el
   motor, contra las que midió Unreal. Tolerancia 0,01 cm (Godot y Unity guardan float32).
Sale 0 si los dos motores dan lo mismo.
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

JAM = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(JAM / "Content/Python"))
sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.modules["unreal"] = None   # el núcleo corre SIN Unreal: es la prueba

import casos_colocar as cc  # noqa: E402
from jam import adaptador_godot as ag  # noqa: E402
from jam import adaptador_unity as au  # noqa: E402

UNREAL = Path.home() / "Dev/games/JamPlayground/Saved/jam_colocar.json"
BANCO = {"godot": Path.home() / "Dev/games/JamGodot", "unity": Path.home() / "Dev/games/JamUnity"}
UNITY = Path.home() / "Dev/engines/unity/6000.3.24f1/Editor/Unity"
TOL = 0.01


def _lanzar(motor: str, proyecto: Path):
    if motor == "godot":
        return subprocess.Popen(["godot", "--headless", "--editor", "--path", str(proyecto)],
                                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL), ag
    return subprocess.Popen([str(UNITY), "-projectPath", str(proyecto), "-logFile",
                             str(proyecto / "jam-colocar.log"), "-batchmode", "-nographics",
                             "-executeMethod", "Jam.JamServidor.Lote"],
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL), au


def _copiar(motor: str, destino: Path) -> Path:
    # Sin git ni logs; con Library (Unity) y .godot, para no reimportar todo. Los enlaces del plugin
    # se copian como enlaces: el plugin que corre es el del repo.
    ignorar = shutil.ignore_patterns(".git", "*.log", "Logs", "mono_crash*", "Temp")
    shutil.copytree(BANCO[motor], destino, symlinks=True, ignore=ignorar)
    return destino


def _conectar(mod, plazo=240.0):
    fin = time.time() + plazo
    while True:
        try:
            cliente = mod.Cliente(plazo=120)
            clase = mod.AdaptadorGodot if mod is ag else mod.AdaptadorUnity
            return cliente, clase(cliente)
        except mod.ErrorAdaptador:
            if time.time() > fin:
                raise
            time.sleep(1)


def correr_casos(cliente, adaptador) -> dict:
    """{caso: [{min, max}] ordenadas} de lo que colocó el último paso de cada caso."""
    salida = {}
    for nombre, pasos in cc.CASOS:
        cliente.pedir("descartar")
        for paso in pasos:
            if paso == cc.FIJAR:
                cliente.pedir("fijar")
                continue
            r = ag.correr_texto(paso, adaptador)
            if not r["ok"]:
                raise RuntimeError(f"{nombre}: {r['errores'] or r['report']}")
        # Todo lo que colocó la corrida, de todos sus `place` (como Unreal cuenta actores nuevos).
        salida[nombre] = sorted(adaptador.colocadas, key=lambda c: (c["min"], c["max"]))
    return salida


def comparar(unreal: dict, otro: dict) -> list[str]:
    fallas = []
    for nombre, _pasos in cc.CASOS:
        a, b = unreal.get(nombre), otro.get(nombre)
        if a is None:
            fallas.append(f"{nombre}: Unreal no lo midió (¿corriste verifica_colocar_58.py?)")
            continue
        if len(a) != len(b):
            fallas.append(f"{nombre}: {len(a)} instancias en Unreal, {len(b)} en el otro")
            continue
        for i, (x, y) in enumerate(zip(a, b)):
            d = max(abs(p - q) for k in ("min", "max") for p, q in zip(x[k], y[k]))
            if d > TOL:
                fallas.append(f"{nombre}[{i}]: difiere {d:.3f} cm — Unreal {x} · otro {y}")
    return fallas


def main(argv=None) -> int:
    a = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    a.add_argument("--motor", choices=("godot", "unity"), required=True)
    args = a.parse_args(argv)
    unreal = json.loads(UNREAL.read_text())["casos"]
    with tempfile.TemporaryDirectory(prefix=f"jam-colocar-{args.motor}-") as tmp:
        proyecto = _copiar(args.motor, Path(tmp) / "proyecto")
        proceso, mod = _lanzar(args.motor, proyecto)
        try:
            cliente, adaptador = _conectar(mod)
            otro = correr_casos(cliente, adaptador)
            if args.motor == "unity":
                try:
                    cliente.pedir("salir")
                except Exception:  # noqa: BLE001
                    pass
        finally:
            if args.motor == "godot":
                proceso.terminate()   # el editor de Godot no sale solo
            try:
                proceso.wait(timeout=30)
            except subprocess.TimeoutExpired:
                proceso.terminate()
                proceso.wait(timeout=30)
    fallas = comparar(unreal, otro)
    print(json.dumps({"veredicto": "ROJO" if fallas else "VERDE", "motor": args.motor,
                      "casos": {n: len(v) for n, v in otro.items()}, "fallas": fallas},
                     ensure_ascii=False, indent=1))
    return 1 if fallas else 0


if __name__ == "__main__":
    sys.exit(main())
