"""PCG — realizar un scatter con el PCG nativo de Unreal, dirigido por un preset de Jam.

Es el último eslabón del pipeline: tools → presets → **PCG usando presets**. En vez de spawnear
cientos de actores sueltos, Jam construye un grafo PCG (superficie → sampler → spawner con HISM) y lo
mete en un PCGVolume: rendimiento nativo, no-destructivo, regenerable. La AUTORÍA del grafo es de Jam
(Dash ni siquiera integra PCG); el preset es la receta.

El grafo se arma desde cero por cada realización (nombre determinista por preset, se sobrescribe al
reaplicar). Gotchas del spike (documentados en tools/experiments/pcg_spike.py): `add_edge` NO lanza si
el pin no existe (loguea y sigue) → se verifica por `pin.edges`; etiquetas reales In/Out (la SALIDA
entra por «Out»); el nodo de entrada no tiene pin «Landscape» (va un PCGGetLandscape aparte); la
generación es ASINCRÓNICA (contar en la misma línea da 0 — hay que dejar correr frames).
"""

from __future__ import annotations

import re

import unreal

from . import library

CARPETA = "/Game/JamPCG"


def _slug(nombre: str) -> str:
    return re.sub(r"[^A-Za-z0-9]+", "_", nombre).strip("_") or "JamPCG"


def _pin(nodo, prop, label):
    for p in nodo.get_editor_property(prop):
        if str(p.get_editor_property("properties").get_editor_property("label")) == label:
            return p
    return None


def _conectar(grafo, a, la, b, lb) -> bool:
    """Conecta y VERIFICA (add_edge sólo loguea si el pin no existe)."""
    grafo.add_edge(a, la, b, lb)
    p = _pin(a, "output_pins", la)
    return bool(p and len(p.get_editor_property("edges")) > 0)


def construir_grafo(nombre: str, mallas: list, *, density: float) -> tuple:
    """Arma (o rehace) el grafo PCG: GetLandscape → SurfaceSampler → StaticMeshSpawner(mallas).
    `density` = puntos por m². Devuelve (grafo, cables_ok:int)."""
    ruta = f"{CARPETA}/{_slug(nombre)}"
    if unreal.EditorAssetLibrary.does_asset_exist(ruta):
        unreal.EditorAssetLibrary.delete_asset(ruta)
    grafo = unreal.AssetToolsHelpers.get_asset_tools().create_asset(
        _slug(nombre), CARPETA, unreal.PCGGraph, unreal.PCGGraphFactory())

    land, _l = grafo.add_node_of_type(unreal.PCGGetLandscapeSettings)
    samp_n, samp = grafo.add_node_of_type(unreal.PCGSurfaceSamplerSettings)
    spaw_n, spaw = grafo.add_node_of_type(unreal.PCGStaticMeshSpawnerSettings)

    cables = sum([
        _conectar(grafo, land, "Out", samp_n, "Surface"),
        _conectar(grafo, grafo.get_input_node(), "In", samp_n, "Bounding Shape"),
        _conectar(grafo, samp_n, "Out", spaw_n, "In"),
        _conectar(grafo, spaw_n, "Out", grafo.get_output_node(), "Out"),
    ])

    samp.set_editor_property("points_per_squared_meter", max(0.0001, density))

    # selector de malla ponderado (una o varias mallas, como el kit del scatter)
    spaw.set_mesh_selector_type(unreal.PCGMeshSelectorWeighted)
    sel = spaw.get_editor_property("mesh_selector_parameters")
    entradas = []
    for m in mallas:
        e = unreal.PCGMeshSelectorWeightedEntry()
        d = e.get_editor_property("descriptor")
        d.set_editor_property("static_mesh", m)
        e.set_editor_property("descriptor", d)
        e.set_editor_property("weight", 1)
        entradas.append(e)
    sel.set_editor_property("mesh_entries", entradas)

    unreal.EditorAssetLibrary.save_asset(ruta, only_if_is_dirty=False)
    return grafo, cables


def realizar(assets, *, nombre="JamPCG", area=1600.0, density=0.0, count=0, centro=None,
             view=True) -> dict:
    """Realiza el scatter como PCG: arma el grafo, pone un PCGVolume en el punto de mira (o `centro`),
    lo escala a `area`, le asigna el grafo y lo genera. `density` en pts/m²; si es 0 se deriva de
    `count` sobre el área. La generación es asíncrona: el conteo se lee después (por eso devuelve el
    volumen para verificar más tarde). Devuelve {volumen, grafo, cables, density, error?}."""
    from . import ue
    rutas = [assets] if isinstance(assets, str) else list(assets)
    mallas = [m for m in (library.cargar_malla(r) for r in rutas) if m is not None]
    if not mallas:
        return {"error": f"ningún asset cargable en {rutas!r}"}

    # densidad: de count/area si no se da. area es semilado en cm → lado_m = 2*area/100.
    if density <= 0.0:
        lado_m = max(0.01, 2.0 * area / 100.0)
        density = max(0.0001, (count or 40) / (lado_m * lado_m))

    grafo, cables = construir_grafo(nombre, mallas, density=density)

    # centro: punto de mira (como las demás tools) salvo que se pase explícito
    cx, cy, cz = 0.0, 0.0, 200.0
    if centro is not None:
        cx, cy = centro[0], centro[1]
    elif view:
        mira = ue.punto_de_mira()
        if mira and mira["punto"]:
            cx, cy, cz = mira["punto"].x, mira["punto"].y, mira["punto"].z + 200.0

    sub = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    vol = sub.spawn_actor_from_class(unreal.PCGVolume, unreal.Vector(cx, cy, cz))
    vol.set_actor_label(f"JamPCG_{_slug(nombre)}")
    escala = max(1.0, area / 100.0)   # el volumen por defecto es ~100cm; escalar al área
    vol.set_actor_scale3d(unreal.Vector(escala, escala, 2.0))
    comp = vol.get_component_by_class(unreal.PCGComponent)
    comp.set_graph(grafo)
    comp.generate(True)
    return {"volumen": vol, "grafo": grafo, "cables": cables, "density": round(density, 4),
            "assets": len(mallas)}


def contar_instancias(vol=None) -> int:
    """Instancias HISM en el nivel (para el oráculo). El PCG cuelga el HISM de distintos actores según
    el modo (el volumen, un PCGPartitionActor, o un actor generado): se recorren TODOS los actores y
    se suman sus InstancedStaticMeshComponent — como el spike verificado."""
    sub = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    total = 0
    for a in sub.get_all_level_actors():
        try:
            for c in a.get_components_by_class(unreal.InstancedStaticMeshComponent):
                total += c.get_instance_count()
        except Exception:  # noqa: BLE001
            continue
    return total
