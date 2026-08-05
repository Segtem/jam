"""Verifica el `_info()` reescrito contra el motor real: esfera cerrada y `casa_madera` (kit
abierto), de punta a punta a través de las funciones públicas de `jam.mesh` — no llamadas sueltas.

El veredicto queda en `BotOO.log` con el prefijo `JAM_INFO_LIMPIO_58`.
"""
from __future__ import annotations

import unreal

from jam import mesh

try:
    esfera = mesh.sphere(radius=100.0, latitude_steps=40, longitude_steps=60)
    if "error" in esfera:
        raise RuntimeError(esfera["error"])
    unreal.log(f"JAM_INFO_LIMPIO_58 — esfera: {esfera['info']}")

    simple = mesh.simplify_count(esfera["mesh"], target_triangles=500, preserve_seams=False)
    if "error" in simple:
        raise RuntimeError(simple["error"])
    unreal.log(f"JAM_INFO_LIMPIO_58 — esfera simplificada: {simple['info']}")

    kit = mesh.copy_static("/Game/KitCasas/casa_madera/casa_madera.casa_madera")
    if "error" in kit:
        raise RuntimeError(kit["error"])
    unreal.log(f"JAM_INFO_LIMPIO_58 — casa_madera: {kit['info']}")

    unreal.log("JAM_INFO_LIMPIO_58 TODO VERDE")
except Exception as exc:  # noqa: BLE001
    unreal.log_error(f"JAM_INFO_LIMPIO_58 ROJO — {type(exc).__name__}: {exc}")
finally:
    unreal.SystemLibrary.quit_editor()
