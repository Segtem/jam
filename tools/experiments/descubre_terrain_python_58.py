"""Descubre qué expone Python del plugin `MeshPartition` una vez habilitado en UE 5.8.1.

No verifica ningún contrato: es el paso anterior. `MeshPartitionDefinition.h` declara `Material`
y `ModifierTypePriorities` como `UPROPERTY` simples, así que deberían leerse con
`get_editor_property` sin que hagan falta sus `UFUNCTION`. Pero eso es una lectura del header, no
una comprobación — este script es la comprobación mínima antes de escribir `jam/terrain.py` y la
sonda real `verifica_terrain_definition_58.py`.

Ejecutar sólo DESPUÉS de:
  1. agregar `MeshPartition` a los plugins de `Jam.uplugin` (o `BotOO.uproject`);
  2. recompilar/reiniciar el editor para que el plugin cargue.

El veredicto queda en `BotOO.log` con el prefijo `JAM_TERRAIN_DISCOVERY_58`.
"""

from __future__ import annotations

import unreal

try:
    simbolos = sorted(n for n in dir(unreal) if "MeshPartition" in n or "Terrain" in n)
    if not simbolos:
        raise RuntimeError(
            "ningún símbolo MeshPartition/Terrain en `unreal` — ¿el plugin quedó habilitado y "
            "el editor se reinició?")

    clase_definicion = getattr(unreal, "MeshPartitionDefinition", None)
    tiene_factory = any("MeshPartitionDefinitionFactory" in s for s in simbolos)
    tiene_asset_tools = hasattr(unreal, "AssetToolsHelpers")

    detalle_propiedades = "sin instancia para probar get_editor_property todavía"
    if clase_definicion is not None:
        # Sólo confirma que la CLASE resolvió; get_editor_property necesita una instancia real
        # (un asset creado), que es el siguiente paso una vez exista la factory.
        detalle_propiedades = f"clase resuelta: {clase_definicion}"

    unreal.log(
        "JAM_TERRAIN_DISCOVERY_58 — "
        f"símbolos={simbolos} · "
        f"MeshPartitionDefinition={'sí' if clase_definicion is not None else 'NO'} · "
        f"factory_visible={'sí' if tiene_factory else 'NO'} · "
        f"AssetToolsHelpers={'sí' if tiene_asset_tools else 'NO'} · "
        f"{detalle_propiedades}")
except Exception as exc:  # noqa: BLE001
    unreal.log_error(f"JAM_TERRAIN_DISCOVERY_58 ROJO — {type(exc).__name__}: {exc}")
finally:
    unreal.SystemLibrary.quit_editor()
