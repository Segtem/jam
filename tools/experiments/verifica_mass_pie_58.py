"""Verifica el ciclo de vida de poblaciones Mass durante un PIE real en UE 5.8.1.

No sirve ``-run=pythonscript``: PIE necesita que el editor completo siga bombeando frames. La sonda
mantiene una poblacion en el mundo editor, crea otra dentro del UWorld PIE y termina la sesion. El
contraste exige que ``OnWorldCleanup`` quite solamente la poblacion PIE.

Receta::

    UnrealEditor BotOO.uproject \
      -ExecutePythonScript=/home/workstation/Dev/jam/tools/experiments/verifica_mass_pie_58.py \
      -RenderOffScreen -unattended -nosplash -stdout

El veredicto autoritativo es ``JAM_MASS_PIE_58 TODO VERDE`` en ``BotOO.log``. El desmontaje del
editor completo puede repetir después el ``double free`` histórico ya delimitado en el Vault.
"""

from __future__ import annotations

import json
import time
import traceback

import unreal


MARCADOR = "JAM_MASS_PIE_58"
LIMITE_SEGUNDOS = 120.0
ESTADO = {
    "fase": "iniciar",
    "desde": time.monotonic(),
    "handle_tick": None,
    "editor_world": None,
    "editor_id": None,
    "pie_id": None,
    "error": None,
}


def _facts(raw) -> dict:
    return json.loads(str(raw))


def _transforms() -> list:
    return [
        unreal.Transform(location=unreal.Vector(100.0, 200.0, 300.0)),
        unreal.Transform(location=unreal.Vector(-40.0, 50.0, 60.0)),
        unreal.Transform(location=unreal.Vector(7.0, 8.0, 9.0)),
    ]


def _spawn(world) -> dict:
    facts = _facts(unreal.JamMassLibrary.spawn_population(world, _transforms()))
    if not facts.get("ok") or facts.get("created") != 3 or facts.get("valid") != 3:
        raise RuntimeError(f"la población no nació completa: {facts}")
    return facts


def _inspect(world, population_id: str) -> dict:
    return _facts(unreal.JamMassLibrary.inspect_population(world, population_id))


def _clear_editor() -> None:
    world = ESTADO["editor_world"]
    population_id = ESTADO["editor_id"]
    if world is not None and population_id:
        unreal.JamMassLibrary.clear_population(world, population_id)
        ESTADO["editor_id"] = None


def _terminar() -> None:
    try:
        _clear_editor()
    finally:
        handle = ESTADO["handle_tick"]
        if handle is not None:
            unreal.unregister_slate_post_tick_callback(handle)
            ESTADO["handle_tick"] = None
        error = ESTADO["error"]
        if error:
            unreal.log_error(f"{MARCADOR} ROJO — {error}")
        else:
            unreal.log(
                f"{MARCADOR} TODO VERDE — editor=3 vivas · PIE=3 vivas · "
                "fin PIE liberó sólo su población")
        unreal.EditorPythonScripting.set_keep_python_script_alive(False)
        unreal.SystemLibrary.quit_editor()


def _fallar(exc: Exception) -> None:
    ESTADO["error"] = f"{type(exc).__name__}: {exc}\n{traceback.format_exc()}"
    subsystem = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
    if subsystem.is_in_play_in_editor():
        subsystem.editor_request_end_play()
        ESTADO["fase"] = "esperar_fin_con_error"
    else:
        _terminar()


def _tick(_delta_seconds: float) -> None:
    try:
        if time.monotonic() - ESTADO["desde"] > LIMITE_SEGUNDOS:
            raise TimeoutError(f"PIE no completo el ciclo en {LIMITE_SEGUNDOS:.0f} s")

        subsystem = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
        fase = ESTADO["fase"]
        if fase == "iniciar":
            editor_world = unreal.get_editor_subsystem(
                unreal.UnrealEditorSubsystem).get_editor_world()
            ESTADO["editor_world"] = editor_world
            editor = _spawn(editor_world)
            ESTADO["editor_id"] = editor["population_id"]
            subsystem.editor_play_simulate()
            ESTADO["fase"] = "esperar_pie"
            return

        if fase == "esperar_pie":
            worlds = unreal.EditorLevelLibrary.get_pie_worlds(False)
            if not worlds:
                return
            pie = _spawn(worlds[0])
            ESTADO["pie_id"] = pie["population_id"]
            comprobacion = _inspect(worlds[0], ESTADO["pie_id"])
            if not comprobacion.get("ok") or comprobacion.get("valid") != 3:
                raise RuntimeError(f"la población PIE no quedó viva: {comprobacion}")
            subsystem.editor_request_end_play()
            ESTADO["fase"] = "esperar_fin"
            return

        if fase in ("esperar_fin", "esperar_fin_con_error"):
            if subsystem.is_in_play_in_editor() or unreal.EditorLevelLibrary.get_pie_worlds(False):
                return
            if fase == "esperar_fin_con_error":
                _terminar()
                return

            editor = _inspect(ESTADO["editor_world"], ESTADO["editor_id"])
            if not editor.get("ok") or editor.get("valid") != 3:
                raise RuntimeError(f"cerrar PIE dañó la población del editor: {editor}")
            pie = _inspect(ESTADO["editor_world"], ESTADO["pie_id"])
            if pie.get("ok") or "inexistente o ya liberada" not in pie.get("error", ""):
                raise RuntimeError(f"OnWorldCleanup no liberó la población PIE: {pie}")
            _terminar()
    except Exception as exc:  # noqa: BLE001 — el log del editor es el veredicto reproducible
        _fallar(exc)


unreal.EditorPythonScripting.set_keep_python_script_alive(True)
ESTADO["handle_tick"] = unreal.register_slate_post_tick_callback(_tick)
