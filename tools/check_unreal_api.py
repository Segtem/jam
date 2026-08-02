"""Verifica contra el editor REAL que cada API de Unreal que llama Jam exista.

La suite headless mockea `unreal`, así que un nombre mal escrito la pasa entera y recién explota en
mitad de un Run. Pasó con `GeometryScript_UVs.scale_mesh_uvs`: el nombre real es `scale_mesh_u_vs`
porque el mangler de UE parte `UVs` en `U` + `Vs` (y `IDs` en `I` + `Ds`). Este script cierra ese
agujero: extrae tanto los símbolos de primer nivel (`unreal.Vector`,
`unreal.get_editor_subsystem`) como los `unreal.Clase.metodo` del código de Jam y comprueba cada
uno en un editor vivo.

    UnrealEditor-Cmd <proyecto>.uproject -run=pythonscript \
        -script=<plugin>/tools/check_unreal_api.py -RenderOffScreen -unattended -nosplash -stdout

Sale con código 1 y lista los faltantes si alguno no existe.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

# `unreal` se importa DENTRO de main(): así el extractor se puede probar headless, sin motor.

# Todo símbolo de primer nivel: clases, enums, constructores y funciones del módulo.
PATRON_SIMBOLO = re.compile(r"\bunreal\.([A-Za-z_][A-Za-z_0-9]*)\b")

# `unreal.Clase.metodo`, sólo métodos en snake_case (descarta constantes y valores de enum).
PATRON_LLAMADA = re.compile(
    r"\bunreal\.([A-Za-z_][A-Za-z_0-9]*)\.([a-z_][a-z_0-9]*)\b")


def raiz_jam() -> Path:
    return Path(__file__).resolve().parents[1] / "Content" / "Python" / "jam"


def _lineas_fuente(raiz: Path):
    """Entrega `(archivo, número, línea)` ignorando comentarios completos."""
    for archivo in sorted(raiz.glob("*.py")):
        for numero, linea in enumerate(archivo.read_text(encoding="utf-8").splitlines(), 1):
            if not linea.lstrip().startswith("#"):
                yield archivo, numero, linea


def simbolos(raiz: Path) -> dict[str, list[str]]:
    """`{símbolo: [archivo:línea, …]}` de todo lo que Jam busca en el módulo Unreal."""
    encontrados: dict[str, list[str]] = {}
    for archivo, numero, linea in _lineas_fuente(raiz):
        for simbolo in PATRON_SIMBOLO.findall(linea):
            encontrados.setdefault(simbolo, []).append(f"{archivo.name}:{numero}")
    return encontrados


def llamadas(raiz: Path) -> dict[tuple[str, str], list[str]]:
    """{(clase, metodo): [archivo:linea, …]} de todo lo que Jam le pide a Unreal."""
    encontrado: dict[tuple[str, str], list[str]] = {}
    for archivo, numero, linea in _lineas_fuente(raiz):
        for clase, metodo in PATRON_LLAMADA.findall(linea):
            encontrado.setdefault((clase, metodo), []).append(f"{archivo.name}:{numero}")
    return encontrado


def main() -> int:
    import unreal

    raiz = raiz_jam()
    objetivo_simbolos = simbolos(raiz)
    objetivo = llamadas(raiz)
    faltantes: list[str] = []
    simbolos_faltantes = [
        f"unreal.{simbolo}  ← {', '.join(lugares)}"
        for simbolo, lugares in sorted(objetivo_simbolos.items())
        if not hasattr(unreal, simbolo)
    ]

    for (clase, metodo), lugares in sorted(objetivo.items()):
        tipo = getattr(unreal, clase, None)
        if tipo is None:
            # Ya aparece, con todos sus usos, en `simbolos_faltantes`.
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

    unreal.log(
        f"[check-api] {len(objetivo_simbolos)} símbolos y {len(objetivo)} llamadas distintas "
        f"a Unreal desde {raiz}")
    if simbolos_faltantes:
        unreal.log_error(f"[check-api] {len(simbolos_faltantes)} símbolo(s) inexistentes:")
        for linea in simbolos_faltantes:
            unreal.log_error("  " + linea)
    if faltantes:
        unreal.log_error(f"[check-api] {len(faltantes)} método(s) inexistentes:")
        for linea in faltantes:
            unreal.log_error("  " + linea)
    if not faltantes and not simbolos_faltantes:
        unreal.log("[check-api] ✓ todas existen en este motor")
        return 0
    return 1


if __name__ == "__main__":
    sys.exit(main())
