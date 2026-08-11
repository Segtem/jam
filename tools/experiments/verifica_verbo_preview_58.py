"""«Ver sin hornear» por el camino REAL del Graph: Compile + Run, contra el mismo grafo horneando."""
import json, time
import unreal
from jam import api, graph

def log(m): unreal.log(f"[VERBO] {m}")
FALLAS = []
def exigir(c, d):
    log(("  OK   " if c else "  FALLA") + f" · {d}")
    if not c: FALLAS.append(d)

def cadena(ultimo):
    return json.dumps({"schema_version": 1, "nodes": {
        "eje": {"verb": "curve_bezier", "params": {"start_x": "0.0", "start_y": "0.0",
                "start_z": "0.0", "end_x": "900.0", "end_y": "0.0", "end_z": "80.0",
                "bend_x": "0.0", "bend_y": "320.0", "bend_z": "-40.0", "segments": "12"},
                "asset": None, "x": 0, "y": 0},
        "cinta": {"verb": "mesh_ribbon", "params": {"width": "360.0"}, "asset": None, "x": 300, "y": 0},
        "fin": {"verb": ultimo, "params": ({"name": "SM_PruebaHornear"} if ultimo == "mesh_to_static"
                else {"name": "JamPreviewVerbo"}), "asset": None, "x": 600, "y": 0}},
        "edges": [["eje", "out", "cinta", "in"], ["cinta", "out", "fin", "in"]]})

log("=" * 70)
for ultimo in ("mesh_preview", "mesh_to_static"):
    g_json = cadena(ultimo)
    reporte = json.loads(api.compile_graph_json(g_json))
    malos = {n: e["texto"] for n, e in reporte["nodes"].items() if e.get("estado") == "error"}
    exigir(not malos, f"«{ultimo}» compila en el Graph ({malos or 'sin errores'})")

    if ultimo == "mesh_to_static":
        try:
            unreal.EditorAssetLibrary.delete_asset("/Game/Jam/Meshes/SM_PruebaHornear")
        except Exception:
            pass
    t = time.perf_counter()
    salida = api.run_graph(g_json)
    ms = (time.perf_counter() - t) * 1000.0
    ok = "error" not in salida.lower() or "✓" in salida
    log(f"  Run con «{ultimo}»: {ms:7.1f}ms")
    exigir(ok, f"«{ultimo}» corre sin error")
    globals()[f"ms_{ultimo}"] = ms

if "ms_mesh_preview" in globals() and "ms_mesh_to_static" in globals():
    a, b = globals()["ms_mesh_preview"], globals()["ms_mesh_to_static"]
    log("-" * 70)
    log(f"ver sin hornear {a:.1f}ms  ·  hornear {b:.1f}ms  →  {b/max(a,0.01):.1f}x más rápido")
    exigir(a < b, "ver sin hornear es más rápido que hornear, por el camino del Graph")

log("JAM_VERBO_PREVIEW_58 TODO VERDE" if not FALLAS else f"JAM_VERBO_PREVIEW_58 ROJO — {len(FALLAS)}")
