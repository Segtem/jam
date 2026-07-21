"""El panel de Jam — una ventana dockeable estilo "Dash Bar", pero con el veredicto del oráculo.

Frontera de UMG-desde-Python en UE 5.7 (medida con sonda): se puede CREAR el EditorUtilityWidget por
Python y CABLEAR botones en runtime (`Button.on_clicked.add_callable`), pero NO poblar el árbol de
widgets (`WidgetTree` es protegido). Por eso el LAYOUT se arma una vez en el editor (un VerticalBox con
botones y un TextBlock, con nombres convenidos) y TODO lo demás vive acá en Python:

  - `crear_asset_panel()` crea el shell del EUW en `/Jam/UI/WBP_JamPanel` (idempotente).
  - `abrir()` spawnea/registra el tab y cablea cada botón a su acción de `jam.menu`, mandando el
    veredicto al TextBlock `txt_veredicto` en vez de a un modal.

Convención de nombres de widgets a poner en el layout (los que falten se saltean, sin romper):
  btn_verificar · btn_colocar · btn_scatter · btn_soltar · btn_grilla · btn_reemplazar ·
  btn_spline · btn_pared · txt_veredicto
"""

from __future__ import annotations

import unreal

RUTA_DIR = "/Jam/UI"
RUTA_BP = "/Jam/UI/WBP_JamPanel"

# (nombre de widget en el layout, función de jam.menu que ejecuta)
_ACCIONES = [
    ("btn_verificar", "on_verificar_espacio"),
    ("btn_colocar", "on_colocar_primero"),
    ("btn_scatter", "on_scatter_demo"),
    ("btn_soltar", "on_soltar_demo"),
    ("btn_grilla", "on_snap_grilla_demo"),
    ("btn_reemplazar", "on_reemplazar_demo"),
    ("btn_spline", "on_crear_spline"),
    ("btn_pared", "on_pared_demo"),
]

# Mantener vivos los handlers cableados (si no, el GC de Python los suelta y el delegate queda muerto).
_HANDLERS: list = []


def crear_asset_panel():
    """Crea (si no existe) el EditorUtilityWidget shell en RUTA_BP y lo devuelve."""
    bp = unreal.load_asset(RUTA_BP)
    if bp is not None:
        return bp
    tools = unreal.AssetToolsHelpers.get_asset_tools()
    factory = unreal.EditorUtilityWidgetBlueprintFactory()
    bp = tools.create_asset("WBP_JamPanel", RUTA_DIR, None, factory)
    if bp is not None:
        unreal.EditorAssetLibrary.save_loaded_asset(bp)
        unreal.log(f"[Jam] panel: asset creado en {RUTA_BP} (armá el layout en el editor)")
    else:
        unreal.log_error("[Jam] panel: no se pudo crear el asset del panel")
    return bp


def _cablear(widget) -> int:
    """Cablea cada botón presente en el layout a su acción, mandando el veredicto al TextBlock."""
    from . import menu

    txt = widget.find_child_widget_by_name("txt_veredicto")

    def hacer(fn_name):
        def handler():
            menu._SILENCIAR_DIALOGO = True
            try:
                cuerpo = getattr(menu, fn_name)()
            except Exception as e:  # noqa: BLE001
                cuerpo = f"[error] {type(e).__name__}: {e}"
            finally:
                menu._SILENCIAR_DIALOGO = False
            if txt is not None:
                txt.set_text(cuerpo)
        return handler

    _HANDLERS.clear()
    n = 0
    for bname, fn_name in _ACCIONES:
        b = widget.find_child_widget_by_name(bname)
        if b is None:
            continue
        try:
            h = hacer(fn_name)
            _HANDLERS.append(h)
            b.on_clicked.add_callable(h)
            n += 1
        except Exception as e:  # noqa: BLE001
            unreal.log_error(f"[Jam] panel: no pude cablear «{bname}»: {e}")
    if txt is not None:
        txt.set_text(f"Jam · {n} herramientas listas — elegí una y mirá el veredicto del oráculo.")
    unreal.log(f"[Jam] panel: {n} botones cableados"
               + ("" if txt is not None else " (falta el TextBlock txt_veredicto)"))
    return n


def abrir():
    """Crea/abre el panel de Jam como tab dockeable y cablea sus botones. Devuelve el widget."""
    bp = crear_asset_panel()
    if bp is None:
        return None
    sub = unreal.get_editor_subsystem(unreal.EditorUtilitySubsystem)
    try:
        widget = sub.spawn_and_register_tab(bp)
    except Exception as e:  # noqa: BLE001
        unreal.log_error(f"[Jam] panel: spawn_and_register_tab FALLO: {e}")
        return None
    if widget is None:
        unreal.log_error("[Jam] panel: el tab no devolvió widget (¿headless sin Slate?)")
        return None
    _cablear(widget)
    return widget
