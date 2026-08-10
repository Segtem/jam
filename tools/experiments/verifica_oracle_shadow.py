"""Verifica la sombra de Oracle por el camino real del editor completo.

`PlacementSubsystem` no existe en `-run=pythonscript`, por lo que este script se ejecuta con
`UnrealEditor`, no con `UnrealEditor-Cmd`:

    UnrealEditor BotOO.uproject \
      -ExecutePythonScript=/ruta/absoluta/verifica_oracle_shadow.py \
      -RenderOffScreen -unattended -nosplash -stdout

El marcador funcional se escribe antes de pedir la salida. El código del proceso se juzga aparte:
una prueba anterior completó placement+snap y luego cayó durante el desmontaje del editor.
"""

from __future__ import annotations

import traceback

import unreal


MARCADOR = "JAM_ORACLE_SHADOW_58"


def main() -> None:
    try:
        from jam import menu

        placement = menu.selftest_colocar()
        snap = menu.selftest_snap()
        scatter = menu.selftest_scatter()
        spline = menu.selftest_spline_modular()
        physics = menu.selftest_physics()
        reemplazo = menu.selftest_reemplazo()
        espacio = menu.selftest_nivel()
        if placement and snap and scatter and spline and physics and reemplazo and espacio:
            unreal.log(
                f"{MARCADOR} TODO VERDE — placement={placement} snap={snap} "
                f"scatter={scatter} spline={spline} physics={physics} "
                f"reemplazo={reemplazo} espacio={espacio} por UE 5.8.1")
        else:
            unreal.log_error(
                f"{MARCADOR} ROJO — placement={placement} snap={snap} "
                f"scatter={scatter} spline={spline} physics={physics} "
                f"reemplazo={reemplazo} espacio={espacio} por UE 5.8.1")
    except Exception as exc:  # noqa: BLE001 — el log del editor es el veredicto reproducible
        unreal.log_error(f"{MARCADOR} EXCEPCIÓN — {type(exc).__name__}: {exc}")
        unreal.log_error(traceback.format_exc())
    finally:
        unreal.SystemLibrary.quit_editor()


main()
