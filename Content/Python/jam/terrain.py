"""Adaptador de lectura de Mesh Terrain (``UMeshPartitionDefinition``) para UE 5.8.1.

Toca ``unreal`` y nada más: obtiene los campos del motor y se los pasa a ``terrain_core``, que es
quien decide qué significan. Mismo reparto que ``nanite`` / ``nanite_core``.

**Sólo lee.** No crea ni modifica definiciones, y es a propósito: la sonda
``descubre_terrain_python_58.py`` confirmó que el plugin **no expone una factory**
(``MeshPartitionDefinitionFactory=NO``), así que crear el asset desde Python por la vía normal
(``AssetTools.create_asset``) no está disponible en 5.8.1. Escribir un creador «como se pueda» sería
inventar un camino que el motor no ofrece.

Alcance de la lectura: ``Material`` y ``ModifierTypePriorities``, los dos únicos campos de
``UMeshPartitionDefinition`` que son ``UPROPERTY`` simples. ``ChannelMap`` y
``CompiledSectionBuildVariants`` son structs C++ propios del plugin y su forma del lado de Python no
está verificada — se agregan cuando una sonda lo confirme, no antes.

Verificado por ``tools/experiments/verifica_terrain_definition_58.py``
(``JAM_TERRAIN_DEFINICION_58 TODO VERDE``): ``get_editor_property`` devuelve las dos propiedades y
``terrain_core`` acepta la forma resultante.
"""

from __future__ import annotations

import unreal

from . import terrain_core


CLASE = unreal.TopLevelAssetPath("/Script/MeshPartition", "MeshPartitionDefinition")


def _cargar(asset):
    """Acepta una ruta o una definición ya cargada, igual que el resto de los verbos."""
    if isinstance(asset, str):
        cargado = unreal.EditorAssetLibrary.load_asset(asset)
        if cargado is None:
            raise ValueError(f"no pude cargar la definición de terreno: {asset}")
        return cargado
    return asset


def definiciones() -> list[str]:
    """Rutas de todas las definiciones de terreno del proyecto.

    Existe porque el caso más probable es que no haya ninguna: el plugin no expone factory, así que
    las crea un humano desde el editor. Un verbo que no encuentra nada tiene que poder decir *por
    qué* en vez de fallar como si el asset estuviera roto.
    """
    registro = unreal.AssetRegistryHelpers.get_asset_registry()
    # `get_assets_by_class` pide un `TopLevelAssetPath`, no un string (ver `library._SM_CLASS`).
    return [str(a.package_name) for a in registro.get_assets_by_class(CLASE, search_sub_classes=True)]


def medir(asset) -> dict:
    """Lee una definición y la pasa por el juicio puro de ``terrain_core``.

    Devuelve la medida más los defectos que esa medida puede defender. No juzga blending de canales,
    resolución ni el aspecto en el mundo: esos hechos necesitan sensores propios sobre
    ``ACompiledSection`` y el ``ChannelMap``, que todavía no están verificados.
    """
    definicion = _cargar(asset)
    ruta = definicion.get_path_name()

    material = definicion.get_editor_property("Material")
    prioridades = definicion.get_editor_property("ModifierTypePriorities")

    medida = terrain_core.medida(
        asset=ruta,
        material=None if material is None else material.get_path_name(),
        modifier_priorities=[str(p) for p in (prioridades or [])],
    )
    medida["defectos"] = terrain_core.diagnosticar(medida)
    return medida
