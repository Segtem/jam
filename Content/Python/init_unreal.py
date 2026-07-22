"""Arranque del plugin Jam — lo corre PythonScriptPlugin al iniciar el editor.

PythonScriptPlugin agrega `<plugin>/Content/Python/` al sys.path y ejecuta este
archivo en cada plugin habilitado. Acá sólo cableamos el oráculo al sys.path; la UI
(Dash Bar / Graph) la registra el módulo C++ `JamEditor` en el menú Tools.
Todo defensivo: si algo falla, se loguea y el editor sigue arrancando.
"""

import unreal

try:
    from jam import bridge

    bridge.ensure_oraculo_on_path()
    unreal.log(f"[Jam] plugin v{__import__('jam').__version__} — oráculo en {bridge.PLUGIN_ROOT}")
except Exception as e:  # noqa: BLE001
    unreal.log_error(f"[Jam] fallo en el arranque: {e}")
    import traceback
    unreal.log_error(traceback.format_exc())
