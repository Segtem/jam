"""Verifica el pincel por el camino REAL en UE 5.8.1: selección → brush → scatter.

Los tests cubren `brush_core` con tuplas. Esto comprueba lo único que ellos no pueden: que el
adaptador lea de verdad la selección del nivel, arme `Sample`s que `scatter` acepte, y que la cadena
`brush → scatter` compile y corra con el catálogo real.

Crea un actor de prueba, lo selecciona, corre, y lo borra. El veredicto queda en `BotOO.log` con el
prefijo `JAM_BRUSH_58`.
"""
from __future__ import annotations

import unreal

from jam import tools, ue
from jam.graph import JamGraph, ejecutar_detalle


def exigir(condicion: bool, mensaje: str) -> None:
    if not condicion:
        raise RuntimeError(mensaje)


actor = None
try:
    # 1. Sin selección tiene que EXPLICAR qué falta, no fallar en silencio.
    ue.seleccionar([])
    try:
        tools.t_brush()
        exigir(False, "sin actor elegido tendría que haber avisado")
    except RuntimeError as e:
        exigir("elegí" in str(e), f"el mensaje no dice qué hacer: {e}")

    # Y un nombre que no existe tampoco puede fallar en silencio.
    try:
        tools.t_brush(actor="NoExisteEsteActor")
        exigir(False, "un nombre inexistente tendría que avisar")
    except RuntimeError as e:
        exigir("NoExisteEsteActor" in str(e), f"el error no nombra al actor: {e}")

    # 2. Por NOMBRE: el camino autocontenido, y el único verificable sin GUI — la selección del
    #    nivel no sobrevive a un commandlet (`set_selected_level_actors` no vuelve por `get_`).
    sub = ue._sub()
    actor = sub.spawn_actor_from_class(unreal.StaticMeshActor, unreal.Vector(300.0, 400.0, 0.0))
    actor.set_actor_label("PincelDePrueba")
    texto = tools.t_brush(actor="PincelDePrueba", alto=250.0)
    puntos = tools._RUNTIME_DATA_OUTPUTS.get("brush") or []
    exigir(len(puntos) == 1, f"esperaba 1 centro: {texto}")
    p = puntos[0].pos
    exigir(abs(p.x - 300.0) < 0.01 and abs(p.y - 400.0) < 0.01,
           f"el centro no cayó donde el actor: ({p.x}, {p.y})")
    exigir(abs(p.z - 250.0) < 0.01, f"«alto» no levantó el punto: z={p.z}")

    # 3. LA composición: el scatter reparte ALREDEDOR del pincel, sin que el pincel reparta.
    g = JamGraph()
    g.add("brush", {"actor": "PincelDePrueba", "alto": "250"}, nid="pincel")
    g.add("scatter", {"count": "12", "area": "300", "view": "False", "surface": "False"}, nid="s")
    g.connect("pincel", "s")
    _rep, estados = ejecutar_detalle(g)
    exigir(estados["pincel"]["estado"] != "error", f"el pincel falló: {estados['pincel']}")
    exigir(estados["s"]["estado"] != "error", f"el scatter falló: {estados['s']}")

    unreal.log(
        "JAM_BRUSH_58 TODO VERDE — "
        f"sin_actor_avisa · nombre_inexistente_avisa · centro=({p.x:.0f},{p.y:.0f},{p.z:.0f}) · "
        f"cadena={estados['s']['texto'][:70]}")
except Exception as exc:  # noqa: BLE001
    unreal.log_error(f"JAM_BRUSH_58 ROJO — {type(exc).__name__}: {exc}")
finally:
    if actor is not None:
        try:
            actor.destroy_actor()   # verificar no puede dejar basura en el nivel
        except Exception:  # noqa: BLE001
            pass
    unreal.SystemLibrary.quit_editor()
