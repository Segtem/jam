"""La VITRINA de la base común: el mismo texto, corrido en Unreal, Godot y Unity, y guardado en la
escena de cada uno para abrirlo y mirarlo. Tarea `base-comun`.

    python tools/vitrina/vitrina.py [--solo godot|unity|unreal] [--texto tools/vitrina/base_comun.jam]

Queda en:
- Unreal: JamPlayground, nivel /Game/Jam/Vitrina
- Godot:  ~/Dev/games/JamGodot/main.tscn   (godot --editor --path ~/Dev/games/JamGodot)
- Unity:  ~/Dev/games/JamUnity, escena Assets/Scenes/JamBaseComun.unity
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path

JAM = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(JAM / "Content/Python"))
sys.modules["unreal"] = None

from jam import adaptador_godot as ag  # noqa: E402
from jam import adaptador_unity as au  # noqa: E402

UE = Path.home() / "Dev/engines/UnrealEngine_5.8/Engine/Binaries/Linux/UnrealEditor"
UPROJECT = Path.home() / "Dev/games/JamPlayground/JamPlayground.uproject"
UNITY = Path.home() / "Dev/engines/unity/6000.3.24f1/Editor/Unity"


def _conectar(mod, intentos=240):
    for _ in range(intentos):
        try:
            return mod.Cliente(plazo=60)
        except mod.ErrorAdaptador:
            time.sleep(1)
    raise SystemExit("el motor no abrió el puerto del plugin Jam")


def _fijar(motor: str, texto: str) -> dict:
    if motor == "godot":
        proceso = subprocess.Popen(["godot", "--headless", "--editor", "--path",
                                    str(Path.home() / "Dev/games/JamGodot")],
                                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        mod, clase = ag, ag.AdaptadorGodot
    else:
        proyecto = Path.home() / "Dev/games/JamUnity"
        proceso = subprocess.Popen([str(UNITY), "-projectPath", str(proyecto), "-logFile",
                                    str(proyecto / "jam-vitrina.log"), "-batchmode", "-nographics",
                                    "-executeMethod", "Jam.JamServidor.Lote"],
                                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        mod, clase = au, au.AdaptadorUnity
    cliente = _conectar(mod)
    try:
        cliente.pedir("descartar")      # la vitrina se rehace entera: nada de corridas viejas
        r = mod.correr_texto(texto, clase(cliente))
        fijado = cliente.pedir("fijar") if r["ok"] else {}
        hechos = cliente.pedir("hechos")["mallas"]
    finally:
        if motor == "unity":
            try:
                cliente.pedir("salir")
            except (OSError, mod.ErrorAdaptador):
                pass
        cliente.cerrar()
        if motor == "godot":
            proceso.terminate()
        proceso.wait(120)
    return {"ok": r["ok"], "errores": r["errores"], "fijado": fijado,
            "mallas": {m["nodo"]: m["hechos"]["triangulos"] for m in hechos}}


def _unreal(ruta_texto: Path) -> dict:
    sonda = JAM / "tools/experiments/vitrina_unreal_58.py"
    salida = UPROJECT.parent / "Saved/jam_vitrina.json"
    salida.unlink(missing_ok=True)
    subprocess.run([str(UE), str(UPROJECT), "-RenderOffScreen", "-unattended", "-nosplash",
                    f"-ExecCmds=py {sonda},QUIT_EDITOR"],
                   env={**os.environ, "JAM_VITRINA": str(ruta_texto)},
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=900)
    r = json.loads(salida.read_text())
    return {"ok": r.get("ok"), "errores": r.get("errores"), "mallas": r.get("en_el_nivel"),
            "guardado": r.get("guardado")}


def main() -> int:
    a = argparse.ArgumentParser(description=__doc__)
    a.add_argument("--solo", choices=("unreal", "godot", "unity"))
    a.add_argument("--texto", default=str(JAM / "tools/vitrina/base_comun.jam"))
    args = a.parse_args()
    ruta = Path(args.texto).resolve()
    texto = ruta.read_text(encoding="utf-8")
    motores = [args.solo] if args.solo else ["unreal", "godot", "unity"]
    resultado = {m: (_unreal(ruta) if m == "unreal" else _fijar(m, texto)) for m in motores}
    print(json.dumps(resultado, ensure_ascii=False, indent=1))
    return 0 if all(r.get("ok") for r in resultado.values()) else 1


if __name__ == "__main__":
    sys.exit(main())
