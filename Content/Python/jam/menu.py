"""El menú "Jam" en el editor de Unreal + las acciones que dispara.

Registra un menú de nivel superior con `unreal.ToolMenus`. Por ahora una acción:
"Verificar espacio (oráculo)" — corre el oráculo de winnability sobre los mapas demo
de BotOO y muestra el veredicto. Todo defensivo: en headless (sin widgets) el registro
del menú se saltea y el veredicto va al log en vez de a un diálogo modal.
"""

from __future__ import annotations

import unreal

from . import oracle_espacio

_MENU_MAIN = "LevelEditor.MainMenu"
_SUBMENU = "Jam"
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
    """Corre el oráculo sobre el mapa BotOO sano y el roto; reporta ambos veredictos."""
    sano = oracle_espacio.veredicto_texto("BotOO sano", oracle_espacio.mapa_botoo_ganable())
    roto = oracle_espacio.veredicto_texto("BotOO roto", oracle_espacio.mapa_botoo_roto())
    ctx = contexto_editor()
    cuerpo = f"{sano}\n\n{roto}\n\nEditor: {ctx}"
    _log("Verificar espacio →")
    _log(cuerpo)
    _mostrar_dialogo("Jam · Oráculo de espacio", cuerpo)
    return cuerpo


def _mostrar_dialogo(titulo: str, cuerpo: str) -> None:
    """Diálogo modal si hay GUI; en headless no hace nada (ya se logueó)."""
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
        menus.refresh_all_widgets()
        _log("Menú «Jam» registrado en la barra del editor.")
        return True
    except Exception as e:  # noqa: BLE001
        _log(f"No se pudo registrar el menú: {e}")
        return False


# ---- selftest headless (para verificar la rebanada sin GUI) ----

def selftest() -> bool:
    """Prueba la rebanada entera sin GUI: el oráculo corre, el sano es ganable, el roto no.
    Se invoca headless con `-ExecCmds "py import jam.menu; jam.menu.selftest()"`."""
    _log("=== SELFTEST ===")
    r_sano = oracle_espacio.veredicto(oracle_espacio.mapa_botoo_ganable())
    r_roto = oracle_espacio.veredicto(oracle_espacio.mapa_botoo_roto())
    _log(oracle_espacio.veredicto_texto("BotOO sano", oracle_espacio.mapa_botoo_ganable()))
    _log(oracle_espacio.veredicto_texto("BotOO roto", oracle_espacio.mapa_botoo_roto()))
    _log(f"contexto: {contexto_editor()}")
    ok = bool(r_sano["solvable"]) and not bool(r_roto["solvable"])
    _log(f"SELFTEST {'OK ✓' if ok else 'FALLÓ ✗'} "
         f"(sano.solvable={r_sano['solvable']}, roto.solvable={r_roto['solvable']})")
    return ok
