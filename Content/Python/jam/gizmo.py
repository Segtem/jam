"""Gizmo de Jam — DÓNDE ESTÁ PARADO Jam en el viewport.

Jam trabaja en el punto de mira de la cámara (`place view=true` coloca ahí). Sin una marca visible,
ese punto es invisible y la herramienta se siente a ciegas: es la misma causa del «confirmé y no veo
nada». El gizmo lo hace explícito, y de paso muestra la HUELLA del asset activo — o sea, cuánto va a
ocupar lo que estás por poner, antes de ponerlo.

Sigue el principio de expresividad: grande, de alto contraste, sin sutilezas.

Se dibuja con debug-draw (no ensucia el nivel ni el Outliner) desde un callback de Slate post-tick,
un frame a la vez, así sigue a la cámara en vivo. `gizmo on` / `gizmo off` desde cualquier interfaz.
"""

from __future__ import annotations

import unreal

# color alto contraste: cian para la mira, ámbar para la huella del asset
_CIAN = unreal.LinearColor(0.0, 1.0, 1.0, 1.0)
_AMBAR = unreal.LinearColor(1.0, 0.65, 0.0, 1.0)
_BLANCO = unreal.LinearColor(1.0, 1.0, 1.0, 1.0)

_ESTADO: dict = {"handle": None, "fallos": 0, "medidas": {}}

_RADIO = 60.0        # cm del disco en la superficie
_NORMAL_LARGO = 200.0  # cm del mástil vertical (para verlo desde lejos)


def encendido() -> bool:
    return _ESTADO["handle"] is not None


def _mundo():
    return unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()


def _medidas(ruta: str):
    """(extent, offset_z) del asset activo, cacheado. None si no se puede medir."""
    if ruta in _ESTADO["medidas"]:
        return _ESTADO["medidas"][ruta]
    med = None
    try:
        malla = unreal.load_asset(ruta)
        if isinstance(malla, unreal.StaticMesh):
            caja = malla.get_bounding_box()
            mn, mx = caja.min, caja.max
            med = (unreal.Vector((mx.x - mn.x) / 2.0, (mx.y - mn.y) / 2.0, (mx.z - mn.z) / 2.0),
                   (mx.z + mn.z) / 2.0 - mn.z)
    except Exception:  # noqa: BLE001
        med = None
    _ESTADO["medidas"][ruta] = med
    return med


def _dibujar(_delta=0.0) -> None:
    """Un frame del gizmo. Defensivo: si algo falla repetidamente, se apaga solo (no spamear)."""
    try:
        from . import session, ue
        mira = ue.punto_de_mira()
        if mira is None:
            return
        p, n = mira["punto"], mira["normal"]
        w = _mundo()
        centro = unreal.Vector(p.x, p.y, p.z)
        arriba = unreal.Vector(p.x + n.x * _NORMAL_LARGO,
                               p.y + n.y * _NORMAL_LARGO,
                               p.z + n.z * _NORMAL_LARGO)

        # disco sobre la superficie + mástil en la normal: "acá y así de inclinado"
        unreal.SystemLibrary.draw_debug_circle(
            w, centro, _RADIO, 32, _CIAN, 0.0, 3.0,
            unreal.Vector(1.0, 0.0, 0.0), unreal.Vector(0.0, 1.0, 0.0), False)
        unreal.SystemLibrary.draw_debug_line(w, centro, arriba, _CIAN, 0.0, 3.0)

        # cruz de ejes en el piso (orientación del mundo, para leer yaw de un vistazo)
        unreal.SystemLibrary.draw_debug_line(
            w, unreal.Vector(p.x - _RADIO * 1.6, p.y, p.z), unreal.Vector(p.x + _RADIO * 1.6, p.y, p.z),
            _BLANCO, 0.0, 1.5)
        unreal.SystemLibrary.draw_debug_line(
            w, unreal.Vector(p.x, p.y - _RADIO * 1.6, p.z), unreal.Vector(p.x, p.y + _RADIO * 1.6, p.z),
            _BLANCO, 0.0, 1.5)

        # huella del asset activo: cuánto va a ocupar lo que estás por colocar
        ruta = session.asset()
        etiqueta = session.nombre() or "(sin asset)"
        if ruta:
            med = _medidas(ruta)
            if med is not None:
                ext, dz = med
                unreal.SystemLibrary.draw_debug_box(
                    w, unreal.Vector(p.x, p.y, p.z + ext.z), ext, _AMBAR,
                    unreal.Rotator(0.0, 0.0, 0.0), 0.0, 2.0)
                etiqueta += f"  {ext.x * 2:.0f}×{ext.y * 2:.0f}×{ext.z * 2:.0f}cm"

        unreal.SystemLibrary.draw_debug_string(
            w, unreal.Vector(0.0, 0.0, _NORMAL_LARGO * 1.15),
            f"JAM · ({p.x:.0f}, {p.y:.0f}, {p.z:.0f})\n{etiqueta}", None, _CIAN, 0.0)

        # el viewport del editor sólo repinta cuando algo cambia: forzarlo para que el gizmo siga a
        # la cámara aunque la escena esté quieta.
        try:
            unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).editor_invalidate_viewports()
        except Exception:  # noqa: BLE001
            pass

        _ESTADO["fallos"] = 0
    except Exception as e:  # noqa: BLE001
        _ESTADO["fallos"] += 1
        if _ESTADO["fallos"] >= 5:
            unreal.log_warning(f"[Jam] gizmo apagado tras 5 fallos: {e}")
            apagar()


def encender() -> str:
    if encendido():
        return "el gizmo de Jam ya estaba encendido."
    _ESTADO["fallos"] = 0
    _ESTADO["handle"] = unreal.register_slate_post_tick_callback(_dibujar)
    return ("GIZMO ON ✓ — el disco cian marca dónde está parado Jam (el punto de mira: ahí coloca "
            "«place»); la caja ámbar es la huella del asset activo.")


def apagar() -> str:
    h = _ESTADO["handle"]
    if h is None:
        return "el gizmo de Jam ya estaba apagado."
    try:
        unreal.unregister_slate_post_tick_callback(h)
    except Exception:  # noqa: BLE001
        pass
    _ESTADO["handle"] = None
    return "gizmo OFF — sin marca en el viewport."


def alternar() -> str:
    return apagar() if encendido() else encender()
