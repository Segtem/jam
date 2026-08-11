"""El preview sin hornear, medido contra la línea base de 68-257ms."""
import time
import unreal
from jam import curve, mesh

def log(m): unreal.log(f"[PREVIEW] {m}")
FALLAS = []
def exigir(c, d):
    log(("  OK   " if c else "  FALLA") + f" · {d}")
    if not c: FALLAS.append(d)

log("=" * 70)
# La misma cadena del tutorial «Borde de camino», que horneando costaba 68,8ms.
t0 = time.perf_counter()
eje = curve.bezier(start_x=0.0, start_y=0.0, start_z=0.0, end_x=900.0, end_y=0.0, end_z=80.0,
                   bend_x=0.0, bend_y=320.0, bend_z=-40.0, segments=12)
uni = curve.resample(eje["curve"], count=25, samples=32)
borde = curve.offset(uni["curve"], distance=180.0, side="left", plane="xy",
                     join="miter", miter_limit=2.5, samples=32)
cinta = mesh.ribbon(borde["curve"], width=360.0, plane="xy", join="miter",
                    miter_limit=2.5, uv_scale=200.0, material_id=0, samples=32)
ms_geo = (time.perf_counter() - t0) * 1000.0

t = time.perf_counter()
r = mesh.mostrar(cinta["mesh"], name="JamPreviewCamino")
ms_mostrar = (time.perf_counter() - t) * 1000.0

if "error" in r:
    log(f"FALLA: {r['error']}")
else:
    total = ms_geo + ms_mostrar
    log(f"geometría {ms_geo:.1f}ms + mostrar {ms_mostrar:.1f}ms = {total:.1f}ms")
    log(f"línea base HORNEANDO el mismo tutorial: 68.8ms → {68.8/max(total,0.01):.0f}x más rápido")
    exigir(r["triangulos"] > 0, f"el preview muestra geometría real ({r['triangulos']} triángulos)")
    exigir(total < 68.8, "es más rápido que hornear")

    # Recocinar: es el gesto del live view, mover un slider.
    t = time.perf_counter()
    cinta2 = mesh.ribbon(borde["curve"], width=420.0, plane="xy", join="miter",
                         miter_limit=2.5, uv_scale=200.0, material_id=0, samples=32)
    r2 = mesh.mostrar(cinta2["mesh"], name="JamPreviewCamino2")
    ms_recook = (time.perf_counter() - t) * 1000.0
    log(f"recocinar tras mover un slider: {ms_recook:.1f}ms")
    exigir(ms_recook < 20.0, f"el gesto del live view es interactivo ({ms_recook:.1f}ms)")
    for actor in (r.get("actor"), r2.get("actor")):
        if actor: unreal.EditorLevelLibrary.destroy_actor(actor)

log("-" * 70)
log("JAM_PREVIEW_58 TODO VERDE" if not FALLAS else f"JAM_PREVIEW_58 ROJO — {len(FALLAS)}")
