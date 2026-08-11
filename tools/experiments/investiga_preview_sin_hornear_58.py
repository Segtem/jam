"""¿Se puede mostrar una M sin hornear? Descubrimiento + medición contra la línea base."""
import time
import unreal
from jam import mesh

def log(m): unreal.log(f"[DMC] {m}")

log("=" * 70)
clases = [n for n in dir(unreal) if "DynamicMesh" in n and "Actor" in n or n == "DynamicMeshActor"]
log(f"clases de actor con DynamicMesh: {clases[:6]}")
comp = [n for n in dir(unreal) if "DynamicMeshComponent" in n]
log(f"componentes: {comp[:4]}")

# Una malla de verdad, del mismo orden que la de los tutoriales.
t = time.perf_counter()
m = mesh.sphere(radius=100.0)
ms_geo = (time.perf_counter() - t) * 1000.0
log(f"construir la malla: {ms_geo:.1f}ms")

if "DynamicMeshActor" not in dir(unreal):
    log("DMC ROJO — no hay DynamicMeshActor en el binding"); raise SystemExit

mundo = unreal.EditorLevelLibrary.get_editor_world()
t = time.perf_counter()
actor = unreal.EditorLevelLibrary.spawn_actor_from_class(
    unreal.DynamicMeshActor, unreal.Vector(0, 0, 0))
ms_spawn = (time.perf_counter() - t) * 1000.0
log(f"spawn del actor: {ms_spawn:.1f}ms · actor={actor}")

if actor is None:
    log("DMC ROJO — no se pudo spawnear"); raise SystemExit

t = time.perf_counter()
componente = actor.get_editor_property("dynamic_mesh_component")
destino = componente.get_dynamic_mesh()
unreal.GeometryScript_MeshBasicEdits.append_mesh(destino, m["mesh"], unreal.Transform())
ms_set = (time.perf_counter() - t) * 1000.0
log(f"pasar la malla al componente: {ms_set:.1f}ms")

total = ms_geo + ms_spawn + ms_set
log("-" * 70)
log(f"TOTAL sin hornear: {total:.1f}ms   (la línea base HORNEANDO era 68-257ms)")
log(f"triángulos mostrados: {unreal.GeometryScript_MeshQueries.get_num_triangle_i_ds(destino)}")
unreal.EditorLevelLibrary.destroy_actor(actor)
log("JAM_DMC_58 MEDIDO")
