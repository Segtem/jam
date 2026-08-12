"""¿De dónde sale el costo de recocinar un grafo que hornea, y por qué es tan desparejo?

Queda medido y sin explicar desde el ping-pong de ranuras: sobrescribir una ruta staged ocupada
costaba 37-86 ms contra ~5 de estrenarla, el costo parecía crecer vuelta a vuelta, y una de las dos
ranuras salía consistentemente más cara que la otra sin que se supiera cuál ni por qué. Eso vive
adentro del bucle del live view: arrastrar un slider recorre esa curva con la mano encima.

⚠️ **La primera versión de esta sonda se equivocó, y vale más que el número.** Intercalaba la serie
que hornea con una que sólo muestra, creyendo que así controlaba la deriva del proceso. Pero
alternar terminales hace que cada corrida deje HUÉRFANO el destino de la otra, y borrarlo cuesta
~142 ms: la serie de «mirar» daba 250 ms por vuelta —cuando ver sin hornear cuesta 1,7— y la de
hornear alternaba 8 y 44 ms según lo que le hubiera dejado la anterior. Es exactamente la trampa
«alternar A/B cuando cada corrida limpia lo anterior» que ya estaba escrita en AGENTS.md, y la
volví a pisar por usarla de control. **Un control que cambia el estado compartido no es un control.**

Acá cada serie corre SOLA, en su propia tanda, y en vez de deducir la ranura por la paridad de la
vuelta se anota **cuál se escribió y en qué estado estaba** —si el asset existía y si el objeto ya
estaba cargado en memoria—. Esas tres columnas son las que vuelven legible el patrón; sin ellas
sólo se ve una serie que sube y baja.

La deriva del proceso se controla repitiendo la MISMA tanda al final: si la segunda arranca donde
terminó la primera, hay deriva; si arranca de nuevo abajo, no la hay.

**LO QUE CONTESTÓ, y por qué el mecanismo cierra todo lo que estaba suelto.** No crece: las medianas
por ranura son planas a lo largo de las cuatro tandas. Lo que hay es un reparto DESPAREJO y estable
—una ranura ~85 ms, la otra ~3— que sale entero de una línea del motor. `create_new_static_mesh_
asset_from_mesh` termina en `NewObject` con un nombre ya ocupado, y `StaticAllocateObject`
(`UObjectGlobals.cpp`) tiene que destruir el objeto viejo antes de reusar su lugar:

    // Wait for the object's asynchronous cleanup to finish.
    while (!Obj->IsReadyForFinishDestroy()) { FPlatformProcess::Sleep(0); }
    …
    "Gamethread hitch waiting for resource cleanup on a UObject (%s) overwrite took %6.2fms.
     Fix the higher level code so that this does not happen."

Es el motor pidiendo por su nombre lo que hay que arreglar. Y el reparto desparejo es un **ciclo que
se sostiene solo**: la vuelta que espera 85 ms le regala ese tiempo al fence de la OTRA ranura, que
por eso llega limpia y cuesta 3; y esos 3 ms no le alcanzan a la primera, que vuelve a esperar. Dos
experimentos lo fijan, cada uno de una línea sobre `panel.py` (no quedan en el árbol):

  · **dar vuelta `_RANURAS`** — la cara pasó a ser la otra letra. No es la ranura, es la posición.
  · **anular la alternancia** — pisando SIEMPRE la misma ruta, todas las vueltas cuestan ~68 ms.
    O sea que la vuelta cara es la normal y **la barata es la excepción**: el ping-pong no está
    pagando de más, está consiguiendo que la mitad de las vueltas salgan gratis.

⚠️ **Y la espera no se cura con tiempo**: dormir hasta 400 ms entre vueltas no la baja. No espera un
plazo sino que le bombeen el render thread, y un commandlet `-run=pythonscript` no tickea nunca.

**VEREDICTO, ya con el editor andando: los 37-86 ms eran del commandlet.** La misma tanda bajo
`UnrealEditor … -RenderOffScreen -ExecCmds="py …,QUIT_EDITOR"` paga el golpe sólo las primeras
vueltas y después **las dos ranuras se plantan en ~2,9 ms**: con el loop andando el fence se
resuelve entre corrida y corrida —y el live view además espera 125 ms de amortiguador— así que no
queda nada que esperar. Los «30 a 80 ms sobre la mesa» no estaban sobre la mesa.

    ranura A · create 2,86 ms      ranura B · create 2,94 ms

Lo que NO era artefacto es el borrado (156 ms con el editor vivo, ver `mide_borrado_asset_58.py`),
que es justamente el motivo por el que existe el ping-pong. Se sostiene.
"""
import json
import statistics
import time

import unreal

from jam import api, mesh, panel

VUELTAS = 20
NOMBRE = "SM_Sobrescritura"
FINAL = mesh.asset_path_for(NOMBRE)


def log(m):
    unreal.log(f"[SOBREESCRITURA] {m}")


FALLAS = []


def exigir(condicion, descripcion):
    log(("  OK   " if condicion else "  FALLA") + f" · {descripcion}")
    if not condicion:
        FALLAS.append(descripcion)


def cadena(terminal, ancho):
    """El mismo grafo con UNA perilla movida: es exactamente lo que hace mover un slider."""
    nombre = NOMBRE if terminal == "mesh_to_static" else "JamPreviewSobrescritura"
    return json.dumps({
        "schema_version": 1,
        "nodes": {
            "eje": {"verb": "curve_bezier", "params": {
                "start_x": "0.0", "start_y": "0.0", "start_z": "0.0",
                "end_x": "900.0", "end_y": "0.0", "end_z": "80.0",
                "bend_x": "0.0", "bend_y": "320.0", "bend_z": "-40.0", "segments": "12"},
                "asset": None, "x": 0, "y": 0},
            "cinta": {"verb": "mesh_ribbon", "params": {"width": f"{ancho:.1f}"},
                      "asset": None, "x": 300, "y": 0},
            "fin": {"verb": terminal, "params": {"name": nombre}, "asset": None, "x": 600, "y": 0},
        },
        "edges": [["eje", "out", "cinta", "in"], ["cinta", "out", "fin", "in"]],
    })


def esta_cargado(ruta):
    """¿El objeto ya está en memoria, o sólo existe el paquete en disco?

    `find_asset` NO carga: es la única forma de preguntar sin cambiar la respuesta.
    """
    buscar = getattr(unreal, "find_asset", None)
    if buscar is None:
        return None
    try:
        return buscar(ruta) is not None
    except Exception:  # noqa: BLE001
        return None


def estado_del_destino():
    """Qué ranura le toca a la próxima corrida y cómo está esa ruta ANTES de escribirla."""
    ranura = panel._ranura_para("graph", FINAL)
    ruta = f"{panel._RAIZ_PREVIEW}/graph/PV{ranura}_{FINAL.rsplit('/', 1)[-1]}"
    return ranura, unreal.EditorAssetLibrary.does_asset_exist(ruta), esta_cargado(ruta)


def tanda(terminal, etiqueta, *, gc=False, anotar_ranura=False):
    """Una serie SOLA: nada más toca el Preview mientras corre."""
    panel._descartar_preview("graph")
    api.run_graph(cadena(terminal, 300.0))          # calentamiento, fuera del cronómetro
    panel._descartar_preview("graph")

    tiempos, filas, errores = [], [], []
    recolectar = getattr(unreal.SystemLibrary, "collect_garbage", None)
    for v in range(VUELTAS):
        antes = estado_del_destino() if anotar_ranura else None
        t = time.perf_counter()
        salida = api.run_graph(cadena(terminal, 320.0 + v))
        ms = (time.perf_counter() - t) * 1000.0
        tiempos.append(ms)
        if "[error]" in salida:
            errores.append(f"{etiqueta}[{v}]: {salida.splitlines()[0]}")
        if antes:
            filas.append((v, ms) + antes)
        if gc and recolectar is not None:
            recolectar()

    for e in errores[:4]:
        log(f"    ! {e[:110]}")
    log(f"  {etiqueta}:")
    for bloque in range(0, len(tiempos), 8):
        log("      " + " ".join(f"{x:7.1f}" for x in tiempos[bloque:bloque + 8]))
    if filas:
        log("      vuelta   ms   ranura  ¿existía?  ¿cargado?")
        for v, ms, ranura, existia, cargado in filas:
            log(f"      {v:>5}  {ms:7.1f}     {ranura}       "
                f"{'sí' if existia else 'no':<8}  {'sí' if cargado else 'no'}")
    primeras = statistics.median(tiempos[:5])
    ultimas = statistics.median(tiempos[-5:])
    log(f"      mediana {statistics.median(tiempos):7.1f} ms · primeras 5 {primeras:7.1f} · "
        f"últimas 5 {ultimas:7.1f} · ×{(ultimas / primeras if primeras else 0):.2f}")
    return tiempos, filas, errores


def midiendo_headless() -> bool:
    """¿Commandlet, que no tickea? Acá no invalida la medición: la PARTE EN DOS.

    Headless sale el ciclo de 85/3 ms; con el loop andando, las dos ranuras planas en ~3. Por eso
    la sonda no se niega —las dos corridas dicen algo— pero tiene que declarar cuál está mirando,
    porque el mismo número significa cosas opuestas en cada modo.
    """
    linea = str(getattr(unreal.SystemLibrary, "get_command_line", lambda: "")())
    return "-run=" in linea


HEADLESS = midiendo_headless()

log("=" * 78)
log(f"Cada serie SOLA, {VUELTAS} vueltas. La ranura se anota, no se deduce.")
log("  modo: " + ("COMMANDLET (no tickea) — se espera el ciclo caro/barato entre ranuras"
                  if HEADLESS else
                  "EDITOR ANDANDO — se espera que las dos ranuras estén parejas y baratas"))
log("-" * 78)

horneando, filas, err_h = tanda("mesh_to_static", "hornear", anotar_ranura=True)

log("-" * 78)
mirando, _, err_m = tanda("mesh_preview", "mirar (ver sin hornear)")

log("-" * 78)
log("La misma tanda que hornea, juntando la basura entre vuelta y vuelta (fuera del reloj):")
con_gc, filas_gc, err_g = tanda("mesh_to_static", "hornear+GC", gc=True, anotar_ranura=True)

log("-" * 78)
log("Y la tanda que hornea OTRA VEZ, al final: si arranca donde terminó la primera, hay deriva.")
horneando2, filas2, err_h2 = tanda("mesh_to_static", "hornear (repetida)", anotar_ranura=True)


def por_ranura(filas_de_la_tanda):
    """Las vueltas separadas por ranura, salteando las dos primeras (esas estrenan la ruta).

    Mezclar las dos ranuras en una sola mediana es lo que hacía que cualquier pregunta sobre
    crecimiento o deriva contestara cualquier cosa: la serie mezclada sube y baja 30× por vuelta,
    así que comparar «las primeras cinco» contra «las últimas cinco» mide qué ranuras cayeron
    adentro de cada ventana y nada más.
    """
    agrupado = {}
    for _v, ms, ranura, _existia, _cargado in filas_de_la_tanda[2:]:
        agrupado.setdefault(ranura, []).append(ms)
    return agrupado


log("=" * 78)
exigir(not (err_h + err_m + err_g + err_h2),
       f"ninguna vuelta falló ({len(err_h + err_m + err_g + err_h2)} errores)")
exigir(statistics.median(mirando) < 20.0,
       f"ver sin hornear sigue siendo barato ({statistics.median(mirando):.1f} ms) — "
       "si no, los 1,7 ms de antes eran otra cosa")

def piso(serie):
    """El MÍNIMO, no la mediana, para preguntar por crecimiento y deriva.

    Con el editor andando la vuelta completa rebota entre ~30 y ~70 ms sin relación con la ranura:
    es el editor haciendo lo suyo en paralelo, y `create` se queda plano en 2,9 ms mientras tanto.
    Ese ruido sólo puede SUMAR tiempo, así que el piso mide el costo y la mediana mide el costo más
    cuánto ruido cayó adentro de la ventana. Comparar medianas de una serie bimodal es la misma
    trampa que separar por ranura ya había arreglado: la primera versión de estas líneas daba
    «×2,23 hay deriva» sobre datos sanos, porque a la tanda repetida le tocaron más vueltas ruidosas.
    """
    return min(serie)


agrupado = por_ranura(filas)
for ranura in sorted(agrupado):
    serie = agrupado[ranura]
    mitad = len(serie) // 2
    primera, segunda = piso(serie[:mitad]), piso(serie[mitad:])
    log(f"  ranura {ranura}: piso {piso(serie):7.1f} ms · mediana {statistics.median(serie):7.1f} · "
        f"primera mitad {primera:7.1f} · segunda {segunda:7.1f} · ×{segunda / primera:.2f}")
    # La pregunta original —«el costo crece vuelta a vuelta»— sólo tiene sentido DENTRO de una
    # ranura. Contestada acá: no crece.
    exigir(segunda <= primera * 1.5,
           f"la ranura {ranura} no crece vuelta a vuelta ({primera:.1f} → {segunda:.1f} ms de piso)")

if not HEADLESS and len(agrupado) == 2:
    caras = sorted(piso(s) for s in agrupado.values())
    # Con el editor andando no queda fence que esperar: si volviera a aparecer el ciclo, algo
    # cambió en el motor o en el staging y el ping-pong dejó de estar de más.
    exigir(caras[1] <= 40.0,
           f"con el loop andando las dos ranuras quedan baratas (la peor dio {caras[1]:.1f} ms)")

cargados = [ms for _v, ms, _r, _e, c in filas[2:] if c]
frios = [ms for _v, ms, _r, _e, c in filas[2:] if c is False]
if cargados and frios:
    log(f"  destino ya cargado {statistics.median(cargados):7.1f} ms · "
        f"sólo en disco {statistics.median(frios):7.1f} ms")

agrupado2 = por_ranura(filas2)
for ranura in sorted(set(agrupado) & set(agrupado2)):
    antes, despues = piso(agrupado[ranura]), piso(agrupado2[ranura])
    log(f"  deriva en la ranura {ranura}: primera tanda {antes:7.1f} ms · "
        f"repetida al final {despues:7.1f} ms · ×{despues / antes:.2f}  (pisos)")
    exigir(despues <= antes * 1.5,
           f"la ranura {ranura} no deriva entre tandas ({antes:.1f} → {despues:.1f} ms de piso)")

panel._descartar_preview("graph")
log("JAM_SOBREESCRITURA_58 TODO VERDE" if not FALLAS else f"JAM_SOBREESCRITURA_58 ROJO — {len(FALLAS)}")
