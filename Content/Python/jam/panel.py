"""El panel de Jam — una ventana dockeable estilo "Dash Bar", pero con el veredicto del oráculo.

Frontera de UMG-desde-Python en UE 5.7 (medida con sonda): se puede CREAR el EditorUtilityWidget por
Python y CABLEAR botones/leer campos en runtime, pero NO poblar el árbol de widgets (`WidgetTree` es
protegido). Por eso el LAYOUT se arma una vez en el editor con nombres convenidos y TODO lo demás vive
acá en Python: cablear botones, LEER los campos de parámetros, poblar el Preset Library y el picker de
assets (el "Content Browser" del panel), y ENCHUFAR el asset elegido a cada herramienta.

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
  Content Browser / picker de assets (Fase C · Tier 1):
            in_buscar (EditableTextBox) · btn_buscar (Button) · cmb_asset (ComboBox String)
            El asset elegido en cmb_asset alimenta colocar/scatter/física/snap/reemplazar/pared.
            Si el picker no está en el layout, todo cae al primer asset de la biblioteca (compat).
"""

from __future__ import annotations

import unreal

from . import preset

RUTA_DIR = "/Jam/UI"
RUTA_BP = "/Jam/UI/WBP_JamPanel"

# Mantener vivos los handlers cableados (si no, el GC de Python los suelta y el delegate queda muerto).
_HANDLERS: list = []

# Picker de assets: etiqueta mostrada en cmb_asset → ObjectPath cargable. Se rearma en cada búsqueda.
_ASSET_MAP: dict[str, str] = {}

# Preview → Submit: las herramientas spawnean primero como PREVIEW (con veredicto); recién «Confirmar»
# las fija o «Descartar» las borra. `_PREVIEW` = actores del preview activo (una preview a la vez).
_PREVIEW: list = []
_TAG_PREVIEW = "jam:preview"


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


def _texto(widget, name: str, default: str = "") -> str:
    w = widget.find_child_widget_by_name(name)
    if w is None or not hasattr(w, "get_text"):
        return default
    try:
        return str(w.get_text()).strip()
    except Exception:  # noqa: BLE001
        return default


def _asset_biblioteca():
    from . import library
    libro = library.buscar(limit=1)
    return libro[0]["ruta"] if libro else None


# ---- Content Browser / picker de assets ----

def _poblar_assets(widget) -> int:
    """Llena cmb_asset con los StaticMesh del proyecto que matchean in_buscar. Devuelve cuántos."""
    cmb = widget.find_child_widget_by_name("cmb_asset")
    if cmb is None:
        return 0
    from . import library
    query = _texto(widget, "in_buscar", "")
    resultados = library.buscar(query, limit=50)
    _ASSET_MAP.clear()
    try:
        cmb.clear_options()
        for r in resultados:
            etiqueta = r["nombre"]
            # nombres repetidos → desambiguar con la carpeta contenedora para no pisar la ruta
            if etiqueta in _ASSET_MAP:
                carpeta = r["ruta"].rsplit("/", 1)[0].rsplit("/", 1)[-1]
                etiqueta = f"{r['nombre']}  ({carpeta})"
            _ASSET_MAP[etiqueta] = r["ruta"]
            cmb.add_option(etiqueta)
        if resultados:
            cmb.set_selected_index(0)
        return len(resultados)
    except Exception as e:  # noqa: BLE001
        unreal.log_error(f"[Jam] panel: poblar assets FALLO: {e}")
        return 0


def _asset_elegido(widget) -> str | None:
    """ObjectPath del asset elegido en cmb_asset; si no hay picker/selección, el primero de la biblioteca."""
    cmb = widget.find_child_widget_by_name("cmb_asset")
    if cmb is not None:
        try:
            etiqueta = str(cmb.get_selected_option()).strip()
            if etiqueta in _ASSET_MAP:
                return _ASSET_MAP[etiqueta]
        except Exception:  # noqa: BLE001
            pass
    return _asset_biblioteca()


def _nombre_corto(ruta: str) -> str:
    return ruta.rsplit(".", 1)[-1] if ruta else "asset"


# ---- Preview → Submit (spawnear con veredicto, después Confirmar o Descartar) ----

def _actor_sub():
    return unreal.get_editor_subsystem(unreal.EditorActorSubsystem)


def _todos():
    return _actor_sub().get_all_level_actors()


def _tags_de(actor) -> list[str]:
    try:
        return [str(t) for t in actor.get_editor_property("tags")]
    except Exception:  # noqa: BLE001
        return []


def _set_tags(actor, tags: list[str]) -> None:
    try:
        actor.set_editor_property("tags", [unreal.Name(t) for t in tags])
    except Exception:  # noqa: BLE001
        pass


def _marcar_preview(actores) -> None:
    for a in actores:
        tags = _tags_de(a)
        if _TAG_PREVIEW not in tags:
            _set_tags(a, tags + [_TAG_PREVIEW])
    _PREVIEW.extend(actores)


def _descartar_preview() -> int:
    """Borra los actores del preview activo. Devuelve cuántos."""
    ed, n = _actor_sub(), 0
    for a in _PREVIEW:
        try:
            ed.destroy_actor(a)
            n += 1
        except Exception:  # noqa: BLE001
            pass
    _PREVIEW.clear()
    return n


def _limpiar_huerfanos() -> int:
    """Borra restos jam:preview de sesiones cerradas sin confirmar/descartar. Devuelve cuántos."""
    ed, n = _actor_sub(), 0
    for a in _todos():
        if _TAG_PREVIEW in _tags_de(a):
            try:
                ed.destroy_actor(a)
                n += 1
            except Exception:  # noqa: BLE001
                pass
    return n


def _preview(fn, widget) -> str:
    """Corre una herramienta como PREVIEW: descarta el preview anterior, spawnea, y captura por
    diff del nivel todo lo que la herramienta agregó (así Descartar limpia hasta los helpers)."""
    _descartar_preview()
    antes = {a.get_path_name() for a in _todos()}
    texto = fn(widget)
    nuevos = [a for a in _todos() if a.get_path_name() not in antes]
    _marcar_preview(nuevos)
    return (f"{texto}\n\nPREVIEW · {len(nuevos)} piezas en escena — "
            "«Confirmar» las fija · «Descartar» las borra.")


def _h_confirmar(widget) -> str:
    if not _PREVIEW:
        return "no hay preview activa para confirmar."
    n = len(_PREVIEW)
    for a in _PREVIEW:
        _set_tags(a, [t for t in _tags_de(a) if t != _TAG_PREVIEW])
    _PREVIEW.clear()
    return f"CONFIRMADO ✓ — {n} piezas fijadas en el nivel."


def _h_descartar(widget) -> str:
    n = _descartar_preview()
    return f"descartado ✗ — {n} piezas borradas." if n else "no hay preview activa para descartar."


# Botones cuyo spawn pasa por preview (los demás corren directo).
_PREVIEW_BOTONES = {"btn_colocar", "btn_scatter", "btn_soltar", "btn_grilla",
                    "btn_reemplazar", "btn_pared"}


def _h_buscar(widget) -> str:
    n = _poblar_assets(widget)
    q = _texto(widget, "in_buscar", "")
    detalle = f"«{q}»" if q else "(todos)"
    return f"Content Browser: {n} StaticMesh para {detalle}. Elegí uno y usá cualquier herramienta."


# ---- handlers param-aware (leen campos + asset del widget; defaults = los de las demos) ----

def _h_colocar(widget) -> str:
    from . import oracle_placement, place
    asset = _asset_elegido(widget)
    if not asset:
        return "biblioteca vacía"
    actor = place.colocar(asset, (0.0, 0.0, 0.0))
    if actor is None:
        return f"no se pudo colocar {_nombre_corto(asset)}"
    otros = unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors()
    return oracle_placement.verificar_texto(actor, otros)


def _h_scatter(widget) -> str:
    from . import oracle_scatter, scatter
    asset = _asset_elegido(widget)
    if not asset:
        return "biblioteca vacía"
    cant = int(_num(widget, "in_cantidad", 9))
    area = _num(widget, "in_area", 500.0)
    seed = int(_num(widget, "in_seed", 7))
    centro, semi = (0.0, 0.0), (area, area)
    actores = scatter.esparcir(asset, centro, semi, cant, seed=seed)
    return oracle_scatter.verificar_texto(actores, centro, semi, cant)


def _h_soltar(widget) -> str:
    from . import oracle_physics, physics, place
    asset = _asset_elegido(widget)
    if not asset:
        return "biblioteca vacía"
    piso = place.colocar(asset, (0.0, 0.0, 0.0), scale=(50.0, 50.0, 1.0))
    piso.set_actor_label("Jam_piso")
    caja = place.colocar(asset, (0.0, 0.0, 800.0))
    r = physics.soltar(caja, [piso])
    return f"cae {r['caida']}cm → " + oracle_physics.verificar_texto(caja, [piso])


def _h_grilla(widget) -> str:
    from . import oracle_snap, place, snap
    asset = _asset_elegido(widget)
    if not asset:
        return "biblioteca vacía"
    grilla = _num(widget, "in_grilla", 100.0)
    caja = place.colocar(asset, (137.4, 62.9, 11.1), (0.0, 0.0, 37.0))
    snap.a_grilla(caja, grilla)
    return oracle_snap.texto_grilla(caja, grilla)


def _h_reemplazar(widget) -> str:
    from . import oracle_reemplazo, place, reemplazar
    asset = _asset_elegido(widget)
    if not asset:
        return "biblioteca vacía"
    blockout = place.colocar(asset, (0.0, 0.0, 150.0), scale=(2.0, 2.0, 3.0))
    blockout.set_actor_label("Jam_blockout")
    nuevo, objetivo = reemplazar.reemplazar(blockout, asset, ajustar_escala=True)
    return oracle_reemplazo.verificar_texto(nuevo, objetivo)


def _h_pared(widget) -> str:
    from . import oracle_pared, pared
    asset = _asset_elegido(widget)
    if not asset:
        return "biblioteca vacía"
    actor = pared.seleccionado_con_spline() or pared.crear_spline()
    build = pared.construir(actor, asset,
                            alto=_num(widget, "in_alto", 300.0),
                            espesor=_num(widget, "in_espesor", 40.0),
                            largo_segmento=_num(widget, "in_largo_seg", 200.0))
    return oracle_pared.verificar_texto(build)


def _mapa_handlers() -> dict:
    """Nombre de botón → handler(widget) → texto de veredicto. Todos usan el asset elegido."""
    from . import menu
    return {
        "btn_verificar": lambda w: menu.on_verificar_espacio(),  # lee el nivel, no usa asset
        "btn_colocar": _h_colocar,
        "btn_scatter": _h_scatter,
        "btn_soltar": _h_soltar,
        "btn_grilla": _h_grilla,
        "btn_reemplazar": _h_reemplazar,
        "btn_spline": lambda w: menu.on_crear_spline(),          # sólo crea el spline
        "btn_pared": _h_pared,
        "btn_buscar": _h_buscar,
        "btn_confirmar": _h_confirmar,
        "btn_descartar": _h_descartar,
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
    """Cablea botones + preset library + picker de assets, mandando cada veredicto a txt_veredicto."""
    txt = widget.find_child_widget_by_name("txt_veredicto")

    def _correr(fn, previa=False):
        from . import menu

        def handler():
            menu._SILENCIAR_DIALOGO = True
            try:
                cuerpo = _preview(fn, widget) if previa else fn(widget)
            except Exception as e:  # noqa: BLE001
                cuerpo = f"[error] {type(e).__name__}: {e}"
            finally:
                menu._SILENCIAR_DIALOGO = False
            if txt is not None:
                txt.set_text(cuerpo)
        return handler

    _limpiar_huerfanos()  # restos de previews no resueltas de sesiones anteriores
    _PREVIEW.clear()
    _HANDLERS.clear()
    n = 0
    for bname, fn in _mapa_handlers().items():
        b = widget.find_child_widget_by_name(bname)
        if b is None:
            continue
        try:
            h = _correr(fn, previa=(bname in _PREVIEW_BOTONES))
            _HANDLERS.append(h)
            b.on_clicked.add_callable(h)
            n += 1
        except Exception as e:  # noqa: BLE001
            unreal.log_error(f"[Jam] panel: no pude cablear «{bname}»: {e}")

    # Preset Library (aplicar un preset también es un spawn → pasa por preview)
    n_presets = _poblar_presets(widget)
    btn_ap = widget.find_child_widget_by_name("btn_aplicar_preset")
    if btn_ap is not None:
        try:
            h = _correr(_h_aplicar_preset, previa=True)
            _HANDLERS.append(h)
            btn_ap.on_clicked.add_callable(h)
        except Exception as e:  # noqa: BLE001
            unreal.log_error(f"[Jam] panel: no pude cablear «btn_aplicar_preset»: {e}")

    # Content Browser: poblar el picker con todo el proyecto de arranque
    n_assets = _poblar_assets(widget)

    if txt is not None:
        txt.set_text(f"Jam · {n} herramientas · {n_presets} presets · {n_assets} assets — "
                     "elegí un asset y una herramienta, y mirá el veredicto.")
    unreal.log(f"[Jam] panel: {n} botones cableados, {n_presets} presets, {n_assets} assets"
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
