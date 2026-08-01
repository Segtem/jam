"""Puente a los oráculos — pone sus dos raíces en el sys.path del intérprete de Unreal.

Los oráculos históricos viven en la RAÍZ del plugin (`<plugin>/oraculo/`) y Oracle se distribuye en
`<plugin>/vendor/oracle/`. Este archivo está en `<plugin>/Content/Python/jam/bridge.py`, así que la
raíz del plugin son 3 niveles arriba. Resolvemos symlinks (el plugin suele estar linkeado dentro de
`BotOO/Plugins/Jam` → `~/Dev/jam`) para que ambos imports caigan en el repo real.
"""

from __future__ import annotations

import sys
from pathlib import Path

PLUGIN_ROOT = Path(__file__).resolve().parents[3]
ORACULO_ROOT = PLUGIN_ROOT  # `import oraculo.*` cuelga de la raíz del plugin
ORACLE_PACKAGE_ROOT = PLUGIN_ROOT / "vendor" / "oracle"


def ensure_oraculo_on_path() -> Path:
    """Garantiza los imports históricos y `oracle_metalenguaje`; devuelve la raíz del plugin."""
    for ruta in (ORACULO_ROOT, ORACLE_PACKAGE_ROOT):
        root = str(ruta)
        if root not in sys.path:
            sys.path.insert(0, root)
    return PLUGIN_ROOT
