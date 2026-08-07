"""La cadena del pincel por el camino REAL, hasta donde el commandlet llega.

`asset ×2 → asset_set → place(points)`. Se corre con el motor de verdad para contestar lo que
ningún test headless puede: si el `A[]` que viaja por el cable llega vivo hasta
`_place_en_puntos`, si de ahí salen StaticMesh de verdad, y si el reparto de variantes por punto
toca las dos.

**Límite conocido:** `EditorActorSubsystem.spawn_actor_from_object` NO spawnea en commandlet —
devuelve None con `LogUtils: SpawnActorFromObject. No actor was spawned.`, incluso con un mapa real
cargado y con un mundo válido (`spawn_actor_from_class` sí anda en la misma corrida). O sea que el
acto de COLOCAR sólo se verifica con el editor abierto. La sonda lo comprueba explícitamente en vez
de dar verde sobre una cadena que en realidad no colocó nada.

El veredicto queda en `BotOO.log` con el prefijo `JAM_PLACE_VARIANTES_58`.
"""

from __future__ import annotations

import unreal

from jam import scatter, ue, variants
from jam.graph import JamGraph, ejecutar_detalle, validar

CUBO = "/Engine/BasicShapes/Cube.Cube"
ESFERA = "/Engine/BasicShapes/Sphere.Sphere"


def exigir(condicion: bool, mensaje: str) -> None:
    if not condicion:
        raise RuntimeError(mensaje)


try:
    # ---- 1. la cadena COMPILA con el registro real (no con uno de mentira) ----
    g = JamGraph()
    g.add("asset", {"name": CUBO}, nid="a1")
    g.add("asset", {"name": ESFERA}, nid="a2")
    g.add("asset_set", {}, nid="vars")
    g.add("scatter", {"count": "8", "area": "600", "surface": "False", "view": "False",
                      "spacing": "150"}, nid="disp")
    g.add("place", {"physics": "True", "surface": "False", "view": "False"}, nid="poner")
    for o, d in (("a1", "vars"), ("a2", "vars"), ("vars", "poner")):
        g.connect(o, d)
    g.connect("disp", "poner", "points")
    exigir(validar(g) == {}, f"la cadena no compila con assets REALES: {validar(g)}")

    # ---- 2. sin `points`, el A[] tiene que ser rechazado (y por el motivo correcto) ----
    sin_puntos = JamGraph()
    sin_puntos.add("asset", {"name": CUBO}, nid="a1")
    sin_puntos.add("asset", {"name": ESFERA}, nid="a2")
    sin_puntos.add("asset_set", {}, nid="vars")
    sin_puntos.add("place", {}, nid="poner")
    for o, d in (("a1", "vars"), ("a2", "vars"), ("vars", "poner")):
        sin_puntos.connect(o, d)
    fallos = validar(sin_puntos).get("poner", [])
    exigir(any("points" in m for m in fallos),
           f"A[] sin points tendría que quejarse del pin que falta: {fallos}")

    # ---- 3. el A[] llega vivo y se convierte en MALLAS de verdad ----
    aset = variants.make_asset_set([CUBO, ESFERA])["asset_set"]
    mallas = scatter._mallas_de(aset)
    exigir(len(mallas) == 2, f"el A[] no se resolvió a dos mallas: {mallas}")
    nombres = [m.get_name() for m in mallas]
    exigir(sorted(nombres) == ["Cube", "Sphere"], f"mallas inesperadas: {nombres}")
    radios = [ue.radio_de_malla(m) for m in mallas]
    exigir(all(r > 0 for r in radios), f"radio nulo, el dedup por huella no mediría: {radios}")

    # ---- 4. el reparto TOCA las dos variantes (no es una sola repetida ocho veces) ----
    reporte, por_nodo = ejecutar_detalle(g)
    from jam import tools
    generados = tools._RUNTIME_DATA_OUTPUTS.get("scatter") or []
    exigir(len(generados) >= 4, f"el scatter dio {len(generados)} puntos")
    elegidas = {s.seed % len(mallas) for s in generados}
    exigir(len(elegidas) == 2,
           f"el reparto por semilla usó una sola variante para los {len(generados)} puntos")

    # ---- 5. el límite, comprobado y no supuesto ----
    texto = por_nodo["poner"]["texto"]
    exigir(texto.startswith("PLACE ✗"),
           f"en commandlet no puede colocar; el veredicto tiene que decirlo: {texto!r}")
    # «warn» (naranja) es el escalón de «el oráculo dice REVISAR ✗: el resultado no sirve»;
    # `error` queda para lo que revienta. Lo que NO puede ser es verde.
    exigir(por_nodo["poner"]["estado"] == "warn",
           f"cero colocados no puede pintar el nodo de verde: {por_nodo['poner']}")

    unreal.log(
        f"JAM_PLACE_VARIANTES_58 TODO VERDE — compila con assets reales · "
        f"A[] → {nombres} · radios={[round(r, 1) for r in radios]} · "
        f"{len(generados)} puntos reparten {len(elegidas)} variantes · "
        f"sin points el Compile lo rechaza · "
        f"colocar queda para el editor GUI (spawn_actor_from_object no anda en commandlet)")
except Exception as exc:  # noqa: BLE001
    unreal.log_error(f"JAM_PLACE_VARIANTES_58 ROJO — {type(exc).__name__}: {exc}")
finally:
    unreal.SystemLibrary.quit_editor()
