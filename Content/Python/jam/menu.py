"""Oráculo de espacio + selftests headless de Jam.

`on_verificar_espacio()` corre el oráculo de winnability sobre el NIVEL REAL (o el mapa demo si el
nivel no tiene nodos jam:*) y devuelve el veredicto — lo llama el verbo DSL «verify» desde la UI C++.
`selftest()` agrega las 9 pruebas headless (una por capacidad) para verificar sin GUI.

Nota: el viejo menú «Jam» de la barra principal y los handlers demo se retiraron — la UI vive en el
módulo C++ `JamEditor` (Tools → Dash Bar / Graph).
"""

from __future__ import annotations

import unreal

from . import (
    geometry,
    library,
    oracle_espacio,
    oracle_pared,
    oracle_physics,
    oracle_reemplazo,
    oracle_scatter,
    oracle_snap,
    nivel,
    pared,
    physics,
    place,
    preset,
    reemplazar,
    scatter,
    snap,
    ue,
)

_LOG_PREFIX = "[Jam]"


def _log(msg: str) -> None:
    for line in str(msg).splitlines():
        unreal.log(f"{_LOG_PREFIX} {line}")


# ---- estado vivo del editor (prueba que el puente al editor está caliente) ----

def contexto_editor() -> str:
    """Lee estado real del editor: mundo actual + cantidad de actores. Defensivo."""
    try:
        actor_sub = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
        actores = actor_sub.get_all_level_actors()
        n = len(actores)
    except Exception as e:  # noqa: BLE001
        n = -1
        _log(f"(no pude leer actores: {e})")
    try:
        ed = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
        world = ed.get_editor_world()
        wn = world.get_name() if world else "?"
    except Exception:  # noqa: BLE001
        wn = "?"
    return f"nivel «{wn}», {n} actores"


# ---- la acción ----

def on_verificar_espacio() -> str:
    """Verifica la winnability del NIVEL REAL (actores etiquetados con tags jam:*). Si el nivel no
    tiene nodos de Jam, cae al mapa demo en código para mostrar de qué se trata el oráculo."""
    r, _g = nivel.veredicto_nivel()
    if r is not None:
        cuerpo = nivel.veredicto_texto_nivel()
    else:
        sano = oracle_espacio.veredicto_texto("BotOO sano (demo)", oracle_espacio.mapa_botoo_ganable())
        roto = oracle_espacio.veredicto_texto("BotOO roto (demo)", oracle_espacio.mapa_botoo_roto())
        cuerpo = (nivel.veredicto_texto_nivel() + "\n\n— mientras tanto, el demo en código —\n\n"
                  + f"{sano}\n\n{roto}")
    cuerpo += f"\n\nEditor: {contexto_editor()}"
    _log("Verificar espacio →")
    _log(cuerpo)
    return cuerpo


# ---- selftest headless (para verificar la rebanada sin GUI) ----

def selftest_espacio() -> bool:
    """Oráculo de espacio: el mapa sano es ganable, el roto no."""
    _log("--- selftest: espacio ---")
    r_sano = oracle_espacio.veredicto(oracle_espacio.mapa_botoo_ganable())
    r_roto = oracle_espacio.veredicto(oracle_espacio.mapa_botoo_roto())
    _log(oracle_espacio.veredicto_texto("BotOO sano", oracle_espacio.mapa_botoo_ganable()))
    _log(oracle_espacio.veredicto_texto("BotOO roto", oracle_espacio.mapa_botoo_roto()))
    ok = bool(r_sano["solvable"]) and not bool(r_roto["solvable"])
    _log(f"espacio {'OK ✓' if ok else 'FALLÓ ✗'}")
    return ok


def selftest_colocar() -> bool:
    """Biblioteca + colocar: enumera la biblioteca real, coloca una malla, y el oráculo distingue
    una copia coincidente (INTERPENETRA) de una lejana (LIMPIO). Limpia los actores al final."""
    _log("--- selftest: biblioteca + colocar ---")
    libro = library.buscar(limit=1)
    if not libro:
        _log("biblioteca vacía — no hay StaticMesh bajo /Game")
        return False
    ruta = libro[0]["ruta"]
    _log(f"biblioteca: {len(library.buscar(limit=9999))} StaticMesh; elegido «{libro[0]['nombre']}»")
    a = place.colocar(ruta, (0.0, 0.0, 0.0))
    b = place.colocar(ruta, (0.0, 0.0, 0.0))          # coincidente con a → debe interpenetrar
    c = place.colocar(ruta, (100000.0, 0.0, 0.0))     # lejos → debe quedar limpio
    fondo = place.colocar(ruta, (0.0, 0.0, 0.0), scale=(2000.0, 2000.0, 2000.0))  # 2 km: escenografía
    fondo.set_actor_label("Jam_fondo_gigante")
    if not (a and b and c and fondo):
        _log("falló el spawn de alguna pieza")
        return False
    todos = [a, b, c, fondo]
    _log(ue.placement_texto(b, todos))
    _log(ue.placement_texto(c, todos))
    v_b = ue.placement(b, todos)   # coincide con a (normal) → interpenetra; fondo se ignora
    v_c = ue.placement(c, todos)   # lejos de a; el fondo enorme NO debe marcarlo
    fondo_ignorado = all("fondo" not in n for n, _ in v_c["interpenetra"])
    ok = (v_b["bounds_ok"] and bool(v_b["interpenetra"])
          and not v_c["interpenetra"] and fondo_ignorado
          and geometry.es_fondo(ue.aabb(fondo)) and not geometry.es_fondo(ue.aabb(a)))
    # limpieza: son actores de prueba en un mapa transitorio, igual los borramos
    actor_sub = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    for x in todos:
        actor_sub.destroy_actor(x)
    _log(f"colocar {'OK ✓' if ok else 'FALLÓ ✗'} "
         f"(coincidente.interpenetra={bool(v_b['interpenetra'])}, lejana.interpenetra={bool(v_c['interpenetra'])}, "
         f"fondo_ignorado={fondo_ignorado})")
    return ok


def selftest_scatter() -> bool:
    """Scatter: un reparto SANO (área amplia → cantidad, contenido, sin clavarse, cubierto) y uno
    SATURADO (área diminuta → las piezas se clavan). El oráculo debe aprobar el 1º y reprobar el 2º.
    Limpia los actores al final."""
    _log("--- selftest: scatter ---")
    libro = library.buscar(limit=1)
    if not libro:
        _log("biblioteca vacía — no hay StaticMesh bajo /Game")
        return False
    ruta = libro[0]["ruta"]

    c_sano, s_sano, n = (0.0, 0.0), (500.0, 500.0), 9
    sano = scatter.esparcir(ruta, c_sano, s_sano, n, seed=7, yaw_aleatorio=False)
    r_sano = oracle_scatter.verificar(ue.piezas(sano), c_sano, s_sano, n)
    _log(oracle_scatter.verificar_texto(ue.piezas(sano), c_sano, s_sano, n))

    c_den, s_den = (100000.0, 0.0), (60.0, 60.0)   # lejos del sano; 120×120cm para 9 cubos de 100
    denso = scatter.esparcir(ruta, c_den, s_den, n, seed=7, yaw_aleatorio=False)
    r_den = oracle_scatter.verificar(ue.piezas(denso), c_den, s_den, n)
    _log(oracle_scatter.verificar_texto(ue.piezas(denso), c_den, s_den, n))

    actor_sub = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    for x in sano + denso:
        actor_sub.destroy_actor(x)

    ok = oracle_scatter.es_ok(r_sano) and bool(r_den["interpenetra"])
    _log(f"scatter {'OK ✓' if ok else 'FALLÓ ✗'} "
         f"(sano.ok={oracle_scatter.es_ok(r_sano)}, denso.interpenetra={len(r_den['interpenetra'])} pares)")
    return ok


def selftest_physics() -> bool:
    """Physics drop: sobre un piso, una pieza que FLOTA debe caer a APOYADO, y una pieza clavada
    debe leerse HUNDIDO. El oráculo debe distinguir los tres estados. Limpia los actores al final."""
    _log("--- selftest: physics (drop) ---")
    libro = library.buscar(limit=1)
    if not libro:
        _log("biblioteca vacía — no hay StaticMesh bajo /Game")
        return False
    ruta = libro[0]["ruta"]
    x0 = 200000.0  # lejos de todo, para que el piso sea el único soporte
    piso = place.colocar(ruta, (x0, 0.0, 0.0), scale=(50.0, 50.0, 1.0))  # top del AABB en +50
    caja = place.colocar(ruta, (x0, 0.0, 800.0))                        # flota muy por encima
    clavada = place.colocar(ruta, (x0 + 1000.0, 0.0, 50.0))             # base en 0 < top piso 50

    r_antes = oracle_physics.verificar(ue.pieza(caja), ue.piezas([piso]))
    _log("caja  " + oracle_physics.verificar_texto(ue.pieza(caja), ue.piezas([piso])))
    drop = physics.soltar(caja, [piso])
    r_desp = oracle_physics.verificar(ue.pieza(caja), ue.piezas([piso]))
    _log(f"caja  cae {drop['caida']}cm → " + oracle_physics.verificar_texto(ue.pieza(caja), ue.piezas([piso])))
    r_clav = oracle_physics.verificar(ue.pieza(clavada), ue.piezas([piso]))
    _log("clav  " + oracle_physics.verificar_texto(ue.pieza(clavada), ue.piezas([piso])))

    actor_sub = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    for x in (piso, caja, clavada):
        actor_sub.destroy_actor(x)

    ok = (r_antes["estado"] == "flotando"
          and r_desp["estado"] == "apoyado"
          and r_clav["estado"] == "hundido")
    _log(f"physics {'OK ✓' if ok else 'FALLÓ ✗'} "
         f"(antes={r_antes['estado']}, después={r_desp['estado']}, clavada={r_clav['estado']})")
    return ok


def selftest_snap() -> bool:
    """Snap: (a) una pieza fuera de grilla debe pasar a EN GRILLA; (b) una pieza con hueco contra
    otra debe pasar a AL RAS, y el oráculo debe leer HUECO antes. Limpia los actores al final."""
    _log("--- selftest: snap / alinear ---")
    libro = library.buscar(limit=1)
    if not libro:
        _log("biblioteca vacía — no hay StaticMesh bajo /Game")
        return False
    ruta = libro[0]["ruta"]
    x0 = 300000.0  # lejos de todo

    # (a) grilla
    caja = place.colocar(ruta, (x0 + 137.4, 62.9, 11.1), (0.0, 0.0, 37.0))
    g_antes = ue.snap_grilla(caja, 100.0)
    _log("grilla " + ue.snap_grilla_texto(caja, 100.0))
    snap.a_grilla(caja, 100.0)
    g_desp = ue.snap_grilla(caja, 100.0)
    _log("grilla " + ue.snap_grilla_texto(caja, 100.0))

    # (b) al ras: objetivo en el origen local; actor con un hueco de 60cm sobre +x (cubos de 100)
    obj = place.colocar(ruta, (x0, 5000.0, 0.0))
    obj.set_actor_label("Jam_objetivo")
    act = place.colocar(ruta, (x0 + 260.0, 5000.0, 0.0))  # centros a 260 → gap 160 sobre x
    r_antes = ue.snap_ras(act, obj, "x")
    _log("ras    " + ue.snap_ras_texto(act, obj, "x"))
    snap.al_ras(act, obj, "x")
    r_desp = ue.snap_ras(act, obj, "x")
    _log("ras    " + ue.snap_ras_texto(act, obj, "x"))

    actor_sub = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    for x in (caja, obj, act):
        actor_sub.destroy_actor(x)

    ok = (not g_antes["en_grilla"] and g_desp["en_grilla"]
          and r_antes["estado"] == "hueco" and r_desp["estado"] == "al_ras")
    _log(f"snap {'OK ✓' if ok else 'FALLÓ ✗'} "
         f"(grilla {not g_antes['en_grilla']}→{g_desp['en_grilla']}, "
         f"ras {r_antes['estado']}→{r_desp['estado']})")
    return ok


def selftest_reemplazo() -> bool:
    """Reemplazo: escalando (ajustar_escala=True) el footprint se PRESERVA; sin escalar el asset
    nativo NO calza la planta del blockout y el oráculo lo caza. Limpia los actores al final."""
    _log("--- selftest: reemplazar blockout ---")
    libro = library.buscar(limit=1)
    if not libro:
        _log("biblioteca vacía — no hay StaticMesh bajo /Game")
        return False
    ruta = libro[0]["ruta"]
    x0 = 400000.0  # lejos de todo

    b1 = place.colocar(ruta, (x0, 0.0, 150.0), scale=(2.0, 2.0, 3.0))  # blockout 200×200×300
    n1, obj1 = reemplazar.reemplazar(b1, ruta, ajustar_escala=True)
    r1 = oracle_reemplazo.verificar(ue.pieza(n1), obj1)
    _log("escala  " + oracle_reemplazo.verificar_texto(ue.pieza(n1), obj1))

    b2 = place.colocar(ruta, (x0 + 1000.0, 0.0, 150.0), scale=(2.0, 2.0, 3.0))
    n2, obj2 = reemplazar.reemplazar(b2, ruta, ajustar_escala=False)  # nativo 100³ vs 200×200×300
    r2 = oracle_reemplazo.verificar(ue.pieza(n2), obj2)
    _log("nativo  " + oracle_reemplazo.verificar_texto(ue.pieza(n2), obj2))

    actor_sub = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    for x in (n1, n2):
        actor_sub.destroy_actor(x)

    ok = oracle_reemplazo.es_ok(r1) and not oracle_reemplazo.es_ok(r2) and not r2["footprint"]
    _log(f"reemplazo {'OK ✓' if ok else 'FALLÓ ✗'} "
         f"(escala.preserva={r1['preserva']}, nativo.preserva={r2['preserva']}, nativo.footprint={r2['footprint']})")
    return ok


def selftest_pared() -> bool:
    """Pared por spline: sobre un spline RECTO la pared es continua; sobre un spline con un PICO y
    segmentos largos las juntas se despegan → discontinua. El oráculo debe distinguirlos.
    Limpia el spline y los segmentos al final."""
    _log("--- selftest: pared por spline ---")
    libro = library.buscar(limit=1)
    if not libro:
        _log("biblioteca vacía — no hay StaticMesh bajo /Game")
        return False
    ruta = libro[0]["ruta"]
    actor_sub = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)

    # recto → continua
    sp_recto = pared.crear_spline([(500000.0, 0.0, 0.0), (502000.0, 0.0, 0.0)], seleccionar=False)
    b_recto = pared.construir(sp_recto, ruta, largo_segmento=200.0)
    r_recto = oracle_pared.verificar(b_recto)
    _log(oracle_pared.verificar_texto(b_recto))

    # pico + segmentos largos → discontinua
    sp_pico = pared.crear_spline(
        [(600000.0, 0.0, 0.0), (600400.0, 700.0, 0.0), (600800.0, 0.0, 0.0)], seleccionar=False)
    b_pico = pared.construir(sp_pico, ruta, largo_segmento=500.0)
    r_pico = oracle_pared.verificar(b_pico)
    _log(oracle_pared.verificar_texto(b_pico))

    for x in (b_recto["segmentos"] + b_pico["segmentos"] + [sp_recto, sp_pico]):
        actor_sub.destroy_actor(x)

    ok = oracle_pared.es_ok(r_recto) and not r_pico["continua"]
    _log(f"pared {'OK ✓' if ok else 'FALLÓ ✗'} "
         f"(recto.continua={r_recto['continua']} maxgap={r_recto['max_gap']}, "
         f"pico.continua={r_pico['continua']} maxgap={r_pico['max_gap']})")
    return ok


def selftest_presets() -> bool:
    """Presets (modelo maduro): hay ≥3 de fábrica; aplicar el de tool (scatter) y el compound (flow)
    corre por el camino maduro; guardar+cargar+aplicar+borrar un preset local roundtrip funciona.
    Limpia los actores del preview y el archivo temporal al final."""
    _log("--- selftest: presets ---")
    globales = preset.listar(scope="global")
    _log(f"presets de fábrica: {len(globales)} — " + ", ".join(p["nombre"] for p in globales))
    if len(globales) < 3:
        _log("faltan presets de fábrica")
        return False
    hay_compound = any(p.get("kind") == "flow" for p in globales)

    from . import panel

    # aplicar el preset de tool de fábrica (scatter) — pasa por preview
    res_tool = preset.aplicar("Escombros densos")
    _log("aplicar tool built-in → " + res_tool["texto"].splitlines()[0])
    tool_ok = "SCATTER" in res_tool["texto"]
    panel._descartar_preview()

    # aplicar el compound (flow) de fábrica — pasa por el evaluador de flow
    res_flow = preset.aplicar("Piso disperso natural")
    _log("aplicar compound built-in → " + res_flow["texto"].splitlines()[0][:90])
    flow_ok = "instance" in res_flow["texto"] or "puntos" in res_flow["texto"]
    panel._descartar_preview()

    # roundtrip local: construir desde comando → guardar → cargar → aplicar → borrar
    demo = preset.desde_comando("Jam Selftest Prop", "place view=false surface=false anchor=base",
                                categoria="test", scope="local")
    ruta = preset.guardar(demo)
    cargado = preset.cargar("Jam Selftest Prop")
    res_local = preset.aplicar(cargado) if cargado else {"ok": False, "texto": "no cargó"}
    _log("roundtrip local → " + res_local["texto"].splitlines()[0])
    borrado = preset.borrar("Jam Selftest Prop")
    panel._descartar_preview()
    try:
        __import__("pathlib").Path(ruta).unlink(missing_ok=True)
    except Exception:  # noqa: BLE001
        pass

    roundtrip_ok = (cargado is not None) and ("[Jam Selftest Prop]" in res_local["texto"]) and borrado
    ok = tool_ok and flow_ok and hay_compound and roundtrip_ok
    _log(f"presets {'OK ✓' if ok else 'FALLÓ ✗'} "
         f"(tool={tool_ok}, compound={flow_ok}, roundtrip={roundtrip_ok})")
    return ok


def selftest_nivel() -> bool:
    """Oráculo sobre el NIVEL REAL: spawnea 5 cubos, los etiqueta como el mapa de extracción de
    BotOO, lee el grafo del nivel y verifica GANABLE; luego rompe el enlace a la pista (el sello se
    vuelve inalcanzable) y verifica NO GANABLE. Limpia los actores al final."""
    _log("--- selftest: oráculo sobre nivel real ---")
    libro = library.buscar(limit=1)
    if not libro:
        _log("biblioteca vacía — no hay StaticMesh bajo /Game")
        return False
    ruta = libro[0]["ruta"]
    x0 = 800000.0
    ent = place.colocar(ruta, (x0, 0.0, 0.0))
    pis = place.colocar(ruta, (x0 + 300, 0.0, 0.0))
    gal = place.colocar(ruta, (x0, 300.0, 0.0))
    cri = place.colocar(ruta, (x0 + 300, 300.0, 0.0))
    ext = place.colocar(ruta, (x0 + 600, 300.0, 0.0))
    nodos = [ent, pis, gal, cri, ext]

    nivel.marcar_nodo(ent, "entrada", tipo="spawn", start=True, enlaces=["pista", "galeria"])
    nivel.marcar_nodo(pis, "pista", tipo="clue", key="sello_antiguo")
    nivel.marcar_nodo(gal, "galeria", enlaces=["cripta"])
    nivel.marcar_nodo(cri, "cripta", tipo="boss")
    # sólo se extrae con el sello: la arista cripta↔extraccion es una puerta que exige la llave
    nivel.marcar_nodo(ext, "extraccion", tipo="extract", goal=True, enlaces=[("cripta", "sello_antiguo")])

    r_sano, g_sano = nivel.veredicto_nivel(nodos)
    _log(nivel.veredicto_texto_nivel(nodos))

    # romper: la entrada deja de enlazar a la pista → el sello queda inalcanzable
    nivel.marcar_nodo(ent, "entrada", tipo="spawn", start=True, enlaces=["galeria"])
    r_roto, _g = nivel.veredicto_nivel(nodos)
    _log(nivel.veredicto_texto_nivel(nodos))

    actor_sub = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    for a in nodos:
        actor_sub.destroy_actor(a)

    ok = (r_sano is not None and r_sano["solvable"]
          and len(g_sano.nodes) == 5 and len(g_sano.edges) == 4
          and r_roto is not None and not r_roto["solvable"])
    _log(f"nivel {'OK ✓' if ok else 'FALLÓ ✗'} "
         f"(sano.ganable={r_sano and r_sano['solvable']}, nodos={len(g_sano.nodes)}, "
         f"aristas={len(g_sano.edges)}, roto.ganable={r_roto and r_roto['solvable']})")
    return ok


def selftest() -> bool:
    """Prueba TODA la rebanada sin GUI. Headless: `-ExecCmds "py import jam.menu as m; m.selftest()"`."""
    _log("=== SELFTEST ===")
    ok_e = selftest_espacio()
    ok_c = selftest_colocar()
    ok_s = selftest_scatter()
    ok_p = selftest_physics()
    ok_n = selftest_snap()
    ok_r = selftest_reemplazo()
    ok_w = selftest_pared()
    ok_pr = selftest_presets()
    ok_nv = selftest_nivel()
    _log(f"contexto: {contexto_editor()}")
    ok = ok_e and ok_c and ok_s and ok_p and ok_n and ok_r and ok_w and ok_pr and ok_nv
    _log(f"SELFTEST {'OK ✓' if ok else 'FALLÓ ✗'} "
         f"(espacio={ok_e}, colocar={ok_c}, scatter={ok_s}, physics={ok_p}, snap={ok_n}, "
         f"reemplazo={ok_r}, pared={ok_w}, presets={ok_pr}, nivel={ok_nv})")
    return ok
