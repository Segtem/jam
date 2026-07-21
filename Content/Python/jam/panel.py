"""El panel de Jam — una ventana dockeable estilo "Dash Bar", pero con el veredicto del oráculo.

Frontera de UMG-desde-Python en UE 5.7 (medida con sonda): se puede CREAR el EditorUtilityWidget por
Python y CABLEAR botones/leer campos en runtime, pero NO poblar el árbol de widgets (`WidgetTree` es
protegido). Por eso el LAYOUT se arma una vez en el editor con nombres convenidos y TODO lo demás vive
acá en Python: cablear botones, LEER los campos de parámetros, y poblar/aplicar el Preset Library.

Widgets del layout (los que falten se saltean, sin romper — el panel se enciende de a poco):
  Botones:  btn_verificar · btn_colocar · btn_scatter · btn_soltar · btn_grilla · btn_reemplazar ·
            btn_spline · btn_pared
  Readout:  txt_veredicto (TextBlock)
  Params (Fase B, EditableTextBox o SpinBox):
            in_cantidad · in_area · in_seed   (scatter)
            in_alto · in_espesor · in_largo_seg (pared)
            in_grilla                          (snap a grilla)
  Presets (Fase B):
            cmb_preset (ComboBox String) · btn_aplicar_preset (Button)
"""

from __future__ import annotations

import unreal

from . import preset

RUTA_DIR = "/Jam/UI"
RUTA_BP = "/Jam/UI/WBP_JamPanel"

# Mantener vivos los handlers cableados (si no, el GC de Python los suelta y el delegate queda muerto).
_HANDLERS: list = []


# ---- lectura de campos de parámetros (defensiva: campo ausente/ilegible → default) ----

def _num(widget, name: str, default: float) -> float:
    w = widget.find_child_widget_by_name(name)
    if w is None:
        return default
    try:
        if hasattr(w, "get_value"):          # SpinBox
            return float(w.get_value())
    except Exception:  # noqa: BLE001
        pass
    try:
        if hasattr(w, "get_text"):           # EditableTextBox
            s = str(w.get_text()).strip().replace(",", ".")
            return float(s) if s else default
    except Exception:  # noqa: BLE001
        pass
    return default


def _asset_biblioteca():
    from . import library
    libro = library.buscar(limit=1)
    return libro[0]["ruta"] if libro else None


# ---- handlers param-aware (leen campos del widget; si faltan usan los defaults de las demos) ----

def _h_scatter(widget) -> str:
    from . import oracle_scatter, scatter
    asset = _asset_biblioteca()
    if not asset:
        return "biblioteca vacía"
    cant = int(_num(widget, "in_cantidad", 9))
    area = _num(widget, "in_area", 500.0)
    seed = int(_num(widget, "in_seed", 7))
    centro, semi = (0.0, 0.0), (area, area)
    actores = scatter.esparcir(asset, centro, semi, cant, seed=seed)
    return oracle_scatter.verificar_texto(actores, centro, semi, cant)


def _h_pared(widget) -> str:
    from . import oracle_pared, pared
    asset = _asset_biblioteca()
    if not asset:
        return "biblioteca vacía"
    actor = pared.seleccionado_con_spline() or pared.crear_spline()
    build = pared.construir(actor, asset,
                            alto=_num(widget, "in_alto", 300.0),
                            espesor=_num(widget, "in_espesor", 40.0),
                            largo_segmento=_num(widget, "in_largo_seg", 200.0))
    return oracle_pared.verificar_texto(build)


def _h_grilla(widget) -> str:
    from . import oracle_snap, place, snap
    asset = _asset_biblioteca()
    if not asset:
        return "biblioteca vacía"
    grilla = _num(widget, "in_grilla", 100.0)
    caja = place.colocar(asset, (137.4, 62.9, 11.1), (0.0, 0.0, 37.0))
    snap.a_grilla(caja, grilla)
    return oracle_snap.texto_grilla(caja, grilla)


def _mapa_handlers() -> dict:
    """Nombre de botón → handler(widget) → texto de veredicto. Los que no usan params delegan al menú."""
    from . import menu
    return {
        "btn_verificar": lambda w: menu.on_verificar_espacio(),
        "btn_colocar": lambda w: menu.on_colocar_primero(),
        "btn_scatter": _h_scatter,
        "btn_soltar": lambda w: menu.on_soltar_demo(),
        "btn_grilla": _h_grilla,
        "btn_reemplazar": lambda w: menu.on_reemplazar_demo(),
        "btn_spline": lambda w: menu.on_crear_spline(),
        "btn_pared": _h_pared,
    }


# ---- Preset Library ----

def _poblar_presets(widget) -> int:
    cmb = widget.find_child_widget_by_name("cmb_preset")
    if cmb is None:
        return 0
    try:
        cmb.clear_options()
        presets = preset.listar()
        for p in presets:
            cmb.add_option(f"{p['nombre']}  ·  {p['tool']}")
        if presets:
            cmb.set_selected_index(0)
        return len(presets)
    except Exception as e:  # noqa: BLE001
        unreal.log_error(f"[Jam] panel: poblar presets FALLO: {e}")
        return 0


def _h_aplicar_preset(widget) -> str:
    cmb = widget.find_child_widget_by_name("cmb_preset")
    if cmb is None:
        return "no hay selector de presets (cmb_preset) en el layout"
    etiqueta = str(cmb.get_selected_option())
    nombre = etiqueta.split("  ·  ")[0].strip()
    res = preset.aplicar(nombre)
    return res["texto"]


# ---- creación del asset y cableado ----

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
    """Cablea botones + preset library, mandando cada veredicto al TextBlock txt_veredicto."""
    txt = widget.find_child_widget_by_name("txt_veredicto")

    def _correr(fn):
        from . import menu

        def handler():
            menu._SILENCIAR_DIALOGO = True
            try:
                cuerpo = fn(widget)
            except Exception as e:  # noqa: BLE001
                cuerpo = f"[error] {type(e).__name__}: {e}"
            finally:
                menu._SILENCIAR_DIALOGO = False
            if txt is not None:
                txt.set_text(cuerpo)
        return handler

    _HANDLERS.clear()
    n = 0
    for bname, fn in _mapa_handlers().items():
        b = widget.find_child_widget_by_name(bname)
        if b is None:
            continue
        try:
            h = _correr(fn)
            _HANDLERS.append(h)
            b.on_clicked.add_callable(h)
            n += 1
        except Exception as e:  # noqa: BLE001
            unreal.log_error(f"[Jam] panel: no pude cablear «{bname}»: {e}")

    # Preset Library
    n_presets = _poblar_presets(widget)
    btn_ap = widget.find_child_widget_by_name("btn_aplicar_preset")
    if btn_ap is not None:
        try:
            h = _correr(_h_aplicar_preset)
            _HANDLERS.append(h)
            btn_ap.on_clicked.add_callable(h)
        except Exception as e:  # noqa: BLE001
            unreal.log_error(f"[Jam] panel: no pude cablear «btn_aplicar_preset»: {e}")

    if txt is not None:
        txt.set_text(f"Jam · {n} herramientas · {n_presets} presets — elegí una y mirá el veredicto.")
    unreal.log(f"[Jam] panel: {n} botones cableados, {n_presets} presets"
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
