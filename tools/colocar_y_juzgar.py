"""Coloca una orden en Unreal (JamPlayground, headless) y la juzga con Oracle. El ciclo del corte 1
de un Aura propio (`commander/docs/AURA-PROPIO-CORTE-1.md`), en un comando:

    python tools/colocar_y_juzgar.py tools/aura/escenario1_mal.json [--json]

orden → `Saved/Oracle/orden.json` → `sonda_colocacion_aura.py` en el editor → `Saved/Oracle/escena.json`
(hechos L0) → `oracle juzgar` con las medidas de COLOCACIÓN. Sale con el código de Oracle: 0 verde,
1 rojo. Los testigos dicen qué par falla y por cuánto: la corrección sale de ahí.

Se juzgan sólo las medidas de colocación (`MEDIDAS`): el resto del catálogo mide otras cosas, y
`snap.grilla`/`snap.yaw` son la promesa del verbo `snap`, no de colocar en cualquier lado.
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path

JAM = Path(__file__).resolve().parents[1]
PROYECTO = Path.home() / "Dev/games/JamPlayground"
EDITOR = Path.home() / "Dev/engines/UnrealEngine_5.8/Engine/Binaries/Linux/UnrealEditor"
SONDA = JAM / "tools/experiments/sonda_colocacion_aura.py"
MEDIDAS = ("colocacion.bounds", "colocacion.interpenetracion", "physics.tiene_suelo",
           "physics.apoyado", "physics.tanda_completa", "physics.tanda_sin_interpenetracion")


def main(argv=None) -> int:
    a = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    a.add_argument("orden", type=Path)
    a.add_argument("--proyecto", type=Path, default=PROYECTO, help="el .uproject vive acá")
    a.add_argument("--json", action="store_true", help="el informe de Oracle en JSON")
    args = a.parse_args(argv)
    carpeta = args.proyecto / "Saved/Oracle"
    carpeta.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(args.orden, carpeta / "orden.json")
    (carpeta / "escena.json").unlink(missing_ok=True)
    uproject = next(args.proyecto.glob("*.uproject"))
    subprocess.run([str(EDITOR), str(uproject), "-RenderOffScreen", "-unattended", "-nosplash",
                    f"-ExecCmds=py {SONDA},QUIT_EDITOR"],
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=600)
    escena = carpeta / "escena.json"
    hechos = json.loads(escena.read_text(encoding="utf-8")) if escena.exists() else {}
    if "error" in hechos or not hechos:
        print(f"✗ la sonda no volcó la escena:\n{hechos.get('error', 'no escribió escena.json')}",
              file=sys.stderr)
        return 2
    # Una tanda a medias no es un veredicto: es un sensor que no vio todo lo que se pidió. Las
    # medidas declaran `requiere` para la tanda vacía; una tanda incompleta sólo se ve contando.
    pedidas = len(json.loads(args.orden.read_text(encoding="utf-8")).get("tanda", []))
    if len(hechos.get("pieza", [])) != pedidas:
        print(f"✗ la sonda volcó {len(hechos.get('pieza', []))} de {pedidas} piezas pedidas",
              file=sys.stderr)
        return 2
    orden = [str(shutil.which("oracle") or "oracle"), "juzgar", "--con", str(escena),
             "--proyecto", str(JAM / "medidas"), "--confiar-escalares", "--parcial"]
    for m in MEDIDAS:
        orden += ["--medida", m]
    if args.json:
        orden.append("--json")
    print(f"hechos: {escena}", file=sys.stderr)
    return subprocess.run(orden).returncode


if __name__ == "__main__":
    sys.exit(main())
