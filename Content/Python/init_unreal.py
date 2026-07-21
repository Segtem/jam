"""Arranque del plugin Jam — lo corre PythonScriptPlugin al iniciar el editor.

PythonScriptPlugin agrega `<plugin>/Content/Python/` al sys.path y ejecuta este
archivo en cada plugin habilitado. Acá cableamos el oráculo y registramos el menú.
Todo defensivo: si algo falla, se loguea y el editor sigue arrancando.
"""

import unreal

try:
    from jam import bridge, menu

    bridge.ensure_oraculo_on_path()
    unreal.log(f"[Jam] plugin v{__import__('jam').__version__} — oráculo en {bridge.PLUGIN_ROOT}")
    menu.register()
except Exception as e:  # noqa: BLE001
    unreal.log_error(f"[Jam] fallo en el arranque: {e}")
    import traceback
    unreal.log_error(traceback.format_exc())
