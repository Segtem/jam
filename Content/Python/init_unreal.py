"""Arranque del plugin Jam — lo corre PythonScriptPlugin al iniciar el editor.

PythonScriptPlugin agrega `<plugin>/Content/Python/` al sys.path y ejecuta este
archivo en cada plugin habilitado. Acá sólo cableamos los oráculos al sys.path; la UI
(Dash Bar / Graph) la registra el módulo C++ `JamEditor` en el menú Tools.
Todo defensivo: si algo falla, se loguea y el editor sigue arrancando.
"""

import unreal

try:
    from jam import bridge

    bridge.ensure_oraculo_on_path()
    unreal.log(f"[Jam] plugin v{__import__('jam').__version__} — oráculos en {bridge.PLUGIN_ROOT}")
except Exception as e:  # noqa: BLE001
    unreal.log_error(f"[Jam] fallo en el arranque: {e}")
    import traceback
    unreal.log_error(traceback.format_exc())

# La puerta de los agentes: `jam.web` en 127.0.0.1:8790 (sólo local), con `POST /api/<función>` para
# `jam-mcp` (~/Dev/jam-mcp). Arranca con el editor para que un agente no dependa de que alguien
# abra la UI web a mano. `JAM_WEB=0` lo apaga. Si el puerto está ocupado —otro editor abierto—,
# este editor sigue sin puerta y lo dice.
try:
    import os

    if os.environ.get("JAM_WEB", "1") != "0":
        from jam import web

        web.iniciar()
except OSError as e:
    unreal.log_warning(f"[Jam] web: no pude abrir el puerto ({e}); jam-mcp no va a llegar a este editor")
except Exception as e:  # noqa: BLE001
    unreal.log_error(f"[Jam] web: fallo al arrancar: {e}")
