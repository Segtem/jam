"""PCG usando presets + hex/triangular. Se verifica lo DETERMINISTA (grafo bien armado, volumen
colocado, params del preset). El CONTEO de instancias es asíncrono y depende del streaming del
landscape de World Partition en headless → se reporta, no se exige (en editor interactivo genera)."""
import unreal

import jam.api as api
import jam.library as library
import jam.pcg as pcg
import jam.scatter as scatter

def log(m): print(f"[PC] {m}")

sub = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
ASSET = library.buscar("SM_", limit=1)[0]
api.select_asset(ASSET["ruta"])


def es_volumen_jam(actor):
    """Preview conserva el nombre original, pero antepone su propio prefijo al label visible."""
    return isinstance(actor, unreal.PCGVolume) and "JamPCG_" in actor.get_actor_label()


def limpiar_pcg():
    for x in sub.get_all_level_actors():
        if es_volumen_jam(x):
            try: sub.destroy_actor(x)
            except Exception: pass


# 1) hex/triangular en el editor (patrones nuevos del catálogo GH)
for pat in ("hexagonal", "triangular"):
    a, v = scatter.esparcir_rico(ASSET["ruta"], (0,0), (900,900), patron=pat, spacing=250,
                                 seed=1, surface=False)
    log(f"1 patrón {pat}: {v['candidatos']} candidatos → {v['colocados']} colocados")
    for x in a: sub.destroy_actor(x)
    assert v["candidatos"] > 10, "el patrón tiene que generar candidatos"

# 2) verbo pcg: arma el grafo y coloca el PCGVolume (lo DETERMINISTA)
r = pcg.realizar(ASSET["ruta"], nombre="JamTest", area=1600, count=300)
assert "error" not in r, r.get("error")
log(f"2 pcg realizar: {r['cables']}/4 cables, {r['density']} pts/m², volumen={r['volumen'].get_actor_label()}")
assert r["cables"] == 4, "el grafo PCG tiene que quedar cableado (superficie→sampler→spawner→out)"
assert r["volumen"] is not None
# el grafo asset existe y tiene 3 nodos + el spawner con nuestra malla
grafo = r["grafo"]
nodos = len(grafo.get_editor_property("nodes"))
log(f"3 grafo asset: {nodos} nodos")
assert nodos == 3
limpiar_pcg()

# 4) PCG USANDO PRESET: los params del preset de scatter dirigen la realización
r2 = api.run('pcg preset="Escombros densos"')
log("4 pcg preset → " + r2.replace("\n"," | "))
vol = next((x for x in sub.get_all_level_actors() if es_volumen_jam(x)), None)
assert vol is not None and "Escombros" in vol.get_actor_label(), "el preset se realiza como PCG"
# el preset «Escombros densos» tiene area=600 → el veredicto lo refleja
assert "600" in r2, "los params del preset (area 600) dirigen la realización"
log(f"5 preset → volumen «{vol.get_actor_label()}» con el área del preset ✓")
limpiar_pcg()

# 6) conteo (informativo): en headless depende del landscape de WP; en editor interactivo genera
r3 = pcg.realizar(ASSET["ruta"], nombre="JamCount", area=1600, count=300)
BASE = pcg.contar_instancias()
ESTADO = {"n": 0, "base": BASE}
def tick(_d):
    ESTADO["n"] += 1
    if ESTADO["n"] >= 90:
        unreal.unregister_slate_post_tick_callback(ESTADO["h"])
        insts = pcg.contar_instancias() - ESTADO["base"]
        log(f"6 conteo async: {insts} instancias HISM "
            + ("(generó ✓)" if insts > 0 else "(0 — landscape WP no cargado en headless; informativo)"))
        limpiar_pcg()
        log("OK — PCG realiza (grafo+volumen+preset) y hex/triangular; conteo async es informativo")
        unreal.SystemLibrary.execute_console_command(None, "QUIT_EDITOR")
ESTADO["h"] = unreal.register_slate_post_tick_callback(tick)
