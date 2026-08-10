"""Verifica LOD y selección ISM/None con viewer y ticks reales del editor UE 5.8.1.

Se ejecuta con ``UnrealEditor -ExecutePythonScript=... -RenderOffScreen``. El commandlet no sirve:
no bombea la simulación Mass ni ofrece el viewer del viewport que gobierna los LOD.
"""

from __future__ import annotations

import json
import time
import traceback

import unreal


MARCADOR = "JAM_MASS_REPRESENTATION_58"
CONFIG = "/Jam/Mass/MC_JamAmbientISM.MC_JamAmbientISM"
DISTANCES = (500.0, 2500.0, 5000.0, 10000.0)
LIMITE_SEGUNDOS = 25.0
ESTADO = {"desde": time.monotonic(), "ticks": 0, "callback": None, "fase": "iniciar_pie",
          "world": None, "population_id": None, "ultimo": None, "error": None,
          "pie_ticks": 0}


def _facts(raw) -> dict:
    return json.loads(str(raw))


def _terminar() -> None:
    try:
        if ESTADO["world"] is not None and ESTADO["population_id"]:
            unreal.JamMassLibrary.clear_population(ESTADO["world"], ESTADO["population_id"])
    finally:
        if ESTADO["callback"] is not None:
            unreal.unregister_slate_post_tick_callback(ESTADO["callback"])
            ESTADO["callback"] = None
        if ESTADO["error"]:
            unreal.log_error(f"{MARCADOR} ROJO — {ESTADO['error']}")
        else:
            unreal.log(
                f"{MARCADOR} TODO VERDE — High=1 · Medium=1 · Low=1 · Off=1 · "
                "ISM=3 · None=1 · limpieza completa")
        unreal.EditorPythonScripting.set_keep_python_script_alive(False)
        unreal.SystemLibrary.quit_editor()


def _fallar(exc: Exception) -> None:
    ESTADO["error"] = f"{type(exc).__name__}: {exc}\n{traceback.format_exc()}"
    subsystem = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
    if ESTADO["world"] is not None and ESTADO["population_id"]:
        unreal.JamMassLibrary.clear_population(ESTADO["world"], ESTADO["population_id"])
        ESTADO["population_id"] = None
        ESTADO["world"] = None
    if subsystem.is_in_play_in_editor():
        subsystem.editor_request_end_play()
        ESTADO["fase"] = "esperar_fin_con_error"
    else:
        _terminar()


def _tick(_delta_seconds: float) -> None:
    try:
        ESTADO["ticks"] += 1
        editor = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
        level = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
        fase = ESTADO["fase"]

        if fase == "iniciar_pie":
            level.editor_request_begin_play()
            ESTADO["fase"] = "esperar_pie"
            return

        if fase in ("esperar_fin", "esperar_fin_con_error"):
            if level.is_in_play_in_editor() or unreal.EditorLevelLibrary.get_pie_worlds(False):
                return
            _terminar()
            return

        if time.monotonic() - ESTADO["desde"] > LIMITE_SEGUNDOS:
            raise TimeoutError(
                f"MassRepresentation no resolvió los LOD dentro del límite: {ESTADO['ultimo']}")

        pie_worlds = unreal.EditorLevelLibrary.get_pie_worlds(False)
        if not pie_worlds:
            return
        world = pie_worlds[0]
        ESTADO["pie_ticks"] += 1

        if ESTADO["population_id"] is None:
            # El PlayerCameraManager nace antes de que su cache de vista sea definitiva.
            if ESTADO["pie_ticks"] < 20:
                return
            controller = unreal.GameplayStatics.get_player_controller(world, 0)
            if controller is None:
                return
            location, rotation = controller.get_player_view_point()
            forward = unreal.MathLibrary.get_forward_vector(rotation)
            transforms = [unreal.Transform(location=unreal.Vector(
                location.x + forward.x * distance,
                location.y + forward.y * distance,
                location.z + forward.z * distance)) for distance in DISTANCES]
            spawned = _facts(unreal.JamMassLibrary.spawn_configured_population(
                world, transforms, CONFIG))
            if not spawned.get("ok") or spawned.get("valid") != 4:
                raise RuntimeError(f"la población LOD no nació completa: {spawned}")
            ESTADO["world"] = world
            ESTADO["population_id"] = spawned["population_id"]
            ESTADO["fase"] = "esperar_lod"
            return

        inspected = _facts(unreal.JamMassLibrary.inspect_population(
            world, ESTADO["population_id"]))
        ESTADO["ultimo"] = inspected
        expected = {"valid": 4, "lod_high": 1, "lod_medium": 1, "lod_low": 1,
                    "lod_off": 1, "representation_ism": 3, "representation_none": 1,
                    "representation_fragments": 4, "lod_fragments": 4,
                    "mesh_desc_valid": 4}
        defects = {field: (inspected.get(field), value) for field, value in expected.items()
                   if inspected.get(field) != value}
        if defects:
            return
        cleared = _facts(unreal.JamMassLibrary.clear_population(world, ESTADO["population_id"]))
        if cleared.get("valid_before") != 4 or cleared.get("valid_after") != 0:
            raise RuntimeError(f"la población representada no se limpió: {cleared}")
        ESTADO["population_id"] = None
        ESTADO["world"] = None
        level.editor_request_end_play()
        ESTADO["fase"] = "esperar_fin"
    except Exception as exc:  # noqa: BLE001 — el marcador en el log es el veredicto
        _fallar(exc)


unreal.EditorPythonScripting.set_keep_python_script_alive(True)
ESTADO["callback"] = unreal.register_slate_post_tick_callback(_tick)
