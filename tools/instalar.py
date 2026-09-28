"""Instala Jam en un proyecto de Unreal, Godot o Unity, en ESTA máquina. Sólo biblioteca estándar.

    git clone git@github.com:Segtem/jam.git
    python jam/tools/instalar.py <carpeta del proyecto> [--copiar]

Reconoce el motor por lo que hay en la carpeta (`*.uproject`, `project.godot`,
`ProjectSettings/ProjectVersion.txt`) y:

- Unreal: `Plugins/Jam` → este repo. Al abrir el `.uproject`, Unreal ofrece compilar JamEditor y
  JamMass (hace falta el toolchain de C++ de UE 5.8).
- Godot:  `addons/jam` → `Godot/addons/jam`, el plugin activado, y en `project.godot` la ruta del
  núcleo y el Python que lo corre (`[jam] nucleo_python`, `python`).
- Unity:  `Assets/Jam` → `Unity/Assets/Jam`, y `ProjectSettings/JamNucleo.json` con lo mismo.

Por defecto ENLAZA (symlink; en Windows, si no hay permiso, una junction), así un `git pull` del repo
actualiza el proyecto. `--copiar` copia en cambio: el proyecto queda independiente del repo.
El Python con el que se corre este script es el que usarán Godot y Unity para el núcleo (≥ 3.11).
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

JAM = Path(__file__).resolve().parents[1]
NUCLEO = JAM / "Content" / "Python"
PYTHON_MINIMO = (3, 11)
PLUGIN_GODOT = "res://addons/jam/plugin.cfg"


class ErrorInstalacion(RuntimeError):
    pass


def motor_de(proyecto: Path) -> str:
    if list(proyecto.glob("*.uproject")):
        return "unreal"
    if (proyecto / "project.godot").is_file():
        return "godot"
    if (proyecto / "ProjectSettings" / "ProjectVersion.txt").is_file():
        return "unity"
    raise ErrorInstalacion(f"{proyecto} no parece un proyecto de Unreal (*.uproject), Godot "
                           "(project.godot) ni Unity (ProjectSettings/ProjectVersion.txt)")


def enlazar(fuente: Path, destino: Path, copiar: bool) -> str:
    """Deja `destino` apuntando a `fuente` (o una copia). Devuelve cómo lo hizo."""
    if destino.is_symlink() or destino.exists():
        if destino.is_symlink() and destino.resolve() == fuente.resolve() and not copiar:
            return "ya estaba enlazado"
        if destino.is_symlink() or (destino.is_dir() and _es_junction(destino)):
            destino.unlink() if destino.is_symlink() else os.rmdir(destino)
        else:
            raise ErrorInstalacion(f"{destino} ya existe y no es un enlace: movelo o borralo a mano "
                                   "(no piso una carpeta con contenido)")
    destino.parent.mkdir(parents=True, exist_ok=True)
    if copiar:
        shutil.copytree(fuente, destino, ignore=shutil.ignore_patterns(
            ".git", "__pycache__", "*.pyc", "tareas", "Vault-kb", "Binaries", "Intermediate", "Saved"))
        return "copiado"
    try:
        os.symlink(fuente, destino, target_is_directory=True)
        return "enlazado"
    except OSError:
        if os.name != "nt":
            raise
        # Windows sin modo desarrollador: una junction no pide permisos de administrador.
        subprocess.run(["cmd", "/c", "mklink", "/J", str(destino), str(fuente)], check=True,
                       capture_output=True)
        return "enlazado (junction)"


def _es_junction(p: Path) -> bool:
    try:
        return bool(os.readlink(p))
    except OSError:
        return False


def _ruta(p: Path) -> str:
    """Una ruta con barras normales: la leen igual Godot, Unity y Python en cualquier sistema."""
    return str(p).replace("\\", "/")


# ---------------------------------------------------------------- Godot

def configurar_godot(texto: str, nucleo: str, python: str) -> str:
    """`project.godot` con el plugin activado y la sección [jam]. Idempotente."""
    lineas = texto.splitlines()

    def seccion(nombre: str) -> tuple[int, int]:
        ini = next((i for i, l in enumerate(lineas) if l.strip() == f"[{nombre}]"), -1)
        if ini < 0:
            return -1, -1
        fin = next((i for i in range(ini + 1, len(lineas)) if lineas[i].startswith("[")), len(lineas))
        return ini, fin

    ini, fin = seccion("editor_plugins")
    if ini < 0:
        lineas += ["", "[editor_plugins]", "", f'enabled=PackedStringArray("{PLUGIN_GODOT}")']
    else:
        i = next((k for k in range(ini, fin) if lineas[k].startswith("enabled=")), -1)
        if i < 0:
            lineas.insert(ini + 1, f'enabled=PackedStringArray("{PLUGIN_GODOT}")')
        elif PLUGIN_GODOT not in lineas[i]:
            actuales = re.findall(r'"([^"]*)"', lineas[i])
            lineas[i] = "enabled=PackedStringArray(" + ", ".join(
                f'"{a}"' for a in actuales + [PLUGIN_GODOT]) + ")"
    ini, fin = seccion("jam")
    nuevas = [f"nucleo_python={json.dumps(nucleo)}", f"python={json.dumps(python)}"]
    if ini < 0:
        lineas += ["", "[jam]", ""] + nuevas
    else:
        cuerpo = [l for l in lineas[ini + 1:fin] if not l.startswith(("nucleo_python=", "python="))]
        lineas[ini + 1:fin] = [""] + [c for c in cuerpo if c.strip()] + nuevas + [""]
    return "\n".join(lineas).rstrip("\n") + "\n"


# ---------------------------------------------------------------- instalación

def verificar_nucleo(python: str) -> None:
    """El núcleo tiene que importar SIN Unreal con el Python que lo va a correr."""
    r = subprocess.run([python, "-c", "import sys; sys.modules['unreal'] = None; "
                        f"sys.path.insert(0, {json.dumps(_ruta(NUCLEO))}); import jam.servidor"],
                       capture_output=True, text=True)
    if r.returncode != 0:
        raise ErrorInstalacion(f"el núcleo no carga con {python}:\n{r.stderr[-800:]}")


def instalar(proyecto: Path, copiar: bool = False, python: str | None = None) -> dict:
    python = python or sys.executable
    if sys.version_info < PYTHON_MINIMO:
        raise ErrorInstalacion(f"hace falta Python {'.'.join(map(str, PYTHON_MINIMO))} o más; "
                               f"este es {sys.version.split()[0]}")
    motor = motor_de(proyecto)
    verificar_nucleo(python)
    nucleo = _ruta(NUCLEO if not copiar else proyecto / _destino(motor) / "_nucleo")
    if motor == "unreal":
        como = enlazar(JAM, proyecto / "Plugins" / "Jam", copiar)
        pasos = ["Abrí el .uproject: Unreal va a ofrecer compilar JamEditor y JamMass → Sí "
                 "(necesita el toolchain de C++ de UE 5.8).",
                 "En el editor: menú de herramientas → «Jam: editor de nodos (web)»."]
    elif motor == "godot":
        como = enlazar(JAM / "Godot" / "addons" / "jam", proyecto / "addons" / "jam", copiar)
        if copiar:
            enlazar(NUCLEO, proyecto / "addons" / "jam" / "_nucleo", True)
        archivo = proyecto / "project.godot"
        archivo.write_text(configurar_godot(archivo.read_text(encoding="utf-8"), nucleo, python),
                           encoding="utf-8")
        pasos = ["Abrí el proyecto en Godot 4.7: el plugin Jam queda activado.",
                 "Proyecto ▸ Herramientas → «Jam: editor de nodos»."]
    else:
        como = enlazar(JAM / "Unity" / "Assets" / "Jam", proyecto / "Assets" / "Jam", copiar)
        if copiar:
            enlazar(NUCLEO, proyecto / "Assets" / "Jam" / "_nucleo~", True)   # «~»: Unity lo ignora
            nucleo = _ruta(proyecto / "Assets" / "Jam" / "_nucleo~")
        (proyecto / "ProjectSettings" / "JamNucleo.json").write_text(
            json.dumps({"nucleo_python": nucleo, "python": python}, indent=1), encoding="utf-8")
        pasos = ["Abrí el proyecto en Unity 6 (6000.3): compila el adaptador solo.",
                 "Menú Jam → «Editor de nodos (web)»."]
    return {"motor": motor, "plugin": como, "nucleo": nucleo, "python": python, "pasos": pasos}


def _destino(motor: str) -> str:
    return {"unreal": "Plugins/Jam", "godot": "addons/jam", "unity": "Assets/Jam"}[motor]


def main(argv=None) -> int:
    a = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    a.add_argument("proyecto", type=Path)
    a.add_argument("--copiar", action="store_true", help="copiar en vez de enlazar")
    a.add_argument("--python", help="el Python que correrá el núcleo (por defecto, éste)")
    args = a.parse_args(argv)
    try:
        r = instalar(args.proyecto.expanduser().resolve(), args.copiar, args.python)
    except ErrorInstalacion as e:
        print(f"✗ {e}", file=sys.stderr)
        return 1
    print(f"✓ Jam instalado en un proyecto de {r['motor']} ({r['plugin']}).")
    print(f"  núcleo: {r['nucleo']}  ·  python: {r['python']}")
    for paso in r["pasos"]:
        print(f"  → {paso}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
