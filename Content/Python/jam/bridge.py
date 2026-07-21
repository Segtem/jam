"""Puente al oráculo — pone `oraculo/` en el sys.path del intérprete de Unreal.

El oráculo vive en la RAÍZ del plugin (`<plugin>/oraculo/`), hermano de `Content/`.
Este archivo está en `<plugin>/Content/Python/jam/bridge.py`, así que la raíz del
plugin son 3 niveles arriba. Resolvemos symlinks (el plugin suele estar linkeado
dentro de `BotOO/Plugins/Jam` → `~/Dev/jam`) para que el import caiga en el repo real.
"""

from __future__ import annotations

import sys
from pathlib import Path

PLUGIN_ROOT = Path(__file__).resolve().parents[3]
ORACULO_ROOT = PLUGIN_ROOT  # `import oraculo.*` cuelga de la raíz del plugin


def ensure_oraculo_on_path() -> Path:
    """Garantiza que `import oraculo.*` funcione. Devuelve la raíz del plugin."""
    root = str(ORACULO_ROOT)
    if root not in sys.path:
        sys.path.insert(0, root)
    return PLUGIN_ROOT
