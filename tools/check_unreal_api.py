"""Verifica contra el editor REAL que cada API de Unreal que llama Jam exista.

La suite headless mockea `unreal`, así que un nombre mal escrito la pasa entera y recién explota en
mitad de un Run. Pasó con `GeometryScript_UVs.scale_mesh_uvs`: el nombre real es `scale_mesh_u_vs`
porque el mangler de UE parte `UVs` en `U` + `Vs` (y `IDs` en `I` + `Ds`). Este script cierra ese
agujero: extrae los `unreal.Clase.metodo` del código de Jam y comprueba cada uno en un editor vivo.

    UnrealEditor-Cmd <proyecto>.uproject -run=pythonscript \
        -script=<plugin>/tools/check_unreal_api.py -RenderOffScreen -unattended -nosplash -stdout

Sale con código 1 y lista los faltantes si alguno no existe.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

# `unreal` se importa DENTRO de main(): así el extractor se puede probar headless, sin motor.

# `unreal.Clase.metodo`, sólo métodos en snake_case (descarta constantes y enums).
PATRON = re.compile(r"\bunreal\.([A-Za-z_][A-Za-z_0-9]*)\.([a-z_][a-z_0-9]*)\b")

# Atributos que no son API del motor sino helpers del módulo Python de UE.
IGNORAR_CLASES = {"log", "log_warning", "log_error"}


def raiz_jam() -> Path:
    return Path(__file__).resolve().parents[1] / "Content" / "Python" / "jam"


def llamadas(raiz: Path) -> dict[tuple[str, str], list[str]]:
    """{(clase, metodo): [archivo:linea, …]} de todo lo que Jam le pide a Unreal."""
    encontrado: dict[tuple[str, str], list[str]] = {}
    for archivo in sorted(raiz.glob("*.py")):
        for numero, linea in enumerate(archivo.read_text(encoding="utf-8").splitlines(), 1):
            if linea.lstrip().startswith("#"):
                continue
            for clase, metodo in PATRON.findall(linea):
                if clase in IGNORAR_CLASES:
                    continue
                encontrado.setdefault((clase, metodo), []).append(f"{archivo.name}:{numero}")
    return encontrado


def main() -> int:
    import unreal

    raiz = raiz_jam()
    objetivo = llamadas(raiz)
    faltantes: list[str] = []
    clases_faltantes: list[str] = []

    for (clase, metodo), lugares in sorted(objetivo.items()):
        tipo = getattr(unreal, clase, None)
        if tipo is None:
            clases_faltantes.append(f"unreal.{clase}  ← {', '.join(lugares)}")
            continue
        if not hasattr(tipo, metodo):
            # Sugerencia: el error casi siempre es el mangler (UVs → u_vs, IDs → i_ds).
            candidatos = [
                nombre for nombre in dir(tipo)
                if not nombre.startswith("_")
                and nombre.replace("_", "") == metodo.replace("_", "")
            ]
            pista = f"  ¿será «{candidatos[0]}»?" if candidatos else ""
            faltantes.append(f"unreal.{clase}.{metodo}{pista}  ← {', '.join(lugares)}")

    unreal.log(f"[check-api] {len(objetivo)} llamadas distintas a Unreal desde {raiz}")
    if clases_faltantes:
        unreal.log_error(f"[check-api] {len(clases_faltantes)} clase(s) inexistentes:")
        for linea in clases_faltantes:
            unreal.log_error("  " + linea)
    if faltantes:
        unreal.log_error(f"[check-api] {len(faltantes)} método(s) inexistentes:")
        for linea in faltantes:
            unreal.log_error("  " + linea)
    if not faltantes and not clases_faltantes:
        unreal.log("[check-api] ✓ todas existen en este motor")
        return 0
    return 1


if __name__ == "__main__":
    sys.exit(main())
