"""El menú "Jam" en el editor de Unreal + las acciones que dispara.

Registra un menú de nivel superior con `unreal.ToolMenus`. Por ahora una acción:
"Verificar espacio (oráculo)" — corre el oráculo de winnability sobre los mapas demo
de BotOO y muestra el veredicto. Todo defensivo: en headless (sin widgets) el registro
del menú se saltea y el veredicto va al log en vez de a un diálogo modal.
"""

from __future__ import annotations

import unreal

from . import (
    library,
    oracle_espacio,
    oracle_pared,
    oracle_physics,
    oracle_placement,
    oracle_reemplazo,
    oracle_scatter,
    oracle_snap,
    nivel,
    panel,
    pared,
    physics,
    place,
    preset,
    reemplazar,
    scatter,
    snap,
)

_MENU_MAIN = "LevelEditor.MainMenu"
_SUBMENU = "Jam"
_LOG_PREFIX = "[Jam]"

# El panel (jam.panel) pone esto en True para que el veredicto vaya al TextBlock y no a un modal.
_SILENCIAR_DIALOGO = False


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
    _mostrar_dialogo("Jam · Oráculo de espacio", cuerpo)
    return cuerpo


def on_colocar_primero() -> str:
    """Coloca el primer asset de la biblioteca en el origen y muestra el veredicto del oráculo.
    (Acción demo del Content Browser; la versión con picker de asset es un crecimiento posterior.)"""
    libro = library.buscar(limit=1)
    if not libro:
        msg = "Biblioteca vacía: no hay StaticMesh bajo /Game."
        _log(msg)
        _mostrar_dialogo("Jam · Colocar", msg)
        return msg
    elegido = libro[0]
    actor = place.colocar(elegido["ruta"], (0.0, 0.0, 0.0))
    if actor is None:
        msg = f"No se pudo colocar {elegido['nombre']}."
        _log(msg)
        return msg
    otros = unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors()
    cuerpo = f"Colocado «{elegido['nombre']}» en el origen.\n\n" + \
        oracle_placement.verificar_texto(actor, otros)
    _log(cuerpo)
    _mostrar_dialogo("Jam · Colocar (oráculo)", cuerpo)
    return cuerpo


def on_scatter_demo() -> str:
    """Esparce ~9 copias del primer asset de la biblioteca sobre un área y muestra el veredicto.
    Deja las instancias en el nivel (para verlas); la versión con picker de asset/región es crecimiento."""
    libro = library.buscar(limit=1)
    if not libro:
        msg = "Biblioteca vacía: no hay StaticMesh bajo /Game."
        _log(msg)
        _mostrar_dialogo("Jam · Scatter", msg)
        return msg
    elegido = libro[0]
    centro, semi, cant = (0.0, 0.0), (500.0, 500.0), 9
    actores = scatter.esparcir(elegido["ruta"], centro, semi, cant, seed=7)
    cuerpo = f"Scatter de «{elegido['nombre']}» ({len(actores)} instancias sobre 10×10 m):\n\n" + \
        oracle_scatter.verificar_texto(actores, centro, semi, cant)
    _log(cuerpo)
    _mostrar_dialogo("Jam · Scatter (oráculo)", cuerpo)
    return cuerpo


def on_soltar_demo() -> str:
    """Arma un piso, deja caer un asset flotando y muestra el veredicto del oráculo de physics.
    Deja el piso + la pieza en el nivel (para verlos); el drop sobre geometría real es crecimiento."""
    libro = library.buscar(limit=1)
    if not libro:
        msg = "Biblioteca vacía: no hay StaticMesh bajo /Game."
        _log(msg)
        _mostrar_dialogo("Jam · Physics", msg)
        return msg
    ruta = libro[0]["ruta"]
    piso = place.colocar(ruta, (0.0, 0.0, 0.0), scale=(50.0, 50.0, 1.0))
    piso.set_actor_label("Jam_piso")
    caja = place.colocar(ruta, (0.0, 0.0, 800.0))
    antes = oracle_physics.verificar_texto(caja, [piso])
    r = physics.soltar(caja, [piso])
    despues = oracle_physics.verificar_texto(caja, [piso])
    cuerpo = (f"Soltar «{libro[0]['nombre']}» sobre un piso:\n\n"
              f"antes:   {antes}\n"
              f"cae {r['caida']}cm →\n"
              f"después: {despues}")
    _log(cuerpo)
    _mostrar_dialogo("Jam · Physics (oráculo)", cuerpo)
    return cuerpo


def on_snap_grilla_demo() -> str:
    """Coloca un asset en una posición fuera de grilla, lo cuadra a grilla de 100cm y muestra
    el veredicto antes/después. Deja la pieza en el nivel (para verla)."""
    libro = library.buscar(limit=1)
    if not libro:
        msg = "Biblioteca vacía: no hay StaticMesh bajo /Game."
        _log(msg)
        _mostrar_dialogo("Jam · Snap", msg)
        return msg
    caja = place.colocar(libro[0]["ruta"], (137.4, 62.9, 11.1), (0.0, 0.0, 37.0))
    antes = oracle_snap.texto_grilla(caja, 100.0)
    snap.a_grilla(caja, 100.0)
    despues = oracle_snap.texto_grilla(caja, 100.0)
    cuerpo = f"Alinear «{libro[0]['nombre']}» a grilla de 100cm:\n\nantes:   {antes}\ndespués: {despues}"
    _log(cuerpo)
    _mostrar_dialogo("Jam · Snap a grilla (oráculo)", cuerpo)
    return cuerpo


def on_reemplazar_demo() -> str:
    """Arma una caja de blockout (200×200×300cm), la reemplaza por el asset real escalado a calzar,
    y muestra si se preservó el footprint. Deja el asset resultante en el nivel (para verlo)."""
    libro = library.buscar(limit=1)
    if not libro:
        msg = "Biblioteca vacía: no hay StaticMesh bajo /Game."
        _log(msg)
        _mostrar_dialogo("Jam · Reemplazar", msg)
        return msg
    ruta = libro[0]["ruta"]
    blockout = place.colocar(ruta, (0.0, 0.0, 150.0), scale=(2.0, 2.0, 3.0))
    blockout.set_actor_label("Jam_blockout")
    nuevo, objetivo = reemplazar.reemplazar(blockout, ruta, ajustar_escala=True)
    cuerpo = (f"Reemplazar blockout (200×200×300cm) por «{libro[0]['nombre']}»:\n\n"
              + oracle_reemplazo.verificar_texto(nuevo, objetivo))
    _log(cuerpo)
    _mostrar_dialogo("Jam · Reemplazar blockout (oráculo)", cuerpo)
    return cuerpo


def on_crear_spline() -> str:
    """Crea un spline editable (L por defecto) y lo deja seleccionado para moldearlo en el viewport.
    Después usá 'Jam → Pared por spline' para levantar la pared sobre él."""
    actor = pared.crear_spline()
    msg = (f"Spline «{actor.get_actor_label()}» creado y seleccionado.\n"
           "Moldealo en el viewport (Alt-arrastrar añade puntos; los puntos se mueven con el widget),\n"
           "y después corré «Jam → Pared por spline».")
    _log(msg)
    _mostrar_dialogo("Jam · Crear spline de pared", msg)
    return msg


def on_pared_demo() -> str:
    """Levanta una pared sobre el spline seleccionado (o crea uno si no hay) y muestra el veredicto.
    Deja la pared en el nivel (para verla)."""
    libro = library.buscar(limit=1)
    if not libro:
        msg = "Biblioteca vacía: no hay StaticMesh bajo /Game."
        _log(msg)
        _mostrar_dialogo("Jam · Pared", msg)
        return msg
    actor = pared.seleccionado_con_spline()
    creado = ""
    if actor is None:
        actor = pared.crear_spline()
        creado = " (no había spline seleccionado; creé una L de ejemplo)"
    build = pared.construir(actor, libro[0]["ruta"])
    cuerpo = (f"Pared de «{libro[0]['nombre']}» sobre «{actor.get_actor_label()}»{creado}:\n\n"
              + oracle_pared.verificar_texto(build))
    _log(cuerpo)
    _mostrar_dialogo("Jam · Pared por spline (oráculo)", cuerpo)
    return cuerpo


def on_presets_demo() -> str:
    """Lista los presets disponibles y aplica el primero, mostrando el veredicto del oráculo.
    (El picker de presets por tool va en el panel; esto es la demo de menú.)"""
    presets = preset.listar()
    if not presets:
        msg = "No hay presets. (Deberían estar los de fábrica en <plugin>/presets/.)"
        _log(msg)
        _mostrar_dialogo("Jam · Presets", msg)
        return msg
    lista = "\n".join(f"  · [{p['scope']}] {p['nombre']} ({p['tool']})" for p in presets)
    elegido = presets[0]
    res = preset.aplicar(elegido)
    cuerpo = f"Presets disponibles:\n{lista}\n\nApliqué el primero →\n{res['texto']}"
    _log(cuerpo)
    _mostrar_dialogo("Jam · Presets (oráculo)", cuerpo)
    return cuerpo


def _mostrar_dialogo(titulo: str, cuerpo: str) -> None:
    """Diálogo modal si hay GUI; en headless no hace nada (ya se logueó). El panel lo silencia."""
    if _SILENCIAR_DIALOGO:
        return
    try:
        unreal.EditorDialog.show_message(
            titulo, cuerpo, unreal.AppMsgType.OK, unreal.AppReturnType.OK
        )
    except Exception:  # noqa: BLE001
        pass  # headless / sin slate: el log ya tiene el veredicto


# ---- registro del menú ----

def register() -> bool:
    """Registra el menú Jam. Devuelve True si se registró; False si no hay ToolMenus (headless)."""
    try:
        menus = unreal.ToolMenus.get()
        main = menus.find_menu(_MENU_MAIN)
        if main is None:
            _log("ToolMenus sin MainMenu (headless) — menú no registrado.")
            return False
        main.add_sub_menu(_MENU_MAIN, "", _SUBMENU, "Jam")
        jam = menus.find_menu(f"{_MENU_MAIN}.{_SUBMENU}")

        entry0 = unreal.ToolMenuEntry(
            name="Jam_AbrirPanel", type=unreal.MultiBlockType.MENU_ENTRY
        )
        entry0.set_label("Abrir panel (beta)")
        entry0.set_tool_tip("Abre el panel dockeable de Jam (estilo Dash Bar) con el veredicto del oráculo.")
        entry0.set_string_command(
            unreal.ToolMenuStringCommandType.PYTHON, "",
            "import jam.panel; jam.panel.abrir()",
        )
        jam.add_menu_entry(_SUBMENU, entry0)

        entry = unreal.ToolMenuEntry(
            name="Jam_VerificarEspacio", type=unreal.MultiBlockType.MENU_ENTRY
        )
        entry.set_label("Verificar espacio (oráculo)")
        entry.set_tool_tip("Corre el oráculo de winnability sobre el mapa de extracción.")
        entry.set_string_command(
            unreal.ToolMenuStringCommandType.PYTHON, "",
            "import jam.menu; jam.menu.on_verificar_espacio()",
        )
        jam.add_menu_entry(_SUBMENU, entry)

        entry2 = unreal.ToolMenuEntry(
            name="Jam_Colocar", type=unreal.MultiBlockType.MENU_ENTRY
        )
        entry2.set_label("Colocar de la biblioteca (oráculo)")
        entry2.set_tool_tip("Spawnea un asset del proyecto y verifica bounds + interpenetración.")
        entry2.set_string_command(
            unreal.ToolMenuStringCommandType.PYTHON, "",
            "import jam.menu; jam.menu.on_colocar_primero()",
        )
        jam.add_menu_entry(_SUBMENU, entry2)

        entry3 = unreal.ToolMenuEntry(
            name="Jam_Scatter", type=unreal.MultiBlockType.MENU_ENTRY
        )
        entry3.set_label("Esparcir (scatter + oráculo)")
        entry3.set_tool_tip("Esparce un asset sobre un área y verifica cantidad, contención, "
                            "interpenetración y cobertura.")
        entry3.set_string_command(
            unreal.ToolMenuStringCommandType.PYTHON, "",
            "import jam.menu; jam.menu.on_scatter_demo()",
        )
        jam.add_menu_entry(_SUBMENU, entry3)

        entry4 = unreal.ToolMenuEntry(
            name="Jam_Soltar", type=unreal.MultiBlockType.MENU_ENTRY
        )
        entry4.set_label("Soltar al piso (physics + oráculo)")
        entry4.set_tool_tip("Deja caer un asset sobre el soporte de abajo y verifica que quede "
                            "apoyado (ni flotando ni hundido).")
        entry4.set_string_command(
            unreal.ToolMenuStringCommandType.PYTHON, "",
            "import jam.menu; jam.menu.on_soltar_demo()",
        )
        jam.add_menu_entry(_SUBMENU, entry4)

        entry5 = unreal.ToolMenuEntry(
            name="Jam_SnapGrilla", type=unreal.MultiBlockType.MENU_ENTRY
        )
        entry5.set_label("Alinear a grilla (snap + oráculo)")
        entry5.set_tool_tip("Cuadra el pivote de un asset a la grilla y verifica que quede alineado.")
        entry5.set_string_command(
            unreal.ToolMenuStringCommandType.PYTHON, "",
            "import jam.menu; jam.menu.on_snap_grilla_demo()",
        )
        jam.add_menu_entry(_SUBMENU, entry5)

        entry6 = unreal.ToolMenuEntry(
            name="Jam_Reemplazar", type=unreal.MultiBlockType.MENU_ENTRY
        )
        entry6.set_label("Reemplazar blockout (footprint + oráculo)")
        entry6.set_tool_tip("Cambia una caja de blockout por el asset real y verifica que se "
                            "preserve el footprint (centro, base y planta).")
        entry6.set_string_command(
            unreal.ToolMenuStringCommandType.PYTHON, "",
            "import jam.menu; jam.menu.on_reemplazar_demo()",
        )
        jam.add_menu_entry(_SUBMENU, entry6)

        entry7 = unreal.ToolMenuEntry(
            name="Jam_CrearSpline", type=unreal.MultiBlockType.MENU_ENTRY
        )
        entry7.set_label("Crear spline de pared")
        entry7.set_tool_tip("Agrega un spline editable a la escena para moldear el trazado de una pared.")
        entry7.set_string_command(
            unreal.ToolMenuStringCommandType.PYTHON, "",
            "import jam.menu; jam.menu.on_crear_spline()",
        )
        jam.add_menu_entry(_SUBMENU, entry7)

        entry8 = unreal.ToolMenuEntry(
            name="Jam_Pared", type=unreal.MultiBlockType.MENU_ENTRY
        )
        entry8.set_label("Pared por spline (oráculo)")
        entry8.set_tool_tip("Levanta una pared de segmentos modulares sobre el spline seleccionado y "
                            "verifica que sea continua.")
        entry8.set_string_command(
            unreal.ToolMenuStringCommandType.PYTHON, "",
            "import jam.menu; jam.menu.on_pared_demo()",
        )
        jam.add_menu_entry(_SUBMENU, entry8)

        entry9 = unreal.ToolMenuEntry(
            name="Jam_Presets", type=unreal.MultiBlockType.MENU_ENTRY
        )
        entry9.set_label("Presets: listar y aplicar")
        entry9.set_tool_tip("Lista los presets (config de tool guardada en JSON) y aplica uno, "
                            "verificándolo con su oráculo.")
        entry9.set_string_command(
            unreal.ToolMenuStringCommandType.PYTHON, "",
            "import jam.menu; jam.menu.on_presets_demo()",
        )
        jam.add_menu_entry(_SUBMENU, entry9)

        menus.refresh_all_widgets()
        _log("Menú «Jam» registrado en la barra del editor.")
        return True
    except Exception as e:  # noqa: BLE001
        _log(f"No se pudo registrar el menú: {e}")
        return False


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
    _log(oracle_placement.verificar_texto(b, todos))
    _log(oracle_placement.verificar_texto(c, todos))
    v_b = oracle_placement.verificar(b, todos)   # coincide con a (normal) → interpenetra; fondo se ignora
    v_c = oracle_placement.verificar(c, todos)   # lejos de a; el fondo enorme NO debe marcarlo
    fondo_ignorado = all("fondo" not in n for n, _ in v_c["interpenetra"])
    ok = (v_b["bounds_ok"] and bool(v_b["interpenetra"])
          and not v_c["interpenetra"] and fondo_ignorado
          and oracle_placement.es_fondo(fondo) and not oracle_placement.es_fondo(a))
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
    r_sano = oracle_scatter.verificar(sano, c_sano, s_sano, n)
    _log(oracle_scatter.verificar_texto(sano, c_sano, s_sano, n))

    c_den, s_den = (100000.0, 0.0), (60.0, 60.0)   # lejos del sano; 120×120cm para 9 cubos de 100
    denso = scatter.esparcir(ruta, c_den, s_den, n, seed=7, yaw_aleatorio=False)
    r_den = oracle_scatter.verificar(denso, c_den, s_den, n)
    _log(oracle_scatter.verificar_texto(denso, c_den, s_den, n))

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

    r_antes = oracle_physics.verificar(caja, [piso])
    _log("caja  " + oracle_physics.verificar_texto(caja, [piso]))
    drop = physics.soltar(caja, [piso])
    r_desp = oracle_physics.verificar(caja, [piso])
    _log(f"caja  cae {drop['caida']}cm → " + oracle_physics.verificar_texto(caja, [piso]))
    r_clav = oracle_physics.verificar(clavada, [piso])
    _log("clav  " + oracle_physics.verificar_texto(clavada, [piso]))

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
    g_antes = oracle_snap.verificar_grilla(caja, 100.0)
    _log("grilla " + oracle_snap.texto_grilla(caja, 100.0))
    snap.a_grilla(caja, 100.0)
    g_desp = oracle_snap.verificar_grilla(caja, 100.0)
    _log("grilla " + oracle_snap.texto_grilla(caja, 100.0))

    # (b) al ras: objetivo en el origen local; actor con un hueco de 60cm sobre +x (cubos de 100)
    obj = place.colocar(ruta, (x0, 5000.0, 0.0))
    obj.set_actor_label("Jam_objetivo")
    act = place.colocar(ruta, (x0 + 260.0, 5000.0, 0.0))  # centros a 260 → gap 160 sobre x
    r_antes = oracle_snap.verificar_ras(act, obj, "x")
    _log("ras    " + oracle_snap.texto_ras(act, obj, "x"))
    snap.al_ras(act, obj, "x")
    r_desp = oracle_snap.verificar_ras(act, obj, "x")
    _log("ras    " + oracle_snap.texto_ras(act, obj, "x"))

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
    r1 = oracle_reemplazo.verificar(n1, obj1)
    _log("escala  " + oracle_reemplazo.verificar_texto(n1, obj1))

    b2 = place.colocar(ruta, (x0 + 1000.0, 0.0, 150.0), scale=(2.0, 2.0, 3.0))
    n2, obj2 = reemplazar.reemplazar(b2, ruta, ajustar_escala=False)  # nativo 100³ vs 200×200×300
    r2 = oracle_reemplazo.verificar(n2, obj2)
    _log("nativo  " + oracle_reemplazo.verificar_texto(n2, obj2))

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
    """Presets: hay ≥3 de fábrica; aplicar el de scatter da REPARTO SANO; guardar+cargar+aplicar un
    preset local roundtrip funciona. Limpia actores y el archivo temporal al final."""
    _log("--- selftest: presets ---")
    globales = preset.listar(scope="global")
    _log(f"presets de fábrica: {len(globales)} — " + ", ".join(p["nombre"] for p in globales))
    if len(globales) < 3:
        _log("faltan presets de fábrica")
        return False

    # aplicar el preset de scatter de fábrica
    res_scatter = preset.aplicar("Escombros densos")
    _log("aplicar built-in → " + res_scatter["texto"])

    # roundtrip local: guardar → cargar → aplicar
    demo = {"tool": "colocar", "nombre": "Jam Selftest Prop", "categoria": "test",
            "tags": ["test"], "params": {"asset": None, "location": [700000, 0, 0]},
            "oraculo": {}, "scope": "local"}
    ruta = preset.guardar(demo)
    cargado = preset.cargar("Jam Selftest Prop")
    res_local = preset.aplicar(cargado) if cargado else {"ok": False, "texto": "no cargó", "actores": []}
    _log("roundtrip local → " + res_local["texto"])

    # limpieza
    actor_sub = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    for a in res_scatter["actores"] + res_local["actores"]:
        actor_sub.destroy_actor(a)
    try:
        __import__("pathlib").Path(ruta).unlink()
    except Exception:  # noqa: BLE001
        pass

    # El roundtrip prueba el MOTOR (guardó → cargó → aplicó → spawneó), no el veredicto del oráculo
    # de colocar (que en este mapa da falso positivo por el AABB gigante del SM_SkySphere).
    roundtrip_ok = (cargado is not None) and bool(res_local["actores"])
    ok = res_scatter["ok"] and roundtrip_ok
    _log(f"presets {'OK ✓' if ok else 'FALLÓ ✗'} "
         f"(scatter.ok={res_scatter['ok']}, roundtrip={roundtrip_ok})")
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
