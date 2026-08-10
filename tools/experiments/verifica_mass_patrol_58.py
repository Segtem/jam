"""Verifica en PIE la patrulla Mass acotada y su representación ISM dinámica."""

from __future__ import annotations

import json
import time
import traceback

import unreal


MARCADOR = "JAM_MASS_PATROL_58"
CONFIG = "/Jam/Mass/MC_JamAmbientPatrol.MC_JamAmbientPatrol"
LIMITE_SEGUNDOS = 25.0
ESTADO = {"desde": time.monotonic(), "callback": None, "fase": "iniciar_pie",
          "world": None, "population_id": None, "pie_ticks": 0,
          "ultimo": None, "error": None}


def _facts(raw) -> dict:
    return json.loads(str(raw))


def _limpiar() -> None:
    if ESTADO["world"] is not None and ESTADO["population_id"]:
        unreal.JamMassLibrary.clear_population(ESTADO["world"], ESTADO["population_id"])
    ESTADO["population_id"] = None


def _terminar() -> None:
    try:
        _limpiar()
        ESTADO["world"] = None
    finally:
        if ESTADO["callback"] is not None:
            unreal.unregister_slate_post_tick_callback(ESTADO["callback"])
            ESTADO["callback"] = None
        if ESTADO["error"]:
            unreal.log_error(f"{MARCADOR} ROJO — {ESTADO['error']}")
        else:
            unreal.log(
                f"{MARCADOR} TODO VERDE — 4/4 inicializadas · 4/4 movidas · "
                "4/4 revirtieron · radio 25 cm respetado · ISM dinámica 4/4 · limpieza")
        unreal.EditorPythonScripting.set_keep_python_script_alive(False)
        unreal.SystemLibrary.quit_editor()


def _fallar(exc: Exception) -> None:
    ESTADO["error"] = f"{type(exc).__name__}: {exc}\n{traceback.format_exc()}"
    level = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
    _limpiar()
    ESTADO["world"] = None
    if level.is_in_play_in_editor():
        level.editor_request_end_play()
        ESTADO["fase"] = "esperar_fin_con_error"
    else:
        _terminar()


def _tick(_delta_seconds: float) -> None:
    try:
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
            raise TimeoutError(f"la patrulla no produjo actividad medible: {ESTADO['ultimo']}")

        pie_worlds = unreal.EditorLevelLibrary.get_pie_worlds(False)
        if not pie_worlds:
            return
        world = pie_worlds[0]
        ESTADO["world"] = world
        ESTADO["pie_ticks"] += 1
        if ESTADO["pie_ticks"] < 20:
            return

        if ESTADO["population_id"] is None:
            config = _facts(unreal.JamMassLibrary.inspect_config(world, CONFIG))
            expected_config = {"ok": True, "moving_ism": True, "stationary": False,
                               "has_patrol": True, "patrol_speed": 800,
                               "patrol_radius": 25}
            if any(config.get(key) != value for key, value in expected_config.items()):
                raise RuntimeError(f"el config de patrulla no conserva su contrato: {config}")
            controller = unreal.GameplayStatics.get_player_controller(world, 0)
            if controller is None:
                return
            location, rotation = controller.get_player_view_point()
            forward = unreal.MathLibrary.get_forward_vector(rotation)
            transforms = []
            for index, distance in enumerate((200.0, 300.0, 400.0, 500.0)):
                transforms.append(unreal.Transform(
                    location=unreal.Vector(location.x + forward.x * distance,
                                           location.y + forward.y * distance,
                                           location.z + forward.z * distance),
                    rotation=unreal.Rotator(0.0, index * 90.0, 0.0)))
            spawned = _facts(unreal.JamMassLibrary.spawn_configured_population(
                world, transforms, CONFIG))
            if not spawned.get("ok") or spawned.get("valid") != 4:
                raise RuntimeError(f"la patrulla no nació completa: {spawned}")
            ESTADO["population_id"] = spawned["population_id"]
            return

        inspected = _facts(unreal.JamMassLibrary.inspect_population(
            world, ESTADO["population_id"]))
        ESTADO["ultimo"] = inspected
        expected = {"valid": 4, "transform_mismatches": 4,
                    "patrol_fragments": 4, "patrol_initialized": 4,
                    "patrol_moved": 4, "patrol_reversed": 4,
                    "patrol_out_of_bounds": 0, "representation_fragments": 4,
                    "lod_fragments": 4, "mesh_desc_valid": 4,
                    "representation_ism": 4}
        if any(inspected.get(field) != value for field, value in expected.items()):
            return
        if inspected.get("patrol_reversals", 0) < 4:
            return
        if inspected.get("patrol_max_abs_distance", 1000.0) > 25.001:
            raise RuntimeError(f"la patrulla salió del radio declarado: {inspected}")
        cleared = _facts(unreal.JamMassLibrary.clear_population(
            world, ESTADO["population_id"]))
        if cleared.get("valid_before") != 4 or cleared.get("valid_after") != 0:
            raise RuntimeError(f"la patrulla no se limpió: {cleared}")
        ESTADO["population_id"] = None
        ESTADO["world"] = None
        level.editor_request_end_play()
        ESTADO["fase"] = "esperar_fin"
    except Exception as exc:  # noqa: BLE001 — el marcador del log es el veredicto
        _fallar(exc)


unreal.EditorPythonScripting.set_keep_python_script_alive(True)
ESTADO["callback"] = unreal.register_slate_post_tick_callback(_tick)
