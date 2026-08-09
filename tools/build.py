"""Compila el C++ de Jam y COMPRUEBA que cada módulo haya quedado al día.

    python tools/build.py            → compila y verifica
    python tools/build.py --solo-ver → sólo verifica, sin compilar

Existe por una trampa que ya costó un reporte falso: **`Result: Succeeded` también lo imprime un
build que no hizo nada**. Un día se reportó un arreglo de UI sobre un `.so` 35 minutos más viejo
que el `.cpp`, y lo que se estaba mirando era el binario anterior.

Comprueba por separado cada carpeta de `Source/` contra su binario y detecta dos formas de quedar
viejo:

  1. **el build no recompiló** — el `.so` es más viejo que algún fuente de `Source/`;
  2. **el editor estaba abierto** — UBT no puede reemplazar el `.so` tomado y linkea un módulo de
     *hot reload* (`…-0001.so`). El editor corriendo lo levanta, pero el binario BASE queda viejo:
     la próxima vez que se abra de cero, carga el código anterior.

La 2 es la traicionera, porque en el momento parece que funcionó.
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
MOTOR = Path(os.environ.get("JAM_UE", Path.home() / "Dev/engines/UnrealEngine_5.8"))
PROYECTO = Path(os.environ.get("JAM_PROYECTO", Path.home() / "Dev/games/BotOO/BotOO.uproject"))
BINARIOS = RAIZ / "Binaries/Linux"


def editor_abierto() -> bool:
    """El editor toma el `.so`; con él abierto, UBT linkea un módulo de hot reload."""
    try:
        salida = subprocess.run(["pgrep", "-af", "UnrealEditor "],
                                capture_output=True, text=True, check=False).stdout
    except FileNotFoundError:
        return False
    return any(str(PROYECTO.name) in linea for linea in salida.splitlines())


def fuente_mas_nueva(modulo: Path) -> tuple[Path | None, float]:
    """El `.cpp`/`.h`/`.cs` más reciente de un módulo."""
    ultima, cuando = None, 0.0
    for ruta in modulo.rglob("*"):
        if ruta.suffix in (".cpp", ".h", ".cs") and ruta.is_file():
            t = ruta.stat().st_mtime
            if t > cuando:
                ultima, cuando = ruta, t
    return ultima, cuando


def compilar() -> bool:
    build = MOTOR / "Engine/Build/BatchFiles/Linux/Build.sh"
    if not build.exists():
        print(f"✗ no encuentro el motor en {MOTOR}\n  (se puede fijar con JAM_UE=/ruta/al/motor)")
        return False
    # -NoUBA es obligatorio: el acelerador se rompe con el symlink Plugins/Jam (ver AGENTS.md).
    cmd = [str(build), "BotOOEditor", "Linux", "Development",
           f"-Project={PROYECTO}", "-WaitMutex", "-FromMsBuild", "-NoUBA"]
    print("· compilando…")
    proc = subprocess.run(cmd, capture_output=True, text=True, check=False)
    hizo_algo = False
    for linea in proc.stdout.splitlines():
        # Las líneas que distinguen un build que trabajó de uno que no. Filtrar sólo por
        # `error:|Result:` las esconde — que es como se escapó la primera vez.
        if any(m in linea for m in ("] Compile ", "] Link ", "Target is up to date", "error:")):
            print(f"    {linea.strip()}")
            hizo_algo = hizo_algo or "] Compile " in linea or "] Link " in linea
    if proc.returncode != 0:
        print(f"✗ el build falló (código {proc.returncode})")
        print(proc.stdout[-2000:])
        return False
    if not hizo_algo:
        print("  (no había nada que recompilar)")
    return True


def verificar() -> bool:
    modulos = sorted(ruta for ruta in (RAIZ / "Source").iterdir() if ruta.is_dir())
    todo_al_dia = True
    print()
    for modulo in modulos:
        fuente, t_fuente = fuente_mas_nueva(modulo)
        base = BINARIOS / f"libUnrealEditor-{modulo.name}.so"
        print(f"  {modulo.name}")
        print(f"    fuente más nueva : {fuente.relative_to(RAIZ) if fuente else '(ninguna)'}")
        print(f"    binario base     : {base.name}")
        if not base.exists():
            print("    ✗ no existe: el módulo nunca se compiló")
            todo_al_dia = False
            continue

        t_base = base.stat().st_mtime
        hot = sorted(BINARIOS.glob(f"libUnrealEditor-{modulo.name}-[0-9]*.so"))
        hot_nuevo = [ruta for ruta in hot if ruta.stat().st_mtime > t_base]
        if hot_nuevo:
            print("    ✗ hay hot reload más nuevo: " + ", ".join(ruta.name for ruta in hot_nuevo))
            todo_al_dia = False
        elif t_base < t_fuente:
            print("    ✗ el binario está viejo")
            todo_al_dia = False
        else:
            print("    ✓ al día")

    if todo_al_dia:
        print("\n✓ AL DÍA — todos los módulos tienen sus cambios.")
        return True
    print("\n✗ HAY MÓDULOS VIEJOS O DE HOT RELOAD.")
    print("  → cerrá el editor, compilá otra vez y comprobá los binarios base.")
    return False


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--solo-ver", action="store_true", help="no compila, sólo verifica")
    args = ap.parse_args()

    if not args.solo_ver:
        if editor_abierto():
            print("⚠ el editor está ABIERTO.")
            print("  UBT no va a poder reemplazar el binario base y va a linkear un módulo de hot")
            print("  reload. Sirve para la sesión abierta, pero el binario base queda viejo.")
            print("  Para dejarlo bien, cerrá el editor y volvé a correr esto.\n")
        if not compilar():
            return 1
    return 0 if verificar() else 1


if __name__ == "__main__":
    raise SystemExit(main())
