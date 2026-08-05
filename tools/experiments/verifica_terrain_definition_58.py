"""Verifica el CONTRATO de lectura de `UMeshPartitionDefinition` desde Python en UE 5.8.1.

`descubre_terrain_python_58.py` ya confirmó que la clase resuelve y que **no hay factory expuesta**
(`MeshPartitionDefinitionFactory=NO`), así que crear el asset desde Python por la vía normal
(`AssetTools.create_asset`) no es una opción. Esto prueba las dos alternativas que quedan, en orden
de preferencia:

  1. Un asset REAL ya existente en el proyecto (lo busca en el AssetRegistry). Es el caso que
     importa: leer lo que el artista construyó.
  2. Una instancia TRANSIENTE (`new_object`). No toca el proyecto y sirve para saber si las
     `UPROPERTY` son legibles, aunque no prueba que un asset en disco se comporte igual.

Lo que se está probando es exactamente lo que `jam/terrain_core.medida()` espera recibir:
`Material` (un objeto o None) y `ModifierTypePriorities` (una lista de nombres). Si esto sale VERDE,
`jam/terrain.py` se puede escribir contra `get_editor_property` sin inventar nada.

No modifica ni guarda ningún asset. El veredicto queda en `BotOO.log` con prefijo
`JAM_TERRAIN_DEFINICION_58`.
"""

from __future__ import annotations

import unreal


try:
    # Ejercita el ADAPTADOR REAL (`jam.terrain`), no una copia paralela: si el script tuviera su
    # propia lectura, podría quedar en verde con el adaptador roto.
    from jam import terrain

    encontrados = terrain.definiciones()

    if encontrados:
        origen = f"asset real: {encontrados[0]}"
        medida = terrain.medir(encontrados[0])
    else:
        # Sin factory expuesta, un proyecto sin definiciones es el caso ESPERADO, no un fallo: las
        # crea un humano desde el editor. La transitoria alcanza para probar el contrato de lectura.
        origen = "instancia transitoria — no hay ninguna definición en el proyecto"
        medida = terrain.medir(unreal.new_object(unreal.MeshPartitionDefinition))

    unreal.log(
        "JAM_TERRAIN_DEFINICION_58 TODO VERDE — "
        f"origen={origen} · "
        f"material={medida['material']} · "
        f"prioridades={medida['modifier_priorities']} · "
        f"definiciones_en_proyecto={len(encontrados)} · "
        f"defectos={medida['defectos']}")
except Exception as exc:  # noqa: BLE001
    unreal.log_error(f"JAM_TERRAIN_DEFINICION_58 ROJO — {type(exc).__name__}: {exc}")
finally:
    unreal.SystemLibrary.quit_editor()
