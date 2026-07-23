"""EXPERIMENTO: ¿puede Jam COLOCAR un PCG, como coloca una malla? — SÍ. Y además AUTORARLO.

Este script es la prueba reproducible (2026-07-23, UE 5.7.4, plugin PCG ya activo en BotOO):
Jam fabrica un grafo PCG desde cero, lo asigna a un PCGVolume puesto en el PUNTO DE MIRA, lo genera,
y un oráculo cuenta lo que salió. Resultado medido: **124 instancias**.

    GetLandscape.Out → sampler.Surface · Input.In → sampler.«Bounding Shape»
    sampler.Out → spawner.In · spawner.Out → Output.Out

Correr:
    UnrealEditor BotOO.uproject -RenderOffScreen -unattended -nosplash \
        -ExecCmds="py <ruta>/pcg_spike.py"
(no lleva QUIT_EDITOR en -ExecCmds: el script se cierra solo tras 200 frames, porque PCG genera
asincrónico y hay que dejar correr el loop).

GOTCHAS que costaron encontrar:
  · `graph.add_edge(...)` NO lanza excepción si el pin no existe: **loguea el error y sigue**. Hay
    que VERIFICAR el cable mirando `pin.edges` — si no, uno cree que cableó y no cableó nada.
  · Las etiquetas reales de los pines: el nodo de ENTRADA saca por «In», el de SALIDA entra por
    «Out» (no «In»), y el sampler pide «Surface» + «Bounding Shape».
  · El nodo de entrada NO tiene pin «Landscape»: la superficie se trae con un nodo
    `PCGGetLandscapeSettings` aparte.
  · La generación es ASINCRÓNICA: llamar `generate(True)` y contar en la misma línea da 0. Hay que
    dejar pasar frames (acá, un callback de Slate post-tick).
  · `PCGComponent` no expone `get_graph` ni `is_partitioned` a Python (sí `set_graph`, `generate`,
    `generate_local`, `cleanup`).

NO es una herramienta de Jam todavía: según el orden acordado (tools → presets → PCG usando
presets), esto va al final. Queda acá como prueba de que el camino está abierto.
"""
import unreal

import jam.library as library
import jam.ue as ue

def log(m): print(f"[E5] {m}")

CARPETA, NOMBRE = "/Game/JamPCG", "PCG_JamScatter"
RUTA = f"{CARPETA}/{NOMBRE}"
if unreal.EditorAssetLibrary.does_asset_exist(RUTA):
    unreal.EditorAssetLibrary.delete_asset(RUTA)

grafo = unreal.AssetToolsHelpers.get_asset_tools().create_asset(
    NOMBRE, CARPETA, unreal.PCGGraph, unreal.PCGGraphFactory())
land_node, _land = grafo.add_node_of_type(unreal.PCGGetLandscapeSettings)
samp_node, samp = grafo.add_node_of_type(unreal.PCGSurfaceSamplerSettings)
spaw_node, spaw = grafo.add_node_of_type(unreal.PCGStaticMeshSpawnerSettings)


def pin(nodo, prop, label):
    for p in nodo.get_editor_property(prop):
        if str(p.get_editor_property("properties").get_editor_property("label")) == label:
            return p
    return None


def conectar(a, la, b, lb) -> bool:
    """Conecta y VERIFICA (add_edge sólo loguea si el pin no existe)."""
    grafo.add_edge(a, la, b, lb)
    p = pin(a, "output_pins", la)
    ok = bool(p and len(p.get_editor_property("edges")) > 0)
    log(f"   {'✓' if ok else '✗'} {la} → {lb}")
    return ok


cables = [
    conectar(land_node, "Out", samp_node, "Surface"),
    conectar(grafo.get_input_node(), "In", samp_node, "Bounding Shape"),
    conectar(samp_node, "Out", spaw_node, "In"),
    conectar(spaw_node, "Out", grafo.get_output_node(), "Out"),
]
log(f"1 cables conectados: {sum(cables)}/4")

samp.set_editor_property("points_per_squared_meter", 0.5)
ASSET = library.buscar("SM_", limit=1)[0]
malla = unreal.load_asset(ASSET["ruta"])
spaw.set_mesh_selector_type(unreal.PCGMeshSelectorWeighted)
sel = spaw.get_editor_property("mesh_selector_parameters")
e = unreal.PCGMeshSelectorWeightedEntry()
d = e.get_editor_property("descriptor")
d.set_editor_property("static_mesh", malla)
e.set_editor_property("descriptor", d)
e.set_editor_property("weight", 1)
sel.set_editor_property("mesh_entries", [e])
unreal.EditorAssetLibrary.save_asset(RUTA, only_if_is_dirty=False)
log(f"2 grafo: 3 nodos, malla = {ASSET['nombre']}, densidad 0.5 pts/m²")

sub = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
mira = ue.punto_de_mira()
p = mira["punto"] if mira else unreal.Vector(0, 0, 0)
vol = sub.spawn_actor_from_class(unreal.PCGVolume, unreal.Vector(p.x, p.y, p.z + 200.0))
vol.set_actor_label("Jam_PCG_test")
vol.set_actor_scale3d(unreal.Vector(8.0, 8.0, 2.0))
comp = vol.get_component_by_class(unreal.PCGComponent)
comp.set_graph(grafo)
comp.generate(True)
log(f"3 volumen colocado en la mira ({p.x:.0f},{p.y:.0f}) de 1600×1600cm · generate lanzado")

ESTADO = {"n": 0}


def contar():
    total = 0
    for a in sub.get_all_level_actors():
        try:
            for c in a.get_components_by_class(unreal.InstancedStaticMeshComponent):
                total += c.get_instance_count()
        except Exception:  # noqa: BLE001
            continue
    return total


def tick(_d):
    ESTADO["n"] += 1
    n = ESTADO["n"]
    if n in (15, 60, 120, 200):
        log(f"4 frame {n}: {contar()} instancias")
    if n >= 200:
        unreal.unregister_slate_post_tick_callback(ESTADO["h"])
        i = contar()
        log(f"5 VEREDICTO: {i} instancias → "
            + ("PCG COLOCADO Y GENERANDO ✓" if i > 0 else "no generó ✗"))
        try:
            sub.destroy_actor(vol)
        except Exception:  # noqa: BLE001
            pass
        log("6 FIN")
        unreal.SystemLibrary.execute_console_command(None, "QUIT_EDITOR")


ESTADO["h"] = unreal.register_slate_post_tick_callback(tick)
