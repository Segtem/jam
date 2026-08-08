"""Verifica el asentado en TANDA por el camino REAL: actores de verdad en un nivel de verdad.

`test_physics_core.py` cubre la matemática con piezas inventadas. Lo que no puede cubrir es el
adaptador: que `ue.piezas()` mida el AABB del actor como el núcleo espera, que
`set_actor_location` deje la pieza donde el cálculo dijo, y que excluir la propia tanda de los
soportes funcione contra `get_all_level_actors` y no contra una lista de mentira.

Es exactamente el escalón donde ya dieron verde cuatro bugs en una sesión por probar con `unreal`
mockeado.

El veredicto queda en `BotOO.log` con el prefijo `JAM_PHYSICS_PAINT_58`.
"""

from __future__ import annotations

import unreal

from jam import physics, physics_core, ue

CUBO = "/Engine/BasicShapes/Cube.Cube"   # 100 cm de lado, siempre disponible


def exigir(condicion: bool, mensaje: str) -> None:
    if not condicion:
        raise RuntimeError(mensaje)


def spawnear(nombre, x, y, z, escala):
    sub = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    a = sub.spawn_actor_from_class(unreal.StaticMeshActor, unreal.Vector(x, y, z))
    malla = unreal.EditorAssetLibrary.load_asset(CUBO)
    a.static_mesh_component.set_static_mesh(malla)
    a.set_actor_scale3d(unreal.Vector(*escala))
    a.set_actor_label(nombre)
    return a


creados = []
try:
    # Piso: 100 m × 100 m × 10 cm, con el TOP en z = 0 para que las cuentas se lean solas.
    piso = spawnear("JamProbe_Piso", 0.0, 0.0, -5.0, (100.0, 100.0, 0.1))
    creados.append(piso)
    base_piso, extent_piso = ue.aabb(piso)
    exigir(abs((base_piso.z + extent_piso.z)) < 1.0,
           f"el piso no quedó con el top en 0: top={base_piso.z + extent_piso.z}")

    # Tres cubos de 1 m en el MISMO XY, a alturas distintas y en desorden a propósito.
    alturas = [("JamProbe_c", 1500.0), ("JamProbe_a", 400.0), ("JamProbe_b", 900.0)]
    cubos = [spawnear(n, 0.0, 0.0, z, (1.0, 1.0, 1.0)) for n, z in alturas]
    creados.extend(cubos)

    res = physics.asentar_actores(cubos)
    exigir(len(res) == 3, f"vinieron {len(res)} resultados para 3 actores")
    exigir(all(r["apoyada"] for r in res), f"alguna no encontró piso: {res}")

    # Lo que importa: NO las tres a cota 0. Se apilaron de a 100 cm.
    bases = sorted(round(physics_core.base_de(ue.aabb(c)), 1) for c in cubos)
    exigir(bases == [0.0, 100.0, 200.0],
           f"no se apilaron en el nivel real, quedaron en {bases}")

    # Y el orden es por ALTURA, no por el de la lista: el que estaba más abajo tocó el piso.
    por_nombre = {c.get_actor_label(): round(physics_core.base_de(ue.aabb(c)), 1) for c in cubos}
    exigir(por_nombre["JamProbe_a"] == 0.0,
           f"el más bajo tenía que ir al piso: {por_nombre}")
    exigir(por_nombre["JamProbe_c"] == 200.0,
           f"el más alto tenía que quedar arriba de todo: {por_nombre}")

    # El piso NO puede estar en la tanda: si `asentar_actores` no lo excluyera de sus propios
    # soportes, se asentaría sobre sí mismo o sobre un cubo.
    exigir(abs(piso.get_actor_location().z + 5.0) < 0.1,
           f"el piso se movió: z={piso.get_actor_location().z}")

        # ---- lo NO confirmado de Jam no es piso ----
    # El Preview anterior sigue vivo hasta que el nuevo termina bien. Una pieza que se apoye en él
    # queda FLOTANDO cuando lo reemplazan: Brian mandó la captura con un barril en el aire.
    falso = spawnear("prev_Jam_falso", 600.0, 0.0, 300.0, (3.0, 3.0, 3.0))
    falso.set_editor_property("tags", [unreal.Name("jam:preview")])
    creados.append(falso)
    encima = spawnear("JamProbe_sobre_preview", 600.0, 0.0, 900.0, (1.0, 1.0, 1.0))
    creados.append(encima)
    r_prev = physics.asentar_actores([encima])
    exigir(r_prev[0]["soporte"] != "prev_Jam_falso",
           f"se apoyó en el Preview anterior: quedaría flotando al reemplazarlo — {r_prev}")
    exigir(abs(physics_core.base_de(ue.aabb(encima))) < 1.0,
           f"tenía que bajar hasta el piso real, no hasta el preview: "
           f"{physics_core.base_de(ue.aabb(encima)):.1f}")

    # ---- 2ª parte: contra un TERRENO real, que es donde el AABB mentía ----
    # Un landscape de 121 m con lomas tiene un AABB cuyo top es el punto más alto de todo el mapa.
    # Con la caja, tres piezas en XY distintos aterrizaban las tres a esa cota, flotando.
    unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).load_level(
        "/Game/UltraDynamicSky/Maps/DemoMap")
    sub2 = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    sobre_terreno = []
    for i, (x, y) in enumerate([(0.0, 0.0), (2500.0, 0.0), (0.0, 2500.0), (-2500.0, 1200.0)]):
        a = sub2.spawn_actor_from_class(unreal.StaticMeshActor, unreal.Vector(x, y, 15000.0))
        a.static_mesh_component.set_static_mesh(unreal.EditorAssetLibrary.load_asset(CUBO))
        a.set_actor_label(f"JamProbe_T{i}")
        sobre_terreno.append(a)
    res_t = physics.asentar_actores(sobre_terreno)
    exigir(all(r["apoyada"] for r in res_t), f"alguna no encontró terreno: {res_t}")
    cotas = [round(physics_core.base_de(ue.aabb(a)), 1) for a in sobre_terreno]
    exigir(len(set(cotas)) > 1,
           f"las {len(cotas)} aterrizaron a la MISMA cota: eso es el AABB, no el terreno — {cotas}")
    for a in sobre_terreno:
        sub2.destroy_actor(a)

    unreal.log(
        f"JAM_PHYSICS_PAINT_58 TODO VERDE — bases={bases} · "
        f"soportes={[r['soporte'] for r in res]} · "
        f"caidas={[r['caida'] for r in res]} · piso_intacto · "
        f"preview_anterior_ignorado(soporte={r_prev[0]['soporte']}) · "
        f"terreno: cotas distintas por pieza = {cotas} (soportes {[r['soporte'] for r in res_t]})")
except Exception as exc:  # noqa: BLE001
    unreal.log_error(f"JAM_PHYSICS_PAINT_58 ROJO — {type(exc).__name__}: {exc}")
finally:
    # La sonda no ensucia el nivel: se lleva lo que trajo y NO guarda.
    try:
        sub = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
        for a in creados:
            sub.destroy_actor(a)
    except Exception:  # noqa: BLE001
        pass
    unreal.SystemLibrary.quit_editor()
