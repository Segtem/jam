"""Puente a los oráculos — pone sus dos raíces en el sys.path del intérprete de Unreal.

Los oráculos históricos viven en la RAÍZ del plugin (`<plugin>/oraculo/`) y Oracle es el paquete
`oracle-metalenguaje` de PyPI, vendorizado como wheel en `<plugin>/vendor/oracle-pkg/`. Esa copia
existe porque el intérprete embebido de Unreal es el suyo: no ve el entorno de `uv`, ni el del
sistema, ni un venv del proyecto. Este archivo está en `<plugin>/Content/Python/jam/bridge.py`, así
que la raíz del plugin son 3 niveles arriba. Resolvemos symlinks (el plugin suele estar linkeado
dentro de `BotOO/Plugins/Jam` → `~/Dev/jam`) para que ambos imports caigan en el repo real.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

PLUGIN_ROOT = Path(__file__).resolve().parents[3]
ORACULO_ROOT = PLUGIN_ROOT  # `import oraculo.*` cuelga de la raíz del plugin
ORACLE_PACKAGE_ROOT = PLUGIN_ROOT / "vendor" / "oracle-pkg"


def python_del_motor() -> Path | None:
    """El `python3` que trae Unreal junto al editor, o None fuera de Unreal.

    En el intérprete embebido `sys.executable` es `UnrealEditor`, no un Python, y Oracle lanza con
    un Python el proceso aislado que corre `medidas/escalares.py`: sin decirle cuál, ninguna medida
    con escalares propias se evaluaba dentro del editor (tarea `oracle-escalares-embebido`)."""
    ejecutable = Path(sys.executable)
    if not ejecutable.name.startswith("UnrealEditor"):
        return None
    tercero = ejecutable.resolve().parents[1] / "ThirdParty" / "Python3"
    python = tercero / ("Win64/python.exe" if os.name == "nt" else "Linux/bin/python3")
    return python if python.is_file() else None


def ensure_oraculo_on_path() -> Path:
    """Garantiza los imports históricos y `oracle_metalenguaje`; devuelve la raíz del plugin."""
    for ruta in (ORACULO_ROOT, ORACLE_PACKAGE_ROOT):
        root = str(ruta)
        if root not in sys.path:
            sys.path.insert(0, root)
    python = python_del_motor()
    if python is not None:
        os.environ.setdefault("ORACLE_PYTHON", str(python))
    return PLUGIN_ROOT
